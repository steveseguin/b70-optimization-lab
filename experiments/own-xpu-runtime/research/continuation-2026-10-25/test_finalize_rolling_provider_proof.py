import copy
import hashlib
import json
import unittest
import tempfile
from pathlib import Path
import finalize_rolling_provider_proof as proof
import test_finalize_pending_provider_proof as pending


def fixture():
    plan=dict(schema='ownrt.rolling-driver-plan.v1',mode='rolling-ring-live-depth2-qualification',stages=[{'id':0},{'id':1}],
        model_identity_sha256='a'*64,draft_model_sha256='b'*64,draft_experts='fp8',prompt_tokens=[3,5],context=32,vocab=97,
        max_new=2,eos_token_ids=[96],config_sha256='c'*64,epoch=0,activation_dtype='F32',rolling_depth2=True,use_proposals=True,
        verify_restore=True,verify_recursive_restore=True,verify_provider_survival=True,draft_training=False)
    identity=dict(model=plan['model_identity_sha256'],draft_manifest=plan['draft_model_sha256'],draft_experts='fp8',prompt=[3,5],
                  context=32,vocab=97,max_new=2,eos=[96],config_sha256='c'*64,mode=plan['mode'])
    plan['request_sha256']=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    original=dict(passed=True,error=None,live_pids=[],returncodes={'0':0,'1':0},actual_provider=True,scripted_oracle_assisted=False,
                  speed_claim=False,cancelled=False,cancelled_provider_incomplete=False,output_ids=[7,9],input_position=3,provider_pairs=2,provider_serial=2)
    result=dict(original,schema='ownrt.rolling-driver-result.v1',mode=plan['mode'])
    reference=dict(passed=True,prompt_tokens=2,target_prompt_token_sha256=proof.token_hash([3,5]),target_output_ids=[7,9],canonical_draft_input_identity=dict(model_sha256='a'*64,
        draft_model_sha256='b'*64,context=32,vocab=97,draft_experts='fp8',arithmetic='F32-target/BF16-draft'))
    return plan,result,original,reference


class RollingFinalizerTests(unittest.TestCase):
    def test_duplicate_witness_keys_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'commands.jsonl';path.write_text('{"sequence":1,"sequence":2}\n')
            with self.assertRaises(ValueError):proof.lines(path)

    def test_real_retained_reference_metadata_format(self):
        # Metadata-only smoke. The synthetic terminal dictionary is not a GPU result.
        plan=proof.read(proof.HERE/'ring-rolling-depth2-plan.json')
        reference=proof.read(proof.HERE/'recursive-provider-reference-v2.json')
        count=len(plan['prompt_tokens'])+len(reference['target_output_ids'])-1
        original=dict(passed=True,error=None,live_pids=[],returncodes={str(s['id']):0 for s in plan['stages']},
            actual_provider=True,scripted_oracle_assisted=False,speed_claim=False,cancelled=False,cancelled_provider_incomplete=False,
            output_ids=reference['target_output_ids'],input_position=count,provider_pairs=count-1,provider_serial=count-1)
        result=dict(original,schema='ownrt.rolling-driver-result.v1',mode=plan['mode'])
        self.assertEqual(proof.validate_plan_result(plan,result,original,reference)[1],plan['prompt_tokens']+result['output_ids'][:-1])

    def test_explicit_actual_mode_and_independent_cohort(self):
        plan,result,original,reference=fixture()
        request,inputs=proof.validate_plan_result(plan,result,original,reference)
        self.assertEqual(request,plan['request_sha256']);self.assertEqual(inputs,[3,5,7])

    def test_assistance_cancellation_reference_and_request_tampering_refused(self):
        for mutation in ('oracle','cancel','draft','prompt','request','output','verification'):
            p,r,o,ref=fixture()
            if mutation=='oracle':p['expected_outputs']=[7,9]
            elif mutation=='cancel':r['cancelled']=o['cancelled']=True
            elif mutation=='draft':ref['canonical_draft_input_identity']['draft_model_sha256']='d'*64
            elif mutation=='prompt':ref['target_prompt_token_sha256']=proof.token_hash([3,6])
            elif mutation=='request':p['request_sha256']='d'*64
            elif mutation=='output':ref['target_output_ids']=[7,10]
            else:p['verify_provider_survival']=False
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):proof.validate_plan_result(p,r,o,ref)

    def test_native_provider_reference_binding_and_survival_unchanged(self):
        pending.PendingFinalizerTests.setUpClass()
        for original,records in pending.PendingFinalizerTests.samples:
            args=copy.deepcopy(original)
            for batch in args[0]:batch['speculative_target_use']=True
            self.assertTrue(proof.audit_provider(*args)['passed'])
            batches,native,reference,replay,prompt,att,request=args
            self.assertTrue(proof.bind_survival(records,replay,batches,reference,prompt,request)['passed'])
            native[0]['parent_final_commit']+=1
            with self.assertRaises(ValueError):proof.audit_provider(*args)


if __name__=='__main__':unittest.main()
