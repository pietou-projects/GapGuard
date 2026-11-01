"""Assert the submission boundary, not merely the final six G1 commands."""
import ast
import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch
import gapguard as gg
from test_recovery import Rig

ROOT=Path(__file__).resolve().parent
SCRIPT='G1 X-20 F15000\nG1 X20\nG1 X-20\nG1 X20\nG1 X-20\nG1 X20'

def assert_single_sequence(test,x):
    submissions=[s for s in x.submissions if 'G1 X' in s['text']]
    test.assertEqual(len(submissions),1)
    test.assertEqual(submissions[0]['text'],SCRIPT)
    moves=[m for m in x.move_records if m['phase']=='WIPE']
    test.assertEqual(len(moves),6)
    test.assertEqual(len({m['submission'] for m in moves}),1)
    test.assertEqual(len({m['mutex_acquisition'] for m in moves}),1)
    test.assertEqual(len({m['submitted_at'] for m in moves}),1)

class WipeSequenceTests(unittest.TestCase):
    def begin(self):
        x=Rig();x.pause();x.until('WIPE');return x

    def test_six_moves_one_script_one_worker_one_mutex(self):
        x=self.begin();acquisitions=x.mutex.acquisitions
        with patch.object(x.r,'advance',wraps=x.r.advance) as advance:
            x.tick();self.assertEqual(advance.call_count,1)
        self.assertEqual(x.mutex.acquisitions,acquisitions+1)
        assert_single_sequence(self,x)
        self.assertEqual(x.state(),'WIPE');self.assertFalse(x.mutex.locked)

    def test_relative_geometry_and_inherited_feedrate(self):
        x=self.begin();before=list(x.commanded);x.tick()
        assert_single_sequence(self,x)
        moves=[m for m in x.move_records if m['phase']=='WIPE']
        self.assertEqual([m['delta'] for m in moves],[[d,0.,0.,0.] for d in (-20,20,-20,20,-20,20)])
        self.assertEqual([m['speed'] for m in moves],[250.]*6)
        self.assertEqual(x.commanded,before)
        self.assertEqual(SCRIPT.count(' F15000'),1)
        self.assertFalse(any(line.startswith('G4') for line in SCRIPT.splitlines()))

    def test_single_flush_after_all_six_submissions(self):
        x=self.begin();seen=[]
        def flush():
            seen.append(len([m for m in x.move_records if m['phase']=='WIPE']))
            return x.finish
        x.toolhead.get_last_move_time=flush
        x.tick();self.assertEqual(seen,[6])
        self.assertEqual(x.r.record['finish'],x.finish)

    def test_no_software_gap_between_queued_moves(self):
        x=self.begin();x.tick()
        moves=[m for m in x.move_records if m['phase']=='WIPE']
        self.assertEqual(len(moves),6)
        for previous,current in zip(moves,moves[1:]):
            self.assertEqual(previous['finish'],current['start'])
            self.assertEqual(previous['submitted_at'],current['submitted_at'])

    def test_wait_whole_sequence_before_finalization(self):
        x=self.begin();x.tick();submitted=list(x.submissions)
        # A first move could be finished; the complete sequence is not.
        moves=[m for m in x.move_records if m['phase']=='WIPE']
        x.t=moves[0]['finish']+.001;x.tick(0)
        self.assertEqual(x.state(),'WIPE');self.assertEqual(x.submissions,submitted)
        x.t=x.finish-.001;x.tick(0)
        self.assertEqual(x.state(),'WIPE');self.assertEqual(x.submissions,submitted)
        x.t=x.finish+.001;x.tick(0)
        self.assertEqual(x.state(),'FINAL');self.assertEqual(x.submissions,submitted)
        self.assertNotIn('M24',x.calls)
        x.until('RESUMED');assert_single_sequence(self,x)
        self.assertEqual(x.calls.count('M24'),1)

    def test_previous_implementation_is_rejected_by_same_sequence_assertion(self):
        raw=(ROOT.parent/'src/gapguard.py').read_text(encoding='utf-8')
        old=(ROOT/'fixtures/previous_rc1/gapguard.py').read_text(encoding='utf-8')
        start="        elif state == 'WIPE':";end="        elif state == 'FINAL':"
        raw=raw[:raw.index(start)]+old[old.index(start):old.index(end)]+raw[raw.index(end):]
        tree=ast.parse(raw)
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='AutoRecovery')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='advance')
        import textwrap
        ns=dict(gg.__dict__)
        exec(compile(textwrap.dedent(ast.get_source_segment(raw,method)),'previous_rc1.advance','exec'),ns)
        with patch.object(gg.AutoRecovery,'advance',ns['advance']):
            x=Rig();x.success()
        self.assertEqual(len([s for s in x.submissions if 'G1 X' in s['text']]),6)
        self.assertEqual(len({m['submitted_at'] for m in x.move_records if m['phase']=='WIPE'}),6)
        with self.assertRaises(AssertionError):assert_single_sequence(self,x)

    def test_only_exact_wipe_patch_in_production(self):
        before=(ROOT/'fixtures/previous_rc1/gapguard.py').read_bytes()
        after=(ROOT/'reference/gapguard_420.py').read_bytes()
        old=b"            cmd = 'G1 X-20 F15000' if r['wipe'] == 0 else ('G1 X20' if r['wipe'] % 2 else 'G1 X-20')\r\n            self.move(r, cmd)\r\n            r['wipe'] += 1"
        new=b"            self.move(r, 'G1 X-20 F15000\\nG1 X20\\nG1 X-20\\n'\r\n                         'G1 X20\\nG1 X-20\\nG1 X20')\r\n            r['wipe'] = 6"
        self.assertEqual(before.count(old),1)
        self.assertEqual(before.replace(old,new),after)
        current=(ROOT.parent/'src/gapguard.py').read_bytes()
        start=b"        elif state == 'WIPE':";end=b"        elif state == 'FINAL':"
        self.assertEqual(after[after.index(start):after.index(end)],current[current.index(start):current.index(end)])


if __name__=='__main__':unittest.main(verbosity=2)
