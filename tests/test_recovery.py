"""Targeted .10 -> .14 tests, including the exact native G-code parser.

No network or machine access. Test clocks and motors are simulated.
"""
import ast
import copy
import hashlib
import json
import math
import re
import shlex
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
import gapguard as gg

P = Path(__file__).resolve().parent
EVIDENCE = json.loads((P/'evidence/native_sources.json').read_text(encoding='utf-8'))
ns = {'__name__': 'exact_native_gcode_move'}
exec(compile(EVIDENCE['extras/gcode_move.py']['text'], 'exact_gcode_move.py', 'exec'), ns)
NativeGcodeMove = ns['GCodeMove']

class Mutex:
    def __init__(self): self.locked=False;self.acquisitions=0
    def test(self): return self.locked
    def __enter__(self):
        assert not self.locked, 'unexpected blocking mutex wait'
        self.acquisitions+=1
        self.locked=True
    def __exit__(self,*args): self.locked=False

class Gcmd:
    def __init__(self, command):
        self.command=command
        self.params={}
        for word in shlex.split(command)[1:]:
            if '=' in word: k,v=word.split('=',1)
            else:k,v=word[0],word[1:]
            self.params[k.upper()]=v
    def get(self,k,default=None):return self.params.get(k,default)
    def get_float(self,k,default=None,**kw):
        return float(self.params[k]) if k in self.params else default
    def get_int(self,k,default=None,**kw):return int(self.get(k,default))
    def get_command_parameters(self):return self.params
    def get_commandline(self):return self.command
    error=ValueError

