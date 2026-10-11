"""4.2.0-rc1 regressions; no network, simulated time and physical positions."""
import ast
import difflib
import hashlib
import unittest
from pathlib import Path
import gapguard as gg
from test_recovery import Rig
from test_requested_changes import section

ROOT = Path(__file__).resolve().parent

def blocks(path):
    raw=path.read_bytes();lines=raw.splitlines(True);tree=ast.parse(raw);out={}
    for node in tree.body:
        if isinstance(node,ast.FunctionDef):
            out[node.name]=b''.join(lines[node.lineno-1:node.end_lineno])
        elif isinstance(node,ast.ClassDef):
            for f in node.body:
                if isinstance(f,ast.FunctionDef):
                    out[node.name+'.'+f.name]=b''.join(lines[f.lineno-1:f.end_lineno])
    return out

class CumulativeTests(unittest.TestCase):
    def run_purge(self,counts):
        self.assertEqual(len(counts),15)
        x=Rig();x.block()
        for index,count in enumerate(counts,1):
            self.assertEqual(x.state(),'BLOCK');self.assertEqual(x.r.record['index'],index)
            self.assertEqual(x.native.state,'paused');self.assertFalse(x.native.active)
            for _ in range(count):x.t+=.01;x.gpio(1-x.r.pd3)
            x.t=x.finish-.001;x.tick(0)
            self.assertEqual(x.state(),'BLOCK')
            self.assertEqual(x.r.record['purged'],20.*(index-1))
            self.assertNotIn('M24',x.calls)
            self.assertNotIn('PD3_TOTAL',[e for e,f in x.events])
            x.t=x.finish+.01;x.tick(0)
            self.assertEqual(x.r.record['block_counts'],counts[:index])
            self.assertEqual(x.r.record['purged'],20.*index)
            if index<15:
                self.assertEqual(x.state(),'PURGE')
                self.assertNotIn('PURGE_OK',[e for e,f in x.events])
                x.until('BLOCK',edges=0)
        self.assertEqual(x.calls.count('G1 E20 F200'),15)
        self.assertEqual(x.r.record['purged'],300.)
        self.assertEqual([f for e,f in x.events if e=='PD3_TOTAL'],
                         [dict(blocks=15,purged_total=300.,transitions=sum(counts),required=2)])
        self.assertNotIn('PD3_WINDOW',[e for e,f in x.events])
        return x

    def assert_success(self,counts):
        x=self.run_purge(counts);self.assertEqual(x.state(),'SETTLE')
        self.assertNotIn('M24',x.calls)
        x.until('RESUMED',edges=0)
        self.assertEqual(x.calls.count('M24'),1)
        self.assertEqual(x.calls.count('G1 E20 F200'),15)
        self.assertEqual(x.native.state,'printing');self.assertTrue(x.native.active)
        return x

    def assert_failure(self,counts):
        x=self.run_purge(counts);self.assertEqual(x.state(),'FAILED');x.tick()
        self.assertEqual(x.native.state,'paused');self.assertFalse(x.native.active)
        self.assertNotIn('M24',x.calls)
        self.assertFalse(any(' X' in c for c in x.calls))
        self.assertNotIn('PURGE_OK',[e for e,f in x.events])
        return x

    def test_a_two_edges_first_block_only(self):self.assert_success([2]+[0]*14)
    def test_b_two_edges_before_last_120mm(self):self.assert_success([0,0,2]+[0]*12)
    def test_b_user_example_three_edges_block_three(self):self.assert_success([0,0,3]+[0]*12)
    def test_c_one_first_one_last(self):self.assert_success([1]+[0]*13+[1])
    def test_d_one_total_fails_only_at_300mm(self):self.assert_failure([1]+[0]*14)
    def test_e_zero_total_fails_only_at_300mm(self):self.assert_failure([0]*15)
    def test_f_many_distributed_edges(self):self.assert_success([3,0,4,2,0]*3)
    def test_no_early_pass_with_eight_first_edges(self):self.assert_success([8]+[0]*14)

    def test_final_failure_logs_total_before_fail(self):
        x=self.assert_failure([0]*14+[1]);names=[e for e,f in x.events]
        self.assertLess(names.index('PD3_TOTAL'),names.index('FAIL'))

    def test_each_block_logs_all_required_measurements_and_total(self):
        counts=[2,0,1,0,0]*3;x=self.assert_success(counts)
        chunks=[f for e,f in x.events if e=='CHUNK_OK']
        self.assertEqual(len(chunks),15)
        for i,(count,fields) in enumerate(zip(counts,chunks),1):
            self.assertEqual(fields,dict(index='%d/15'%i,distance=20,transitions=count,
                 total_transitions=sum(counts[:i]),purged_total=20.*i,PD4='PRESENT'))

    def test_pd4_loss_overrides_already_sufficient_total(self):
        x=Rig();x.block()
        for _ in range(2):x.t+=.01;x.gpio(1-x.r.pd3)
        x.t=x.finish+.01;x.tick();x.until('BLOCK',edges=0)
        self.assertEqual(sum(x.r.record['block_counts']),2)
        x.gpio(pd4=0);self.assertEqual(x.state(),'FAILED');x.tick()
        self.assertEqual(x.native.state,'paused');self.assertNotIn('M24',x.calls)
        self.assertNotIn('PD3_TOTAL',[e for e,f in x.events])

