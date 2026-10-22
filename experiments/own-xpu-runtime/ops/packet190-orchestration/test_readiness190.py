import copy,unittest
from bracket_gate import evaluate,verify
FRESH=60.50488520482965;INLOAD=[60.61511915016977,60.44423785613836,60.49835839474562];K3X=[62.24199434282818,62.22542821257332]
V3=[FRESH,*INLOAD]
class Readiness(unittest.TestCase):
 def test_real_packet189_rows(self):
  r=verify();self.assertTrue(r['all_views_exact'] and r['chain_rule_met']);self.assertAlmostEqual(r['min_gain_vs_every_v3_view_percent'],2.656613,places=5)
  self.assertAlmostEqual(r['slower_k3x_rate'],62.22542821257332,places=9);self.assertAlmostEqual(r['fresh_v3_rate'],FRESH,places=9)
  self.assertEqual(len(r['rows']),3);self.assertEqual(len(r['evidence']),148);self.assertEqual(r['s189_kill_rules']['fired'],[])
 def test_chain_bar_two_percent(self):
  with self.assertRaises(ValueError):evaluate(V3,[x*0.99 for x in K3X])  # +1.6% over the fastest V3 view -> refused
  with self.assertRaises(ValueError):evaluate([FRESH,61.1,60.44,60.50],K3X)  # one in-load V3 view at 61.1 breaks +2% for 62.225
 def test_record_bar(self):
  with self.assertRaises(ValueError):evaluate([59.0]*4,[61.5,61.6])  # +4% but below 61.873
  evaluate([60.0]*4,[61.88,61.9])
 def test_every_v3_view(self):
  with self.assertRaises(ValueError):evaluate([FRESH,60.6,62.3,60.5],K3X)
 def test_drift(self):
  with self.assertRaises(ValueError):evaluate([FRESH,60.6,58.5,60.5],[62.3,62.3])
 def test_exactness_and_proposals(self):
  for kw in (dict(exact=False),dict(proposals=False),dict(acceptance=False),dict(smoke_exact=False),dict(fresh_proposals=False)):
   with self.assertRaises(ValueError):evaluate(V3,K3X,**kw)
 def test_nonfinite_and_shape(self):
  for k3x in ([float('nan'),62.2],[0,62.2],[62.2],[62.2,62.2,62.2]):
   with self.assertRaises(ValueError):evaluate(V3,k3x)
  with self.assertRaises(ValueError):evaluate(INLOAD,K3X)  # the fresh reference is required
if __name__=='__main__':unittest.main()