class Rig:
    def __init__(self, enabled=1):
        self.t=100.;self.calls=[];self.callbacks=[];self.shut=False
        self.submissions=[];self.last_move_submission=None;self.move_records=[]
        self.fail_command=None;self.on_command=None;self.commands_with_mutex=[]
        self.native=gg.Native('printing',True,'/cube.gcode')
        self.heater=NS(min_temp=0.,max_temp=300.,can_extrude=True)
        self.temp=220.;self.target=0.;self.heater.get_temp=lambda t:(self.temp,self.target)
        self.fan_value=0.;self.beds=[60.,60.,60.,60.]
        self.mutex=Mutex();self.finish=99.;self.move_start=99.;self.start_e=0.;self.end_e=0.
        self.commanded=[25.,29.,210.,0.];self.end_confirm=True
        self.gm=object.__new__(NativeGcodeMove)
        self.gm.absolute_coord=True;self.gm.absolute_extrude=False
        self.gm.base_position=[0.,0.,0.,0.];self.gm.homing_position=[0.,0.,0.,0.]
        self.gm.last_position=list(self.commanded)
        self.gm.speed=100.;self.gm.speed_factor=1./60.;self.gm.extrude_factor=1.
        self.gm.move_with_transform=self.move
        self.gm.saved_states={}
        self.gm.cmd_SAVE_GCODE_STATE(Gcmd('SAVE_GCODE_STATE NAME=timelapse_state_a'))
        self.gm.saved_states['timelapse_state_a']['last_position']=[100.,100.,5.,200.]
        self.gm.saved_states['timelapse_state_a']['absolute_extrude']=True
        self.gm.cmd_SAVE_GCODE_STATE(Gcmd('SAVE_GCODE_STATE NAME=timelapse_state_b'))
        self.gm.saved_states['timelapse_state_b']['last_position']=[103.,100.,10.,198.]
        self.rv=dict(saved_x=100.,saved_y=100.,saved_z=5.,saved_e=200.,etemp=220.,flag_print_status=1)
        self.pv=dict(flag_print_status=0)
        self.pr=NS(is_paused=False,sd_paused=False,pause_command_sent=False)
        self.m=gg.Machine(gg.Settings(dict(verify_trigger=20.,verify_distance=20.,verify_transitions=2)))
        self.m.start_ready(0.,1);self.m.gpio(1.,3,0.);self.m.observe(self.t,self.native,0.)
        self.m.request_pause('VERIFY_FAIL');self.fault=self.m.claim_pause(self.native)
        self.fan=dict(epoch=self.m.epoch,path=self.m.path,value=.5,scale=255.,phase='off')
        self.toolhead=NS(get_position=lambda:list(self.commanded),
                         get_last_move_time=lambda:self.finish,check_busy=self.busy)
        self.o=NS(machine=self.m,_dead=False,now=lambda:self.t,native=lambda:self.native,
                  position=self.position,extruder_name='extruder',_saved_fan1=self.fan,
                  _fan_owned=lambda r:r is self.fan and r is not None,
                  _ui_emit=lambda text:None,
                  mcu=NS(estimated_print_time=lambda t:t,is_shutdown=lambda:self.shut),
                  extruder=NS(get_heater=lambda:self.heater),
                  fan1=NS(scale=255.,get_status=lambda t:{'value':self.fan_value}))
        self.o.reactor=NS(register_timer=lambda cb:cb,update_timer=lambda *a:None,
            register_callback=lambda cb,when:self.callbacks.append(cb),NOW=0.,NEVER=1e30)
        objs={'toolhead':self.toolhead,'gcode_move':self.gm,'pause_resume':self.pr,
              'gcode_macro RESUME':NS(get_status=lambda t:dict(self.rv)),
              'gcode_macro PAUSE':NS(get_status=lambda t:dict(self.pv))}
        self.handlers={};self.timer_updates=[]
        self.o.reactor.update_timer=lambda timer,when:self.timer_updates.append((timer,when))
        self.o.printer=NS(lookup_object=lambda name:objs[name],is_shutdown=lambda:self.shut,
                          register_event_handler=lambda event,cb:self.handlers.setdefault(event,[]).append(cb))
        self.o.gcode=NS(get_mutex=lambda:self.mutex)
        self.o.script=self.script
        values=dict(gg.AutoRecovery.DEFAULTS,auto_recovery_enabled=enabled)
        self.r=gg.AutoRecovery(self.o,values);self.r.bind()
        self.events=[];self.r.emit=lambda event,**fields:self.events.append((event,dict(fields)))
    def busy(self,t):return self.finish,t,self.end_confirm
    def position(self,t):
        if self.finish<=self.move_start:return self.end_e
        f=max(0.,min(1.,(t-self.move_start)/(self.finish-self.move_start)))
        return self.start_e+(self.end_e-self.start_e)*f
    def move(self,pos,speed):
        submission=len(self.submissions)
        queued=self.t<=self.finish
        if queued:
            assert self.state()=='WIPE' and submission==self.last_move_submission, 'movement queued outside a single WIPE script'
        start=max(self.t,self.finish) if queued else self.t
        self.start_e=self.position(self.t);self.end_e=pos[3];self.move_start=self.t
        xyz=math.sqrt(sum((pos[i]-self.commanded[i])**2 for i in range(3)))
        distance=xyz if xyz else abs(pos[3]-self.commanded[3])
        assert -5.<=pos[0]<=815.5 and -1.<=pos[1]<=805.5 and -12.<=pos[2]<=1020.
        self.finish=start+distance/speed
        self.move_records.append(dict(submission=submission,phase=self.state(),
            submitted_at=self.t,mutex_acquisition=self.mutex.acquisitions,
            start=start,finish=self.finish,speed=speed,
            delta=[a-b for a,b in zip(pos,self.commanded)]))
        self.last_move_submission=submission
        self.commanded=list(pos)
    def script(self,text):
        assert self.mutex.test(), 'G-code without mutex'
        self.submissions.append(dict(text=text,time=self.t,mutex_acquisition=self.mutex.acquisitions))
        for line in text.splitlines():
            self.calls.append(line);self.commands_with_mutex.append(self.mutex.test())
            if self.fail_command and self.fail_command in line:raise ValueError('injected send failure')
            c=Gcmd(line);name=line.split()[0]
            if name=='SET_HEATER_TEMPERATURE':self.target=c.get_float('TARGET')
            elif name=='SET_GCODE_VARIABLE':
                (self.rv if c.get('MACRO')=='RESUME' else self.pv)[c.get('VARIABLE')]=c.get_float('VALUE')
            elif name=='M24':self.native=gg.Native('printing',True,self.m.path)
            else:getattr(self.gm,'cmd_'+name)(c)
            if self.on_command:self.on_command(line)
    def arm(self):
        token=self.m.token()
        self.native=gg.Native('paused',False,self.m.path)
        self.m.observe(self.t,self.native,self.position(self.t))
        self.fan.update(epoch=self.m.epoch,path=self.m.path)
        return self.r.pause_completed(self.fault,token,self.m.path)
    def pause(self):return self.arm()
    def tick(self,dt=.25):
        self.t+=dt;self.r.tick(self.t)
        todo,self.callbacks=self.callbacks,[]
        for cb in todo:cb(self.t)
    def gpio(self,pd3=None,pd4=1,when=None):
        if pd3 is None:pd3=self.r.pd3
        self.r.gpio(self.t if when is None else when,pd3+2*pd4)
        self.m.motion.acquire(pd3+2*pd4)
    def state(self):return self.r.record['state'] if self.r.record else 'IDLE'
    def until(self,state,maxsteps=4000,edges=2):
        seen=set()
        for _ in range(maxsteps):
            if self.state()==state:return
            if self.state()=='FAILED' and state!='FAILED':raise AssertionError(self.r.record)
            if self.state()=='BLOCK':
                i=self.r.record['index']
                if i not in seen:
                    for j in range(edges):
                        self.t+=.01;self.gpio(1-self.r.pd3)
                    seen.add(i)
            self.tick()
        raise AssertionError('timeout '+self.state())
    def block(self):
        self.pause();self.until('BLOCK');return self.r.record
    def success(self):
        self.pause();self.until('RESUMED')
    def cancel(self):
        self.native=gg.Native('cancelled',False,None);self.m.reset(self.t)
        self.r.invalidate('reset_file')

