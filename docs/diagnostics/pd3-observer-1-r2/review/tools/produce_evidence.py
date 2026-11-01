"""Generate explicit SIMULATED examples and PC-only observation cost estimates."""
from pathlib import Path
import collections
import json
import logging
import platform
import statistics
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT/'src'),str(ROOT/'tests')]
from test_observer import Harness, baseline, variant

def dump(h):
    h.a._trace_pd3_fault()
    lines=[]
    def capture(fmt,*args):
        if fmt.startswith('[GAPGUARD_PD3_DIAG]'):
            lines.append(fmt % args)
    with patch.object(logging,'info',side_effect=capture):
        while h.a._pd3_observer.pending:h.a._pd3_diag('flush')
    return lines

with patch.object(logging,'info',lambda *args,**kw:None):
    h=Harness();h.event(3,2.)
    h.event(2,eventtime=99.)
    drain=h.a._drain_edges;h.a._drain_edges=lambda:None
    h.event(2,3.)
    h.m.rearm_pd3(h.e,h.time,'SIMULATED_GENERATION_CHANGE')
    drain()
    h.event(2,3.)
    h.m.epoch+=1  # Synthetic harness stimulus only, never in production module.
    h.a._drain_edges()
    h.a._drain_edges=drain;drain()
    h.observe(23.1);h.event(2,43.01);h.observe(43.01)
    (ROOT/'results/example-received-rejected-SIMULATED.log').write_text('\n'.join(dump(h))+'\n',encoding='utf-8')
    h=Harness();h.event(3,2.);h.observe(11.);h.observe(22.);h.observe(42.)
    (ROOT/'results/example-no-callback-SIMULATED.log').write_text('\n'.join(dump(h))+'\n',encoding='utf-8')
    h=Harness();h.observe(20.1);h.event(3,25.);h.event(2,40.)
    h.observe(60.);h.observe(80.)
    (ROOT/'results/example-VERIFY-counted-SIMULATED.log').write_text('\n'.join(dump(h))+'\n',encoding='utf-8')

    times={}
    for name,mod in [('baseline',baseline),('observer',variant)]:
        samples=[]
        for _ in range(5):
            h=Harness(mod);start=time.perf_counter_ns()
            for i in range(10000):
                h.event(2+i%2,i*.1);h.calls.clear()
            samples.append((time.perf_counter_ns()-start)/10000/1000)
        times[name+'_microseconds_per_callback']=samples

    h=Harness()
    for i in range(256):
        h.event(2+i%2,i*.1)
        if i%4==0:h.m.change_mode('FULL',h.e,h.time)
    start=time.perf_counter_ns();h.a._trace_pd3_fault()
    snapshot_us=(time.perf_counter_ns()-start)/1000
    h.a._trace_pd3_fault()
    o=h.a._pd3_observer
    def size(value,seen=None):
        seen=set() if seen is None else seen
        if id(value) in seen:return 0
        seen.add(id(value));n=sys.getsizeof(value)
        if isinstance(value,dict):
            n+=sum(size(k,seen)+size(v,seen) for k,v in value.items())
        elif isinstance(value,(list,tuple,collections.deque)):
            n+=sum(size(v,seen) for v in value)
        return n
    memory=size((o.records,o.links,o.checkpoints,o.pending,o.counters))
    lengths=[];flush_times=[]
    def sink(fmt,*args):lengths.append(len((fmt % args).encode('utf-8')))
    with patch.object(logging,'info',side_effect=sink):
        while o.pending:
            start=time.perf_counter_ns();h.a._pd3_diag('flush')
            flush_times.append((time.perf_counter_ns()-start)/1000)

result=dict(build=variant.PD3Observer.BUILD,simulated_only=True,host=platform.platform(),python=sys.version,
            measurements=times,
            median_baseline_us=statistics.median(times['baseline_microseconds_per_callback']),
            median_observer_us=statistics.median(times['observer_microseconds_per_callback']),
            fault_snapshot_us=snapshot_us,
            stored_graph_bytes_at_two_pending_dumps=memory,
            dump_total_bytes_for_two_faults=sum(lengths),
            max_line_bytes=max(lengths),max_flush_serialization_us=max(flush_times),
            logger_disk_IO_measured=False,
            warning='PC measurements only; not a timing or memory guarantee on the Giga.')
(ROOT/'results/cost-estimate-PC.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
