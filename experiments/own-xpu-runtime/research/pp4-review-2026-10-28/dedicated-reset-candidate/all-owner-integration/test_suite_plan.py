"""CPU suite authority/admission regression gate; no native launch or model reads."""
import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
ENGINE=next(p/'engine' for p in HERE.parents if (p/'engine/tools/pipeline_driver.py').exists())
sys.path[:0]=[str(HERE/'overlay/tools'),str(ENGINE/'tools'),str(ENGINE/'planning')]
import dedicated_provider_suite_plan as S

class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.config=self.root/'config.json';self.authority=self.root/'authority';self.suite=self.root/'suite.json'
  self.rows=[dict(id=str(i),prompt_tokens=[i,1,2],max_new=512)for i in range(12)]
  self.suite.write_text(json.dumps(dict(schema='ownrt.persistent-rolling-inputs.v1',model_identity_sha256='a'*64,activation_dtype='F32',eos_token_ids=[2],prompts=self.rows)))
  self.config.write_text(json.dumps(dict(dedicated_reset_protocol='ownrt.dedicated-reset-request.v2',dedicated_request_suite=str(self.suite),dedicated_suite_authority=str(self.authority),dedicated_reset_payload_bounds={},dedicated_reset_evidence_bytes=1)))
  self.plan=dict(config=str(self.config),dedicated_bulk_prefill=True,max_new=512,context=1024,vocab=99,model_identity_sha256='a'*64,eos_token_ids=[2],reference_route_tie_sort=False,check_policy='measured',speculative_depth=3,prefill_rows=256,dedicated_prefill_slots=4,pins={},prompt_tokens=[0,1,2],request_sha256='b'*64,stages=[dict(environment={'OWNRT_REFERENCE_ROUTE_TIE_SORT':'0'},argv=[])],provider=dict(environment={'OWNRT_REFERENCE_ROUTE_TIE_SORT':'0'},argv=[]))
  self.mock=patch.object(S.single,'make_plan',side_effect=lambda p:copy.deepcopy(self.plan));self.mock.start();self.addCleanup(self.mock.stop)
  self.forecast=patch.object(S.runtime,'forecast');self.forecast.start();self.addCleanup(self.forecast.stop)
 def prepare(self):return S.make_plan(self.config,prepare_authority=True)
 def test_preparation_then_pure_regeneration_and_dependency_pins(self):
  first=self.prepare();before={p.name:(p.stat().st_mtime_ns,p.read_bytes())for p in self.authority.iterdir()}
  self.assertEqual(first,S.make_plan(self.config))
  self.assertEqual(before,{p.name:(p.stat().st_mtime_ns,p.read_bytes())for p in self.authority.iterdir()})
  for module in (S.runtime.reader,S.runtime.reset_all.target_reset.evidence,S.runtime.reset_all.target_reset.rolling):
   path=Path(module.__file__).resolve();self.assertEqual(first['pins'][str(path)],S.base.digest(path))
  with self.assertRaisesRegex(ValueError,'fresh immutable'):self.prepare()
  (self.authority/'extra').write_bytes(b'x')
  with self.assertRaisesRegex(ValueError,'inventory'):S.make_plan(self.config)
 def test_exact_native_token_bounds_before_authority_creation(self):
  for count in (1,2,513):
   suite=json.loads(self.suite.read_text());suite['prompts'][1]['prompt_tokens']=[1]*count;self.suite.write_text(json.dumps(suite))
   with self.assertRaisesRegex(ValueError,'token geometry'):self.prepare()
   self.assertFalse(self.authority.exists())
  suite['prompts'][1]['prompt_tokens']=[1]*512;self.suite.write_text(json.dumps(suite));self.prepare()
 def test_validated_run_refuses_hash_pin_and_regeneration_changes(self):
  plan=self.prepare();pp=self.root/'plan.json';pp.write_text(json.dumps(plan));ap=self.root/'admission.json';ap.write_text(json.dumps(dict(plan_sha256=S.base.digest(pp))))
  self.assertEqual(S.validate_run(pp,ap)[0],plan)
  ap.write_text(json.dumps(dict(plan_sha256='0'*64)))
  with self.assertRaisesRegex(ValueError,'admission plan hash'):S.validate_run(pp,ap)
  ap.write_text(json.dumps(dict(plan_sha256=S.base.digest(pp))))
  altered=dict(plan,unexpected_identity_field=True);pp.write_text(json.dumps(altered));ap.write_text(json.dumps(dict(plan_sha256=S.base.digest(pp))))
  with self.assertRaisesRegex(ValueError,'plan/source/runtime identity'):S.validate_run(pp,ap)
  pp.write_text(json.dumps(plan));ap.write_text(json.dumps(dict(plan_sha256=S.base.digest(pp))))
  pin=self.authority/'prompt-01.i32';pin.chmod(0o600);pin.write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'pin changed'):S.validate_run(pp,ap)
 def test_cli_run_checks_identity_before_execute(self):
  plan=self.prepare();pp=self.root/'plan.json';pp.write_text(json.dumps(plan));ap=self.root/'admission.json';ap.write_text(json.dumps(dict(plan_sha256='0'*64)))
  with patch.object(sys,'argv',['suite','--run','--plan',str(pp),'--admission',str(ap),'--unit','fixture']),patch.object(S.single.lifecycle,'execute')as execute:
   with self.assertRaisesRegex(ValueError,'admission plan hash'):S.main()
   execute.assert_not_called()
  ap.write_text(json.dumps(dict(plan_sha256=S.base.digest(pp))))
  with patch.object(sys,'argv',['suite','--run','--plan',str(pp),'--admission',str(ap),'--unit','fixture']),patch.object(S.single.lifecycle,'execute',return_value={'passed':True})as execute:
   S.main();self.assertEqual(execute.call_args.args,(plan,json.loads(ap.read_text()),'fixture'))
if __name__=='__main__':unittest.main()
