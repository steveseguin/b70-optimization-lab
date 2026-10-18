#!/usr/bin/env python3
"""Read completed evidence only. No launches, compilation, model reads or mutation."""
import argparse,hashlib,json,math,statistics
from pathlib import Path
P=Path(__file__).resolve().parent
RULES={
 'schema':'packet58ae.decisions.v1',
 'diagnostic_only':True,
 'required_views':['A0','B0','A1','B1','A2'],
 'tokens_per_request':64,'prompts_per_view':12,
 'overhead_strict_upper_fraction':0.02,'warm_control_drift_upper_fraction':0.02,
 'publication_baseline_ms':1.231,'publication_required_saving_ms':0.7386,
 'publication_remaining_budget_ms':0.4924,
 'rank4_required_net_gain_fraction':0.03,
 'm2_required_tok_s':30.723,'m2_draft_and_cache_costs_required':True,
 'mixed_kernel_duration_is_not_miss_stall':True,
 'unknown_is_not_zero':True,
 'all_tokens_oracle_checked':True,
 'no_device_evidence_status':'pending',
}
def require(ok,why):
    if not ok:raise ValueError(why)
def number(x):
    require(type(x) in (int,float) and math.isfinite(x) and x>=0,'invalid nonnegative measurement');return x
def interval(event):
    a,b=event['start_ns'],event['end_ns'];number(a);number(b)
    require(a>0 and b>=a,'invalid device interval');return (b-a)/1e6
def overhead(views):
    require([v['label'] for v in views]==RULES['required_views'],'complete ordered bracket required')
    require(all(v['exact_oracle'] is True and v['request_count']==12 and v['requested_max_new']==64 and v['cached_tokens']==0 for v in views),'complete exact cold requests required')
    # Same prompts at same positions. A0 is reported as cold-cache warm-up;
    # BOTH measured views must stay below 2% against BOTH warm off controls.
    for v in views:
        require(len(v['request_decode_ms'])==12,'paired prompt coverage')
        for x in v['request_decode_ms']:require(number(x)>0,'zero request time')
    by={v['label']:v for v in views}
    controls=[by[n]['request_decode_ms'] for n in ('A1','A2')]
    drift=statistics.median(abs(a/b-1) for a,b in zip(*controls))
    arms={}
    for label in ('B0','B1'):
        ratios=[statistics.median(a/b-1 for a,b in zip(by[label]['request_decode_ms'],control)) for control in controls]
        arms[label]=dict(worst_paired_overhead_fraction=max(ratios),per_control=ratios,passed=max(ratios)<.02)
    return dict(passed=drift<=.02 and all(x['passed'] for x in arms.values()),warm_control_drift_fraction=drift,arms=arms)
def publication(rows):
    require(rows,'missing arm 1 tokens');totals=[]
    for row in rows:
        require(row['arm']==1 and row['extra_waits']==0,'arm 1 identity')
        pack=number(row['pack_ms']);wait=number(row['publication_wait_ms']);boundary=number(row['publication_boundary_ms'])
        events=[e for e in row['events'] if e['layer']==-1]
        require(len(events)==2*row['publications'],'publication event coverage')
        upload=sum(interval(e) for e in events if e['projection']==0)
        scatter=sum(interval(e) for e in events if e['projection']==1)
        # Host wait OVERLAPS device intervals. Never add it to device service.
        require(boundary+1e-6>=pack+wait,'host partition inconsistent')
        totals.append(dict(pack_ms=pack,h2d_ms=upload,scatter_ms=scatter,host_wait_inclusive_ms=wait,
            boundary_ms=boundary,host_other_ms=max(0,boundary-pack-wait)))
    means={k:statistics.mean(r[k] for r in totals) for k in totals[0]}
    # Clock duration supplies a bound, not a prediction that all of it is removable.
    worth=means['h2d_ms']+means['scatter_ms']>=RULES['publication_required_saving_ms']
    return dict(per_token_mean=means,host_wait_overlaps_device=True,
        decision='reopen sparse-publication feasibility only' if worth else 'keep packet58ac closed under this measured service budget',
        implementation_gate='A complete safe replacement must measure <=0.4924 ms, including host, dependencies and waits; no adoption from this diagnostic.')
