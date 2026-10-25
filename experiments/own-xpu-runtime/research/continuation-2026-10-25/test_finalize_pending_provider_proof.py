"""Bind actual socket-schedule provenance to provider and survival evidence."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import finalize_pending_provider_proof as proof
sys.path.insert(0,str(proof.HERE.parents[1]/'engine/tools'))
import test_pending_ring_live_driver as fixture


class PendingFinalizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.samples=[];original=fixture.pending.drive
        def wrapped(stages,plan,guard,output):
            result=original(stages,plan,guard,output)
            schedule=proof.lines(output/'schedule.jsonl');batches=proof.lines(output/'provider-batches.jsonl')
            reference=json.loads(Path(plan['recursive_reference']).read_text())
            reference['canonical_draft_input_identity']['pair_sequence_sha256']=proof.token_hash(
                [[r[k] for k in ('position','token','head','hidden_sha256')] for r in reference['canonical_pairs']])
            replay=proof.audit_controller(schedule,plan['prompt_tokens']+result['output_ids'][:-1],plan['request_sha256'],len(stages))
            native=[];size=100
            for batch,context in zip(batches,replay['providers']):
                seed,parent=context['seed'],context['parent'];position=context['position'];head=position>=len(plan['prompt_tokens'])-1
                native.append(dict(sequence=context['sequence'],provider_serial=position,target_pending_depth=len(context['pending']),
                    seed_row=seed['id'],parent_row=parent['id'],seed_position=position,confirmed_token=seed['token'],
                    fixture=max(0,position-len(plan['prompt_tokens'])+2),parent_final_ticket=parent['row_sequence'],
                    parent_final_commit=parent['accept_sequence'],hidden_sha256=batch['parent_hidden_sha256'],guesses=batch['guesses'],
                    restored_position=position,mutable_bytes_verified=head,snapshot_bytes=size if head else 0))
            att=dict(provider_trace_records=len(native),provider_trace_omitted=0,provider_private_bytes=size,
                provider_snapshot_captures=reference['expected_recursive_captures'],provider_snapshot_restores=reference['expected_recursive_restores'],
                provider_byteverified_restore_count=reference['expected_recursive_restores'])
            args=[batches,native,reference,replay,len(plan['prompt_tokens']),att,plan['request_sha256']]
            records=[]
            for event in replay['aborts']:
                position=event['provider_position'];context=replay['providers'][position-1]
                count=sum(r['head'] for r in reference['canonical_pairs'][:position])
                payload=dict(position=position,provider_serial=position,sequence=dict(last_sequence=context['sequence'],
                    last_commit=context['parent']['accept_sequence'],last_seed=proof.full_row(context['seed'],len(plan['prompt_tokens']),plan['request_sha256']),
                    last_result=dict(guesses=batches[position-1]['guesses'])),host=dict(captures=count,restores=count,verified_restores=count,
                    current=dict(extent=32),saved=dict(extent=32)))
                records.append(dict(abort_sequence=event['sequence'],oldest=proof.full_row(event['oldest'],len(plan['prompt_tokens']),plan['request_sha256']),
                    discarded_row_ids=[r['id'] for r in event['discarded']],provider_at_capture=[dict(row=proof.full_row(r,len(plan['prompt_tokens']),plan['request_sha256']),
                        position=r['provider_position_at_capture'],serial=r['provider_serial_at_capture']) for r in event['discarded']],before_payload=json.dumps(payload)))
            cls.samples.append((args,records));return result
        with patch.object(fixture.pending,'drive',side_effect=wrapped):
            fixture.PendingTests('test_two_slot_then_older_accept_one_slot_actual_truth_two_four_six').test_two_slot_then_older_accept_one_slot_actual_truth_two_four_six()

    def test_all_true_pairs_and_survival_bind_to_actual_command_schedule(self):
        for args,records in self.samples:
            result=proof.audit_provider(*args);self.assertEqual(result['pending_borrows'],[(6,2),(7,2),(8,1)])
            b,n,ref,replay,prompt,att,request=args
            survival=proof.bind_survival(records,replay,b,ref,prompt,request)
            self.assertEqual((survival['checks'],survival['discarded_rows']),(2,3))

    def test_restored_identity_cannot_be_replaced_with_position_based_row_ids(self):
        args=copy.deepcopy(self.samples[0][0]);args[0][7]['seed_row']=args[0][7]['seed_position']+1
        with self.assertRaises(ValueError):proof.audit_provider(*args)
        args=copy.deepcopy(self.samples[0][0]);args[0][7]['original_seed_tentative']=False
        with self.assertRaises(ValueError):proof.audit_provider(*args)

    def test_native_pending_parent_and_guess_fabrication_refused(self):
        for field,value in [('target_pending_depth',0),('parent_final_commit',1),('guesses',[1,2]),('mutable_bytes_verified',False)]:
            args=copy.deepcopy(self.samples[0][0]);args[1][5][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):proof.audit_provider(*args)

    def test_survival_receipt_must_bind_exact_abort_and_capture_age(self):
        for mutation in ('sequence','capture-age','last-seed','recursive-count'):
            args,records=copy.deepcopy(self.samples[0]);b,n,ref,replay,prompt,att,request=args
            if mutation=='sequence':records[0]['abort_sequence']+=1
            elif mutation=='capture-age':records[0]['provider_at_capture'][0]['serial']+=1
            else:
                payload=json.loads(records[0]['before_payload'])
                if mutation=='last-seed':payload['sequence']['last_seed']['ticket']+=1
                else:payload['host']['captures']+=1
                records[0]['before_payload']=json.dumps(payload)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):proof.bind_survival(records,replay,b,ref,prompt,request)


if __name__=='__main__':unittest.main()
