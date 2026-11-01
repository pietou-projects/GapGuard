"""Offline reader regression examples, generated from actual observer payloads."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests'),str(ROOT/'tools')]
from test_diagnostic_integrity import captured, encode
from read_diagnostic import read, render, MARKER

a,b=captured(9),captured(9)
cases={
    'intact':a,
    'header-missing':a[1:],
    'header-corrupt':[MARKER+' {corrupted-header']+a[1:],
    'batch-missing':a[:2]+a[3:],
    'cross-instance-collision':[a[0]]+b[1:],
    'two-instances-intact':a+b,
}
directory=ROOT/'results/integrity-examples'
directory.mkdir(exist_ok=True)
summary={}
for name,items in cases.items():
    path=directory/(name+'-SIMULATED.log')
    path.write_text(encode(items),encoding='utf-8')
    result=read(path)
    path.with_suffix('.txt').write_text(render(path,result),encoding='utf-8')
    summary[name]=dict(captures={k:d['complete'] for k,d in result['captures'].items()},
                       issues=result['issues'])
    if name in ('intact','two-instances-intact'):
        assert not result['issues'] and all(d['complete'] for d in result['captures'].values())
    else:
        assert result['issues'] and not any(d['complete'] for d in result['captures'].values())
(directory/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
print('Six simulated integrity examples verified; original dump=1 collision remains INCOMPLETE.')
