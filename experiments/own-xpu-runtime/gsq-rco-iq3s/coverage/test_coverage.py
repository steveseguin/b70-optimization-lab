import contextlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('coverage_test_once',P/'once.py');O=importlib.util.module_from_spec(s);s.loader.exec_module(O);S=O.S
T=S.load(S.L/'baseline/test_suite.py','coverage_old_fixture')
class Coverage(unittest.TestCase):
 def fake(self,root,**kw):return T.SuiteTests().fixture(root,**kw)
 def invoke(self,args,prefix=None):
  t,reset,controller,state=args
  with patch.object(S.A,'reset',reset),patch.object(S.A.BASE,'NativeController',controller),patch.object(S.A,'state_hashes',state),patch.object(S,'prefix_reference',return_value=prefix or [2]*128),patch.object(S,'storage_guard'),patch.object(S.C,'capture_stamp',return_value={}),patch.object(S.C,'verify_capture_stamps'),patch.object(S.B,'confirmed_inputs',side_effect=lambda r,p:len(p)+len(r['tokens'])-1),patch.object(S.B,'guess_outcomes'),patch.object(S.T,'decode',return_value='synthetic exact text'):
   return S.run_attached(t,{'lifetime_seconds':7200,'manifest_sha256':S.MANIFEST_SHA})
 def test_fixed_schedule_tokenizer_and_context(self):
  m=S.manifest();self.assertEqual([87,512,2084],[x['input_tokens'] for x in m['cases']]);self.assertEqual({'early':60,'middle':1048,'late':2037},m['cases'][2]['rubric']['positions']);self.assertEqual([512,512,128],[x['max_new'] for x in m['cases']]);self.assertEqual(2,m['order_balance']['target_first'])
 def test_six_resets_caps_and_final_repeat(self):
  with tempfile.TemporaryDirectory() as root:
   args=self.fake(root);result=self.invoke(args);t=args[0]
   self.assertEqual(6,len(t.calls));self.assertEqual(6,len(t.resets));self.assertEqual([512]*4+[128]*2,[x[2] for x in t.calls]);self.assertEqual(['none','mtp','mtp','none','none','mtp'],[x[0] for x in t.calls]);self.assertTrue(result['all_target_mtp_exact']);self.assertFalse(result['quality_qualified'])
 def test_prefix_mismatch_stops_after_first_request(self):
  with tempfile.TemporaryDirectory() as root:
   args=self.fake(root)
   with self.assertRaisesRegex(ValueError,'first128'):self.invoke(args,[9]*128)
   self.assertEqual(1,len(args[0].calls));self.assertTrue((Path(root)/'prompt00-extended-none/request-result.json').is_file())
 def test_state_mismatch_stops_before_next_case(self):
  with tempfile.TemporaryDirectory() as root:
   args=self.fake(root,state_bad=True)
   with self.assertRaisesRegex(ValueError,'state mismatch'):self.invoke(args)
   self.assertEqual(2,len(args[0].calls))
 def test_json_rubric_no_repair_and_failure_retention(self):
  case=S.manifest()['cases'][2];good=json.dumps(case['rubric']['expected']);self.assertTrue(S.quality(case,good,[])['automated_passed'])
  for text in ['```json\n'+good+'\n```',good.replace('"H7"','"H8"'),good[:-1]]:self.assertFalse(S.quality(case,text,[])['automated_passed'])
 def test_eos_short_case_retained(self):
  result=dict(tokens=[2,248046],timing_rows=[dict(generated_index=1,token_id=2,completed_monotonic=1.),dict(generated_index=2,token_id=248046,completed_monotonic=1.1)],decode_wall_ms=100,decode_intervals=1,prompt_wall_ms=1)
  self.assertEqual('eos',S.H.metric(result,512)['termination']);result['tokens'][-1]=2;result['timing_rows'][-1]['token_id']=2
  with self.assertRaises(ValueError):S.H.metric(result,512)
 def test_coordinator_identity_and_exact_argv(self):
  self.assertIs(O.O.S,S);self.assertIs(O.O.S.A.RetainedOwner,S.A.RetainedOwner);self.assertEqual(O.CONTROL,O.M.CONTROL)
  plan=dict(output='/private',evidence_output='/external',binary='/qualified',context=4096,seconds=7200,max_new=512,mini=False)
  for rank in (0,1):self.assertEqual(S.H.A.command(plan,rank,31,32),S.A.command(plan,rank,31,32))
 def test_retained_error_class_unchanged(self):
  original=RuntimeError('uncertain');retained=S.A.RetainedOwner(original,object(),[])
  class Broken:
   def __init__(self,*a,**kw):raise original
  with patch.object(S,'validate_plan',return_value={}),patch.object(S,'storage_guard'),patch.object(S.A,'Transport',Broken),patch.object(S.A,'cleanup_failure',side_effect=retained):
   with self.assertRaises(S.A.RetainedOwner) as c:S.qualification({'adapter':{}},admit=lambda p:None,check=lambda:None,launch_hook=lambda p:None)
   self.assertIs(c.exception.original,original)
if __name__=='__main__':unittest.main(verbosity=2)
