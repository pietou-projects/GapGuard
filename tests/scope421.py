"""Exact allowed delta from the immutable 4.2.0 production module."""
from pathlib import Path
import ast
CHANGED={'Motion.edge','Machine.__init__','Machine.reset','Machine.gpio',
         'Machine.observe','Machine.change_mode','Machine.status',
         'AutoRecovery.gpio','AutoRecovery.guard','AutoRecovery.confirm','AutoRecovery.fail','AutoRecovery.invalidate',
         'AutoRecovery.advance','AutoRecovery.confirm_resume','AutoRecovery.finalize',
         'GapGuard._drain_edges','GapGuard._gpio_observed','GapGuard._gpio','GapGuard._trace'}
ADDED={'Machine.rearm_pd3','Machine.generation_valid','AutoRecovery.edge_window',
       'AutoRecovery.detector_coherent','AutoRecovery.retire_pd3'}
def blocks(p):
    raw=p.read_bytes();lines=raw.splitlines(True);tree=ast.parse(raw)
    return {c.name+'.'+f.name:b''.join(lines[f.lineno-1:f.end_lineno])
            for c in tree.body if isinstance(c,ast.ClassDef)
            for f in c.body if isinstance(f,ast.FunctionDef)}
def assert_scope(test):
    p=Path(__file__).parent;a=blocks(p/'reference/gapguard_420.py');b=blocks(p.parent/'src/gapguard.py')
    test.assertEqual(set(a)-set(b),set())
    test.assertEqual(set(b)-set(a),ADDED)
    test.assertEqual({k for k in a if a[k]!=b[k]},CHANGED)
