"""Réarmement commun, générations et 100 cycles naturels; aucune machine réelle."""
import collections,copy,json,os,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace as NS
from test_recovery import Rig,gg
from test_requested_changes import machine,adapter,render_idle,apply_heaters
from scope421 import assert_scope

def snapshot(m):
    return dict(mode=m.mode,state=m.motion.state,reference=m.motion.reference,
                position=m.motion.position,verify_start=m.motion.verify_start,
                verify_end=m.motion.verify_end,count=m.motion.count,
                last_edge_position=m.motion.last_edge_position,pd3=m.motion.pd3,
                pd4=m.motion.pd4,initialized=m.initialized,generation=m.motion_generation,
                pause_requested=m.pause_requested,pause_dispatched=m.pause_dispatched,
                reason=m.reason)

class NaturalRig(Rig):
    """Natural detector fault -> real adapter worker -> simulated Elegoo macro.

    Only motors, native macro execution and clocks are simulated. Detection,
    queue, pause executor, recovery, lifecycle and fan observer are production.
    """
    def __init__(self):
        super().__init__(initial_fault=False)
        self.target=220.;self.fan_value=.5
        a=self.o;a._saved_fan1=a._fan_restore_pending=None
        a._observe_fan=gg.GapGuard._observe_fan.__get__(a)
        a._fan_owned=gg.GapGuard._fan_owned.__get__(a)
        a._scheduled=False;a._busy=False;a._wake_id=0
        a._wake_stamp=None;a._wake_time=float('inf')
        a.gcode.run_script_from_command=self.script
        a.gcode.respond_info=lambda text:None
    def script(self,text):
        if text=='PAUSE':
            assert self.mutex.test()
            self.calls.append(text)
            self.native=gg.Native('paused',False,self.m.path)
            self.rv.update(etemp=self.target,saved_e=self.gm._get_gcode_position()[3],flag_print_status=1)
            self.pv['flag_print_status']=0
            return
        if text.startswith('SET_PIN PIN=fan1'):
            assert self.mutex.test();self.calls.append(text)
            self.fan_value=float(text.split('VALUE=')[1])/255.;return
        super().script(text)
    def feed(self,distance,edge=False):
        self.t=max(self.t,self.finish)+.1
        e=self.end_e+distance
        self.start_e=self.end_e=e;self.finish=self.move_start=self.t-.01
        self.commanded[3]=self.gm.last_position[3]=e
        if edge:self.gpio(1-self.m.motion.pd3)
        self.o._observe(self.t,self.native,e)
    def fault_naturally(self):
        # No request_pause injection: the ordinary 9/20/20/2 detector decides.
        self.feed(9.);assert self.m.motion.state=='SUSPECT'
        self.feed(11.);assert self.m.motion.state=='VERIFY_50'
        self.feed(20.);assert self.m.pause_requested
        self.o._wake_id+=1
        self.o._worker(self.t,self.m.token(),self.o._wake_id)
        assert self.m.last_fault=='PD3_NO_MOTION'
        assert self.native.state=='paused'

