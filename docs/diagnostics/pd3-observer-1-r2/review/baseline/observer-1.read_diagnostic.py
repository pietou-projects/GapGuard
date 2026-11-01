"""Offline log reader. No printer API, no network, no commands sent."""
import argparse
import json
from pathlib import Path

def read(path):
    dumps={}
    for line_number,line in enumerate(path.read_text(encoding='utf-8',errors='replace').splitlines(),1):
        marker='[GAPGUARD_PD3_DIAG] '
        if marker not in line:continue
        try:p=json.loads(line.split(marker,1)[1])
        except ValueError:continue
        # A boot can restart dump numbering. A header starts a new occurrence.
        if p['kind']=='FAULT_CONTEXT':
            key=(p['dump'],line_number)
            dumps[key]=dict(header=p,records=[],complete=False,lines=[line_number])
        else:
            keys=[k for k in dumps if k[0]==p['dump']]
            if not keys:continue
            d=dumps[keys[-1]]
            if p['offset']!=len(d['records']):
                d['gap']=True
            d['records'].extend(p['records']);d['lines'].append(line_number)
            d['complete']=p['complete'] and len(d['records'])==d['header']['records'] and not d.get('gap')
    return dumps

def render(path):
    lines=['SOURCE: '+str(path),'Times below are Reactor monotonic seconds, not wall-clock timestamps.']
    for key,d in read(path).items():
        h=d['header'];lines += ['',f"DUMP {key[0]} lines {d['lines']} COMPLETE={d['complete']}",
          'Captured: '+str(h['captured_at']), 'Last callback [id,event,processed]: '+str(h['last_callback']),
          'Counters: '+json.dumps(h['counters'],sort_keys=True),
          'Observer errors: '+str(h['wrapper_errors']),
          'Fault detector: '+json.dumps(h['detector'],sort_keys=True)]
        for r in d['records']:
            p=r.get('processing',{});b=p.get('before',{});e=r.get('effect',{});a=e.get('after',{})
            lines.append(' | '.join([
                'id='+str(r['id']),'event='+str(r['eventtime']),
                'received='+str(r.get('processed_at','UNRECORDED')),
                'return='+json.dumps(r.get('return',{}),sort_keys=True),
                'E='+str(p.get('E',r.get('queued',{}).get('E'))), 'ref='+str(b.get('reference')),
                'state='+str(b.get('state'))+'->'+str(a.get('state')),
                'VERIFY='+str(b.get('start'))+'..'+str(b.get('end')),
                'count='+str(b.get('count'))+'->'+str(a.get('count')),
                'electrical='+str(e.get('electrical_transition')),
                'machine_accepted='+str(e.get('machine_accepted')),
                'verify_counted='+str(e.get('verify_counted'))]))
    return '\n'.join(lines)+'\n'

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('log',type=Path)
    p.add_argument('--output',type=Path);a=p.parse_args();result=render(a.log)
    if a.output:a.output.write_text(result,encoding='utf-8')
    else:print(result,end='')
