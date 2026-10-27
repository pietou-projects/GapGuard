import ast
import unittest
from pathlib import Path
import gapguard as gg
from test_recovery import Rig

class WindowTests(unittest.TestCase):
    def run_counts(self, counts, threshold=2):
        x=Rig()
        x.r.values['auto_recovery_min_transitions']=threshold
        x.block()
        for index,count in enumerate(counts,1):
            self.assertEqual(x.state(),'BLOCK')
            self.assertEqual(x.r.record['index'],index)
            for _ in range(count):
                x.t+=.01
                x.gpio(1-x.r.pd3)
            x.t=x.finish+.01
            x.tick()
            if x.state()=='FAILED':
                x.tick()
                break
            if index<len(counts):
                x.until('BLOCK',edges=0)
        return x

    def test_runtime_45_edges_accepts_zero_block(self):
        x=self.run_counts([10,12,12,4,7,0])
        self.assertEqual(x.state(),'PURGE')
        self.assertEqual(sum(x.r.record['block_counts']),45)

    def test_first_five_zero_blocks_allowed(self):
        x=self.run_counts([0]*5)
        self.assertEqual(x.state(),'PURGE')
        self.assertEqual(x.r.record['purged'],100.)

    def test_six_zero_blocks_continue_without_early_failure(self):
        x=self.run_counts([0]*6)
        self.assertEqual(x.state(),'PURGE')
        self.assertEqual(x.r.record['purged'],120.)
        self.assertEqual(x.calls.count('G1 E20 F200'),6)
        self.assertNotIn('M24',x.calls)

    def test_one_cumulative_edge_fails(self):
        self.assertEqual(self.run_counts([0,0,1]+[0]*12).state(),'FAILED')

    def test_two_edges_spread_across_blocks_pass(self):
        self.assertEqual(self.run_counts([1,0,0,0,0,1]).state(),'PURGE')

    def test_old_edges_retained_at_seventh(self):
        x=self.run_counts([2,0,0,0,0,0,0])
        self.assertEqual(x.state(),'PURGE')
        self.assertEqual(x.r.record['block_counts'],[2]+[0]*6)
        self.assertEqual(x.r.record['purged'],140.)

    def test_last_six_zero_blocks_preserve_prior_evidence(self):
        x=self.run_counts([2]*9+[0]*6)
        self.assertEqual(x.state(),'SETTLE')
        self.assertEqual(x.r.record['purged'],300.)
        self.assertNotIn('M24',x.calls)
        self.assertFalse(any(' X' in c for c in x.calls))
        x.until('RESUMED',edges=0)
        self.assertEqual(x.calls.count('M24'),1)

    def test_full_purge_no_extra_last_60mm_rule(self):
        x=self.run_counts([2]*12+[0]*3)
        self.assertEqual(x.state(),'SETTLE')
        x.until('RESUMED',edges=0)
        self.assertEqual(x.calls.count('G1 E20 F200'),15)
        self.assertEqual(x.calls.count('M24'),1)
        self.assertEqual(x.r.record['purged'],300.)

    def test_all_fifteen_counts_retained_and_one_final_total(self):
        x=self.run_counts([1]*15)
        windows=[f for e,f in x.events if e=='PD3_WINDOW']
        self.assertEqual(windows,[])
        self.assertEqual([f for e,f in x.events if e=='PD3_TOTAL'],
                         [dict(blocks=15,purged_total=300.,transitions=15,required=2)])
        self.assertEqual(x.r.record['block_counts'],[1]*15)

    def test_configurable_minimum_is_applied(self):
        self.assertEqual(self.run_counts([1]*6+[0]*9,threshold=7).state(),'FAILED')
        self.assertEqual(self.run_counts([1]*6+[0]*9,threshold=6).state(),'SETTLE')

    def test_valid_configurable_threshold(self):
        for v in (1,2,3,8):
            x=Rig()
            r=gg.AutoRecovery(x.o,dict(gg.AutoRecovery.DEFAULTS,auto_recovery_min_transitions=v))
            self.assertEqual(r.values['auto_recovery_min_transitions'],v)
            self.assertEqual(r.total_blocks,15)

    def test_invalid_thresholds_rejected(self):
        for v in (0,-1,1.5,float('nan'),float('inf')):
            with self.subTest(v=v),self.assertRaises(ValueError):
                gg.AutoRecovery(Rig().o,dict(gg.AutoRecovery.DEFAULTS,auto_recovery_min_transitions=v))

    def test_pd4_immediate_before_window_is_full(self):
        x=self.run_counts([0,0]);x.until('BLOCK',edges=0)
        x.gpio(pd4=0)
        self.assertEqual(x.state(),'FAILED')
        x.tick()
        self.assertNotIn('M24',x.calls)
        self.assertEqual(x.calls.count('G1 E20 F200'),3)

    def test_purge_emission_settle_wipe_finalize_byte_identical(self):
        root=Path(__file__).resolve().parent
        before=(root/'reference/window6.gapguard.py').read_bytes()
        after=(root/'reference/gapguard_420.py').read_bytes()
        for start,end in [(b"        elif state == 'PURGE':",b"        elif state == 'BLOCK':"),
                          (b"        elif state == 'SETTLE':",b"        elif state == 'WIPE':"),
                          (b"        elif state == 'FINAL':",b"        elif state == 'RESUMING':")]:
            self.assertEqual(before[before.index(start):before.index(end)],after[after.index(start):after.index(end)])
        self.assertNotIn(b'WINDOW_BLOCKS',after)
        self.assertNotIn(b'PD3_WINDOW',after)
        from scope421 import assert_scope
        assert_scope(self)
