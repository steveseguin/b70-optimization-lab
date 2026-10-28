#!/usr/bin/env python3
"""Offline matched single-prompt decode diagnostic; never launches inference."""
import argparse
import json
from pathlib import Path
import sys

TOOLS=Path(__file__).resolve().parents[3]/'engine/tools'
sys.path.insert(0,str(TOOLS))
from persistent_live_suite import timing_from_tokens


def need(condition,message):
    if not condition:raise ValueError(message)

def read(path):return json.loads(Path(path).read_text())

def core(plan):
    flags=('--attention-q8-p33','--qkv-q6-p33','--expert-iq3xxs-block','--dense-q6-p33',
           '--dense-packed-block','--recurrent-f32','--gsq-packed')
    valued=('--memory','--host-path','--activations','--dispatch','--selection')
    signatures=[];envs=[]
    for stage in plan['stages']:
        argv=stage['argv'];sig={f:argv.count(f) for f in flags}
        for f in valued:
            need(argv.count(f)<=1,'duplicate core option')
            if f in argv:
                value=argv[argv.index(f)+1]
                sig[f]=plan['pins'].get(str(Path(value).resolve()),value) if f in ('--dispatch','--selection') else value
            else:sig[f]=None
        signatures.append(sig)
        envs.append({k:v for k,v in stage['environment'].items() if k not in
                     ('FilterBdfPath','SYCL_CACHE_DIR','NEO_CACHE_DIR','XDG_CACHE_HOME')})
    need(all(s==signatures[0] for s in signatures),'intra-target core flags differ')
    need(all(e==envs[0] for e in envs),'intra-target kernel environment differs')
    return dict(flags=signatures[0],environment=envs[0])


