import copy
import hashlib
import json
import unittest
import finalize_persistent_rolling_proof as proof
import test_persistent_rolling_trace_audit as trace_fixture


def metadata(policy):
    plan=proof.read(proof.HERE/'ring-rolling-depth2-plan.json')
    reference=proof.read(proof.HERE/'recursive-provider-reference-v2.json')
    enabled=policy=='qualification'
    plan.update(schema='ownrt.persistent-rolling-plan.v1',mode='persistent-rolling',check_policy=policy,
        persistent_requests=True,dump_each=True,suite_prompt_count=2,verify_restore=enabled,
        verify_recursive_restore=enabled,verify_provider_survival=enabled)
    identity=dict(model=plan['model_identity_sha256'],draft_manifest=plan['draft_model_sha256'],draft_experts=plan['draft_experts'],
        prompt=plan['prompt_tokens'],context=plan['context'],max_new=plan['max_new'],vocab=plan['vocab'],eos=plan['eos_token_ids'],
        config_sha256=plan['config_sha256'],mode=plan['mode'],check_policy=policy)
    plan['request_sha256']=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    suite=dict(schema='ownrt.persistent-rolling-inputs.v1',model_identity_sha256=plan['model_identity_sha256'],activation_dtype='F32',
        eos_token_ids=plan['eos_token_ids'],prompts=[dict(id=name,prompt_tokens=plan['prompt_tokens'],max_new=32) for name in ('a','b')])
    terminal=dict(schema='ownrt.persistent-rolling-result.v1',mode='persistent-rolling',check_policy=policy,passed=True,error=None,
        live_pids=[],returncodes={str(s['id']):0 for s in plan['stages']},actual_provider=True,scripted_oracle_assisted=False)
    return plan,suite,terminal,reference


class PersistentFinalizerTests(unittest.TestCase):
    def test_actual_retained_cohort_metadata_both_policies(self):
        for policy in ('qualification','measured'):
            self.assertEqual(proof.validate_identity(*metadata(policy)),policy)

    def test_policy_mutation_or_runtime_oracle_cannot_qualify(self):
        for kind in ('policy','oracle','cohort','dump','failure','cold-count'):
            plan,suite,terminal,reference=metadata('measured')
            if kind=='policy':plan['verify_restore']=True
            elif kind=='oracle':suite['prompts'][0]['expected_output_ids']=reference['target_output_ids']
            elif kind=='cohort':suite['prompts'][1]=dict(suite['prompts'][1],prompt_tokens=[3,4])
            elif kind=='dump':plan['dump_each']=False
            elif kind=='failure':terminal['returncodes']['0']=1
            else:plan['suite_prompt_count']=12
            with self.subTest(kind=kind),self.assertRaises(ValueError):proof.validate_identity(plan,suite,terminal,reference)

    def test_real_epoch_provider_trace_and_omitted_bytechecks_are_distinct(self):
        trace_fixture.PersistentTraceTests.setUpClass()
        helper=trace_fixture.PersistentTraceTests()
        for sample in trace_fixture.PersistentTraceTests.samples:
            plan,row,record,logs,count=sample;replay=helper.audit(sample);batches=logs['provider-batches.jsonl']
            pairs=[];native=[];depths=[];size=100;prompt=len(row['prompt_tokens']);head_count=0
            for batch,context in zip(batches,replay['providers']):
                seed,parent=context['seed'],context['parent'];position=seed['position'];head=position>=prompt-1;head_count+=head
                pairs.append(dict(position=position,token=seed['token'],head=head,hidden_sha256=batch['parent_hidden_sha256'],
                                  proposal=batch['guesses'][0] if head else -1))
                if head:depths.append(dict(seed_position=position,guesses=batch['guesses']))
                native.append(dict(sequence=context['sequence'],provider_serial=position,target_pending_depth=len(context['pending']),
                    seed_row=seed['id'],parent_row=parent['id'],seed_position=position,confirmed_token=seed['token'],
                    fixture=max(0,position-prompt+2),parent_final_ticket=parent['row_sequence'],parent_final_commit=parent['accept_sequence'],
                    hidden_sha256=batch['parent_hidden_sha256'],guesses=batch['guesses'],restored_position=position,
                    mutable_bytes_verified=head and plan['check_policy']=='qualification',snapshot_bytes=size if head else 0))
            reference=dict(canonical_pairs=pairs,depth2_rows=depths,expected_recursive_captures=head_count,expected_recursive_restores=head_count,
                canonical_draft_input_identity=dict(pair_sequence_sha256=proof.token_hash([[p[k] for k in ('position','token','head','hidden_sha256')] for p in pairs])))
            att=dict(provider_trace_records=len(native),provider_trace_omitted=0,provider_private_bytes=size,
                provider_snapshot_captures=head_count,provider_snapshot_restores=head_count,
                provider_byteverified_restore_count=head_count if plan['check_policy']=='qualification' else 0)
            args=(batches,native,reference,replay,prompt,att,record['request_sha256'])
            self.assertTrue(proof.audit_provider(*args,epoch=record['epoch'],policy=plan['check_policy'])['passed'])
            with self.assertRaises(ValueError):proof.audit_provider(*args,epoch=0,policy=plan['check_policy'])
            if plan['check_policy']=='measured':
                att['provider_byteverified_restore_count']=head_count
                with self.assertRaises(ValueError):proof.audit_provider(*args,epoch=record['epoch'],policy='measured')

    def test_timing_keeps_actual_observer_window(self):
        rows=[dict(index=i,token=t,committed_monotonic_s=10+i*.25) for i,t in enumerate((3,7,2))]
        record=dict(request_started_monotonic_s=9,request_finished_monotonic_s=11,
            timing=dict(first_token_seconds=1,full_response_seconds=2,committed_output_span_seconds=.5,decode_intervals=2,
                        decode_tokens_per_second=4,full_response_tokens_per_second=1.5))
        self.assertEqual(proof.audit_timing(rows,[3,7,2],record)['numerator'],2)
        record['timing']['decode_intervals']=99
        with self.assertRaises(ValueError):proof.audit_timing(rows,[3,7,2],record)


if __name__=='__main__':unittest.main()
