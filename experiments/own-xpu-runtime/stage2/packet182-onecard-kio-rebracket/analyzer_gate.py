"""Replay actual old device evidence without relabeling it as this candidate.

packet182 (2026-10-22): the packet58as and packet174 v5 run trees (and packet176's own
v5 tree) were removed with untracked files on 2026-10-19 21:42 EDT; only packet171b's
real spin streams remain (ignored by Git, so they survived). This gate therefore runs on
packet171b alone (60 exact real device requests, 5 views) and adds:
- the packet176 fields must equal packet176's committed analyzer output for packet171b
  (git HEAD, evidence/analyzer-real-parent.json): the packet182 additions change nothing
  the device readout already reported;
- the packet182 fill split (filled vs unfilled decode tokens) and fill_lever_price on every
  view, with the unfilled-vs-next-fill control slope.
The original packet176 docstring follows.

packet176: the real packet58as v5 spin bracket (this packet's parent), the
real packet171b bracket (spin parent and compute-queue copies) and the real
packet174 bracket (spin parent and fill kick). None carries the foreground-io
identity, so all must be refused as packet176 evidence. The packet176
mechanism readout must reproduce, on every spin view of every run: the slow
foreground transfer occurs only on fill-submission tokens, and its excess is
linear in that token's fill bytes (0.030-0.040 ms/MB, intercept < 0.2 ms);
the carrying engine is the copy engine and the head/tail split is unavailable
on these streams (the fields are new in packet176).
Raw streams are read in place (host-local parent evidence); their digests are
recorded as {name, parent_relpath, parent_digest} provenance records only.
"""
import copy,json,math,sys
from pathlib import Path
from build_engine import P,sha,save
sys.path.insert(0,str(P/'screen'))
import suite_driver as D
import mechanism as M
from compare_bracket import compare
ROOT=P.parents[3]
RUNS=[('packet171b',P.parent/'packet171b-onecard-cqcopy/screen/evidence/card0-171b-v5-a/resident/WSCREEN/run',('A0','B0','A1','B1','A2'))]
MISSING=[('packet58as',P.parent/'packet58as-onecard-spinwait/screen/evidence/card0-58as-v5-a/resident/WSCREEN/run'),
         ('packet174',P.parent/'packet174-onecard-fillkick/screen/evidence/card0-174-v5-a/resident/WSCREEN/run'),
         ('packet176',P.parent/'packet176-onecard-kernelio/screen/evidence/card0-176-v5-a/resident/WSCREEN/run')]
ORIGINAL_FIELDS=('tokens','foreground_io','engine','copy_engine_commands_per_decode_token','wall_ms','wait_ms','transfer_wall_ms',
                 'median_transfer_wall_ms','slow_readback_fraction','fill_tokens','fill_mb_per_token','p_slow_readback_on_fill_token',
                 'p_slow_readback_on_unfilled_token','readback_ms_per_fill_mb','readback_intercept_ms','wall_ms_per_fill_mb',
                 'wall_intercept_ms','wait_ms_per_fill_mb','wait_intercept_ms','next_token_transfer_ms_per_previous_fill_mb',
                 'end_of_position_states','fill_wait_carrier')
LABELS=['A0','B0','A1','B1','A2']

