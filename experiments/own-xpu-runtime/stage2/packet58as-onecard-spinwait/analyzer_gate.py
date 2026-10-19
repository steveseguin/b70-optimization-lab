"""Replay actual old device evidence without relabeling it as this candidate."""
import copy,json,math,sys
from pathlib import Path
from build_engine import P,sha,save
sys.path.insert(0,str(P/'screen'))
import suite_driver as D
from compare_bracket import compare

def main():
 manifest=D.oracle_inputs();records=[];pins={};max_cold=0
 for name,relative,labels,cap in [
 ('packet58aj','packet58aj-onecard-resident/screen/evidence/card0-58ajb-screen-a/resident/WSCREEN/run',['A0','B0','A1','B1','A2'],128),
 ('packet58aq','packet58aq-onecard-split/screen/evidence/card0-58aq-split-a/resident/WSCREEN/run',['A0','U0','S0','D0','W0','A1'],32)]:
  root=P/'lineage/device-evidence'/name;rows=[];timing_count=0
  for label in labels:
   summary=D.summarize(root,'WSCREEN',manifest,label,cap);assert summary['passed'];rows.append(summary)
   for e in manifest['prompts']:
    for leaf in ('result.json','timings.jsonl','prefill-timings.jsonl'):
     f=root/'run'/label/e['prompt_id']/leaf;pins[str(f.relative_to(P.parents[3]))]=sha(f)
     if leaf.endswith('.jsonl'):
      stream=[json.loads(s) for s in f.read_text().splitlines()];assert stream
      assert all(math.isfinite(r['wall_ms']) and r['wall_ms']>=0 for r in stream)
      timing_count+=len(stream)
      if leaf.startswith('prefill'):max_cold=max(max_cold,max(r['wall_ms']/1000 for r in stream))
  # Real parent lacks new CPU/wait identity; it must not qualify as p58as.
  try:D.verify_lookup_views(root,'resident')
  except (ValueError,FileNotFoundError,KeyError):pass
  else:raise AssertionError('old evidence accepted as spin candidate')
  records.append(dict(name=name,exact_requests=sum(r['request_count'] for r in rows),timing_rows=timing_count,new_identity_refused=True,measured_rates=[r['class_balanced_tok_s_1_100_intervals_after_ttft']['median'] for r in rows]))
  if cap==128:
   # Comparator arithmetic uses real token identities with explicitly synthetic rates.
   fixture=copy.deepcopy(rows)
   for i,r in enumerate(fixture):r.update(label=labels[i],view='spin' if i%2 else 'poll');r['class_balanced_tok_s_1_100_intervals_after_ttft']['median']=[1,100.5,100,100.5,100][i]
   assert compare(fixture)['candidate_beats_all_controls']
   fixture[3]['class_balanced_tok_s_1_100_intervals_after_ttft']['median']=100.499
   assert not compare(fixture)['candidate_beats_all_controls']
   fixture[3]['class_balanced_tok_s_1_100_intervals_after_ttft']['median']=110
   fixture[1]['class_balanced_tok_s_1_100_intervals_after_ttft']['median']=110
   fixture[4]['class_balanced_tok_s_1_100_intervals_after_ttft']['median']=103.01
   assert not compare(fixture)['candidate_beats_all_controls']
   fixture[-1]['requests'][-1]['tokens'][-1]+=1
   try:compare(fixture)
   except ValueError:pass
   else:raise AssertionError('corruption accepted')
 assert 600>=4*max_cold
 save(P/'evidence/analyzer-real-parent.json',dict(passed=True,device_executed=False,records=records,source_hashes=pins,maximum_measured_cold_phase_seconds=max_cold,per_operation_wait_seconds=600,wait_at_least_four_times_cold=True,synthetic_threshold_checks_labeled=True))
 print('PASS 132 exact real device requests; old identity refused; thresholds and drift tested')
if __name__=='__main__':main()
