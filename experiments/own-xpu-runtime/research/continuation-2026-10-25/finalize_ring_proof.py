#!/usr/bin/env python3
"""Audit a terminal scripted target-only ring run and compare every target buffer."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct

from finalize_wavefront_proof import HERE, compare, identity, save, token_hash
from finalize_live_proof import compressed, retain_bundle


def need(ok, why):
    if not ok:raise ValueError(why)


def read(path):return json.loads(Path(path).read_text())
def lines(path):return [json.loads(row) for row in Path(path).read_text().splitlines()]


def audit_native(rows, sent, created, inputs, attestation, final, speculative_depth=2):
    need(type(speculative_depth)is int and speculative_depth in (2,3),'supported speculative depth')
    need(len(rows)==len(sent),'native/controller command count differs')
    physical=committed=accepted_id=0;pending=[];accepted=[];discarded=[];peak=0
    totals=dict(rows=0,tentative_rows=0,commits=0,abort_count=0,discarded_rows=0,accepted_tentative_rows=0)
    for native,event in zip(rows,sent):
        row=created[event['row']]
        need((native['op'],native['sequence'],native['row_id'],native['parent_id'],native['position'],native['token'])
             ==(event['op'],event['sequence'],event['row'],row['parent'],event['position'],row['token']),
             'native row command identity differs from controller')
        need(type(native['tentative']) is bool,'native tentative flag type')
        op=native['op']
        if op==24:
            need(native['position']==physical and native['parent_id']==(pending[-1]['row_id'] if pending else accepted_id),
                 'physical cursor or full parent lineage differs')
            need(not final or not native['tentative'],'final target stage speculated')
            need(not pending or native['tentative'] and all(r['tentative'] for r in pending),
                 'later row bypassed unaccepted verified row')
            need(not native['discarded'],'ROW reported a discard')
            pending.append(native);physical+=1;peak=max(peak,len(pending))
            need(len(pending)<=(1 if final else speculative_depth),'native pending capacity exceeded')
            totals['rows']+=1;totals['tentative_rows']+=int(native['tentative'])
        elif op==25:
            need(pending and native['row_id']==pending[0]['row_id'] and native['tentative'] is pending[0]['tentative'],
                 'accept did not retain oldest exact row flags')
            need(native['position']==committed and native['token']==inputs[committed] and not native['discarded'],
                 'accepted input is not the confirmed canonical prefix')
            accepted.append(native['token']);accepted_id=native['row_id'];committed+=1
            totals['commits']+=1;totals['accepted_tentative_rows']+=int(pending.pop(0)['tentative'])
        elif op==26:
            need(pending and not final and all(r['tentative'] for r in pending)
                 and native['row_id']==pending[0]['row_id'] and native['position']==committed
                 and native['tentative'] is True,'abort is not oldest tentative suffix')
            need(native['discarded']==[r['row_id'] for r in pending],'native suffix discarded IDs differ')
            discarded.append(dict(sequence=native['sequence'],position=committed,row_ids=native['discarded']))
            totals['abort_count']+=1;totals['discarded_rows']+=len(pending)
            pending.clear();physical=committed
        else:raise ValueError('non-ring operation in native ring trace')
        need((native['physical'],native['committed'],native['pending'])==(physical,committed,len(pending)),
             'native physical/logical cursor or pending count differs')
    need(not pending and physical==committed==len(inputs) and accepted==inputs,'native final prefix not drained/exact')
    need(all(type(attestation[k]) is int and attestation[k]==v for k,v in totals.items()),'trace/attestation counters differ')
    need(attestation['max_pending']==peak and attestation['trace_records']==len(rows) and attestation['trace_omitted']==0,
         'native trace incomplete or peak differs')
    return dict(passed=True,commands=len(rows),accepted_input_rows=len(accepted),peak_pending=peak,
                counters=totals,suffix_restores=discarded)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();run,out=args.run.resolve(),args.out.resolve()
    result=read(run/'ring-result.json');original=read(run/'result.json');plan=read(run/'plan.json')
    need(result['schema']=='ownrt.ring-driver-result.v1' and result['mode']=='scripted-target-only-ring'
         and plan['schema']=='ownrt.ring-driver-plan.v1' and plan['mode']=='scripted-target-only-ring', 'explicit scripted ring result/plan required')
    need(result['lifecycle_result_sha256']==identity(run/'result.json')['sha256']
         and result['plan_sha256']==identity(run/'plan.json')['sha256'],'ring wrapper source hashes differ')
    need(all(result.get(k)==v for k,v in original.items() if k not in ('schema','mode')),'wrapper changed execution evidence')
    need(result['passed'] is True and result['error'] is None and result['live_pids']==[]
         and result['returncodes']=={str(s['id']):0 for s in plan['stages']},'terminal clean stages required')
    need(result['scripted_oracle_assisted'] is True and result['speed_claim'] is False
         and plan['verify_restore'] is True,'scripted diagnostic/full restore-byte proof required')
    request_identity=dict(model=plan['model_identity_sha256'],prompt=plan['prompt_tokens'],max_new=plan['max_new'],
        context=plan['context'],vocab=plan['vocab'],eos=plan['eos_token_ids'],reference=plan['scripted_proposal_tokens'],
        misses=plan['force_miss_positions'],activation='F32',mode='scripted-target-only-ring')
    need(hashlib.sha256(json.dumps(request_identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
         ==plan['request_sha256'],'ring request digest does not bind actual plan identity')
    baseline=HERE.parent/'review-2026-10-25/pp-proof/pp2'
    gold=read(baseline/'result.json');gold_plan=read(baseline/'plan.json')
    need(plan['prompt_tokens']==gold_plan['prompt_tokens'] and result['output_ids']==gold['output_ids'],'gold prompt/output ID identity')
    out.mkdir(parents=True,exist_ok=False)
    for name in ('plan.json','result.json','ring-result.json','ring-coverage.json','admission.json','unit.json','schedule.jsonl','tokens.jsonl'):
        shutil.copyfile(run/name,out/name)
    reference=read(baseline/'state-set.json')
    reference['provenance']=dict(original_state_set=identity(baseline/'state-set.json'),engine_sha256=reference['input_identity'].pop('engine_sha256'))
    for stage in reference['stages']:
        for key in ('dump','plan','metadata'):stage[key]=str((baseline/stage[key]).resolve())
    save(out/'reference-state-set.json',reference)
    candidate=dict(schema='ownrt.pipeline-state-set.v3',mode='verified-ring',layer_count=plan['boundaries'][-1],
        require_byte_verified_restores=True,ring_request_sha256=plan['request_sha256'],ring_epoch=plan['epoch'],
        input_identity=dict(model_sha256=plan['model_identity_sha256'],prompt_token_sha256=token_hash(plan['prompt_tokens']),
            output_token_sha256=token_hash(result['output_ids']),arithmetic=plan['activation_dtype'],position=result['input_position']),
        provenance=dict(plan=identity(run/'plan.json'),result=identity(run/'ring-result.json')),stages=[])
    events=result['events'];schedule=lines(run/'schedule.jsonl')
    need([e for e in schedule if e['event']!='native-reply']==events,'controller schedule omits/reorders model events')
    token_rows=lines(run/'tokens.jsonl')
    need([r['index'] for r in token_rows]==list(range(len(result['output_ids'])))
         and [r['token'] for r in token_rows]==result['output_ids'], 'output publication records differ')
    outputs=[e for e in events if e['event']=='verified-output']
    need([e['token'] for e in outputs]==result['output_ids']
         and [e['position'] for e in outputs]==list(range(len(plan['prompt_tokens'])-1,result['input_position'])),
         'verified output positions/tokens differ')
    created={e['row']:e for e in events if e['event']=='row-created'}
    need(len(created)==sum(e['event']=='row-created' for e in events),'duplicate global row ID')
    need(all(r['epoch']==plan['epoch'] for r in created.values()),'row epoch differs from request')
    need([e['row'] for e in events if e['event']=='row-created']==sorted(created),'global row IDs not increasing')
    inputs=plan['prompt_tokens']+result['output_ids'][:-1]
    need(result['input_position']==len(inputs),'terminal input position differs')
    raw_bundles=[];audits=[]
    for stage in plan['stages']:
        native=Path(stage['native_output']);local=out/f'stage{stage["id"]}';local.mkdir()
        dump=native/'state-2147483647';retain_bundle(dump,local/dump.name,raw_bundles)
        for name in ('launch-plan.json','pipeline-stage.json','ring-checkpoint-layout.json','state-2147483647.ring-state.json',
                     'ring-quiescence.json','ring.jsonl','receipt.json'):
            if (native/name).is_file():shutil.copyfile(native/name,local/name)
        candidate['stages'].append(dict(id=stage['id'],begin=stage['begin'],end=stage['end'],dump=str(dump),
            plan=str(local/'launch-plan.json'),metadata=str(local/'pipeline-stage.json'),quiescence=str(native/'state-2147483647.ring-state.json')))
        sent=[e for e in events if e['event']=='send' and e['stage']==stage['id']]
        replied=[e for e in events if e['event']=='reply' and e['stage']==stage['id']]
        need([(e['op'],e['sequence'],e['row']) for e in sent]==[(e['op'],e['sequence'],e['row']) for e in replied], 'controller missing or mismatched replies')
        need([e['sequence'] for e in sent]==list(range(1,len(sent)+1)),'global per-owner wire sequence gap/duplicate')
        att=read(native/'state-2147483647.ring-state.json')
        native_rows=lines(native/'ring.jsonl')
        need(all(r['fixture']==max(0,r['position']-len(plan['prompt_tokens'])+2) for r in native_rows),
             'native prompt/head fixture differs')
        audit=audit_native(native_rows,sent,created,inputs,att,stage['final'])
        save(local/'command-audit.json',audit);audits.append(dict(stage=stage['id'],**audit))
    save(out/'candidate-state-set.json',candidate)
    comparison=compare.compare(compare.load_set(out/'reference-state-set.json'),compare.load_set(out/'candidate-state-set.json'))
    comparison_receipt=compressed(out/'comparison.json.gz',comparison)
    coverage=read(run/'ring-coverage.json');need(coverage==result['ring'],'ring coverage records differ')
    initial=hashlib.sha256(b'ownrt.ring-request.v1\0'+bytes.fromhex(plan['request_sha256'])+struct.pack('<Q',plan['epoch'])).digest()
    def extend(before,position,token):
        return hashlib.sha256(b'ownrt.ring-prefix.v1\0'+before+struct.pack('<II',position,token)).digest()
    prefixes={0:initial}
    for row_id,row in sorted(created.items()):
        need(row['parent'] in prefixes and (row['parent']==0 and row['position']==0
             or row['parent']!=0 and created[row['parent']]['position']+1==row['position']), 'global row parent/position lineage')
        prefixes[row_id]=extend(prefixes[row['parent']],row['position'],row['token'])
    batches={e['ticket']:e for e in events if e['event']=='proposal'}
    need(len(batches)==sum(e['event']=='proposal' for e in events),'duplicate proposal batch ticket')
    for row_id,issued in coverage['issued_proposals'].items():
        row=created[int(row_id)];batch=batches[issued['batch_ticket']];offset=row['position']-batch['seed']
        need(0<=offset<len(batch['tokens'])<=2 and issued['depth']==offset+1 and issued['position']==row['position']
             and issued['token']==row['token']==batch['tokens'][offset], 'issued hypothesis depth/token differs from actual batch')
        before=initial
        for pos,token in enumerate(inputs[:batch['seed']]):before=extend(before,pos,token)
        for pos,token in enumerate(batch['tokens'][:offset],batch['seed']):before=extend(before,pos,token)
        need(before==prefixes[row['parent']],'issued child was attached to a different hypothetical prefix')
    rejected=coverage['rejected_rows'];depths={r['depth'] for r in rejected.values()}
    freezes=[e for e in events if e['event']=='freeze' and e['reason']=='miss']
    need(set(map(int,rejected))=={e['cut'] for e in freezes},'rejection positions differ from target decisions')
    for position,issued in rejected.items():
        need(any(coverage['issued_proposals'].get(str(r['row_ids'][0]))==issued and r['position']==int(position)
                 for r in audits[0]['suffix_restores']), 'rejected proposal not tied to actual oldest restored native row')
    need(set(plan['required_miss_depths'])<=depths,'required rejection depths absent')
    for position in plan['force_miss_positions']:
        key=str(position)
        need(key in rejected and any(r['position']==position for audit in audits for r in audit['suffix_restores']), 'forced miss lacks real native suffix rollback')
    actual_two=[r for r in audits[0]['suffix_restores'] if len(r['row_ids'])==2]
    need(not plan['require_two_row_abort'] or actual_two,'no actual two-row stage0 abort')
    claimed_two=coverage['two_row_stage0_restores']
    need([(r['sequence'],r['position'],r['discarded']) for r in claimed_two]
         ==[(r['sequence'],r['position'],r['row_ids']) for r in actual_two]
         and all(r['byte_checked'] is True for r in claimed_two),'two-row restore receipt differs from native trace')
    summary=dict(schema='ownrt.scripted-ring-proof.v1',passed=comparison['passed'],source_run=str(run),
        output_tokens_exact=True,target_state_exact=comparison['passed'],target_buffer_count=len(comparison['compared_source_keys']),
        input_rows=len(inputs),output_tokens=len(result['output_ids']),boundaries=plan['boundaries'],
        native_command_audits=audits,required_miss_depths=plan['required_miss_depths'],observed_miss_depths=sorted(depths),
        stage0_two_row_restores=len(actual_two),comparison=comparison_receipt,raw_bundles=raw_bundles,
        raw_bytes=sum(r['bytes'] for r in raw_bundles),scripted_oracle_assisted=True,live_draft=False,speed_claim=False,
        scope='Exact target state and token identity after real native scripted one-/two-row rollback. No recursive provider, live drafting, speed or portability claim.',
        finalizer=identity(Path(__file__)),comparator=identity(Path(compare.__file__)))
    save(out/'summary.json',summary)
    (out/'RESULT.md').write_text(f'''# Scripted target-only depth-two ring proof: {'PASSED' if summary['passed'] else 'FAILED'}

All {len(result['output_ids'])} gold output IDs match. All {summary['target_buffer_count']}
canonical target buffers and layouts compare exactly: {comparison['passed']}.
Every stage's native trace replays the {len(inputs)} confirmed inputs in order,
with exact row lineage, global wire sequence, oldest acceptance, suffix discard
and physical/logical cursor accounting. Required rejected depths: {sorted(depths)};
actual two-row stage0 suffix restores: {len(actual_two)}. Every restore was byte-verified.

[Summary](summary.json), [full state comparison](comparison.json.gz),
[strict ring state manifest](candidate-state-set.json), [explicit ring result](ring-result.json).
The original result.json retains the reused lifecycle's older mode label; its exact
hash is bound by ring-result.json. No original evidence was rewritten.

Guesses were scripted from retained reference tokens. This is target rollback
qualification, not live recursive drafting or speed evidence. Full raw target
bundles remain external with retained seals pending durable archival.
''')
    print(json.dumps({k:summary[k] for k in ('passed','target_buffer_count','output_tokens','observed_miss_depths','stage0_two_row_restores')}))
    return 0 if summary['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
