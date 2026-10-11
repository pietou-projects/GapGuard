# GapGuard v4.1.0-candidate.10 — SFS calibration and session-scoped fan1 pause handling.
# SPDX-License-Identifier: GPL-3.0-or-later
"""SFS surveillance only. Confirmed fault -> public manufacturer PAUSE.

GapGuard pauses cut hotend/fan1 after native proof; fan1 restores on real resume.
No recovery or motion logic.
All observed E coordinates come from find_past_position().
"""
import collections
import json
import logging
import math

VERSION = '4.1.0-candidate.10'
MODES = ('FULL', 'PARTIAL', 'BYPASS')

def positive(value, name, allow_zero=False):
    value = float(value)
    if not math.isfinite(value) or value < 0 or (not allow_zero and value == 0):
        raise ValueError('%s must be finite and %s' %
                         (name, 'nonnegative' if allow_zero else 'positive'))
    return value

class Settings:
    """SFS monitoring thresholds and acquisition timing only."""
    DEFAULTS = dict(suspect_distance=9., verify_trigger=50., verify_distance=12.,
                    verify_transitions=6, check_interval=.250, init_guard=.250)

    def __init__(self, values, default_mode='FULL'):
        unknown = set(values) - set(self.DEFAULTS)
        if unknown:
            raise ValueError('unknown settings: %s' % sorted(unknown))
        for name, value in dict(self.DEFAULTS, **values).items():
            setattr(self, name, positive(value, name))
        if self.verify_transitions != int(self.verify_transitions):
            raise ValueError('verify_transitions must be an integer')
        self.verify_transitions = int(self.verify_transitions)
        if self.init_guard < .250:
            raise ValueError('init_guard must be >= 0.250 s')
        if self.suspect_distance >= self.verify_trigger:
            raise ValueError('suspect_distance must be below verify_trigger')
        if default_mode not in MODES:
            raise ValueError('invalid default_mode')
        self.default_mode = default_mode


class Native:
    """Read-only file status; no pause_resume transaction ownership."""
    def __init__(self, state='standby', active=False, path=None):
        self.state, self.active, self.path = state, active, path

    def printing(self, path=None):
        return bool(self.state == 'printing' and self.active and self.path
                    and (path is None or path == self.path))

class Motion:
    """Electrical acquisition is separate from transitions and native position."""
    def __init__(self, settings):
        self.s = settings
        self.pd3 = self.pd4 = None
        self.reset()

    def reset(self):
        self.state = 'DISABLED'
        self.reference = self.position = None
        self.verify_start = self.verify_end = None
        self.count = 0
        self.last_edge_position = None

    def arm(self, position):
        self.reset()
        self.reference = self.position = position
        self.state = 'ARMING'

    def acquire(self, mask):
        old = self.pd3
        self.pd3, self.pd4 = mask & 1, (mask >> 1) & 1
        return old is not None and old != self.pd3

    def _enter_verify(self):
        self.state = 'VERIFY_50'
        self.verify_start = self.reference + self.s.verify_trigger
        self.verify_end = self.verify_start + self.s.verify_distance
        self.count = 0

    def edge(self, position):
        self.last_edge_position = position
        if self.state in ('DISABLED', 'HARD'):
            return
        start = self.reference + self.s.verify_trigger
        # Edges at the entry boundary win, even if a timer already opened it.
        if position <= start and (self.state != 'VERIFY_50' or self.count == 0):
            self.reference, self.state = position, 'NORMAL'
            self.verify_start = self.verify_end = None
            return
        if self.state != 'VERIFY_50':
            self._enter_verify()
        if self.verify_start <= position <= self.verify_end:
            self.count += 1
            if self.count >= self.s.verify_transitions:
                self.reference, self.state = position, 'NORMAL'
                self.verify_start = self.verify_end = None

    def observe(self, position, initialized):
        self.position = position
        if self.state in ('DISABLED', 'HARD'):
            return None
        gap = position - self.reference
        if self.state != 'VERIFY_50':
            if gap >= self.s.verify_trigger:
                if self.pd3 is None:
                    if not initialized:
                        return None
                    self.state = 'HARD'
                    return 'PD3_NO_SIGNAL'
                self._enter_verify()
            elif gap >= self.s.suspect_distance:
                self.state = 'SUSPECT'
        if self.state == 'VERIFY_50' and position >= self.verify_end:
            # Candidate fault only. Edges already queued at the exact end may
            # still arrive before the worker commits the native pause.
            return 'VERIFY_FAIL'
        return None


