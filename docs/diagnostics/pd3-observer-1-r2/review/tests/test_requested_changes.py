"""Offline regressions for the four requested changes; never uses the network."""
import ast
import collections
import hashlib
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'test_dependencies'))
import jinja2
import gapguard as gg
from test_recovery import Rig, Gcmd
from test_post_pause_hook import worker_fixture, run_worker

def section(data, name):
    return re.search(rb'(?m)^\[' + re.escape(name.encode()) + rb'\][\s\S]*?(?=^\[|\Z)', data).group()

def template(name, live=False):
    p = ROOT / 'fixtures/live/printer.cfg' if live else ROOT / 'printer.cfg'
    text = section(p.read_bytes(), name).decode('utf-8')
    body = text.split('gcode:', 1)[1]
    env = jinja2.Environment(variable_start_string='{', variable_end_string='}',
                             undefined=jinja2.StrictUndefined)
    return env.from_string(body)

def render_idle(status, temp=20., live=False):
    printer = {'gapguard':status, 'toolhead':NS(extruder='extruder'),
               'extruder':NS(temperature=temp)}
    rendered = template('idle_timeout', live).render(
        printer=printer, action_respond_info=lambda msg:'')
    return [l.strip() for l in rendered.splitlines() if l.strip() and not l.lstrip().startswith('#')]

def apply_heaters(lines, heaters):
    for line in lines:
        if line == 'TURN_OFF_HEATERS':
            for key in heaters: heaters[key] = 0.
        elif line.startswith('SET_HEATER_TEMPERATURE'):
            c = Gcmd(line); heaters[c.get('HEATER')] = c.get_float('TARGET')

def machine():
    s = gg.Settings(dict(suspect_distance=9., verify_trigger=20.,
                         verify_distance=20., verify_transitions=2))
    m = gg.Machine(s); n = gg.Native('printing', True, '/active.gcode')
    m.start_ready(0., 1); m.gpio(1., 2, 0.); m.observe(10., n, 0.)
    return m, n

def adapter(m, n, now=20., pos=10.):
    a = object.__new__(gg.GapGuard)
    a.machine=m; a.s=m.s; a.motion_trace=False; a._edges=collections.deque()
    a._saved_fan1=a._fan_restore_pending=None; a._dead=False
    a._boot_snapshot=None; a.now=lambda:now; a.position=lambda t:pos
    a.native=lambda:n; a._wake=lambda:None
    a.auto_recovery=NS(gpio=lambda *args:None,edge_window=lambda when:False)
    return a

