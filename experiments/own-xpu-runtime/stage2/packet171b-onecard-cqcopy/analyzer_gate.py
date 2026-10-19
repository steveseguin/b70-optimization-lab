"""Replay actual old device evidence without relabeling it as this candidate.

packet171b adds the real packet58as v5 bracket (the spin parent of this packet)
and the mechanism readout, which must reproduce packet171's measured.json.
"""
import copy,json,math,sys
from pathlib import Path
from build_engine import P,sha,save
sys.path.insert(0,str(P/'screen'))
import suite_driver as D
import mechanism as M
from compare_bracket import compare

MEASURED=P.parent/'packet171-onecard-host-parity/measured.json'

def main():
 manifest=D.oracle_inputs();records=[];pins={};max_cold=0;prompt_ids=[e['prompt_id'] for e in manifest['prompts']]
 for name,labels,cap in [('packet58as',['A0','B0','A1','B1','A2'],128),('packet58aj',['A0','B0','A1','B1','A2'],128),
                         ('packet58aq',['A0','U0','S0','D0','W0','A1'],32)]:
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
  # Real parent evidence lacks the packet171b foreground-copy identity; it must not qualify.
  try:D.verify_lookup_views(root,'resident')
  except (ValueError,FileNotFoundError,KeyError):pass
  else:raise AssertionError('old evidence accepted as compute-queue-copy candidate')
  record=dict(name=name,exact_requests=sum(r['request_count'] for r in rows),timing_rows=timing_count,new_identity_refused=True,
              measured_rates=[r['class_balanced_tok_s_1_100_intervals_after_ttft']['median'] for r in rows])
  if name=='packet58as':
   # Mechanism readout on the real spin-parent bracket reproduces packet171 measured.json.
   measured=json.loads(MEASURED.read_text())['views']
   out=M.readout(root/'run',labels,prompt_ids,candidate_wins=False)
   for label in labels:
    got=out['views'][label];want=measured[label]
    assert got['tokens']==want['tokens'],label
    for k,w in (('slow_readback_fraction','slow_readback_fraction'),('transfer_wall_ms','transfer_wall_ms'),('wait_ms','wait_ms'),('wall_ms','wall_ms'),
                ('median_transfer_wall_ms','median_transfer_wall_ms'),('p_slow_readback_after_fill_token','p_slow_readback_given_previous_token_high_other'),
                ('p_slow_readback_on_fill_token','p_slow_readback_given_same_token_high_other')):
     assert abs(got[k]-want[w])<=1e-4,(label,k,got[k],want[w])
    assert abs(got['slow_token_wait_excess_ms']-(want['slow_tokens']['wait_ms']-want['fast_tokens']['wait_ms']))<=2e-4,label
   # The parent spin views keep the bimodal slow mode: the readout must not call it collapsed.
   assert not out['slow_mode_collapsed'] and out['verdict'].startswith('close row 1')
   record['mechanism_readout']=out;record['mechanism_matches_packet171_measured']=True
   record['measured_digest']=dict(name='measured.json',parent_relpath=str(MEASURED.relative_to(P.parents[3])),parent_digest=sha(MEASURED))
  records.append(record)
  if name=='packet58as':
   # Comparator arithmetic uses real token identities with explicitly synthetic rates.
   fixture=copy.deepcopy(rows)
   for i,r in enumerate(fixture):r.update(label=labels[i],view='spin-cq' if i%2 else 'spin');r['class_balanced_tok_s_1_100_intervals_after_ttft']['median']=[1,100.5,100,100.5,100][i]
   assert compare(fixture)['candidate_beats_all_controls']
   fixture[3]['class_balanced_tok_s_1_100_intervals_after_ttft']['median']=100.499
   assert not compare(fixture)['candidate_beats_all_controls']
   fixture[3]['class_balanced_tok_s_1_100_intervals_after_ttft']['median']=110
   fixture[1]['class_balanced_tok_s_1_100_intervals_after_ttft']['median']=110
   fixture[4]['class_balanced_tok_s_1_100_intervals_after_ttft']['median']=103.01
   assert not compare(fixture)['candidate_beats_all_controls']
   relabeled=copy.deepcopy(fixture);relabeled[1]['view']='poll'
   try:compare(relabeled)
   except ValueError:pass
   else:raise AssertionError('poll/spin parent labels accepted as candidate order')
   fixture[-1]['requests'][-1]['tokens'][-1]+=1
   try:compare(fixture)
   except ValueError:pass
   else:raise AssertionError('corruption accepted')
   # Synthetic collapse readout: labeled synthetic, never device data.
   synthetic=M.readout(root/'run',labels,prompt_ids,candidate_wins=True)
   assert synthetic['verdict'].startswith('mixed')
 assert 600>=4*max_cold
 save(P/'evidence/analyzer-real-parent.json',dict(passed=True,device_executed=False,records=records,source_hashes=pins,maximum_measured_cold_phase_seconds=max_cold,per_operation_wait_seconds=600,wait_at_least_four_times_cold=True,synthetic_threshold_checks_labeled=True))
 print('PASS',sum(r['exact_requests'] for r in records),'exact real device requests; old identity refused; mechanism readout reproduces measured.json; thresholds and drift tested')
if __name__=='__main__':main()