class Machine:
    """SFS policy only. A fault requests the public Elegoo PAUSE once."""
    def __init__(self, settings):
        self.s = settings
        self.motion = Motion(settings)
        self.mode = settings.default_mode
        self.epoch = self.serial = 0
        self.min_eventtime = float('-inf')
        self.min_motion_time = float('-inf')
        self.ready = False
        self.initialized = False
        self.acquire_deadline = None
        self.pending_new = False
        self.last_fault = None
        self._clear()

    def _clear(self):
        self.session = self.running = False
        self.path = None
        self.pause_requested = self.pause_dispatched = False
        self.reason = self.active_fault = self.pause_error = None
        self.motion.reset()

    def token(self):
        return self.epoch, self.serial

    def valid(self, token):
        return self.ready and token == self.token()

    def reset(self, now, pending_new=False, shutdown=False):
        self.epoch += 1
        self.serial += 1
        self.min_eventtime = self.min_motion_time = now
        self._clear()
        self.pending_new = pending_new
        if shutdown:
            self.ready = self.initialized = False
            self.motion.pd3 = self.motion.pd4 = None

    def start_ready(self, now, buttons_oid):
        self.ready = True
        self.acquire_deadline = now + 1.5 + .01 * buttons_oid + self.s.init_guard

    def gpio(self, now, mask, position):
        if not self.ready or now < self.min_eventtime:
            return
        edge = self.motion.acquire(mask)
        self.initialized = True
        if not self.running or self.pause_dispatched:
            return
        if (edge and self.mode == 'FULL' and position is not None
                and now >= self.min_motion_time):
            self.motion.edge(position)
        if self.mode != 'BYPASS' and self.motion.pd4 == 0:
            self.request_pause('PD4_ABSENT')

    def observe(self, now, native, position, evaluate=True):
        if not self.ready:
            return
        if not self.initialized and now >= self.acquire_deadline:
            self.motion.acquire(0)
            self.initialized = True
        terminal = native.state in ('complete', 'cancelled', 'error')
        if self.session and (terminal or native.path != self.path):
            self.reset(now)
        printing = native.printing()
        if not self.session and printing:
            self.serial += 1
            self.session, self.path = True, native.path
            self.pending_new = False
        if not self.session:
            return
        printing = printing and native.path == self.path
        if not printing:
            if self.running:
                self.serial += 1
                self.min_motion_time = now
                self.motion.reset()
                self.pause_requested = self.pause_dispatched = False
                self.reason = None
            self.running = False
            return
        if not self.running:
            self.serial += 1
            self.min_motion_time = now
            self.running = True
            self.pause_requested = self.pause_dispatched = False
            self.reason = self.active_fault = self.pause_error = None
            if self.mode == 'FULL':
                self.motion.arm(position)
        if not evaluate or not self.initialized or self.pause_dispatched:
            return
        if self.mode != 'BYPASS' and self.motion.pd4 == 0:
            self.request_pause('PD4_ABSENT')
        if self.mode == 'FULL' and not self.pause_requested:
            reason = self.motion.observe(position, self.initialized)
            if reason:
                self.request_pause(reason)

    def request_pause(self, reason):
        if not self.running or self.pause_dispatched:
            return False
        # Presence takes precedence over a pending motion-boundary decision.
        if self.pause_requested and reason != 'PD4_ABSENT':
            return False
        if not self.pause_requested or self.reason != reason:
            self.serial += 1
            self.pause_requested = True
            self.reason = reason
        return True

    def claim_pause(self, native):
        if (not self.ready or not self.session or not self.running
                or not self.pause_requested or self.pause_dispatched
                or not native.printing(self.path)):
            return None
        if self.reason == 'VERIFY_FAIL' and self.motion.state == 'NORMAL':
            # Sixth queued edge at the end boundary won before dispatch.
            self.pause_requested = False
            self.reason = None
            return None
        if (self.mode == 'BYPASS'
                or (self.reason != 'PD4_ABSENT' and self.mode != 'FULL')):
            self.pause_requested = False
            self.reason = None
            return None
        fault = 'PD4_ABSENT' if self.reason == 'PD4_ABSENT' else 'PD3_NO_MOTION'
        self.pause_requested = False
        self.pause_dispatched = True
        self.active_fault = self.last_fault = fault
        return fault

    def change_mode(self, mode, position, now):
        if mode not in MODES:
            raise ValueError('invalid mode')
        self.serial += 1
        self.mode = mode
        self.pause_requested = False
        self.reason = None
        self.min_motion_time = now
        if self.running and not self.pause_dispatched and mode == 'FULL':
            self.motion.arm(position)
        else:
            self.motion.reset()

    def status(self, native):
        m = self.motion
        printing = self.session and self.running and native.printing(self.path)
        return dict(version=VERSION, mode=self.mode, cycle=native.state,
                    session_active=self.session, epoch=self.epoch,
                    file_path=self.path, printing=printing,
                    pd3=m.pd3, pd4=m.pd4, initialized=self.initialized,
                    pd3_protection=self.mode == 'FULL',
                    pd4_protection=self.mode != 'BYPASS',
                    pd3_led='UNKNOWN' if m.pd3 is None else 'BLUE' if m.pd3 else 'OFF',
                    monitoring=bool(printing and self.initialized
                                    and self.mode != 'BYPASS' and not self.pause_dispatched),
                    motion_state=m.state,
                    gap=None if m.reference is None or m.position is None else max(0., m.position-m.reference),
                    verify_start=m.verify_start, verify_end=m.verify_end,
                    verify_transitions=m.count, required_transitions=self.s.verify_transitions,
                    paused=bool(self.session and native.path == self.path
                                and native.state == 'paused' and not native.active),
                    pause_requested=self.pause_requested, pause_dispatched=self.pause_dispatched,
                    active_fault=self.active_fault, last_fault=self.last_fault,
                    pause_error=self.pause_error)


