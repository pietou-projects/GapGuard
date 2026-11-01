"""Capture identity and damaged-log regressions; entirely offline."""
import ast
import copy
import hashlib
import importlib.util
import json
import logging
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import read_diagnostic as reader
from test_observer import Harness, baseline, variant


def captured(number=9):
    """Use the actual observer serializer, not hand-invented valid payloads."""
    h=Harness()
    for i in range(number):h.event(2+i%2,float(i))
    if not number:h.a._pd3_diag('observation',h.time,h.n,h.e,False)
    h.a._trace_pd3_fault()
    payloads=[]
    def collect(fmt,*args):
        if fmt.startswith(reader.MARKER):payloads.append(json.loads(args[0]))
    with patch.object(logging,'info',side_effect=collect):
        while h.a._pd3_observer.pending:h.a._pd3_diag('flush')
    return payloads


def encode(items):
    return '\n'.join(item if isinstance(item,str) else reader.MARKER+' '+json.dumps(item) for item in items)+'\n'


class DiagnosticIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'diagnostic.log'

    def read(self,items):
        self.path.write_text(encode(items),encoding='utf-8')
        return reader.read(self.path)

    def codes(self,result):return [(i['line'],i['code']) for i in result['issues']]

    def incomplete(self,result):
        self.assertFalse(any(d['complete'] for d in result['captures'].values()))
        self.assertTrue(result['issues'])
        self.assertNotIn('COMPLETE=True',reader.render(self.path,result))

    def test_intact_capture(self):
        p=captured();r=self.read(p)
        self.assertEqual(r['issues'],[])
        d=r['captures'][p[0]['capture_id']]
        self.assertTrue(d['complete']);self.assertEqual(len(d['records']),9)
        self.assertEqual(d['lines'],[1,2,3,4])

    def test_missing_header_explicit_orphans_each_line(self):
        r=self.read(['ordinary log line']+captured()[1:])
        self.assertEqual(self.codes(r),[(2,'ORPHAN_EVENTS'),(3,'ORPHAN_EVENTS'),(4,'ORPHAN_EVENTS')])
        self.incomplete(r)

    def test_corrupted_header_json_and_orphans(self):
        r=self.read([reader.MARKER+' {broken']+captured()[1:])
        self.assertEqual(self.codes(r),[(1,'UNREADABLE_DIAGNOSTIC'),(2,'ORPHAN_EVENTS'),(3,'ORPHAN_EVENTS'),(4,'ORPHAN_EVENTS')])
        self.incomplete(r)

    def test_corrupted_header_schema_and_orphans(self):
        p=captured();p[0]['records']='nine';r=self.read(p)
        self.assertIn((1,'UNREADABLE_DIAGNOSTIC'),self.codes(r))
        self.assertIn((2,'ORPHAN_EVENTS'),self.codes(r));self.incomplete(r)

    def test_middle_batch_missing(self):
        p=captured();r=self.read(p[:2]+p[3:])
        self.assertIn((3,'OFFSET_MISMATCH'),self.codes(r));self.incomplete(r)

    def test_final_batch_missing(self):
        r=self.read(captured()[:-1]);self.incomplete(r)
        self.assertIn((1,'INCOMPLETE_CAPTURE'),self.codes(r))

    def test_final_marker_missing(self):
        p=captured();p[-1]['complete']=False;r=self.read(p)
        self.incomplete(r)

    def test_corrupted_middle_batch_does_not_silently_disappear(self):
        p=captured();p[2]=reader.MARKER+' [malformed';r=self.read(p)
        self.assertIn((3,'UNREADABLE_DIAGNOSTIC'),self.codes(r))
        self.assertIn((3,'UNATTRIBUTED_DAMAGE'),self.codes(r));self.incomplete(r)

    def test_review_collision_reproduces_old_bug_but_not_new_reader(self):
        a,b=captured(1),captured(1)
        self.assertEqual(a[0]['dump'],b[0]['dump'])
        self.assertNotEqual(a[0]['instance_id'],b[0]['instance_id'])
        r=self.read([a[0]]+b[1:])
        spec=importlib.util.spec_from_file_location('old_reader',ROOT/'baseline/observer-1.read_diagnostic.py')
        old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
        self.assertTrue(any(d['complete'] for d in old.read(self.path).values()))
        self.incomplete(r)
        self.assertIn((2,'ORPHAN_EVENTS'),self.codes(r))
        self.assertEqual(r['captures'][a[0]['capture_id']]['records'],[])

    def test_two_intact_instances_same_dump_are_separate(self):
        a,b=captured(),captured();r=self.read(a+b)
        self.assertEqual(len(r['captures']),2);self.assertEqual(r['issues'],[])
        self.assertTrue(all(d['complete'] for d in r['captures'].values()))

    def test_interleaved_captures_do_not_mix(self):
        a,b=captured(),captured();r=self.read([a[0],b[0],a[1],b[1],a[2],b[2],a[3],b[3]])
        self.assertEqual(r['issues'],[])
        for p in (a,b):
            self.assertEqual(r['captures'][p[0]['capture_id']]['records'],sum([x['records'] for x in p[1:]],[]))

    def test_duplicate_header_never_resets_error_state(self):
        p=captured();r=self.read([p[0],p[0]]+p[1:]);self.incomplete(r)
        self.assertIn((2,'DUPLICATE_HEADER'),self.codes(r))

    def test_duplicate_or_reordered_batches(self):
        p=captured()
        for sequence in ([p[0],p[1],p[1],p[2],p[3]],[p[0],p[2],p[1],p[3]]):
            r=self.read(sequence);self.incomplete(r)
            self.assertTrue(any(code=='OFFSET_MISMATCH' for _,code in self.codes(r)))

    def test_events_after_end_invalidate_capture(self):
        p=captured();r=self.read(p+[p[-1]]);self.incomplete(r)
        self.assertIn((5,'EVENTS_AFTER_END'),self.codes(r))

    def test_metadata_mismatch_invalidates_capture(self):
        p=captured();p[1]['build']='other-build';r=self.read(p);self.incomplete(r)
        self.assertIn((2,'METADATA_MISMATCH'),self.codes(r))

    def test_inconsistent_instance_and_capture_ids_are_not_joined(self):
        p=captured();p[1]['instance_id']='0'*32;r=self.read(p);self.incomplete(r)
        self.assertIn((2,'UNREADABLE_DIAGNOSTIC'),self.codes(r))

    def test_legacy_capture_not_certified(self):
        p=captured()
        for item in p:
            for k in ('schema','instance_id','capture_id'):item.pop(k)
        r=self.read(p);self.incomplete(r)
        self.assertEqual(len(r['issues']),4)
        self.assertTrue(all(i['code']=='UNREADABLE_DIAGNOSTIC' for i in r['issues']))

    def test_duplicate_json_keys_and_invalid_shapes_report_lines(self):
        a=reader.MARKER+' {"kind":"EVENTS","kind":"FAULT_CONTEXT"}'
        r=self.read([a,reader.MARKER+' null',reader.MARKER+' []',reader.MARKER+' NaN'])
        self.assertEqual(self.codes(r),[(i,'UNREADABLE_DIAGNOSTIC') for i in range(1,5)])

    def test_empty_capture_valid_only_with_matching_end(self):
        p=captured(0);r=self.read(p)
        self.assertEqual(r['issues'],[]);self.assertTrue(next(iter(r['captures'].values()))['complete'])
        self.incomplete(self.read(p[:1]))

    def test_cli_exit_status_and_warning_output(self):
        self.read(captured())
        out=Path(self.temp.name)/'report.txt'
        self.assertEqual(reader.main([str(self.path),'--output',str(out)]),0)
        self.read(captured()[1:])
        self.assertEqual(reader.main([str(self.path),'--output',str(out)]),2)
        self.assertIn('WARNING line 1 [ORPHAN_EVENTS]',out.read_text(encoding='utf-8'))

    def test_uuid_once_per_observer_not_per_callback_or_dump(self):
        with patch.object(variant.uuid,'uuid4',wraps=variant.uuid.uuid4) as new_id:
            h=Harness()
            for i in range(12):h.event(2+i%2,float(i))
            h.a._trace_pd3_fault();h.a._trace_pd3_fault()
            self.assertEqual(new_id.call_count,1)
            headers=[p['header'] for p in h.a._pd3_observer.pending]
            self.assertEqual(headers[0]['instance_id'],headers[1]['instance_id'])
            self.assertNotEqual(headers[0]['capture_id'],headers[1]['capture_id'])

    def test_uuid_failure_does_not_change_functional_decisions(self):
        a,b=Harness(baseline),Harness()
        with patch.object(variant.uuid,'uuid4',side_effect=OSError('simulated unavailable randomness')):
            for mask,e in ((3,2.),(2,6.)):
                a.event(mask,e);b.event(mask,e)
        self.assertEqual(a.snapshot(),b.snapshot())
        self.assertGreater(b.a._pd3_diag_errors,0)

    def test_embedded_delta_from_previous_observer_is_metadata_only(self):
        a=(ROOT/'baseline/observer-1.gapguard.py').read_bytes()
        b=(ROOT/'src/gapguard.py').read_bytes()
        self.assertEqual(hashlib.sha256(a).hexdigest(),'85f801153e69506b1270d8b4a287c51f0fe86b6066528c007731de9900ccd66a')
        def blocks(raw):
            lines=raw.splitlines(True)
            return {c.name+'.'+m.name:b''.join(lines[m.lineno-1:m.end_lineno])
                    for c in ast.parse(raw).body if isinstance(c,ast.ClassDef)
                    for m in c.body if isinstance(m,ast.FunctionDef)}
        x,y=blocks(a),blocks(b)
        self.assertEqual(x.keys(),y.keys())
        self.assertEqual({k for k in x if x[k]!=y[k]},
                         {'PD3Observer.__init__','PD3Observer.fault','PD3Observer.flush'})
        class StripMetadata(ast.NodeTransformer):
            def visit_Import(self,n):
                return None if len(n.names)==1 and n.names[0].name=='uuid' else n
            def visit_Assign(self,n):
                if ast.unparse(n.targets[0])=='self.instance_id':return None
                if ast.unparse(n.targets[0])=='BUILD':n.value=ast.Constant('BUILD')
                return self.generic_visit(n)
            def visit_ClassDef(self,n):
                if n.name=='PD3Observer':n.body=n.body[1:]  # docstring build label
                return self.generic_visit(n)
            def visit_Call(self,n):
                if isinstance(n.func,ast.Name) and n.func.id=='dict':
                    n.keywords=[k for k in n.keywords if k.arg not in ('schema','instance_id','capture_id')]
                return self.generic_visit(n)
        def normal(raw):return ast.dump(StripMetadata().visit(ast.parse(raw)),include_attributes=False)
        self.assertEqual(normal(a),normal(b))

    def test_reader_python37_syntax(self):
        ast.parse((ROOT/'tools/read_diagnostic.py').read_bytes(),feature_version=(3,7))

if __name__=='__main__':unittest.main(verbosity=2)