def misses(rows):
    require(rows,'missing arm 2 tokens');layers={i:[] for i in range(48)}
    for row in rows:
        require(row['arm']==2 and row['extra_waits']==0,'arm 2 identity')
        require([r['layer'] for r in row['layers']]==list(range(48)),'layer route coverage')
        for r in row['layers']:
            require(r['hits']+r['misses']==10,'all routed slots required')
            if r['layer']!=row['sample_layer']:continue
            events=[e for e in row['events'] if e['layer']==r['layer']]
            require(sorted(e['projection'] for e in events)==[0,1],'both expert events required')
            layers[r['layer']].append(dict(miss_bytes=number(r['miss_bytes']),sampled_expert_tail_ms=sum(interval(e) for e in events)))
    require(all(layers.values()),'all 48 sampled layers required')
    # The current light instrumentation cannot distinguish concurrently scheduled
    # resident/miss subgroups inside one event. Preserve this blocker explicitly.
    return dict(per_layer=[dict(layer=i,miss_bytes_mean=statistics.mean(r['miss_bytes'] for r in data),
        sampled_expert_tail_ms_mean=statistics.mean(r['sampled_expert_tail_ms'] for r in data),miss_stall_ms=None,
        resident_slot_compute_ms=None,overlap_window_ms=None) for i,data in layers.items()],
        measurement_complete=False,rank4_decision='unresolved: need independently timed miss and resident slots',
        m2_decision='keep packet58aa closed: mixed event duration cannot price an M2 miss stall or complete verification cycle')
def analyze(root):
    summary=root/'WSCREEN/run/summary.json'
    if not summary.exists():return dict(passed=False,status='pending',device_evidence_available=False,decisions=RULES)
    doc=json.loads(summary.read_text());views=[];rows={1:[],2:[]}
    import suite_driver as D
    # Re-run the complete bound oracle, request tokens, resets and native identity.
    checked=D.summarize_bracket(root/'WSCREEN/run','max',D.oracle_inputs(),'overlap')
    for view in checked['views']:
        requests=view['requests']
        times=[]
        for req in requests:
            folder=root/'WSCREEN/run/run'/view['label']/req['prompt_id']
            result=json.loads((folder/'result.json').read_text())
            stamps=[r['completed_monotonic'] for r in result['timing_rows']]
            times.append((stamps[-1]-stamps[0])*1000)
            if view['label'] in ('B0','B1'):
                arm=1 if view['label']=='B0' else 2
                tokens=[json.loads(line) for line in (folder/'measure.jsonl').read_text().splitlines()]
                require(len(tokens)==len(req['tokens']),'every measured token required')
                require([t['token_id'] for t in tokens]==req['tokens'],'measurement token identity')
                rows[arm].extend(tokens)
        views.append(dict(label=view['label'],exact_oracle=True,request_count=len(requests),requested_max_new=64,cached_tokens=0,request_decode_ms=times))
    budget=overhead(views)
    if not budget['passed']:return dict(passed=False,status='invalid-instrumentation-overhead',overhead=budget,decisions=RULES)
    return dict(passed=False,status='arm2-unresolved',overhead=budget,arm1=publication(rows[1]),arm2=misses(rows[2]),
        qualification='Diagnostic only; no speed/quality promotion.',decisions=RULES)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('evidence',type=Path,nargs='?',default=P/'evidence/card0-measure-a/combined');args=ap.parse_args()
    try:result=analyze(args.evidence)
    except (ValueError,KeyError,OSError,TypeError) as error:result=dict(passed=False,status='invalid-evidence',reason=str(error))
    print(json.dumps(result,indent=2,allow_nan=False))
if __name__=='__main__':main()
