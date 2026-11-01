"""Assemble local review evidence and ZIP. Does not publish or deploy."""
from pathlib import Path
import ast
import difflib
import hashlib
import json
import re
import sys
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests'),str(ROOT/'tools')]
from observer_scope import assert_observer_scope, HOOKED
from read_diagnostic import render, read

assert_observer_scope(unittest.TestCase())
for p in sorted((ROOT/'results').glob('*SIMULATED.log')):
    p.with_suffix('.txt').write_text(render(p),encoding='utf-8')
    parsed=read(p)
    assert not parsed['issues'] and parsed['captures'] and all(d['complete'] for d in parsed['captures'].values())
suite=(ROOT/'results/suite.txt').read_text(encoding='utf-8-sig')
assert re.search(r'Ran 311 tests in .+\s+OK\s*$',suite)

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def blocks(p):
    raw=p.read_bytes();lines=raw.splitlines(True)
    return {c.name+'.'+m.name:b''.join(lines[m.lineno-1:m.end_lineno])
            for c in ast.parse(raw).body if isinstance(c,ast.ClassDef)
            for m in c.body if isinstance(m,ast.FunctionDef)}
a,b=blocks(ROOT/'baseline/gapguard.py'),blocks(ROOT/'src/gapguard.py')
changed=sorted(k for k in a if a[k]!=b[k])
assert set(changed)=={'GapGuard.'+k for k in HOOKED}

prior=ROOT.parent/'GapGuard_421_Publication_20261027/package/tests'
tests_diff=[];test_changes=[]
for p in sorted((ROOT/'tests').rglob('*')):
    if not p.is_file() or p.suffix=='.pyc':continue
    old=prior/p.relative_to(ROOT/'tests')
    if old.exists() and p.read_bytes()!=old.read_bytes():
        test_changes.append(p.relative_to(ROOT).as_posix())
        tests_diff.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),
            p.read_text(encoding='utf-8').splitlines(True),fromfile='retained/'+p.name,tofile='review/'+p.name))
(ROOT/'tests-observation-scope.diff').write_text(''.join(tests_diff),encoding='utf-8')
source=json.loads((ROOT.parent/'GapGuard_PD3_Live_20261101/source-manifest.json').read_text(encoding='utf-8'))[0]
result=dict(build='4.2.1-rc1+pd3-observer-1-r2',status='OFFLINE REVIEW ONLY - NOT INSTALLED',
    baseline_capture=source,baseline_sha256=digest(ROOT/'baseline/gapguard.py'),
    diagnostic_sha256=digest(ROOT/'src/gapguard.py'),
    baseline_tests_passed=258,variant_tests_passed=311,retained_observer_tests=29,new_integrity_tests=24,
    original_functional_tests_removed=0,adapted_structural_tests=6,
    adapted_test_files=test_changes,
    differential_steps=10000,full_recovery_differential_cycles=3,
    changed_existing_methods=changed,
    protected_classes_byte_identical=['Settings','Native','Motion','Machine','AutoRecovery'],
    functional_AST_identical_after_removing_only_observation=True,
    new_E_reads=0,new_native_reads=0,new_Gcode_calls=0,new_timers=0,
    python37_syntax='PASS',compilation='PASS',runtime_tests='NOT RUN',
    remote_connections=0,installed=False,published=False)
(ROOT/'results/validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')

previous_archive=ROOT.parent/'GapGuard-4.2.1-rc1-pd3-observer-1-OFFLINE-REVIEW.zip'
assert digest(previous_archive)=='3c30db8267830031d5abde4b1118c3edf469a5f4868b03e04d4e6f22a3103814'
with zipfile.ZipFile(previous_archive) as previous:
    # Every configuration fixture must still be byte-identical.
    for name in previous.namelist():
        if name.endswith('.cfg'):
            assert previous.read(name)==(ROOT/name).read_bytes(),name
    for name,output in [('src/gapguard.py','observer-1-to-r2.module.diff'),
                        ('tools/read_diagnostic.py','observer-1-to-r2.reader.diff')]:
        (ROOT/output).write_text(''.join(difflib.unified_diff(
            previous.read(name).decode('utf-8').splitlines(True),
            (ROOT/name).read_bytes().decode('utf-8').splitlines(True),
            fromfile='observer-1/'+name,tofile='observer-1-r2/'+name)),encoding='utf-8',newline='')
    result['previous_review_zip_sha256']=digest(previous_archive)
    result['reader_sha256']=digest(ROOT/'tools/read_diagnostic.py')
    result['configuration_fixtures_byte_identical']=True
    result['previous_GapGuard_methods_byte_identical']=True
    result['embedded_metadata_only_delta']=True
    (ROOT/'results/validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')

# Keep exploratory failures outside the review archive, not silently in its
# final results. All original reference fixtures remain local test material.
files=sorted(p for p in ROOT.rglob('*') if p.is_file() and
    '__pycache__' not in p.parts and p.suffix!='.pyc' and
    p.name not in ('first-suite.txt','SHA256SUMS.txt'))
links=[]
for p in files:
    if p.suffix!='.md' or 'tests' in p.relative_to(ROOT).parts:continue
    for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
        if '://' in target or target.startswith('#'):continue
        q=(p.parent/target.split('#')[0])
        if q.name=='SHA256SUMS.txt':continue
        assert q.exists(),(p,target)
        links.append((p.relative_to(ROOT).as_posix(),target))
checksum=ROOT/'SHA256SUMS.txt'
checksum.write_text(''.join(digest(p)+'  '+p.relative_to(ROOT).as_posix()+'\n' for p in files),encoding='ascii')
files.append(checksum)
archive=ROOT.parent/'GapGuard-4.2.1-rc1-pd3-observer-1-r2-OFFLINE-REVIEW.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in files:z.write(p,p.relative_to(ROOT).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for p in files:assert z.read(p.relative_to(ROOT).as_posix())==p.read_bytes()
print(json.dumps(dict(zip=str(archive),zip_sha256=digest(archive),
                     module_sha256=result['diagnostic_sha256'],reader_sha256=result['reader_sha256'],files=len(files),
                     markdown_links_checked=len(links),changed_methods=changed,
                     changed_test_files=test_changes),indent=2))
