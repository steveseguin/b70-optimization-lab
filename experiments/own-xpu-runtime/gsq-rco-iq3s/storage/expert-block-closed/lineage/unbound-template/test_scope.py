import copy,importlib.util,unittest
from pathlib import Path
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('expert_archive_scope',P/'closed_expert_bundles.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
class Scope(unittest.TestCase):
 def test_exact_schedule_and_quota(self):
  self.assertEqual(54,len(set(A.NAMES)));self.assertEqual(27,len(A.CAPTURES));self.assertEqual(A.NAMES[:2],['rank0/state-2147483647/state.bundle','rank1/state-2147483647/state.bundle'])
  self.assertLess(125561972+8192+1024**2,A.CAP);self.assertEqual(5987065536,27*(125561972+96181196))
  for i,n in enumerate(A.NAMES):self.assertEqual(n,A.selected(i));self.assertEqual(tuple(n.split('/')),A.C.relative(n))
 def test_bad_paths_and_batches(self):
  for x in ('../state.bundle','/rank0/state.bundle','rank0//state-2147483647/state.bundle','rank0/./state-2147483647/state.bundle','prompt-12-none/rank0/state-2147483647/state.bundle','rank0/state-2147483647/state.json'):
   with self.assertRaises(Exception):A.C.relative(x)
  for x in (-1,54,True,'0'):
   with self.assertRaises(Exception):A.selected(x)
 def test_unbound_refuses_before_authority_or_payload(self):
  self.assertIsNone(A.BINDING_SHA)
  with self.assertRaisesRegex(Exception,'not yet bound'):A.plan()
 def test_complete_closure_and_failed_contact_refused(self):
  b={'index_sha256':'a'*64,'full_result_sha256':'b'*64}
  r=dict(passed=True,requests=26,measured_arms=24,exact_pairs=12,all12_exact=True,bundles=54,paired_state_dump_groups=27,physical_drain=True,kernel_fault_baseline_unchanged=True,explicit_final_repeat_and_closed_stamps_verified=True,same_persistent_rank_pair=True,index_sha256='a'*64,plan_sha256=A.PLAN_SHA,native_binary_sha256=A.BINARY_SHA,ownership=dict(returncodes=[0,0],retained_pids=[],signals_sent=0,stop_requested=False),owners=[dict(safe_to_exit=True,in_flight=0,live_bytes=0,exit_code=0)]*2,rank_pids=[1,2],full_result_sha256='b'*64)
  t=dict(passed=True,first_error=None,original_error=None,children_exited=True,target_descriptors_empty=True,observed_target_contact=[True,True],plan_sha256=A.PLAN_SHA,rank_identities=[[1,10],[2,20]],result={'full_result_sha256':'b'*64})
  A.validate_closure(b,r,t)
  for key,value in [('passed',False),('bundles',52),('requests',25),('all12_exact',False)]:
   bad=copy.deepcopy(r);bad[key]=value
   with self.assertRaises(Exception):A.validate_closure(b,bad,t)
  bad=copy.deepcopy(t);bad['observed_target_contact']=[True,False]
  with self.assertRaisesRegex(Exception,'positive terminal'):A.validate_closure(b,r,bad)
if __name__=='__main__':unittest.main(verbosity=2)
