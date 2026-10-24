import copy,importlib.util,unittest
from pathlib import Path
P=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('native_closed_audit',P/'audit_closed.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
class Tests(unittest.TestCase):
 def test_first_difference_and_shorter(self):
  c={'tokens':[1,2,3],'stop_type':'limit'};self.assertEqual(A.comparison([1,9,8],c)['first_difference'],1);self.assertEqual(A.comparison([1],c)['first_difference'],1);self.assertTrue(A.comparison([1,2,3],c)['equal'])
 def test_safe_numerical_mismatch_vs_runtime(self):
  err=repr(ValueError(A.MISMATCH));t=dict(passed=False,result=None,original_error=err,first_error=err);o=dict(retained_pids=[],signals_sent=0,diagnostic_errors=[],stop_requested=True,returncodes=[1,1]);owners=[dict(safe_to_exit=True,in_flight=0,live_bytes=0,exit_code=0)]*2;flags={'physical':True,'faults':True};rows=[dict(equal=False)];incident=dict(error=err);errors=['cooperative rank stop']*2
  self.assertEqual(A.classify(t,o,owners,flags,rows,incident,errors)[0],'numerical_mismatch_safely_closed')
  flags['faults']=False;self.assertEqual(A.classify(t,o,owners,flags,rows,incident,errors)[0],'owner_fault_or_other_runtime_failure');flags['faults']=True
  self.assertEqual(A.classify(t,o,owners,flags,rows,incident,['device error',errors[1]])[0],'owner_fault_or_other_runtime_failure')
  t['first_error']='storage';self.assertEqual(A.classify(t,o,owners,flags,rows,incident,errors)[0],'owner_fault_or_other_runtime_failure')
 def test_success_is_metadata_only(self):
  t=dict(passed=True);o=dict(retained_pids=[],signals_sent=0,diagnostic_errors=[],stop_requested=False,returncodes=[0,0]);owners=[dict(safe_to_exit=True,in_flight=0,live_bytes=0,exit_code=0)]*2
  self.assertEqual(A.classify(t,o,owners,{'safe':True},[dict(equal=True)]*3,None,['',''])[0],'all_three_token_trajectories_equal_metadata_only')
 def test_reference_rank_at_aligned_difference(self):
  top=[dict(id=i,logprob=-i*.25) for i in range(32)];r=dict(tokens=[0,0],completion_probabilities=[dict(id=0,logprob=0.,top_logprobs=top)]*2)
  x=A.reference_at_difference(r,[0,2],1);self.assertEqual(x['native_selected_rank_in_reference_top32'],3);self.assertEqual(x['reference_top2_logprob_margin'],.25)
  self.assertTrue(A.reference_at_difference(r,[0,50],1)['native_selected_outside_reference_top32']);r['completion_probabilities']=r['completion_probabilities'][:1]
  self.assertFalse(A.reference_at_difference(r,[0,2],1)['unambiguous_probability_position'])
 def test_fixed_admitted_plan_only(self):
  self.assertEqual(A.sha(P/'plan.json'),A.PLAN_SHA);self.assertEqual(A.sha(A.B_PATH),A.B_SHA)
if __name__=='__main__':unittest.main()
