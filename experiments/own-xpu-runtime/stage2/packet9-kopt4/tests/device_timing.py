#!/usr/bin/env python3
"""Coordinator-only paired fresh-owner expert and whole-layer GEMV timing."""
import argparse
import json
import math
import os
import statistics
from pathlib import Path
from common import BUILD, INPUTS, LATCH, MANIFEST, HERE, MODES, admit, plan, planlib, save, sha, teardown_ok, watch, passes


def spans(events):
    if not events or any(set(e) != {'start_ns','end_ns'} for e in events):
        raise ValueError('event coverage')
    if any(type(v) is not int or v < 0 for e in events for v in e.values()):
        raise ValueError('timestamps')
    if any(e['end_ns'] <= e['start_ns'] for e in events) or any(a['end_ns'] > b['start_ns'] for a,b in zip(events,events[1:])):
        raise ValueError('event order')
    return (events[-1]['end_ns']-events[0]['start_ns'])/1e6


def summarize(raw, layer):
    if raw.get('schema') != 'own-runtime.iq3.packet9.timing-native.v1' or not teardown_ok(raw) or raw.get('device') != raw['teardown']['backend']:
        raise ValueError('native failure/teardown')
    has_experts=bool(layer['expert_active_bytes'])
    if raw.get('route_status') != ([[0]*10]*3 if has_experts else []):
        raise ValueError('route status')
    dispatch={t['name']:t['variant'] for t in json.loads((HERE/'dispatch.json').read_text())['tensors']}
    shape=[]
    for j in layer['jobs']:
        if 'ffn_gate_exps' in j['name']:shape.extend([1,1,1])
        elif j['experts']==1:shape.append(passes(dispatch[j['name']]))
    summary={}
    for kind in ('fused','sequence'):
        rows=raw.get(kind)
        expected=list(MODES) if kind=='sequence' or has_experts else []
        if not isinstance(rows,list) or [r['variant'] for r in rows] != expected:
            raise ValueError('missing fused/sequence coverage')
        out=[]
        for r in rows:
            ns=[1,1,1] if kind=='fused' else shape
            if r.get('layer')!=layer['layer'] or r.get('launches')!=sum(ns) or len(r.get('iterations',[]))!=20:
                raise ValueError('layer/launch/sample extent')
            samples=[];sums=[];walls=[];submits=[];parts=[[],[],[]]
            previous_end=-1
            for iteration in r['iterations']:
                events=iteration['events'];allparts=iteration['pass_events']
                if len(events)!=len(ns) or len(allparts)!=len(ns):raise ValueError('sequence coverage')
                samples.append(spans(events))
                if events[0]['start_ns']<previous_end:raise ValueError('iteration overlap')
                previous_end=events[-1]['end_ns']
                total=0
                for e,ps,n in zip(events,allparts,ns):
                    if len(ps)!=n:raise ValueError('missing split pass')
                    spans(ps)
                    if e!=dict(start_ns=ps[0]['start_ns'],end_ns=ps[-1]['end_ns']):raise ValueError('inclusive split span')
                    total+=sum(p['end_ns']-p['start_ns'] for p in ps)/1e6
                sums.append(total)
                wall,submit=iteration['host_wall_ms'],iteration['host_submit_ms']
                if not all(type(t) in (int,float) and math.isfinite(t) for t in (wall,submit)) or not 0<=submit<=wall:raise ValueError('host clock')
                walls.append(wall);submits.append(submit)
                if kind=='fused':
                    for i,e in enumerate(events):parts[i].append((e['end_ns']-e['start_ns'])/1e6)
            packed=layer['expert_active_bytes'] if kind=='fused' else layer['gemv_active_bytes']
            row=dict(variant=r['variant'],launches=sum(ns),**planlib.metrics(samples,packed),
                median_kernel_sum_ms=statistics.median(sums),median_queue_gap_ms=statistics.median([a-b for a,b in zip(samples,sums)]),
                median_host_wall_ms=statistics.median(walls),median_host_submit_ms=statistics.median(submits))
            if kind=='fused':
                row['stage_median_ms']=dict(zip(('gate_up','down','weighted_epilogue'),map(statistics.median,parts)))
                row['work_groups']=layer['expert_groups'][r['variant']]
            out.append(row)
        summary[kind]=out
    return summary


def validate_census(censuses,layer):
    if len(censuses)!=2:raise ValueError('resident/released census')
    live=[r for r in censuses[0]['allocations'] if r['live']]
    weights=[r for r in live if r['category']=='weights']
    expected={j['name']+'/weights':j['weight_bytes'] for j in layer['jobs']}
    if {r['label']:r['bytes'] for r in weights}!=expected or len(weights)!=len(expected):raise ValueError('weight census')
    if any(r['memory']!='device' for r in weights):raise ValueError('weight placement')
    for memory in ('device','host-pinned','host-shadow'):
        if censuses[0]['totals'][memory]!=sum(r['bytes'] for r in live if r['memory']==memory):raise ValueError('census total')
    if any(censuses[-1]['totals'].values()) or any(r['live'] for r in censuses[-1]['allocations']):raise ValueError('live allocations')


