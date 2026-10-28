#!/usr/bin/env python3
"""Host-observed overlap only. Reads a completed capture run; never contacts GPUs."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import statistics
import compare as proof

need=proof.need

def summary(seconds):
    values=sorted(seconds)
    return dict(count=len(values),sum_s=sum(values),mean_ms=statistics.mean(values)*1000 if values else None,
                median_ms=statistics.median(values)*1000 if values else None,
                p95_ms=values[min(len(values)-1,int(.95*len(values)))]*1000 if values else None,
                max_ms=values[-1]*1000 if values else None)

def analyze(commands,final_stage):
    pending={};providers=[];targets=[];last=-math.inf
    for index,command in enumerate(commands):
        timestamp=command['monotonic_s']
        need(type(timestamp)in(int,float) and math.isfinite(timestamp) and timestamp>=last,
             'actual finite globally ordered monotonic timestamps required')
        last=timestamp;owner=command.get('owner',command.get('stage'));sequence=command['sequence'];key=(owner,sequence)
        event=command['event']
        if event=='issued':
            need(key not in pending,'unique outstanding host command')
            pending[key]=dict(issued=command,index=index)
        elif event=='parent-captured':
            need(owner=='provider' and key in pending and 'captured' not in pending[key], 'one ACK per outstanding provider')
            pending[key]['captured']=command;pending[key]['captured_index']=index
        elif event=='completed':
            need(key in pending,'completion after actual issued command')
            job=pending.pop(key);job['completed']=command;job['completed_index']=index
            if owner=='provider':
                need('captured' in job,'capture-enabled provider must ACK before completion')
                if job['issued']['row']['fixture']>1:providers.append(job)
            else:targets.append(job)
        else:raise ValueError('unknown host command event '+event)
    need(not pending,'completed run has no outstanding host command')
    need(providers,'steady provider fixture>1 required')
    windows=[];totals=Counter();durations=[];pre_capture=[];provider_span=[];overlap=[]
    for job in providers:
        issued,captured,completed=(job[key] for key in ('issued','captured','completed'))
        begin=captured['monotonic_s'];end=completed['monotonic_s'];start=issued['monotonic_s']
        need(start<=begin<=end,'provider host capture chronology')
        durations.append(end-begin);pre_capture.append(begin-start);provider_span.append(end-start)
        count=Counter();same_seed=[];intersections=[]
        for target in targets:
            command=target['issued'];finish=target['completed']['monotonic_s'];issue=command['monotonic_s']
            # All summaries intentionally use the same steady fixture>1 domain.
            if command['row']['fixture']<=1:continue
            if job['captured_index']<target['index']<job['completed_index']:
                count[f"stage{command['stage']}_op{command['op']}_issued"]+=1
                if command['stage']==final_stage and command['op']==24:
                    same_seed.append(command['row']==issued['row'])
                    if target['completed_index']<job['completed_index']:count['final_ROW_completed_inside']+=1
            if command['stage']==final_stage and command['op']==24:
                width=max(0.,min(end,finish)-max(begin,issue))
                if width:
                    intersections.append((max(begin,issue),min(end,finish)))
                    if target['index']<job['captured_index']:count['final_ROW_already_inflight_at_capture']+=1
        # Final owner is exclusive; take union explicitly rather than double count.
        merged=[]
        for left,right in sorted(intersections):
            if merged and left<=merged[-1][1]:merged[-1]=(merged[-1][0],max(right,merged[-1][1]))
            else:merged.append((left,right))
        width=sum(right-left for left,right in merged);overlap.append(width)
        count['same_seed_final_ROW_issued']=sum(same_seed)
        count['other_seed_final_ROW_issued']=len(same_seed)-sum(same_seed)
        totals.update(count)
        windows.append(dict(provider_sequence=issued['sequence'],fixture=issued['row']['fixture'],
            seed_position=issued['row']['position'],issued_s=start,captured_s=begin,completed_s=end,
            post_capture_host_s=end-begin,final_ROW_host_inflight_intersection_s=width,
            events=dict(count)))
    final_rows=[job for job in targets if job['issued']['stage']==final_stage and job['issued']['op']==24
                and job['issued']['row']['fixture']>1]
    return dict(schema='ownrt.dedicated-capture-host-overlap.v1',provider_windows=len(providers),
        decode_filter='raw fixture>1 (same domain as measured-critical-path.txt; first head/JIT excluded)',
        host_provider_issue_to_capture=summary(pre_capture),host_provider_capture_to_completion=summary(durations),
        host_provider_issue_to_completion=summary(provider_span),counts=dict(totals),
        windows_with_final_ROW_issue=sum(bool(w['events'].get(f'stage{final_stage}_op24_issued')) for w in windows),
        windows_with_final_ROW_host_interval_overlap=sum(value>0 for value in overlap),
        windows_with_any_target_issue=sum(any(key.endswith('_issued') and key.startswith('stage') and value for key,value in w['events'].items()) for w in windows),
        host_final_ROW_inflight_intersection=summary(overlap),
        steady_final_ROW_host_issue_to_completion=summary([job['completed']['monotonic_s']-job['issued']['monotonic_s'] for job in final_rows]),
        windows=windows,
        scope='Controller log times only: issued means queued for send; captured means ACK received/validated; completed means reply decoded. Intersected intervals include socket/dispatch/host scheduling/native work. They do not establish GPU overlap, GPU duration, idle wait duration, ready-input availability, or causal throughput savings.')

def run(output):
    terminal,ts=proof.read(output/'terminal.json')
    need(terminal['schema']=='ownrt.dedicated-provider-terminal.v1' and terminal['passed'] is True
         and not terminal['error'] and not terminal['live_pids']
         and all(type(value)is int and value==0 for value in terminal['returncodes'].values()),'clean completed native terminal required')
    result,rs=proof.driver_result(output/'driver-result.json');plan,ps=proof.read(output/'plan.json')
    need(plan.get('dedicated_capture_ready') is True,'explicit capture-enabled plan required')
    raw,cs=proof.trace_source(output/'commands.jsonl');commands=[json.loads(line,object_pairs_hook=proof.T.BUNDLE.pairs) for line in raw.splitlines()]
    # Authenticate ACK raw framing/actual parent source and exact event coverage.
    pairs=proof.canonical_pairs(commands,result['input_position'],capture_ready=True,target_stages=len(plan['stages']))
    analysis=analyze(commands,len(plan['stages'])-1)
    analysis.update(passed=True,sources=[ts,rs,ps,cs],output_ids=len(result['output_ids']),
                    complete_canonical_pairs=len(pairs),script_sha256=proof.T.sha(Path(__file__).read_bytes()))
    return analysis

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);parser.add_argument('--out',required=True,type=Path);args=parser.parse_args()
    result=run(args.output)
    with args.out.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({key:value for key,value in result.items() if key not in ('windows','sources')}))
