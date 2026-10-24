import copy,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent
def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
O=load(P/'once.py','candidate_test_once');S=O.S;C=S.C
T=load(O.L/'baseline/test_suite.py','frozen_test_fixture')
class CandidateTests(unittest.TestCase):
 def fake(self,root,**options):
  return T.SuiteTests().fixture(root,**options)
 def refs(self):
  rows={}
  for i,p in enumerate(S.manifest()['prompts']):
   for mode in p['order']:
    rows[f'prompt-{i:02d}-{mode}']=dict(mode=mode,prompt_tokens=p['tokens'],result={'tokens':[2]*128},state_sha256={'0':{'state':'exact'},'1':{'state':'exact'}})
  return rows
 def invoke(self,t,reset,controller,state):
  plan=dict(lifetime_seconds=7200,manifest_sha256=S.sha(S.MANIFEST))
  with patch.object(S.A,'reset',reset),patch.object(S.A.BASE,'NativeController',controller),patch.object(S.A,'state_hashes',state),patch.object(S,'storage_guard'),patch.object(C,'bind_references'),patch.object(C,'REFERENCES',self.refs()),patch.object(C,'capture_stamp',return_value={}),patch.object(C,'verify_capture_stamps'):
   return S.run_attached(t,plan)
 def test_every_arm_exact_gate_and_full_reset(self):
  with tempfile.TemporaryDirectory() as root:
   args=self.fake(root);out=self.invoke(*args)
   self.assertTrue(out['passed']);self.assertEqual(26,len(args[0].calls));self.assertEqual(26,len(args[0].resets));self.assertEqual(24,len(list(Path(root).glob('prompt-*/baseline-exact.json'))))
 def test_first_target_mismatch_stops_before_mtp(self):
  with tempfile.TemporaryDirectory() as root:
   t,reset,controller,state=self.fake(root)
   def bad_state(t):return {'0':{'state':'wrong'},'1':{'state':'exact'}}
   with self.assertRaisesRegex(ValueError,'baseline'):self.invoke(t,reset,controller,bad_state)
   self.assertEqual(3,len(t.calls));self.assertEqual('none',t.calls[-1][0]);self.assertTrue((Path(root)/'prompt-00-none/suite-request.json').exists());self.assertFalse((Path(root)/'prompt-00-mtp').exists())
 def test_later_arm_token_error_stops_immediately(self):
  with tempfile.TemporaryDirectory() as root:
   args=self.fake(root,token_bad=True)
   with self.assertRaisesRegex(ValueError,'tokens differ from baseline'):self.invoke(*args)
   self.assertEqual(4,len(args[0].calls));self.assertFalse((Path(root)/'prompt-01-mtp').exists())
 def test_same_wrong_outputs_cannot_pass_self_comparison(self):
  refs=self.refs();refs['prompt-00-none']['result']['tokens'][0]=9
  row=dict(name='prompt-00-none',mode='none',prompt_tokens=refs['prompt-00-none']['prompt_tokens'],requested_max_new=128,result={'tokens':[2]*128},state_sha256={'0':{'state':'exact'},'1':{'state':'exact'}})
  with patch.object(C,'REFERENCES',refs),self.assertRaisesRegex(ValueError,'tokens differ'):C.check_arm(row)
 def test_candidate_command_delta_only_flag_binary(self):
  original=O.M.ADAPTER
  p=dict(output='/private/control',evidence_output='/external/result',binary='/candidate',context=4096,seconds=7200,max_new=128,mini=False)
  for rank in (0,1):self.assertEqual(original.command(p,rank,51,52)+['--attention-q8-p33','--qkv-q6-p33','--expert-iq3xxs-block'],S.A.command(p,rank,51,52))
 def test_materialization_and_memory_authority(self):
  C.verify_materialization();ledger=json.loads((P/'candidate-ledger.json').read_text())
  self.assertEqual([30947490698,29824495508],[r['device_logical_bytes'] for r in ledger['scenarios']['split24-24_mtp-rank0']['ranks']])
 def test_coordinator_uses_exact_candidate_exception_class(self):
  self.assertIs(O.O.S,S);self.assertIs(O.O.S.A.RetainedOwner,S.A.RetainedOwner)
  self.assertEqual(O.CONTROL,O.M.CONTROL);self.assertEqual(O.CONTROL,O.O.CONTROL)
  self.assertEqual(O.EVIDENCE,O.M.EVIDENCE);self.assertEqual(O.UNIT,O.M.UNIT)
 def test_independent_baseline_pins_refuse_change(self):
  with patch.object(C,'REVIEW_SHA','0'*64),self.assertRaisesRegex(ValueError,'review changed'):C.baseline()
 def test_actual_scale_receipt_schema_and_source(self):
  scale=C.scale_authority();self.assertIsInstance(scale['source_sha256'],str);self.assertTrue(scale['all_scales_finite']);self.assertEqual(48,len(scale['tensors']));self.assertEqual(84,C.qkv_authority()['exact_pairs'])
 def test_cleanup_preserves_actual_retained_exception(self):
  original=RuntimeError('owner uncertain');retained=S.A.RetainedOwner(original,object(),[])
  class Broken:
   def __init__(self,*a,**kw):raise original
  with patch.object(S,'validate_plan',return_value=S.manifest()),patch.object(S,'storage_guard'),patch.object(S.A,'Transport',Broken),patch.object(S.A,'cleanup_failure',side_effect=retained):
   with self.assertRaises(S.A.RetainedOwner) as caught:S.qualification({'adapter':{}},admit=lambda _:None,check=lambda:None,launch_hook=lambda _:None)
   self.assertIs(caught.exception.original,original)
 def test_final_dump_mismatch_refuses_completed_suite(self):
  with tempfile.TemporaryDirectory() as root:
   t,reset,controller,state=self.fake(root);calls=[]
   def final_bad(t):
    calls.append(1)
    return state(t) if len(calls)<=24 else {'0':{'state':'changed'},'1':{'state':'exact'}}
   with self.assertRaisesRegex(ValueError,'final explicit DUMP'):self.invoke(t,reset,controller,final_bad)
   self.assertEqual(26,len(t.calls));self.assertEqual(25,len(calls))
 def test_closed_stamp_detects_change_and_extra_file(self):
  with tempfile.TemporaryDirectory() as root:
   dest=Path(root)/'prompt-00-none'
   for rank in (0,1):
    path=dest/f'rank{rank}/state-2147483647';path.mkdir(parents=True)
    for name in ('state.bundle','state-index.tsv','state-seal.txt','state.json'):(path/name).write_bytes(b'x')
   stamps={'prompt-00-none':C.capture_stamp(dest)};C.verify_capture_stamps(Path(root),stamps)
   (dest/'rank0/state-2147483647/state.bundle').write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'sealed capture changed'):C.verify_capture_stamps(Path(root),stamps)
   (dest/'rank0/state-2147483647/extra').write_bytes(b'partial')
   with self.assertRaisesRegex(ValueError,'exact bundle inventory'):C.capture_stamp(dest)
if __name__=='__main__':unittest.main(verbosity=2)
