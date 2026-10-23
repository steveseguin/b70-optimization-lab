import copy,unittest
from bracket_gate import evaluate,verify,RECORD
K3X=[62.16819391948735,62.1545086431731,62.19271882349937];DIET=[63.47365308529516,63.4128279073371];SAVING=10.794891960615857
class Readiness(unittest.TestCase):
 def test_real_packet194_rows(self):
  r=verify();self.assertTrue(r['all_views_exact'] and r['screen_winner'] and r['idle_lane_exception']['authorized'] and r['idle_lane_exception']['required'])
  self.assertFalse(r['chain_rule_met']);self.assertAlmostEqual(r['min_gain_vs_every_k3x_view_percent'],1.961820,places=5);self.assertAlmostEqual(r['chain_rule_shortfall_points'],0.038180,places=5)
  self.assertAlmostEqual(r['slower_diet_rate'],63.4128279073371,places=9);self.assertAlmostEqual(r['faster_k3x_rate'],62.19271882349937,places=9);self.assertAlmostEqual(r['k3x_drift_percent'],0.061476,places=5)
  self.assertEqual(len(r['rows']),2);self.assertGreater(len(r['evidence']),100);self.assertEqual(r['s194_kill_rules']['fired'],[]);self.assertEqual(r['record'],62.345281904743764)
 def test_screen_bar_half_percent(self):
  with self.assertRaises(ValueError):evaluate(K3X,[62.4,62.45],SAVING)  # +0.33% over the fastest k3x view -> refused
  evaluate(K3X,[62.51,62.6],SAVING)  # +0.51% -> screen winner (chain not met, exception authorized)
 def test_chain_rule_reported_not_required_with_exception(self):
  r=evaluate(K3X,DIET,SAVING);self.assertFalse(r['chain_rule_met']);self.assertTrue(r['idle_lane_exception']['required'])
  r=evaluate([62.0]*3,[63.6,63.7],SAVING);self.assertTrue(r['chain_rule_met']);self.assertFalse(r['idle_lane_exception']['required'])  # +2.58% and >= 63.592
  r=evaluate([60.0]*3,[61.5,61.6],SAVING);self.assertFalse(r['chain_rule_met'])  # +2.5% but below the 63.592 record bar
  with self.assertRaises(ValueError):evaluate(K3X,DIET,SAVING,idle_lane_exception=False)  # without the ruling the +1.96% screen is refused
 def test_every_k3x_view(self):
  with self.assertRaises(ValueError):evaluate([62.17,63.3,62.19],DIET,SAVING)
 def test_drift(self):
  with self.assertRaises(ValueError):evaluate([62.17,61.8,62.19],[63.47,63.41],SAVING)  # 0.63% drift > 0.5%
 def test_saving(self):
  with self.assertRaises(ValueError):evaluate(K3X,DIET,4.9)
  with self.assertRaises(ValueError):evaluate(K3X,DIET,None)
  with self.assertRaises(ValueError):evaluate(K3X,DIET,float('nan'))
 def test_exactness_and_proposals(self):
  for kw in (dict(exact=False),dict(proposals=False),dict(acceptance=False),dict(smoke_exact=False)):
   with self.assertRaises(ValueError):evaluate(K3X,DIET,SAVING,**kw)
 def test_nonfinite_and_shape(self):
  for diet in ([float('nan'),63.4],[0,63.4],[63.4],[63.4,63.4,63.4]):
   with self.assertRaises(ValueError):evaluate(K3X,diet,SAVING)
  with self.assertRaises(ValueError):evaluate(K3X[:2],DIET,SAVING)
  with self.assertRaises(ValueError):evaluate([*K3X,62.2],DIET,SAVING)
if __name__=='__main__':unittest.main()
