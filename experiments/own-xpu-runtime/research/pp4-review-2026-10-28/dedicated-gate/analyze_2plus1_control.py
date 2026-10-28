#!/usr/bin/env python3
"""Offline single-prompt 2+1 depth3 versus incumbent two-card depth1 diagnostic."""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
from analyze_decode import core, need, read, timing_from_tokens
from colocated_control import native_timing


def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def binary(plan):
    rows=[h for path,h in plan['pins'].items() if path.endswith('/sc117-engine')]
    need(len(rows)==1,'one native binary identity required');return rows[0]

def clean(root,result,owners):
    terminal=read(root/'terminal.json')
    for row in (result,terminal):
        need(row.get('passed') is True and not row.get('error') and not row.get('live_pids')
             and set(row.get('returncodes',{}))==owners
             and all(type(v)is int and v==0 for v in row['returncodes'].values()),'all expected owners must finish cleanly')

def flag(argv,name,default=None):
    need(argv.count(name)<=1,'duplicate draft/model option')
    return argv[argv.index(name)+1] if name in argv else default

def identity(d,c):
    for key in ('prompt_tokens','context','max_new','vocab','eos_token_ids','model_identity_sha256','activation_dtype'):
        need(d.get(key)==c.get(key),'identity differs: '+key)
    need(len(d['prompt_tokens'])==1677 and d['context']==65536 and d['max_new']==512,'fixed1677/512/64K diagnostic')
    need(d['speculative_depth']==3 and c['speculative_depth']==1 and d['boundaries']==[0,25,48]
         and c['boundaries']==[0,23,48] and len(d['stages'])==len(c['stages'])==2,
         'explicit depth/topology treatment differs')
    need(d.get('check_policy')=='measured' and d.get('dedicated_capture_ready') is True,'measured capture-ready candidate')
    need(c.get('mode')=='native-controller-colocated-depth1' and c.get('native_launch_max_new')==128
         and c.get('native_request_max_new')==512,'explicit native launch128/request512 contract')
    need(binary(d)==binary(c),'same current native binary required')
    need(core(d)==core(c),'kernel flags/environment mismatch')
    da,ca=d['provider']['argv'],c['stages'][0]['argv']
    for name,default in (('--draft-model',None),('--draft-experts',None),('--draft-head','full'),('--draft-fault','none')):
        need(flag(da,name,default)==flag(ca,name,default),'draft arithmetic/source differs: '+name)
    dm,cm=flag(da,'--draft-manifest'),flag(ca,'--draft-manifest')
    need(dm is not None and cm is not None and d['pins'].get(dm)==c['pins'].get(cm)
         and d['pins'].get(dm) is not None,'draft manifest pin differs')
    for ds in d['stages']:
        for cs in c['stages']:
            for name in ('--model-dir','--plan','--identity'):
                dv,cv=flag(ds['argv'],name),flag(cs['argv'],name)
                need(dv is not None and dv==cv,'target model/quant source differs: '+name)
                if name!='--model-dir':need(d['pins'].get(dv)==c['pins'].get(cv) and d['pins'].get(dv) is not None,'target authority pin differs')


def qualification(proof_path,proof_sha,quality_plan_path,measured,outputs):
    need(type(proof_sha)is str and len(proof_sha)==64 and digest(proof_path)==proof_sha,'quality proof exact SHA256 required')
    p=read(proof_path);qpath=Path(quality_plan_path);q=read(qpath)
    need(p.get('schema')=='ownrt.dedicated-cross-context-proof.v1' and p.get('passed') is True
         and p.get('candidate_context')==65536 and p.get('reference_context')==262144
         and p.get('input_position')==1708 and p.get('outputs')==32 and p.get('canonical_pairs')==1707,
         'successful registered cross-context qualification required')
    for role,total,exact,capacity in (('target',2065,2017,48),('draft',73,69,4)):
        part=p[role]
        need(part['source_count']==total and len(part['exact_source_keys'])==exact
             and len(part['capacity_sources'])==capacity,'complete registered quality inventory required')
    sources={str(Path(s['path']).resolve()):s['sha256'] for s in p['sources']}
    need(sources.get(str(qpath.resolve()))==digest(qpath),'quality plan not bound by actual proof')
    qrpath=Path(q['output'])/'driver-result.json';qr=read(qrpath)
    need(sources.get(str(qrpath.resolve()))==digest(qrpath),'quality result not bound by actual proof')
    need(qr.get('passed') is True and qr['output_ids']==outputs[:32] and qr.get('input_position')==1708,
         'quality32 output prefix differs')
    for key in ('prompt_tokens','context','vocab','eos_token_ids','model_identity_sha256','draft_model_sha256',
                'activation_dtype','boundaries','speculative_depth','dedicated_capture_ready'):
        need(q.get(key)==measured.get(key),'qualified candidate identity differs: '+key)
    need(q['max_new']==32 and q['check_policy']=='qualification' and binary(q)==binary(measured)
         and core(q)==core(measured),'quality binary/core/policy differs')
    need(q['provider']['bdf']==measured['provider']['bdf']
         and [s['bdf'] for s in q['stages']]==[s['bdf'] for s in measured['stages']], 'quality placement differs')
    return dict(path=str(proof_path),sha256=proof_sha,quality_plan=str(qpath),quality_plan_sha256=digest(qpath),
        scope='32-output full target/draft state cross-context capacity proof; measured512 requires exact output identity and lifecycle separately')


