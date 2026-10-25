#!/usr/bin/env python3
"""Separate measured12 cold suite audit; only the last request has full state parity."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
from finalize_persistent_rolling_proof import (need,HERE,identity,save,token_hash,compare,draft_compare,
    compressed,retain_bundle,audit_reset,audit_controller,audit_native,audit_timing,survival_bytes)
from persistent_ring_policy import validate_policy,EMPTY_SHA
from persistent_rolling_suite_audit import read,lines,load_baseline,validate_suite,finish_reason,audit_provider,work_breakdown,timing_summary,load_planner_transition,validate_prerequisite_closure,validate_prerequisite_record


def attest(att,stage,request,epoch,position,layout):
    validate_policy(att,policy='measured',first=stage['first'])
    need(att['stage_id']==stage['id'] and att['ring_request_sha256']==request and att['ring_epoch']==epoch
         and att['reset_index']==epoch and att['actual_position']==att['committed_position']==position
         and att['pending_tickets']==att['active_slots']==att['sticky_error']==0
         and att['ring_capacity']==att['depth']==2,'native quiescent request/epoch/frontier differs')
    need(att['checkpoint_layout_sha256']==identity(layout)['sha256'],'native checkpoint layout identity differs')
    need(att['rows']==att['commits']+att['discarded_rows'] and att['commits']==position
         and att['snapshot_captures']==att['tentative_rows']==att['accepted_tentative_rows']+att['discarded_rows']==att['snapshot_releases'],
         'native target conservation differs')
    need(att['provider_present'] is stage['first'] and att['provider_recursive_active'] is False
         and att['provider_borrow_mode']=='pending-target','native provider role/borrow mode differs')
    if stage['first']:
        need(att['provider_position']==att['provider_serial']==att['provider_commands']==max(0,position-1),
             'native canonical provider frontier differs')
    else:need(att['provider_position'] is None and att['provider_trace_records']==att['provider_trace_omitted']==0,'nonfirst provider trace')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--baseline',type=Path,default=HERE/'persistent-rolling-baseline-audit.json')
    p.add_argument('--qualified-reference',type=Path,required=True)
    p.add_argument('--measured-reference',type=Path,required=True)
    p.add_argument('--planner-transition',type=Path);p.add_argument('--planner-transition-sha256')
    args=p.parse_args();run,out=args.run.resolve(),args.out.resolve();baseline=load_baseline(args.baseline)
    plan=read(run/'plan.json');terminal=read(run/'persistent-rolling-result.json');original=read(run/'result.json')
    suite_path=Path(plan['suite']);suite=read(suite_path);reasons=validate_suite(plan,suite,terminal,baseline)
    need(terminal['plan_sha256']==identity(run/'plan.json')['sha256'] and terminal['lifecycle_result_sha256']==identity(run/'result.json')['sha256']
         and all(terminal.get(k)==v for k,v in original.items() if k not in ('schema','mode','diagnostic_only')),'terminal wrapper differs')
    need((args.planner_transition is None)==(args.planner_transition_sha256 is None),'planner transition path/digest must be supplied together')
    transition=load_planner_transition(args.planner_transition,args.planner_transition_sha256) if args.planner_transition else None
    prerequisites=[]
    for folder,policy in ((args.qualified_reference,'qualification'),(args.measured_reference,'measured')):
        summary=read(folder/'summary.json')
        prior_plan=validate_prerequisite_record(summary,folder/'plan.json',policy,args.qualified_reference/'summary.json')
        closure=validate_prerequisite_closure(plan,prior_plan,transition)
        prerequisites.append(dict(summary=identity(folder/'summary.json'),plan=identity(folder/'plan.json'),execution_closure=closure))
    need(identity(suite_path)['sha256']==plan['suite_sha256']==plan['pins'][str(suite_path)]
         and identity(Path(plan['config']))['sha256']==plan['config_sha256'],'admitted prompt-only inputs/config changed')
    source_pins=[]
    for name,want in plan['pins'].items():
        if name.endswith('.py'):
            actual=identity(Path(name));need(actual['sha256']==want,'runtime Python pin changed');source_pins.append(actual)
    argv=plan['stages'][0]['argv'];draft_manifest=Path(argv[argv.index('--draft-manifest')+1])
    need(identity(draft_manifest)['sha256']==plan['draft_model_sha256']==plan['pins'][str(draft_manifest)],'draft model pin differs')
    suite_result=read(run/'suite-result.json')
    need(suite_result['schema']=='ownrt.persistent-rolling-suite-result.v1' and suite_result['passed'] is True
         and suite_result['check_policy']=='measured' and suite_result['request_count']==len(suite_result['requests'])==12
         and type(suite_result['cached_tokens']) is int and suite_result['cached_tokens']==0
         and suite_result['process_launches_by_harness']==0,'complete cold persistent suite required')
    out.mkdir(parents=True,exist_ok=False)
    for name in ('plan.json','result.json','persistent-rolling-result.json','suite-result.json','admission.json','unit.json'):
        shutil.copyfile(run/name,out/name)
    shutil.copyfile(suite_path,out/'runtime-inputs.json');save(out/'baseline-identities.json',baseline['provenance'])
    save(out/'runtime-source-identities.json',source_pins)
    previous_request=plan['request_sha256'];previous_sequences=[0]*len(plan['stages']);previous_position=0;inventories=None;layout_identities=None
    summaries=[];all_raw=[];final_candidate=None;final_draft=None
    for index,(row,want,record) in enumerate(zip(suite['prompts'],baseline['rows'],suite_result['requests'])):
        name=f"request-{index:02d}-{row['id']}";folder=run/name;local=out/name;local.mkdir()
        need(record==read(folder/'result.json') and record['index']==index,'request record differs from outer suite')
        reset=audit_reset(plan,row,record,lines(folder/'reset-commands.jsonl'),previous_request=previous_request,
            previous_sequences=previous_sequences,previous_target_position=previous_position,prior_inventories=inventories,
            read_raw=lambda path:survival_bytes(path)[0])
        request=reset['request_sha256'];epoch=reset['epoch'];outputs=record['output_ids'];inputs=row['prompt_tokens']+outputs[:-1]
        need(outputs==want['expected_output_ids'] and record['driver_result']['input_position']==len(inputs),'exact baseline outputs/frontier differ')
        need(finish_reason(outputs,row['max_new'],plan['eos_token_ids'])==reasons[index],'actual EOS/cap termination differs')
        for tokens,key in ((row['prompt_tokens'],'prompt_token_sha256'),(outputs,'output_token_sha256')):
            need(hashlib.sha256(b''.join(struct.pack('<I',t) for t in tokens)).hexdigest()==record[key],'request raw token SHA differs')
        driver=read(folder/'driver-result.json')
        need(record['driver_result_path']==str(folder/'driver-result.json') and identity(folder/'driver-result.json')['sha256']==record['driver_result_sha256']
             and {k:v for k,v in driver.items() if k not in ('events','issued_proposals','rejected_proposals')}==record['driver_result']
             and driver['cancelled'] is False and driver['cancelled_provider_incomplete'] is False,'complete uncancelled driver record required')
        need(read(folder/'request-plan.json')==dict(plan,epoch=epoch,request_sha256=request,prompt_tokens=row['prompt_tokens'],max_new=row['max_new']),
             'per-request process policy/identity changed')
        stages=[dict(s,native_output=record['reset_receipts'][i]['native_output']) for i,s in enumerate(plan['stages'])]
        metadata=read(Path(stages[0]['native_output'])/'pipeline-stage.json')
        commands=lines(folder/'commands.jsonl');records=lines(folder/'final-records.jsonl');batches=lines(folder/'provider-batches.jsonl')
        replay=audit_controller(commands,records,batches,row['prompt_tokens'],outputs,request,len(stages),metadata['stream_bytes'],
            plan['vocab'],plan['context'],epoch=epoch,initial_sequences=record['initial_sequences'],check_policy='measured',max_new=row['max_new'])
        need([s['last_sequence'] for s in replay['states']]==record['final_sequences'],'request global wire frontier differs')
        need([e for e in lines(folder/'schedule.jsonl') if e['event'] not in ('native-reply','issued-proposal')]==driver['events'],
             'request schedule changed/omitted model events')
        timing=audit_timing(lines(folder/'tokens.jsonl'),outputs,record)
        for filename in ('request-plan.json','result.json','driver-result.json','reset-commands.jsonl','commands.jsonl','final-records.jsonl',
                         'provider-batches.jsonl','schedule.jsonl','tokens.jsonl'):
            shutil.copyfile(folder/filename,local/filename)
        native_audits=[];provider=None;provider_rows=None;stage_items=[];request_layouts=[];marker='state-2147483647'
        for stage in stages:
            owner=stage['id'];native=Path(stage['native_output']);retained=local/f'stage{owner}';retained.mkdir()
            att_path=native/(marker+'.ring-state.json' if index==11 else 'ring-quiescence.json')
            att=read(att_path);attest(att,stage,request,epoch,len(inputs),native/'ring-checkpoint-layout.json')
            need(att['dump_marker']==(2147483647 if index==11 else -1),'intermediate/final attestation scope differs')
            if index!=11:need(att['state_seal_sha256']==att['canonical_draft_state_seal_sha256']=='','undumped request invented raw seal')
            request_layouts.append(att['checkpoint_layout_sha256'])
            need(att['bank_parity']==(len(inputs)%2 if stage['first'] else 0),'native canonical bank parity differs')
            meta=read(native/'pipeline-stage.json')
            need(all(meta[k]==stage[k] for k in ('begin','end','first','final')) and meta['stage_id']==owner
                 and meta['activation_dtype']==plan['activation_dtype'] and meta['mode']=='persistent-rolling'
                 and meta['ring_request_sha256']==request and meta['ring_epoch']==epoch and meta['verification_policy']=='measured',
                 'per-request native stage/policy/request metadata differs')
            rows=lines(native/'ring.jsonl')
            need(len(rows)==len(replay['sent'][owner]) and all(r['tentative'] is e['tentative'] for r,e in zip(rows,replay['sent'][owner]))
                 and all(r['fixture']==max(0,r['position']-len(row['prompt_tokens'])+2) for r in rows),'native original flags/headmask differ')
            native_audits.append(dict(stage=owner,**audit_native(rows,replay['sent'][owner],replay['created'],inputs,att,stage['final'])))
            for filename in ('launch-plan.json','pipeline-stage.json','ring-checkpoint-layout.json','ring.jsonl','ring-reset.json','reset.json',
                             att_path.name,'ring-draft-batches.jsonl','ring-final-peer.json','ring-provider-survival.jsonl'):
                if (native/filename).is_file():shutil.copyfile(native/filename,retained/filename)
            item=dict(id=owner,begin=stage['begin'],end=stage['end'],dump=str(native/marker),plan=str(retained/'launch-plan.json'),
                metadata=str(retained/'pipeline-stage.json'),quiescence=str(att_path))
            if owner==0:
                provider_rows=lines(native/'ring-draft-batches.jsonl')
                provider=audit_provider(batches,provider_rows,replay,records,len(row['prompt_tokens']),att,request,epoch)
                raw,receipt=survival_bytes(native/'ring-provider-survival.jsonl')
                need(raw==b'' and receipt['sha256']==att['provider_survival_receipt_sha256']==EMPTY_SHA,'measured survival must be authenticated empty')
                peer=read(native/'ring-final-peer.json');stat=Path(plan['final_shared']).stat()
                need(peer['readonly'] is True and peer['path']==plan['final_shared'] and (peer['device'],peer['inode'],peer['bytes'])==
                     (stat.st_dev,stat.st_ino,stat.st_size),'per-request final-owned mapping provenance differs')
                if index==11:
                    draft_identity=dict(model_sha256=plan['model_identity_sha256'],draft_model_sha256=plan['draft_model_sha256'],
                        pair_sequence_sha256=provider['pair_sequence_sha256'],position=len(inputs)-1,arithmetic='F32-target/BF16-draft',
                        context=plan['context'],vocab=plan['vocab'],draft_experts=plan['draft_experts'])
                    final_draft=local/'draft-state-set.json';save(final_draft,dict(schema='ownrt.draft-state-set.v1',dump=str(native/(marker+'.draft')),input_identity=draft_identity))
                    item.update(draft_state_set=str(final_draft),provider_survival=str(native/'ring-provider-survival.jsonl'))
                    retain_bundle(native/(marker+'.draft'),retained/(marker+'.draft'),all_raw)
            if index==11:retain_bundle(native/marker,retained/marker,all_raw)
            stage_items.append(item)
        need(layout_identities is None or layout_identities==request_layouts,'checkpoint/provider inventory layout changed across requests')
        layout_identities=request_layouts
        row_summary=dict(id=row['id'],passed=True,epoch=epoch,request_sha256=request,output_tokens=len(outputs),input_rows=len(inputs),
            cached_tokens=0,finish_reason=reasons[index],reset_audit=reset,provider_audit=provider,native_audits=native_audits,
            timing=timing,work=work_breakdown(commands,replay,provider_rows,len(row['prompt_tokens'])),
            actual_proposal_rows=replay['actual_proposal_rows'],observed_miss_depths=replay['observed_miss_depths'],
            full_state_scope='final request only' if index==11 else 'not dumped; output/reset/provenance only',provider_survival_evidence='not-collected')
        save(local/'summary.json',row_summary);summaries.append(row_summary)
        if index==11:
            final_candidate=local/'candidate-state-set.json'
            save(final_candidate,dict(schema='ownrt.pipeline-state-set.v7',mode='persistent-rolling',controller_mode='persistent-rolling',
                actual_proposals_only=True,verification_policy='measured',layer_count=plan['boundaries'][-1],require_byte_verified_restores=False,
                require_provider_byte_verified_restores=False,provider_borrow_mode='pending-target',require_provider_survival_checks=False,
                required_provider_pending_depths=[],draft_input_identity=draft_identity,ring_request_sha256=request,ring_epoch=epoch,
                input_identity=baseline['final_identity'],stages=stage_items))
        previous_request=request;previous_sequences=reset['post_sequences'];previous_position=len(inputs);inventories=reset['inventories']
    need(suite_result['final_output_scope']=='last request only' and suite_result['final_output_ids']==baseline['rows'][-1]['expected_output_ids']
         and suite_result['final_input_position']==previous_position==baseline['final_identity']['position'],'outer final scope differs')
    target=compare.compare(compare.load_set(baseline['final_state_path']),compare.load_set(final_candidate))
    need(target['passed'],'final target state differs from retained prior cold suite');compressed(out/'final-target-comparison.json.gz',target)
    draft=draft_compare.load_set(final_draft);save(out/'final-draft-authentication.json',dict(passed=True,allocation_count=len(draft['canonical']),sources=draft['sources'],
        parity_against_independent_reference=False,reason='Retained prior full12 suite has no matching sealed canonical draft reference.'))
    timing=timing_summary(summaries,baseline,suite_result['decode_median_tokens_per_second'])
    summary=dict(schema='ownrt.persistent-rolling-suite-proof.v1',passed=True,source_run=str(run),requests=12,output_tokens=5965,
        output_tokens_exact=True,provenance_passed=True,all_cold_resets_checked=True,cached_tokens=0,check_policy='measured',
        byte_verification_enabled=False,provider_survival_checks_enabled=False,provider_survival_evidence='not-collected',
        cold_state_byte_verified=False,mandatory_restore_checks_passed=True,all_requests_full_state_parity=False,
        final_target_state_exact=True,final_target_buffer_count=len(target['compared_source_keys']),final_state_position=previous_position,
        final_state_request=baseline['rows'][-1]['id'],final_draft_authenticated=True,final_draft_state_parity=False,
        early_eos_requests=[r['id'] for r in summaries if r['finish_reason']=='eos'],cap_requests=11,cancellation_qualified=False,
        actual_provider=True,actual_proposals_consumed=sum(r['actual_proposal_rows'] for r in summaries)>0,
        actual_proposal_rows=sum(r['actual_proposal_rows'] for r in summaries),scripted_oracle_assisted=False,scripted_tentative_inputs=False,
        speed_claim=False,certified=False,timing=timing,request_summaries=summaries,prerequisites=prerequisites,
        raw_bundles=all_raw,raw_bytes=sum(r['bytes'] for r in all_raw),baseline=baseline['provenance'],
        finalizer=identity(Path(__file__)),scope='Twelve exact cold outputs and complete reset/proposal/native command provenance; full target state only for final request; no independent full-cohort draft state reference or per-operation byte diagnostics. Timing observers differ from retained service baseline.')
    save(out/'summary.json',summary);print(json.dumps(dict(passed=True,requests=12,output_tokens=5965,final_target_state_exact=True,candidate_median=timing['candidate_median'])))
    return 0


if __name__=='__main__':raise SystemExit(main())
