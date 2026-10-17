import unittest
from analyze import prompt,aggregate,projection
class TestAcceptance(unittest.TestCase):
 def fixture(self):
  receipt=dict(passed=True,exact_oracle=True,cached_tokens=0,prompt_tokens=4,tokens=[10,11,12,13],prompt_id='fixture',prompt_class='code',guess_rows=[dict(position=4,guess=10,actual=10,hit=True),dict(position=5,guess=99,actual=11,hit=False),dict(position=6,guess=12,actual=12,hit=True)])
  probes=[dict(schema='packet66.depth2.cycle.v1',rank=1,discarded=True,d1_position=p,d2_position=p+1,d1=d1,d2=d2,extra_pass_wall_ms=2,extra_pass_gpu_ms=1,snapshot_ms=.1,restore_ms=.1) for p,d1,d2 in ((4,10,11),(5,99,12),(6,12,999),(7,13,5))]
  return receipt,probes
 def test_condition_and_end_censor(self):
  r,p=self.fixture();s=prompt(r,p);self.assertEqual((s['accepted_d1_with_successor'],s['accepted_d2'],s['censored'],s['a2']),(2,1,1,.5))
 def test_missing_or_duplicate_refused(self):
  r,p=self.fixture()
  with self.assertRaises(ValueError):prompt(r,p[1:])
  with self.assertRaises(ValueError):prompt(r,p+[p[0]])
 def test_shift_refused(self):
  r,p=self.fixture();p[0]['d1']=11
  with self.assertRaises(ValueError):prompt(r,p)
 def test_projection(self):
  rows=projection(.6,1.77,5);self.assertTrue(rows[0]['projected_tok_s']<rows[1]['projected_tok_s']<rows[2]['projected_tok_s'])
if __name__=='__main__':unittest.main()
