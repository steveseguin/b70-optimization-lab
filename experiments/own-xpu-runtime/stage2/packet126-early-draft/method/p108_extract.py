#!/usr/bin/env python3
"""Read existing receipts only. Never launches device/runtime code.

nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet108-attribution/extract.py --output /tmp/p108-attribution-check.json </dev/null
"""
import argparse, hashlib, importlib.util, json, resource, statistics as st
from collections import defaultdict
from pathlib import Path
resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
ROOT=Path(__file__).resolve().parents[4]
ST=ROOT/'experiments/own-xpu-runtime/stage2'
SH=ST/'screen/v4-lanes/evidence'
SOURCES={}
def read(p):
    p=Path(p); b=p.read_bytes(); SOURCES[str(p.relative_to(ROOT))]={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)};return b
def load(p):return json.loads(read(p))
mp=ST/'packet85-critical-path/model.py'; read(mp)
spec=importlib.util.spec_from_file_location('p85_model',mp);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def union_ms(trace,rank,a,b):
    spans=sorted((max(a,t['rank_received']),min(b,t['rank_completed'])) for t in trace if t['rank']==rank and t['rank_completed']>a and t['rank_received']<b)
    total=0;last=a
    for x,y in spans:
        total+=max(0,y-max(x,last));last=max(last,y)
    return total*1000
def run(p):
    d=load(p);requests=d.get('requests',[])
    if not requests:
        requests=[load(q) for q in sorted(p.parent.glob('repeat-1/*/receipt.json'))]
    rows=[];census=[];host=defaultdict(list)
    for r in requests:
        rr=m.intervals(r); stamps=r['generated_token_completion_timestamps']
        for i,x in enumerate(rr):
            for rank in (0,1):
                busy=union_ms(r['rank_trace'],rank,stamps[i],stamps[i+1]);x[f'rank{rank}_host_command_busy_ms']=busy;x[f'rank{rank}_outside_host_commands_ms']=x['elapsed_ms']-busy
        rows+=rr
        rdir=p.parent/'run'/r.get('prompt_id','')
        if not rdir.exists():rdir=p.parent/'repeat-1'/r.get('prompt_id','')
        # Current sites files exist but are empty: retain evidence of absence.
        for rank in (0,1):
            f=rdir/f'rank{rank}'/'sites.jsonl'
            if f.exists():read(f);census.append({'path':str(f.relative_to(ROOT)),'bytes':f.stat().st_size})
            f=rdir/f'rank{rank}'/'timings.jsonl'
            if f.exists():
                for line in read(f).splitlines():
                    t=json.loads(line)
                    if t.get('cancelled') or not (r['prompt_tokens'] <= t['position'] < r['prompt_tokens']+99):continue
                    key=f'rank{rank}_'+('speculative' if t['speculative'] else 'corrected_or_target')
                    host[key].append(t)
    if not rows:return {'source':str(p.relative_to(ROOT)),'unavailable':'No compatible depth-one request traces'}
    keys=['elapsed_ms','A','B','C','D','R','unresolved_control_gaps_ms','rank0_slack_ms','handoff_ready_to_rank1_ms','draft_issue_after_emission_ms','emission_after_race_ms','rank0_host_command_busy_ms','rank1_host_command_busy_ms','rank0_outside_host_commands_ms','rank1_outside_host_commands_ms']
    paths={}
    for hit,label in ((True,'hit'),(False,'miss')):
        z=[x for x in rows if x['hit']==hit]
        paths[label]={'n':len(z),'mean_ms':{k:st.mean(x[k] for x in z) for k in keys}}
    timing={}
    for key,tt in host.items():
        timing[key]={'n':len(tt),'mean':{k:st.mean(t[k] for t in tt) for k in ('launches_issued','prepare_ms','enqueue_loop_ms','wait_ms','p76_retirement_ms','p76_profiling_ms','host_waits') if all(k in t for t in tt)}}
    return {'source':str(p.relative_to(ROOT)),'request_count':len(requests),'interval_count':len(rows),'hit_fraction':st.mean(x['hit'] for x in rows),'reported_class_balanced_tok_s':d.get('class_balanced_tok_s_1_100_intervals_after_ttft',{}).get('median'),'reported_full_decode_hit_miss':d.get('hit_miss_cycle_statistics'),'first99_conditional_paths':paths,'command_components_ms':m.components(rows),'host_timers_overlap_device_execution':timing,'site_file_census':census,'fresh_gpu_class_ms':{k:None for k in ['MoE_gate_up','MoE_down','shared_expert','HC','QSA','GDN','dense_attention','head','draft','transfers','launch_gaps','GPU_idle']},'missing_reason':'No nonempty per-site device event file in these current performance/smoke requests. Host command time is measured; it does not separate GPU classes or pure idle.'}
