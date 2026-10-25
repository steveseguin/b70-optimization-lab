import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from persistent_rolling_trace_audit import audit_controller
import test_persistent_rolling as fixture
from persistent_rolling_reset_audit import audit_reset


class PersistentTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.samples=[];original=fixture.suite.run
        def capture(stages,plan,guard,output,**kwargs):
            result=original(stages,plan,guard,output,**kwargs)
            inputs=json.loads(Path(plan['suite']).read_text())['prompts']
            for record,row in zip(result['requests'],inputs):
                folder=Path(output)/f"request-{record['index']:02d}-{record['id']}"
                logs={name:[json.loads(line) for line in (folder/name).read_text().splitlines()]
                      for name in ('commands.jsonl','final-records.jsonl','provider-batches.jsonl','reset-commands.jsonl')}
                logs['reset_files']={r[key]:Path(r[key]).read_bytes() for r in record['reset_receipts']
                                     for key in ('descriptor_path','receipt_path')}
                cls.samples.append((dict(plan,stages=[dict(s.spec) for s in stages]),row,record,logs,len(stages)))
            return result
        with patch.object(fixture.suite,'run',side_effect=capture):
            for policy in ('qualification','measured'):
                for count in (2,4,6):
                    fixture.exercise(count,policy=policy,second_prompt=[7,2,14],first_options=dict(miss_first=(3,9),miss_second=(6,11)))

    def audit(self,sample,**overrides):
        plan,row,record,logs,count=sample
        args=dict(epoch=record['epoch'],initial_sequences=record['initial_sequences'],check_policy=plan['check_policy'],max_new=row['max_new'])
        args.update(overrides)
        return audit_controller(logs['commands.jsonl'],logs['final-records.jsonl'],logs['provider-batches.jsonl'],
            row['prompt_tokens'],record['output_ids'],record['request_sha256'],count,16,97,128,**args)

    def test_two_epochs_both_policies_and_distinct_prompt_histories(self):
        self.assertEqual(len(self.samples),12)
        for sample in self.samples:
            result=self.audit(sample)
            self.assertEqual(len(result['providers']),sample[2]['driver_result']['provider_serial'])

    def test_epoch_wire_baseline_and_verification_policy_cannot_be_relabelled(self):
        for sample in self.samples:
            record=sample[2]
            with self.subTest(epoch=record['epoch']),self.assertRaises(ValueError):self.audit(sample,epoch=record['epoch']+1)
            with self.assertRaises(ValueError):self.audit(sample,initial_sequences=[n-1 for n in record['initial_sequences']])
            if any(e['op']==26 for e in sample[3]['commands.jsonl']):
                policy='measured' if sample[0]['check_policy']=='qualification' else 'qualification'
                with self.assertRaises(ValueError):self.audit(sample,check_policy=policy)

    def test_complete_reset_chain_preserves_allocations_and_global_sequences(self):
        for first,second in zip(self.samples[::2],self.samples[1::2]):
            prior_request=first[0]['request_sha256'];prior_seq=[500]*first[-1];position=0;inventories=None
            for plan,row,result,logs,count in (first,second):
                checked=audit_reset(plan,row,result,logs['reset-commands.jsonl'],previous_request=prior_request,
                    previous_sequences=prior_seq,previous_target_position=position,prior_inventories=inventories,
                    read_raw=lambda p:logs['reset_files'][str(p)])
                self.assertTrue(checked['passed']);self.assertFalse(checked['cold_state_byte_verified'])
                prior_request=checked['request_sha256'];prior_seq=checked['post_sequences'];inventories=checked['inventories']
                position=result['driver_result']['input_position']

    def test_missing_reset_owner_stale_previous_epoch_and_invented_cold_bytecheck_refused(self):
        for mutation in ('missing','epoch','cold-bytecheck'):
            plan,row,result,logs,count=copy.deepcopy(self.samples[0])
            if mutation=='missing':logs['reset-commands.jsonl'].pop()
            elif mutation=='epoch':logs['reset-commands.jsonl'][0]['descriptor']['previous_epoch']=9
            else:
                complete=next(e for e in logs['reset-commands.jsonl'] if e['event']=='completed')
                complete['receipt']['cold_state_byte_verified']=True
                raw=json.dumps(complete['receipt']).encode();logs['reset_files'][complete['receipt_path']]=raw
                from persistent_rolling_reset_audit import sha
                complete['receipt_sha256']=sha(raw)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                audit_reset(plan,row,result,logs['reset-commands.jsonl'],previous_request=plan['request_sha256'],
                    previous_sequences=[500]*count,previous_target_position=0,prior_inventories=None,
                    read_raw=lambda p:logs['reset_files'][str(p)])

    def test_rehashed_duplicate_descriptor_or_receipt_key_refused(self):
        from persistent_rolling_reset_audit import sha
        for kind in ('descriptor','receipt'):
            plan,row,result,logs,count=copy.deepcopy(self.samples[0])
            issued=next(e for e in logs['reset-commands.jsonl'] if e['event']=='issued')
            complete=next(e for e in logs['reset-commands.jsonl'] if e['event']=='completed')
            if kind=='descriptor':
                path=complete['descriptor_path'];raw=logs['reset_files'][path].rstrip()[:-1]+b',"oracle":""}\n'
                logs['reset_files'][path]=raw;issued['descriptor_sha256']=complete['descriptor_sha256']=sha(raw)
                complete['receipt']['metadata_sha256']=sha(raw)
                receipt=json.dumps(complete['receipt']).encode()
            else:
                receipt=logs['reset_files'][complete['receipt_path']].rstrip()[:-1]+b',"passed":true}\n'
            complete['receipt_sha256']=sha(receipt);logs['reset_files'][complete['receipt_path']]=receipt
            result['reset_receipts'][0]={k:v for k,v in complete.items() if k!='event'}
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'duplicate'):
                audit_reset(plan,row,result,logs['reset-commands.jsonl'],previous_request=plan['request_sha256'],
                    previous_sequences=[500]*count,previous_target_position=0,prior_inventories=None,
                    read_raw=lambda p:logs['reset_files'][str(p)])


if __name__=='__main__':unittest.main()
