#!/usr/bin/env python3
"""Read packet58y receipts, recheck exactness, and rank bounded next levers.

No subprocess, device API, service, queue mutation or model payload access.
Only the explicit report output is written. CPU limits are installed in main.
"""
import argparse,hashlib,json,math,os,resource,shutil,statistics,sys
from decimal import Decimal
from pathlib import Path
P=Path(__file__).resolve().parents[1]
ROOT=P.parents[3]
sys.path.insert(0,str(P))
from attribution_schema import validate,PHASES,CAUSES,CLASSES,COUNTERS
GATE=3.0
LEVER_NAMES={
 'prepare':'Token lookup, preparation and input upload',
 'enqueue':'Host command submission',
 'publication':'Cache publication and fill submission at the safe boundary',
 'planning':'Overlapped CPU cache planning',
 'readbacks':'Token/route readbacks and cache bookkeeping',
 'compute_tail':'Compute-tail wait, including zero-copy miss kernels',
}

class Evidence:
    def __init__(self):self.pins={}
    def raw(self,path):
        path=Path(path);require(path.stat().st_size<=64*1024**2,'oversized evidence input')
        raw=path.read_bytes();self.pins[str(path.relative_to(ROOT))]=hashlib.sha256(raw).hexdigest();return raw
    def js(self,path):return json.loads(self.raw(path))
    def lines(self,path):return [json.loads(x) for x in self.raw(path).splitlines()]
    def verify_files(self,root,pins):
        require(isinstance(pins,dict) and pins,'missing file closure')
        for name,digest in pins.items():
            rel=Path(name);require(not rel.is_absolute() and '..' not in rel.parts,'unsafe evidence path')
            path=root/rel;require(path.resolve().is_relative_to(root.resolve()),'evidence path escapes closure')
            require(hashlib.sha256(self.raw(path)).hexdigest()==digest,'changed evidence '+str(path))

def require(good,message):
    if not good:raise ValueError(message)

def balanced(rows,key):
    classes={}
    for row in rows:classes.setdefault(row['prompt_class'],[]).append(row[key])
    require(len(classes)>=5,'varied complete prompt classes required')
    medians={name:statistics.median(values) for name,values in classes.items()}
    return dict(median=statistics.median(medians.values()),class_medians=medians,
                all_prompt_median=statistics.median(row[key] for row in rows))

def removed(row,lever):
    h={k:Decimal(str(v)) for k,v in row['host_exclusive_ms'].items()}
    w={k:Decimal(str(v)) for k,v in row['host_wait_ms'].items()}
    return {
      'prepare':h['prepare']+w['input_upload'],
      'enqueue':h['enqueue'],
      'publication':h['cache_boundary']+w['table_publication'],
      'planning':h['cache_plan'],
      'readbacks':h['readbacks']+h['cache_after']+w['readbacks'],
      'compute_tail':w['compute_including_zero_copy_miss'],
    }[lever]

def rank_levers(prompts):
    baseline=balanced([dict(prompt_class=p['prompt_class'],rate=Decimal(99000)/Decimal(str(p['interval_ms']))) for p in prompts],'rate')['median'];ranked=[]
    for lever,title in LEVER_NAMES.items():
        projected=[];savings=[]
        for prompt in prompts:
            saving=sum(removed(row,lever) for row in prompt['selected'])
            # Removing all recorded host spans is an optimistic bound, not a
            # causal prediction; host enqueue/planning overlaps device work.
            duration=Decimal(str(prompt['interval_ms']))
            require(0<=saving<duration,'bucket exceeds actual 99-interval span')
            projected.append(dict(prompt_class=prompt['prompt_class'],rate=99_000/(duration-saving)))
            savings.append(saving/99)
        rate=balanced(projected,'rate')['median'];gain=100*(rate/baseline-1)
        ranked.append(dict(lever=lever,label=title,perfect_removal_bound_gain_pct=float(gain),
            mean_bucket_ms=float(statistics.mean(savings)),perfect_removal_bound_tok_s=float(rate),
            decision='kill_below_3pct' if rate<baseline*Decimal('1.03') else 'needs_causal_test',
            supported_projection_gain_pct=None,passes_implementation_gate=False,
            caveat='optimistic upper bound only; no proof these spans are removable critical-path time'))
    ranked.sort(key=lambda row:row['perfect_removal_bound_gain_pct'],reverse=True)
    return ranked

def window(e,root,build_sha):
    import onecard_admission as A
    row=e.js(root/'window.json')
    require(row.get('passed') is True and row.get('device_executed') is True and row.get('child_still_running') is False and row.get('stop_reasons')==[],'window incomplete or failed')
    require(row['card']==0 and row['gpu_count']==1 and row['context']==4096 and row['build_receipt_sha256']==build_sha,'window identity changed')
    A.verify(row);e.verify_files(root,row['native_files']);return row

