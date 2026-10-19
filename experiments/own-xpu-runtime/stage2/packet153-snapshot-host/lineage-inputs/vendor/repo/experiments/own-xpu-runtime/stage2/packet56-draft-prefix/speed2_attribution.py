"""Read-only retained-receipt attribution; no build or device access."""
import importlib.util,json,statistics as st
from pathlib import Path
P=Path(__file__).resolve().parent;E=P/'evidence/speed2'
def main():
 spec=importlib.util.spec_from_file_location('retained_analysis',P/'evidence/regression-analysis/analyze.py')
 a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
 for dr in (0,1):
  archived=P/f'build/results-65c5eb22b/c4096-dr{dr}-gpu/WS128'
  if archived.exists():a.RUNS[f'p45-dr{dr}']=archived
 classes={r['prompt_id']:r['prompt_class'] for r in a.read(a.RUNS['p45-dr0']/'run/summary.json')['rows']}
 result={}
 for name,root in a.RUNS.items():
  label=name.replace('p45-','speed1-')
  if not (root/'window.json').exists():result[label]={'complete':False};continue
  row=a.analyze(root,classes)
  if name.startswith('p45') and row['complete']:
   expected=json.loads((P/'evidence/speed2/before-build-receipt.json').read_text())['artifacts_sha256']['device/own-rt-iq3']
   assert row['window']['artifacts_sha256']['device/own-rt-iq3']==expected,'not SPEED1 artifact'
  if not row['complete']:result[label]=row;continue
  partition={'hit':[],'miss':[]};publication=[];snapshots=[]
  for f in sorted((root/'run/repeat-1').glob('*/receipt.json')):
   receipt=a.read(f);trace=receipt['rank_trace']
   for d in receipt['draft_rows']:
    if d.get('hit') is None or d['position']<100 or 'cycle_ms' not in d:continue
    left=d['target_completed_monotonic'];right=left+d['cycle_ms']/1000
    halves=[t for t in trace if t['rank']==1 and t['op']==1 and t['rank_received']>=left and t['rank_completed']<=right+1e-6]
    assert len(halves)==1;half=halves[0]
    parts=dict(before_rank1_half_ms=(half['rank_received']-left)*1000,rank1_half_ms=a.span(half),completion_observation_lag_ms=(right-half['rank_completed'])*1000,cycle_ms=d['cycle_ms'])
    for op in (1,3,9):parts[f'rank0_op{op}_before_half_ms']=sum(a.clip(t,left,half['rank_received']) for t in trace if t['rank']==0 and t['op']==op)
    assert abs(sum(parts[k] for k in ('before_rank1_half_ms','rank1_half_ms','completion_observation_lag_ms'))-parts['cycle_ms'])<1e-6
    partition['hit' if d['hit'] else 'miss'].append(parts)
   for i,t in enumerate(trace):
    if t['op']==9 and t['position']>=100:
     after=[q['sent'] for q in trace[i+1:] if q['sent']>=t['rank_completed']]
     if after:publication.append((min(after)-t['rank_completed'])*1000)
   snap=f.parent/'rank0/speculative-snapshot.json'
   if snap.exists():snapshots.append(a.read(snap))
  row['additive_pooled_cycle_means']={k:{f:st.mean(x[f] for x in xs) for f in xs[0]} for k,xs in partition.items()}
  row['draft_completion_to_next_sent_ms']=a.stats(publication)
  row['snapshot_counters']=snapshots
  result[label]=row
 (E/'cycle-attribution.json').write_text(json.dumps(result,indent=2)+'\n')
 (E/'attribution-input-hashes.json').write_text(json.dumps(a.HASHES,indent=2)+'\n')
 print(json.dumps({n:dict(rate=r['class_balanced_rate'],cycles=r['reported_cycle_mean_median'],paired=r['paired_miss_spec_minus_redo']) if r['complete'] else r for n,r in result.items()},indent=2))
if __name__=='__main__':main()
