#!/usr/bin/env python3
"""Qualify actual canonical-provider survival through scripted target rollback.

This explicit v5 proof never promotes quiescent v4 evidence or claims rolling
proposal consumption. All work is CPU-only against a terminal completed run.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from finalize_ring_live_proof import read,lines,need,HERE,compare,identity,save,token_hash,compressed,retain_bundle,draft_compare
from finalize_ring_proof import audit_native
from pending_provider_trace_audit import audit_controller


def full_row(row,prompt_length,request):
    return dict(epoch=0,id=row['id'],parent=row['parent'],ticket=row['row_sequence'],position=row['position'],
                token=row['token'],fixture=max(0,row['position']-prompt_length+2),tentative=row['tentative'],
                request=request,before=row['before'].hex(),after=row['after'].hex())


def audit_provider(batches,native,reference,replay,prompt_length,att,request):
    contexts=replay['providers'];pairs=reference['canonical_pairs'];depths={r['seed_position']:r for r in reference['depth2_rows']}
    need(len(batches)==len(native)==len(contexts)==len(pairs)==att['provider_trace_records'] and att['provider_trace_omitted']==0,
         'complete controller/native canonical provider cohort')
    observed=[];pending=[]
    for position,(batch,row,context,want) in enumerate(zip(batches,native,contexts,pairs),1):
        seed,parent=context['seed'],context['parent'];head=position>=prompt_length-1;guesses=depths[position]['guesses'] if head else []
        need((want['position'],want['token'],want['head'])==(position,seed['token'],head),'canonical reference input/head identity')
        need((batch['epoch'],batch['request_sha256'],batch['sequence'],batch['provider_serial'],batch['seed_row'],batch['parent_row'],
              batch['seed_position'],batch['restored_position'],batch['seed_prefix_sha256'],batch['final_commit'])
             ==(0,request,context['sequence'],position,seed['id'],parent['id'],position,position,seed['after'].hex(),parent['accept_sequence']),
             'provider actual seed/parent/prefix/command differs')
        need(batch['parent_hidden_sha256']==want['hidden_sha256'] and batch['guesses']==guesses
             and batch['available_depth']==len(guesses) and (guesses[0] if head else -1)==want['proposal']
             and batch['restored'] is True and batch['speculative_target_use'] is False,'actual d1/d2 or raw hidden identity differs')
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
        need(row['mutable_bytes_verified'] is head and row['snapshot_bytes']==(att['provider_private_bytes'] if head else 0),
             'native recursive restore byte proof differs')
        observed.append([position,seed['token'],head,want['hidden_sha256']])
        if context['pending']:pending.append((position,len(context['pending'])))
    need(token_hash(observed)==reference['canonical_draft_input_identity']['pair_sequence_sha256'],'ordered actual true-pair digest differs')
    head_count=sum(r[2] for r in observed)
    need(head_count==reference['expected_recursive_captures']==reference['expected_recursive_restores']
         ==att['provider_snapshot_captures']==att['provider_snapshot_restores']==att['provider_byteverified_restore_count'],
         'complete recursive restore count differs')
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


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--reference',type=Path,default=HERE/'live-pp4-proof');a=p.parse_args()
    run,out,reference=a.run.resolve(),a.out.resolve(),a.reference.resolve()
    plan,result,original=(read(run/n) for n in ('plan.json','pending-ring-live-result.json','result.json'))
    need(plan['schema']=='ownrt.pending-ring-live-driver-plan.v1' and result['schema']=='ownrt.pending-ring-live-driver-result.v1'
         and plan['mode']==result['mode']=='pending-ring-live-depth2','explicit pending-provider plan/result required')
    need(result['lifecycle_result_sha256']==identity(run/'result.json')['sha256'] and result['plan_sha256']==identity(run/'plan.json')['sha256']
         and all(result.get(k)==v for k,v in original.items() if k not in ('schema','mode')),'pending wrapper changed original evidence')
    need(result['passed'] is True and result['error'] is None and result['live_pids']==[]
         and result['returncodes']=={str(s['id']):0 for s in plan['stages']},'clean terminal native owners required')
    need(plan['verify_restore'] is True and plan['verify_recursive_restore'] is True and plan['verify_provider_survival'] is True
         and plan['use_proposals'] is False and plan['draft_training'] is False and plan['scripted_tentative_inputs'] is True
         and result['actual_provider'] is True and result['scripted_tentative_inputs'] is True and result['speed_claim'] is False,
         'verified diagnostic pending-provider policy required')
    canonical_request=dict(model=plan['model_identity_sha256'],prompt=plan['prompt_tokens'],context=plan['context'],
        max_new=plan['max_new'],vocab=plan['vocab'],eos=plan['eos_token_ids'],mode='quiescent-ring-live-depth2')
    parent_sha=hashlib.sha256(json.dumps(canonical_request,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    request=hashlib.sha256(json.dumps(dict(parent_request=parent_sha,cases=plan['pending_cases'],mode='pending-ring-live-depth2'),
                                        sort_keys=True,separators=(',',':')).encode()).hexdigest()
    need(request==plan['request_sha256'],'pending request/case identity differs')
    recursive_path=Path(plan['recursive_reference']);recursive=read(recursive_path)
    need(identity(recursive_path)['sha256']==plan['pins'][str(recursive_path)],'recursive reference pin differs')
    need(read(reference/'summary.json')['passed'] is True,'accepted state reference required')
    draft_reference=read(reference/'draft-state-set.json')
    need(recursive['canonical_draft_input_identity']==draft_reference['input_identity'],'canonical draft semantic identity differs')
    need(result['output_ids']==recursive['target_output_ids'] and len(result['output_ids'])==plan['max_new'],'exact complete target output IDs required')
    inputs=plan['prompt_tokens']+result['output_ids'][:-1]
    need(result['input_position']==len(inputs) and result['provider_pairs']==result['provider_serial']==len(inputs)-1,'target/provider terminal frontier')
    argv=plan['stages'][0]['argv'];draft_manifest=Path(argv[argv.index('--draft-manifest')+1])
    need(identity(draft_manifest)['sha256']==plan['pins'][str(draft_manifest)]==plan['draft_model_sha256']
         ==recursive['canonical_draft_input_identity']['draft_model_sha256'],'pinned actual draft tensor identity differs')
    schedule=lines(run/'schedule.jsonl');replay=audit_controller(schedule,inputs,request,len(plan['stages']))
    batches=lines(run/'provider-batches.jsonl');coverage=read(run/'pending-provider-coverage.json')
    need(coverage==result['pending_provider'],'pending coverage differs from terminal')
    need([(r['index'],r['token']) for r in lines(run/'tokens.jsonl')]==list(enumerate(result['output_ids'])),'target output publication trace differs')
    out.mkdir(parents=True,exist_ok=False)
    for name in ('plan.json','result.json','pending-ring-live-result.json','admission.json','unit.json','schedule.jsonl','tokens.jsonl',
                 'provider-batches.jsonl','pending-provider-coverage.json'):
        shutil.copyfile(run/name,out/name)
    shutil.copyfile(recursive_path,out/'recursive-reference.json')
    draft_dump=Path(plan['stages'][0]['native_output'])/'state-2147483647.draft'
    draft_set=dict(schema='ownrt.draft-state-set.v1',dump=str(draft_dump),input_identity=recursive['canonical_draft_input_identity'],
        provenance=dict(plan=identity(run/'plan.json'),reference=identity(recursive_path),draft_manifest=identity(draft_manifest)))
    save(out/'draft-state-set.json',draft_set)
    candidate=dict(schema='ownrt.pipeline-state-set.v5',mode='verified-ring-pending-provider',layer_count=plan['boundaries'][-1],
        require_byte_verified_restores=True,require_provider_byte_verified_restores=True,provider_borrow_mode='pending-target',
        require_provider_survival_checks=True,required_provider_pending_depths=[1,2],draft_input_identity=draft_set['input_identity'],
        ring_request_sha256=request,ring_epoch=0,input_identity=dict(model_sha256=plan['model_identity_sha256'],
            prompt_token_sha256=token_hash(plan['prompt_tokens']),output_token_sha256=token_hash(result['output_ids']),
            arithmetic=plan['activation_dtype'],position=len(inputs)),stages=[])
    raw_bundles=[];audits=[];provider_audit=survival_audit=None
    for stage in plan['stages']:
        index=stage['id'];native=Path(stage['native_output']);local=out/f'stage{index}';local.mkdir()
        dump=native/'state-2147483647';retain_bundle(dump,local/dump.name,raw_bundles)
        for name in ('launch-plan.json','pipeline-stage.json','ring-checkpoint-layout.json','ring.jsonl','ring-quiescence.json',
                     'state-2147483647.ring-state.json','ring-draft-batches.jsonl','ring-final-peer.json','ring-provider-survival.jsonl','draft-rows.jsonl'):
            if (native/name).is_file():shutil.copyfile(native/name,local/name)
        item=dict(id=index,begin=stage['begin'],end=stage['end'],dump=str(dump),plan=str(local/'launch-plan.json'),
            metadata=str(local/'pipeline-stage.json'),quiescence=str(native/'state-2147483647.ring-state.json'))
        att=read(native/'state-2147483647.ring-state.json');rows=lines(native/'ring.jsonl')
        audits.append(audit_native(rows,replay['sent'][index],replay['created'],inputs,att,stage['final']))
        if index==0:
            item.update(draft_state_set=str(out/'draft-state-set.json'),provider_survival=str(native/'ring-provider-survival.jsonl'))
            retain_bundle(draft_dump,local/draft_dump.name,raw_bundles)
            provider_audit=audit_provider(batches,lines(native/'ring-draft-batches.jsonl'),recursive,replay,len(plan['prompt_tokens']),att,request)
            survival_audit=bind_survival(lines(native/'ring-provider-survival.jsonl'),replay,batches,recursive,len(plan['prompt_tokens']),request)
            peer=read(native/'ring-final-peer.json');peer_path=Path(plan['final_shared']);st=peer_path.stat()
            need(peer['readonly'] is True and peer['path']==str(peer_path) and (peer['device'],peer['inode'],peer['bytes'])
                 ==(st.st_dev,st.st_ino,st.st_size),'readonly final-owner map provenance differs')
        candidate['stages'].append(item)
    cases=plan['pending_cases'];first,second=cases[0]['seed_position'],cases[1]['seed_position']
    need([c['kind'] for c in cases]==['two-row-abort','accept-then-one-row-abort']
         and provider_audit['pending_borrows']==[(first,2),(second,2),(second+1,1)],'configured exact pending borrow cohort differs')
    need([(e['provider_position'],len(e['discarded'])) for e in replay['aborts']]==[(first,2),(second+1,1)],'configured target rejection/survival cohort differs')
    need(coverage['canonical_pairs']==coverage['provider_serial']==len(inputs)-1 and coverage['pending_borrows']==plan['expected_pending_borrows']=={'1':1,'2':2}
         and len(coverage['aborts'])==survival_audit['checks']==plan['expected_survival_checks']==2
         and survival_audit['discarded_rows']==plan['expected_discarded_rows']==3,'required pending coverage totals differ')
    need(coverage['aborts']==[{k:r[k] for k in r if k!='event'} for r in schedule if r['event']=='target-verified-suffix-abort'],
         'pending coverage abort records differ from command trace')
    save(out/'candidate-state-set.json',candidate)
    target=compare.compare(compare.load_set(reference/'candidate-state-set.json'),compare.load_set(out/'candidate-state-set.json'))
    draft=draft_compare.compare(draft_compare.load_set(reference/'draft-state-set.json'),draft_compare.load_set(out/'draft-state-set.json'))
    compressed(out/'target-comparison.json.gz',target);compressed(out/'draft-comparison.json.gz',draft)
    legacy=read(HERE/'live-draft-legacy-prefix.json')
    need([{k:r[k] for k in ('position','token','head','proposal')} for r in recursive['canonical_pairs'] if r['head']]==legacy['rows'],
         'canonical d1 proposals differ from retained legacy control')
    summary=dict(schema='ownrt.pending-provider-proof.v1',passed=target['passed'] and draft['passed'],source_run=str(run),
        target_state_exact=target['passed'],draft_state_exact=draft['passed'],output_tokens_exact=True,legacy_proposals_exact=True,
        target_buffer_count=len(target['compared_source_keys']),draft_allocation_count=len(draft['compared_source_keys']),
        output_tokens=len(result['output_ids']),input_rows=len(inputs),boundaries=plan['boundaries'],
        provider_pairs=provider_audit['pairs'],recursive_depth2_pairs=provider_audit['depth2_pairs'],pending_borrows=coverage['pending_borrows'],
        provider_survival_passed=survival_audit['passed'],provider_survival_checks=survival_audit['checks'],
        provider_survival_discarded_rows=survival_audit['discarded_rows'],provider_survival_advanced_checks=survival_audit['checks'],
        provider_audit=provider_audit,survival_audit=survival_audit,native_command_audits=audits,raw_bundles=raw_bundles,
        raw_bytes=sum(r['bytes'] for r in raw_bundles),actual_provider=True,scripted_tentative_inputs=True,
        recursive_proposals_consumed=False,speed_claim=False,original_plan=identity(run/'plan.json'),
        original_result=identity(run/'pending-ring-live-result.json'),finalizer=identity(Path(__file__)),
        comparator=identity(Path(compare.__file__)),scope='Actual canonical provider state/private backup/host/Sequence survive target suffix abort with two and one pending rows, and final target/draft states match accepted replay. Tentative target inputs are scripted; recursive proposals remain discarded. No rolling, speed or independent CPU arithmetic qualification.')
    save(out/'summary.json',summary)
    (out/'RESULT.md').write_text(f'''# Provider survival through target rollback: {'PASSED' if summary['passed'] else 'FAILED'}

All {summary['output_tokens']} output tokens, {summary['target_buffer_count']} target buffers and
{summary['draft_allocation_count']} canonical draft allocations match accepted replay.
All {summary['provider_pairs']} canonical true pairs and {summary['recursive_depth2_pairs']} recursive predictions match.
Two target aborts discarded three rows after provider advancement; full canonical,
pinned and private bytes, host/Sequence state and prepared descriptor identities survived.
Provider calls exercised pending depths 2, 2 and 1, including older ACCEPT without rewind.

[Summary](summary.json), [target proof](target-comparison.json.gz),
[draft proof](draft-comparison.json.gz), [native survival receipts](stage0/ring-provider-survival.jsonl).
Tentative inputs were scripted to force actual target rejection. Recursive proposals
were discarded. This is not rolling inference, a speed result or CPU-reference equivalence.
Raw bundles remain external with retained metadata pending durable archival.
''')
    print(json.dumps({k:summary[k] for k in ('passed','target_buffer_count','draft_allocation_count','provider_survival_checks','pending_borrows')}))
    return 0 if summary['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