def describe_top_items(ranking,capacity):
    return dict(larger_cache='Not measured by this diagnostic; coordinator reviews independent capacity evidence.',
        miss_path='Not independently ranked: zero-copy miss kernels share the compute queue. Counts and logical bytes are measured; their removable stall time is unknown.',
        larger_cache_and_miss_path_both_remain_top='not established',
        largest_host_bound=ranking[0]['lever'],
        next_action=('Use the largest surviving bound to design a matched exact change; no implementation is admitted solely by a perfect-removal bound.'
                     if any(r['decision']=='needs_causal_test' for r in ranking) else
                     'All isolated host bounds are below +3%; investigate a larger mechanism without extending these isolated levers.'))

def verify_hold(batch):
    pause=batch['pause'];start=batch['lanequeue_start']
    require(all(type(pause.get(k)) is int and pause[k]>=0 for k in ('device','inode','mtime_ns','ctime_ns')),'invalid stored pause identity')
    event=start['event']
    require(event.get('event')=='START' and event.get('lane')=='A' and event.get('name')=='packet58y-attrib-A','wrong stored START')
    text=pause['text'].lower()
    require(('one-card' in text or 'one card' in text) and ('whole-host' in text or 'whole host' in text) and 'hold' in text,'invalid hold text')
    require(hashlib.sha256(pause['text'].encode()).hexdigest()==pause['sha256'],'hold text hash changed')
    from datetime import datetime
    stamp=datetime.fromisoformat(event['utc'].replace('Z','+00:00'))
    ns=int(stamp.timestamp())*1_000_000_000+stamp.microsecond*1000
    require(ns==start['started_utc_ns'] and pause['mtime_ns']<ns and pause['ctime_ns']<ns,'hold did not predate START')
    return ns

def analyze():
    import suite_driver as D
    import window as W
    e=Evidence();run=P/'evidence/card0-attribution-b/attrib'
    if not (run/'queue.json').is_file():
        return dict(schema='packet58y.analysis.v1',status='pending_device_evidence',passed=False,
            device_executed=False,analysis_only=True,kill_gate_gain_pct=GATE,
            required_first_evidence=str(run/'queue.json'),measured_split=None,ranking=None,
            larger_cache_and_miss_path_both_remain_top='not established; packet58y device evidence is pending',
            no_measurements_invented=True,submission_eligible=False)
    W.build_gate();ready=e.js(P/'READY-FOR-DEVICE.json')
    require(ready['build_receipt_sha256']==hashlib.sha256(e.raw(P/'build-receipt.json')).hexdigest(),'ready/build binding changed')
    queue=e.js(run/'queue.json')
    require(queue.get('passed') is True and queue.get('completed')==['K1a','K1b','WSCREEN'] and queue.get('running') is None,'diagnostic queue incomplete')
    batch=queue['batch_admission'];require(batch.get('passed') is True and batch.get('same_hold_required') is True and batch.get('standalone_hold_allowed') is False,'same-hold evidence missing')
    hold_start=verify_hold(batch)
    proof=window(e,run/'WSCREEN',ready['build_receipt_sha256']);require(proof['boot_id']==batch['boot_id'],'batch boot changed')
    require(type(proof.get('started_utc_ns')) is int and hold_start<=proof['started_utc_ns'],'diagnostic precedes job START')
    manifest=D.oracle_inputs()
    recomputed=D.summarize_bracket(run/'WSCREEN/run','attrib',manifest)
    require(recomputed==e.js(run/'WSCREEN/run/summary.json'),'stored summary differs from actual oracle/trace recheck')
    require(recomputed['attribution_passed'] is True,'trace gate did not pass')
    requests=recomputed['views'][0]['requests'];prompts=[];all_generated=[]
    for request in requests:
        folder=run/'WSCREEN/run/run/D0'/request['prompt_id'];result=e.js(folder/'result.json')
        trace=e.lines(folder/'attribution.jsonl');generated=[r for r in trace if r['generated_index']>0]
        require(len(generated)>=100,'complete 100-event diagnostic metric required; early completion reported without ranking')
        selected=generated[1:100]
        require(len(selected)==99,'99 interval coverage')
        stamps=[r['completed_monotonic'] for r in result['timing_rows']]
        require(all(math.isfinite(x) for x in stamps) and all(b>a for a,b in zip(stamps,stamps[1:])),'invalid event timestamps')
        interval=(stamps[99]-stamps[0])*1000;rate=99_000/interval
        prompt=dict(prompt_id=request['prompt_id'],prompt_class=request['prompt_class'],rate=rate,interval_ms=interval,
            event_count=100,interval_count=99,numerator=99,start_event=1,end_event=100,
            start_monotonic=stamps[0],end_monotonic=stamps[99],selected=selected,
            output_tokens=len(generated),cold_first_request=len(prompts)==0,
            token_span_sum_ms=sum(r['wall_ms'] for r in selected),first_token=generated[0])
        prompt['interval_minus_traced_spans_ms']=interval-prompt['token_span_sum_ms']
        prompts.append(prompt);all_generated.extend(generated)
    require(len(prompts)==12,'complete twelve-prompt set required')
    primary=balanced(prompts,'rate')
    require(math.isclose(primary['median'],recomputed['views'][0]['class_balanced_tok_s_1_100_intervals_after_ttft']['median'],rel_tol=1e-9),'metric differs from sealed suite')
    selected=[r for p in prompts for r in p['selected']]
    def split(rows):
        return dict(tokens=len(rows),mean_token_wall_ms=statistics.mean(r['wall_ms'] for r in rows),
            host_exclusive_ms={k:statistics.mean(r['host_exclusive_ms'][k] for r in rows) for k in PHASES},
            host_wait_ms={k:statistics.mean(r['host_wait_ms'][k] for r in rows) for k in CAUSES},
            host_wait_calls={k:statistics.mean(r['host_wait_calls'][k] for r in rows) for k in CAUSES},
            enqueue_class_ms={k:statistics.mean(r['enqueue_class_ms'][i] for r in rows) for i,k in enumerate(CLASSES)},
            counters_per_token={k:statistics.mean(r[k] for r in rows) for k in COUNTERS},
            residual_ms=statistics.mean(r['residual_ms'] for r in rows),
            device_class_ms={k:None for k in CLASSES},zero_copy_miss_stall_ms=None)
    ranking=rank_levers(prompts);capacity=dict(decision='not_measured_by_this_diagnostic',passes_3pct_screen_gate=False)
    # Keep outputs bounded: raw rows remain hash-bound in their original files.
    per_prompt=[{k:v for k,v in row.items() if k!='selected'} for row in prompts]
    return dict(schema='packet58y.analysis.v1',status='complete_diagnostic',passed=True,device_executed=False,analysis_only=True,
        arithmetic=D.ARITHMETIC,kv_dtype='BF16',cache_maintenance='overlap',cache_bytes=18_000_000_000,
        build_receipt_sha256=ready['build_receipt_sha256'],oracle_completion_sha256=recomputed['views'][0]['oracle_completion_sha256'],
        primary_metric=primary,metric_definition='median of class medians; 99 intervals between generated events 1 and 100',
        measured_split=split(selected),all_decode_split=split(all_generated),per_prompt=per_prompt,
        kill_gate_gain_pct=GATE,ranking=ranking,larger_cache=capacity,priority_assessment=describe_top_items(ranking,capacity),
        instrumentation_overhead_gate='not measured with a matched uninstrumented control',
        independent_miss_cost_known=False,implementation_gate_passed=False,
        caveats=['Diagnostic attribution; no new speed headline','Host spans may overlap device execution; removal bounds are not predictions',
                 'Logical byte counts are not PCIe traffic','Cold first prompt retained; no warmed-prompt filtering',
                 'No valid device class timestamps or isolated miss stall','One load and 128-token cap do not satisfy promotion gates'],
        sources=e.pins,submission_eligible=False)