def project(records, p):
    # Proxy only: representative layers, not a model execution. PLE/upgraded
    # GDN times replace two ordinary GDNs. Both fresh-owner receipts retained.
    times={v:{} for v in MODES}
    for variant in MODES:
        for layer in p['layers']:
            values=[next(r for r in rec['summary']['sequence'] if r['variant']==variant)['median_ms'] for rec in records if rec['layer']==layer['layer']]
            selected=[rec for rec in records if rec['layer']==layer['layer']]
            if len(values)!=2 or {rec['repeat'] for rec in selected}!={0,1}:raise ValueError('two fresh owners required')
            times[variant][layer['layer']]=statistics.median(values)
    lookup_bytes=3540
    rows=[]
    for variant,ms in times.items():
        head=ms[4];embedding=lookup_bytes/(590*1e6)
        for gdn,qsa,label in ((36,12,'checkpoint: 48 total layers'),(48,12,'requested hypothetical: 60 total layers, not this checkpoint')):
            total=(gdn-2)*ms[0]+ms[1]+ms[2]+qsa*ms[3]+head+embedding
            rows.append(dict(variant=variant,scope=label,gdn_layers=gdn,qsa_layers=qsa,
                gdn_ms=ms[0],ple_gdn_ms=ms[1],upgraded_gdn_ms=ms[2],qsa_ms=ms[3],head_and_final_hc_ms=head,
                embedding_floor_ms=embedding,projected_ms_per_token=total,projected_tok_s=1000/total,
                reference_tok_s=28.49,reference_ms_per_token=1000/28.49))
    return dict(measured=False,scope='GEMV-only representative-layer projection, two-card sequential layer split; NOT full decode',
        limitations=['prepared independent nonlinear inputs','fixed routes and packed-row tiling','representative shapes, not every layer timed',
            'embedding uses optimistic VRAM byte floor; host lookup mapping/latency unmeasured','omits non-GEMV ops, PCIe, state and KV',
            'no doubled bandwidth for sequential layer splitting'],
        checkpoint_payload_bytes=4951240940,checkpoint_590_GB_s_floor_ms=4951240940/(590*1e6),
        checkpoint_590_GB_s_ceiling_tok_s=590e9/4951240940,rows=rows)


def execute(card,output,exactness):
    out,manifest=admit(card,output)
    exact=json.loads(exactness.read_text())
    if exact.get('schema')!='own-runtime.iq3.packet9.device-window.v1' or exact.get('passed') is not True or exact.get('card')!=card or exact.get('prepared_sha256')!=sha(MANIFEST):
        raise ValueError('matching packet9 exactness required')
    if [r.get('kernel') for r in exact.get('variants',[])]!=list(MODES) or not all(r.get('passed') is True and r['native']['checks']==manifest['fixture_cases'][r['kernel']] and teardown_ok(r['native']) for r in exact['variants']):
        raise ValueError('exactness coverage')
    out.mkdir(parents=True)
    record=dict(schema='own-runtime.iq3.packet9.timing.v1',passed=False,device_executed=True,card=card,
        prepared_sha256=sha(MANIFEST),prepared_manifest=manifest,exactness_sha256=sha(exactness),plan=plan(),layers=[],
        environment={k:v for k,v in os.environ.items() if k.startswith(('SYCL_','ZE_','ONEAPI_','UR_')) or k=='OMP_NUM_THREADS'})
    try:
        for repeat in range(2):
            for layer in record['plan']['layers']:
                dest=out/('repeat%d-layer%d'%(repeat,layer['layer']))
                cmd=[str(BUILD/'device/device-timing'),'--authorized-device-window',str(card),str(INPUTS/('layer%d.tsv'%layer['layer'])),str(dest/'native.json'),str(dest/'census.json')]
                window=watch(cmd,dest)
                raw=json.loads((dest/'native.json').read_text());census=json.loads((dest/'census.json').read_text())
                validate_census(census,layer);summary=summarize(raw,layer)
                record['layers'].append(dict(repeat=repeat,layer=layer['layer'],window=window,native=raw,census=census,summary=summary,kernel_journal_sha256=sha(dest/'kernel-window.txt')))
                if window['returncode']!=0 or window['stop_reason'] is not None:raise ValueError('timing window failed')
        record['projection']=project(record['layers'],record['plan']);record['passed']=True
    except Exception as e:
        record['error']=str(e);save(LATCH,dict(reason=str(e),output=str(out)))
    save(out/'timing.json',record)
    return record['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run',action='store_true');mode.add_argument('--authorized-device-window',action='store_true')
    p.add_argument('--card',type=int);p.add_argument('--output',type=Path);p.add_argument('--exactness',type=Path);a=p.parse_args()
    if a.dry_run:print(json.dumps(plan(),indent=2))
    else:
        if a.card is None or a.output is None or a.exactness is None:p.error('card, output, exactness required')
        raise SystemExit(0 if execute(a.card,a.output,a.exactness) else 1)
