"""Post-PAUSE hookup and independent invalidation tests; no machine access."""
import ast
import collections
import copy
import types
import unittest
from types import SimpleNamespace as NS
from test_recovery import Rig, P, gg

baseline=types.ModuleType('candidate10_reference')
exec(compile((P/'reference/candidate10.gapguard.py').read_bytes(),
             'candidate10_reference.py','exec'),baseline.__dict__)

def worker_fixture(enabled=1, use_baseline=False, fault='PD3_NO_MOTION'):
    x=Rig(enabled=enabled)
    cls=baseline.GapGuard if use_baseline else gg.GapGuard
    a=object.__new__(cls);a.__dict__.update(vars(x.o))
    a._saved_fan1=a._fan_restore_pending=None;a.motion_trace=False;a.s=x.m.s
    a._scheduled=True;a._busy=False;a._wake_id=1;a._wake_stamp=None;a._wake_time=0
    a._edges=collections.deque();a._trace_previous_edge=None
    a._drain_edges=lambda:None
    a._fan_owned=cls._fan_owned.__get__(a)
    a.script=cls.script.__get__(a)
    x.target=220.;x.fan_value=.5;x.sequence=[];x.hook_calls=[]
    x.raise_pause=False;x.during_pause=None
    def execute(s):
        x.sequence.append(s)
        if s=='PAUSE':
            x.calls.append(s)
            if x.raise_pause:raise ValueError('injected native PAUSE error')
            x.native=gg.Native('paused',False,x.m.path)
            if x.during_pause:x.during_pause()
        elif s.startswith('SET_PIN'):
            x.calls.append(s);x.fan_value=0.
        else:x.script(s)
    a.gcode=NS(get_mutex=lambda:x.mutex,run_script_from_command=execute,respond_info=lambda s:None)
    original_observe=a._observe
    def observe(*args,**kwargs):
        original_observe(*args,**kwargs);x.sequence.append('OBSERVE_COMPLETED')
    a._observe=observe
    if not use_baseline:
        x.handlers.clear()
        a.auto_recovery=gg.AutoRecovery(a,dict(gg.AutoRecovery.DEFAULTS,auto_recovery_enabled=enabled))
        a.auto_recovery.bind()
        completed=a.auto_recovery.pause_completed
        def hook(**kwargs):
            x.sequence.append('HOOK');x.hook_calls.append(kwargs)
            return completed(**kwargs)
        a.auto_recovery.pause_completed=hook
    x.m.pause_dispatched=False;x.m.pause_requested=True
    x.m.reason='PD4_ABSENT' if fault=='PD4_ABSENT' else 'VERIFY_FAIL'
    if fault=='PD4_ABSENT':x.m.motion.pd4=0
    return x,a

def run_worker(x,a):a._worker(x.t,x.m.token(),1)