def human_reason(reason):
    text = str(reason or '')
    return {
        'PD4_ABSENT': 'filament absent au capteur de présence PD4',
        'PD3_NO_MOTION': 'mouvement de filament non confirmé par PD3',
        'GapGuard not ready': 'GapGuard n’est pas encore prêt',
        'invalid mode': 'mode inconnu',
    }.get(text, 'incident technique ; consulter GAPGUARD_STATUS_DEBUG et le journal Klipper')

def human_mode(mode):
    return {
        'FULL': 'PD4 - présence filament : ACTIVE\nPD3 - mouvement filament : ACTIVE',
        'PARTIAL': 'PD4 - présence filament : ACTIVE\nPD3 - mouvement filament : DÉSACTIVÉ',
        'BYPASS': 'Protections PD3 / PD4 : DÉSACTIVÉES',
    }[mode]

def human_status(status):
    s = status
    yes = lambda v: 'OUI' if v else 'NON'
    enabled = lambda v: 'ACTIVE' if v else 'DÉSACTIVÉE'
    cycles = {'standby': 'EN ATTENTE', 'printing': 'IMPRESSION EN COURS',
              'paused': 'EN PAUSE', 'complete': 'TERMINÉE',
              'cancelled': 'ANNULÉE', 'error': 'ERREUR'}
    monitoring = s['monitoring'] and s['pd3_protection']
    surveillance = ('ACTIVE' if monitoring else
                    'INACTIVE (acquisition des capteurs en cours)' if not s['initialized'] else
                    'INACTIVE (aucune impression)' if not s['session_active'] else
                    'INACTIVE (protection PD3 désactivée)' if not s['pd3_protection'] else
                    'INACTIVE (fichier suspendu ou pause demandée)')
    lines = ['========== GAPGUARD v4.1.0 ==========', '',
             'Mode              : ' + s['mode'],
             'Impression        : ' + cycles.get(s['cycle'], 'ÉTAT NON RECONNU'),
             'Session GapGuard  : ' + ('ACTIVE' if s['session_active'] else 'INACTIVE'), '',
             'PD4 - Filament    : ' + ('INCONNU' if s['pd4'] is None else 'PRÉSENT' if s['pd4'] else 'ABSENT'),
             'Protection PD4    : ' + enabled(s['pd4_protection']), '',
             'PD3 - Mouvement   : ' + ('INCONNU' if s['pd3'] is None else 'BLEU (niveau haut)' if s['pd3'] else 'OFF'),
             'Protection PD3    : ' + enabled(s['pd3_protection']),
             'Surveillance      : ' + surveillance, '',
             'Pause native      : ' + yes(s['paused']),
             'Défaut actif      : ' + (human_reason(s['active_fault']) if s['active_fault'] else 'AUCUN'),
             'Dernier défaut    : ' + (human_reason(s['last_fault']) if s['last_fault'] else 'AUCUN')]
    if s['session_active'] and s['gap'] is not None and s['pd3_protection']:
        lines.append('Écart actuel      : %.2f mm' % s['gap'])
    if s['motion_state'] == 'SUSPECT':
        lines.append('État mouvement    : SUSPECT')
    if s['motion_state'] == 'VERIFY_50':
        lines += ['Vérification      : VERIFY_50',
                  'Fenêtre           : %.1f -> %.1f mm' % (s['verify_start'], s['verify_end']),
                  'Transitions       : %d / %d' % (s['verify_transitions'], s['required_transitions'])]
    if s['motion_state'] == 'ARMING':
        lines.append('État mouvement    : ARMING (attente de mouvement réel)')
    if s['pause_requested']:
        lines.append('Action            : demande de pause SFS en attente')
    if s['pause_error']:
        lines.append('Action            : anomalie PAUSE native ; consulter le diagnostic')
    lines += ['', '======================================']
    return '\n'.join(lines)

