import copy,unittest
from bracket_gate import evaluate,verify,SUMMARY
class Readiness(unittest.TestCase):
 def test_real_bracket(self):
  r=verify();self.assertTrue(r['all_views_exact']);self.assertAlmostEqual(r['minimum_gain_percent'],.345607,places=5)
 def test_every_control(self):
  with self.assertRaises(ValueError):evaluate([60,60.13,60.1,60.2,60])
 def test_every_candidate(self):
  with self.assertRaises(ValueError):evaluate([60,60.13,60,60.1,60])
 def test_drift(self):
  with self.assertRaises(ValueError):evaluate([60,62,60.61,62,60])
 def test_idle_exception(self):
  with self.assertRaises(ValueError):evaluate([58.6,58.9,58.6,58.9,58.6],lanes_idle=False)
  self.assertTrue(evaluate([58.6,58.9,58.6,58.9,58.6])['idle_lanes_exception'])
 def test_nonfinite(self):
  for rates in ([1,2,1,2],[1,float('nan'),1,2,1],[0,2,1,2,1]):
   with self.assertRaises(ValueError):evaluate(rates)
if __name__=='__main__':unittest.main()
