"""Fail-closed reader for observed whole-token census; no sampling extrapolation."""
import argparse,collections,hashlib,json,math,statistics
from pathlib import Path
P=Path(__file__).resolve().parent
RECORD_TPS=30.396
PERIOD_MS=1000/RECORD_TPS
CLOSE_MS=.670
BRIEF_MS=1.0

def require(ok,why):
    if not ok:raise ValueError(why)
def read(p):return json.loads(Path(p).read_text())
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def gain(ms):
    require(math.isfinite(ms) and 0<=ms<PERIOD_MS,'saving outside record period')
    return 100*(PERIOD_MS/(PERIOD_MS-ms)-1)
def distribution(values):
    require(bool(values),'empty distribution')
    s=sorted(values)
    return dict(count=len(s),minimum=s[0],maximum=s[-1],mean=statistics.mean(s),median=statistics.median(s),
                p10=s[(len(s)-1)//10],p90=s[9*(len(s)-1)//10],
                histogram={str(k):v for k,v in sorted(collections.Counter(s).items())})
def duration(event):return (event['end_ns']-event['start_ns'])/1e6

def token(row):
    require(row.get('schema')=='packet58ai.token.v1' and row.get('arm') in (1,2),'census identity')
    require(type(row.get('position')) is int and row['position']>=0,'position')
    require(type(row.get('generated_index')) is int and row['generated_index']>=0,'generated index')
    require(row.get('extra_waits')==0,'new token wait')
    require([l.get('layer') for l in row.get('layers',[])]==list(range(48)),'48 layers required')
    events=collections.defaultdict(dict)
    for e in row.get('events',[]):
        require(type(e.get('start_ns')) is int and type(e.get('end_ns')) is int and 0<e['start_ns']<e['end_ns'],'invalid event endpoints')
        require(e.get('layer') in range(48),'event layer')
        key=(e.get('projection'),e.get('partition'))
        require(key not in events[e['layer']],'duplicate event')
        events[e['layer']][key]=e
    out=[]
    for l in row['layers']:
        for key in ('hits','misses','hit_bytes','miss_bytes'):
            require(type(l.get(key)) is int and l[key]>=0,'invalid count/bytes')
        require(l['hits']+l['misses']==10,'ten routed slots required')
        for count,ids,byteskey in [('hits','hit_ids','hit_bytes'),('misses','miss_ids','miss_bytes')]:
            v=l.get(ids);require(isinstance(v,list) and len(v)==l[count] and len(set(v))==len(v),'route IDs/count mismatch')
            require(all(type(x) is int and 0<=x<512 for x in v),'expert ID range')
            require(bool(l[byteskey])==bool(l[count]),'byte/count mismatch')
        require(not set(l['hit_ids'])&set(l['miss_ids']),'resident/miss overlap')
        es=events[l['layer']];split=row['arm']==2
        keys={(2,0),(0,1),(0,2),(1,1),(1,2)} if split else {(2,0),(0,0),(1,0)}
        require(set(es)==keys,'event coverage differs')
        ordered=[es[k] for k in ([(2,0),(0,1),(0,2),(1,1),(1,2)] if split else [(2,0),(0,0),(1,0)])]
        require(all(a['end_ns']<=b['start_ns'] for a,b in zip(ordered,ordered[1:])),'events not serial')
        base=dict(layer=l['layer'],hits=l['hits'],misses=l['misses'],miss_ids=l['miss_ids'],hit_ids=l['hit_ids'],
                  miss_bytes=l['miss_bytes'],hit_bytes=l['hit_bytes'],
                  router_to_first_expert_ms=(ordered[1]['start_ns']-ordered[0]['end_ns'])/1e6)
        if split:
            base.update(miss_kernel_ms=sum(duration(es[k]) for k in [(0,2),(1,2)]) if l['misses'] else 0.,
                        resident_kernel_ms=sum(duration(es[k]) for k in [(0,1),(1,1)]) if l['hits'] else 0.,
                        empty_partition_ms=sum(duration(es[(proj,part)]) for proj in (0,1) for part,count in [(1,l['hits']),(2,l['misses'])] if not count),
                        resident_compute_while_miss_waits_ms=sum(duration(es[(proj,1)]) for proj in (0,1)) if l['hits'] and l['misses'] else 0.,
                        actual_concurrent_compute_ms=0.)
        else:
            service=sum(duration(es[(proj,0)]) for proj in (0,1))
            # Erase the entire miss-containing launch, including indispensable resident
            # arithmetic: deliberately generous ceiling on recoverable expert service.
            base.update(mixed_kernel_ms=service,miss_containing_kernel_ceiling_ms=service if l['misses'] else 0.)
        out.append(base)
    return out

def paired(unsplit,split):
    require(len(unsplit)==len(split)>0,'paired census positions')
    rows=[];layer_rows=collections.defaultdict(list);demand_differences=[]
    for a,b in zip(unsplit,split):
        require(a['arm']==1 and b['arm']==2,'paired arm order')
        require(all(a.get(k)==b.get(k) for k in ('position','generated_index','token_id')),'position/output mismatch')
        aa,bb=token(a),token(b)
        for x,y in zip(aa,bb):
            if any(x[k]!=y[k] for k in ['hits','misses','hit_ids','miss_ids','hit_bytes','miss_bytes']):
                demand_differences.append(dict(position=a['position'],generated_index=a['generated_index'],layer=x['layer'],unsplit_misses=x['misses'],split_misses=y['misses']))
        # Prefill gets its own evidence, never folded into decode or rank-4 decision.
        if a['generated_index']<2:continue
        metrics=dict(misses=sum(x['misses'] for x in aa),
            unsplit_upper_bound_ms=sum(x['miss_containing_kernel_ceiling_ms'] for x in aa),
            miss_kernel_ms=sum(x['miss_kernel_ms'] for x in bb),
            resident_kernel_ms=sum(x['resident_kernel_ms'] for x in bb),
            router_to_first_expert_ms=sum(x['router_to_first_expert_ms'] for x in aa),
            split_overlap_available_ms=sum(x['resident_compute_while_miss_waits_ms'] for x in bb))
        metrics.update(position=a['position'],generated_index=a['generated_index'],token_id=a['token_id'])
        rows.append(metrics)
        for x,y in zip(aa,bb):layer_rows[x['layer']].append(dict(x,**y))
    require(rows,'no decode census')
    primary=[r for r in rows if r['generated_index']<=100]
    require(primary,'first-100 interval census required')
    upper=statistics.mean(r['unsplit_upper_bound_ms'] for r in primary)
    split_ceiling=statistics.mean(r['miss_kernel_ms'] for r in rows)
    # Never close a lever using a perturbed split alone. The bound is ordinary
    # unsplit event service, with resident arithmetic deliberately overcounted.
    decision='brief-transfer-mechanism' if upper>=BRIEF_MS else 'close-rank-4' if upper<CLOSE_MS else 'between-thresholds-measure-tighter-bound'
    return dict(passed=True,diagnostic_only=True,promotable=False,record_tok_s=RECORD_TPS,record_ms_per_token=PERIOD_MS,
        upper_bound_scope='generated positions 2..100 (the first 99 inter-token intervals), pooled observed tokens',threshold_ms=CLOSE_MS,threshold_gain_percent=gain(CLOSE_MS),exact_two_percent_saving_ms=PERIOD_MS-PERIOD_MS/1.02,
        decision=decision,upper_bound_ms_per_token=upper,
        upper_bound_gain_percent=gain(upper) if upper<PERIOD_MS else None,
        upper_bound_definition='erase complete original mixed kernels only in layers with a routed miss; includes resident and miss arithmetic; excludes router gaps',
        split_miss_service_ceiling_ms_per_token=split_ceiling,
        split_ceiling_is_original_schedule_bound=False,
        counts=distribution([r['misses'] for r in rows]),cache_demand_identical=not demand_differences,cache_demand_differences=demand_differences,
        cross_schedule_cost_subtraction_allowed=False,
        means={k:statistics.mean(r[k] for r in rows) for k in ['miss_kernel_ms','resident_kernel_ms','router_to_first_expert_ms','split_overlap_available_ms']},
        actual_concurrent_overlap_ms=0.,
        overlap_definition='original router-ready-to-first-expert window; split resident service is a separate potential transfer window under changed scheduling',
        per_token=rows,per_layer=[dict(layer=i,samples=len(v),mean_misses=statistics.mean(x['misses'] for x in v),
            miss_kernel_ms=statistics.mean(x['miss_kernel_ms'] for x in v),resident_kernel_ms=statistics.mean(x['resident_kernel_ms'] for x in v)) for i,v in sorted(layer_rows.items())])

def overhead(views):
    require(set(views)=={'A0','B0','A1','B1','A2'},'five views')
    require(all(len(v)==12 and all(math.isfinite(x) and x>0 for x in v) for v in views.values()),'12 valid durations/view')
    return dict(warm_control_drift_percent=100*(max(statistics.median(views[x]) for x in ['A1','A2'])/min(statistics.median(views[x]) for x in ['A1','A2'])-1),
        percent_by_instrument_and_control={b:{a:100*statistics.median(x/y-1 for x,y in zip(views[b],views[a])) for a in ['A1','A2']} for b in ['B0','B1']},
        A0_exact_but_cold=True,baseline='dormant hooks in same executable; parent executable overhead unmeasured')

def native_closure(folder,receipt):
    folder=Path(folder)
    expected={'summary.json','kernel-before.jsonl','kernel-window.jsonl'}
    expected.update(str(p.relative_to(folder)) for p in (folder/'run').rglob('*') if p.is_file())
    require(set(receipt.get('native_files',{}))==expected,'complete native census closure required')
    require({'run/receipt.json','run/summary.json','run/run/receipt.json'}<=expected,'native receipts missing')

def first_request(folder):
    """Validate the smoke's own completed request, with no elapsed-time gate."""
    folder=Path(folder)
    result=read(folder/'result.json')
    require(result.get('passed') is True and result.get('tokens'),'first request output missing')
    require(result.get('arithmetic')=='iq3-p49-split32-v1','first request arithmetic')
    with (folder/'measure.jsonl').open() as stream:
        rows=[json.loads(line) for line in stream if line.strip()]
    require(rows,'first request census stream empty')
    require(all(r.get('arm')==2 for r in rows),'first request split stream required')
    generated=[r for r in rows if r.get('generated_index',0)>0]
    require([r['token_id'] for r in generated]==result['tokens'],'first request output binding')
    require([r['generated_index'] for r in generated]==list(range(1,len(result['tokens'])+1)),
            'first request generated coverage')
    require([r['position'] for r in rows]==list(range(len(rows))),'first request position coverage')
    layers=[layer for row in rows for layer in token(row)]
    streams={key:[layer[key] for layer in layers] for key in
             ('misses','miss_kernel_ms','resident_kernel_ms','router_to_first_expert_ms',
              'resident_compute_while_miss_waits_ms')}
    require(all(values and all(math.isfinite(v) and v>=0 for v in values)
                for values in streams.values()),'missing or empty first request streams')
    return dict(passed=True,diagnostic_only=True,request=str(folder),
                result_sha256=sha(folder/'result.json'),measure_sha256=sha(folder/'measure.jsonl'),
                streams={k:len(v) for k,v in streams.items()},wall_deadline_seconds=None)

def analyze(root):
    root=Path(root)
    if not (root/'queue.json').exists():return dict(passed=False,status='pending-device',device_executed=False,upper_bound_ms_per_token=None,decision=None)
    import suite_driver as D,window as W
    queue=read(root/'queue.json');require(queue.get('passed') is True and queue.get('completed')==['K1a','K1b','WSCREEN'],'completed single load required')
    receipt=read(root/'WSCREEN/window.json')
    require(receipt.get('passed') is True and receipt.get('device_executed') is True and receipt.get('child_still_running') is False and receipt.get('stop_reasons')==[],'clean drained census required')
    require(receipt['build_receipt_sha256']==sha(P/'build-receipt.json'),'build identity')
    native_closure(root/'WSCREEN',receipt)
    W.A.verify(receipt);W.verify_files(root/'WSCREEN',receipt['native_files'])
    for leaf in ['kernel-before.jsonl','kernel-window.jsonl']:require(not W.S.FAULT.search((root/'WSCREEN'/leaf).read_text()),'kernel fault')
    checked=D.summarize_bracket(root/'WSCREEN/run','p60fusion',D.oracle_inputs(),'overlap')
    times={};data={};chain=read(P/'lineage/record-chain-outputs.json')
    for view in checked['views']:
        label=view['label'];times[label]=[];data[label]=[]
        for req in view['requests']:
            require(req['tokens']==chain['tokens'][req['prompt_id']],'packet58ad chain token identity')
            folder=root/'WSCREEN/run/run'/label/req['prompt_id'];result=read(folder/'result.json')
            stamps=[r['completed_monotonic'] for r in result['timing_rows']]
            times[label].append((stamps[-1]-stamps[0])*1000)
            if label in ['B0','B1']:
                with (folder/'measure.jsonl').open() as stream:tokens=[json.loads(line) for line in stream]
                generated=[t for t in tokens if t['generated_index']>0]
                require([t['token_id'] for t in generated]==req['tokens'],'census output binding')
                require([t['generated_index'] for t in generated]==list(range(1,len(req['tokens'])+1)),'generated coverage')
                require([t['position'] for t in tokens]==list(range(len(tokens))),'all input and generated positions')
                for row in tokens:token(row)
                data[label].append(tokens)
    reports=[paired(a,b) for a,b in zip(data['B0'],data['B1'])]
    # Aggregate complete observed tokens, never extrapolate from sampled layers.
    result=paired([r for group in data['B0'] for r in group],[r for group in data['B1'] for r in group])
    result.update(status='measured-diagnostic',device_executed=True,overhead=overhead(times),
        exact_packet58ad_chain=True,exact_oracle=True,acceptance='target-only; no speculative acceptance in either line',
        per_prompt=[dict(prompt_id=p,upper_bound_ms_per_token=r['upper_bound_ms_per_token']) for p,r in zip(D.CHECK.PROMPT_IDS,reports)])
    o=result['overhead']
    result['measurement_stability_gate']=dict(passed=o['warm_control_drift_percent']<=3 and all(abs(v)<=2 for v in o['percent_by_instrument_and_control']['B0'].values()),
        max_control_drift_percent=3,max_unsplit_instrumentation_overhead_percent=2)
    result['threshold_decision_before_stability_gate']=result['decision']
    if not result['measurement_stability_gate']['passed']:
        result['decision']='measurement-overhead-or-drift-blocks-rank4'
    if result['decision']=='brief-transfer-mechanism':
        result['transfer_brief']='After the router, identify missing expert IDs from the published table; start byte-exact demand copies into bounded staging while independent resident slots compute; fence each missing projection before its consumer, preserve the reduction/output order and two-phase pointer generations. Charge routing, submissions, copies, waits, staging and cache effects. This ceiling includes unavoidable arithmetic and does not forecast a speedup. Packet125 pipeline gains are not counted.'
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--output',type=Path);a=ap.parse_args()
    result=analyze(a.root);text=json.dumps(result,indent=2,allow_nan=False)+'\n'
    if a.output:a.output.write_text(text)
    else:print(text,end='')
if __name__=='__main__':main()
