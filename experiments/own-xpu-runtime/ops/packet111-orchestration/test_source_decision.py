import unittest
from source_decision import threshold,decide
class DecisionTests(unittest.TestCase):
 def test_both_controls(self):
  self.assertFalse(threshold(56.421,[56.199,56.213]))
  self.assertFalse(threshold(101,[99,100.6]))
  self.assertTrue(threshold(100.5,[99,100]))
 def test_pending_or_veto_excluded(self):
  self.assertEqual(decide({'target_head':{'eligible':False},'other_fusion':{'eligible':False}}),dict(target_head='production',other_fusion='production'))
 def test_four_possible_compositions_only(self):
  rows={tuple(sorted(decide({'target_head':{'eligible':h},'other_fusion':{'eligible':f}}).items())) for h in (False,True) for f in (False,True)}
  self.assertEqual(len(rows),4)
if __name__=='__main__':unittest.main()
