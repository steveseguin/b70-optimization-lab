#!/usr/bin/env python3
"""CPU-only v6 qualification of actual rolling proposals and all sealed state."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from finalize_ring_live_proof import read,lines,need,HERE,compare,identity,save,token_hash,compressed,retain_bundle,draft_compare
from finalize_ring_proof import audit_native
from finalize_pending_provider_proof import bind_survival
from rolling_provider_trace_audit import audit_controller
from compare_rolling_provider_survival import survival_bytes


def read(path):
    raw,_=survival_bytes(Path(path))
    return json.loads(raw,object_pairs_hook=compare.BUNDLE.pairs)


def lines(path):
    raw,_=survival_bytes(Path(path))
    return [json.loads(line,object_pairs_hook=compare.BUNDLE.pairs) for line in raw.decode().splitlines()]


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


def validate_plan_result(plan,result,original,recursive):
    need(plan['schema']=='ownrt.rolling-driver-plan.v1' and result['schema']=='ownrt.rolling-driver-result.v1'
         and plan['mode']==result['mode']=='rolling-ring-live-depth2-qualification','explicit rolling plan/result required')
    need(all(result.get(k)==v for k,v in original.items() if k not in ('schema','mode')),'rolling wrapper changed original evidence')
    need(result['passed'] is True and result['error'] is None and result['live_pids']==[]
         and result['returncodes']=={str(s['id']):0 for s in plan['stages']},'clean terminal native owners required')
    need(all(plan.get(k) is True for k in ('rolling_depth2','use_proposals','verify_restore','verify_recursive_restore','verify_provider_survival'))
         and plan['draft_training'] is False and result['actual_provider'] is True and result['scripted_oracle_assisted'] is False
         and result['speed_claim'] is False and result['cancelled'] is False and result['cancelled_provider_incomplete'] is False,
         'normal verified actual rolling completion required')
    need(not any(k in plan for k in ('recursive_reference','scripted_proposal_tokens','force_miss_positions','expected_outputs','pending_cases')),
         'rolling runtime plan contains reference/oracle assistance')
    request_identity=dict(model=plan['model_identity_sha256'],draft_manifest=plan['draft_model_sha256'],draft_experts=plan['draft_experts'],
        prompt=plan['prompt_tokens'],context=plan['context'],max_new=plan['max_new'],vocab=plan['vocab'],eos=plan['eos_token_ids'],
        config_sha256=plan['config_sha256'],mode=plan['mode'])
    request=hashlib.sha256(json.dumps(request_identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    need(request==plan['request_sha256'],'rolling request digest differs')
    need(result['output_ids']==recursive['target_output_ids'] and len(result['output_ids'])==plan['max_new'],
         'exact complete matched reference output IDs required')
    inputs=plan['prompt_tokens']+result['output_ids'][:-1]
    need(result['input_position']==len(inputs) and result['provider_pairs']==result['provider_serial']==len(inputs)-1,
         'rolling target/provider terminal frontier')
    need(plan['epoch']==0 and plan['draft_model_sha256']==recursive['canonical_draft_input_identity']['draft_model_sha256']
         and plan['model_identity_sha256']==recursive['canonical_draft_input_identity']['model_sha256'],
         'independent reference model/draft identity differs')
    need(recursive['passed'] is True and len(plan['prompt_tokens'])==recursive['prompt_tokens']
         and token_hash(plan['prompt_tokens'])==recursive['target_prompt_token_sha256']
         and all(plan[key]==recursive['canonical_draft_input_identity'][key] for key in ('context','vocab','draft_experts'))
         and plan['activation_dtype']=='F32' and recursive['canonical_draft_input_identity']['arithmetic']=='F32-target/BF16-draft',
         'matched reference prompt/arithmetic/draft geometry required')
    return request,inputs


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--reference',type=Path,default=HERE/'live-pp4-proof')
    p.add_argument('--recursive-reference',type=Path,default=HERE/'recursive-provider-reference-v2.json')
    a=p.parse_args();run,out,reference=a.run.resolve(),a.out.resolve(),a.reference.resolve()
    recursive_path=a.recursive_reference.resolve();recursive=read(recursive_path)
    plan,result,original=(read(run/n) for n in ('plan.json','rolling-ring-live-result.json','result.json'))
    need(result['lifecycle_result_sha256']==identity(run/'result.json')['sha256'] and result['plan_sha256']==identity(run/'plan.json')['sha256'],
         'rolling wrapper source hashes differ')
    request,inputs=validate_plan_result(plan,result,original,recursive)
    need(identity(Path(plan['config']))['sha256']==plan['config_sha256'],'rolling config identity differs')
    code_sources=[]
    for name,digest in plan['pins'].items():
        if name.endswith('.py'):
            item=identity(Path(name));need(item['sha256']==digest,'rolling runtime code pin differs: '+name);code_sources.append(item)
    need(any(s['path'].endswith('/rolling_provider/transport.py') for s in code_sources)
         and any(s['path'].endswith('/rolling_ring_driver.py') for s in code_sources),'rolling transport/controller source closure absent')
    need(read(reference/'summary.json')['passed'] is True,'accepted state reference required')
    draft_reference=read(reference/'draft-state-set.json')
    need(recursive['canonical_draft_input_identity']==draft_reference['input_identity'],'canonical draft semantic identity differs')
    argv=plan['stages'][0]['argv'];draft_manifest=Path(argv[argv.index('--draft-manifest')+1])
    need(identity(draft_manifest)['sha256']==plan['pins'][str(draft_manifest)]==plan['draft_model_sha256'],
         'actual draft tensor manifest pin differs')
    commands=lines(run/'commands.jsonl');records=lines(run/'final-records.jsonl');batches=lines(run/'provider-batches.jsonl')
    meta=read(Path(plan['stages'][0]['native_output'])/'pipeline-stage.json')
    replay=audit_controller(commands,records,batches,plan['prompt_tokens'],result['output_ids'],request,len(plan['stages']),
                            meta['stream_bytes'],plan['vocab'],plan['context'])
    need(replay['actual_proposal_rows']>0,'qualification requires actual proposals consumed by target rows')
    schedule=lines(run/'schedule.jsonl')
    need([e for e in schedule if e['event'] not in ('native-reply','issued-proposal')]==result['events'],
         'rolling model trace omitted/reordered')
    need([(r['index'],r['token']) for r in lines(run/'tokens.jsonl')]==list(enumerate(result['output_ids'])),'target output publication differs')
    out.mkdir(parents=True,exist_ok=False)
    for name in ('plan.json','result.json','rolling-ring-live-result.json','admission.json','unit.json','schedule.jsonl','tokens.jsonl',
                 'commands.jsonl','provider-batches.jsonl','final-records.jsonl'):
        shutil.copyfile(run/name,out/name)
    shutil.copyfile(recursive_path,out/'recursive-reference.json')
    save(out/'runtime-source-identities.json',code_sources)
    draft_dump=Path(plan['stages'][0]['native_output'])/'state-2147483647.draft'
    draft_set=dict(schema='ownrt.draft-state-set.v1',dump=str(draft_dump),input_identity=recursive['canonical_draft_input_identity'],
        provenance=dict(plan=identity(run/'plan.json'),reference=identity(recursive_path),draft_manifest=identity(draft_manifest)))
    save(out/'draft-state-set.json',draft_set)
    candidate=dict(schema='ownrt.pipeline-state-set.v6',mode='verified-ring-pending-provider',controller_mode=plan['mode'],actual_proposals_only=True,
        layer_count=plan['boundaries'][-1],require_byte_verified_restores=True,require_provider_byte_verified_restores=True,
        provider_borrow_mode='pending-target',require_provider_survival_checks=True,required_provider_pending_depths=[],
        draft_input_identity=draft_set['input_identity'],ring_request_sha256=request,ring_epoch=0,
        input_identity=dict(model_sha256=plan['model_identity_sha256'],prompt_token_sha256=token_hash(plan['prompt_tokens']),
            output_token_sha256=token_hash(result['output_ids']),arithmetic=plan['activation_dtype'],position=len(inputs)),stages=[])
    raw_bundles=[];audits=[];provider_audit=survival_audit=None;survival_records=[]
    for stage in plan['stages']:
        index=stage['id'];native=Path(stage['native_output']);local=out/f'stage{index}';local.mkdir()
        dump=native/'state-2147483647';retain_bundle(dump,local/dump.name,raw_bundles)
        for name in ('launch-plan.json','pipeline-stage.json','ring-checkpoint-layout.json','ring.jsonl','ring-quiescence.json',
                     'state-2147483647.ring-state.json','ring-draft-batches.jsonl','ring-final-peer.json','ring-provider-survival.jsonl','draft-rows.jsonl'):
            if (native/name).is_file():shutil.copyfile(native/name,local/name)
        item=dict(id=index,begin=stage['begin'],end=stage['end'],dump=str(dump),plan=str(local/'launch-plan.json'),
            metadata=str(local/'pipeline-stage.json'),quiescence=str(native/'state-2147483647.ring-state.json'))
        att=read(native/'state-2147483647.ring-state.json');rows=lines(native/'ring.jsonl')
        need(all(r['fixture']==max(0,r['position']-len(plan['prompt_tokens'])+2) for r in rows),'native head mask differs')
        need(len(rows)==len(replay['sent'][index]) and all(r['tentative'] is e['tentative'] for r,e in zip(rows,replay['sent'][index])),
             'native original tentative flags differ from submitted command witnesses')
        audit=audit_native(rows,replay['sent'][index],replay['created'],inputs,att,stage['final'])
        audits.append(dict(stage=index,**audit));save(local/'command-audit.json',audit)
        if index==0:
            item.update(draft_state_set=str(out/'draft-state-set.json'),provider_survival=str(native/'ring-provider-survival.jsonl'))
            retain_bundle(draft_dump,local/draft_dump.name,raw_bundles)
            provider_audit=audit_provider(batches,lines(native/'ring-draft-batches.jsonl'),recursive,replay,len(plan['prompt_tokens']),att,request)
            observed_borrows={str(depth):sum(len(p['pending'])==depth for p in replay['providers']) for depth in (0,1,2)}
            need(att['provider_pending_borrows']=={key:observed_borrows[key] for key in ('1','2')}
                 and att['provider_quiescent_borrows']==observed_borrows['0'],'native borrow-depth counts differ from actual command replay')
            survival_records=lines(native/'ring-provider-survival.jsonl')
            survival_audit=bind_survival(survival_records,replay,batches,recursive,len(plan['prompt_tokens']),request)
            peer=read(native/'ring-final-peer.json');peer_path=Path(plan['final_shared']);st=peer_path.stat()
            need(peer['readonly'] is True and peer['path']==str(peer_path) and (peer['device'],peer['inode'],peer['bytes'])
                 ==(st.st_dev,st.st_ino,st.st_size),'readonly final-owner map provenance differs')
        candidate['stages'].append(item)
    save(out/'candidate-state-set.json',candidate)
    target=compare.compare(compare.load_set(reference/'candidate-state-set.json'),compare.load_set(out/'candidate-state-set.json'))
    draft=draft_compare.compare(draft_compare.load_set(reference/'draft-state-set.json'),draft_compare.load_set(out/'draft-state-set.json'))
    compressed(out/'target-comparison.json.gz',target);compressed(out/'draft-comparison.json.gz',draft)
    legacy=read(HERE/'live-draft-legacy-prefix.json')
    need([{k:r[k] for k in ('position','token','head','proposal')} for r in recursive['canonical_pairs'] if r['head']]==legacy['rows'],
         'actual canonical d1 differs from retained legacy control')
    pending={str(depth):sum(len(p['pending'])==depth for p in replay['providers']) for depth in (0,1,2)}
    summary=dict(schema='ownrt.rolling-provider-proof.v1',passed=target['passed'] and draft['passed'],source_run=str(run),
        target_state_exact=target['passed'],draft_state_exact=draft['passed'],output_tokens_exact=True,legacy_proposals_exact=True,
        target_buffer_count=len(target['compared_source_keys']),draft_allocation_count=len(draft['compared_source_keys']),
        output_tokens=len(result['output_ids']),input_rows=len(inputs),boundaries=plan['boundaries'],provider_pairs=provider_audit['pairs'],
        recursive_depth2_pairs=provider_audit['depth2_pairs'],pending_borrows=pending,provider_survival_passed=survival_audit['passed'],
        provider_survival_checks=survival_audit['checks'],provider_survival_discarded_rows=survival_audit['discarded_rows'],
        provider_survival_advanced_checks=sum(r['provider_advanced_since_snapshot'] for r in survival_records),
        actual_proposal_rows=replay['actual_proposal_rows'],observed_miss_depths=replay['observed_miss_depths'],provenance_passed=True,
        provider_audit=provider_audit,survival_audit=survival_audit,native_command_audits=audits,raw_bundles=raw_bundles,
        raw_bytes=sum(r['bytes'] for r in raw_bundles),actual_provider=True,actual_proposals_consumed=True,
        scripted_oracle_assisted=False,scripted_tentative_inputs=False,speed_claim=False,original_plan=identity(run/'plan.json'),
        qualified_termination='matched-full-cap-reference',early_eos_qualified=False,cancellation_qualified=False,
        original_result=identity(run/'rolling-ring-live-result.json'),finalizer=identity(Path(__file__)),comparator=identity(Path(compare.__file__)),
        scope='Actual depth-two MTP proposals consumed by target rows; exact final target/draft parity and complete native rollback/provider survival accounting. Coverage is observed, not forced. No speed, portability or independent CPU arithmetic claim.')
    save(out/'summary.json',summary)
    (out/'RESULT.md').write_text(f"# Actual rolling provider proof: {'PASSED' if summary['passed'] else 'FAILED'}\n\n"
        f"{summary['output_tokens']} outputs, {summary['target_buffer_count']} target buffers and {summary['draft_allocation_count']} draft allocations match accepted replay. "
        f"{summary['actual_proposal_rows']} target rows consumed actual MTP proposals. "
        f"{summary['provider_survival_checks']} stage-zero aborts preserved provider state; {summary['provider_survival_advanced_checks']} had newer canonical provider state.\n\n"
        "[Summary](summary.json) retains actual coverage and per-stage counters. No forced coverage or speed claim. Raw bundles remain external pending durable archive.\n")
    print(json.dumps({k:summary[k] for k in ('passed','target_buffer_count','draft_allocation_count','actual_proposal_rows','pending_borrows')}))
    return 0 if summary['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
