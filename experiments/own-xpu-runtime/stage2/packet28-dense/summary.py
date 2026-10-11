"""Admit class candidates only after two fresh same-card exact timing owners."""
import collections,json,statistics,math,re,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent
TIMES=P.parent/'packet26-specialised/receipts-cards01-20261011-native-w2m/class-timing-run-b/class-times.json'
def load(p):return json.loads(Path(p).read_text())
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def lines(p):return [json.loads(s) for s in Path(p).read_text().splitlines() if s.strip()]
def stats(values):
 s=sorted(values);assert len(s)==200,'200 GPU samples required'
 return dict(median_us=statistics.median(s),p90_us=s[math.ceil(.9*len(s))-1],samples=len(s))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def allowed(t):
 if t=='IQ4_NL':return {'p28.private.rows4','p28.private.wg32','p28.shared.rows4','p28.shared.wg32','r5'}
 if t in ('IQ2_S','IQ3_S'):return {'p28.private.rows4','p28.private.wg32','p28.shared.rows4','p28.shared.wg32','p28.paired.rows4','p28.paired.wg32','r5'}
 return {'p28.dense.rows4','p28.dense.wg32','r5'}
def owner_summary(path):
 grouped=collections.defaultdict(lambda:collections.defaultdict(list));names={}
 for row in lines(path/'timing.jsonl'):
  assert row['exact'] is True
  key=(row['class'],row['workload'],row['candidate']);names[key]=row['current_kernel']
  assert 0<=row['repetition']<200
  assert row['end_ns']>row['start_ns']
  grouped[key][row['repetition']].append(row)
 out={}
 for key,repetitions in grouped.items():
  if set(repetitions)!=set(range(200)):continue # interrupted candidate: never admit incomplete timings
  sums=[]
  for group in repetitions.values():
   assert len({r['event_index'] for r in group})==len(group),'duplicate event'
   counts={r['event_count'] for r in group};assert len(counts)==1 and next(iter(counts)) in (1,2)
   assert set(r['event_index'] for r in group)==set(range(next(iter(counts)))),'missing constituent event'
   sums.append(sum(r['end_ns']-r['start_ns'] for r in group)/1000)
  out[key]=dict(**stats(sums),current_kernel=names[key])
 return out

