"""Independent small terminal/counter/provenance review; no raw state-array reads."""
import hashlib
import json
from pathlib import Path
import struct
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'engine/tools'))
import compare_rolling_provider_survival as survival


def digest(raw):return hashlib.sha256(raw).hexdigest()


def main():
    inputs={}
    def blob(path):
        data,receipt=survival.survival_bytes(Path(path));inputs[str(path)]=receipt;return data
    def read(path):return json.loads(blob(path),object_pairs_hook=survival.BUNDLE.pairs)
    def lines(path):return [json.loads(line,object_pairs_hook=survival.BUNDLE.pairs) for line in blob(path).decode().splitlines()]
    proof=HERE/'ring-rolling-depth2-proof';summary=read(proof/'summary.json');run=Path(summary['source_run'])
    plan=read(run/'plan.json');result=read(run/'rolling-ring-live-result.json');original=blob(run/'result.json')
    assert result['passed'] is True and result['error'] is None and result['live_pids']==[]
    assert result['returncodes']==dict.fromkeys(('0','1','2','3'),0)
    assert result['lifecycle_result_sha256']==digest(original)
    assert result['plan_sha256']==summary['original_plan']['sha256']==inputs[str(run/'plan.json')]['sha256']
    assert summary['original_result']['sha256']==inputs[str(run/'rolling-ring-live-result.json')]['sha256']
    assert len(result['output_ids'])==summary['output_tokens']==32
    true_inputs=plan['prompt_tokens']+result['output_ids'][:-1]
    assert len(true_inputs)==result['input_position']==summary['input_rows']==118
    commands=lines(run/'commands.jsonl');batches=lines(run/'provider-batches.jsonl');records=lines(run/'final-records.jsonl')
    final_by_row={r['row']:r for r in records};assert len(final_by_row)==len(records)==len(true_inputs)
    for r in records:
        raw=bytes.fromhex(r['record_hex']);assert len(raw)==360 and digest(raw)==r['record_sha256']
    issued={};completed={}
    for command in commands:
        key=(command['stage'],command['sequence']);table=issued if command['event']=='issued' else completed
        assert key not in table;table[key]=command
    assert issued.keys()==completed.keys()
    for key,command in issued.items():
        reply=completed[key]
        assert all(command[k]==reply[k] for k in ('op','row','tentative','row_ticket'))
    native_counts=[]
    for stage in range(4):
        native=run/f'stage{stage}/native';rows=lines(native/'ring.jsonl');att=read(native/'state-2147483647.ring-state.json')
        seqs=[seq for (owner,seq) in issued if owner==stage]
        assert sorted(seqs)==list(range(1,len(seqs)+1))
        for row in rows:
            source=issued[(stage,row['sequence'])]
            assert (row['op'],row['row_id'],row['parent_id'],row['position'],row['token'],row['tentative'])==(
                source['op'],source['row']['id'],source['row']['parent'],source['row']['position'],source['row']['token'],source['tentative'])
        accepted=[r for r in rows if r['op']==25]
        assert [r['token'] for r in accepted]==true_inputs
        counts=dict(rows=sum(r['op']==24 for r in rows),tentative_rows=sum(r['op']==24 and r['tentative'] for r in rows),
                    commits=len(accepted),abort_count=sum(r['op']==26 for r in rows),
                    discarded_rows=sum(len(r['discarded']) for r in rows),accepted_tentative_rows=sum(r['tentative'] for r in accepted))
        assert counts==summary['native_command_audits'][stage]['counters']
        assert all(att[k]==v for k,v in counts.items())
        assert counts['rows']==counts['commits']+counts['discarded_rows']
        assert counts['tentative_rows']==counts['accepted_tentative_rows']+counts['discarded_rows']
        native_counts.append(dict(stage=stage,**counts))
    native=run/'stage0/native';att=read(native/'state-2147483647.ring-state.json')
    native_provider=lines(native/'ring-draft-batches.jsonl');reference=read(HERE/'recursive-provider-reference-v2.json')
    depths={r['seed_position']:r for r in reference['depth2_rows']}
    assert len(batches)==len(native_provider)==summary['provider_pairs']==117
    pending={str(i):0 for i in (0,1,2)};by_ticket={};head_count=0
    for pos,(batch,native_row,want) in enumerate(zip(batches,native_provider,reference['canonical_pairs']),1):
        raw=bytes.fromhex(batch['proposal_hex']);reply=bytes.fromhex(batch['reply_hex'])
        assert len(raw)==192 and digest(raw)==batch['proposal_sha256'] and digest(reply)==batch['reply_sha256']
        witness=completed[(0,batch['sequence'])]
        assert witness['metadata_hex']==batch['proposal_hex'] and witness['provider']==batch
        parent=final_by_row[batch['parent_row']]
        assert batch['parent_hidden_sha256']==parent['hidden_sha256']==native_row['hidden_sha256']==want['hidden_sha256']
        assert batch['final_commit']==parent['sequence']==native_row['parent_final_commit']
        assert batch['seed_position']==native_row['seed_position']==batch['provider_serial']==pos
        assert native_row['confirmed_token']==want['token']==true_inputs[pos]
        head=bool(want['head']);guesses=depths[pos]['guesses'] if head else []
        assert batch['guesses']==native_row['guesses']==guesses
        assert native_row['mutable_bytes_verified'] is head
        assert batch['pending_depth']==native_row['target_pending_depth']==len(batch['pending_target_rows'])
        assert batch['speculative_target_use'] is True and batch['restored'] is True
        pending[str(batch['pending_depth'])]+=1;head_count+=head;by_ticket[batch['sequence']]=batch
    assert pending==summary['pending_borrows']=={'0':94,'1':23,'2':0}
    assert head_count==summary['recursive_depth2_pairs']==32
    proposal_rows=[]
    for (stage,seq),command in issued.items():
        if stage!=0 or command['op']!=24 or command['proposal'] is None:continue
        r=command['row'];p=command['proposal'];batch=by_ticket[p['batch_ticket']]
        depth=r['position']-batch['seed_position'];before=bytes.fromhex(batch['seed_prefix_sha256'])
        for position,token in enumerate(batch['guesses'][:depth-1],batch['seed_position']+1):
            before=hashlib.sha256(b'ownrt.ring-prefix.v1\0'+before+struct.pack('<II',position,token)).digest()
        assert depth==p['depth'] and 1<=depth<=len(batch['guesses'])
        assert r['token']==batch['guesses'][depth-1] and r['before']==p['parent_digest']==before.hex()
        proposal_rows.append(r['id'])
    assert len(set(proposal_rows))==len(proposal_rows)==summary['actual_proposal_rows']==35
    spec=read(proof/'candidate-state-set.json');layout=read(native/'ring-checkpoint-layout.json');meta=read(native/'pipeline-stage.json')
    survival_records=lines(native/'ring-provider-survival.jsonl')
    assert inputs[str(native/'ring-provider-survival.jsonl')]['sha256']==att['provider_survival_receipt_sha256']
    survival.validate_records(survival_records,spec,layout,meta,att)
    actual_survival=[]
    for record in survival_records:
        before=json.loads(record['before_payload']);captures=record['provider_at_capture']
        assert record['before_payload']==record['after_payload']
        assert digest(record['before_payload'].encode())==record['before_payload_sha256']==record['after_payload_sha256']
        command=issued[(0,record['abort_sequence'])]
        assert command['row']['id']==record['oldest']['id'] and command['pending_target_rows']==record['discarded_row_ids']
        advanced=before['position']>captures[0]['position']
        assert advanced is record['provider_advanced_since_snapshot']
        actual_survival.append(dict(sequence=record['abort_sequence'],provider_position=before['position'],
            captured_position=captures[0]['position'],advanced=advanced,discarded_rows=len(record['discarded_row_ids']),
            compared_bytes=record['comparison_bytes'],payload_sha256=record['before_payload_sha256']))
    assert len(actual_survival)==summary['provider_survival_checks']==7
    assert sum(r['advanced'] for r in actual_survival)==summary['provider_survival_advanced_checks']==5
    assert sum(r['discarded_rows'] for r in actual_survival)==summary['provider_survival_discarded_rows']==11
    assert summary['speed_claim'] is False and summary['early_eos_qualified'] is False and summary['cancellation_qualified'] is False
    inputs[str(Path(__file__))]=dict(path=str(Path(__file__)),sha256=digest(Path(__file__).read_bytes()))
    print(json.dumps(dict(schema='ownrt.rolling-provider-independent-receipt-review.v1',passed=True,
        source_run=str(run),native_counts=native_counts,actual_proposal_rows=len(proposal_rows),canonical_pairs=len(batches),
        recursive_pairs=head_count,pending_borrows=pending,survival=actual_survival,inputs=inputs,
        scope='Independent terminal/raw witness/native counter/actual proposal/full survival payload review. Existing v6 finalizer established exact raw target/draft state; large state arrays were not reread. No speed or unobserved two-pending-borrow coverage claim.'),indent=2))


if __name__=='__main__':main()