class PD3RequestedTests(unittest.TestCase):
    def test_full_both_polarities(self):
        m,n=machine()
        for t,mask,e in [(11.,3,4.),(12.,2,7.)]:
            m.gpio(t,mask,e)
            self.assertEqual((m.motion.state,m.motion.reference),('NORMAL',e))

    def test_suspect_real_front(self):
        m,n=machine();m.observe(11.,n,9.);self.assertEqual(m.motion.state,'SUSPECT')
        m.gpio(11.1,3,10.);self.assertEqual((m.motion.state,m.motion.reference),('NORMAL',10.))

    def test_verify_two_fronts_counted(self):
        m,n=machine();m.observe(11.,n,20.1)
        m.gpio(11.1,3,25.);self.assertEqual(m.motion.count,1)
        m.gpio(11.2,2,40.);self.assertEqual(m.motion.count,2)
        self.assertEqual((m.motion.state,m.motion.reference),('NORMAL',40.))

    def test_same_level_is_not_movement(self):
        m,n=machine();m.gpio(11.,2,12.)
        self.assertEqual(m.motion.reference,0.);self.assertIsNone(m.motion.last_edge_position)

    def test_unknown_acquisition_not_edge(self):
        m,n=machine();m.motion.pd3=None;m.gpio(11.,3,12.)
        self.assertEqual(m.motion.reference,0.)

    def test_partial_acquires_without_motion(self):
        m,n=machine();m.change_mode('PARTIAL',0.,11.)
        m.gpio(12.,3,50.);m.observe(13.,n,100.)
        self.assertEqual(m.motion.pd3,1);self.assertEqual(m.motion.state,'DISABLED')
        self.assertIsNone(m.motion.reference);self.assertFalse(m.pause_requested)

    def test_bypass_unchanged(self):
        m,n=machine();m.change_mode('BYPASS',0.,11.)
        m.gpio(12.,1,100.);m.observe(13.,n,200.)
        self.assertFalse(m.pause_requested);self.assertEqual(m.motion.state,'DISABLED')

    def test_current_edge_before_artificial_barrier(self):
        m,n=machine();m.min_motion_time=50.
        m.gpio(11.,3,4.);self.assertEqual(m.motion.reference,4.)

    def test_pending_pause_does_not_deny_edge(self):
        m,n=machine();m.observe(11.,n,20.1);m.gpio(12.,3,25.)
        m.observe(13.,n,40.);self.assertTrue(m.pause_requested)
        m.gpio(13.,2,40.);self.assertIsNone(m.claim_pause(n))

    def test_committed_action_does_not_deny_evidence_or_send_second_pause(self):
        m,n=machine();m.request_pause('VERIFY_FAIL');self.assertEqual(m.claim_pause(n),'PD3_NO_MOTION')
        m.gpio(11.,3,4.);self.assertEqual(m.motion.reference,4.)
        self.assertTrue(m.pause_dispatched);self.assertIsNone(m.claim_pause(n))

    def test_paused_does_not_arm_on_extrusion(self):
        m,n=machine();m.observe(11.,gg.Native('paused',False,n.path),5.)
        m.gpio(12.,3,25.);self.assertEqual(m.motion.state,'DISABLED')
        self.assertIsNone(m.motion.reference)

    def test_old_epoch_changes_neither_levels_nor_reference(self):
        m,n=machine();a=adapter(m,n)
        a._edges.append((m.epoch-1,m.motion_generation,19.,3,8.));a._drain_edges()
        self.assertEqual(m.motion.pd3,0);self.assertEqual(m.motion.reference,0.)
        self.assertFalse(a._edges)

    def test_pre_session_timestamp_still_rejected(self):
        m,n=machine();m.min_eventtime=10.
        m.gpio(9.,3,8.);self.assertEqual(m.motion.pd3,0);self.assertEqual(m.motion.reference,0.)

    def test_old_generation_queue_cannot_seed_observed_resume(self):
        m,n=machine();m.observe(12.,gg.Native('paused',False,n.path),5.)
        a=adapter(m,n,now=20.,pos=11.)
        a._edges.append((m.epoch,m.motion_generation,19.9,3,10.));a._drain_edges()
        self.assertEqual(m.min_motion_time,20.)
        self.assertEqual((m.motion.state,m.motion.reference),('ARMING',11.))
        self.assertIsNone(m.motion.last_edge_position)
        self.assertEqual(m.motion.pd3,0)

    def test_gpio_callback_first_after_resume(self):
        m,n=machine();m.observe(12.,gg.Native('paused',False,n.path),5.)
        a=adapter(m,n,now=20.,pos=10.);a._gpio(19.9,3)
        self.assertEqual((m.motion.state,m.motion.reference),('NORMAL',10.))

    def test_find_past_position_conversion_preserved(self):
        a=object.__new__(gg.GapGuard);seen=[]
        a.mcu=NS(estimated_print_time=lambda t:t-100.)
        a.extruder=NS(find_past_position=lambda t:seen.append(t) or 321.)
        self.assertEqual(a.position(105.),321.);self.assertEqual(seen,[5.])

    def test_live_twenty_boundary_priority(self):
        m,n=machine();m.observe(11.,n,20.)
        m.gpio(11.,3,20.);self.assertEqual((m.motion.state,m.motion.reference),('NORMAL',20.))

    def test_no_edges_still_fault_at_forty(self):
        m,n=machine();m.observe(11.,n,9.);m.observe(12.,n,20.)
        m.observe(13.,n,40.);self.assertEqual(m.claim_pause(n),'PD3_NO_MOTION')