class HookTests(unittest.TestCase):
    def test_01_hook_after_entire_original_pause_path(self):
        x,a=worker_fixture();run_worker(x,a)
        self.assertEqual(x.sequence,['PAUSE','SET_GCODE_VARIABLE MACRO=RESUME VARIABLE=etemp VALUE=220.0','SET_HEATER_TEMPERATURE HEATER=extruder TARGET=0',
                                    'SET_PIN PIN=fan1 VALUE=0','OBSERVE_COMPLETED','HOOK'])
        self.assertEqual(x.m.pause_error,None)
    def test_02_single_notification(self):
        x,a=worker_fixture();run_worker(x,a);run_worker(x,a)
        self.assertEqual(len(x.hook_calls),1);self.assertEqual(x.calls.count('PAUSE'),1)
    def test_03_no_pd4_notification(self):
        x,a=worker_fixture(fault='PD4_ABSENT');run_worker(x,a)
        self.assertEqual(x.hook_calls,[]);self.assertEqual(x.calls.count('PAUSE'),1)
    def test_04_failed_pause_never_arms(self):
        x,a=worker_fixture();x.raise_pause=True;run_worker(x,a)
        self.assertIsNone(a.auto_recovery.record);self.assertIn('native PAUSE error',x.m.pause_error)
    def test_05_internal_hook_error_cannot_change_pause(self):
        x,a=worker_fixture();ar=a.auto_recovery
        ar.fingerprint=lambda:(_ for _ in ()).throw(ValueError('injected fingerprint error'))
        run_worker(x,a)
        self.assertEqual(x.m.pause_error,None);self.assertEqual(x.native.state,'paused')
        self.assertEqual(x.target,0.);self.assertEqual(x.fan_value,0.)
        self.assertEqual(ar.hook_error,'injected fingerprint error');self.assertIsNone(ar.record)
    def test_06_disabled_matches_candidate10(self):
        old,ao=worker_fixture(use_baseline=True);new,an=worker_fixture(enabled=0)
        run_worker(old,ao);run_worker(new,an)
        self.assertEqual([c for c in new.calls if not c.startswith('SET_GCODE_VARIABLE MACRO=RESUME VARIABLE=etemp')],old.calls)
        self.assertIn('SET_GCODE_VARIABLE MACRO=RESUME VARIABLE=etemp VALUE=220.0',new.calls)
        self.assertEqual(new.m.pause_origin,'gapguard')
        snap=lambda m:{k:v for k,v in vars(m).items() if k not in ('s','motion','pause_origin')}
        self.assertEqual(snap(new.m),snap(old.m))
        self.assertEqual(dict(vars(new.m.motion),s=None),dict(vars(old.m.motion),s=None))
        self.assertEqual((new.target,new.fan_value),(old.target,old.fan_value))
        self.assertIsNone(an.auto_recovery.record)
    def test_07_hook_has_no_immediate_actions_or_machine_mutations(self):
        x=Rig();x.native=gg.Native('paused',False,x.m.path);x.m.observe(x.t,x.native,x.position(x.t))
        snapshot=copy.deepcopy(vars(x.m));parser=copy.deepcopy(x.gm.saved_states)
        x.r.pause_completed(x.fault,x.m.token(),x.m.path)
        self.assertEqual(x.calls,[]);self.assertEqual(x.gm.saved_states,parser)
        current=vars(x.m)
        for k in snapshot:
            if k not in ('s','motion','pause_origin'):self.assertEqual(current[k],snapshot[k])
        self.assertEqual(dict(vars(x.m.motion),s=None),dict(vars(snapshot['motion']),s=None))
        self.assertEqual(x.r.record['state'],'ARMED')
    def test_08_delay_starts_after_notification_and_completion(self):
        x,a=worker_fixture();run_worker(x,a);ar=a.auto_recovery
        self.assertNotIn('deadline',ar.record);notification=ar.record['notified_at']
        x.finish=x.t+4;x.t+=1;ar.tick(x.t)
        for cb in list(x.callbacks):cb(x.t)
        x.callbacks.clear();self.assertEqual(ar.record['state'],'ARMED')
        x.t=x.finish+1;ar.tick(x.t)
        for cb in list(x.callbacks):cb(x.t)
        self.assertGreater(ar.record['deadline'],notification+30.)
        self.assertEqual(ar.record['deadline'],x.t+30.)
    def test_09_original_reset_shutdown_identical(self):
        def method(path,name):
            raw=path.read_bytes();tree=ast.parse(raw.decode());lines=raw.splitlines(True)
            cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='GapGuard')
            m=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==name)
            return b''.join(lines[m.lineno-1:m.end_lineno])
        for name in ('_reset_file','_shutdown'):
            self.assertEqual(method(P.parent/'src/gapguard.py',name),method(P/'reference/candidate10.gapguard.py',name))
    def test_10_all_own_event_handlers_revoke_queued_callbacks(self):
        for event in ('klippy:shutdown','klippy:disconnect','gcode:request_restart','virtual_sdcard:reset_file'):
            x=Rig();x.pause();x.r.tick(x.t);self.assertTrue(x.callbacks)
            before=copy.deepcopy(x.gm.saved_states);n=len(x.calls);generation=x.r.generation
            x.handlers[event][0](123.)
            for cb in x.callbacks:cb(x.t)
            self.assertEqual(x.calls[n:],[]);self.assertEqual(x.gm.saved_states,before)
            self.assertEqual(x.r.generation,generation+1)
            self.assertEqual(x.timer_updates[-1][1],x.o.reactor.NEVER)
    def test_11_cancel_during_wait_no_future_actions(self):
        x=Rig();x.pause();x.until('WAIT');x.cancel();n=len(x.calls);x.tick(60);self.assertEqual(x.calls[n:],[])
    def test_12_manual_resume_during_wait_no_future_actions(self):
        x=Rig();x.pause();x.until('WAIT');x.native=gg.Native('printing',True,x.m.path)
        n=len(x.calls);x.tick(60);x.tick();self.assertEqual(x.calls[n:],[])
    def test_13_epoch_file_not_authorization(self):
        x=Rig();x.native=gg.Native('paused',False,x.m.path)
        self.assertIsNotNone(x.r.pause_completed(x.fault,(x.m.epoch+1,0),'/other'))
    def test_14_invalidated_old_callback_cannot_clear_new_pending(self):
        x=Rig();x.pause();x.r.tick(x.t);old=x.callbacks.pop()
        x.handlers['virtual_sdcard:reset_file'][0]();x.m.reset(x.t)
        x.native=gg.Native('printing',True,'/next');x.m.observe(x.t,x.native,0.)
        x.m.request_pause('VERIFY_FAIL');x.fault=x.m.claim_pause(x.native)
        x.pause();x.r.tick(x.t);self.assertTrue(x.r.pending)
        old(x.t);self.assertTrue(x.r.pending)
    def test_15_all_original_worker_lines_in_order(self):
        def worker(path):
            raw=path.read_bytes();t=ast.parse(raw.decode());lines=raw.splitlines(True)
            c=next(n for n in t.body if isinstance(n,ast.ClassDef) and n.name=='GapGuard')
            m=next(n for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='_worker')
            return lines[m.lineno-1:m.end_lineno]
        old=worker(P/'reference/candidate10.gapguard.py');new=iter(worker(P.parent/'src/gapguard.py'))
        self.assertTrue(all(any(line==candidate for candidate in new) for line in old))
    def test_16_no_exception_escape_even_if_hook_replaced(self):
        x,a=worker_fixture();a.auto_recovery.pause_completed=lambda **kw:(_ for _ in ()).throw(RuntimeError('bad hook'))
        run_worker(x,a);self.assertEqual(x.m.pause_error,None);self.assertFalse(a._busy)
    def test_17_pause_error_not_extra_authorization(self):
        x,a=worker_fixture();x.fail_command='HEATER=extruder TARGET=0';run_worker(x,a)
        self.assertEqual(len(x.hook_calls),1);self.assertIsNotNone(x.m.pause_error)
        self.assertIsNotNone(a.auto_recovery.record)
    def test_18_epoch_change_does_not_suppress_hook(self):
        x,a=worker_fixture();x.during_pause=lambda:x.m.reset(x.t)
        run_worker(x,a);self.assertEqual(len(x.hook_calls),1);self.assertIsNotNone(a.auto_recovery.record)
    def test_19_notification_has_no_persistent_lock(self):
        x=Rig();old=x.pause()
        new=x.r.pause_completed(x.fault,x.m.token(),x.m.path)
        self.assertIsNotNone(new);self.assertIsNot(new,old)
        self.assertEqual(new['block_counts'],[])
    def test_20_enabled_matches_native_pause_actions(self):
        old,ao=worker_fixture(use_baseline=True);new,an=worker_fixture(enabled=1)
        run_worker(old,ao);run_worker(new,an);self.assertEqual([c for c in new.calls if not c.startswith('SET_GCODE_VARIABLE MACRO=RESUME VARIABLE=etemp')],old.calls)
        self.assertIn('SET_GCODE_VARIABLE MACRO=RESUME VARIABLE=etemp VALUE=220.0',new.calls)
        self.assertEqual(new.m.pause_origin,'gapguard')
        self.assertEqual(new.native.state,old.native.state)
    def test_21_hook_timer_failure_no_deferred_recovery(self):
        x=Rig();x.o.reactor.update_timer=lambda *a:(_ for _ in ()).throw(ValueError('timer failure'))
        self.assertIsNone(x.pause());self.assertIsNone(x.r.record);self.assertEqual(x.r.hook_error,'timer failure')
        self.assertEqual(x.r.tick(x.t),x.o.reactor.NEVER);self.assertEqual(x.calls,[])
    def test_22_passive_gpio_failure_does_not_block_detector(self):
        x,a=worker_fixture();a.auto_recovery.gpio=lambda *a:(_ for _ in ()).throw(ValueError('observer failure'))
        calls=[];a._drain_edges=lambda:calls.append('native drain');a._wake=lambda:calls.append('native wake')
        a._gpio(x.t,3);self.assertEqual(calls,['native drain','native wake']);self.assertEqual(len(a._edges),1)
    def test_23_no_private_gapguard_reset_called_by_events(self):
        x=Rig();x.pause()
        def forbidden(*a):raise AssertionError('private reset called')
        x.o._shutdown=x.o._reset_file=forbidden
        for name in ('klippy:shutdown','klippy:disconnect','gcode:request_restart','virtual_sdcard:reset_file'):
            x.handlers[name][0]()
    def test_24_invalidation_during_heating_emission_revokes_wait(self):
        x=Rig();x.on_command=lambda s:x.handlers['virtual_sdcard:reset_file'][0]() if s.startswith('SET_HEATER') else None
        x.pause();x.until('FAILED');n=len(x.calls);x.tick(100);self.assertEqual(x.calls[n:],[])
    def test_25_manual_pause_command_has_no_auto_hook(self):
        old=(P/'reference/candidate10.gapguard.py').read_text(encoding='utf-8')
        new=(P.parent/'src/gapguard.py').read_text(encoding='utf-8')
        def cmd(text):
            c=next(n for n in ast.parse(text).body if isinstance(n,ast.ClassDef) and n.name=='GapGuard')
            return ast.dump(next(n for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='cmd_pause'))
        self.assertEqual(cmd(old),cmd(new))

if __name__=='__main__':unittest.main(verbosity=2)