def analyze(dedicated_output,control_output,quality_proof,quality_proof_sha256,quality_plan):
    dr,cr=Path(dedicated_output),Path(control_output)
    d,c=read(dr/'driver-result.json'),read(cr/'result.json');dp,cp=read(dr/'plan.json'),read(cr/'plan.json')
    need(d.get('schema')=='ownrt.dedicated-provider-driver-result.v1'
         and c.get('schema')=='ownrt.colocated-native-control-result.v1','actual driver result schemas required')
    clean(dr,d,{'0','1','provider'});clean(cr,c,{'0','1'});identity(dp,cp)
    outputs=d['output_ids']
    need(len(outputs)==512 and outputs==c['tokens']==c['actual_output_ids']==cp['expected_output_ids']
         and not any(t in dp['eos_token_ids'] for t in outputs[:-1]),'exact full512 outputs and honored EOS required')
    frontier=1677+512-1
    need(d.get('input_position')==frontier and d.get('provider_pairs')==frontier-1
         and d.get('provider_serial')==frontier-1 and d.get('cancelled') is False,'complete actual candidate progression')
    first=None
    with (dr/'commands.jsonl').open() as f:
        for line in f:
            row=json.loads(line)
            if row.get('event')=='issued' and row.get('stage')==0 and row.get('op')==24:first=row;break
    need(first is not None and first['row']['position']==0,'candidate cold first ROW position0 required')
    need(cp.get('fresh_cold_request') is True and type(c.get('cached_tokens'))is int and c['cached_tokens']==0,
         'fresh single native-control request required')
    values=list(map(int,(cr/'transport/native-request.txt').read_text().split()))
    expected=[3,512,1,0,1677,0,len(cp['eos_token_ids']),*cp['prompt_tokens'],*cp['eos_token_ids']]
    need(values==expected,'actual native request must be cold512 MTP/overlap without continuation/trailers')
    ownership=read(cr/'native/ownership.json')
    need(ownership.get('retained_pids')==[] and ownership.get('returncodes')==[0,0]
         and ownership.get('stop_requested') is False,'normal native FINISH ownership receipt required')
    proof=qualification(quality_proof,quality_proof_sha256,quality_plan,dp,outputs)
    rows=[json.loads(line) for line in (dr/'tokens.jsonl').read_text().splitlines()]
    elapsed=d.get('emitted_elapsed_seconds')
    need(len(rows)==len(outputs) and isinstance(elapsed,list) and len(elapsed)==len(outputs),'complete candidate timing')
    started=rows[0]['committed_monotonic_s']-elapsed[0]
    need(all(type(e)in (int,float) and math.isfinite(e) and abs(r['committed_monotonic_s']-started-e)<1e-6
             for r,e in zip(rows,elapsed)),'candidate elapsed and actual commit identity')
    actual=timing_from_tokens(dr/'tokens.jsonl',outputs,started,started+d['scheduler_wall_seconds'])
    stamps=[r['committed_monotonic_s'] for r in rows]
    need(stamps[99]>stamps[0] and actual['committed_output_span_seconds']>0,'positive candidate timing intervals')
    ct=native_timing(c,outputs,c['request_started_monotonic_s'],c['request_finished_monotonic_s'])
    dt=dict(first99_decode_tokens_per_second=99/(stamps[99]-stamps[0]),decode_tokens_per_second=actual['decode_tokens_per_second'])
    windows={}
    for name,key in (('first99','first99_decode_tokens_per_second'),('all511','decode_tokens_per_second')):
        a,b=dt[key],ct[key]
        windows[name]=dict(intervals=99 if name=='first99' else 511,dedicated_tokens_per_second=a,
            colocated_tokens_per_second=b,
            dedicated_over_colocated_ratio=a/b,dedicated_rate_change_percent=(a/b-1)*100)
    return dict(schema='ownrt.2plus1-colocated-singlecase-diagnostic.v1',passed=True,exact_prompt_output_ids=True,
        context=65536,prompt_tokens=1677,output_count=512,ended_on_eos=outputs[-1] in dp['eos_token_ids'],
        native_binary_sha256=binary(dp),quality_proof=proof,windows=windows,
        differences=['Dedicated2targets[0,25,48]+provider:3 GPUs/depth3 versus incumbent native2targets[0,23,48] with colocated draft:2 GPUs/depth1.',
            'Dedicated capture-ready leases/host scheduler versus incumbent internal native-controller overlap.',
            'Both carry incumbent raw-ring flag; native control rank1 uses512-row QSA raw ring, pipeline targets retain full context raw arrays.',
            'Each is first cold request on fresh owners; load/JIT and prompt excluded from decode; independently loaded processes may warm differently.'],
        normalization='Same model/quant authority, native binary, core flags/environment; only BDF/cache paths normalized. Topology/depth/layout/controller differences remain explicit.',
        scope='One prompt timing diagnostic, no suite/localmax claim, no66.21-suite comparison, no independent-reference resolution.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('dedicated-output','control-output','quality-proof','quality-plan','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--quality-proof-sha256',required=True);a=p.parse_args()
    result=analyze(a.dedicated_output,a.control_output,a.quality_proof,a.quality_proof_sha256,a.quality_plan)
    with a.output.open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
