#!/usr/bin/env python3
"""Strict two-request persistent rolling parity with a fixed diagnostic policy."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import shutil
import struct

from finalize_ring_live_proof import need,HERE,compare,identity,save,token_hash,compressed,retain_bundle,draft_compare
from finalize_ring_proof import audit_native
from finalize_rolling_provider_proof import read,lines
from compare_rolling_provider_survival import survival_bytes
from persistent_rolling_trace_audit import audit_controller
from persistent_rolling_reset_audit import audit_reset


def full_row(row,prompt_length,request):
    return dict(epoch=row['epoch'],id=row['id'],parent=row['parent'],ticket=row['row_sequence'],position=row['position'],
                token=row['token'],fixture=max(0,row['position']-prompt_length+2),tentative=row['tentative'],
                request=request,before=row['before'].hex(),after=row['after'].hex())


def audit_provider(batches,native,reference,replay,prompt_length,att,request,*,epoch,policy):
    contexts=replay['providers'];pairs=reference['canonical_pairs'];depths={r['seed_position']:r for r in reference['depth2_rows']}
    need(len(batches)==len(native)==len(contexts)==len(pairs)==att['provider_trace_records'] and att['provider_trace_omitted']==0,
         'complete controller/native canonical provider cohort')
    observed=[];pending=[]
    for position,(batch,row,context,want) in enumerate(zip(batches,native,contexts,pairs),1):
        seed,parent=context['seed'],context['parent'];head=position>=prompt_length-1;guesses=depths[position]['guesses'] if head else []
        need((want['position'],want['token'],want['head'])==(position,seed['token'],head),'canonical reference input/head identity')
        need((batch['epoch'],batch['request_sha256'],batch['sequence'],batch['provider_serial'],batch['seed_row'],batch['parent_row'],
              batch['seed_position'],batch['restored_position'],batch['seed_prefix_sha256'],batch['final_commit'])
             ==(epoch,request,context['sequence'],position,seed['id'],parent['id'],position,position,seed['after'].hex(),parent['accept_sequence']),
             'provider actual seed/parent/prefix/command differs')
        need(batch['parent_hidden_sha256']==want['hidden_sha256'] and batch['guesses']==guesses
             and batch['available_depth']==len(guesses) and (guesses[0] if head else -1)==want['proposal']
             and batch['restored'] is True and batch['speculative_target_use'] is True,'actual d1/d2 or raw hidden identity differs')
        need((batch['target_physical'],batch['target_committed'],batch['pending_depth'],batch['pending_target_rows'],
              batch['accepted_seed_sequence'],batch['original_seed_tentative'])
             ==(context['physical'],context['committed'],len(context['pending']),context['pending'],seed['accept_sequence'],seed['tentative']),
             'provider pending suffix/accepted seed differs')
        need((row['sequence'],row['provider_serial'],row['target_pending_depth'],row['seed_row'],row['parent_row'],row['seed_position'],
              row['confirmed_token'],row['fixture'],row['parent_final_ticket'],row['parent_final_commit'],row['hidden_sha256'],
              row['guesses'],row['restored_position'])
             ==(context['sequence'],position,len(context['pending']),seed['id'],parent['id'],position,seed['token'],
                max(0,position-prompt_length+2),parent['row_sequence'],parent['accept_sequence'],want['hidden_sha256'],guesses,position),
             'native provider provenance/result differs from actual owner commands')
        need(row['mutable_bytes_verified'] is (head and policy=='qualification') and row['snapshot_bytes']==(att['provider_private_bytes'] if head else 0),
             'native recursive restore byte proof differs')
        observed.append([position,seed['token'],head,want['hidden_sha256']])
        if context['pending']:pending.append((position,len(context['pending'])))
    need(token_hash(observed)==reference['canonical_draft_input_identity']['pair_sequence_sha256'],'ordered actual true-pair digest differs')
    head_count=sum(r[2] for r in observed)
    need(head_count==reference['expected_recursive_captures']==reference['expected_recursive_restores']
         ==att['provider_snapshot_captures']==att['provider_snapshot_restores'],
         'complete recursive restore count differs')
    need(att['provider_byteverified_restore_count']==(head_count if policy=='qualification' else 0), 'fixed provider byte verification counter differs')
    return dict(passed=True,pairs=len(observed),depth2_pairs=head_count,pending_borrows=pending,pair_sequence_sha256=token_hash(observed))


def bind_survival(records,replay,batches,reference,prompt_length,request):
    need(len(records)==len(replay['aborts']),'native/controller survival record count differs')
    frontiers=[]
    for record,event in zip(records,replay['aborts']):
        need(record['abort_sequence']==event['sequence'] and record['oldest']==full_row(event['oldest'],prompt_length,request)
             and record['discarded_row_ids']==[r['id'] for r in event['discarded']], 'native survival receipt not bound to actual ABORT')
        captures=[dict(row=full_row(r,prompt_length,request),position=r['provider_position_at_capture'],serial=r['provider_serial_at_capture'])
                  for r in event['discarded']]
        need(record['provider_at_capture']==captures,'provider survival capture provenance differs from issued work')
        payload=json.loads(record['before_payload']);position=event['provider_position'];context=replay['providers'][position-1]
        need(payload['position']==payload['provider_serial']==position==event['provider_serial']
             and payload['sequence']['last_sequence']==context['sequence']
             and payload['sequence']['last_commit']==context['parent']['accept_sequence']
             and payload['sequence']['last_seed']==full_row(context['seed'],prompt_length,request),
             'provider host/Sequence survival not tied to latest actual provider command')
        need(payload['sequence']['last_result']['guesses']==batches[position-1]['guesses'], 'surviving provider result differs')
        head_count=sum(r['head'] for r in reference['canonical_pairs'][:position])
        need(payload['host']['captures']==payload['host']['restores']==payload['host']['verified_restores']==head_count,
             'surviving recursive counters differ from actual canonical history')
        frontiers.append(dict(provider_position=position,current_extent=payload['host']['current']['extent'],
            saved_extent=payload['host']['saved']['extent'],discarded_rows=len(event['discarded']),
            captured_provider_position=event['oldest']['provider_position_at_capture'],abort_sequence=event['sequence']))
    return dict(passed=True,checks=len(records),discarded_rows=sum(len(e['discarded']) for e in replay['aborts']),frontiers=frontiers)


def validate_identity(plan,suite,terminal,reference):
    policy=plan['check_policy'];enabled=policy=='qualification'
    need(plan['schema']=='ownrt.persistent-rolling-plan.v1' and plan['mode']=='persistent-rolling'
         and policy in ('qualification','measured') and plan['persistent_requests'] is True
         and plan['use_proposals'] is True and plan['dump_each'] is True and plan['suite_prompt_count']==2,
         'explicit two-request full-state persistent proof required')
    need(all(plan[k] is enabled for k in ('verify_restore','verify_recursive_restore','verify_provider_survival'))
         and plan['draft_training'] is False,'fixed process policy cannot be toggled')
    need(terminal['schema']=='ownrt.persistent-rolling-result.v1' and terminal['mode']=='persistent-rolling'
         and terminal['check_policy']==policy and terminal['passed'] is True and terminal['error'] is None
         and terminal['live_pids']==[] and terminal['returncodes']=={str(s['id']):0 for s in plan['stages']}
         and terminal['actual_provider'] is True and terminal['scripted_oracle_assisted'] is False,
         'clean persistent terminal and actual-provider mode required')
    identity=dict(model=plan['model_identity_sha256'],draft_manifest=plan['draft_model_sha256'],draft_experts=plan['draft_experts'],
        prompt=plan['prompt_tokens'],context=plan['context'],max_new=plan['max_new'],vocab=plan['vocab'],eos=plan['eos_token_ids'],
        config_sha256=plan['config_sha256'],mode=plan['mode'],check_policy=policy)
    need(hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()==plan['request_sha256'],
         'persistent process request digest differs')
    need(set(suite)=={'schema','model_identity_sha256','activation_dtype','eos_token_ids','prompts'}
         and suite['schema']=='ownrt.persistent-rolling-inputs.v1' and len(suite['prompts'])==2,
         'strict runtime input suite with no output oracle required')
    need(suite['model_identity_sha256']==plan['model_identity_sha256']==reference['canonical_draft_input_identity']['model_sha256']
         and suite['activation_dtype']==plan['activation_dtype']=='F32' and suite['eos_token_ids']==plan['eos_token_ids']
         and plan['draft_model_sha256']==reference['canonical_draft_input_identity']['draft_model_sha256'],
         'independent baseline model/arithmetic/draft identity differs')
    need(reference['passed'] is True and all(plan[k]==reference['canonical_draft_input_identity'][k] for k in ('context','vocab','draft_experts')),
         'persistent/reference context and draft geometry differs')
    ids=set()
    for row in suite['prompts']:
        need(set(row)=={'id','prompt_tokens','max_new'} and isinstance(row['id'],str)
             and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',row['id']) and row['id'] not in ids,
             'unique safe oracle-free runtime request')
        ids.add(row['id'])
        need(len(row['prompt_tokens'])==reference['prompt_tokens'] and token_hash(row['prompt_tokens'])==reference['target_prompt_token_sha256']
             and row['max_new']==len(reference['target_output_ids'])==32,'first persistent gate requires exact two32 cohort')
    return policy


def audit_timing(rows,outputs,record):
    need([(r['index'],r['token']) for r in rows]==list(enumerate(outputs)),'complete observed token clock identity')
    stamps=[r['committed_monotonic_s'] for r in rows];start=record['request_started_monotonic_s'];end=record['request_finished_monotonic_s']
    need(all(type(t)in (int,float) and math.isfinite(t) for t in stamps+[start,end]) and start<=stamps[0]<=stamps[-1]<=end
         and all(a<=b for a,b in zip(stamps,stamps[1:])),'request-local monotonic clock window')
    span=stamps[-1]-stamps[0];numerator=len(outputs)-1
    expected=dict(first_token_seconds=stamps[0]-start,full_response_seconds=end-start,committed_output_span_seconds=span,
        decode_intervals=numerator,decode_tokens_per_second=numerator/span if numerator and span>0 else None,
        full_response_tokens_per_second=len(outputs)/(end-start) if end>start else None)
    need(all(record['timing'][k]==v for k,v in expected.items()),'reported timing differs from actual recorded observations')
    return dict(numerator=numerator,denominator_seconds=span,first_timestamp=stamps[0],last_timestamp=stamps[-1],
        observer='controller committed-output observation',window='first through last output, excludes RESET and DUMP',certified=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--reference',type=Path,default=HERE/'live-pp4-proof')
    parser.add_argument('--recursive-reference',type=Path,default=HERE/'recursive-provider-reference-v2.json')
    parser.add_argument('--qualified-reference',type=Path,default=HERE/'persistent-rolling-qualified-proof')
    args=parser.parse_args();run=args.run.resolve();out=args.out.resolve();baseline=args.reference.resolve()
    plan=read(run/'plan.json');terminal=read(run/'persistent-rolling-result.json');original=read(run/'result.json')
    suite_path=Path(plan['suite']);suite=read(suite_path);recursive=read(args.recursive_reference)
    need(terminal['plan_sha256']==identity(run/'plan.json')['sha256'] and terminal['lifecycle_result_sha256']==identity(run/'result.json')['sha256']
         and all(terminal.get(k)==v for k,v in original.items() if k not in ('schema','mode','diagnostic_only')), 'persistent terminal wrapper/source differs')
    policy=validate_identity(plan,suite,terminal,recursive);enabled=policy=='qualification'
    need(identity(suite_path)['sha256']==plan['suite_sha256']==plan['pins'][str(suite_path)]
         and identity(Path(plan['config']))['sha256']==plan['config_sha256'],'admitted runtime inputs/config changed')
    source_pins=[]
    for name,want in plan['pins'].items():
        if name.endswith('.py'):
            receipt=identity(Path(name));need(receipt['sha256']==want,'persistent runtime source pin changed');source_pins.append(receipt)
    need(any(p['path'].endswith('/persistent_rolling_suite.py') for p in source_pins)
         and any(p['path'].endswith('/persistent_rolling_driver.py') for p in source_pins),'persistent code closure incomplete')
    argv=plan['stages'][0]['argv'];draft_manifest=Path(argv[argv.index('--draft-manifest')+1])
    need(identity(draft_manifest)['sha256']==plan['draft_model_sha256']==plan['pins'][str(draft_manifest)],'actual draft manifest pin differs')
    suite_result=read(run/'suite-result.json')
    need(suite_result['schema']=='ownrt.persistent-rolling-suite-result.v1' and suite_result['passed'] is True
         and suite_result['check_policy']==policy and suite_result['request_count']==len(suite_result['requests'])==2
         and suite_result['process_launches_by_harness']==0 and suite_result['cached_tokens']==0,'complete one-process cold request suite required')
    need(read(baseline/'summary.json')['passed'] is True,'accepted reference proof required')
    draft_ref=read(baseline/'draft-state-set.json')
    need(draft_ref['input_identity']==recursive['canonical_draft_input_identity'],'accepted canonical true-pair identity differs')
    target_gold=compare.load_set(baseline/'candidate-state-set.json');draft_gold=draft_compare.load_set(baseline/'draft-state-set.json')
    qualified=None
    if not enabled:
        qualified=args.qualified_reference.resolve();q=read(qualified/'summary.json')
        need(q['schema']=='ownrt.persistent-rolling-proof.v1' and q['passed'] is True and q['check_policy']=='qualification'
             and q['all_requests_full_state_parity'] is True and q['requests']==2,'measured parity requires accepted persistent qualification')
    out.mkdir(parents=True,exist_ok=False)
    for name in ('plan.json','result.json','persistent-rolling-result.json','suite-result.json','admission.json','unit.json'):
        shutil.copyfile(run/name,out/name)
    shutil.copyfile(suite_path,out/'runtime-inputs.json');shutil.copyfile(args.recursive_reference,out/'recursive-reference.json')
    save(out/'runtime-source-identities.json',source_pins)
    previous_request=plan['request_sha256'];previous_sequences=[0]*len(plan['stages']);previous_position=0;inventories=None
    summaries=[];all_raw=[]
    for index,(row,record) in enumerate(zip(suite['prompts'],suite_result['requests'])):
        name=f"request-{index:02d}-{row['id']}";request_run=run/name;request_out=out/name;request_out.mkdir()
        need(record==read(request_run/'result.json') and record['index']==index,'request result/outer suite differs')
        reset=audit_reset(plan,row,record,lines(request_run/'reset-commands.jsonl'),previous_request=previous_request,
            previous_sequences=previous_sequences,previous_target_position=previous_position,prior_inventories=inventories,
            read_raw=lambda p:survival_bytes(p)[0])
        epoch=reset['epoch'];request=reset['request_sha256'];outputs=record['output_ids'];input_rows=row['prompt_tokens']+outputs[:-1]
        need(outputs==recursive['target_output_ids'] and record['driver_result']['input_position']==len(input_rows),'exact per-request canonical output required')
        need(record['prompt_token_sha256']==hashlib.sha256(b''.join(struct.pack('<I',t) for t in row['prompt_tokens'])).hexdigest()
             and record['output_token_sha256']==hashlib.sha256(b''.join(struct.pack('<I',t) for t in outputs)).hexdigest(),'request token array SHA differs')
        driver=read(request_run/'driver-result.json')
        need(record['driver_result_path']==str(request_run/'driver-result.json')
             and identity(request_run/'driver-result.json')['sha256']==record['driver_result_sha256']
             and {k:v for k,v in driver.items() if k not in ('events','issued_proposals','rejected_proposals')}==record['driver_result'],
             'full/compact driver evidence differs')
        need(driver['cancelled'] is False and driver['cancelled_provider_incomplete'] is False,'cancelled request cannot qualify')
        request_plan=read(request_run/'request-plan.json')
        expected_plan=dict(plan,epoch=epoch,request_sha256=request,prompt_tokens=row['prompt_tokens'],max_new=row['max_new'])
        need(request_plan==expected_plan,'request plan changed process policy/identity')
        stages=[dict(stage,native_output=record['reset_receipts'][i]['native_output']) for i,stage in enumerate(plan['stages'])]
        native0=Path(stages[0]['native_output']);metadata=read(native0/'pipeline-stage.json')
        batches=lines(request_run/'provider-batches.jsonl')
        replay=audit_controller(lines(request_run/'commands.jsonl'),lines(request_run/'final-records.jsonl'),batches,row['prompt_tokens'],outputs,
            request,len(stages),metadata['stream_bytes'],plan['vocab'],plan['context'],epoch=epoch,
            initial_sequences=record['initial_sequences'],check_policy=policy,max_new=row['max_new'])
        need([s['last_sequence'] for s in replay['states']]==record['final_sequences'],'request ending global sequences differ')
        need(replay['actual_proposal_rows']>0,'actual proposals must be consumed in each qualification request')
        need([e for e in lines(request_run/'schedule.jsonl') if e['event'] not in ('native-reply','issued-proposal')]==driver['events'],
             'request model event journal differs')
        timing=audit_timing(lines(request_run/'tokens.jsonl'),outputs,record)
        for f in ('request-plan.json','result.json','driver-result.json','reset-commands.jsonl','commands.jsonl','final-records.jsonl',
                  'provider-batches.jsonl','schedule.jsonl','tokens.jsonl'):
            shutil.copyfile(request_run/f,request_out/f)
        marker=2000000000+index;dump_name=f'state-{marker}';draft_dump=native0/(dump_name+'.draft')
        draft_set=dict(schema='ownrt.draft-state-set.v1',dump=str(draft_dump),input_identity=recursive['canonical_draft_input_identity'])
        save(request_out/'draft-state-set.json',draft_set)
        candidate=dict(schema='ownrt.pipeline-state-set.v7',mode='persistent-rolling',controller_mode='persistent-rolling',
            actual_proposals_only=True,verification_policy=policy,layer_count=plan['boundaries'][-1],
            require_byte_verified_restores=enabled,require_provider_byte_verified_restores=enabled,provider_borrow_mode='pending-target',
            require_provider_survival_checks=enabled,required_provider_pending_depths=[],draft_input_identity=draft_set['input_identity'],
            ring_request_sha256=request,ring_epoch=epoch,input_identity=dict(model_sha256=plan['model_identity_sha256'],
                prompt_token_sha256=token_hash(row['prompt_tokens']),output_token_sha256=token_hash(outputs),arithmetic=plan['activation_dtype'],
                position=len(input_rows)),stages=[])
        raw_bundles=[];audits=[];provider=None;survival_records=[]
        for stage in stages:
            number=stage['id'];native=Path(stage['native_output']);local=request_out/f'stage{number}';local.mkdir()
            dump=native/dump_name;retain_bundle(dump,local/dump_name,raw_bundles)
            for f in ('launch-plan.json','pipeline-stage.json','ring-checkpoint-layout.json','ring.jsonl','ring-reset.json','reset.json',
                      dump_name+'.ring-state.json','ring-draft-batches.jsonl','ring-final-peer.json','ring-provider-survival.jsonl'):
                if (native/f).is_file():shutil.copyfile(native/f,local/f)
            item=dict(id=number,begin=stage['begin'],end=stage['end'],dump=str(dump),plan=str(local/'launch-plan.json'),
                metadata=str(local/'pipeline-stage.json'),quiescence=str(native/(dump_name+'.ring-state.json')))
            att=read(native/(dump_name+'.ring-state.json'));native_rows=lines(native/'ring.jsonl')
            need(len(native_rows)==len(replay['sent'][number]) and all(r['tentative'] is e['tentative'] for r,e in zip(native_rows,replay['sent'][number])),
                 'actual native original row flags differ')
            need(all(r['fixture']==max(0,r['position']-len(row['prompt_tokens'])+2) for r in native_rows),'native prompt/head mask differs')
            audits.append(dict(stage=number,**audit_native(native_rows,replay['sent'][number],replay['created'],input_rows,att,stage['final'])))
            if number==0:
                item.update(draft_state_set=str(request_out/'draft-state-set.json'),provider_survival=str(native/'ring-provider-survival.jsonl'))
                retain_bundle(draft_dump,local/draft_dump.name,raw_bundles)
                provider=audit_provider(batches,lines(native/'ring-draft-batches.jsonl'),recursive,replay,len(row['prompt_tokens']),att,request,
                                        epoch=epoch,policy=policy)
                pending={str(d):sum(len(v['pending'])==d for v in replay['providers']) for d in (0,1,2)}
                need(att['provider_pending_borrows']=={k:pending[k] for k in ('1','2')} and att['provider_quiescent_borrows']==pending['0'],
                     'native actual borrow depth counts differ')
                survival_records=lines(native/'ring-provider-survival.jsonl')
                survival_result=bind_survival(survival_records,replay,batches,recursive,len(row['prompt_tokens']),request) if enabled else None
                need(enabled or not survival_records,'measured policy must not invent survival records')
                peer=read(native/'ring-final-peer.json');stat=Path(plan['final_shared']).stat()
                need(peer['readonly'] is True and peer['path']==plan['final_shared'] and (peer['device'],peer['inode'],peer['bytes'])==
                     (stat.st_dev,stat.st_ino,stat.st_size),'per-request final owner mapping provenance differs')
            candidate['stages'].append(item)
        save(request_out/'candidate-state-set.json',candidate)
        target_state=compare.load_set(request_out/'candidate-state-set.json');draft_state=draft_compare.load_set(request_out/'draft-state-set.json')
        target=compare.compare(target_gold,target_state);draft=draft_compare.compare(draft_gold,draft_state)
        compressed(request_out/'target-comparison.json.gz',target);compressed(request_out/'draft-comparison.json.gz',draft)
        qualified_parity=None
        if qualified is not None:
            qualified_summary=read(qualified/'summary.json');qualified_dir=qualified/qualified_summary['request_summaries'][index]['directory']
            qt=compare.compare(compare.load_set(qualified_dir/'candidate-state-set.json'),target_state)
            qd=draft_compare.compare(draft_compare.load_set(qualified_dir/'draft-state-set.json'),draft_state)
            compressed(request_out/'qualified-target-comparison.json.gz',qt);compressed(request_out/'qualified-draft-comparison.json.gz',qd)
            qualified_parity=qt['passed'] and qd['passed'];need(qualified_parity,'measured state differs from qualified persistent state')
        row_summary=dict(passed=target['passed'] and draft['passed'],directory=name,id=row['id'],epoch=epoch,request_sha256=request,
            target_state_exact=target['passed'],draft_state_exact=draft['passed'],target_buffer_count=len(target['compared_source_keys']),
            draft_allocation_count=len(draft['compared_source_keys']),output_tokens=len(outputs),input_rows=len(input_rows),
            check_policy=policy,reset_audit=reset,provider_audit=provider,native_command_audits=audits,pending_borrows=pending,
            provider_survival_evidence='verified' if enabled else 'not-collected',provider_survival_checks=len(survival_records),
            provider_survival_advanced_checks=sum(r['provider_advanced_since_snapshot'] for r in survival_records),
            survival_audit=survival_result,actual_proposal_rows=replay['actual_proposal_rows'],observed_miss_depths=replay['observed_miss_depths'],
            qualified_reference_parity=qualified_parity,timing=timing,raw_bundles=raw_bundles)
        save(request_out/'summary.json',row_summary);summaries.append(row_summary);all_raw.extend(raw_bundles)
        previous_request=request;previous_sequences=reset['post_sequences'];previous_position=len(input_rows);inventories=reset['inventories']
    need(suite_result['final_output_scope']=='last request only' and suite_result['final_output_ids']==recursive['target_output_ids']
         and suite_result['final_input_position']==previous_position,'outer suite final request scope differs')
    summary=dict(schema='ownrt.persistent-rolling-proof.v1',passed=all(r['passed'] for r in summaries),source_run=str(run),
        check_policy=policy,requests=2,output_tokens=sum(r['output_tokens'] for r in summaries),request_summaries=summaries,
        all_requests_full_state_parity=all(r['passed'] for r in summaries),target_state_exact=all(r['target_state_exact'] for r in summaries),
        draft_state_exact=all(r['draft_state_exact'] for r in summaries),output_tokens_exact=True,provenance_passed=True,
        all_cold_resets_checked=True,cold_state_byte_verified=False,mandatory_restore_checks_passed=True,
        byte_verification_enabled=enabled,provider_survival_checks_enabled=enabled,actual_provider=True,actual_proposals_consumed=True,
        scripted_oracle_assisted=False,scripted_tentative_inputs=False,speed_claim=False,early_eos_qualified=False,cancellation_qualified=False,
        qualified_reference_parity=all(r['qualified_reference_parity'] for r in summaries) if qualified else None,
        qualified_reference=identity(qualified/'summary.json') if qualified else None,raw_bundles=all_raw,raw_bytes=sum(r['bytes'] for r in all_raw),
        original_plan=identity(run/'plan.json'),original_result=identity(run/'persistent-rolling-result.json'),
        finalizer=identity(Path(__file__)),comparator=identity(Path(compare.__file__)),
        scope='Two matched full-cap requests with native cold reset, epoch/global wire continuity and exact target/draft state against accepted baseline. Measured policy omits per-operation byte diagnostics honestly; mandatory copy/host/causal checks remain. Cold allocations were not all individually read back. No certified speed, portable deployment or full12-prompt state qualification.')
    save(out/'summary.json',summary)
    (out/'RESULT.md').write_text(f"# Persistent rolling {policy}: {'PASSED' if summary['passed'] else 'FAILED'}\n\n"
        "Both32-output requests match all2,065 target buffers and73 canonical draft allocations against accepted replay. "
        "Epoch/request and global wire sequences, native cold reset receipts and complete actual-proposal histories match.\n\n"
        f"Per-operation byte/survival checks: {'enabled and verified' if enabled else 'disabled; no verification claim'}. "
        "Cold zeroing and host metadata were checked; full cold allocation bytes were not individually read back. No speed claim.\n\n[Summary](summary.json). Raw bundles pending durable archive.\n")
    print(json.dumps(dict(passed=summary['passed'],check_policy=policy,requests=2,output_tokens=summary['output_tokens'])))
    return 0 if summary['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
