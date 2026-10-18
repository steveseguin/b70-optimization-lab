import unittest
from source_decision import threshold,decide,lane_a_loss
class DecisionTests(unittest.TestCase):
 def test_both_controls(self):
  self.assertFalse(threshold(56.421,[56.199,56.213]))
  self.assertFalse(threshold(101,[99,100.6]))
  self.assertTrue(threshold(100.5,[99,100]))
 def test_lane_a_loss_for_either_dimension(self):
  for choice in ('head-split','candidate'):
   for key in ('screens','views'):
    row={key:[dict(choice='control',rate=100),dict(choice=choice,rate=99),dict(choice='control',rate=100)]}
    self.assertTrue(lane_a_loss(row,choice));row[key][1]['rate']=101;self.assertFalse(lane_a_loss(row,choice))
 def test_pending_or_veto_excluded(self):
  self.assertEqual(decide({'target_head':{'eligible':False},'other_fusion':{'eligible':False}}),dict(target_head='production',other_fusion='production'))
 def test_four_possible_compositions_only(self):
  rows={tuple(sorted(decide({'target_head':{'eligible':h},'other_fusion':{'eligible':f}}).items())) for h in (False,True) for f in (False,True)}
  self.assertEqual(len(rows),4)
if __name__=='__main__':unittest.main()