def main():
 manifest=D.oracle_inputs();records=[];provenance=[];max_cold=0;synthetic_attribution=False
 for name,root,spin_views in RUNS:
  rows=[];timing_count=0
  for label in LABELS:
   summary=D.summarize(root,'WSCREEN',manifest,label,128);assert summary['passed'];rows.append(summary)
   for e in manifest['prompts']:
    for leaf in ('timings.jsonl','prefill-timings.jsonl'):
     f=root/'run'/label/e['prompt_id']/leaf
     stream=[json.loads(s) for s in f.read_text().splitlines()];assert stream
     assert all(math.isfinite(r['wall_ms']) and r['wall_ms']>=0 for r in stream)
     timing_count+=len(stream)
     if leaf.startswith('prefill'):max_cold=max(max_cold,max(r['wall_ms']/1000 for r in stream))
  for leaf in ('run/cache.jsonl','suite-inputs.tsv','run/receipt.json'):
   f=root/leaf;provenance.append(dict(name=f'{name}:{leaf}',parent_relpath=str(f.relative_to(ROOT)),parent_digest=sha(f)))
  try:D.verify_lookup_views(root,'resident')
  except (ValueError,FileNotFoundError,KeyError):pass
  else:raise AssertionError('old evidence accepted as foreground-io candidate')
  out=M.readout(root/'run',LABELS,None,candidate_wins=False)
  for label in spin_views:
   v=out['views'][label]
   assert v['tokens']==1524 and v['p_slow_readback_on_unfilled_token']==0.0,(name,label,v['p_slow_readback_on_unfilled_token'])
   assert 0.030<=v['readback_ms_per_fill_mb']<=0.040 and abs(v['readback_intercept_ms'])<0.2,(name,label,v['readback_ms_per_fill_mb'],v['readback_intercept_ms'])
   assert v['p_slow_readback_on_fill_token']>=0.75 and abs(v['fill_mb_per_token']-30.63)<0.01,(name,label)
   assert v['foreground_io']=='copy' and v['engine']==M.COPY and v['copy_engine_commands_per_decode_token']>0
   assert v['head_ms_per_fill_mb'] is None and v['tail_ms_per_fill_mb'] is None and v['fill_wait_carrier'].startswith('unsplit')
  assert not out['slow_mode_collapsed'] and out['verdict'].startswith('close')
  import subprocess
  committed=json.loads(subprocess.run(['git','-C',str(ROOT),'show','HEAD:experiments/own-xpu-runtime/stage2/packet176-onecard-kernelio/evidence/analyzer-real-parent.json'],
                                      stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True).stdout)
  old=next(r for r in committed['records'] if r['name']==name)['mechanism_readout']
  for label in LABELS:
   for k in ORIGINAL_FIELDS:assert out['views'][label][k]==old['views'][label][k],(name,label,k)
  for k in ('slow_mode_collapsed','fill_cost_moved','verdict','collapse_rule','moved_rule'):assert out[k]==old[k],k
  for label in LABELS:
   s=out['views'][label]['fill_split'];assert s['available'] and s['filled_tokens']+s['unfilled_tokens']==1524
   assert abs(s['outside_transfer_ms_per_fill_mb_filled_tokens']-s['control_unfilled_outside_transfer_ms_per_next_fill_mb'])<0.002,label
   assert 0.55<s['fill_attributable_outside_transfer_ms_per_filled_token']<0.70 and s['fill_attributable_fraction_of_wall']<0.012,label
  records.append(dict(name=name,exact_requests=sum(r['request_count'] for r in rows),timing_rows=timing_count,new_identity_refused=True,
                      spin_views=list(spin_views),measured_rates=[r['class_balanced_tok_s_1_100_intervals_after_ttft']['median'] for r in rows],
                      mechanism_readout=out,slow_readback_only_on_fill_tokens=True,readback_linear_in_same_token_fill_bytes=True))
  if name=='packet171b':
   # Comparator arithmetic uses real token identities with explicitly synthetic rates.
   fixture=copy.deepcopy(rows)
   for i,r in enumerate(fixture):r.update(label=LABELS[i],view='spin-kio' if i%2 else 'spin');r['class_balanced_tok_s_1_100_intervals_after_ttft']['median']=[1,100.5,100,100.5,100][i]
   # 171b's B views are 'spin-cq': real compare must refuse them as kio candidates.
   try:compare([dict(r,label=LABELS[i],view='spin-cq' if i%2 else 'spin') for i,r in enumerate(rows)])
   except ValueError:pass
   else:raise AssertionError('spin-cq views accepted as kernel-io candidates')
   assert compare(fixture)['candidate_beats_all_controls']
   fixture[3]['class_balanced_tok_s_1_100_intervals_after_ttft']['median']=100.499
   assert not compare(fixture)['candidate_beats_all_controls']
   fixture[3]['class_balanced_tok_s_1_100_intervals_after_ttft']['median']=110
   fixture[1]['class_balanced_tok_s_1_100_intervals_after_ttft']['median']=110
   fixture[4]['class_balanced_tok_s_1_100_intervals_after_ttft']['median']=103.01
   assert not compare(fixture)['candidate_beats_all_controls']
   for wrong in ('poll','spin-cq','spin-kick'):
    relabeled=copy.deepcopy(fixture);relabeled[1]['view']=wrong
    try:compare(relabeled)
    except ValueError:pass
    else:raise AssertionError(f'{wrong} labels accepted as candidate order')
   fixture[-1]['requests'][-1]['tokens'][-1]+=1
   try:compare(fixture)
   except ValueError:pass
   else:raise AssertionError('corruption accepted')
   # Synthetic collapse decision: labeled synthetic, never device data.
   synthetic=M.readout(root/'run',LABELS,None,candidate_wins=True)
   assert synthetic['verdict'].startswith('mixed')
   # Synthetic head/tail attribution on real rows (labeled synthetic): the excess
   # placed in the head must read 'head', in the tail 'tail'.
   real=M._rows(root/'run',LABELS)
   for where in ('head','tail'):
    rows=copy.deepcopy(real)
    for r in rows:
     x=r['transfer_wall_ms'];r['head_transfer_ms']=x-0.05 if where=='head' else 0.05;r['tail_transfer_ms']=0.05 if where=='head' else x-0.05;r['route_log_ms']=0.02
    assert M.view(rows,'A1')['fill_wait_carrier']==where
    synthetic_attribution=True
 assert 600>=4*max_cold
 missing=[dict(name=n,parent_relpath=str(r.relative_to(ROOT)),present=r.is_dir(),reason='untracked run tree removed 2026-10-19 21:42 EDT') for n,r in MISSING]
 assert not any(m['present'] for m in missing),'a removed run tree is back: add it to RUNS'
 save(P/'evidence/analyzer-real-parent.json',dict(passed=True,device_executed=False,records=records,synthetic_head_tail_attribution=synthetic_attribution,provenance=provenance,maximum_measured_cold_phase_seconds=max_cold,per_operation_wait_seconds=600,wait_at_least_four_times_cold=True,synthetic_threshold_fixture=True,
     unavailable_real_runs=missing,packet176_fields_identical_to_committed_packet176_readout=True,fill_split_checked=True))
 print('PASS',sum(r['exact_requests'] for r in records),'exact real device requests (packet171b); old identity refused; packet176 fields identical to its committed readout; fill split on 5 views')
if __name__=='__main__':main()