class WipeTests(unittest.TestCase):
    def capture(self,speed_factor=1./60.,extrude_factor=1.):
        x=Rig();x.gm.speed_factor=speed_factor;x.gm.extrude_factor=extrude_factor
        moves=[]
        def record(pos,speed):
            moves.append(dict(phase=x.state(),delta=[a-b for a,b in zip(pos,x.commanded)],speed=speed))
            x.move(pos,speed)
        x.gm.move_with_transform=record
        x.success()
        return x,moves

    def test_six_relative_x_moves_at_250_mm_s_in_native_parser(self):
        x,moves=self.capture();wipe=[m for m in moves if m['phase']=='WIPE']
        self.assertEqual([m['delta'] for m in wipe],[[d,0.,0.,0.] for d in (-20,20,-20,20,-20,20)])
        self.assertEqual([m['speed'] for m in wipe],[250.]*6)
        self.assertEqual(x.gm.absolute_coord,True)

    def test_feedrate_inheritance_after_purge_and_overrides(self):
        x,moves=self.capture(.8/60.,.93)
        wipe=[m for m in moves if m['phase']=='WIPE']
        self.assertEqual([m['speed'] for m in wipe],[250.]*6)
        purge=[m for m in moves if m['phase']=='BLOCK']
        self.assertEqual(len(purge),15)
        for m in purge:
            self.assertAlmostEqual(m['delta'][3],20.)
            self.assertAlmostEqual(m['speed'],200./60.)
        restore=[m['speed'] for m in moves if m['phase']=='FINAL']
        self.assertEqual(restore,[250.,50.])

    def test_settle_and_final_unchanged_around_wipe(self):
        a=(ROOT/'fixtures/live/gapguard.py').read_bytes();b=(ROOT.parent/'src/gapguard.py').read_bytes()
        for start,end in [(b"        elif state == 'SETTLE':",b"        elif state == 'WIPE':"),
                          (b"        elif state == 'FINAL':",b"        elif state == 'RESUMING':")]:
            self.assertEqual(a[a.index(start):a.index(end)],b[b.index(start):b.index(end)])

class ScopeTests(unittest.TestCase):
    def test_previous_proposal_function_changes_exact(self):
        a=blocks(ROOT/'fixtures/previous_proposal/gapguard.py');b=blocks(ROOT.parent/'src/gapguard.py')
        self.assertEqual(set(a),set(b))
        self.assertEqual({k for k in a if a[k]!=b[k]},
                         {'human_status','human_debug','AutoRecovery.__init__','AutoRecovery.advance','GapGuard._ready'})




if __name__=='__main__':unittest.main(verbosity=2)
