class PD3Observer:
    """OFFLINE REVIEW BUILD pd3-observer-1-r2. Passive, bounded flight recorder.

    Never calls position(), native(), Machine methods, G-code or the MCU.
    Only GapGuard._pd3_diag() calls this class; all its exceptions are contained.
    """
    BUILD = '4.2.1-rc1+pd3-observer-1-r2'
    CAPACITY = 128
    CHECKPOINTS = 32
    PENDING = 2
    BATCH = 4

    def __init__(self, owner):
        self.o = owner
        # Diagnostic identity only: fresh for each observer, including restart.
        # No clock, PID, file, E position or persistent machine state is used.
        self.instance_id = uuid.uuid4().hex
        self.records = collections.deque()
        self.links = {}
        self.checkpoints = collections.deque(maxlen=self.CHECKPOINTS)
        self.pending = collections.deque()
        self.counters = collections.Counter()
        self.sequence = self.dump_sequence = 0
        self.active = self.last_entry = self.last_native = None
        self.checkpoint_key = None

    def context(self):
        m = self.o.machine
        return dict(ready=m.ready, initialized=m.initialized, session=m.session,
                    epoch=m.epoch, generation=m.motion_generation, serial=m.serial,
                    running=m.running, mode=m.mode, phase=m.motion_phase,
                    min_eventtime=m.min_eventtime, generation_time=m.generation_time,
                    min_motion_time=m.min_motion_time,
                    path=m.path[:256] if m.path is not None else None)

    def detector(self):
        m, d = self.o.machine, self.o.machine.motion
        return dict(pd3=d.pd3, pd4=d.pd4, state=d.state, E=d.position,
                    reference=d.reference, start=d.verify_start, end=d.verify_end,
                    count=d.count, motion_edges=m.motion_edges,
                    last_edge_E=d.last_edge_position)

    def validity(self, epoch, generation, when):
        m = self.o.machine
        epoch = m.epoch if epoch is None else epoch
        generation = m.motion_generation if generation is None else generation
        # Describe all comparisons, including ones short-circuited by native code.
        checks = dict(ready=m.ready, epoch_equal=epoch == m.epoch,
                      generation_equal=generation == m.motion_generation,
                      time_at_least_floor=when >= max(m.min_eventtime, m.generation_time))
        return dict(received_epoch=epoch, current_epoch=m.epoch,
                    received_generation=generation, current_generation=m.motion_generation,
                    eventtime=when, min_eventtime=m.min_eventtime,
                    generation_time=m.generation_time, checks=checks,
                    failed=[k for k, v in checks.items() if not v])

    def entry(self, when, mask):
        self.sequence += 1
        self.counters['callback_entries'] += 1
        r = dict(id=self.sequence, eventtime=when, processed_at=self.o.now(),
                 mask=mask, entry=self.context())
        self.last_entry = (r['id'], when, r['processed_at'])
        self.append(r)
        return r

    def append(self, r):
        if len(self.records) == self.CAPACITY:
            old = self.records.popleft()
            queued = old.pop('_tuple', None)
            if queued is not None:
                self.links.pop(id(queued), None)
                self.counters['queue_correlations_evicted'] += 1
            self.counters['records_evicted'] += 1
        self.records.append(r)

    def reject(self, r, condition):
        if r is None:
            return
        r['return'] = dict(condition=condition, dead=getattr(self.o, '_dead', False),
                           current=self.context(),
                           comparisons=self.validity(None, None, r['eventtime']))
        self.counters[condition] += 1

    def enqueue(self, r, queued):
        if r is None:
            return
        r['queued'] = dict(epoch=queued[0], generation=queued[1],
                           eventtime=queued[2], mask=queued[3], E=queued[4],
                           depth=len(self.o._edges))
        # Retain this tuple while linked so Python cannot recycle its id.
        r['_tuple'] = queued
        self.links[id(queued)] = r
        self.counters['enqueued'] += 1

    def bootstrap(self, epoch, generation, when, mask, position):
        # This prescan is acquisition, not a counted edge. No E is sampled here.
        for r in self.records:
            q = r.get('_tuple')
            if q == (epoch, generation, when, mask, position):
                r['bootstrap_acquisition'] = dict(mask=mask, before=self.detector())
                return
        self.counters['bootstrap_without_entry'] += 1

    def dequeue(self, queued):
        r = self.links.pop(id(queued), None)
        if r is None:
            self.sequence += 1
            r = dict(id=self.sequence, eventtime=queued[2], mask=queued[3],
                     missing_callback_record=True,
                     queued=dict(epoch=queued[0], generation=queued[1], E=queued[4]))
            self.append(r)
            self.counters['dequeue_without_entry'] += 1
        r.pop('_tuple', None)
        r['dequeued'] = dict(processed_at=self.o.now(), current=self.context(),
                             comparisons=self.validity(queued[0], queued[1], queued[2]))
        self.active = r
        self.counters['dequeued'] += 1

    def queue_reject(self):
        if self.active is not None:
            self.active['return'] = dict(condition='queue_generation_valid_false',
                comparisons=self.active['dequeued']['comparisons'])
            self.counters['queue_rejected'] += 1
        self.active = None

    def processing(self, when, mask, position, acquire_only, epoch, generation):
        r, self.active = self.active, None
        if r is None:
            self.sequence += 1
            r = dict(id=self.sequence, eventtime=when, mask=mask,
                     direct_processing_without_dequeue=True)
            self.append(r)
        r['processing'] = dict(processed_at=self.o.now(), E=position,
                               acquire_only=acquire_only, current=self.context(),
                               comparisons=self.validity(epoch, generation, when),
                               before=self.detector())
        self.counters['processing'] += 1
        return r

    def effect(self, r, accepted, recovery):
        if r is None:
            return
        p, after = r['processing'], self.detector()
        before, ctx = p['before'], p['current']
        valid = not p['comparisons']['failed'] or p['acquire_only']
        electrical = valid and before['pd3'] is not None and after['pd3'] != before['pd3']
        acquisition = valid and before['pd3'] is None and after['pd3'] is not None
        recovery_branch = recovery and ctx['phase'] == 'RECOVERY' and not ctx['running']
        # Count evidence comes from the existing counter, not a second detector.
        # A newly opened VERIFY starts at zero; its first count can equal the
        # retained count from a previously closed window.
        window_before = before['state'] == 'VERIFY_50'
        counted = bool(accepted and not recovery_branch and
            (after['count'] > before['count'] if window_before else
             before['state'] in ('ARMING', 'NORMAL', 'SUSPECT') and
             before['reference'] is not None and p['E'] is not None and
             p['E'] > before['reference'] + self.o.s.verify_trigger and after['count'] > 0))
        reasons = []
        if not valid:
            reasons = ['generation_valid_false'] + p['comparisons']['failed']
        elif p['acquire_only']:
            reasons = ['acquire_only']
        elif not accepted:
            if not electrical:
                reasons.append('initial_acquisition' if acquisition else 'no_PD3_level_change')
            if not ctx['running'] and not recovery_branch:
                reasons.append('not_running')
            if ctx['mode'] != 'FULL':
                reasons.append('mode_not_FULL')
            if p['E'] is None:
                reasons.append('E_unavailable')
            if recovery_branch and before['state'] not in ('ARMING', 'NORMAL'):
                reasons.append('recovery_state_not_ARMING_or_NORMAL')
        r['effect'] = dict(after=after, machine_accepted=accepted,
                           recovery_window=recovery, electrical_transition=electrical,
                           acquisition=acquisition, verify_counted=counted,
                           not_accepted_reasons=reasons)
        self.counters['electrical_transitions'] += int(electrical)
        self.counters['machine_accepted'] += int(bool(accepted))
        self.counters['verify_counted'] += int(counted)

    def after_observers(self, r):
        if r is not None:
            after = self.detector()
            if after != r.get('effect', {}).get('after'):
                r['after_recovery_observer'] = after

    def clear(self, reason):
        for r in self.links.values():
            r['return'] = dict(condition=reason, current=self.context())
            r.pop('_tuple', None)
            self.counters['queue_cleared'] += 1
        self.links.clear()
        self.active = None

    def observation(self, when, native, position, evaluate):
        self.last_native = dict(observed_at=when, state=native.state,
                                active=native.active, path=native.path[:256] if native.path else None,
                                sampled_E=position, evaluate=evaluate)
        ctx, d = self.context(), self.detector()
        key = (ctx['epoch'], ctx['generation'], ctx['ready'], ctx['session'],
               ctx['running'], ctx['mode'], ctx['phase'], d['state'])
        if key != self.checkpoint_key:
            self.checkpoint_key = key
            self.checkpoints.append(dict(when=when, context=ctx, detector=d,
                                         native=self.last_native,
                                         callback_entries=self.counters['callback_entries']))

    def fault(self):
        self.dump_sequence += 1
        if len(self.pending) >= self.PENDING:
            self.counters['dumps_dropped'] += 1
            return
        # Shallow record copies are sufficient: nested snapshots are immutable
        # after assignment; _tuple is private correlation data and is excluded.
        records = [{k: v for k, v in r.items() if k != '_tuple'} for r in self.records]
        header = dict(build=self.BUILD, dump=self.dump_sequence, kind='FAULT_CONTEXT',
                      schema=2, instance_id=self.instance_id,
                      capture_id='%s:%d' % (self.instance_id, self.dump_sequence),
                      captured_at=self.o.now(), context=self.context(), detector=self.detector(),
                      native=self.last_native, last_callback=self.last_entry,
                      counters=dict(self.counters),
                      wrapper_errors=getattr(self.o, '_pd3_diag_errors', 0),
                      records=len(records), checkpoints=list(self.checkpoints),
                      capacity=self.CAPACITY)
        self.pending.append(dict(header=header, records=records, offset=0, sent_header=False))

    def flush(self):
        # Called at most once per existing monitor tick, after its normal work.
        # Do not log while the GapGuard pause worker is waiting in native PAUSE.
        if not self.pending or getattr(self.o, '_busy', False):
            return
        p = self.pending[0]
        if not p['sent_header']:
            payload = p['header']
        else:
            start = p['offset']
            end = min(start + self.BATCH, len(p['records']))
            payload = dict(build=self.BUILD, dump=p['header']['dump'], kind='EVENTS',
                           schema=p['header']['schema'], instance_id=p['header']['instance_id'],
                           capture_id=p['header']['capture_id'],
                           offset=start, records=p['records'][start:end],
                           complete=end == len(p['records']))
        # Advance even if the logging backend fails: no retry loop or backlog.
        try:
            logging.info('[GAPGUARD_PD3_DIAG] %s', json.dumps(self.json_safe(payload), separators=(',', ':'), allow_nan=False))
        finally:
            if not p['sent_header']:
                p['sent_header'] = True
            else:
                p['offset'] = end
                if end == len(p['records']):
                    self.pending.popleft()

    def json_safe(self, value):
        # Klipper uses +/-infinity for inactive deadlines. Preserve their
        # meaning as strings while keeping dumps valid strict JSON.
        if isinstance(value, float) and not math.isfinite(value):
            return repr(value)
        if isinstance(value, dict):
            return {k: self.json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.json_safe(v) for v in value]
        return value