class GenerationTests(unittest.TestCase):
    def test_common_primitive_equivalence_manual_partial_full_and_recovery(self):
        x=NaturalRig();y=NaturalRig()
        x.m.motion.state=y.m.motion.state='HARD'
        x.m.motion.count=y.m.motion.count=17
        x.m.motion.verify_start=y.m.motion.verify_start=10.
        x.m.motion.verify_end=y.m.motion.verify_end=20.
        x.m.pause_requested=y.m.pause_requested=True
        x.m.reason=y.m.reason='VERIFY_FAIL'
        x.m.change_mode('PARTIAL',0.,x.t)
        x.m.change_mode('FULL',0.,x.t)
        y.m.running=False
        y.m.rearm_pd3(0.,y.t,'AUTO_RECOVERY',phase='RECOVERY')
        self.assertEqual(snapshot(x.m),snapshot(y.m))
        for r in (x,y):
            before=snapshot(r.m)
            self.assertFalse(r.m.gpio(r.t,2,999.,generation=r.m.motion_generation-1))
            self.assertEqual(snapshot(r.m),before)
        with patch.object(y.m,'rearm_pd3',wraps=y.m.rearm_pd3) as called:
            y.fault='PD3_NO_MOTION';y.pause();y.until('WAIT')
            self.assertEqual(called.call_count,1)
            self.assertEqual(called.call_args.args[2],'AUTO_RECOVERY')

    def test_main_motion_accepts_purge_edges(self):
        x=Rig();r=x.block();self.assertEqual(x.m.motion.state,'ARMING')
        with patch.object(x.m.motion,'edge',wraps=x.m.motion.edge) as edge:
            x.t+=.1;x.gpio(0);x.t+=.1;x.gpio(1)
            self.assertEqual(edge.call_count,2)
        self.assertEqual(x.m.motion.state,'NORMAL')
        self.assertEqual(x.m.motion_edges,2);self.assertEqual(r['count'],2)
        self.assertFalse(x.m.running)

    def test_two_main_edges_only_complete_full_purge(self):
        x=Rig();x.block();x.t+=.1;x.gpio(0);x.t+=.1;x.gpio(1)
        x.until('RESUMED',edges=0)
        self.assertEqual(x.calls.count('G1 E20 F200'),15)
        self.assertEqual(sum(x.r.record['block_counts']),2)
        self.assertEqual(x.calls.count('M24'),1)

    def test_unknown_is_acquisition_not_movement(self):
        x=Rig();r=x.block();x.m.motion.pd3=None;x.t+=.1;x.gpio(1)
        self.assertEqual(x.m.motion_edges,0);self.assertEqual(r['count'],0)
        self.assertEqual(x.m.motion.state,'ARMING')

    def test_pd4_event_does_not_credit_motion(self):
        x=Rig();r=x.block();x.gpio(pd4=0)
        self.assertEqual(x.m.motion_edges,0);self.assertEqual(r['count'],0)
        self.assertEqual(x.state(),'FAILED')

    def test_old_generation_cannot_change_electrical_baseline(self):
        x=Rig();x.block();before=snapshot(x.m)
        x.o._edges.append((x.m.epoch,x.m.motion_generation-1,x.t,0,999.))
        x.o._drain_edges();self.assertEqual(snapshot(x.m),before)

    def test_pre_pause_queue_discarded_by_recovery_generation(self):
        x=Rig();old=x.m.motion_generation;x.block();before=snapshot(x.m)
        x.o._edges.append((x.m.epoch,old,x.t,0,999.));x.o._drain_edges()
        self.assertEqual(snapshot(x.m),before);self.assertEqual(x.r.record['count'],0)

    def test_old_timestamp_rejected_even_with_current_tag(self):
        x=Rig();x.block();before=snapshot(x.m)
        x.o._gpio(x.m.generation_time-.001,0)
        self.assertEqual(snapshot(x.m),before)

    def test_purge_event_rejected_in_resume_generation(self):
        x=Rig();x.pause();x.until('RESUMING');r=x.r.record
        baseline=(x.m.motion.pd3,x.m.motion.pd4)
        x.o._edges.append((x.m.epoch,r['purge_generation'],x.t,0,999.))
        x.o._drain_edges()
        self.assertEqual((x.m.motion.pd3,x.m.motion.pd4),baseline)
        self.assertEqual(x.m.motion.state,'ARMING');self.assertEqual(x.m.motion_edges,0)

    def test_resume_generation_exists_before_m24(self):
        x=Rig();observed=[]
        def on(cmd):
            if cmd=='M24':observed.append((x.m.motion_generation,x.m.motion.state,x.r.record['resume_generation']))
        x.on_command=on;x.success()
        self.assertEqual(len(observed),1)
        self.assertEqual(observed[0],(x.m.motion_generation,'ARMING',x.m.motion_generation))

    def test_lifecycle_does_not_rearm_prepared_generation(self):
        x=Rig();x.pause();x.until('RESUMING');g=x.m.motion_generation
        with patch.object(x.m.motion,'arm',wraps=x.m.motion.arm) as arm:
            x.tick();x.tick();self.assertEqual(arm.call_count,0)
        self.assertEqual(x.m.motion_generation,g)

    def test_first_post_resume_edge_enters_normal(self):
        x=Rig();x.success();self.assertEqual(x.m.motion.state,'ARMING')
        x.t+=.1;x.gpio(1-x.m.motion.pd3)
        self.assertEqual(x.m.motion.state,'NORMAL');self.assertEqual(x.m.motion_edges,1)

    def test_incoherent_detector_blocks_commit_even_with_documentary_counts(self):
        for state in ('HARD','DISABLED','VERIFY_50'):
            x=Rig();x.pause();x.until('FINAL');x.m.motion.state=state
            x.until('FAILED');x.tick()
            self.assertNotIn('M24',x.calls);self.assertEqual(x.target,0.)
            self.assertEqual(x.beds,[60.]*4)

    def test_documentary_counter_cannot_validate_without_main_edges(self):
        x=Rig();x.block();x.r.record['count']=999;x.r.record['block_counts']=[999]
        x.until('FAILED',edges=0);x.tick();self.assertNotIn('M24',x.calls)

    def test_pending_fault_prevents_commit(self):
        x=Rig();x.pause();x.until('FINAL');x.m.pause_requested=True;x.m.reason='VERIFY_FAIL'
        x.until('FAILED');x.tick();self.assertNotIn('M24',x.calls)

    def test_generation_change_after_validation_prevents_m24(self):
        x=Rig();x.pause();x.until('SETTLE')
        x.m.rearm_pd3(x.position(x.t),x.t,'MANUAL_FULL')
        x.until('FAILED');x.tick();self.assertNotIn('M24',x.calls)

    def test_after_physical_block_finish_not_counted(self):
        x=Rig();r=x.block();x.t=x.finish+.01;x.gpio(0)
        self.assertEqual(r['count'],0);self.assertEqual(x.m.motion_edges,0)

    def test_exact_physical_finish_edge_accepted(self):
        x=Rig();r=x.block();x.t=x.finish;x.gpio(0)
        self.assertEqual(r['count'],1);self.assertEqual(x.m.motion_edges,1)

    def test_between_blocks_not_counted(self):
        x=Rig();x.block();x.until('PURGE',edges=0);x.gpio(0)
        self.assertEqual(x.m.motion_edges,0)

    def test_submitted_but_not_physically_started_is_not_purge_evidence(self):
        x=Rig();r=x.block();x.gpio(0,when=x.move_start)
        self.assertEqual(r['count'],0);self.assertEqual(x.m.motion_edges,0)

    def test_actual_confirm_matches_manual_partial_full(self):
        manual=Rig(initial_fault=False);auto=Rig()
        for x in (manual,auto):
            x.m.motion.state='HARD';x.m.motion.count=17
            x.m.motion.verify_start=20.;x.m.motion.verify_end=40.
        auto.pause();auto.until('WAIT')
        manual.t=auto.t
        manual.m.change_mode('PARTIAL',0.,manual.t)
        manual.m.change_mode('FULL',0.,manual.t)
        self.assertEqual(snapshot(manual.m),snapshot(auto.m))
        if os.environ.get('GAPGUARD_TEST_EVIDENCE_DIR'):
            p=Path(os.environ['GAPGUARD_TEST_EVIDENCE_DIR']);p.mkdir(parents=True,exist_ok=True)
            (p/'equivalence.json').write_text(json.dumps({'manual_partial_full':snapshot(manual.m),
                'autorecovery_confirm':snapshot(auto.m),'equal':True},indent=2),encoding='utf-8')

    def test_wrong_file_cannot_confirm_resume(self):
        x=Rig();x.pause();x.until('RESUMING')
        x.native=gg.Native('printing',True,'/other.gcode');x.tick()
        self.assertNotEqual(x.state(),'RESUMED')
        x.tick(11);self.assertEqual(x.state(),'FAILED')

    def test_passive_confirmation_works_with_mutex_busy(self):
        x=Rig();x.pause();x.until('RESUMING');g=x.m.motion_generation
        x.mutex.locked=True;x.r.tick(x.t)
        self.assertEqual(x.state(),'RESUMED');self.assertEqual(x.m.motion_generation,g)

    def test_manual_resume_still_rearms_without_prepared_generation(self):
        m,n=machine();m.observe(12.,gg.Native('paused',False,n.path),5.);g=m.motion_generation
        m.observe(15.,n,8.)
        self.assertEqual(m.motion_generation,g+1);self.assertEqual(m.motion.reference,8.)
        self.assertEqual(m.motion.state,'ARMING')

    def test_manual_full_after_recovery_has_same_functional_reset(self):
        x=Rig();x.success();before=snapshot(x.m)
        x.m.change_mode('PARTIAL',x.position(x.t),x.t)
        x.m.change_mode('FULL',x.position(x.t),x.t)
        after=snapshot(x.m);before['generation']=after['generation']
        self.assertEqual(before,after)

    def test_b_to_a_short_gap_no_pause(self):
        x=NaturalRig();x.feed(8.);x.feed(2.,edge=True);x.feed(8.,edge=True)
        self.assertEqual(x.m.motion.state,'NORMAL');self.assertNotIn('PAUSE',x.calls)

    def test_a_to_b_initial_long_gap_then_healthy_motion(self):
        x=NaturalRig();x.fault_naturally();x.until('RESUMED');x.feed(1.,edge=True)
        for _ in range(100):x.feed(2.,edge=True)
        self.assertEqual(x.calls.count('PAUSE'),1);self.assertEqual(x.calls.count('M24'),1)
        self.assertEqual(x.m.motion.state,'NORMAL');self.assertFalse(x.m.pause_requested)

    def test_100_complete_natural_cycles_same_session(self):
        x=NaturalRig();epoch=x.m.epoch;rows=[];generations=set()
        for cycle in range(1,101):
            x.fault_naturally();self.assertEqual(x.target,0.)
            x.until('RESUMED');r=x.r.record;g=x.m.motion_generation
            self.assertNotIn(g,generations);generations.add(g)
            self.assertEqual(x.m.motion.state,'ARMING');self.assertEqual(x.m.motion.count,0)
            self.assertEqual(x.m.motion_edges,0);self.assertIsNone(x.m.motion.last_edge_position)
            self.assertEqual(x.m.motion.reference,x.position(x.t));self.assertIsNone(x.m.motion.verify_start)
            self.assertIsNone(x.m.motion.verify_end);self.assertFalse(x.m.pause_requested)
            self.assertFalse(x.m.pause_dispatched);self.assertIsNone(x.m.reason)
            self.assertIsNone(x.m.active_fault);self.assertFalse(x.o._edges)
            baseline=(x.m.motion.pd3,x.m.motion.pd4)
            x.o._edges.append((epoch,r['purge_generation'],x.t,0,999.));x.o._drain_edges()
            self.assertEqual((x.m.motion.pd3,x.m.motion.pd4),baseline)
            x.feed(1.,edge=True);self.assertEqual(x.m.motion.state,'NORMAL')
            self.assertEqual(x.m.motion_edges,1);self.assertEqual(x.m.epoch,epoch)
            x.tick();self.assertEqual(x.fan_value,.5);self.assertEqual(x.beds,[60.]*4)
            self.assertEqual(x.calls.count('PAUSE'),cycle);self.assertEqual(x.calls.count('M24'),cycle)
            self.assertEqual(x.calls.count('G1 E20 F200'),15*cycle)
            rows.append(dict(cycle=cycle,epoch=epoch,purge_generation=r['purge_generation'],
                             resume_generation=g,purged=r['purged'],transitions=sum(r['block_counts']),
                             first_edge_state=x.m.motion.state,m24=1))
        if os.environ.get('GAPGUARD_TEST_EVIDENCE_DIR'):
            p=Path(os.environ['GAPGUARD_TEST_EVIDENCE_DIR']);p.mkdir(parents=True,exist_ok=True)
            (p/'100_cycles.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')

    def test_exact_unchanged_native_thermal_fan_and_configuration_scope(self):
        assert_scope(self)

    def test_four_bed_idle_targets_preserved_during_recovery(self):
        x=NaturalRig();x.fault_naturally();x.until('BLOCK')
        heaters=dict(extruder=220.,heater_bed=51.,heater_bed1=52.,heater_bed2=53.,heater_bed3=54.)
        apply_heaters(render_idle(x.m.status(x.native)),heaters)
        self.assertEqual(heaters,dict(extruder=0.,heater_bed=51.,heater_bed1=52.,heater_bed2=53.,heater_bed3=54.))

    def test_no_automatic_retry_after_failure(self):
        x=NaturalRig();x.fault_naturally();x.until('FAILED',edges=0);x.tick();n=len(x.calls)
        for _ in range(100):x.tick()
        self.assertEqual(len(x.calls),n);self.assertNotIn('M24',x.calls)

    def test_failed_m24_retires_prepared_generation_before_manual_resume(self):
        x=Rig();x.fail_command='M24';x.pause();x.until('FAILED');x.tick()
        self.assertIsNone(x.m.resume_generation);self.assertEqual(x.m.motion_phase,'IDLE')
        old=x.m.motion_generation;x.native=gg.Native('printing',True,x.m.path)
        x.o._drain_edges();self.assertEqual(x.m.motion_generation,old+1)
        self.assertEqual(x.m.motion.state,'ARMING')

    def test_invalidate_retires_only_owned_generation(self):
        x=Rig();x.pause();x.until('RESUMING');old=x.m.motion_generation
        x.r.invalidate('request_restart')
        self.assertIsNone(x.m.resume_generation);self.assertEqual(x.m.motion_generation,old+1)
        x.m.rearm_pd3(x.position(x.t),x.t,'MANUAL_FULL');before=snapshot(x.m)
        x.r.invalidate('duplicate event');self.assertEqual(snapshot(x.m),before)

    def test_old_armed_record_cannot_rearm_a_new_file(self):
        x=Rig();x.pause();x.m.epoch+=1;g=x.m.motion_generation
        x.tick();self.assertEqual(x.state(),'FAILED')
        self.assertEqual(x.m.motion_generation,g);self.assertEqual(x.calls,[])

    def test_required_logs_are_emitted(self):
        with self.assertLogs(level='INFO') as capture:
            x=NaturalRig();x.fault_naturally();x.until('RESUMED');x.feed(1.,edge=True)
        text='\n'.join(capture.output)
        for event in ('PD3_REARM_BEGIN','PD3_RECOVERY_EDGE','PD3_RECOVERY_VALIDATED',
                      'PD3_RESUME_GENERATION','PD3_RESUME_ACTIVE','PD3_FIRST_POST_RESUME_EDGE'):
            self.assertIn(event,text)

if __name__=='__main__':unittest.main()
