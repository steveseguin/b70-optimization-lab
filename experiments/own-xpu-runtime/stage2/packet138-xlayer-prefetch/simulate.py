"""Matched 18 GB cache simulations and explicit conditional rate ranges."""
import gzip,json,resource,statistics,sys,time
from dataclasses import asdict,replace
from pathlib import Path
from cache_sim import Scenario,Simulator,projection
from router_replay import P,ROOT,sha,save,PREDICTORS,analysis_identity

def read(path):
 raw=Path(path).read_bytes();return json.loads(gzip.decompress(raw) if str(path).endswith('.gz') else raw)

def main():
 from build_engine import limits
 limits();pred_path=P/'evidence/predictions.json.gz'
 if not pred_path.exists():
  save(P/'evidence/projection-status.json',dict(status='pending_real_capture_and_exact_replay',passed=False,phase2_decision='pending',projected_tok_s=None,zero_copy_bytes_per_token=None))
  print('Prediction capture/replay pending; no cache result or rate invented.');return
 from capture_inputs import require_ready
 require_ready();pred=read(pred_path);replay_path=P/'evidence/router-replay.json.gz';replay=read(replay_path)
 assert pred['passed'] and replay['passed'] and replay['exact_same_layer']
 assert replay['analysis_seal_sha256']==analysis_identity(),'replay analysis implementation changed'
 assert pred['capture_manifest_sha256']==sha(P/'evidence/capture-inputs.json')==replay['capture_manifest_sha256']
 assert pred['router_replay_sha256']==sha(replay_path)
 prefill_path=P/'evidence/prefill-inputs.json.gz';pre=read(prefill_path);assert pre['passed']
 binding=read(P/'evidence/prefill-binding.json');assert binding['sha256']==sha(prefill_path)
 for name,h in pre['sources'].items():assert sha(ROOT/name)==h,name
 timing=read(P/'evidence/timing-inputs.json');assert timing['passed']
 for name,h in timing['sources'].items():assert sha(ROOT/name)==h,name
 suite=read(P/'suite.snapshot.json');entries=[e for e in suite['prompts'] if e['analysis_included']]
 assert set(pred['truth'])=={e['prompt_id'] for e in entries}==set(pre['prompts'])
 sizes=[r['bytes'] for r in replay['expert_sizes']];assert len(sizes)==48
 predictions={}
 for row in pred['rows']:
  key=(row['predictor'],row['prompt_id'],row['target_layer']);assert key not in predictions
  assert len(row['ids'])==48 and all(len(ids)==16 and len(set(ids))==16 and all(0<=i<512 for i in ids) for ids in row['ids'])
  predictions[key]=row['ids']
 assert len(predictions)==5*12*47
 results=[];controls=[];started=time.monotonic()
 for cfg in timing['assumed_scenarios']:
  penalties=timing['k1_remote_penalty_ms_per_missing_expert'][cfg['remote_penalty']]
  base=timing['metric_events_2_100'];remote=penalties['0']/sizes[0]
  scenario=Scenario(cfg['name'],timing['equal_share_remainder_ms'],cfg['pre_router_fraction'],cfg['bandwidth_GB_s']*1e6*cfg['dma_fraction'],
    cfg['predictor_ms'],cfg['publication_ms'],cfg['plan_extra_ms'],cfg['fill_submit_ms'],cfg['window_fraction'],
    timing['record_reciprocal_ms']-cfg['hidden_control_cache_fraction']*base['cache_wall_ms'],remote,False,penalties['2']/sizes[2])
  def run(predictor=None,k=0,window_scale=1.):
   sim=Simulator(sizes,scenario);by_prompt=[]
   for e in entries:
    name=e['prompt_id'];sim.reset_request();sim.s=scenario
    for token in pre['prompts'][name]:sim.token(token,record=False)
    sim.s=replace(scenario,layer_ms=scenario.layer_ms*window_scale)
    start=len(sim.token_rows)
    for index,route in enumerate(pred['truth'][name]):
     assert len(route)==48 and all(len(ids)==10 and len(set(ids))==10 for ids in route)
     guess=None if predictor is None else [[]]+[predictions[predictor,name,layer][index][:k] for layer in range(1,48)]
     sim.token(route,guess,predictor or 'router_input')
    rows=sim.token_rows[start:];by_prompt.append(dict(prompt_id=name,category=e['category'],tokens=len(rows),zero_copy_bytes=sum(r.get('zero_copy_bytes',0) for r in rows)/len(rows)))
   out=sim.summary();out['by_prompt']=by_prompt;return out
  control=run();controls.append(dict(scenario=asdict(scenario),result=control))
  for predictor in PREDICTORS:
   for k in (10,12,16):
    candidate=run(predictor,k);rate=projection(control,candidate,scenario)
    original_gain=rate['gain_percent'];maximum_gain=max(0,original_gain);window_scale=1.;consistent=True;iterations=0
    # A faster candidate has less compute time in which to hide its next copy.
    # Retain the tightest window encountered, never enlarge it to obtain a pass.
    if maximum_gain>0:
     consistent=False
     for iterations in range(1,6):
      window_scale=1/(1+maximum_gain/100)
      candidate=run(predictor,k,window_scale);rate=projection(control,candidate,scenario)
      if rate['gain_percent']<=maximum_gain+1e-6:consistent=True;break
      maximum_gain=rate['gain_percent']
    rate['self_consistent_windows']=consistent
    results.append(dict(scenario=cfg['name'],predictor=predictor,k=k,candidate=candidate,projection=rate,
     initial_fixed_window_gain_percent=original_gain,candidate_window_scale=window_scale,window_rechecks=iterations))
    print(cfg['name'],predictor,k,'conditional gain',round(rate['gain_percent'],3),'percent; elapsed',round(time.monotonic()-started,1),flush=True)
    limits()
 ranges=[]
 for predictor in PREDICTORS:
  for k in (10,12,16):
   rows=[r for r in results if r['predictor']==predictor and r['k']==k]
   ranges.append(dict(predictor=predictor,k=k,projected_tok_s_range=[min(r['projection']['candidate_tok_s'] for r in rows),max(r['projection']['candidate_tok_s'] for r in rows)],
    projected_gain_percent_range=[min(r['projection']['gain_percent'] for r in rows),max(r['projection']['gain_percent'] for r in rows)],
    assumed_traffic_fits_all=all(r['projection']['traffic_fits_assumed_windows'] and r['projection']['self_consistent_windows'] for r in rows)))
 # Phase 1 is a projection gate, not a device performance certification. Require
 # the entire registered sensitivity range and every charged transfer to fit.
 modeled_pass=any(r['projected_gain_percent_range'][0]>=3 and r['assumed_traffic_fits_all'] for r in ranges)
 all_upper_fail=all(r['projected_gain_percent_range'][1]<3 for r in ranges)
 decision=('proceed_to_phase2_design_conditional_on_timing_assumptions' if modeled_pass else
           'close_below_3_percent_even_optimistic' if all_upper_fail else 'close_gain_or_traffic_gate_not_met')
 save(P/'evidence/cache-projections.json.gz',dict(schema='packet138.cache-projection.v1',passed=True,device_executed=False,projected_not_measured=True,
  controls=controls,results=results,ranges=ranges,modeled_gate_passed=modeled_pass,phase2_design_allowed=modeled_pass,decision=decision,
  measured_per_layer_windows_available=False,assumptions=timing['assumptions'],
  limitations=['No latency fitting to benchmark prompt outputs; estimates use independent calibration miss deltas and a 58p period anchor.',
   'Prior packet55 non-speculative prefill initializes the cache; new capture covers accepted decode only.',
   'Candidate moves demand planning after its layer prefetches and charges an explicit cost; it does not claim to execute unchanged 58v device scheduling.',
   'Fixed causal windows are sensitivities, not measured per-layer time; 48-token calibration is not a 99-interval headline.'],
  sources={str(f.relative_to(ROOT)):sha(f) for f in (pred_path,replay_path,prefill_path,P/'evidence/timing-inputs.json',P/'cache_sim.py',P/'simulate.py')},elapsed_seconds=time.monotonic()-started))
 save(P/'evidence/projection-status.json',dict(passed=True,projected_not_measured=True,phase2_decision=decision,modeled_gate_passed=modeled_pass,phase2_design_allowed=modeled_pass,ranges=ranges))
 print('Phase 1 decision:',decision)
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
