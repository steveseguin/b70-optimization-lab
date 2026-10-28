from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from analyze_2plus1_control import identity, qualification, digest

class IdentityTests(unittest.TestCase):
    def plans(self):
        argv=['/build/sc117-engine','--gsq-packed','--model-dir','/target-model','--plan','/placement','--identity','/authority',
              '--draft-model','/draft-model','--draft-experts','fp8','--draft-manifest','/draft-manifest']
        stage=dict(argv=argv,environment={'FilterBdfPath':'23','SYCL_CACHE_DIR':'/fresh','MATH':'1','OWNRT_QSA_RAW_RING':'1'},bdf='23')
        shared=dict(prompt_tokens=[1]*1677,context=65536,max_new=512,vocab=1000,eos_token_ids=[998,999],
            model_identity_sha256='model',activation_dtype='F32',draft_model_sha256='draft',
            pins={'/build/sc117-engine':'binary','/draft-manifest':'draft','/placement':'placement','/authority':'model'},
            stages=[deepcopy(stage),deepcopy(stage)])
        d=dict(deepcopy(shared),boundaries=[0,25,48],speculative_depth=3,check_policy='measured',
               dedicated_capture_ready=True,provider=deepcopy(stage))
        c=dict(deepcopy(shared),boundaries=[0,23,48],speculative_depth=1,mode='native-controller-colocated-depth1',
               native_launch_max_new=128,native_request_max_new=512)
        return d,c
    def test_explicit_treatments_with_same_core(self):
        d,c=self.plans();identity(d,c)
    def test_changed_binary_context_math_or_draft_refused(self):
        for change in (lambda p:p['pins'].update({'/build/sc117-engine':'different'}),
                       lambda p:p.update(context=262144),
                       lambda p:p['stages'][0]['environment'].update(MATH='0'),
                       lambda p:p['pins'].update({'/draft-manifest':'changed'}),
                       lambda p:p['stages'][1]['argv'].append('--dense-q6-p33')):
            d,c=self.plans();change(c)
            with self.assertRaises(ValueError):identity(d,c)
    def test_depth_not_silently_normalized(self):
        d,c=self.plans();c['speculative_depth']=3
        with self.assertRaisesRegex(ValueError,'treatment'):identity(d,c)

    def proof_fixture(self,tmp):
        d,_=self.plans();q=deepcopy(d);q.update(max_new=32,check_policy='qualification',output=str(tmp/'quality'))
        Path(q['output']).mkdir();qr=Path(q['output'])/'driver-result.json';qr.write_text(json.dumps(dict(passed=True,output_ids=list(range(32)),input_position=1708)))
        qp=tmp/'plan.json';qp.write_text(json.dumps(q))
        proof=dict(schema='ownrt.dedicated-cross-context-proof.v1',passed=True,candidate_context=65536,
            reference_context=262144,input_position=1708,outputs=32,canonical_pairs=1707,
            target=dict(source_count=2065,exact_source_keys=list(range(2017)),capacity_sources=list(range(48))),
            draft=dict(source_count=73,exact_source_keys=list(range(69)),capacity_sources=list(range(4))),
            sources=[dict(path=str(p),sha256=digest(p)) for p in (qp,qr)])
        pp=tmp/'proof.json';pp.write_text(json.dumps(proof));return d,qp,qr,pp
    def test_exact_hash_bound_quality_plan_and_output_prefix(self):
        with TemporaryDirectory() as tmp:
            d,qp,qr,pp=self.proof_fixture(Path(tmp));h=digest(pp)
            self.assertEqual(qualification(pp,h,qp,d,list(range(512)))['sha256'],h)
            with self.assertRaisesRegex(ValueError,'SHA256'):qualification(pp,'0'*64,qp,d,list(range(512)))
            q=json.loads(qp.read_text());q['model_identity_sha256']='other';qp.write_text(json.dumps(q))
            with self.assertRaisesRegex(ValueError,'not bound'):qualification(pp,h,qp,d,list(range(512)))
    def test_quality_wrong_prefix_or_partial_inventory_refused(self):
        with TemporaryDirectory() as tmp:
            d,qp,qr,pp=self.proof_fixture(Path(tmp));h=digest(pp)
            outputs=list(range(512));outputs[0]=800
            with self.assertRaisesRegex(ValueError,'prefix'):qualification(pp,h,qp,d,outputs)
            p=json.loads(pp.read_text());p['target']['capacity_sources'].pop();pp.write_text(json.dumps(p))
            with self.assertRaisesRegex(ValueError,'inventory'):qualification(pp,digest(pp),qp,d,list(range(512)))

if __name__=='__main__':unittest.main()