def analyze(dedicated_output,pp4_request):
    droot,proot=Path(dedicated_output),Path(pp4_request)
    d=read(droot/'driver-result.json');p=read(proot/'result.json');pd=read(proot/'driver-result.json')
    dp=read(droot/'plan.json');pp=read(proot/'request-plan.json')
    need(d.get('schema')=='ownrt.dedicated-provider-driver-result.v1' and d.get('passed') is True,
         'dedicated clean completed driver schema required')
    need(p.get('schema')=='ownrt.persistent-rolling-request-result.v1' and p.get('passed') is True,
         'PP4 completed persistent request schema required')
    need(not d.get('live_pids') and d.get('returncodes') and all(v==0 for v in d['returncodes'].values()),
         'dedicated clean native lifecycle required')
    outer=read(proot.parent/'result.json')
    need(outer.get('passed') is True and not outer.get('live_pids') and outer.get('returncodes')
         and all(v==0 for v in outer['returncodes'].values()),'PP4 clean outer lifecycle required')
    for key in ('prompt_tokens','context','max_new','vocab','eos_token_ids','speculative_depth',
                'check_policy','model_identity_sha256','draft_model_sha256','activation_dtype'):
        need(dp.get(key)==pp.get(key),'core identity mismatch: '+key)
    need(dp['max_new']==512 and dp['check_policy']=='measured','measured full512 output cap required')
    need(core(dp)==core(pp),'kernel flags/environment mismatch (only device and cache paths normalized)')
    binaries=lambda plan: sorted(value for key,value in plan['pins'].items() if key.endswith('/sc117-engine'))
    need(len(binaries(dp))==1 and binaries(dp)==binaries(pp),'native binary identity differs')
    draft_owner=lambda plan: plan.get('provider') or plan['stages'][plan.get('provider_stage',0)]
    for flag in ('--draft-experts','--draft-model'):
        a=draft_owner(dp)['argv'];b=draft_owner(pp)['argv']
        need(a.count(flag)==b.count(flag)==1 and a[a.index(flag)+1]==b[b.index(flag)+1],
             'draft arithmetic/source differs: '+flag)
    outputs=d['output_ids'];need(outputs==p['output_ids']==pd['output_ids'],'exact output IDs differ')
    need(1<=len(outputs)<=512 and (len(outputs)==512 or outputs[-1] in dp['eos_token_ids']),
         'output incomplete before cap/EOS')
    frontier=len(dp['prompt_tokens'])+len(outputs)-1
    for result in (d,pd):
        need(result.get('input_position')==frontier and result.get('provider_pairs')==frontier-1
             and result.get('provider_serial')==frontier-1,'full fresh canonical request progression required')
        need(result.get('cancelled') is False,'cancelled request refused')
    need(p.get('cached_tokens')==0 and p.get('prompt_state_reused') is False,'PP4 explicit cold reset/cache evidence required')
    # Dedicated has no HTTP cached_tokens field. Bind the fresh engine lifecycle
    # to actual position0 first ROW and complete canonical coverage instead.
    first=None
    with (droot/'commands.jsonl').open() as commands:
        for line in commands:
            row=json.loads(line)
            if row.get('event')=='issued' and row.get('stage')==0 and row.get('op')==24:
                first=row;break
    need(first is not None and first['row']['position']==0,'dedicated cold position0 ROW evidence required')
    timing={}
    for name,root,result in (('dedicated',droot,d),('pp4',proot,pd)):
        rows=[json.loads(line) for line in (root/'tokens.jsonl').read_text().splitlines()]
        need(rows and 'committed_monotonic_s' in rows[0],'actual commit timestamps required')
        if name=='dedicated':
            elapsed=result.get('emitted_elapsed_seconds')
            need(isinstance(elapsed,list) and len(elapsed)==len(outputs),'dedicated actual elapsed timing required')
            started=rows[0]['committed_monotonic_s']-elapsed[0]
            need(all(abs(row['committed_monotonic_s']-started-e)<1e-6 for row,e in zip(rows,elapsed)),
                 'dedicated elapsed/commit timestamp identity')
            finished=started+result['scheduler_wall_seconds']
        else:
            started=p['request_started_monotonic_s'];finished=p['request_finished_monotonic_s']
        actual=timing_from_tokens(root/'tokens.jsonl',outputs,started,finished)
        stamps=[r['committed_monotonic_s'] for r in rows]
        first100=None
        if len(stamps)>=100:
            span=stamps[99]-stamps[0];need(span>0,'positive first100 commit span required')
            first100=dict(outputs=100,intervals=99,seconds=span,tokens_per_second=99/span)
        timing[name]=dict(first100=first100,all_output=dict(outputs=len(outputs),
            intervals=actual['decode_intervals'],seconds=actual['committed_output_span_seconds'],
            tokens_per_second=actual['decode_tokens_per_second']))
    return dict(schema='ownrt.matched-decode-diagnostic.v1',exact_prompt_and_output_ids=True,
        prompt_tokens=len(dp['prompt_tokens']),output_count=len(outputs),output_cap=512,
        ended_on_eos=outputs[-1] in dp['eos_token_ids'],timing=timing,
        cold_input=dict(pp4_cached_tokens=0,dedicated='No cache field invented: fresh lifecycle, first ROW position0 and full canonical progression verified.'),
        normalization='Only target BDF/filter and fresh SYCL/NEO/XDG cache paths normalized. Core arithmetic flags and other environment compare exactly.',
        differences=['Dedicated3target+separateprovider versus PP4collocatedprovider; boundaries/device ownership differ.',
        'Dedicated holds source leases until completion; PP4may use capture overlap/flat copy.',
        'Dedicated fresh process versus PP4persistent cold reset. Load/JIT/warmup differ; no load/prompt timing included in decode intervals.'],
        scope='One prompt sustained decode diagnostic, not suite/localmax record, independent reference resolution or performance certification.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dedicated-output',type=Path,required=True)
    parser.add_argument('--pp4-request',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=analyze(args.dedicated_output,args.pp4_request)
    text=json.dumps(result,indent=2)+'\n'
    if args.output:
        with args.output.open('x') as file:file.write(text)
    else:print(text,end='')