def markdown(row):
    if row['status']=='refused_incomplete_or_invalid_evidence':
        return '# Packet58y analysis: evidence refused\n\nNo current ranking is valid.\n\nReason: '+row['error']+'\n'
    if row['status']=='pending_device_evidence':
        return '# Packet58y analysis: device evidence pending\n\nNo measured split or lever ranking exists yet. Run the coordinator-owned\n58y diagnostic inside an existing continuous one-card whole-host hold, then\nrerun analyze.py. The +3% gate is preregistered; no data is invented.\n'
    text=['# Packet58y measured diagnostic split','',
          f"The class-balanced diagnostic rate is {row['primary_metric']['median']:.4f} tok/s. This is not a record.",
          'The first cold prompt remains included. Host spans are descriptive; the table below gives optimistic removal bounds, not promised gains.','',
          '| Lever | Mean bucket ms/token | Perfect-removal gain bound | Decision |',
          '| --- | ---: | ---: | --- |']
    for r in row['ranking']:text.append(f"| {r['label']} | {r['mean_bucket_ms']:.4f} | {r['perfect_removal_bound_gain_pct']:.2f}% | {r['decision']} |")
    text+=['',row['priority_assessment']['larger_cache'],'',row['priority_assessment']['miss_path'],'',
           'Device-class times and isolated miss-stall time are unavailable. No implementation passes solely on these upper bounds. The full numeric split and file hashes are in report.json.','']
    return '\n'.join(text)

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,default=P/'analysis/report.json');args=ap.parse_args(argv)
    require(os.getpriority(os.PRIO_PROCESS,0)==19,'CPU analysis requires nice19')
    require(set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32)),'CPU analysis affinity')
    require(shutil.disk_usage('/').free>=25_000_000_000,'root below 25 GB')
    output=args.output.resolve();require(output.is_relative_to(P/'analysis'),'report must stay in analysis/')
    try:row=analyze()
    except (ValueError,KeyError,OSError,AssertionError) as error:
        row=dict(schema='packet58y.analysis.v1',status='refused_incomplete_or_invalid_evidence',passed=False,device_executed=False,
                 analysis_only=True,error=str(error),ranking=None,kill_gate_gain_pct=GATE,submission_eligible=False)
        output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(row,indent=2)+'\n')
        output.with_suffix('.md').write_text(markdown(row))
        print(json.dumps(row));return 1
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(row,indent=2)+'\n')
    output.with_suffix('.md').write_text(markdown(row));print(json.dumps(dict(status=row['status'],passed=row['passed'],report=str(output))))
    return 0
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3));raise SystemExit(main())
