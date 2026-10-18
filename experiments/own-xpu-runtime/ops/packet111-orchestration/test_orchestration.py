import copy,unittest
from unittest.mock import patch
import composite_jobs as c
class PolicyTests(unittest.TestCase):
 def test_current_sources_and_selections(self):
  _,row=c.current();c.validate(row)
 def test_unqualified_head_cannot_enter(self):
  _,row=c.current();row=copy.deepcopy(row);row['candidate']['target_head']='split'
  with self.assertRaises(AssertionError):c.validate(row)
 def test_forged_eligibility_cannot_enter(self):
  _,row=c.current();row=copy.deepcopy(row);row['sources']['target_head']['eligible']=True;row['candidate']['target_head']='split';row['extra_dimension_selected']=True
  with self.assertRaisesRegex(AssertionError,'qualification differs'):c.validate(row)
 def test_identical_selection_is_not_speed_evidence(self):
  from verify_ready import matched
  _,row=c.current();row=copy.deepcopy(row);row['candidate']=row['control']
  with self.assertRaisesRegex(AssertionError,'Identical|identical'):matched(row)
 def test_source_snapshot_hash_required(self):
  _,row=c.current();row=copy.deepcopy(row);row['sources']['target_head']['sha256']='0'*64
  with self.assertRaisesRegex(AssertionError,'source snapshot changed'):c.validate(row)
 def test_exact_fresh_outputs(self):
  _,row=c.current();a=c.jobs(row,'A');b=c.jobs(row,'B')
  self.assertEqual([x['choice'] for x in a],['control','candidate','control'])
  self.assertEqual(len({x['out'] for x in a+b}),6)
  self.assertTrue(all(x['mode']=='grid' for x in a+b))
if __name__=='__main__':unittest.main()
