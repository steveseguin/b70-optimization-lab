#!/usr/bin/env python3
"""Cold prompts on one preloaded live pipeline; CPU-tested integration contract.

No process launch, native admission, service control or fallback. The owner must
supply already admitted stages and retain the existing outer lifecycle guard.
Native reset capability and the live-drive sequence hook must both be present.
"""
import hashlib
import inspect
import json
import math
import os
import re
import stat
from pathlib import Path
import statistics
import struct
import time

import live_wavefront_driver as live
base=live.base
RESET=11
PROTOCOL='ownrt.pipeline-reset.v1'


def token_sha(tokens):
    return hashlib.sha256(b''.join(struct.pack('<I',token) for token in tokens)).hexdigest()


def validate_suite(suite,plan,expected_count=12):
    base.require(suite.get('schema')=='ownrt.persistent-cold-suite.v1','cold suite schema')
    base.require(suite.get('model_identity_sha256')==plan['model_identity_sha256']
                 and suite.get('activation_dtype')==plan['activation_dtype'],'baseline model/arithmetic identity')
    rows=suite['prompts']
    base.require(type(expected_count)is int and 1<=expected_count<=64 and len(rows)==expected_count,'explicit suite prompt count')
    seen=set()
    for row in rows:
        name=row['id'];prompt=row['prompt_tokens'];expected=row['expected_output_ids'];maximum=row['max_new']
        base.require(isinstance(name,str) and name not in ('','.','..') and Path(name).name==name
                     and all(c.isalnum() or c in '-_.' for c in name) and name not in seen,'unique safe prompt id')
        seen.add(name)
        base.require(row.get('cached_tokens')==0 and type(row.get('cached_tokens'))is int,'uncached baseline required')
        base.require(type(maximum)is int and 1<=maximum<=plan['max_new'],'per-prompt generation bound')
        base.require(isinstance(prompt,list) and prompt and len(prompt)+maximum-1<=plan['context']
                     and all(type(t)is int and 0<=t<plan['vocab'] for t in prompt),'prompt vocabulary/context')
        base.require(isinstance(expected,list) and 1<=len(expected)<=maximum
                     and all(type(t)is int and 0<=t<plan['vocab'] for t in expected),'expected output bounds')
        base.require(row.get('expected_output_sha256')==token_sha(expected),'baseline output token digest')
        if len(expected)<maximum:
            base.require(expected[-1] in plan.get('eos_token_ids',[plan.get('eos')]),
                         'baseline early stop token missing from admitted EOS set')
    return rows


def seed_model_sequences(model,initial_sequences):
    """Hook called by live.drive immediately after constructing a fresh scheduler."""
    base.require(model.frontier==0 and model.counter==0 and not model.rows
                 and len(initial_sequences)==len(model.stages),'fresh scheduler sequence seed')
    for state,sequence in zip(model.stages,initial_sequences):
        base.require(state.position==0 and state.sequence==0 and state.busy is None and state.pending is None
                     and type(sequence)is int and 0<=sequence<2**31-100000,'quiescent bounded sequence seed')
    for state,sequence in zip(model.stages,initial_sequences):state.sequence=sequence


def enable_reset_plan(plan,receipt_path):
    """Augment an already validated live plan using its pinned build receipt."""
    receipt_path=Path(receipt_path).absolute()
    base.require(plan['pins'].get(str(receipt_path))==base.digest(receipt_path),'pinned reset build receipt')
    receipt=read_json(receipt_path,4*1024**2)
    source_sha=receipt.get('sources',{}).get('pipeline/request_reset.hpp')
    base.require(receipt.get('schema')=='ownrt.engine.build.v1' and isinstance(source_sha,str)
                 and re.fullmatch('[0-9a-f]{64}',source_sha),'build lacks persistent reset source capability')
    base.require(plan['pins'].get(receipt['binary'])==receipt['binary_sha256'],'reset binary/plan identity')
    result=dict(plan,persistent_reset_protocol=PROTOCOL,persistent_reset_source_sha256=source_sha)
    result['stages']=[]
    for stage in plan['stages']:
        argv=list(stage['argv'])
        base.require('--pipeline-wavefront' in argv and '--pipeline-live-draft' in argv
                     and '--pipeline-persistent-requests' not in argv,'explicit new live persistent opt-in')
        argv.append('--pipeline-persistent-requests')
        result['stages'].append(dict(stage,argv=argv))
    result['pins']=dict(plan['pins'],**{str(Path(__file__).resolve()):base.digest(__file__)})
    return result