def write_summary(root):
 root=Path(root);window=load(root/'window.json')
 assert window.get('completed') and window.get('fresh_owners')==2
 assert len({x['unit'] for x in window['owners']})==2
 assert len({x['pid'] for x in window['owners']})==2
 build=load(P/'build-receipt.json');assert sha(P/'build-receipt.json')==window['build_receipt_sha256']
 assert sha(P/'class-registry.json')==build['sources_sha256']['class-registry.json']
 assert sha(TIMES)==build['external_sources_sha256'][str(TIMES.relative_to(P.parents[3]))]
 registry=load(P/'class-registry.json');registered={(r['class'],r['label']):r for r in registry}
 owners=[]
 for index,owner in enumerate(window['owners'],1):
  path=root/'run'/('owner'+str(index))
  for file,key in [('receipt.json','native_receipt_sha256'),('exactness.jsonl','exactness_sha256'),('timing.jsonl','timing_sha256')]:assert sha(path/file)==owner[key],file+' changed'
  receipt=load(path/'receipt.json');assert receipt['completed'] and receipt['safe_to_exit'] and receipt['device_executed'] and receipt['live_bytes']==0 and receipt['in_flight']==0
  exact=collections.defaultdict(list)
  for r in lines(path/'exactness.jsonl'):
   identity=(r['class'],r['workload']);assert identity in registered
   assert r['candidate'] in allowed(registered[identity]['type'])
   exact[(*identity,r['candidate'])].append(r)
  data=owner_summary(path);eligible={}
  for key,val in data.items():
   assert key[:2] in registered and key[2] in allowed(registered[key[:2]]['type'])
   checks=exact[key];base=exact[(key[0],key[1],'r5')]
   if not all(r['passed'] for r in checks+base):continue
   expected_modes=set(range(6 if registered[key[:2]]['count']>1 else 5))
   if {r['mode'] for r in checks}!=expected_modes or {r['mode'] for r in base}!=expected_modes:continue
   if not all(r['passed'] for r in checks+base):continue
   if key[2]!='r5' and not all(r.get('new_current_bytes_equal') is True for r in checks):continue
   eligible[key]=val
  owners.append(eligible)
 timing=load(TIMES);metrics={r['class']:r for r in timing['classes']}
 registry=load(P/'class-registry.json');byclass=collections.defaultdict(list)
 for row in registry:byclass[row['class']].append(row)
 result=[];dispatch={}
 for klass,workloads in byclass.items():
  metric=metrics[workloads[0].get('timing_class',klass)]
  expected=metric['device_ms']*1000/metric['groups'] if metric['groups'] else None
  frequency=metric['groups']/timing['tokens'];launches=metric['launches']/timing['tokens']
  base=[];valid=True;reason=[]
  for sh in workloads:
   key=(klass,sh['label'],'r5')
   if not all(key in o for o in owners):valid=False;reason.append('missing exact R5 timing '+sh['label']);continue
   for o in owners:
    v=o[key];base.append(v['median_us'])
    if expected is None or not .85*expected<=v['median_us']<=1.15*expected:valid=False;reason.append('R5 does not reproduce in-model time within 15%: '+sh['label'])
  candidates=set.intersection(*(set(k[2] for k in o if k[0]==klass and k[1]==sh['label']) for o in owners for sh in workloads)) if workloads else set()
  admitted=[];details=[]
  for candidate in sorted(candidates-{'r5'}):
   vals=[];deltas=[];eligible=valid
   for sh in workloads:
    for o in owners:
     k=(klass,sh['label'],candidate);b=(klass,sh['label'],'r5')
     if b not in o:eligible=False;continue
     vals.append(o[k]['median_us']);deltas.append(o[b]['median_us']-o[k]['median_us'])
     eligible &= o[k]['median_us'] < .9*o[b]['median_us']
   entry=dict(candidate=candidate,eligible=bool(eligible),median_us=statistics.median(vals),p90_us=max(o[(klass,sh['label'],candidate)]['p90_us'] for o in owners for sh in workloads))
   details.append(entry)
   if eligible:admitted.append((min(deltas),candidate,entry))
  best=max(admitted,default=None)
  chosen=best[1] if best else 'r5';dispatch[klass]=chosen
  # Conservative accounting across mixed formats: minimum saving, never weighted
  # by an invented format frequency. Groups count logical GEMVs; launches count
  # all baseline GPU events and are retained separately.
  saved=(best[0]*frequency/1000) if best else 0
  result.append(dict(class_name=klass,current_kernel=sorted({o[k]['current_kernel'] for o in owners for k in o if k[0]==klass and k[2]=='r5'}),in_model_group_us=expected,r5_median_us=statistics.median(base) if base else None,baseline_matches_model=valid,reason=sorted(set(reason)),groups_per_token=frequency,launches_per_token=launches,selected=chosen,ms_per_token_saved_lower_bound=saved,candidates=details))
 result.sort(key=lambda r:r['ms_per_token_saved_lower_bound'],reverse=True)
 save(root/'dispatch-gemv-measured.json',dict(schema='packet26.dispatch.v1',classes={},gemv=dispatch,fusions={}))
 save(root/'summary.json',dict(device_executed=True,measured_on_tiled_fixtures=True,model_speed_claim=False,rows=result))
 text='| Class | Runtime R5 kernel | In-model us/group | R5 us | Selected | Conservative ms/token saved | Baseline within 15% |\n|---|---|---:|---:|---|---:|---|\n'
 for r in result:text+=f"| {r['class_name']} | {', '.join(r['current_kernel'])} | {r['in_model_group_us']} | {r['r5_median_us']} | {r['selected']} | {r['ms_per_token_saved_lower_bound']:.4f} | {r['baseline_matches_model']} |\n"
 (root/'timing-table.md').write_text(text+'\nRows with a baseline mismatch do not measure representative runtime cost and cannot change dispatch. Savings are conservative fixture accounting, not measured model throughput.\n')
 return result
if __name__=='__main__':
 import sys
 write_summary(sys.argv[1])
