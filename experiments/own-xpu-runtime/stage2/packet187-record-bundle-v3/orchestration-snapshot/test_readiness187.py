import copy,unittest
from bracket_gate import evaluate,verify
SPLIT=[58.59516726664728,58.440641274178176];U=[57.832172137081876,57.80218598395255,57.84007353525389];V3=[60.57342231630567,60.532554891070376]
class Readiness(unittest.TestCase):
 def test_real_packet186_rows(self):
  r=verify();self.assertTrue(r['all_views_exact'] and r['chain_rule_met']);self.assertAlmostEqual(r['min_gain_vs_split_controls_percent'],3.306395,places=5)
  self.assertEqual(len(r['rows']),4);self.assertGreater(len(r['evidence']),100)
 def test_chain_bar_two_percent(self):
  with self.assertRaises(ValueError):evaluate(SPLIT,U,[x*0.99 for x in V3])  # +2.3% over 58.441 but < +2% over 58.595? -> refused
  with self.assertRaises(ValueError):evaluate([59.37,59.37],U,V3)  # second control above 59.37 breaks +2%
 def test_record_bar(self):
  with self.assertRaises(ValueError):evaluate([57.0,57.0],[56.9]*3,[59.9,59.95])  # +5% but below 59.974
 def test_every_control_view(self):
  with self.assertRaises(ValueError):evaluate(SPLIT,[57.8,60.6,57.8],V3)
 def test_drift(self):
  with self.assertRaises(ValueError):evaluate([58.6,56.0],U,V3)
  with self.assertRaises(ValueError):evaluate(SPLIT,[57.8,56.0,57.8],V3)
 def test_exactness_and_proposals(self):
  for kw in (dict(exact=False),dict(proposals=False),dict(acceptance=False),dict(smoke_exact=False)):
   with self.assertRaises(ValueError):evaluate(SPLIT,U,V3,**kw)
 def test_nonfinite(self):
  for v3 in ([float('nan'),60.5],[0,60.5],[60.5]):
   with self.assertRaises(ValueError):evaluate(SPLIT,U,v3)
if __name__=='__main__':unittest.main()
