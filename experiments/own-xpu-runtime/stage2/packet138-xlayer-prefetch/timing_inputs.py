"""Extract exact 58p/58g anchors; absent per-layer clocks remain null."""
import json,resource
from router_replay import P,ROOT,sha,save

def main():
 from build_engine import limits
 limits();source=P.parent/'packet58v-async-cache/evidence/measurement.json';m=json.loads(source.read_text())
 assert m['passed'] and m['device_executed'] is False
 record=next(r for r in m['records'] if r['path'].endswith('/WS128'))
 for name,h in m['sources'].items():
  if name.startswith(record['path']+'/'):assert sha(ROOT/name)==h,name
 base=record['metric_events_2_100'];assert base['positions']==1188
 period=1000/record['rate'];assert abs(record['rate']-26.228599)<1e-6
 penalty_path=P.parent/'packet58i-onecard-attribution/lever-models.json';penalty=json.loads(penalty_path.read_text())['k1_estimated_remote_penalty_ms_per_missing_expert']
 sources={str(source.relative_to(ROOT)):sha(source),str(penalty_path.relative_to(ROOT)):sha(penalty_path)}
 sources.update({n:h for n,h in m['sources'].items() if n.startswith(record['path']+'/')})
 # The per-layer budget is a sensitivity derived from a measured aggregate,
 # not a made-up per-layer measurement. Head/host work makes it optimistic.
 average=(base['token_wall_ms']-base['cache_wall_ms'])/48
 row=dict(passed=True,device_executed=False,projected_not_measured=True,record_tok_s=record['rate'],record_reciprocal_ms=period,
  metric_events_2_100=base,per_layer_measured_ms=None,per_layer_reason='58g/58p device profiling disabled; zero fields are placeholders',
  equal_share_remainder_ms=average,k1_remote_penalty_ms_per_missing_expert=penalty,
  assumed_scenarios=[dict(name='conservative',bandwidth_GB_s=19,dma_fraction=.5,window_fraction=.25,predictor_ms=.05,publication_ms=.01,plan_extra_ms=.25,fill_submit_ms=.006,pre_router_fraction=.5,hidden_control_cache_fraction=.5,remote_penalty='mixed_half_host_linear'),
   dict(name='middle',bandwidth_GB_s=25,dma_fraction=.5,window_fraction=.5,predictor_ms=.025,publication_ms=.005,plan_extra_ms=.1,fill_submit_ms=.003,pre_router_fraction=.5,hidden_control_cache_fraction=.5,remote_penalty='mixed_half_host_linear'),
   dict(name='optimistic',bandwidth_GB_s=25,dma_fraction=.75,window_fraction=1.,predictor_ms=.01,publication_ms=.002,plan_extra_ms=.05,fill_submit_ms=.001,pre_router_fraction=.5,hidden_control_cache_fraction=.5,remote_penalty='all_host_linear')],
  assumptions=['Control is the modeled 58v delayed asynchronous schedule, anchored to the 58p token period with half its cache span hidden; no measured 58v speed is claimed.',
   'Equal per-layer remainder is a proxy; the fixed 25/50/100% causal window shares reserve unmeasured head/host/PCIe work.',
   'DMA bandwidth and fraction, extra router/publication cost, and plan cost are sensitivity assumptions, not measured on this path.',
   'Remote penalties are linear K1 host-vs-device proxies from 58g/58i, not measured per-expert sparse miss costs.',
   'Both arms use the same inputs, byte capacity, empty initial cache, prior prompt prefill and global LRU.',
   'Candidate layer-boundary publication is a modeling assumption; there is no device implementation or lossless device proof.'],sources=sources)
 save(P/'evidence/timing-inputs.json',row)
 print('58p anchor',record['rate'],'tok/s; equal-share remainder',average,'ms/layer (assumed); measured layer clocks absent')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