def human_debug(s, settings):
    yes = lambda v: 'OUI' if v else 'NON'
    active = lambda v: 'ACTIVE' if v else 'INACTIVE'
    value = lambda v: '-' if v is None else str(v)
    mm = lambda v: '-' if v is None else '%.2f mm' % v
    lines = ['========== GAPGUARD DEBUG v4.1.0 ==========',
             'Version : ' + s['version'],
             'Trace PD3 : ' + active(s.get('motion_trace', False)), '',
             'État général',
             '- Cycle              : ' + s['cycle'].upper(),
             '- Impression         : ' + yes(s['printing']),
             '- Pause native       : ' + yes(s['paused']),
             '- Session            : ' + active(s['session_active']),
             '- Epoch              : ' + str(s['epoch']),
             '- Fichier            : ' + value(s['file_path']), '',
             'Détection',
             '- Défaut actif       : ' + (s['active_fault'] or 'AUCUN'),
             '- Dernier défaut     : ' + (s['last_fault'] or 'AUCUN'),
             '- Surveillance       : ' + active(s['monitoring']),
             '- État mouvement     : ' + s['motion_state'],
             '- Gap actuel         : ' + mm(s['gap']), '',
             'Capteurs',
             '- Acquisition        : ' + ('TERMINÉE' if s['initialized'] else 'EN COURS'),
             '- PD4 présence       : ' + ('INCONNU' if s['pd4'] is None else 'PRÉSENT' if s['pd4'] else 'ABSENT'),
             '- Protection PD4     : ' + active(s['pd4_protection']),
             '- PD3 mouvement      : ' + ('INCONNU' if s['pd3'] is None else 'BLEU (niveau haut)' if s['pd3'] else 'OFF'),
             '- Protection PD3     : ' + active(s['pd3_protection']), '',
             'Vérification PD3',
             '- Distance SUSPECT   : ' + mm(settings.suspect_distance),
             '- Déclenchement      : ' + mm(settings.verify_trigger),
             '- Longueur fenêtre   : ' + mm(settings.verify_distance),
             '- Fin relative       : ' + mm(settings.verify_trigger + settings.verify_distance),
             '- Seuil transitions  : ' + str(s['required_transitions']),
             '- Transitions vues   : ' + str(s['verify_transitions']),
             '- Début fenêtre (E)  : ' + mm(s['verify_start']),
             '- Fin fenêtre (E)    : ' + mm(s['verify_end']), '',
             'Pause',
             '- Demandée           : ' + yes(s['pause_requested']),
             '- Envoyée            : ' + yes(s['pause_dispatched']),
             '- Erreur             : ' + (s['pause_error'] or 'AUCUNE'), '',
             '============================================']
    return '\n'.join(lines)


