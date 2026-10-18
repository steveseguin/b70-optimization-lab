"""Fail-closed grid, KD projection, baseline composition and override tests."""
import copy,json,math,unittest
from unittest.mock import patch
from build_engine import P,save
import screen_jobs as s
from bundle_selection import selection,views
class Gates(unittest.TestCase):
 def rows(self):
  return [dict(choice=v,rate=r,exact=True,acceptance_counts=[(13,24)]*12) for v,r in zip(('production',*s.VIEWS[1:],'production'),(50,51,52,50.5))]
 def test_grid(self):self.assertEqual([r['choice'] for r in s.jobs('B')],['production',*s.VIEWS[1:],'production'])
 def test_winner(self):self.assertEqual(s.choose(self.rows())['choice'],s.VIEWS[2])
 def test_incomplete_grid(self):
  for i in range(4):
   with self.assertRaises(ValueError):s.choose(self.rows()[:i])
 def test_reordered(self):
  r=self.rows();r[1],r[2]=r[2],r[1]
  with self.assertRaises(ValueError):s.choose(r)
 def test_both_controls(self):
  r=self.rows();r[-1]['rate']=53
  with self.assertRaises(ValueError):s.choose(r)
 def test_exact(self):
  for i in range(4):
   r=self.rows();r[i]['exact']=False
   with self.assertRaises(ValueError):s.choose(r)
 def test_acceptance(self):
  r=self.rows();r[2]['acceptance_counts'][0]=(14,24)
  with self.assertRaises(ValueError):s.choose(r)
 def test_nonfinite(self):
  for value in (math.nan,math.inf,0,-1):
   r=self.rows();r[1]['rate']=value
   with self.assertRaises(ValueError):s.choose(r)
 def test_a_refuses_missing_b(self):
  # Actual result loader attempts the complete B grid before selecting an A arm.
  with self.assertRaises((FileNotFoundError,ValueError)):s.winner(qualified=s.VIEWS[1:])
 def test_a_matches_winner(self):
  winner=s.choose(self.rows())['choice']
  self.assertEqual([r['choice'] for r in s.jobs('A',winner)],['production',winner,'production'])
 def test_baseline(self):
  base=json.loads((P/'p104b-parent-selection.json').read_text())
  expected=('exp-halfcache+down-tile16','gate-tile16+down-tile16','gate-halfcache-tile16+down-tile16')
  for name,expert in zip(views(),expected):
   v=selection(name);self.assertEqual(v['choices']['experts'],expert);v['choices']['experts']=base['choices']['experts'];self.assertEqual(v,base)
 def test_kd(self):
  from kd_reference import project,TARGET_ONLY
  for name in views():
   v=selection(name);r=project(v);self.assertEqual(v['draft'],r['draft'])
   self.assertEqual(r['choices']['experts'],'wide64')
   for key in v['choices']:
    if key not in TARGET_ONLY:self.assertEqual(v['choices'][key],r['choices'][key])
 def test_override_does_not_pass_micro(self):
  from screening_override import verify
  self.assertEqual(verify(),s.VIEWS[1:]);self.assertEqual(json.loads((P/'evidence/micro-B/qualification.json').read_text())['qualified'],[])
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Gates))
 save(P/'evidence/python-tests104b.json',dict(passed=result.wasSuccessful(),device_executed=False,tests=result.testsRun))
 raise SystemExit(not result.wasSuccessful())