def category(site):
    if site=='expsgate':return 'MoE_gate_up'
    if site=='expsdown':return 'MoE_down'
    if site.startswith('hc.'):return 'HC'
    if site.startswith('qsa.'):return 'QSA'
    if site.startswith('gdn.'):return 'GDN'
    if site=='attention':return 'dense_attention_output_projection'
    if site.startswith('shexp'):return 'shared_expert_down_and_activation_only'
    if site=='router':return 'fused_router_and_shared_gate_up_unsplittable'
    return 'other_route_mixture_activation_combine'
def historical():
    p=SH/'packet77-attribution-B-a/run/attribution-summary.json';d=load(p);out=[]
    for rank in (0,1):
        groups=defaultdict(list)
        for r in d['sites']:
            if r['rank']==rank:groups[category(r['site'])].append(r)
        for cat,rs in groups.items():
            us=sum(r['estimated_us_per_half'] for r in rs); floor=sum(r['reference_floor_us']*r['occurrences_per_half'] for r in rs)
            out.append({'rank':rank,'category':cat,'sample_scaled_half_ms':us/1000,'read_only_555GBs_reference_ms':floor/1000,'ratio_to_read_only_reference':us/floor if floor else None,'sites':sorted(set(r['site'] for r in rs)),'sampled_layers':sorted(set(r['layer'] for r in rs))})
    return {'source':str(p.relative_to(ROOT)),'reference_GBs':d['reference_GBs'],'identity':d['selected_view'],'warning':'Historical packet70 selection via p77. Layer22/23 and24/27 medians scaled18 GDN+6 QSA per half. NOT current p97+tile16 times and NOT independently measured hit/speculative/miss totals. Read-only useful-byte reference is not a measured DRAM or compute floor.','classes':out,'sites':d['sites'],'rank1_outside':d['rank1_outside_split'],'draft_event_breakdown':d['draft_breakdown'],'compute_floor':None,'compute_floor_reason':'No retained per-kernel instruction mix/throughput/occupancy evidence supports a numerical compute floor.','transfers_warning':'Zero-width old target copy event fields mean unavailable, not zero latency.'}
def micros():
    out=[]
    for name in ('packet100b-route-capture','packet104-tile-transpose'):
        p=ST/name/'evidence/micro-B/qualification.json';d=load(p)
        out.append({'source':str(p.relative_to(ROOT)),'threshold':d['threshold'],'candidates':{k:v['time_ratio'] for k,v in d['candidates'].items()},'qualified':d.get('qualified'),'draft_route_caveat':d.get('draft_route_caveat'),'warning':'Operator ratio only; not a full-half measured cost or speed claim.'})
    return out
def smoke_transfers():
    root=SH/'p105s-B-head-split-compute-incident64-v1';groups=defaultdict(list)
    for rank in (0,1):
        p=root/f'run/ranks/rank{rank}/p105-transfers.jsonl'
        for b in read(p).splitlines():
            d=json.loads(b);groups[(rank,d['leg'],d['bytes'])].append(d['host_us'] if 'host_us' in d else d['host_dependency_wait_us'])
    read(ROOT/'notes/2026-10-18-own-runtime-packet105-device-result.md')
    return {'scope':'Candidate-only single 64-token request, includes first-token warm/start effect. Packet105 later failed architecture-tradeoff oracle; not qualified baseline or speed comparison. Packet105b repair is separate pending evidence.','warning':'These are host command envelopes; hidden-export includes producer dependency wait. Never add them to the DAG host command totals or call pure DMA latency.','rows':[{'rank':r,'leg':l,'bytes':b,'n':len(v),'mean_host_us':st.mean(v),'median_host_us':st.median(v)} for (r,l,b),v in sorted(groups.items())]}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args()
    names=['p104b-B-grid-A-0-production','p104b-B-grid-A-2-production','p104b-B-grid-B-0-production','p104b-B-grid-B-3-production','p101-reseal-20261018-520cf01bd7b6-A-grid-0-control','p101-reseal-20261018-520cf01bd7b6-A-grid-1-draft_attention','p101-reseal-20261018-520cf01bd7b6-A-grid-2-control','p105s-B-head-split-compute-incident64-v1','p100-down-tile16-B-grid-A-0-production','p100-down-tile16-B-grid-A-1-down-tile16','p100-down-tile16-B-grid-A-2-production']
    paths=[SH/n/'summary.json' for n in names]+[ST/'packet97-record-bundle/build/device-cards01-b/WS128/run/summary.json']
    result={'schema':'packet108.existing-attribution.v1','definition':'One verified emission to next; first99 intervals per 128-token request (63 for 105 smoke); pool interval means within hit/miss, not class-balanced throughput. Use starting emission verified guess to classify; next rank0 speculation overlaps rank1.','dependencies':'hit=D+max(A+offset,B)+G; miss=max(D,R+C)+max(A+offset,B)+G. A=next rank0 speculation, B=rank1 target, C=corrected rank0, D=rank1 draft, R=restore.','runs':[run(p) for p in paths if p.exists()],'historical':historical()}
    result['operator_micros']=micros();result['packet105_smoke_transfers']=smoke_transfers()
    result['sources']=SOURCES
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'output':args.output,'runs':len(result['runs']),'sources':len(SOURCES)}))
if __name__=='__main__':main()
