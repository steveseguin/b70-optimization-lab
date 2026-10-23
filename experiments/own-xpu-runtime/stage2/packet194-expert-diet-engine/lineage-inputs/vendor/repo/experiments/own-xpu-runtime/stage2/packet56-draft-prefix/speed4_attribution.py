"""Read-only retained-receipt attribution; no build or device access."""
import importlib.util,json,statistics as st
from pathlib import Path
P=Path(__file__).resolve().parent;E=P/'evidence/speed4'
def main():
 spec=importlib.util.spec_from_file_location('retained_analysis',P/'evidence/regression-analysis/analyze.py')
 a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
 prior_stats=a.stats;a.stats=lambda values:prior_stats(x for x in values if x is not None)
 a.RUNS={'p44-record':P.parent/'packet44-context/build/c4096b/WS128',
 'p44-control':P.parent/'packet44-context/build/c4096ctl15a/WS128',
 'p45-dr0':P/'build/speed3-c4096-dr0-s24-gpu/WS128',
 'p45-dr1':P/'build/speed3-c4096-dr1-gpu/WS128'}
 classes={r['prompt_id']:r['prompt_class'] for r in a.read(a.RUNS['p45-dr0']/'run/summary.json')['rows']}
 result={}
 for name,root in a.RUNS.items():
  label=name.replace('p45-','speed3-')
  if not (root/'window.json').exists():result[label]={'complete':False};continue
  row=a.analyze(root,classes)
  if name.startswith('p45') and row['complete']:
   expected=json.loads((P/'evidence/speed4/before-build-receipt.json').read_text())['artifacts_sha256']['device/own-rt-iq3']
   assert row['window']['artifacts_sha256']['device/own-rt-iq3']==expected,'not SPEED3 artifact'
  if not row['complete']:result[label]=row;continue
  partition={'hit':[],'miss':[]};publication=[];snapshots=[];request_parts=[]
  for f in sorted((root/'run/repeat-1').glob('*/receipt.json')):
   receipt=a.read(f);trace=receipt['rank_trace']
   per_request={'hit':[],'miss':[]}
   for d in receipt['draft_rows']:
    if d.get('hit') is None or 'cycle_ms' not in d:continue
    left=d['target_completed_monotonic'];right=left+d['cycle_ms']/1000
    halves=[t for t in trace if t['rank']==1 and t['op']==1 and t['rank_received']>=left and t['rank_completed']<=right+1e-6]
    assert len(halves)==1;half=halves[0]
    parts=dict(before_rank1_half_ms=(half['rank_received']-left)*1000,rank1_half_ms=a.span(half),completion_observation_lag_ms=(right-half['rank_completed'])*1000,cycle_ms=d['cycle_ms'])
    for op in (1,3,9):parts[f'rank0_op{op}_before_half_ms']=sum(a.clip(t,left,half['rank_received']) for t in trace if t['rank']==0 and t['op']==op)
    parts['controller_handoff_remainder_ms']=parts['before_rank1_half_ms']-sum(parts[f'rank0_op{op}_before_half_ms'] for op in (1,3,9))
    assert abs(sum(parts[k] for k in ('before_rank1_half_ms','rank1_half_ms','completion_observation_lag_ms'))-parts['cycle_ms'])<1e-6
    kind='hit' if d['hit'] else 'miss';per_request[kind].append(parts)
    if d['position']>=100:partition[kind].append(parts)
   request_parts.append(dict(prompt=f.parent.name,**{k:{field:st.mean(x[field] for x in xs) for field in xs[0]} for k,xs in per_request.items()}))
   for i,t in enumerate(trace):
    if t['op']==9 and t['position']>=100:
     after=[q['sent'] for q in trace[i+1:] if q['sent']>=t['rank_completed']]
     if after:publication.append((min(after)-t['rank_completed'])*1000)
   snap=f.parent/'rank0/speculative-snapshot.json'
   if snap.exists():snapshots.append(a.read(snap))
  row['full_scope_request_mean_medians']={k:{field:st.median(q[k][field] for q in request_parts) for field in request_parts[0][k]} for k in ('hit','miss')}
  row['per_request_phases']=request_parts
  assert all(abs(row['full_scope_request_mean_medians'][k]['cycle_ms']-row['reported_cycle_mean_median'][k])<1e-8 for k in ('hit','miss'))
  row['pooled_cycle_medians']={k:{f:st.median(x[f] for x in xs) for f in xs[0]} for k,xs in partition.items()}
  row['additive_pooled_cycle_means']={k:{f:st.mean(x[f] for x in xs) for f in xs[0]} for k,xs in partition.items()}
  row['draft_completion_to_next_sent_ms']=a.stats(publication)
  row['snapshot_counters']=snapshots
  result[label]=row
 (E/'cycle-attribution.json').write_text(json.dumps(result,indent=2)+'\n')
 (E/'attribution-input-hashes.json').write_text(json.dumps(a.HASHES,indent=2)+'\n')
 print(json.dumps({n:dict(rate=r['class_balanced_rate'],cycles=r['reported_cycle_mean_median'],paired=r['paired_miss_spec_minus_redo']) if r['complete'] else r for n,r in result.items()},indent=2))
if __name__=='__main__':main()
