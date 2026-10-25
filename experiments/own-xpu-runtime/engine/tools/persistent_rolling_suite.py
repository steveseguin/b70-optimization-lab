"""Cold rolling requests on an already admitted, continuously loaded owner set.

No process creation, reference answers, restart, device admission or training.
RESET is an all-owner barrier; no next ROW is admitted on a partial reset.
"""
from hashlib import sha256
import json
from pathlib import Path
import re
import socket
import statistics
import time

import rolling_ring_driver as rolling
import persistent_live_suite as evidence

base, bridge = rolling.base, rolling.bridge
RESET = 11
RESET_SCHEMA = 'ownrt.ring-reset-request.v1'
RECEIPT_SCHEMA = 'ownrt.ring-reset.v1'


def digest_json(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def validate_suite(suite, plan, count):
    base.require(isinstance(suite,dict) and set(suite)=={'schema','model_identity_sha256',
        'activation_dtype','eos_token_ids','prompts'} and
        suite['schema']=='ownrt.persistent-rolling-inputs.v1','strict runtime-only cold input schema')
    base.require(suite['model_identity_sha256']==plan['model_identity_sha256'] and
        suite['activation_dtype']==plan['activation_dtype'] and suite['eos_token_ids']==plan['eos_token_ids'],
        'cold input model/arithmetic/EOS identity')
    rows=suite['prompts']
    base.require(type(count) is int and 1<=count<=64 and isinstance(rows,list) and len(rows)==count,
                 'explicit bounded request count')
    seen=set()
    for row in rows:
        base.require(isinstance(row,dict) and set(row)=={'id','prompt_tokens','max_new'},
                     'runtime requests accept no expected output/reference/cache assertion')
        name=row['id'];prompt=row['prompt_tokens'];maximum=row['max_new']
        base.require(isinstance(name,str) and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',name)
            and name not in seen,'unique bounded safe request id')
        seen.add(name)
        base.require(type(maximum) is int and 1<=maximum<=plan['max_new'],'per-request admitted output cap')
        base.require(isinstance(prompt,list) and prompt and len(prompt)+maximum-1<=plan['context']
            and all(type(token) is int and 0<=token<plan['vocab'] for token in prompt),
            'cold prompt vocabulary/context')
    return rows


def request_identity(plan, row, index, epoch):
    return digest_json(dict(schema='ownrt.persistent-rolling-request-identity.v1',
        process_request_sha256=plan['request_sha256'],suite_sha256=plan['suite_sha256'],
        model_identity_sha256=plan['model_identity_sha256'],draft_model_sha256=plan['draft_model_sha256'],
        draft_experts=plan['draft_experts'],activation_dtype=plan['activation_dtype'],
        context=plan['context'],vocab=plan['vocab'],eos_token_ids=plan['eos_token_ids'],
        check_policy=plan['check_policy'],index=index,epoch=epoch,**row))


def quiescent(stages):
    evidence.quiescent(stages)
    for stage in stages:
        base.require(not getattr(stage,'pending_rows',()) and
            getattr(stage,'physical',0)==getattr(stage,'committed',0),
            'reset requires drained target physical/logical frontiers')


def validate_receipt(receipt, descriptor, stage, policy, metadata_sha256):
    expected=dict(descriptor,schema=RECEIPT_SCHEMA,passed=True,check_policy=policy,
        target_position=0,target_physical=0,target_committed=0,target_pending=0,
        draft_position=0 if stage.spec['first'] else None,
        provider_serial=0 if stage.spec['first'] else None,
        context_extent=32,alternate_extent=32,
        draft_context_extent=32 if stage.spec['first'] else None,
        pending_ticket=False,sticky_error=0,allocation_ids_preserved=True,
        counters_reset=True,trace_reset=True,shared_publication_invalidated=True,
        reset_index=descriptor['next_epoch'],metadata_sha256=metadata_sha256,
        previous_target_position=getattr(stage,'committed',0),cold_state_byte_verified=False)
    base.require(all(type(receipt.get(key)) is type(value) and receipt.get(key)==value
                     for key,value in expected.items()),'native cold reset identity/state/policy')
    before=receipt.get('allocation_inventory_before_sha256')
    base.require(isinstance(before,str) and re.fullmatch('[0-9a-f]{64}',before)
        and before==receipt.get('allocation_inventory_after_sha256'),'reset allocation inventory changed')
    for key in ('provider_cold_host_sha256','provider_cold_sequence_sha256'):
        value=receipt.get(key)
        base.require(isinstance(value,str) and (bool(re.fullmatch('[0-9a-f]{64}',value))
            if stage.spec['first'] else value==''),'reset cold provider host/Sequence identity')


def reset(stages, plan, guard, output, *, previous_epoch, previous_request, epoch, request):
    base.require(plan.get('persistent_requests') is True and epoch==previous_epoch+1
        and all('--pipeline-ring-persistent-requests' in stage.spec['argv'] for stage in stages),
        'explicit native persistent reset capability and consecutive epoch')
    base.require(all(re.fullmatch('[0-9a-f]{64}',s) for s in (previous_request,request))
        and previous_request!=request,'fresh reset request identity')
    quiescent(stages);guard.check()
    metadata=[]
    for stage in stages:
        original=Path(stage.spec['native_output'])
        destination=original/'requests'/output.name
        sequence=stage.sequence+1
        base.require(type(sequence) is int and 0<sequence<2**31-100000,'bounded global wire sequence')
        path=original/f'reset-{sequence}.json'
        base.require(original.is_absolute() and original==original.resolve() and original.is_dir()
            and not path.exists() and not path.is_symlink() and not destination.exists()
            and not destination.is_symlink() and destination==destination.resolve()
            and destination.resolve().is_relative_to(original),
            'fresh bounded native reset metadata/destination')
        base.require('--oracle' not in stage.spec['argv'] or base.option(stage.spec['argv'],'--oracle')=='',
                     'persistent rolling never accepts an oracle file')
        descriptor=dict(schema=RESET_SCHEMA,stage_id=stage.spec['id'],global_sequence=sequence,
            previous_epoch=previous_epoch,next_epoch=epoch,previous_request_sha256=previous_request,
            next_request_sha256=request,destination=str(destination),oracle='')
        raw=(json.dumps(descriptor,sort_keys=True)+'\n').encode()
        base.require(len(raw)<=8192,'native reset descriptor byte bound')
        metadata.append((stage,path,destination,descriptor,raw))
    for stage,path,destination,descriptor,raw in metadata:
        with path.open('xb') as stream:stream.write(raw)
    receipts=[]
    with (output/'reset-commands.jsonl').open('x') as log:
        for stage,path,destination,descriptor,descriptor_raw in metadata:
            guard.check();stage.sock.settimeout(.2)
            sequence=descriptor['global_sequence']
            packet=base.REQUEST.pack(RESET,0,0,0,0,sequence,stage.spec['id'],int(stage.spec['final']))
            descriptor_sha=sha256(descriptor_raw).hexdigest()
            log.write(json.dumps(dict(event='issued',descriptor=descriptor,descriptor_sha256=descriptor_sha,
                request_hex=packet.hex(),previous_wire_sequence=stage.sequence))+'\n');log.flush()
            # Reserve before send; any partial send/receive failure terminates the
            # outer lifecycle. No retry/reset or next request follows failure.
            stage.sequence=sequence
            stage.sock.sendall(packet)
            raw=bytearray();deadline=time.monotonic()+plan['seconds']
            while len(raw)<base.REPLY.size:
                guard.check();base.require(time.monotonic()<deadline,'reset reply lifetime expired')
                try:part=stage.sock.recv(base.REPLY.size-len(raw))
                except socket.timeout:continue
                base.require(part,'reset reply channel closed');raw.extend(part)
            reply=base.REPLY.unpack(raw)
            base.require(reply[:8]==(0,0,0,0,sequence,0 if stage.spec['first'] else 1,
                         stage.spec['id'],int(stage.spec['final'])),'reset raw reply owner/sequence/zero payload')
            receipt_path=destination/'ring-reset.json'
            receipt_raw=evidence.read_bounded(receipt_path,65536)
            receipt=json.loads(receipt_raw)
            validate_receipt(receipt,descriptor,stage,plan['check_policy'],descriptor_sha)
            record=dict(stage_id=stage.spec['id'],descriptor=descriptor,descriptor_path=str(path),
                descriptor_sha256=descriptor_sha,receipt=receipt,receipt_path=str(receipt_path),
                receipt_sha256=sha256(receipt_raw).hexdigest(),native_output=str(destination),reply_hex=bytes(raw).hex())
            receipts.append(record)
            log.write(json.dumps(dict(event='completed',**record))+'\n');log.flush()
    # Only after every native owner attests cold state may Python replace its
    # target/provider ledgers. start_async does not reset the global sequence.
    for stage in stages:
        base.require(not any(stage.shared),'native reset did not invalidate complete shared publication mapping')
        stage.start_async()
        stage.sock.settimeout(.2)
        if hasattr(stage,'handoff'):del stage.handoff
    quiescent(stages)
    return receipts


def run(stages, plan, guard, output, *, suite=None, drive=None):
    raw=evidence.read_bounded(plan['suite'],4*1024**2)
    base.require(sha256(raw).hexdigest()==plan['suite_sha256'],'cold inputs changed before execution')
    loaded=json.loads(raw)
    base.require(suite is None or suite==loaded,'test inputs differ from admitted runtime inputs')
    rows=validate_suite(loaded,plan,plan['suite_prompt_count'])
    drive=bridge.drive if drive is None else drive
    output=Path(output);results=[];epoch=0;request=plan['request_sha256'];inventory=None
    try:
        for index,row in enumerate(rows):
            guard.check();quiescent(stages)
            destination=output/f"request-{index:02d}-{row['id']}";destination.mkdir(mode=0o700)
            next_epoch=epoch+1;next_request=request_identity(plan,row,index,next_epoch)
            before_sequences=[stage.sequence for stage in stages]
            started_reset=time.monotonic()
            receipts=reset(stages,plan,guard,destination,previous_epoch=epoch,previous_request=request,
                           epoch=next_epoch,request=next_request)
            current_inventory=[r['receipt']['allocation_inventory_after_sha256'] for r in receipts]
            base.require(inventory is None or current_inventory==inventory,'allocation inventory changed between requests')
            inventory=current_inventory
            reset_seconds=time.monotonic()-started_reset
            epoch,request=next_epoch,next_request
            request_plan=dict(plan,epoch=epoch,request_sha256=request,prompt_tokens=row['prompt_tokens'],max_new=row['max_new'])
            base.save(destination/'request-plan.json',request_plan)
            for stage in stages:stage.plan=request_plan
            initial_sequences=[stage.sequence for stage in stages]
            started=time.monotonic()
            result=drive(stages,request_plan,guard,destination,epoch=epoch)
            finished=time.monotonic();quiescent(stages)
            outputs=result['output_ids']
            base.require(result.get('cancelled') is False and result.get('cancelled_provider_incomplete') is not True,
                         'cancelled request cannot qualify cold persistent completion')
            base.require(1<=len(outputs)<=row['max_new'] and (len(outputs)==row['max_new'] or outputs[-1] in plan['eos_token_ids'])
                and result['input_position']==len(row['prompt_tokens'])+len(outputs)-1,
                'complete target-owned output boundary')
            base.require(result['provider_serial']==result['provider_pairs']==result['input_position']-1,
                         'complete fresh canonical provider progression')
            final_sequences=[stage.sequence for stage in stages]
            timing=evidence.timing_from_tokens(destination/'tokens.jsonl',outputs,started,finished)
            # Full trace/proposal lists remain in per-request evidence. Avoid
            # copying all long-suite event payloads into every outer summary.
            result_path=destination/'driver-result.json';base.save(result_path,result)
            compact={key:value for key,value in result.items()
                     if key not in ('events','issued_proposals','rejected_proposals')}
            dump_sequences=[]
            if plan['dump_each']:
                for stage in stages:
                    stage.command(4,position=2000000000+index);dump_sequences.append(stage.sequence)
            record=dict(schema='ownrt.persistent-rolling-request-result.v1',passed=True,id=row['id'],index=index,
                epoch=epoch,request_sha256=request,check_policy=plan['check_policy'],cached_tokens=0,
                cold_state_evidence='all native reset receipts validated before first ROW',
                prompt_tokens=len(row['prompt_tokens']),prompt_token_sha256=evidence.token_sha(row['prompt_tokens']),
                output_ids=outputs,output_token_sha256=evidence.token_sha(outputs),reset_seconds=reset_seconds,
                reset_receipts=receipts,previous_sequences=before_sequences,initial_sequences=initial_sequences,
                final_sequences=final_sequences,post_dump_sequences=[stage.sequence for stage in stages],
                dump_sequences=dump_sequences,timing=timing,driver_result=compact,
                driver_result_path=str(result_path),driver_result_sha256=base.digest(result_path),
                request_started_monotonic_s=started,request_finished_monotonic_s=finished,
                process_reused=True,prompt_state_reused=False,speed_claim=False)
            base.save(destination/'result.json',record);results.append(record)
            guard.validate(guard.obs.observe())
    except Exception as error:
        base.save(output/'suite-partial.json',dict(passed=False,completed=len(results),error=repr(error),requests=results))
        raise
    rates=[item['timing']['decode_tokens_per_second'] for item in results]
    summary=dict(schema='ownrt.persistent-rolling-suite-result.v1',passed=True,requests=results,
        request_count=len(results),check_policy=plan['check_policy'],cached_tokens=0,process_launches_by_harness=0,
        last_request_id=results[-1]['id'],final_input_position=results[-1]['driver_result']['input_position'],
        final_output_ids=results[-1]['output_ids'],final_output_scope='last request only',
        decode_median_tokens_per_second=statistics.median(rates) if all(rate is not None for rate in rates) else None,
        diagnostic_only=plan['check_policy']=='qualification',speed_claim=False,
        limits='Controller completion only; independent per-request reset/provenance/state/output qualification required. Decode interval excludes reset/dump; no prompt state reuse. No clean-host/service/performance certification.')
    base.save(output/'suite-result.json',summary)
    return summary
