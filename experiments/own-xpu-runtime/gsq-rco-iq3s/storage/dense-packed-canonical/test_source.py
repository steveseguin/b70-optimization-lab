import copy,importlib.util,json,unittest
from pathlib import Path
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('fixed_dense_packed_canonical',P/'reuse.py');M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
class Scope(unittest.TestCase):
 def test_exact54_scope_and_unchanged_parent_operations(self):
  self.assertEqual(len(M.NAMES),54);self.assertEqual(len(set(M.NAMES)),54)
  self.assertEqual(sum(125561972 if '/rank0/' in '/'+n else 96181196 for n in M.NAMES),M.TOTAL)
  self.assertTrue(all(n.endswith('/state-2147483647/state.bundle') and '..' not in Path(n).parts and not Path(n).is_absolute() for n in M.NAMES))
  for name in ('verify','release','hashes','descriptors','raw_held','review_pin'):
   self.assertEqual(Path(getattr(M.M,name).__code__.co_filename),M.PARENT)
 def test_pending_closure_precedes_any_current_evidence_read(self):
  self.assertIsNone(M.BINDING_SHA)
  with self.assertRaisesRegex(ValueError,'binding pending'):M.authority(0)
  for bad in (-1,54,True,'0'):
   with self.assertRaisesRegex(ValueError,'fixed batch'):M.authority(bad)
 def test_canonical_metadata_contains_exact54(self):
  prior=json.loads(M.CANON_REVIEW.read_text());rows=M.index(M.CANON_REVIEW.parent/'artifact-index.jsonl.gz',prior['index_sha256'])
  complete=json.loads(M.CANON_COMPLETE.read_text());archives={x['name']:x for x in complete['batches']}
  self.assertEqual(set(rows),set(M.NAMES));self.assertEqual(set(archives),set(M.NAMES));self.assertEqual(sum(x['bytes'] for x in rows.values()),M.TOTAL)
 def test_incomplete_or_wrong_binary_closure_refused(self):
  review=dict(passed=True,all12_exact=True,bundles=54,requests=26,measured_arms=24,physical_drain=True,kernel_fault_baseline_unchanged=True,native_binary_sha256=M.BINARY,plan_sha256=M.PLAN,full_result_sha256='a'*64,capture_budget=dict(finished=True,remaining_payload_bytes=0,resets=26,target_dumps=24,final_repeats=1,events=[{}]*52),owners=[dict(safe_to_exit=True,in_flight=0,live_bytes=0,exit_code=0)]*2)
  term=dict(passed=True,children_exited=True,target_descriptors_empty=True,observed_target_contact=[True,True],first_error=None,original_error=None,plan_sha256=M.PLAN,result=dict(full_result_sha256='a'*64));M.closed(review,term)
  for field,value in [('passed',False),('bundles',53),('native_binary_sha256','0'*64),('physical_drain',False)]:
   bad=copy.deepcopy(review);bad[field]=value
   with self.assertRaises(ValueError):M.closed(bad,term)
  bad=copy.deepcopy(term);bad['observed_target_contact']=[True,False]
  with self.assertRaises(ValueError):M.closed(review,bad)
if __name__=='__main__':unittest.main(verbosity=2)
