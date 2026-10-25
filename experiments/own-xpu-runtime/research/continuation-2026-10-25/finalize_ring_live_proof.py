#!/usr/bin/env python3
"""Audit discarded actual depth-two proposals with sealed target/draft parity.

CPU evidence only. This does not certify target speculation using those proposals.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from finalize_wavefront_proof import HERE, compare, identity, save, token_hash
from finalize_live_proof import compressed, retain_bundle, draft_compare
from finalize_ring_proof import audit_native, need


def read(path):
    raw, _ = draft_compare.small(Path(path))
    return json.loads(raw,object_pairs_hook=compare.BUNDLE.pairs)


def lines(path):
    # Small diagnostic traces only; no model or bundle payload duplication.
    path=Path(path);need(path.stat().st_size<=32*1024**2,'bounded diagnostic trace')
    return [json.loads(row,object_pairs_hook=compare.BUNDLE.pairs) for row in path.read_text().splitlines()]


def audit_pairs(batches,native,reference,inputs,prompt_length,final_events,att,request_sha):
    pairs=reference['canonical_pairs'];depths={r['seed_position']:r for r in reference['depth2_rows']}
    need(len(batches)==len(native)==len(pairs)==len(inputs)-1,'complete actual provider pair cohort')
    need(att['provider_trace_records']==len(native) and att['provider_trace_omitted']==0,'provider trace omitted commands')
    observed=[];head_count=0;prefix=hashlib.sha256(b'ownrt.ring-request.v1\0'+bytes.fromhex(request_sha)+(0).to_bytes(8,'little')).digest()
    def extend(value,pos,token):
        import struct
        return hashlib.sha256(b'ownrt.ring-prefix.v1\0'+value+struct.pack('<II',pos,token)).digest()
    prefix=extend(prefix,0,inputs[0])
    for position,(batch,row,want) in enumerate(zip(batches,native,pairs),1):
        head=position>=prompt_length-1;prefix=extend(prefix,position,inputs[position])
        guesses=depths[position]['guesses'][:2] if head else []
        need((want['position'],want['token'],want['head'])==(position,inputs[position],head),'canonical reference true-pair identity')
        need(batch['epoch']==0 and batch['request_sha256']==request_sha and batch['seed_prefix_sha256']==prefix.hex(),
             'provider request/full canonical prefix differs')
        need((batch['seed_position'],batch['restored_position'],batch['seed_row'],batch['parent_row'],batch['provider_serial'])
             ==(position,position,position+1,position,position),'provider causal identity differs')
        need(batch['guesses']==guesses and batch['available_depth']==len(guesses)
             and batch['parent_hidden_sha256']==want['hidden_sha256']
             and (guesses[0] if guesses else -1)==want['proposal']
             and batch['restored'] is True and batch['speculative_target_use'] is False,
             'actual provider guesses/hidden/restore differ from reference')
        parent=final_events[position-1]
        need(batch['final_commit']==parent['commit_sequence'],'provider parent not final-owner committed event')
        need((row['sequence'],row['provider_serial'],row['seed_row'],row['parent_row'],row['seed_position'],row['confirmed_token'],row['fixture'])
             ==(batch['sequence'],position,position+1,position,position,inputs[position],max(0,position-prompt_length+2)),
             'native/controller provider command identity differs')
        need(row['parent_final_ticket']==parent['row_sequence'] and row['parent_final_commit']==parent['commit_sequence']
             and row['hidden_sha256']==want['hidden_sha256'] and row['guesses']==guesses
             and row['restored_position']==position, 'native final-parent/true-pair/draft result differs')
        need(type(row['mutable_bytes_verified']) is bool and row['mutable_bytes_verified'] is head
             and row['snapshot_bytes']==(att['provider_private_bytes'] if head else 0),
             'native recursive restoration evidence differs')
        for key in ('canonical_ms','capture_ms','recursive_ms','restore_ms'):
            need(type(row[key]) in (int,float) and 0<=row[key]<1e9,'finite nonnegative provider timing')
        observed.append([position,inputs[position],head,want['hidden_sha256']]);head_count+=head
    need(head_count==reference['expected_recursive_captures']==reference['expected_recursive_restores']
         ==att['provider_snapshot_captures']==att['provider_snapshot_restores']==att['provider_byteverified_restore_count'],
         'recursive depth-two cohort/restoration counts differ')
    need(token_hash(observed)==reference['canonical_draft_input_identity']['pair_sequence_sha256'],
         'ordered true-pair sequence digest differs')
    return dict(passed=True,pairs=len(pairs),head_pairs=head_count,depth2_pairs=head_count,
                pair_sequence_sha256=token_hash(observed),canonical_true_pair_fields=['position','token','head','hidden_sha256'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--reference',type=Path,default=HERE/'live-pp4-proof')
    a=parser.parse_args();run,out,reference=a.run.resolve(),a.out.resolve(),a.reference.resolve()
    plan,result,original=(read(run/name) for name in ('plan.json','ring-live-result.json','result.json'))
    need(plan['schema']=='ownrt.ring-live-driver-plan.v1' and result['schema']=='ownrt.ring-live-driver-result.v1'
         and plan['mode']==result['mode']=='quiescent-ring-live-depth2','explicit actual-provider qualification mode')
    need(result['lifecycle_result_sha256']==identity(run/'result.json')['sha256']
         and result['plan_sha256']==identity(run/'plan.json')['sha256'],'live wrapper provenance differs')
    need(all(result.get(k)==v for k,v in original.items() if k not in ('schema','mode')),'wrapper changed original evidence')
    need(result['passed'] is True and result['error'] is None and result['live_pids']==[]
         and result['returncodes']=={str(s['id']):0 for s in plan['stages']},'all native owners must exit cleanly')
    need(plan['use_proposals'] is False and plan['verify_recursive_restore'] is True and plan['draft_training'] is False
         and result['actual_provider'] is True and result['speculative_target_use'] is False
         and result['speed_claim'] is False,'discarded actual verified proposals only')
    request=dict(model=plan['model_identity_sha256'],prompt=plan['prompt_tokens'],context=plan['context'],
                 max_new=plan['max_new'],vocab=plan['vocab'],eos=plan['eos_token_ids'],mode='quiescent-ring-live-depth2')
    need(hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':')).encode()).hexdigest()==plan['request_sha256'],
         'request digest differs from run identity')
    recursive_path=Path(plan['recursive_reference']);recursive=read(recursive_path)
    need(identity(recursive_path)['sha256']==plan['pins'][str(recursive_path)]==result['reference_sha256'],
         'recursive reference pin differs')
    need(read(reference/'summary.json')['passed'] is True,'accepted reference required')
    reference_target=read(reference/'candidate-state-set.json');reference_draft=read(reference/'draft-state-set.json')
    need(result['output_ids']==recursive['target_output_ids'] and len(result['output_ids'])==plan['max_new'], 'target output token identity')
    inputs=plan['prompt_tokens']+result['output_ids'][:-1]
    need(result['input_position']==len(inputs) and result['provider_pairs']==len(inputs)-1,'terminal target/draft position')
    argv=plan['stages'][0]['argv'];draft_manifest=Path(argv[argv.index('--draft-manifest')+1])
    need(identity(draft_manifest)['sha256']==plan['pins'][str(draft_manifest)]==plan['draft_model_sha256']
         ==recursive['canonical_draft_input_identity']['draft_model_sha256'],'draft tensor identity differs')
    need(recursive['canonical_draft_input_identity']==reference_draft['input_identity'],'canonical draft reference input identity differs')
    out.mkdir(parents=True,exist_ok=False)
    for name in ('plan.json','result.json','ring-live-result.json','admission.json','unit.json','schedule.jsonl','tokens.jsonl','provider-batches.jsonl'):
        shutil.copyfile(run/name,out/name)
    shutil.copyfile(recursive_path,out/'recursive-reference.json')
    draft_dump=Path(plan['stages'][0]['native_output'])/'state-2147483647.draft'
    draft_set=dict(schema='ownrt.draft-state-set.v1',dump=str(draft_dump),input_identity=recursive['canonical_draft_input_identity'],
                   provenance=dict(plan=identity(run/'plan.json'),reference=identity(recursive_path),draft_manifest=identity(draft_manifest)))
    save(out/'draft-state-set.json',draft_set)
    candidate=dict(schema='ownrt.pipeline-state-set.v4',mode='verified-ring-live',layer_count=plan['boundaries'][-1],
        require_byte_verified_restores=False,require_provider_byte_verified_restores=True,provider_borrow_mode='quiescent-target',
        draft_input_identity=draft_set['input_identity'],ring_request_sha256=plan['request_sha256'],ring_epoch=0,
        input_identity=dict(model_sha256=plan['model_identity_sha256'],prompt_token_sha256=token_hash(plan['prompt_tokens']),
            output_token_sha256=token_hash(result['output_ids']),arithmetic=plan['activation_dtype'],position=len(inputs)),stages=[])
    schedule=lines(run/'schedule.jsonl');need(len(schedule)==len(inputs)*len(plan['stages']),'complete target acceptance schedule')
    need([(r['position'],r['stage']) for r in schedule]==[(p,s['id']) for p in range(len(inputs)) for s in plan['stages']],
         'target stage schedule not ordered and quiescent')
    tokens=lines(run/'tokens.jsonl');need([(r['index'],r['token']) for r in tokens]==list(enumerate(result['output_ids'])),'output publication trace')
    final_events=[r for r in schedule if r['stage']==len(plan['stages'])-1]
    batches=lines(run/'provider-batches.jsonl');raw_bundles=[];audits=[];provider_audit=None
    created={p+1:dict(parent=p,token=t) for p,t in enumerate(inputs)}
    for stage in plan['stages']:
        index=stage['id'];native=Path(stage['native_output']);local=out/f'stage{index}';local.mkdir()
        dump=native/'state-2147483647';retain_bundle(dump,local/dump.name,raw_bundles)
        for name in ('launch-plan.json','pipeline-stage.json','ring-checkpoint-layout.json','ring.jsonl','ring-quiescence.json',
                     'state-2147483647.ring-state.json','ring-draft-batches.jsonl','ring-final-peer.json','draft-rows.jsonl'):
            if (native/name).is_file():shutil.copyfile(native/name,local/name)
        item=dict(id=index,begin=stage['begin'],end=stage['end'],dump=str(dump),plan=str(local/'launch-plan.json'),
                  metadata=str(local/'pipeline-stage.json'),quiescence=str(native/'state-2147483647.ring-state.json'))
        att=read(native/'state-2147483647.ring-state.json');rows=lines(native/'ring.jsonl')
        accepted=[r for r in schedule if r['stage']==index];sent=[]
        for position,event in enumerate(accepted):
            need(event['event']=='verified-target-accept' and (event['position'],event['token'],event['row'],event['physical'],event['committed'])
                 ==(position,inputs[position],position+1,position+1,position+1),'controller accepted target identity')
            for op,key in ((24,'row_sequence'),(25,'commit_sequence')):
                sent.append(dict(op=op,sequence=event[key],row=position+1,position=position))
        audits.append(audit_native(rows,sent,created,inputs,att,stage['final']))
        sequence=[r['sequence'] for r in rows]
        if index==0:
            item['draft_state_set']=str(out/'draft-state-set.json');retain_bundle(draft_dump,local/draft_dump.name,raw_bundles)
            provider_rows=lines(native/'ring-draft-batches.jsonl')
            provider_audit=audit_pairs(batches,provider_rows,recursive,inputs,len(plan['prompt_tokens']),final_events,att,plan['request_sha256'])
            sequence += [r['sequence'] for r in provider_rows]
            for row,event in zip(provider_rows,accepted[1:]):
                need(row['sequence']==event['commit_sequence']+1,'provider command did not follow locally accepted seed')
            peer=read(native/'ring-final-peer.json');peer_path=Path(plan['final_shared']);st=peer_path.stat()
            need(peer['readonly'] is True and peer['path']==str(peer_path) and (peer['device'],peer['inode'],peer['bytes'])
                 ==(st.st_dev,st.st_ino,st.st_size),'final-owned peer mapping identity differs')
        need(sorted(sequence)==list(range(1,len(sequence)+1)),'per-owner command sequence gaps/duplicates')
        candidate['stages'].append(item)
    save(out/'candidate-state-set.json',candidate)
    target=compare.compare(compare.load_set(reference/'candidate-state-set.json'),compare.load_set(out/'candidate-state-set.json'))
    draft=draft_compare.compare(draft_compare.load_set(reference/'draft-state-set.json'),draft_compare.load_set(out/'draft-state-set.json'))
    compressed(out/'target-comparison.json.gz',target);compressed(out/'draft-comparison.json.gz',draft)
    legacy=read(HERE/'live-draft-legacy-prefix.json')
    observed=[{k:r[k] for k in ('position','token','head','proposal')} for r in recursive['canonical_pairs'] if r['head']]
    need(observed==legacy['rows'],'canonical head proposals differ from retained legacy control')
    summary=dict(schema='ownrt.ring-live-proof.v1',passed=target['passed'] and draft['passed'],source_run=str(run),
        target_state_exact=target['passed'],draft_state_exact=draft['passed'],output_tokens_exact=True,legacy_proposals_exact=True,
        target_buffer_count=len(target['compared_source_keys']),draft_allocation_count=len(draft['compared_source_keys']),
        output_tokens=len(result['output_ids']),input_rows=len(inputs),boundaries=plan['boundaries'],provider_audit=provider_audit,
        native_command_audits=audits,raw_bundles=raw_bundles,raw_bytes=sum(r['bytes'] for r in raw_bundles),
        actual_provider=True,speculative_target_use=False,speed_claim=False,finalizer=identity(Path(__file__)),
        comparator=identity(Path(compare.__file__)),draft_comparator=identity(Path(draft_compare.__file__)),
        scope='Actual existing-MTP recursive depth-two outputs discarded; all target and canonical draft buffers match accepted replay. Quiescent ownership only, not target consumption, overlap, independent CPU arithmetic correctness or speed qualification.')
    save(out/'summary.json',summary)
    (out/'RESULT.md').write_text(f'''# Actual depth-two provider qualification: {'PASSED' if summary['passed'] else 'FAILED'}

All {summary['output_tokens']} output tokens match. All {summary['target_buffer_count']} target buffers and
{summary['draft_allocation_count']} canonical draft allocations compare exactly.
All {provider_audit['pairs']} true pairs and {provider_audit['depth2_pairs']} recursive d1/d2 predictions match
retained evidence; every recursive restore was byte-verified.

[Summary](summary.json), [target state comparison](target-comparison.json.gz),
[draft state comparison](draft-comparison.json.gz). Proposals were discarded;
target owners were quiescent throughout provider borrowing. This does not yet
qualify consuming recursive proposals, target/provider overlap or a speed gain.
Raw state bundles remain external with retained seals pending durable archival.
''')
    print(json.dumps({k:summary[k] for k in ('passed','target_buffer_count','draft_allocation_count','provider_audit')}))
    return 0 if summary['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
