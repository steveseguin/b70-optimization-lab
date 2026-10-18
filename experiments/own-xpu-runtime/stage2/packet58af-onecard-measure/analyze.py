#!/usr/bin/env python3
"""Read completed evidence only. No launches, compilation, model reads or mutation."""
import argparse,hashlib,json,math,statistics
from pathlib import Path
P=Path(__file__).resolve().parent
RULES={
 'schema':'packet58af.decisions.v1',
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
 'miss_stall_definition':'serialized dependency delay after resident completion, not hardware memory-stall cycles',
 'overlap_definition':'resident service interval available to a future transfer; actual concurrent overlap is zero',
 'rank4_required_saving_ms':1000/29.259764-1000/(29.259764*1.03),
 'partition_order':[1,2],
 'graphs_used':False,
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
        require(events==row['events'] and [(e['projection'],e.get('partition',0)) for e in events]==[(0,0),(1,0)]*row['publications'],'ordered upload/scatter pairs required')
        require(all(b['start_ns']>=a['end_ns'] for a,b in zip(events,events[1:])),'publication dependency order')
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
            require(all(type(r[k]) is int and r[k]>=0 for k in ('hits','misses','hit_bytes','miss_bytes')),'integer nonnegative route counters')
            require(r['hits']+r['misses']==10,'all routed slots required')
            if r['layer']!=row['sample_layer']:continue
            events=[e for e in row['events'] if e['layer']==r['layer']]
            require([(e['projection'],e.get('partition')) for e in events]==[(0,1),(0,2),(1,1),(1,2)],'both separate expert partitions required')
            resident=miss=stall=gap=noop=0.0
            for hit,host in (events[:2],events[2:]):
                hd,md=interval(hit),interval(host)
                require(host['start_ns']>=hit['end_ns'],'serial partition event order')
                idle=(host['start_ns']-hit['end_ns'])/1e6
                gap+=idle
                resident+=hd if r['hits'] else 0
                miss+=md if r['misses'] else 0
                # Inclusive delay after resident finishes, before dependent work
                # can proceed. It includes launch gap and miss arithmetic.
                stall+=(md+idle) if r['misses'] else 0
                noop+=(hd if not r['hits'] else 0)+(md if not r['misses'] else 0)
            require(events[2]['start_ns']>=events[1]['end_ns'],'gate before down')
            number(r['hit_bytes']);number(r['miss_bytes'])
            require((r['miss_bytes']>0)==(r['misses']>0),'miss byte/count consistency')
            require((r['hit_bytes']>0)==(r['hits']>0),'resident byte/count consistency')
            layers[r['layer']].append(dict(miss_bytes=r['miss_bytes'],miss_kernel_ms=miss,
                miss_stall_ms=stall,resident_slot_compute_ms=resident,overlap_window_ms=resident,
                interlaunch_gap_ms=gap,no_op_partition_ms=noop,actual_concurrent_overlap_ms=0.0))
    require(all(layers.values()),'all 48 sampled layers required')
    per_layer=[dict(layer=i,samples=len(data),**{k:statistics.mean(r[k] for r in data) for k in data[0]}) for i,data in layers.items()]
    budget=sum(r['miss_kernel_ms'] for r in per_layer)
    return dict(per_layer=per_layer,measurement_complete=True,
        sampled_layer_service_sum_ms=budget,
        sum_is_sampling_estimate_not_measured_token_latency=True,
        miss_stall_definition=RULES['miss_stall_definition'],overlap_definition=RULES['overlap_definition'],
        rank4_decision=('reopen bounded sparse-transfer feasibility; measure all transfer, compute, dependency and cache costs before requiring >3% net gain'
            if budget>RULES['rank4_required_saving_ms'] else 'keep sparse-transfer build closed under the sampled service budget'),
        m2_decision='keep packet58aa closed until a complete verification cycle including draft, miss, rejection, feedback and cache costs supports >30.723 tok/s',
        m2_complete_cycle_ms=None,promotable=False)
def analyze(root):
    summary=root/'WSCREEN/run/summary.json'
    if not summary.exists():return dict(passed=False,status='pending',device_evidence_available=False,decisions=RULES)
    doc=json.loads(summary.read_text());views=[];rows={1:[],2:[]}
    import suite_driver as D
    import window as W
    queue=json.loads((root/'queue.json').read_text())
    require(queue.get('passed') is True and queue.get('completed')==['K1a','K1b','WSCREEN'],'completed combined job required')
    receipt=json.loads((root/'WSCREEN/window.json').read_text())
    require(receipt.get('passed') is True and receipt.get('device_executed') is True and receipt.get('stop_reasons')==[], 'clean device receipt required')
    require(receipt['build_receipt_sha256']==D.sha(P/'build-receipt.json'),'measurement build identity')
    W.A.verify(receipt)
    closure={'summary.json','kernel-before.jsonl','kernel-window.jsonl'}
    closure|={str(p.relative_to(root/'WSCREEN')) for p in (root/'WSCREEN/run').rglob('*') if p.is_file()}
    require(set(receipt.get('native_files',{}))==closure,'complete measurement file closure required')
    W.verify_files(root/'WSCREEN',receipt['native_files'])
    require(receipt.get('child_still_running') is False and receipt.get('qualifying') is False,'drained diagnostic required')
    for leaf in ('kernel-before.jsonl','kernel-window.jsonl'):
        require(not W.S.FAULT.search((root/'WSCREEN'/leaf).read_text()),'kernel fault invalidates measurement')
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
                require([t['generated_index'] for t in tokens]==list(range(1,len(tokens)+1)),'measurement token order')
                require(all(t['schema']=='packet58af.token.v1' and t['sample_layer']==(t['generated_index']-1)%48 for t in tokens),'measurement schema/sampling identity')
                rows[arm].extend(tokens)
        views.append(dict(label=view['label'],exact_oracle=True,request_count=len(requests),requested_max_new=64,cached_tokens=0,request_decode_ms=times))
    budget=overhead(views)
    if not budget['passed']:return dict(passed=False,status='invalid-instrumentation-overhead',overhead=budget,decisions=RULES)
    return dict(passed=True,status='measurement-complete',overhead=budget,arm1=publication(rows[1]),arm2=misses(rows[2]),
        qualification='Diagnostic only; no speed/quality promotion.',decisions=RULES)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('evidence',type=Path,nargs='?',default=P/'evidence/card0-measure-a/combined');args=ap.parse_args()
    try:result=analyze(args.evidence)
    except (ValueError,KeyError,OSError,TypeError) as error:result=dict(passed=False,status='invalid-evidence',reason=str(error))
    print(json.dumps(result,indent=2,allow_nan=False))
if __name__=='__main__':main()