def reset_capability(plan,stages):
    base.require(plan.get('persistent_reset_protocol')==PROTOCOL
                 and re.fullmatch('[0-9a-f]{64}',plan.get('persistent_reset_source_sha256','')),
                 'native persistent reset build capability not admitted')
    base.require(all(stage.spec.get('argv',[]).count('--pipeline-persistent-requests')==1 for stage in stages),
                 'native persistent reset opt-in absent')


def quiescent(stages):
    for stage in stages:
        base.require(getattr(stage,'command_pending',None) is None
                     and not getattr(stage,'transmit',b'') and not getattr(stage,'received',b''),
                     'reset/next prompt while wire command unresolved')


def read_bounded(path,cap):
    fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        base.require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode),'regular evidence file required')
        raw=stream.read(cap+1)
    base.require(len(raw)<=cap,'bounded reset/suite receipt')
    return raw


def read_json(path,cap=65536):
    return json.loads(read_bounded(path,cap))


def validate_reset_receipt(receipt,stage,sequence):
    expected=dict(schema=PROTOCOL,passed=True,stage_id=stage.spec['id'],global_sequence=sequence,
                  target_position=0,draft_position=0 if stage.spec['first'] else None,
                  pending_ticket=False,sticky_error=0,allocation_ids_preserved=True,
                  context_extent=32,alternate_extent=32,counters_reset=True,trace_reset=True)
    base.require(all(receipt.get(k)==v for k,v in expected.items()),'native cold reset receipt identity/state')


def reset_stages(stages,plan,guard,destination):
    reset_capability(plan,stages)
    quiescent(stages);guard.check()
    destination=Path(destination).absolute()
    base.require(destination.is_dir(),'per-request evidence directory required')
    metadata=[]
    # Validate every path before any RESET. The original process output owns the
    # command metadata even after request_reset changes Engine::a.output.
    for stage in stages:
        original=Path(stage.spec['native_output'])
        next_sequence=stage.sequence+1
        target=original/'requests'/destination.name
        path=original/f'reset-{next_sequence}.txt'
        base.require(original.is_absolute() and original.is_dir() and not path.exists()
                     and not target.exists(),'fresh reset metadata and native destination')
        base.require('\n' not in str(target),'reset destination line encoding')
        metadata.append((stage,path,target,next_sequence))
    for stage,path,target,next_sequence in metadata:
        with path.open('x') as out:out.write(str(target)+'\n\n')
    receipts=[]
    for stage,path,target,next_sequence in metadata:
        guard.check()
        stage.sock.settimeout(.2)
        reply=stage.command(RESET,token=0,position=0,fixture=0)
        base.require(stage.sequence==next_sequence and reply[1]==0 and reply[3]==0,'RESET reply/sequence identity')
        receipt=read_json(target/'wavefront-reset.json')
        validate_reset_receipt(receipt,stage,next_sequence)
        if hasattr(stage,'handoff'):del stage.handoff
        receipts.append(dict(receipt,native_output=str(target)))
    quiescent(stages)
    return receipts


def timing_from_tokens(path,outputs,started,finished):
    raw=read_bounded(path,512*1024)
    rows=[json.loads(line) for line in raw.splitlines()]
    base.require(len(rows)==len(outputs) and [r['index'] for r in rows]==list(range(len(outputs)))
                 and [r['token'] for r in rows]==outputs,'complete output timing identity')
    stamps=[r['committed_monotonic_s'] for r in rows]
    base.require(stamps and all(type(t)in (int,float) and math.isfinite(t) and started<=t<=finished for t in stamps)
                 and all(a<=b for a,b in zip(stamps,stamps[1:])),'monotonic committed output timing')
    interval=stamps[-1]-stamps[0]
    return dict(first_token_seconds=stamps[0]-started,full_response_seconds=finished-started,
                committed_output_span_seconds=interval,decode_intervals=max(0,len(outputs)-1),
                decode_tokens_per_second=(len(outputs)-1)/interval if len(outputs)>1 and interval>0 else None,
                full_response_tokens_per_second=len(outputs)/(finished-started) if finished>started else None,
                definition='Decode=(output_count-1)/(last_commit-first_commit); full response includes prompt and final draft/drain, excludes reset and dump.')


