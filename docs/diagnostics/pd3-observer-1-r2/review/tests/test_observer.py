"""Observability and differential tests. Simulations, not printer validation."""
import ast
import collections
import copy
import importlib.util
import json
import logging
import random
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import gapguard as variant
from observer_scope import assert_observer_scope

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('exact_live', ROOT/'baseline/gapguard.py')
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)

class Harness:
    def __init__(self, mod=variant):
        self.mod = mod
        self.time, self.e = 100., 0.
        self.calls = []
        s = mod.Settings(dict(suspect_distance=9., verify_trigger=20., verify_distance=20., verify_transitions=2))
        self.m = mod.Machine(s)
        self.n = mod.Native('printing', True, '/simulated.gcode')
        self.m.start_ready(0., 1)
        self.m.gpio(1., 2, 0.)
        self.m.observe(self.time, self.n, self.e)
        a = self.a = object.__new__(mod.GapGuard)
        a.machine, a.s = self.m, s
        a.motion_trace = True
        a._trace_previous_edge = None
        a._edges = collections.deque()
        a._dead = a._busy = False
        a._boot_snapshot = None
        a._saved_fan1 = a._fan_restore_pending = None
        a._monitor_timer = object()
        a.now = lambda:self.time
        a.position = self.position
        a.native = self.native
        a._wake = lambda:self.calls.append(('wake',))
        a._observe_fan = lambda n:self.calls.append(('fan_observe', n.state, n.active, n.path))
        a.auto_recovery = NS(edge_window=self.window, gpio=self.recovery_gpio)
        a.printer = NS(is_shutdown=lambda:False)
        a.button_group = NS(mcu=NS(is_shutdown=lambda:False))
        a.reactor = NS(NEVER=1e30, update_timer=lambda *args:self.calls.append(('timer', args[1])))
    def position(self, t):
        self.calls.append(('E_read', t))
        return self.e
    def native(self):
        self.calls.append(('native_read',))
        return self.n
    def window(self, t):
        self.calls.append(('recovery_window', t))
        return False
    def recovery_gpio(self, t, accepted):
        self.calls.append(('recovery_gpio', t, accepted))
    def event(self, mask, e=None, eventtime=None):
        self.time += .1
        if e is not None:self.e = e
        self.a._gpio(self.time if eventtime is None else eventtime, mask)
    def observe(self, e=None):
        self.time += .25
        if e is not None:self.e = e
        self.a._monitor(self.time)
    def snapshot(self):
        return dict(machine={k:copy.deepcopy(v) for k,v in vars(self.m).items() if k not in ('s','motion')},
                    motion={k:copy.deepcopy(v) for k,v in vars(self.m.motion).items() if k != 's'},
                    queue=list(self.a._edges), calls=self.calls[:],
                    boot=self.a._boot_snapshot, dead=self.a._dead,
                    trace=self.a._trace_previous_edge)
    def last(self):return self.a._pd3_observer.records[-1]

