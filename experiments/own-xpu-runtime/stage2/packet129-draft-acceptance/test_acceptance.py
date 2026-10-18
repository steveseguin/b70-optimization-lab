"""Denominator/threshold and shadow integrity regression tests."""
import copy,unittest
from analyze import paired,decide
def fixture():
 native=dict(draft_rows=[dict(position=i+128,guess=42,actual=42,provider_error=0,hit=True if i<127 else None) for i in range(128)])
 shadow=[dict(draft_position=i+126,production=42,candidate=42,restored_exact=True) for i in range(128)]
 return native,shadow
def requests(gain=20):
 return [dict(group=g,paired=dict(verified=127,production_hits=100,candidate_hits=100+(gain if i==0 and g=='independent' else 0))) for g,n in [('independent',10),('secondary',12)] for i in range(n)]
class Tests(unittest.TestCase):
 def test_terminal_excluded(self):
  a,b=fixture();self.assertEqual(paired(a,b,128)['verified'],127)
 def test_tampered_production(self):
  a,b=fixture();b[0]['production']=43
  with self.assertRaisesRegex(ValueError,'production guess'):paired(a,b,128)
 def test_missing(self):
  a,b=fixture()
  with self.assertRaises(ValueError):paired(a,b[:-1],128)
 def test_duplicate(self):
  a,b=fixture()
  with self.assertRaises(ValueError):paired(a,b+[b[0]],128)
 def test_restore_failure(self):
  a,b=fixture();b[1]['restored_exact']=False
  with self.assertRaises(ValueError):paired(a,b,128)
 def test_provider_failure(self):
  a,b=fixture();a['draft_rows'][0]['provider_error']=1
  with self.assertRaises(ValueError):paired(a,b,128)
 def test_threshold_exact_integer(self):
  self.assertFalse(decide(requests(19))['acceptance_gate_passed'])
  self.assertTrue(decide(requests(20))['acceptance_gate_passed'])
 def test_secondary_cannot_rescue(self):
  rows=requests(0)
  for row in rows[10:]:row['paired']['candidate_hits']=127
  self.assertFalse(decide(rows)['acceptance_gate_passed'])
 def test_missing_corpus(self):
  with self.assertRaises(ValueError):decide(requests()[:-1])
 def test_natural_completion(self):
  a,b=fixture();a['draft_rows']=a['draft_rows'][:17];b=b[:17]
  self.assertEqual(paired(a,b,128,17)['verified'],17)
 def test_insufficient_independent(self):
  rows=requests()
  for row in rows[:10]:row['paired'].update(verified=10,production_hits=5,candidate_hits=10)
  with self.assertRaisesRegex(ValueError,'512'):decide(rows)
if __name__=='__main__':unittest.main()
