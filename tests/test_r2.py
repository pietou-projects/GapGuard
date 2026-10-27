import ast,unittest
from pathlib import Path
from test_recovery import Rig,gg

class R2Tests(unittest.TestCase):
    def test_three_recoveries_same_print(self):
        x=Rig();epoch=x.m.epoch
        for _ in range(3):
            x.rv['flag_print_status']=1;x.pv['flag_print_status']=0;x.target=0.
            x.m.observe(x.t,x.native,x.position(x.t))
            x.m.request_pause('VERIFY_FAIL');x.m.claim_pause(x.native)
            x.success()
        self.assertEqual(x.m.epoch,epoch)
        self.assertEqual(x.calls.count('M24'),3)
        self.assertEqual(x.calls.count('G1 E20 F200'),45)

    def test_failed_attempt_does_not_lock_next_fault(self):
        x=Rig();x.block();x.until('FAILED',edges=0);x.tick()
        x.native=gg.Native('printing',True,x.m.path);x.m.observe(x.t,x.native,x.position(x.t))
        x.m.request_pause('VERIFY_FAIL');x.m.claim_pause(x.native)
        x.success();self.assertEqual(x.state(),'RESUMED')

    def test_fan_phase_not_authorization(self):
        x=Rig();x.fan['phase']='saved';x.fan_value=.7;x.success()
        self.assertEqual(x.state(),'RESUMED');self.assertEqual(x.fan_value,.7)

    def test_epoch_path_change_invalidates_waiting_recovery(self):
        x=Rig();x.pause();x.until('WAIT');x.m.epoch+=42
        x.m.path='/another.gcode';x.native=gg.Native('paused',False,x.m.path)
        x.until('FAILED');self.assertEqual(x.calls.count('M24'),0)
        self.assertEqual(x.calls,[])

    def test_delay_remains_30_seconds(self):
        x=Rig();x.pause();x.until('WAIT');deadline=x.r.record['deadline']
        x.t=deadline-.001;x.tick(0);self.assertEqual(x.calls,[])
        x.t=deadline;x.tick(0);self.assertEqual(x.state(),'HEAT')

    def test_not_paused_at_deadline_no_commands(self):
        x=Rig();x.pause();x.until('WAIT');x.native=gg.Native('printing',True,x.m.path)
        x.tick(30);x.tick();self.assertEqual(x.calls,[])

    def test_pd4_absent_at_deadline_no_commands(self):
        x=Rig();x.pause();x.until('WAIT');x.gpio(pd4=0)
        x.tick(30);x.tick();self.assertEqual(x.calls,[])

    def test_no_fan_or_session_quota_with_explicit_generation_contract(self):
        p=Path(__file__).resolve().parent.parent/'src/gapguard.py'
        source=p.read_text(encoding='utf-8');tree=ast.parse(source)
        c=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='AutoRecovery')
        for name in ('pause_completed','live','paused','guard','confirm','tick'):
            m=next(n for n in c.body if isinstance(n,ast.FunctionDef) and n.name==name)
            for n in ast.walk(m):
                if isinstance(n,ast.Compare):
                    s=ast.get_source_segment(source,n)
                    self.assertFalse(any(t in s for t in ('fan','used_key')),s)
        text=ast.get_source_segment(source,c)
        self.assertNotIn('used_key',text);self.assertNotIn('auto_recovery_max_per_session',text)
        self.assertIn("(self.o.machine.epoch, self.o.machine.motion_generation)",text)
        self.assertIn("n.printing(r['key'][1])",text)