def run_suite(stages,plan,guard,output,*,suite,drive=None,expected_count=12,dump_each=False):
    """Pass as the outer wave.execute driver after separate plan/build admission."""
    drive=live.drive if drive is None else drive
    # Refuse before reset until the owner lands the explicit sequence hook. No
    # module-global mutation, implicit monkeypatch, or stale sequence fallback.
    base.require('initial_sequences' in inspect.signature(drive).parameters,'live drive lacks persistent sequence hook')
    reset_capability(plan,stages)
    rows=validate_suite(suite,plan,expected_count)
    output=Path(output);results=[]
    base.require(output.is_dir(),'outer lifecycle output must already exist')
    try:
        for index,row in enumerate(rows):
            guard.check();quiescent(stages)
            request=output/f"request-{index:02d}-{row['id']}";request.mkdir(mode=0o700)
            reset_started=time.monotonic()
            receipts=reset_stages(stages,plan,guard,request)
            reset_seconds=time.monotonic()-reset_started
            prompt_plan=dict(plan,prompt_tokens=row['prompt_tokens'],max_new=row['max_new'])
            initial_sequences=tuple(stage.sequence for stage in stages)
            began=time.monotonic()
            result=drive(stages,prompt_plan,guard,request,initial_sequences=initial_sequences)
            finished=time.monotonic();quiescent(stages)
            outputs=result['output_ids']
            base.require(result.get('input_position')==len(row['prompt_tokens'])+len(outputs)-1,
                         'cold prompt processed position differs from output prefix')
            timing=timing_from_tokens(request/'tokens.jsonl',outputs,began,finished)
            matched=outputs==row['expected_output_ids']
            record=dict(schema='ownrt.persistent-cold-prompt-result.v1',id=row['id'],passed=matched,
                cached_tokens=0,prompt_tokens=len(row['prompt_tokens']),prompt_token_sha256=token_sha(row['prompt_tokens']),
                output_ids=outputs,output_token_sha256=token_sha(outputs),expected_output_sha256=row['expected_output_sha256'],
                reset_seconds=reset_seconds,reset_receipts=receipts,initial_sequences=initial_sequences,
                final_sequences=[stage.sequence for stage in stages],timing=timing,driver_result=result,
                process_reused=True,prompt_state_reused=False,speed_claim=False)
            base.save(request/'result.json',record);results.append(record)
            base.require(matched,'baseline output differs: '+row['id'])
            if dump_each:
                for stage in stages:stage.command(4,position=2000000000+index)
            guard.validate(guard.obs.observe())
    except Exception as error:
        base.save(output/'suite-partial.json',dict(passed=False,completed=len(results),error=repr(error),prompts=results))
        raise
    rates=[r['timing']['decode_tokens_per_second'] for r in results]
    summary=dict(schema='ownrt.persistent-cold-suite-result.v1',passed=True,prompts=results,
        prompt_count=len(results),cached_tokens=0,process_launches_by_harness=0,
        last_prompt_id=results[-1]['id'],final_input_position=results[-1]['driver_result']['input_position'],
        final_output_ids=results[-1]['output_ids'],final_output_scope='last prompt only',
        decode_median_tokens_per_second=statistics.median(rates) if all(r is not None for r in rates) else None,
        full_response_seconds=sum(r['timing']['full_response_seconds'] for r in results),
        diagnostic_only=True,speed_claim=False,
        limits='Cold request state in one resident process set. Model/runtime/page caches remain warm. Full-state reset qualification and matching timing identity required before performance claims.')
    base.save(output/'suite-result.json',summary)
    return summary