class ObserverTests(unittest.TestCase):
    def test_exact_scope_and_protected_classes(self):
        assert_observer_scope(self)

    def test_python37_parse(self):
        ast.parse((ROOT/'src/gapguard.py').read_bytes(), feature_version=(3,7))

    def test_no_extra_position_native_or_recovery_reads(self):
        a,b = Harness(baseline),Harness()
        for mask,e in [(3,2.),(2,5.),(2,25.),(3,30.),(2,45.)]:
            a.event(mask,e);b.event(mask,e)
            self.assertEqual(a.snapshot(),b.snapshot())
        self.assertTrue(any(x[0]=='E_read' for x in b.calls))

    def test_entry_before_dead_return(self):
        h=Harness();h.a._dead=True;h.event(3)
        self.assertEqual(h.last()['return']['condition'],'dead')
        self.assertEqual(h.calls,[])

    def test_not_ready_snapshot_preserved_not_electrical_edge(self):
        h=Harness();h.m.ready=False;h.event(3)
        self.assertEqual(h.last()['return']['condition'],'not_ready_boot_snapshot_saved')
        self.assertEqual(h.a._boot_snapshot,3)
        self.assertNotIn('effect',h.last());self.assertEqual(h.calls,[])

    def test_old_callback_timestamp_rejection_values(self):
        h=Harness();h.event(3,eventtime=99.)
        r=h.last()
        self.assertEqual(r['return']['condition'],'eventtime_below_floor')
        self.assertEqual(r['return']['comparisons']['generation_time'],100.)
        self.assertEqual(r['eventtime'],99.)
        self.assertGreater(r['processed_at'],r['eventtime'])

    def test_queue_epoch_generation_and_time_independent(self):
        for epoch_delta,generation_delta,when,failed in [(-1,0,100.,'epoch_equal'),(0,-1,100.,'generation_equal'),(0,0,99.,'time_at_least_floor')]:
            h=Harness();h.a._edges.append((h.m.epoch+epoch_delta,h.m.motion_generation+generation_delta,when,3,8.))
            before=h.m.motion.pd3;h.a._drain_edges();r=h.last()
            self.assertEqual(r['return']['comparisons']['failed'],[failed])
            self.assertEqual(h.m.motion.pd3,before)
            self.assertTrue(r['missing_callback_record'])

    def test_queue_combined_rejection_keeps_all_comparisons(self):
        h=Harness();h.a._edges.append((-1,-1,0.,3,10.));h.a._drain_edges()
        self.assertEqual(h.last()['return']['comparisons']['failed'],['epoch_equal','generation_equal','time_at_least_floor'])

    def test_entry_queue_dequeue_processing_same_record(self):
        h=Harness();h.event(3,2.)
        r=h.last();self.assertEqual(len(h.a._pd3_observer.records),1)
        self.assertEqual(r['id'],1)
        self.assertEqual(r['queued']['E'],2.)
        self.assertEqual(r['processing']['E'],2.)
        self.assertEqual(r['queued']['generation'],r['dequeued']['current']['generation'])
        self.assertTrue(r['effect']['electrical_transition'])

    def test_unknown_bootstrap_is_visible_and_not_counted(self):
        h=Harness();h.m.initialized=False;h.m.motion.pd3=h.m.motion.pd4=None
        h.event(3,2.)
        self.assertIsNone(h.last()['bootstrap_acquisition']['before']['pd3'])
        self.assertFalse(h.last()['effect']['electrical_transition'])
        self.assertFalse(h.last()['effect']['verify_counted'])

    def test_no_change_pd4_only_not_pd3_edge(self):
        h=Harness();h.event(0,2.)
        self.assertFalse(h.last()['effect']['electrical_transition'])
        self.assertEqual(h.m.reason,'PD4_ABSENT')

    def test_partial_real_edge_not_motion_count(self):
        h=Harness();h.m.change_mode('PARTIAL',0.,100.)
        h.event(3,2.)
        self.assertTrue(h.last()['effect']['electrical_transition'])
        self.assertFalse(h.last()['effect']['machine_accepted'])
        self.assertIn('mode_not_FULL',h.last()['effect']['not_accepted_reasons'])

    def test_paused_real_edge_not_motion_count(self):
        h=Harness();h.n=h.mod.Native('paused',False,h.n.path);h.event(3,2.)
        self.assertTrue(h.last()['effect']['electrical_transition'])
        self.assertIn('not_running',h.last()['effect']['not_accepted_reasons'])

    def test_two_verify_edges_boundary_counted(self):
        h=Harness();h.observe(20.1);h.event(3,25.);h.event(2,40.)
        records=list(h.a._pd3_observer.records)
        self.assertTrue(all(r['effect']['verify_counted'] for r in records))
        self.assertEqual(h.last()['processing']['before']['end'],40.)
        self.assertEqual(h.last()['effect']['after']['state'],'NORMAL')
        self.assertEqual(h.last()['effect']['after']['count'],2)

    def test_trigger_edge_priority_is_not_verify_count(self):
        h=Harness();h.observe(20.);h.event(3,20.)
        self.assertFalse(h.last()['effect']['verify_counted'])
        self.assertEqual(h.m.motion.reference,20.)

    def test_edge_beyond_verify_received_but_not_counted(self):
        h=Harness();h.observe(20.1);h.event(3,40.01)
        self.assertTrue(h.last()['effect']['electrical_transition'])
        self.assertTrue(h.last()['effect']['machine_accepted'])
        self.assertFalse(h.last()['effect']['verify_counted'])
        self.assertGreater(h.last()['processing']['E'],h.last()['processing']['before']['end'])

    def test_new_window_first_count_after_previous_count_two(self):
        h=Harness();h.observe(20.1);h.event(3,25.);h.event(2,40.)
        h.event(3,65.)
        self.assertEqual(h.last()['processing']['before']['count'],2)
        self.assertEqual(h.last()['effect']['after']['count'],1)
        self.assertTrue(h.last()['effect']['verify_counted'])

    def test_generation_reject_inside_machine_is_described(self):
        h=Harness();h.a._gpio_observed(100.,3,8.,epoch=h.m.epoch,generation=-1)
        self.assertEqual(h.last()['effect']['not_accepted_reasons'],['generation_valid_false','generation_equal'])

    def test_recovery_window_true_but_machine_uses_normal_branch(self):
        h=Harness();h.a.auto_recovery.edge_window=lambda t:True
        h.observe(20.1);h.event(3,25.)
        self.assertTrue(h.last()['effect']['verify_counted'])

    def test_later_recovery_observer_effect_distinguished(self):
        h=Harness();h.a.auto_recovery.gpio=lambda *args:h.m.motion.reset()
        h.event(3,2.)
        self.assertEqual(h.last()['effect']['after']['state'],'NORMAL')
        self.assertEqual(h.last()['after_recovery_observer']['state'],'DISABLED')

    def test_queue_clear_abandonment(self):
        for action,reason in [('_reset_file','reset_file_queue_clear'),('_shutdown','shutdown_queue_clear')]:
            h=Harness();h.a._drain_edges=lambda:None;h.event(3,2.)
            getattr(h.a,action)()
            self.assertEqual(h.last()['return']['condition'],reason)
            self.assertEqual(len(h.a._edges),0)

    def test_bounded_queue_correlations(self):
        h=Harness();drain=h.a._drain_edges;h.a._drain_edges=lambda:None
        for i in range(1000):h.event(2+i%2,float(i))
        o=h.a._pd3_observer
        self.assertEqual(len(o.records),128);self.assertEqual(len(o.links),128)
        self.assertEqual(o.counters['queue_correlations_evicted'],872)
        drain();self.assertEqual(len(o.links),0)
        self.assertEqual(o.counters['dequeue_without_entry'],1000)
        # Earlier uncorrelated dequeues evict the remaining late records.
        self.assertEqual(len(o.records),128)

    def test_bounded_fault_dumps_and_flush_budget(self):
        h=Harness()
        for i in range(160):h.event(2+i%2,float(i))
        for _ in range(5):h.a._trace_pd3_fault()
        o=h.a._pd3_observer
        self.assertEqual(len(o.pending),2);self.assertEqual(o.counters['dumps_dropped'],3)
        output=[]
        with patch.object(logging,'info',side_effect=lambda fmt,payload:output.append(json.loads(payload))):
            h.a._busy=True;h.a._pd3_diag('flush');self.assertEqual(output,[])
            h.a._busy=False
            for _ in range(66):h.a._pd3_diag('flush')
        self.assertEqual(len(output),66)
        self.assertTrue(all(len(x['records'])<=4 for x in output if x['kind']=='EVENTS'))
        self.assertEqual(len(o.pending),0)
        self.assertTrue(output[-1]['complete'])

    def test_diagnostic_failure_does_not_change_function(self):
        a,b=Harness(baseline),Harness()
        with patch.object(variant.PD3Observer,'entry',side_effect=RuntimeError('simulated observer error')):
            for mask,e in [(3,1.),(2,3.)]:a.event(mask,e);b.event(mask,e)
        self.assertEqual(a.snapshot(),b.snapshot())
        self.assertEqual(b.a._pd3_diag_errors,2)

    def test_logging_failure_does_not_retry_or_block(self):
        h=Harness();h.event(3,2.);h.a._trace_pd3_fault()
        with patch.object(logging,'info',side_effect=OSError('simulated log failure')):
            h.a._pd3_diag('flush');h.a._pd3_diag('flush')
        self.assertEqual(len(h.a._pd3_observer.pending),0)
        self.assertEqual(h.a._pd3_diag_errors,2)

    def test_no_callback_interval_has_explicit_last_entry_and_counter(self):
        h=Harness();h.event(3,2.);h.observe(22.);h.observe(42.)
        h.a._trace_pd3_fault();header=h.a._pd3_observer.pending[0]['header']
        self.assertEqual(header['counters']['callback_entries'],1)
        self.assertEqual(header['last_callback'][0],1)
        self.assertLess(header['last_callback'][2],header['captured_at'])
        self.assertEqual(header['detector']['end'],42.)
        self.assertTrue(all(x['callback_entries']==1 for x in header['checkpoints']))

    def test_original_rearm_resume_traces_retained(self):
        baseline_text=(ROOT/'baseline/gapguard.py').read_text(encoding='utf-8')
        text=(ROOT/'src/gapguard.py').read_text(encoding='utf-8')
        for marker in ('PD3_REARM_BEGIN','PD3_RECOVERY_VALIDATED','PD3_RESUME_GENERATION','PD3_RESUME_ACTIVE','PD3_FIRST_POST_RESUME_EDGE'):
            self.assertEqual(text.count(marker),baseline_text.count(marker))

    def test_randomized_differential_10000_steps(self):
        a,b=Harness(baseline),Harness();r=random.Random(20261101)
        for i in range(10000):
            op=r.randrange(10);delta=r.choice([0.,.1,2.,9.,20.,20.001,-.5]);mask=r.randrange(4)
            for h in (a,b):
                if op<5:h.event(mask,h.e+delta)
                elif op==5:h.observe(h.e+delta)
                elif op==6:
                    h.m.change_mode(('FULL','PARTIAL','BYPASS')[i%3],h.e,h.time)
                elif op==7:
                    h.n=h.mod.Native('paused',False,h.n.path);h.observe()
                elif op==8:
                    h.n=h.mod.Native('printing',True,'/simulated.gcode');h.observe()
                else:
                    h.event(mask,h.e,eventtime=h.time-50.)
            self.assertEqual(a.snapshot(),b.snapshot(),i)
            a.calls.clear();b.calls.clear()

    def test_complete_auto_recovery_equivalence(self):
        import test_recovery as tr
        import test_pd3_generation as tg
        def run(mod):
            with patch.object(tr,'gg',mod),patch.object(tg,'gg',mod):
                h=tg.NaturalRig();samples=[];reads=[]
                orig=h.o.position
                def position(t):reads.append(t);return orig(t)
                h.o.position=position
                for i in range(3):
                    h.fault_naturally();h.until('RESUMED')
                    for _ in range(10):h.feed(1.,edge=True)
                    samples.append((tg.snapshot(h.m),copy.deepcopy(h.r.record)))
                return samples,h.calls,reads,h.gm.saved_states,h.beds
        a,b=run(baseline),run(variant)
        self.assertEqual(a,b)
        self.assertEqual(b[1].count('M24'),3)
        self.assertEqual(b[1].count('G1 E20 F200'),45)

if __name__=='__main__':unittest.main(verbosity=2)
