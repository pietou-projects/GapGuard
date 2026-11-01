"""Independent scope check: erase only observation, recover exact baseline AST."""
import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = 'bf74084df26570d529a15efdbe3dfb6d93653f2f2dc53a6cb2d6e7a2eb27403a'
HOOKED = {'_drain_edges', '_monitor', '_observe', '_gpio_observed',
          '_trace_pd3_fault', '_shutdown', '_reset_file', '_gpio'}

def is_hook(n):
    return isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and ast.dump(n.func.value) == "Name(id='self', ctx=Load())" and n.func.attr == '_pd3_diag'

class EraseObservation(ast.NodeTransformer):
    def visit_Import(self, n):
        if len(n.names) == 1 and n.names[0].name == 'uuid' and n.names[0].asname is None:
            return None
        return n

    def visit_ClassDef(self, n):
        if n.name == 'PD3Observer':
            return None
        return self.generic_visit(n)

    def visit_FunctionDef(self, n):
        if n.name == '_pd3_diag':
            return None
        return self.generic_visit(n)

    def visit_Expr(self, n):
        return None if is_hook(n.value) else self.generic_visit(n)

    def visit_Assign(self, n):
        if is_hook(n.value):
            assert len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'diagnostic_event'
            return None
        if len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'queued':
            assert ast.unparse(n.value) == 'self._edges.popleft()'
            return None
        if isinstance(n.value, ast.Name) and n.value.id == 'queued':
            assert ast.unparse(n.targets[0]) == '(epoch, generation, when, mask, pos)'
            n.value = ast.parse('self._edges.popleft()', mode='eval').body
        return self.generic_visit(n)

def canonical(raw, erase=False):
    tree = ast.parse(raw)
    if erase:
        tree = EraseObservation().visit(tree)
    return ast.dump(tree, include_attributes=False)

def assert_observer_scope(test):
    a = (ROOT/'baseline/gapguard.py').read_bytes()
    b = (ROOT/'src/gapguard.py').read_bytes()
    test.assertEqual(hashlib.sha256(a).hexdigest(), BASE_SHA)
    test.assertEqual(canonical(a), canonical(b, erase=True))
    def classes(raw):
        lines = raw.splitlines(True)
        return {n.name:b''.join(lines[n.lineno-1:n.end_lineno]) for n in ast.parse(raw).body if isinstance(n, ast.ClassDef)}
    x, y = classes(a), classes(b)
    for name in ('Settings','Native','Motion','Machine','AutoRecovery'):
        test.assertEqual(x[name], y[name], name)

def remove_observation_lines(raw):
    # For historical byte-for-byte guards on reset/shutdown/observe/monitor.
    # Full-module AST equality above independently covers ALL hooks.
    return b''.join(l for l in raw.splitlines(True) if not l.lstrip().startswith(b'self._pd3_diag('))
