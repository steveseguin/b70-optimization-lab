#!/usr/bin/env python3
"""Explicit counterfactuals, never performance measurements or promotion claims."""
import gzip
import json
from pathlib import Path
import statistics as st

HERE=Path(__file__).resolve().parent


def main():
    a=json.loads((HERE/'ATTRIBUTION.json').read_text())
    w=a['windows']
    replay=json.loads((HERE/'route-replay.json').read_text())['comparisons']
    baseline=a['baseline']
    def scenario(name,save,assumptions):
        classes={}
        points={}
        for prompt,p in w['WS128']['prompts'].items():
            delta=save(p['attribution'])
            rate=1000/(p['measured_interval_ms']/99-delta)
            points[prompt]=dict(assumed_saved_ms=delta,predicted_tok_s=rate)
            classes.setdefault(p['prompt_class'],[]).append(rate)
        rate=st.median(st.median(v) for v in classes.values())
        return dict(name=name,measured=False,conditional_estimate=True,
                    predicted_class_balanced_tok_s=rate,gain_pct=100*(rate/baseline-1),
                    assumptions=assumptions,per_prompt=points)
    costs={}
    for mode,label,misses in [(1,'all_host_linear',10),(2,'mixed_half_host_linear',5)]:
        samples=[]
        for k in ('K1a','K1b'):
            cases={(r['format'],r['mode']):r['ms'] for r in w[k]['cases']}
            # Ordinary: IQ2 gate/up plus IQ4 down. Layer2: IQ3 gate/up plus IQ4 down.
            samples.append({str(layer):sum(cases[(f,mode)]-cases[(f,0)] for f in formats)/misses
                            for layer,formats in [(0,(22,20)),(2,(21,20))]})
        costs[label]={layer:st.mean(s[layer] for s in samples) for layer in ('0','2')}
    def remote_penalty(p,label='mixed_half_host_linear'):
        c=p['cache']
        layer2=(1-c['layer2_hit_rate'])*10
        ordinary=c['fills']['mean']-layer2
        return ordinary*costs[label]['0']+layer2*costs[label]['2']
    base=replay['18GB_LRU']['totals']['decode']
    policies=[]
    for name,config in replay.items():
        r=config['totals']['decode']
        miss_ratio=r['miss_bytes']/base['miss_bytes']
        fill_ratio=(r['demand_fill_bytes']+r['speculative_fill_bytes'])/base['demand_fill_bytes']
        result=scenario(name,
            lambda p,m=miss_ratio,f=fill_ratio:remote_penalty(p)*(1-m)+p['cache']['wall_ms']['mean']*(1-f),
            ['Transfer packet55 held-out miss/fill byte ratios to WS128; this is not a native one-card route replay.',
             'Charge K1 mixed-five-miss host-minus-resident time linearly by inferred missing experts.',
             'Scale the ENTIRE cache wall by fill-byte ratio, including fixed costs; optimistic for smaller fill volumes.',
             'No new CPU policy cost. Full speculative traffic is charged.',
             '20.121 GB is conditional on proving unused allowance reusable under the same host bound; not admitted.'])
        result.update(miss_byte_ratio=miss_ratio,fill_byte_ratio=fill_ratio)
        policies.append(result)
    # Read per-position records to fit cache timing only; no inferred device timing.
    rows=[json.loads(x) for x in gzip.decompress((HERE/'position-attribution.jsonl.gz').read_bytes()).decode().splitlines()]
    fits=[]
    for name in ('WS','WS128x','WS128'):
        cold=[r for r in rows if r['window']==name and r['cache']['evictions']==0]
        fit=st.linear_regression([r['cache']['fills'] for r in cold],[r['cache']['wall_ms'] for r in cold])
        metric=[r for r in rows if r['window']==name and r['phase']=='decode' and 2<=r['timing']['generated_index']<=100]
        delta=st.mean(r['cache']['wall_ms']-fit.intercept-fit.slope*r['cache']['fills'] for r in metric)
        fits.append(dict(window=name,no_eviction_samples=len(cold),intercept_ms=fit.intercept,
            slope_ms_per_fill=fit.slope,metric_residual_mean_ms=delta,
            interpretation='Estimate/confounded: cannot identify victim-scan cost separately from fragmentation, occupancy, or scheduling.'))
    postrouter=[]
    for cost in costs:
        for overlap in (0,.5,1):
            for overhead in (.48,2.4):
                result=scenario(f'postrouter:{cost}:overlap={overlap}:new_overhead_ms={overhead}',
                    lambda p,cost=cost,o=overlap,h=overhead:remote_penalty(p,cost)+o*p['cache']['fill_bytes']['mean']/25e6-h,
                    ['Demand copy replaces zero-copy reads and reuses the baseline admission transfer exactly once.',
                     '25 GB/s is the inherited copy-floor proxy, not measured pure DMA in WS128.',
                     f'Assume {overlap:.0%} of fill-DMA service hidden by resident gate/up; this overlap was NOT measured.',
                     f'Assume {overhead} ms total new synchronization/launch/policy cost; NOT measured.',
                     '0.48 ms charges only 96 launches at 5 us; 2.4 ms is a 50 us/layer sensitivity, not a measured delay.',
                     'No compute/compute overlap; future layer routes are unavailable until their router runs.',
                     'Victims cannot be overwritten while current readers own them; more frequent publication may change hit rates.'])
                postrouter.append(result)
    thresholds=[]
    for k in ('K1a','K1b'):
        cases={(r['format'],r['mode']):r['ms'] for r in w[k]['cases']}
        for fmt in (22,21,20):
            z,v,s=(cases[(fmt,m)] for m in (1,0,3))
            thresholds.append(dict(window=k,format=fmt,host_device_ms=z,resident_device_ms=v,
                streamed_wall_ms=s,estimated_reuses_break_even=(s-v)/(z-v),
                caveat='Streaming wall includes host waits; host/resident fields are kernel event times. Device sums are not end-to-end matched costs.'))
    decision=dict(status='closeout_no_build',threshold_tok_s=26.774,
        rationale='No measured critical-path split or one-card route replay supports a >=10% prediction. Favorable post-router sensitivities exceed it only by assigning unmeasured overlap and synchronization costs.',
        highest_simple_DMA_only_scenario_tok_s=next(s['predicted_class_balanced_tok_s'] for s in a['scenarios'] if s['name'].startswith('hide_only_DMA')),
        postrouter_point_prediction=None,device_quality_gate_ran=False,seal_ready_runtime_design=False,
        runtime_code_written=False,queue_job_created=False,
        ranking_basis='Rank interpretable isolated scenarios; leave unidentifiable mechanisms unranked, not assigned fake speeds.',
        revisit='A matched one-card route trace plus short bounded stage timing separating router readback, cache planning, DMA, publication and resident gate/up, within original memory admission.')
    result=dict(schema='packet58i.lever-models.v1',baseline_tok_s=baseline,
        k1_estimated_remote_penalty_ms_per_missing_expert=costs,
        policy_scenarios=policies,postrouter_sensitivities=postrouter,
        cache_eviction_regression=fits,copy_threshold_proxies=thresholds,decision=decision)
    (HERE/'lever-models.json').write_text(json.dumps(result,indent=2)+'\n')
    a['lever_models']=result
    a['decision']=decision
    rates={s['name']:s['predicted_class_balanced_tok_s'] for s in a['scenarios']}
    a['lever_ranking']=[
        dict(rank=1,lever='overlap_existing_between_position_DMA_only',conditional_tok_s=rates['hide_only_DMA_at_assumed_25_GB_s_no_new_overhead'],
             status='optimistic service-only scenario; below +10%; exact ownership changes needed'),
        dict(rank=2,lever='larger_cache_20.121GB',conditional_tok_s=policies[1]['predicted_class_balanced_tok_s'],
             status='independent-trace ratio proxy; unused allowance must be proved reassignable'),
        dict(rank=3,lever='coalesce_pointer_table_publication',conditional_tok_s_range=[rates['remove_143_table_submissions_at_3.4us'],rates['remove_143_table_submissions_at_5us']],
             status='launch-only estimate, less than +2%'),
        dict(rank=4,lever='two_hit_admission',conditional_tok_s=policies[3]['predicted_class_balanced_tok_s'],
             status='proxy only; overlaps rank3 estimate range, no resolved ordering'),
        dict(rank=5,lever='contiguous_host_expert_triples',conditional_tok_s_range=[rates['merge_three_expert_copies_to_one_at_3.4us'],rates['merge_three_expert_copies_to_one_at_5us']],
             status='launch-only estimate; in-place final layout, no second host copy'),
        dict(rank=6,lever='frequency_speculative_prefetch_one_per_layer_visit',conditional_tok_s=policies[4]['predicted_class_balanced_tok_s'],
             status='rejected tested predictor; extra traffic and pollution'),
        dict(rank=7,lever='LFU',conditional_tok_s=policies[2]['predicted_class_balanced_tok_s'],
             status='rejected tested policy'),
        dict(rank=None,lever='postrouter_demand_copy_overlap_resident_gate_up',conditional_tok_s=None,
             status='unrankable: unknown sparse-miss penalty, gate duration, copy overlap, new synchronization'),
        dict(rank=None,lever='replace_linear_LRU_victim_scan_with_index',conditional_tok_s=None,
             status='unrankable: regression residual is not isolated victim-selection time'),
        dict(rank=None,lever='zero_copy_vs_demand_copy_threshold',conditional_tok_s=None,
             status='K1 scopes differ and do not measure sparse per-layer demand-copy break-even')]
    (HERE/'ATTRIBUTION.json').write_text(json.dumps(a,indent=2)+'\n')
    print(json.dumps(dict(policy_scenarios=[{k:r[k] for k in ('name','predicted_class_balanced_tok_s','gain_pct')} for r in policies],
        costs=costs,fits=fits,postrouter=[{k:r[k] for k in ('name','predicted_class_balanced_tok_s')} for r in postrouter],decision=decision),indent=2))


if __name__=='__main__':
    main()
