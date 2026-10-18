"""Human-readable phase-1 report derived only from the completed real analysis."""
import gzip,json,resource
from router_replay import P,sha,save

def read(path):return json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes())
def span(values,digits=2):return f'{min(values):.{digits}f} to {max(values):.{digits}f}'

def main():
 from build_engine import limits
 limits();e=P/'evidence';continuation=read(e/'continuation.json');assert continuation['passed']
 for name,digest in continuation['outputs'].items():assert sha(e/name)==digest,name
 replay=read(e/'router-replay.json.gz');cache=read(e/'cache-projections.json.gz')
 assert replay['passed'] and cache['passed'] and replay['exact_same_layer']
 recall={(r['predictor'],r['k']):r['recall'] for r in replay['predictors']}
 summary={}
 for axis in ('target_layer','category'):
  groups={}
  for row in replay['per_prompt_layer']:
   key=row['predictor'],row['k'],row[axis];group=groups.setdefault(key,[0,0])
   group[0]+=row['matched_experts'];group[1]+=row['target_experts']
  summary[axis]=[dict(predictor=p,k=k,**{axis:value},matched_experts=h,target_experts=n,recall=h/n)
                 for (p,k,value),(h,n) in sorted(groups.items())]
 save(e/'recall-summary.json',dict(passed=True,router_replay_sha256=sha(e/'router-replay.json.gz'),**summary))
 best=max(cache['results'],key=lambda r:r['projection']['gain_percent'])
 control_rates=[1000/c['scenario']['control_anchor_ms'] for c in cache['controls']]
 controls_miss=[c['result']['per_token'].get('zero_copy_bytes',0)/1e6 for c in cache['controls']]
 rows=['# Packet138 phase-1 results','',
  '**All rates and cache outcomes below are projections, not device speed measurements.**','',
  f"Decision: `{cache['decision']}`. Phase-2 design allowed by this gate: **{str(cache['phase2_design_allowed']).lower()}**.",'',
  'The coordinator captured 48 accepted tokens on each of twelve independent held-out prompts and one separate sanity prompt. All 624 output tokens match their pinned references; the sanity prompt is excluded from analysis. Exact same-layer CPU replay agrees on all 14,155,776 BF16 logits and 276,480 expert IDs.', '',
  f"The modeled 58v control is {span(control_rates,4)} tok/s with {span(controls_miss,3)} MB/token read zero-copy. Its speed is not a measured 58v result. The unchanged one-card measured record remains 26.228599 tok/s.", '',
  f"The highest projected gain in any registered scenario is {best['projection']['gain_percent']:+.3f}% ({best['predictor']}, width {best['k']}, {best['scenario']}). This is a diagnostic best case, not a selected benchmark headline.", '',
  f"Even that case has {best['candidate']['totals'].get('prefetch_late_batches',0)} late batches out of {best['candidate']['totals'].get('prefetch_batches',0)} submitted. It moves {best['candidate']['per_token'].get('prefetch_bytes',0)/1e6:.3f} MB/token by prefetch, including {best['candidate']['per_token'].get('prefetch_wrong_bytes',0)/1e6:.3f} MB/token not used by the predicted next layer. No registered case fits every copy inside its assumed window.", '',
  '| Predictor | Width | Recall | Zero-copy MB/token | Projected tok/s | Gain vs modeled control | Every copy fits all scenarios? |',
  '| --- | ---: | ---: | ---: | ---: | ---: | --- |']
 for r in cache['ranges']:
  p,k=r['predictor'],r['k'];group=[x for x in cache['results'] if x['predictor']==p and x['k']==k]
  miss=[x['candidate']['per_token'].get('zero_copy_bytes',0)/1e6 for x in group]
  rows.append(f"| {p} | {k} | {recall[p,k]*100:.2f}% | {span(miss,3)} | {span(r['projected_tok_s_range'],3)} | {span(r['projected_gain_percent_range'],2)}% | {'yes' if r['assumed_traffic_fits_all'] else 'no'} |")
 rows+=['','## Charged traffic','',
  '| Predictor | Width | Prefetch MB/token | Wrong prefetch MB/token | Late batches/token |',
  '| --- | ---: | ---: | ---: | ---: |']
 for r in cache['ranges']:
  p,k=r['predictor'],r['k'];group=[x['candidate']['per_token'] for x in cache['results'] if x['predictor']==p and x['k']==k]
  rows.append(f"| {p} | {k} | {span([x.get('prefetch_bytes',0)/1e6 for x in group],3)} | {span([x.get('prefetch_wrong_bytes',0)/1e6 for x in group],3)} | {span([x.get('prefetch_late_batches',0) for x in group],3)} |")
 rows+=['','## Limits and evidence','',
  'The registered scenarios charge wrong and late copies, predictor work, publication and extra planning. The 18 GB cache keeps the original global LRU and packed expert sizes. Prediction is disabled during historical prompt prefill. A positive candidate is checked again with shorter decode windows; prefill timing is unchanged.', '',
  'The old receipts lack measured layer clocks. Per-layer time, bandwidth fractions, router costs and the hidden share of 58v cache work are explicit assumptions. Remote penalties are historical K1 proxies. These estimates cannot certify a speedup or replace a phase-2 device quality check. This 48-token calibration capture is not the realistic performance suite.', '',
  '- [Capture hashes and exactness](evidence/capture-inputs.json)',
  '- [Exact replay and per-prompt/layer recall](evidence/router-replay.json.gz)',
  '- [Recall by layer and class](evidence/recall-summary.json)',
  '- [All cache outcomes and projections](evidence/cache-projections.json.gz)',
  '- [Timing inputs and assumptions](evidence/timing-inputs.json)',
  '- [CPU continuation receipt](evidence/continuation.json)',
  '- [Method and idea credit](ANALYSIS.md)',
  '- [Retention and restoration](RETENTION.md)','']
 (P/'RESULTS.md').write_text('\n'.join(rows))
 status=read(e/'analysis-status.json')
 status.update(phase2_decision=cache['decision'],phase2_design_allowed=cache['phase2_design_allowed'],
               cache_projection_sha256=sha(e/'cache-projections.json.gz'))
 save(e/'analysis-status.json',status)
 save(e/'report-identity.json',dict(passed=True,sources={str(f.relative_to(P)):sha(f) for f in
  (P/'report_results.py',e/'continuation.json',e/'router-replay.json.gz',e/'cache-projections.json.gz')},
  outputs={str(f.relative_to(P)):sha(f) for f in (P/'RESULTS.md',e/'recall-summary.json',e/'analysis-status.json')}))
 print('Phase-1 report generated from completed real analysis:',cache['decision'])

if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