class RecoveryTests(unittest.TestCase):
    def test_01_no_pd4_recovery(self):
        x=Rig();x.fault='PD4_ABSENT';self.assertIsNone(x.arm())
    def test_02_first_pd3_eligible(self):
        x=Rig();self.assertEqual(x.arm()['state'],'ARMED')
    def test_03_no_session_limit_setting(self):
        x=Rig();self.assertNotIn('auto_recovery_max_per_session',x.r.values)
        self.assertFalse(hasattr(x.r,'used_key'));self.assertIsNotNone(x.arm())
    def test_04_original_pause_executor_unchanged(self):
        self.assert_method_unchanged('native_pause')  # target snapshot is the requested thermal change
        tree=ast.parse((P.parent/'src/gapguard.py').read_text(encoding='utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='GapGuard')
        w=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_worker')
        calls=[n for n in ast.walk(w) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='_execute_pause']
        self.assertEqual(len(calls),1)
    def macro(self,data,name):
        return re.search(rb'(?m)^\[gcode_macro '+name.encode()+rb'\][\s\S]*?(?=^\[|\Z)',data).group()
    def test_05_pause_bytes(self):self.assert_macro('PAUSE')
    def test_06_resume_bytes(self):self.assert_macro('RESUME')
    def assert_macro(self,name):
        self.assertEqual(self.macro((P/'printer.cfg').read_bytes(),name),self.macro((P/'fixtures/live/printer.cfg').read_bytes(),name))
    def test_07_no_resume_call(self):
        x=Rig();x.success();self.assertNotIn('RESUME',x.calls)
    def test_08_no_base_resume_call(self):
        x=Rig();x.success();self.assertNotIn('BASE_RESUME',x.calls)
    def test_09_no_early_m24(self):
        x=Rig();x.block();self.assertNotIn('M24',x.calls)
    def test_10_delay_after_physical_pause(self):
        x=Rig();r=x.pause();x.finish=x.t+3
        x.tick();self.assertEqual(x.state(),'ARMED')
        x.t=x.finish+1;x.tick();self.assertEqual(r['deadline'],x.t+30)
    def test_11_wait_nonblocking_no_commands(self):
        x=Rig();r=x.pause();x.tick();x.tick(29.);self.assertEqual(x.calls,[]);self.assertFalse(x.mutex.test())
    def test_12_pd4_loss_wait_latched(self):
        x=Rig();x.pause();x.tick();x.gpio(pd4=0);x.gpio(pd4=1);x.tick();self.assertEqual(x.state(),'FAILED');self.assertNotIn('M24',x.calls)
    def test_13_bad_target(self):
        for v in (0.,-1.,float('nan'),301.):
            x=Rig();x.rv['etemp']=v;x.pause();x.until('FAILED');self.assertFalse(any(s.startswith('G1') for s in x.calls))
    def test_14_only_extruder_heated(self):
        x=Rig();x.block();self.assertEqual([s for s in x.calls if s.startswith('SET_HEATER')],['SET_HEATER_TEMPERATURE HEATER=extruder TARGET=220.0'])
    def test_15_beds_untouched(self):
        x=Rig();x.success();self.assertEqual(x.beds,[60.]*4);self.assertFalse(any('heater_bed' in s for s in x.calls))
    def test_16_no_fan_restore_during_recovery(self):
        x=Rig();x.success();self.assertFalse(any('fan1' in s for s in x.calls));self.assertEqual(x.fan['phase'],'off')
    def test_17_exactly_15_blocks(self):
        x=Rig();x.success();self.assertEqual(x.calls.count('G1 E20 F200'),15)
    def test_18_chunk_physical_20(self):
        x=Rig();x.gm.extrude_factor=.9;x.gm.speed_factor=.8/60.;x.block();self.assertAlmostEqual(x.end_e-x.start_e,20.)
    def test_19_total_300(self):
        x=Rig();x.success();self.assertEqual(x.r.record['purged'],300.);self.assertAlmostEqual(x.end_e,300.)
    def test_20_no_e300(self):
        x=Rig();x.success();self.assertFalse(any('E300' in s for s in x.calls))
    def test_21_no_extra_native_purge(self):
        x=Rig();x.success();self.assertFalse(any('E140' in s or 'E100' in s for s in x.calls))
    def test_22_f200(self):
        x=Rig();x.block();self.assertAlmostEqual(x.finish-x.move_start,6.)
    def test_23_only_real_edges_unknown_excluded(self):
        x=Rig();r=x.block();x.r.pd3=None;x.gpio(1);self.assertEqual(r['count'],0);x.gpio(0);self.assertEqual(r['count'],1)
    def test_24_pd4_only_not_counted(self):
        x=Rig();r=x.block();x.gpio();self.assertEqual(r['count'],0)
    def test_25_zero_edges_fail(self):self.assert_block_fails(0)
    def test_26_one_edge_fails(self):self.assert_block_fails(1)
    def assert_block_fails(self,n):
        x=Rig();x.block()
        for i in range(n):x.gpio(1-x.r.pd3)
        x.until('FAILED',edges=0);x.tick();self.assertEqual(x.calls.count('G1 E20 F200'),15)
        self.assertEqual(x.r.record['purged'],300.)
    def test_27_two_edges_next(self):
        x=Rig();x.block();x.until('PURGE');self.assertEqual(x.r.record['index'],1)
    def test_28_pd4_midblock(self):
        x=Rig();x.block();x.tick(2);x.gpio(pd4=0);x.tick();self.assertEqual(x.state(),'FAILED');self.assertEqual(x.target,0.)
    def test_29_no_more_blocks_failed(self):self.assert_block_fails(0)
    def test_30_no_wipe_failed(self):
        x=Rig();x.block();x.until('FAILED',edges=0);x.tick();self.assertFalse(any(' X' in s for s in x.calls))
    def test_31_no_m24_failed(self):
        x=Rig();x.block();x.until('FAILED',edges=0);x.tick();self.assertNotIn('M24',x.calls)
    def test_32_native_pause_kept(self):
        x=Rig();x.block();x.until('FAILED',edges=0);x.tick();self.assertEqual(x.native.state,'paused')
    def test_33_hotend_zero_failed(self):
        x=Rig();x.block();x.until('FAILED',edges=0);x.tick();self.assertEqual(x.target,0.)
    def test_34_parser_restored_no_move(self):
        x=Rig();x.gm.absolute_extrude=True;x.gm.extrude_factor=.93;x.block();x.until('FAILED',edges=0);x.tick()
        self.assertTrue(x.gm.absolute_extrude);self.assertEqual(x.gm.extrude_factor,.93);self.assertEqual(x.commanded[:3],[25.,29.,210.])
    def test_35_saved_e_failure(self):
        x=Rig();x.block();x.until('FAILED',edges=0);x.tick();self.assertAlmostEqual(x.gm._get_gcode_position()[3],200.)
    def test_36_validated_only_15(self):
        x=Rig();x.success();events=[e for e,f in x.events];self.assertEqual(events.count('CHUNK_OK'),15);self.assertEqual(events.count('PURGE_OK'),1)
    def test_37_settle_two_seconds(self):
        x=Rig();x.pause();x.until('SETTLE');n=len(x.calls);x.tick(1.9);self.assertEqual(len(x.calls),n);x.tick(.2);self.assertEqual(x.state(),'WIPE')
    def test_38_exact_wipe_sequence(self):
        x=Rig();x.success();self.assertEqual([s for s in x.calls if s.startswith('G1 X')],['G1 X-20 F15000','G1 X20','G1 X-20','G1 X20','G1 X-20','G1 X20'])
    def test_39_final_restore_order(self):
        x=Rig();x.success();rs=[s for s in x.calls if s.startswith('RESTORE')]
        self.assertEqual(rs,['RESTORE_GCODE_STATE NAME=timelapse_state_b MOVE=1 MOVE_SPEED=250','RESTORE_GCODE_STATE NAME=timelapse_state_a MOVE=1 MOVE_SPEED=50'])
    def test_40_g92_saved_e(self):
        x=Rig();x.success();self.assertIn('G92 E200.0',x.calls)
    def test_41_flags_and_order(self):
        x=Rig();x.success();self.assertEqual(x.rv['flag_print_status'],0);self.assertEqual(x.pv['flag_print_status'],1)
        self.assertLess(x.calls.index('SET_GCODE_VARIABLE MACRO=PAUSE VARIABLE=flag_print_status VALUE=1'),x.calls.index('RESTORE_GCODE_STATE NAME=timelapse_state_b MOVE=1 MOVE_SPEED=250'))
    def test_42_fan_observer_unchanged(self):
        for n in ('_observe_fan','_restore_fan','_pause_fan_off','_capture_pause_fan'):self.assert_method_unchanged(n)
    def test_43_unique_m24(self):
        x=Rig();x.success();x.tick(10);self.assertEqual(x.calls.count('M24'),1)
    def test_44_same_session_confirmation(self):
        x=Rig();x.success();self.assertEqual(x.r.record['key'],x.r.key());self.assertEqual(x.events[-1][0],'RESUMED')
    def cancel_at(self,state):
        x=Rig();x.pause();x.until(state);n=len(x.calls);x.cancel();x.tick(40);self.assertEqual(x.calls[n:],[]);self.assertNotIn('M24',x.calls)
    def test_45_cancel_wait(self):self.cancel_at('WAIT')
    def test_46_cancel_heat(self):self.cancel_at('HEAT')
    def test_47_cancel_block(self):self.cancel_at('BLOCK')
    def test_48_cancel_wipe(self):self.cancel_at('WIPE')
    def test_49_cancel_before_m24(self):
        x=Rig();x.pause();x.until('FINAL')
        for _ in range(100):
            if x.r.record['final']>=4:break
            self.assertNotEqual(x.state(),'FAILED');x.tick()
        self.assertEqual(x.r.record['final'],4)
        x.cancel();x.tick();self.assertNotIn('M24',x.calls)
    def test_50_manual_resume_invalidates(self):
        x=Rig();x.block();x.native=gg.Native('printing',True,x.m.path);n=len(x.calls);x.tick();x.tick(40);self.assertEqual(x.calls[n:],[])
    def test_51_different_file(self):
        x=Rig();x.block();x.native=gg.Native('paused',False,'/other');n=len(x.calls);x.tick();x.tick();self.assertEqual(x.calls[n:],[])
    def test_52_epoch_changed(self):
        x=Rig();x.block();x.m.epoch+=1;n=len(x.calls);x.tick();x.tick();self.assertEqual(x.calls[n:],[])
    def test_53_shutdown(self):
        x=Rig();x.block();x.shut=True;x.r.invalidate('shutdown');n=len(x.calls);x.tick();self.assertEqual(x.calls[n:],[])
    def test_54_gcode_send_error(self):
        x=Rig();x.fail_command='G1 E20';x.pause();x.until('FAILED');x.tick();self.assertEqual(x.native.state,'paused');self.assertEqual(x.target,0.)
    def test_55_thermal_loss(self):
        x=Rig();x.block();x.temp=180.;x.tick();x.tick();self.assertEqual(x.state(),'FAILED');self.assertEqual(x.target,0.)
    def test_56_no_used_status_after_success(self):
        x=Rig();x.success();self.assertNotIn('used',x.r.status())
    def test_57_second_fault_same_print_recovers(self):
        x=Rig();x.success();epoch=x.m.epoch
        x.m.observe(x.t,x.native,x.position(x.t));x.m.request_pause('VERIFY_FAIL');x.m.claim_pause(x.native)
        x.rv['flag_print_status']=1;x.pv['flag_print_status']=0;x.target=0.
        self.assertIsNotNone(x.arm());x.until('RESUMED')
        self.assertEqual(x.m.epoch,epoch);self.assertEqual(x.calls.count('M24'),2)
        self.assertEqual(x.calls.count('G1 E20 F200'),30)
    def test_58_sfs_lifecycle_unchanged(self):
        for n in ('_observe','_monitor','cmd_mode','cmd_pause','native'):self.assert_method_unchanged(n)
        a=ast.parse((P/'reference/candidate10.gapguard.py').read_text(encoding='utf-8'));b=ast.parse((P.parent/'src/gapguard.py').read_text(encoding='utf-8'))
        for name in ('Motion','Settings','Native'):
            get=lambda t:ast.dump(next(n for n in t.body if isinstance(n,ast.ClassDef) and n.name==name))
            self.assertEqual(get(a),get(b))
    def test_59_compile(self):compile((P.parent/'src/gapguard.py').read_bytes(),'gapguard.py','exec')
    def test_60_python37(self):ast.parse((P.parent/'src/gapguard.py').read_text(encoding='utf-8'),feature_version=(3,7))
    def test_61_stale_callback_cannot_act(self):
        x=Rig();x.pause();x.r.tick(x.t);x.cancel();n=len(x.calls)
        for cb in x.callbacks:cb(x.t)
        self.assertEqual(x.calls[n:],[])
    def test_62_busy_manual_resume_invalidates_before_m24(self):
        x=Rig();x.block();x.mutex.locked=True;x.r.tick(x.t);self.assertEqual(x.state(),'FAILED')
        x.native=gg.Native('printing',True,x.m.path);x.mutex.locked=False;n=len(x.calls);x.tick();self.assertEqual(x.calls[n:],[])
    def test_63_existing_motion_guard_during_purge_retained(self):
        x=Rig();x.block();x.gm.last_position[0]+=5;x.tick();self.assertEqual(x.state(),'FAILED')
    def test_64_missing_native_saved_state(self):
        x=Rig();del x.gm.saved_states['timelapse_state_b'];self.assertIsNone(x.pause())
        self.assertIsNotNone(x.r.hook_error);x.tick();self.assertEqual(x.calls,[])
    def test_65_temp_state_not_start_authorization(self):
        x=Rig();x.gm.saved_states[x.r.TEMP_STATE]={};x.success();self.assertEqual(x.state(),'RESUMED')
    def test_66_completion_timeout(self):
        x=Rig();x.block();x.end_confirm=False;x.t=x.finish+6;x.tick();x.tick();self.assertEqual(x.state(),'FAILED');self.assertNotIn('M24',x.calls)
    def test_67_heat_timeout(self):
        x=Rig();x.temp=50.;x.pause();x.until('HEAT');x.tick(601);x.tick();self.assertEqual(x.state(),'FAILED');self.assertEqual(x.target,0.)
    def test_68_native_can_extrude_required(self):
        x=Rig();x.heater.can_extrude=False;x.pause();x.until('HEAT');x.tick(5);self.assertEqual(x.state(),'HEAT');self.assertFalse(any('G1' in s for s in x.calls))
    def test_69_heater_low_boundary_accepted(self):
        x=Rig();x.temp=216.;x.block();self.assertEqual(x.state(),'BLOCK')
    def test_70_heater_high_boundary(self):
        x=Rig();x.temp=270.01;x.pause();x.until('HEAT');x.tick(1);self.assertEqual(x.state(),'HEAT')
    def test_71_cancel_during_emission_revalidates(self):
        x=Rig();x.on_command=lambda s:x.cancel() if s=='G1 E20 F200' else None
        x.pause();x.until('FAILED');x.tick();self.assertEqual(x.calls.count('G1 E20 F200'),1);self.assertNotIn('M24',x.calls)
    def test_72_late_callback_not_counted(self):
        x=Rig();r=x.block();x.t=x.finish+1;x.gpio(1-x.r.pd3);self.assertEqual(r['count'],0)
    def test_73_no_cross_block_edge_credit(self):
        x=Rig();x.block();x.until('PURGE');x.tick();self.assertEqual(x.r.record['count'],0)
    def test_74_m24_error_cleans_flags_no_retry(self):
        x=Rig();x.fail_command='M24';x.pause();x.until('FAILED');x.tick();x.tick()
        self.assertEqual(x.calls.count('M24'),1);self.assertEqual(x.target,0.);self.assertEqual(x.rv['flag_print_status'],1);self.assertEqual(x.native.state,'paused')
    def test_75_no_resumed_trace_before_observation(self):
        x=Rig();x.pause();x.until('RESUMING');self.assertNotIn('RESUMED',[e for e,f in x.events]);x.tick();self.assertEqual(x.events[-1][0],'RESUMED')
    def test_76_config_delta_only(self):
        cfg=(P/'printer.cfg').read_bytes();base=(P/'fixtures/live/printer.cfg').read_bytes()
        def functional(b):return [l for l in b.splitlines() if l.strip() and not l.lstrip().startswith(b'#') and not l.startswith(b'auto_recovery_max_per_session:')]
        from test_requested_changes import section
        self.assertEqual(functional(cfg.replace(section(cfg,'idle_timeout'),b'')),functional(base.replace(section(base,'idle_timeout'),b'')))
        self.assertNotIn(b'auto_recovery_max_per_session',cfg)
        self.assertIn(gg.VERSION.encode(),cfg)
    def test_77_no_stats_collision(self):self.assertFalse(hasattr(gg.GapGuard,'stats'));self.assertFalse(hasattr(Rig().r,'stats'))
    def test_78_no_new_pin_api(self):
        source=ast.get_source_segment((P.parent/'src/gapguard.py').read_text(encoding='utf-8'),next(n for n in ast.parse((P.parent/'src/gapguard.py').read_text(encoding='utf-8')).body if isinstance(n,ast.ClassDef) and n.name=='AutoRecovery'))
        for token in ('buttons_add','pulse_counter','PD3_PIN_REINIT','wait_moves(',"script('PAUSE')","script('RESUME')",'G4 P','TEMPERATURE_WAIT'):
            self.assertNotIn(token,source)
    def test_79_disabled_config(self):x=Rig(enabled=0);self.assertIsNone(x.arm())
    def test_80_diagnostic_parameters_not_silently_changed(self):
        x=Rig();v=dict(gg.AutoRecovery.DEFAULTS,auto_recovery_distance=440)
        with self.assertRaises(ValueError):gg.AutoRecovery(x.o,v)
    def test_81_fan_not_authorization(self):
        x=Rig();x.o._saved_fan1=None;x.o._fan_owned=lambda r:False;x.fan_value=.5
        x.success();self.assertEqual(x.state(),'RESUMED');self.assertEqual(x.fan_value,.5)
    def test_82_native_pause_flags_are_false(self):
        x=Rig();x.pause();x.until('WAIT');self.assertFalse(x.pr.is_paused)
    def test_83_native_flags_not_start_authorization(self):
        x=Rig();x.pr.is_paused=True;x.pause();x.until('HEAT')
        self.assertIn('SET_HEATER_TEMPERATURE HEATER=extruder TARGET=220.0',x.calls)
    def test_84_exact_source_native_purge_is_100(self):
        macro=self.macro((P/'reference/candidate10.printer.cfg').read_bytes(),'RESUME')
        self.assertIn(b'G1 E100 F200',macro);self.assertNotIn(b'G1 E140',macro)
    def test_85_parser_factors_restore_on_success(self):
        x=Rig();x.gm.saved_states['timelapse_state_a']['extrude_factor']=.93
        x.gm.saved_states['timelapse_state_a']['speed_factor']=.8/60.
        x.success();self.assertEqual(x.gm.extrude_factor,.93);self.assertEqual(x.gm.speed_factor,.8/60.)
    def test_86_no_trace_off_dependency(self):
        x=Rig();x.o.motion_trace=False;x.success();self.assertEqual(x.state(),'RESUMED')
    def test_87_native_worker_pause_once_and_arm_hook(self):
        import collections
        x=Rig();a=object.__new__(gg.GapGuard);a.__dict__.update(vars(x.o))
        a._saved_fan1=a._fan_restore_pending=None;a.motion_trace=False;a.s=x.m.s
        a._scheduled=True;a._busy=False;a._wake_id=1;a._wake_stamp=None;a._wake_time=0
        a._edges=collections.deque();a._trace_previous_edge=None
        a._drain_edges=lambda:None
        a._fan_owned=gg.GapGuard._fan_owned.__get__(a)
        a.script=gg.GapGuard.script.__get__(a)
        def execute(s):
            if s=='PAUSE':
                x.calls.append(s);x.native=gg.Native('paused',False,x.m.path)
            elif s.startswith('SET_PIN'):x.calls.append(s);x.fan_value=0.
            else:x.script(s)
        a.gcode=NS(get_mutex=lambda:x.mutex,run_script_from_command=execute,respond_info=lambda s:None)
        a.auto_recovery=gg.AutoRecovery(a,gg.AutoRecovery.DEFAULTS);a.auto_recovery.bind()
        x.m.pause_dispatched=False;x.m.pause_requested=True;x.m.reason='VERIFY_FAIL'
        a._worker(x.t,x.m.token(),1)
        self.assertEqual(x.calls.count('PAUSE'),1);self.assertEqual(a.auto_recovery.record['notified_at'],x.t)
        self.assertEqual(a._saved_fan1['phase'],'off')
    def test_88_fan_restored_only_on_real_lifecycle(self):
        import collections
        x=Rig();x.pause();x.until('WAIT')
        a=object.__new__(gg.GapGuard);a.__dict__.update(vars(x.o));a._fan_restore_pending=None
        a.motion_trace=False;a.s=x.m.s;a._edges=collections.deque()
        a._fan_owned=gg.GapGuard._fan_owned.__get__(a)
        a._drain_edges=lambda:None
        a.script=lambda s:x.calls.append(s)
        a._observe(x.t,x.native,x.position(x.t));self.assertEqual(x.callbacks,[])
        x.native=gg.Native('printing',True,x.m.path)
        a._observe(x.t,x.native,x.position(x.t));self.assertEqual(len(x.callbacks),1)
        for cb in list(x.callbacks):cb(x.t)
        self.assertIn('SET_PIN PIN=fan1 VALUE=127.5',x.calls);self.assertIsNone(a._saved_fan1)
    def test_89_epoch_is_diagnostic_only(self):
        x=Rig();r=x.block();x.m.epoch+=1;x.gpio(1-x.r.pd3);self.assertEqual(r['count'],1)
    def test_90_new_session_eligible_after_terminal(self):
        x=Rig();x.pause();x.until('WAIT');x.cancel();x.tick()
        x.native=gg.Native('printing',True,'/new.gcode');x.m.observe(x.t,x.native,0.)
        x.m.request_pause('VERIFY_FAIL');x.fault=x.m.claim_pause(x.native)
        self.assertIsNotNone(x.arm())
    def test_91_no_parser_authorization_before_wait(self):
        x=Rig();x.pause();x.gm.last_position[0]+=1;x.tick();self.assertEqual(x.state(),'WAIT');self.assertEqual(x.calls,[])
    def test_92_new_fault_can_rearm_after_pd4_failure(self):
        x=Rig();x.pause();x.until('WAIT');x.gpio(pd4=0);x.gpio(pd4=1);x.tick(40)
        self.assertEqual(x.state(),'FAILED');self.assertIsNotNone(x.arm())
    def test_93_partial_distance_not_undone(self):
        x=Rig();x.block();x.tick(3);x.gpio(pd4=0);self.assertAlmostEqual(x.r.record['purged'],10.)
        x.tick();self.assertFalse(any(s.startswith('G1 E-') for s in x.calls))
    def test_94_flags_recoverable_on_restore_failure(self):
        x=Rig();x.fail_command='NAME=timelapse_state_b MOVE=1';x.pause();x.until('FAILED');x.tick()
        self.assertEqual(x.rv['flag_print_status'],1);self.assertEqual(x.pv['flag_print_status'],0)
        self.assertNotIn('M24',x.calls)
    def test_95_gpio_pd4_loss_during_pause_macro(self):
        x=Rig();x.gpio(pd4=0);self.assertIsNone(x.pause());x.tick()
        self.assertEqual(x.state(),'IDLE');self.assertNotIn('M24',x.calls)
    def test_97_quantized_extruder_position_accepted(self):
        x=Rig();step=28.845/(200*16*5.2)
        exact=x.o.position;x.o.position=lambda t:round(exact(t)/step)*step
        x.success();self.assertEqual(x.r.record['purged'],300.)
    def test_98_executed_distance_mismatch_rejected(self):
        x=Rig();x.block();x.end_e-=.02;x.until('FAILED');self.assertNotIn('M24',x.calls)
    def test_99_nonfinite_executed_distance_rejected(self):
        x=Rig();x.block();x.o.position=lambda t:float('nan');x.until('FAILED');self.assertNotIn('M24',x.calls)
    def test_100_cancel_handler_invalidates_without_native_state_write(self):
        x=Rig();x.block();snapshot=copy.deepcopy(x.gm.saved_states);x.cancel();x.tick()
        self.assertEqual(x.gm.saved_states,snapshot);self.assertFalse(x.r.record['temp_saved'])
        self.assertIsNotNone(x.r.orphan_temp)
    def test_101_external_state_replacement_not_deleted(self):
        x=Rig();x.block();other={'external':True};x.gm.saved_states[x.r.TEMP_STATE]=other
        x.cancel();x.tick();self.assertIs(x.gm.saved_states[x.r.TEMP_STATE],other)
    def assert_method_unchanged(self,name):
        def get(path):
            raw=path.read_bytes();tree=ast.parse(raw.decode());lines=raw.splitlines(True)
            cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='GapGuard')
            f=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==name)
            return b''.join(lines[f.lineno-1:f.end_lineno])
        self.assertEqual(get(P.parent/'src/gapguard.py'),get(P/'reference/candidate10.gapguard.py'))

if __name__=='__main__':unittest.main(verbosity=2)
