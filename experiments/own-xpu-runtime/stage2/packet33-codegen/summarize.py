#!/usr/bin/env python3
"""CPU-only strict event aggregation into packet26 dispatch vocabulary."""
import argparse,collections,json,statistics,hashlib
from pathlib import Path
EXPECTED={('gemv:expsdown','p33.down.bank'):{'expsdown'},('gemv:expsdown','p33.down.select'):{'expsdown'},('gemv:expsgate','p33.gate.restrict'):{'expsgate.iq2','expsgate.iq3'},('gemv:gdn.qkv','p33.dense.segment'):{'gdn.qkv.q6','gdn.qkv.q8'},('gemv:qsa.k','p33.dense.segment'):{'qsa.k'},('route','p33.route.rank4'):{''},('qsa.attention','p33.qsa.shape'):{''}}
COUNTS={'gemv:expsdown':48,'gemv:expsgate':48,'gemv:gdn.qkv':36,'gemv:qsa.k':12,'route':48,'qsa.attention':12}
def expected_stages(klass,arm):
 if klass=='gemv:qsa.k':return 1 if arm=='packet18' else 2
 return (5 if arm=='packet18' else 3) if klass=='route' else (3 if klass=='qsa.attention' else 1)
def summarize(root):
 root=Path(root);receipt=json.loads((root/'receipt.json').read_text())
 if not receipt.get('passed') or not receipt.get('reference_exact') or (root/'candidate-failures.jsonl').exists():raise ValueError('failed/missing exactness gate')
 rows=[json.loads(l) for l in (root/'events.jsonl').read_text().splitlines()]
 groups=collections.defaultdict(list)
 for r in rows:
  if r.get('variant') not in ('packet18','specialised') or type(r.get('repetition')) is not int or not 0<=r['repetition']<200:raise ValueError('unexpected variant/repetition')
  if r.get('full_payload_bytes',0)>8000000 and r.get('timing_mode')!='rotated':continue
  key=(r['class'],r['candidate'],r.get('workload',''),r['variant'],r['repetition']);groups[key].append(r)
 table=[]
 seen={(k[0],k[1],k[2]) for k in groups}
 if seen!={(c,k,w) for (c,k),ws in EXPECTED.items() for w in ws}:raise ValueError('exact candidate/workload coverage required')
 for (klass,candidate),workloads in EXPECTED.items():
  ws=[]
  for workload in sorted(workloads):
   rates={}
   for arm in ('packet18','specialised'):
    values=[]
    for rep in range(200):
     events=groups[(klass,candidate,workload,arm,rep)]
     if len(events)!=expected_stages(klass,arm) or len({e['event'] for e in events})!=len(events) or any(e['stage_count']!=len(events) or not e.get('exact') or e['end_ns']<=e['start_ns'] or e['end_ns']-e['start_ns']>4e9 for e in events):raise ValueError('invalid/missing stage or exactness')
     values.append(sum(e['end_ns']-e['start_ns'] for e in events)/1000)
    rates[arm]=statistics.median(values)
   ws.append(dict(workload=workload,incumbent_us=rates['packet18'],candidate_us=rates['specialised']))
  saving=min(w['incumbent_us']-w['candidate_us'] for w in ws)*COUNTS[klass]/1000
  table.append(dict(klass=klass,candidate=candidate,workloads=ws,conservative_ms_per_token_saved=saving,selected=all(w['candidate_us']<.9*w['incumbent_us'] for w in ws)))
 table.sort(key=lambda x:x['conservative_ms_per_token_saved'],reverse=True)
 dispatch=dict(schema='packet26.dispatch.v1',classes={},gemv={},fusions={})
 # Fastest admitted candidate per class, all declared type workloads must win.
 for r in table:
  section='gemv' if r['klass'].startswith('gemv:') else 'classes';name=r['klass'].removeprefix('gemv:')
  if r['selected'] and name not in dispatch[section]:dispatch[section][name]=r['candidate']
 data=dict(schema='packet33.k2-summary.v1',device_executed=True,passed=True,selection_scope='one-card kernel diagnostic; not model speed',table=table,events_sha256=hashlib.sha256((root/'events.jsonl').read_bytes()).hexdigest())
 (root/'summary.json').write_text(json.dumps(data,indent=2)+'\n');(root/'dispatch-measured.json').write_text(json.dumps(dispatch,indent=2)+'\n')
 return data
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('root');a=ap.parse_args();print(json.dumps(summarize(a.root),indent=2))