class ThermalRequestedTests(unittest.TestCase):
    def thermal_pause(self, fault='PD4_ABSENT', temp=100., target=215.):
        x,a=worker_fixture(fault=fault);x.temp=temp;x.target=target
        beds=[51.25,52.5,53.75,54.125];x.beds=list(beds)
        printer={'toolhead':NS(axis_minimum=NS(x=-5,y=-1),extruder='extruder'),
                 'gcode_move':NS(gcode_position=NS(x=100,y=100,z=5,e=200),position=NS(z=5)),
                 'extruder':NS(temperature=temp,target=target),
                 'heater_bed':NS(target=beds[0])}
        for i in range(1,4):printer['heater_generic heater_bed'+str(i)]=NS(target=beds[i])
        rendered=template('gcode_macro PAUSE').render(printer=printer,params={},
            flag_home_x=1,flag_home_y=1,flag_print_status=1)
        # Execute the native template's saved-target assignments in the fake port.
        def save_native():
            for line in rendered.splitlines():
                if 'SET_GCODE_VARIABLE' in line:x.script(line.strip())
        x.during_pause=save_native
        if fault is None:
            x.m.pause_requested=False;x.m.active_fault=x.m.last_fault=None
            a._refresh_for_command=lambda:None
            with x.mutex:a.cmd_pause(NS(respond_info=lambda msg:None))
        else:run_worker(x,a)
        return x,a,beds

    def test_pd4_pause_captures_five_targets_and_cools_only_hotend(self):
        x,a,beds=self.thermal_pause()
        self.assertEqual(x.rv['etemp'],215.);self.assertEqual(x.target,0.)
        self.assertEqual([x.rv[k] for k in ['bed_temp','bed_temp1','bed_temp2','bed_temp3']],beds)
        self.assertEqual(x.beds,beds);self.assertEqual(x.m.status(x.native)['pause_origin'],'gapguard')

    def test_pd3_pause_origin(self):
        x,a,beds=self.thermal_pause('PD3_NO_MOTION',220.,220.)
        self.assertEqual(x.m.status(x.native)['pause_origin'],'gapguard');self.assertEqual(x.beds,beds)

    def test_voluntary_gapguard_no_false_fault(self):
        x,a,beds=self.thermal_pause(None)
        self.assertIsNone(x.m.active_fault);self.assertIsNone(x.m.last_fault)
        self.assertEqual(x.m.status(x.native)['pause_origin'],'gapguard');self.assertEqual(x.target,0.)

    def test_timeout_after_gapguard_pause_preserves_all_four_exact_targets(self):
        for fault in ('PD4_ABSENT','PD3_NO_MOTION',None):
            with self.subTest(fault=fault):
                x,a,beds=self.thermal_pause(fault)
                lines=render_idle(x.m.status(x.native),20.)
                h=dict(zip(['heater_bed','heater_bed1','heater_bed2','heater_bed3'],beds));h['extruder']=0.
                for _ in range(3):apply_heaters(lines,h)
                self.assertEqual([h[k] for k in ['heater_bed','heater_bed1','heater_bed2','heater_bed3']],beds)
                self.assertEqual(h['extruder'],0.);self.assertNotIn('TURN_OFF_HEATERS',lines)

    def test_timeout_hot_gapguard_no_140_target(self):
        x,a,beds=self.thermal_pause();lines=render_idle(x.m.status(x.native),220.)
        self.assertEqual(lines,['SET_HEATER_TEMPERATURE HEATER=extruder TARGET=0'])

    def test_live_timeout_reproduces_bed_loss(self):
        x,a,beds=self.thermal_pause();lines=render_idle(x.m.status(x.native),20.,live=True)
        self.assertEqual(lines,['TURN_OFF_HEATERS'])

    def test_manual_elegoo_pause_unchanged_hot_and_cold(self):
        m,n=machine();m.observe(11.,gg.Native('paused',False,n.path),0.)
        st=m.status(gg.Native('paused',False,n.path));self.assertIsNone(st['pause_origin'])
        for temp in (20.,160.,161.,220.):
            self.assertEqual(render_idle(st,temp),render_idle(st,temp,live=True))

    def test_origin_cleared_on_real_resume(self):
        x,a,beds=self.thermal_pause();x.native=gg.Native('printing',True,x.m.path)
        x.m.observe(x.t+1,x.native,100.);self.assertIsNone(x.m.pause_origin)
        x.native=gg.Native('paused',False,x.m.path);x.m.observe(x.t+2,x.native,100.)
        self.assertIsNone(x.m.status(x.native)['pause_origin'])

    def test_cancel_complete_new_file_clear_origin(self):
        for state in ('cancelled','complete','error'):
            x,a,beds=self.thermal_pause();x.m.observe(x.t+1,gg.Native(state,False,None),0.)
            self.assertIsNone(x.m.pause_origin)
        x,a,beds=self.thermal_pause();x.m.observe(x.t+1,gg.Native('printing',True,'/new'),0.)
        self.assertIsNone(x.m.pause_origin)

    def test_origin_never_authorizes_nonpaused_state(self):
        x,a,beds=self.thermal_pause()
        for native in [gg.Native('printing',True,x.m.path),gg.Native('cancelled',False,None),gg.Native('paused',False,'/other')]:
            self.assertIsNone(x.m.status(native)['pause_origin'])

    def test_cold_and_zero_target_saved_without_changing_manual_macro(self):
        for target in (0.,205.5):
            x,a,beds=self.thermal_pause(temp=30.,target=target)
            self.assertEqual(x.rv['etemp'],target)