class GapGuard:
    """SFS adapter; native GapGuard pause, hotend/fan off, fan on real resume."""
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        try:
            values = {k: config.getfloat(k, v) for k, v in Settings.DEFAULTS.items()}
            self.s = Settings(values, config.get('default_mode', 'FULL').upper())
        except (ValueError, TypeError) as exc:
            raise config.error(str(exc))
        self.machine = Machine(self.s)
        self.motion_trace = bool(config.getint('motion_trace', 1, minval=0, maxval=1))
        self._trace_previous_edge = None
        self._saved_fan1 = self._fan_restore_pending = None
        self.extruder_name = config.get('extruder', 'extruder')
        motion_pin = config.get('motion_pin', 'PD3')
        presence_pin = config.get('presence_pin', 'PD4')
        if any('!' in p for p in (motion_pin, presence_pin)):
            raise config.error('S6 requires non-inverted motion/presence pins')
        self.buttons = self.printer.load_object(config, 'buttons')
        self.buttons.register_buttons([motion_pin, presence_pin], self._gpio)
        groups = [group for group in self.buttons.mcu_buttons.values()
                  if any(cb == self._gpio for mask, shift, cb in group.callbacks)]
        if len(groups) != 1:
            raise config.error('unable to identify the shared MCU_buttons group')
        self.button_group = groups[0]
        self._scheduled = self._busy = False
        self._wake_id = 0
        self._wake_stamp = None
        self._wake_time = float('inf')
        self._edges = collections.deque()
        self._boot_snapshot = None
        self._dead = False
        self._monitor_timer = self.reactor.register_timer(self._monitor)
        self._commands()
        for event, callback in [('klippy:ready', self._ready),
                                ('virtual_sdcard:reset_file', self._reset_file),
                                ('klippy:shutdown', self._shutdown),
                                ('klippy:disconnect', self._shutdown),
                                ('gcode:request_restart', self._shutdown)]:
            self.printer.register_event_handler(event, callback)

    def _commands(self):
        self.gcode.register_command('GAPGUARD_INTERNAL_PAUSE', self.cmd_pause)
        self.gcode.register_command('GAPGUARD_INTERNAL_STATUS', self.cmd_status)
        self.gcode.register_command('GAPGUARD_INTERNAL_STATUS_DEBUG', self.cmd_status_debug)
        for command, mode in [('GAPGUARD_INTERNAL_ENABLE_FULL', 'FULL'),
                              ('GAPGUARD_INTERNAL_ENABLE_PARTIAL', 'PARTIAL'),
                              ('GAPGUARD_INTERNAL_DISABLE_ALL', 'BYPASS')]:
            self.gcode.register_command(command, lambda g, m=mode: self.cmd_mode(g, m))

    def _ready(self):
        self.extruder = self.printer.lookup_object(self.extruder_name)
        self.mcu = self.printer.lookup_object('mcu')
        self.vsd = self.printer.lookup_object('virtual_sdcard')
        self.print_stats = self.printer.lookup_object('print_stats')
        self.fan1 = self.printer.lookup_object('output_pin fan1')
        for obj, members in [(self.extruder, ('find_past_position',)),
                             (self.fan1, ('get_status', 'scale')),
                             (self.vsd, ('is_active', 'file_path')),
                             (self.button_group, ('oid',)),
                             (self.gcode, ('get_mutex', 'run_script_from_command'))]:
            if not all(hasattr(obj, name) for name in members):
                raise self.printer.config_error('GapGuard incompatible native interface')
        if self.printer.lookup_object('gcode_macro PAUSE', None) is None:
            raise self.printer.config_error('GapGuard requires the public Elegoo PAUSE macro')
        if any(self.printer.lookup_object(name, None) is not None for name in
               ('filament_switch_sensor fila', 'filament_motion_sensor sfs_motion')):
            raise self.printer.config_error('remove both native SFS sections atomically')
        self.machine.start_ready(self.now(), self.button_group.oid)
        if self._boot_snapshot is not None:
            self.machine.motion.acquire(self._boot_snapshot)
            self.machine.initialized = True
            self._boot_snapshot = None
        self.reactor.update_timer(self._monitor_timer, self.reactor.NOW)

    def native(self):
        return Native(self.print_stats.get_status(self.now())['state'],
                      self.vsd.is_active(), self.vsd.file_path())

    def _drain_edges(self):
        # Refresh file eligibility before accepting GPIO qualification. Events
        # older than an observed resume still update levels but cannot qualify E.
        if not self.machine.initialized:
            for epoch, when, mask, pos in self._edges:
                if epoch == self.machine.epoch and when >= self.machine.min_eventtime:
                    # A real report wins over the silent-low deadline fallback.
                    self.machine.motion.acquire(mask)
                    self.machine.initialized = True
                    break
        now = self.now()
        self._observe(now, self.native(), self.position(now), evaluate=False)
        while self._edges:
            epoch, when, mask, pos = self._edges.popleft()
            if epoch == self.machine.epoch:
                self._gpio_observed(when, mask, pos)
            else:
                # Session reset discards qualification, not the latest received
                # electrical snapshot. No old-session edge can qualify motion.
                self._gpio_observed(when, mask, pos, acquire_only=True)

    def _monitor(self, eventtime):
        if not self.machine.ready or self.printer.is_shutdown():
            return self.reactor.NEVER
        if self.button_group.mcu.is_shutdown():
            self._shutdown()
            return self.reactor.NEVER
        self._drain_edges()
        self._observe(eventtime, self.native(), self.position(eventtime))
        self._wake()
        return eventtime + self.s.check_interval

    def _wake(self, delay=0.):
        if not self.machine.ready or not self.machine.pause_requested:
            return
        stamp = self.machine.token()
        when = self.now() + delay
        if self._scheduled and self._wake_stamp == stamp and self._wake_time <= when:
            return
        self._wake_id += 1
        wake_id = self._wake_id
        self._wake_stamp, self._wake_time = stamp, when
        self._scheduled = True
        self.reactor.register_callback(
            lambda et: self._worker(et, stamp, wake_id), when)

    def _worker(self, eventtime, stamp, wake_id):
        if wake_id != self._wake_id:
            return
        self._scheduled = False
        if self._busy or not self.machine.valid(stamp):
            return
        self._busy = True
        try:
            with self.gcode.get_mutex():
                if not self.machine.valid(stamp):
                    return
                self._drain_edges()
                if not self.machine.valid(stamp):
                    return
                fault = self.machine.claim_pause(self.native())
                if fault is None:
                    return
                self._ui_emit('GapGuard : défaut SFS confirmé\nRaison : %s\nPause Elegoo demandée' % human_reason(fault))
                if fault == 'PD3_NO_MOTION':
                    self._trace_pd3_fault()
                self._execute_pause(stamp, fault)
        finally:
            self._busy = False
            self._wake()

    def _execute_pause(self, stamp, fault):
        record = self._capture_pause_fan()
        try:
            self.native_pause()
        except Exception as exc:
            if self._saved_fan1 is record:
                self._forget_fan()
            logging.exception('GapGuard public Elegoo PAUSE failed')
            if self.machine.valid(stamp):
                self.machine.pause_error = str(exc)
            self._ui_emit('GapGuard : erreur lors de la PAUSE Elegoo ; vérifier l’imprimante et le journal')
            return
        native = self.native()
        self._cool_sfs_pause(native, stamp[0], fault)
        self._pause_fan_off(record, self.native(), fault)
        if self.machine.valid(stamp) and native.printing(self.machine.path):
            self.machine.pause_error = 'public PAUSE returned while file is still printing'
            self._ui_emit('GapGuard : PAUSE Elegoo exécutée mais fichier encore en impression ; vérifier l’imprimante')
        self._observe(self.now(), native, self.position(self.now()), evaluate=False)

    def _cool_sfs_pause(self, native, epoch, fault):
        # Native PAUSE has already saved RESUME.etemp. A normal observed pause
        # may advance serial during M400/M25; epoch/file/fault remain the guards.
        if (not self.machine.ready or self.machine.epoch != epoch
                or not self.machine.session or self.machine.active_fault != fault
                or native.path != self.machine.path or native.state != 'paused'
                or native.active):
            return
        try:
            self.script('SET_HEATER_TEMPERATURE HEATER=%s TARGET=0' % self.extruder_name)
        except Exception as exc:
            logging.exception('GapGuard SFS hotend target-off failed')
            self.machine.pause_error = 'hotend target-off failed: %s' % exc
            self._ui_emit('GapGuard : pause native effectuée, mais coupure de consigne buse en échec ; vérifier le journal')

    def _forget_fan(self):
        self._saved_fan1 = None
        self._fan_restore_pending = None

    def _fan_owned(self, record):
        m = self.machine
        return (record is not None and self._saved_fan1 is record and m.ready
                and m.session and m.epoch == record['epoch']
                and m.path == record['path'])

    def _capture_pause_fan(self):
        # Caller holds the G-code mutex, immediately before public PAUSE.
        # Keep the original if a second fault wins before deferred restoration.
        record = self._saved_fan1
        if self._fan_owned(record) and record['phase'] == 'off':
            return record
        self._forget_fan()
        try:
            value = float(self.fan1.get_status(self.now())['value'])
            scale = float(self.fan1.scale)
            if not math.isfinite(value) or not 0. <= value <= 1.:
                raise ValueError('fan1 runtime value must be normalized 0..1')
            if not math.isfinite(scale) or scale <= 0.:
                raise ValueError('invalid fan1 scale')
            record = dict(epoch=self.machine.epoch, path=self.machine.path,
                          value=value, scale=scale, phase='captured')
            self._saved_fan1 = record
            return record
        except Exception as exc:
            self._fan_error('capture', exc)
            return None

    def _fan_error(self, action, exc):
        logging.exception('GapGuard fan1 %s failed', action)
        previous = self.machine.pause_error
        self.machine.pause_error = ((previous + '; ') if previous else '') + 'fan1 %s failed: %s' % (action, exc)
        self._ui_emit('GapGuard : anomalie fan1 (%s) ; vérifier le journal' % action)

    def _pause_fan_off(self, record, native, fault):
        # Same proof as the existing hotend cut; no wait and no bed commands.
        if not self._fan_owned(record):
            return
        if (native.path != record['path'] or native.state != 'paused'
                or native.active or self.machine.active_fault != fault):
            self._forget_fan()
            return
        try:
            self.script('SET_PIN PIN=fan1 VALUE=0')
            if self._fan_owned(record):
                record['phase'] = 'off'
        except Exception as exc:
            if self._fan_owned(record):
                record['phase'] = 'failed'
                self._fan_error('off', exc)

    def _observe_fan(self, native):
        record = self._saved_fan1
        if record is None:
            return
        if (not self._fan_owned(record) or native.path != record['path']
                or native.state in ('complete', 'cancelled', 'error')):
            self._forget_fan()
            return
        if (record['phase'] == 'off' and native.printing(record['path'])
                and self._fan_restore_pending is not record):
            self._fan_restore_pending = record
            # GPIO/timer observers may only schedule. SET_PIN needs the mutex.
            self.reactor.register_callback(
                lambda et: self._restore_fan(record), self.now())

    def _restore_fan(self, record):
        try:
            with self.gcode.get_mutex():
                # A wait for the mutex grants no right to act on an old file.
                if not self._fan_owned(record) or record['phase'] != 'off':
                    return
                self._drain_edges()
                native = self.native()
                m = self.machine
                if (not self._fan_owned(record) or not m.running
                        or not native.printing(record['path'])
                        or m.pause_requested or m.pause_dispatched):
                    return
                try:
                    # Exact installed output_pin divides VALUE by scale.
                    # Preserve fractional PWM values too; do not round to int.
                    self.script('SET_PIN PIN=fan1 VALUE=%s' %
                                repr(record['value'] * record['scale']))
                    if self._fan_owned(record):
                        self._forget_fan()
                except Exception as exc:
                    if self._fan_owned(record):
                        record['phase'] = 'failed'
                        self._fan_error('restore', exc)
        finally:
            if self._fan_restore_pending is record:
                self._fan_restore_pending = None


    def native_pause(self):
        # Deliberately call the restored public manufacturer macro, not BASE_PAUSE.
        self.script('PAUSE')

    def cmd_mode(self, gcmd, mode):
        try:
            self._refresh_for_command()
            self.machine.change_mode(mode, self.position(self.now()), self.now())
        except ValueError as exc:
            raise gcmd.error('GapGuard : activation %s impossible\nMode actif : %s\nRaison : %s' % (mode, self.machine.mode, human_reason(exc)))
        gcmd.respond_info('GapGuard : mode %s activé\n%s' % (self.machine.mode, human_mode(self.machine.mode)))
        self._wake()

    def cmd_status(self, gcmd):
        try:
            self._refresh_for_command()
            text = human_status(self.get_status(self.now()))
        except Exception:
            logging.exception('GapGuard status display failed')
            raise gcmd.error('GapGuard : état indisponible ; consulter le journal Klipper')
        gcmd.respond_info(text)
        self._wake()

    def cmd_status_debug(self, gcmd):
        self._refresh_for_command()
        status = self.get_status(self.now())
        gcmd.respond_info(human_debug(status, self.s))
        if gcmd.get_int('RAW', 0, minval=0, maxval=1):
            gcmd.respond_info(json.dumps(status, sort_keys=True))
        self._wake()

    def _trace(self, event, **fields):
        if not self.motion_trace:
            return
        # Diagnostics must never raise into the detector or the pause path.
        try:
            fields['epoch'] = self.machine.epoch
            logging.info('[GAPGUARD_TRACE] %s %s', event,
                         ' '.join('%s=%s' % (k, repr(v) if isinstance(v, float) else
                                            '-' if v is None else v)
                                  for k, v in fields.items()))
        except Exception:
            pass

    def _trace_snapshot(self):
        m = self.machine.motion
        return dict(state=m.state, reference=m.reference, count=m.count,
                    start=m.verify_start, end=m.verify_end,
                    pd3=m.pd3, pd4=m.pd4)

    def _trace_steps(self, before, when, position, edge=False):
        m = self.machine.motion
        gap = None if before['reference'] is None or position is None else position - before['reference']
        pd3 = 'UNKNOWN' if m.pd3 is None else 'HIGH' if m.pd3 else 'LOW'
        pd4 = 'UNKNOWN' if m.pd4 is None else 'PRESENT' if m.pd4 else 'ABSENT'
        if before['state'] != 'SUSPECT' and m.state == 'SUSPECT':
            self._trace('SUSPECT', ts=when, E=position, gap=gap, PD3=pd3, PD4=pd4)
        # Observe entry also when a one-edge configured window opens and closes
        # inside the same original Motion.edge call. This never drives detection.
        entered = (before['state'] != 'VERIFY_50' and
                   (m.state == 'VERIFY_50' or
                    (edge and before['state'] in ('ARMING', 'NORMAL', 'SUSPECT')
                     and gap is not None and gap > self.s.verify_trigger
                     and m.state == 'NORMAL' and m.count >= self.s.verify_transitions)))
        if entered:
            start = before['reference'] + self.s.verify_trigger
            self._trace('VERIFY_START', ts=when, E=position, gap=gap,
                        verify_start=start, verify_end=start + self.s.verify_distance,
                        transitions='0/%d' % self.s.verify_transitions,
                        PD3=pd3, PD4=pd4)
        return entered

    def _observe(self, when, native, position, evaluate=True):
        before = self._trace_snapshot() if self.motion_trace else None
        self.machine.observe(when, native, position, evaluate=evaluate)
        self._observe_fan(native)
        if before is not None:
            self._trace_steps(before, when, position)

    def _gpio_observed(self, when, mask, position, acquire_only=False):
        before = self._trace_snapshot() if self.motion_trace else None
        qualified = (not acquire_only and self.machine.ready and self.machine.running
                     and not self.machine.pause_dispatched and self.machine.mode == 'FULL'
                     and position is not None and when >= self.machine.min_eventtime
                     and when >= self.machine.min_motion_time)
        if acquire_only:
            self.machine.motion.acquire(mask)
            self.machine.initialized = True
        else:
            self.machine.gpio(when, mask, position)
        if before is None:
            return
        m = self.machine.motion
        edge = before['pd3'] is not None and m.pd3 is not None and before['pd3'] != m.pd3
        entered = self._trace_steps(before, when, position, edge=edge and qualified)
        if not edge:
            return
        kind = 'HIGH->LOW' if before['pd3'] else 'LOW->HIGH'
        previous = self._trace_previous_edge
        same_epoch = previous is not None and previous[0] == self.machine.epoch
        de = position - previous[2] if same_epoch and position is not None and previous[2] is not None else None
        dt = when - previous[1] if same_epoch else None
        self._trace_previous_edge = (self.machine.epoch, when, position)
        self._trace('PD3', ts=when, edge=kind, E=position, dE=de, dt=dt,
                    state=before['state'],
                    PD4='UNKNOWN' if m.pd4 is None else 'PRESENT' if m.pd4 else 'ABSENT')
        counted = not acquire_only and ((entered and m.count > 0) or
                                       (before['state'] == 'VERIFY_50' and m.count > before['count']))
        if counted:
            start = before['start'] if before['start'] is not None else before['reference'] + self.s.verify_trigger
            consumed = position - start
            self._trace('VERIFY_EDGE', ts=when, edge=kind, E=position, distance=consumed,
                        verify_start=start, verify_end=start + self.s.verify_distance,
                        transitions='%d/%d' % (m.count, self.s.verify_transitions))
            if m.state == 'NORMAL' and m.count >= self.s.verify_transitions:
                self._trace('VERIFY_OK', ts=when, E=position, distance=consumed,
                            verify_start=start, verify_end=start + self.s.verify_distance,
                            transitions='%d/%d' % (m.count, self.s.verify_transitions))

    def _trace_pd3_fault(self):
        if not self.motion_trace:
            return
        m = self.machine.motion
        # Use the E sample evaluated by Motion.observe, not an invented E read
        # after the native pause has already reset the live window.
        gap = None if m.reference is None or m.position is None else m.position - m.reference
        self._trace('FAULT', ts=self.now(), type='PD3_NO_MOTION', E=m.position,
                    gap=gap, verify_start=m.verify_start, verify_end=m.verify_end,
                    transitions='%d/%d' % (m.count, self.s.verify_transitions),
                    PD3='UNKNOWN' if m.pd3 is None else 'HIGH' if m.pd3 else 'LOW',
                    PD4='UNKNOWN' if m.pd4 is None else 'PRESENT' if m.pd4 else 'ABSENT')

    def cmd_pause(self, gcmd):
        # Public macro commands already hold the G-code mutex. Share the same
        # native PAUSE + target-off path as a confirmed SFS fault, without one.
        self._refresh_for_command()
        m = self.machine
        if not m.session or not m.running or not self.native().printing(m.path):
            gcmd.respond_info('GapGuard : aucune impression active à mettre en pause')
            return
        if m.pause_dispatched:
            gcmd.respond_info('GapGuard : une pause a déjà été demandée')
            return
        m.pause_requested = False
        m.reason = None
        m.pause_dispatched = True
        gcmd.respond_info('GapGuard : pause volontaire demandée ; coupure de consigne buse après la pause Elegoo')
        self._execute_pause(m.token(), m.active_fault)
        self._wake()

    def _shutdown(self, *args):
        self._forget_fan()
        self._dead = True
        self._boot_snapshot = None
        self.machine.reset(self.now(), shutdown=True)
        self._edges.clear()
        self.reactor.update_timer(self._monitor_timer, self.reactor.NEVER)

    def _reset_file(self, *args):
        self._forget_fan()
        self.machine.reset(self.now(), pending_new=True)
        self._edges.clear()
        self._wake()

    def now(self):
        return self.reactor.monotonic()

    def position(self, eventtime):
        return self.extruder.find_past_position(self.mcu.estimated_print_time(eventtime))

    def _gpio(self, eventtime, mask):
        if self._dead:
            return
        if not self.machine.ready:
            # buttons_query may report during connect, before klippy:ready.
            # Keep that real group snapshot; otherwise a stable HIGH could
            # incorrectly be replaced by the silent-low fallback after ready.
            self._boot_snapshot = mask
            return
        if eventtime < self.machine.min_eventtime:
            return
        # Acquisition and intent only; no G-code or physical wait in this path.
        self._edges.append((self.machine.epoch, eventtime, mask, self.position(eventtime)))
        self._drain_edges()
        self._wake()

    def script(self, commands):
        # Caller already owns the mutex. Never call run_script() here.
        self.gcode.run_script_from_command(commands)

    def _refresh_for_command(self):
        if not self.machine.ready:
            raise ValueError('GapGuard not ready')
        self._drain_edges()
        self._observe(self.now(), self.native(), self.position(self.now()))

    def _ui_emit(self, text):
        # Presentation errors must never propagate into the safety executor.
        try:
            self.gcode.respond_info(text)
        except Exception:
            logging.exception('GapGuard user-interface output failed')

    def get_status(self, eventtime):
        native = self.native() if self.machine.ready else Native()
        status = self.machine.status(native)
        status['motion_trace'] = self.motion_trace
        return status


def load_config(config):
    return GapGuard(config)
