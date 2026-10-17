#!/usr/bin/env python3
"""Fail-closed native byte/event validation and fresh-owner operator summary."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

CLASSES = ('expsgate.iq2','expsdown','gdn.qkv.q6','gdn.z.q6',
           'expsgate.iq3','gdn.qkv.q8','gdn.z.q8')
PRIMARY = CLASSES[:4]
WEIGHT_BYTES = dict(zip(CLASSES,(10_496_000,9_216_000,32_768_000,19_660_800,
                               14_080_000,29_491_200,17_694_720)))
HERE=Path(__file__).resolve().parent

def require(ok,why):
    if not ok: raise ValueError(why)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p): return [json.loads(line) for line in Path(p).read_text().splitlines()]
def digest(x):
    return isinstance(x,str) and len(x)==64 and all(c in '0123456789abcdef' for c in x)
def manifest(mode):
    return [(c,m,i) for c in CLASSES for m in (1,2) for i in range(9 if mode=='exact' else 28)]

def exact(path,cpu=False):
    path=Path(path);r=json.loads((path/'receipt.json').read_text());mode=r.get('mode')
    require(mode in ('exact','timing'),'native mode')
    require(r.get('schema')=='ownrt.packet48.native.v1' and r.get('passed') is True and
            r.get('device_executed') is (not cpu) and r.get('safe_teardown') is True,'native completion/teardown')
    records=rows(path/'comparisons.jsonl')
    require([(v.get('class'),v.get('M'),v.get('iteration')) for v in records]==manifest(mode),'complete ordered byte matrix required')
    require(r.get('checks')==len(records),'check count')
    for v in records:
        require(v.get('equal') is True and type(v.get('bytes')) is int and v['bytes']>0 and
                digest(v.get('sha256')) and digest(v.get('input_sha256')),'invalid byte comparison')
        # Exact sizes cover all four output/status buffers and error, including
        # deliberately poisoned unused peer outputs in single-projection cases.
        n=5 if cpu else (640 if v['class'].startswith('expsgate') else 2560 if v['class']=='expsdown' else 10240 if 'qkv' in v['class'] else 6144)
        slots=10 if v['class'].startswith('exps') else 1
        require(v['bytes']==v['M']*(n*slots*4+slots*8+4),'capture extent changed')
    for c in CLASSES:
        for m in (1,2):
            subset=[v for v in records if v['class']==c and v['M']==m]
            require(len({v['input_sha256'] for v in subset})==len(subset),'inputs did not change')
            require(len({v['sha256'] for v in subset})>1,'outputs did not respond to input changes')
    identity=hashlib.sha256(''.join(v['sha256'] for v in records).encode()).hexdigest()
    require(identity==r.get('exact_output_identity'),'output identity not bound to complete raw comparisons')
    if mode=='exact':require(not rows(path/'iterations.jsonl'),'exact mode includes timing rows')
    return r

def timing(path):
    path=Path(path);r=exact(path);require(r['mode']=='timing','timing receipt required')
    data=rows(path/'iterations.jsonl')
    expected=[(c,m,i,a) for c,m,i in manifest('timing') for a in (False,True)]
    require([(v.get('class'),v.get('M'),v.get('iteration'),v.get('candidate')) for v in data]==expected,'complete ordered timing matrix required')
    stamps=[]
    for v in data:
        require(v.get('warmup') is (v['iteration']<4),'warmup classification')
        ev=v.get('events',[]);require(len(ev)==(1 if v['candidate'] else v['M']),'event coverage')
        for e in ev:
            a,b=e.get('start_ns'),e.get('end_ns')
            require(type(a) is int and type(b) is int and 0<a<b and b-a<4_000_000_000,'event timestamps')
            stamps.append((a,b))
        require(v.get('gpu_ns')==sum(e['end_ns']-e['start_ns'] for e in ev),'event sum')
    stamps.sort();require(all(a[1]<=b[0] for a,b in zip(stamps,stamps[1:])),'duplicated/overlapping events on one in-order compute queue')
    data=[v for v in data if not v['warmup']]
    lookup={(v['class'],v['M'],v['iteration'],v['candidate']):v['gpu_ns']/1000 for v in data}
    classes={}
    for c in CLASSES:
        classes[c]={}
        for m in (1,2):
            strata={'all':list(range(4,28))}
            if m==2 and c.startswith('exps'):
                strata.update({name:[i for i in range(4,28) if i%3==remainder] for name,remainder in [('same_slots',0),('overlap5_no_same_slots',1),('disjoint',2)]})
            classes[c][str(m)]={name:dict(old_us=statistics.median(lookup[c,m,i,False] for i in its),
                new_us=statistics.median(lookup[c,m,i,True] for i in its),pairs=len(its)) for name,its in strata.items()}
            for name,v in classes[c][str(m)].items():
                old_bytes=WEIGHT_BYTES[c]*m
                # Source-level useful reads, not DRAM counters. Mixed route
                # strata have no honest single numerator, so retain null.
                new_bytes=(None if name=='all' else WEIGHT_BYTES[c]*(1 if name=='same_slots' else 2)) if m==2 and c.startswith('exps') else WEIGHT_BYTES[c]
                v.update(old_useful_weight_read_bytes=old_bytes,new_useful_weight_read_bytes=new_bytes,
                         old_effective_GBs=old_bytes/(v['old_us']*1000),
                         new_effective_GBs=None if new_bytes is None else new_bytes/(v['new_us']*1000),
                         hardware_dram_counter=False)
    old_exp=statistics.median(sum(lookup[c,1,i,False] for c in PRIMARY[:2]) for i in range(4,28))
    new_exp=statistics.median(sum(lookup[c,1,i,True] for c in PRIMARY[:2]) for i in range(4,28))
    saved=statistics.median(sum(lookup[c,1,i,False]-lookup[c,1,i,True] for c in PRIMARY) for i in range(4,28))
    # Independent p46 per-class medians are a comparability guard, not this run's denominator.
    historical={'expsgate.iq2':(81.875,81.771),'expsdown':(91.875,91.875),
                'gdn.qkv.q6':(100.105,100.104),'gdn.z.q6':(39.740,39.791)}
    ratios={c:classes[c]['1']['all']['old_us']/statistics.median(v) for c,v in historical.items()}
    control_matched=all(.85<=v<=1.15 for v in ratios.values())
    return dict(schema='ownrt.packet48.timing.v1',passed=True,classes=classes,
        expert_old_us=old_exp,expert_new_us=new_exp,expert_speedup=old_exp/new_exp,
        ordinary_gdn_saved_us=saved,performance_bar_met=old_exp/new_exp>=1.5 or saved>=40,
        current_primary_controls_within_15pct=control_matched,control_vs_p46_ratios=ratios,
        integration_eligible=(old_exp/new_exp>=1.5 or saved>=40) and control_matched,
        model_speed_claim=False)

def combine(paths):
    from window_support import prerequisite,verify_files,sealed_gate
    sealed_gate()
    require(len(paths)==2,'two fresh timing owners required');ws=[];summaries=[]
    for p in paths:
        p=Path(p);w=json.loads(p.read_text())
        require(w.get('schema')=='own-runtime.packet48.window.v1' and w.get('passed') is True and w.get('mode')=='timing' and w.get('device_executed') is True and w.get('child_still_running') is False,'timing owner incomplete')
        verify_files(w['native_files'],p.parent)
        require(set(w['native_files'])=={'run/receipt.json','run/comparisons.jsonl','run/iterations.jsonl'},'complete timing file closure')
        require(w['seal_sha256']==sha(HERE/'seal.json'),'current seal drift')
        require(sha(p.parent/'summary.json')==w.get('summary_sha256'),'summary changed')
        ex=w.get('exactness_companions',[]);require(len(ex)==2,'exact companions missing')
        for e in ex:require(sha(e['path'])==e['sha256'],'exact companion drift')
        prerequisite([e['path'] for e in ex],w)
        exact_owners={(v['pid'],v['process_start_ticks']) for v in [json.loads(Path(e['path']).read_text()) for e in ex]}
        require((w.get('pid'),w.get('process_start_ticks')) not in exact_owners,'timing reused an exactness process')
        summary=timing(p.parent/'run');require(summary==json.loads((p.parent/'summary.json').read_text()),'summary inconsistent')
        ws.append(w);summaries.append(summary)
    for key in ('seal_sha256','binary_sha256','card','boot_id','environment','coordinator_fault_review','exactness_companions'):
        require(ws[0].get(key)==ws[1].get(key),'timing identity mismatch: '+key)
    require(len({(w['pid'],w['process_start_ticks']) for w in ws})==2,'fresh timing processes required')
    return dict(schema='ownrt.packet48.summary.v1',passed=True,device_qualified=True,
                both_performance_bars_met=all(s['performance_bar_met'] for s in summaries),
                integration_eligible=all(s['integration_eligible'] for s in summaries),
                windows=[dict(path=str(p),sha256=sha(p)) for p in paths],results=summaries,
                model_speed_claim=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--windows',type=Path,nargs=2,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    require(not a.output.exists(),'new summary path required');a.output.write_text(json.dumps(combine(a.windows),indent=2)+'\n')