class M24RequestedTests(unittest.TestCase):
    def resuming(self):
        x=Rig();x.pause();x.until('RESUMING');return x

    def test_full_recovery_busy_mutex_then_resumed_no_commands(self):
        x=self.resuming();self.assertEqual(x.calls.count('G1 E20 F200'),15)
        self.assertEqual(x.calls.count('M24'),1);self.assertEqual(x.r.record['purged'],300.)
        x.mutex.locked=True;before=list(x.calls);x.tick()
        self.assertEqual(x.state(),'RESUMED');self.assertEqual(x.calls,before)
        self.assertNotIn('FAIL',[e for e,f in x.events])
        for bad in ('RESUME','BASE_RESUME','BASE_PAUSE','PAUSE'):self.assertNotIn(bad,x.calls)

    def test_wait_for_real_printing_while_mutex_busy(self):
        x=self.resuming();x.native=gg.Native('paused',False,x.m.path);x.mutex.locked=True
        before=list(x.calls);x.tick();self.assertEqual(x.state(),'RESUMING')
        x.native=gg.Native('printing',True,x.m.path);x.tick();self.assertEqual(x.state(),'RESUMED')
        self.assertEqual(x.calls,before)

    def test_inactive_printing_not_success(self):
        x=self.resuming();x.native=gg.Native('printing',False,x.m.path);x.mutex.locked=True
        x.tick();self.assertEqual(x.state(),'RESUMING')

    def test_original_deadline_failure_with_busy_mutex(self):
        x=self.resuming();x.native=gg.Native('paused',False,x.m.path);x.mutex.locked=True
        x.t=x.r.record['deadline']+.01;x.tick(0)
        self.assertEqual(x.state(),'FAILED');self.assertEqual(x.r.record['error'],'real file resume not confirmed')
        self.assertEqual(x.calls.count('M24'),1)

    def test_terminal_after_m24_unchanged(self):
        for state in ('complete','cancelled','error'):
            x=self.resuming();x.native=gg.Native(state,False,None);x.mutex.locked=True;x.tick()
            self.assertEqual(x.state(),'FAILED');self.assertEqual(x.r.record['error'],'print ended after M24')

    def test_mutex_before_m24_still_failure(self):
        x=Rig();x.block();x.mutex.locked=True;x.r.tick(x.t)
        self.assertEqual(x.state(),'FAILED');self.assertNotIn('M24',x.calls)

    def test_insufficient_pd3_stays_paused_no_m24(self):
        x=Rig();x.block();x.until('FAILED',edges=0);x.tick()
        self.assertEqual(x.native.state,'paused');self.assertNotIn('M24',x.calls)

    def test_late_stale_step_after_resumed_cannot_send_commands(self):
        x=self.resuming();r=x.r.record;generation=x.r.generation
        x.tick();before=list(x.calls);x.r.step(r,generation)
        self.assertEqual(x.calls,before)

class PreservationTests(unittest.TestCase):


    def test_config_only_idle_timeout_changed(self):
        a=(ROOT/'fixtures/live/printer.cfg').read_bytes();b=(ROOT/'printer.cfg').read_bytes()
        def functional(raw):return [line for line in raw.splitlines() if line.strip() and not line.lstrip().startswith(b'#')]
        self.assertEqual(functional(a.replace(section(a,'idle_timeout'),b'')),functional(b.replace(section(b,'idle_timeout'),b'')))

    def test_python_scope_method_allowlist(self):
        def blocks(p):
            raw=p.read_bytes();lines=raw.splitlines(True);tree=ast.parse(raw)
            return {c.name+'.'+f.name:b''.join(lines[f.lineno-1:f.end_lineno])
                    for c in tree.body if isinstance(c,ast.ClassDef)
                    for f in c.body if isinstance(f,ast.FunctionDef)}
        a=blocks(ROOT/'fixtures/live/gapguard.py');b=blocks(ROOT/'reference/gapguard_420.py')
        changed={k for k in a if a[k]!=b[k]}
        self.assertEqual(changed,{'Machine._clear','Machine.gpio','Machine.observe','Machine.status',
            'AutoRecovery.__init__','AutoRecovery.tick','AutoRecovery.advance','GapGuard._ready','GapGuard._drain_edges',
            'GapGuard._gpio_observed','GapGuard._execute_pause','GapGuard._cool_sfs_pause'})
        self.assertEqual(set(b)-set(a),{'AutoRecovery.confirm_resume'})
        from scope421 import assert_scope
        assert_scope(self)

    def test_new_version_and_normal_defaults_unchanged(self):
        src=(ROOT/'fixtures/live/gapguard.py').read_text(encoding='utf-8')
        self.assertEqual(gg.VERSION,'4.2.1-rc1')
        self.assertIn("VERSION = '4.1.0-candidate.14-window6-r2'",src)
        self.assertEqual(gg.Settings.DEFAULTS,dict(suspect_distance=9.,verify_trigger=50.,verify_distance=12.,verify_transitions=6,check_interval=.25,init_guard=.25))

    def test_actual_config_values_preserved(self):
        s=section((ROOT/'printer.cfg').read_bytes(),'gapguard').decode()
        for val in ['suspect_distance: 9.0','verify_trigger: 20.0','verify_distance: 20.0','verify_transitions: 2',
                    'auto_recovery_delay: 30.0','auto_recovery_distance: 300.0','auto_recovery_chunk: 20.0',
                    'auto_recovery_min_transitions: 2','auto_recovery_feedrate: 200']:
            self.assertIn(val,s)

    def test_python37_syntax(self):
        raw=(ROOT.parent/'src/gapguard.py').read_bytes();compile(raw,'gapguard.py','exec');ast.parse(raw,feature_version=(3,7))

if __name__=='__main__':unittest.main(verbosity=2)
