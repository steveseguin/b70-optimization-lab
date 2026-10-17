import contextlib,io,unittest
from unittest.mock import patch
import jobs,run,winner,screen
class QuickTests(unittest.TestCase):
 def test_orders_and_gaps(self):
  for lane,n in [('A',6),('B',3)]:
   rows=jobs.jobs(jobs.HERE/f'jobs-{lane}.txt',lane,best='experts2-b');commands=[];gaps=[]
   with contextlib.redirect_stdout(io.StringIO()):run.run_jobs(rows,lane,'/review',lambda c:commands.append(c) or 0,gaps.append)
   self.assertEqual(len(commands),n);self.assertEqual(gaps,[90]*(n-1))
   self.assertGreaterEqual(screen.WATCHDOG['tp2'],4*210)
 def test_failure_never_retries(self):
  rows=jobs.jobs(jobs.HERE/'jobs-A.txt','A');calls=[]
  with contextlib.redirect_stdout(io.StringIO()),self.assertRaises(ValueError):run.run_jobs(rows,'A','/review',lambda c:calls.append(c) or 75,lambda n:self.fail('gap'))
  self.assertEqual(len(calls),1)
 def test_winner_quality_and_both_controls(self):
  rows=[dict(choice=c,rate=r,exact=True) for c,r in zip(jobs.ORDERS['A'],[10,11,12,14,13,12])]
  self.assertEqual(winner.choose(rows)['choice'],'experts2-b')
  self.assertEqual(winner.choose(rows)['control'],11)
  rows[2]['exact']=False
  with self.assertRaises(ValueError):winner.choose(rows)
  rows[2]['exact']=True
  for row in rows[1:-1]:row['rate']=11
  with self.assertRaises(ValueError):winner.choose(rows)
 def test_tie_order_and_missing(self):
  rows=[dict(choice=c,rate=10 if c=='production' else 11,exact=True) for c in jobs.ORDERS['A']]
  self.assertEqual(winner.choose(rows)['choice'],'hc-wide')
  with self.assertRaises(ValueError):winner.choose(rows[:-1])
 def test_b_resolves_all_registered_winners(self):
  for name in jobs.CANDIDATES:
   with patch.object(winner,'verify_lane_a',return_value={'choice':name}):rows=jobs.jobs(jobs.HERE/'jobs-B.txt','B')
   self.assertEqual([r['choice'] for r in rows],['production',name,'production'])
   self.assertEqual(rows[1]['seal'],str(jobs.P/'selections'/name/'screen-seal.json'))
   self.assertIn('best-of-lane-A',rows[1]['out'])
  with self.assertRaises(ValueError):jobs.jobs(jobs.HERE/'jobs-B.txt','B',best='production')
 def test_b_refuses_before_any_launch(self):
  with patch.object(winner,'verify_lane_a',side_effect=ValueError('pending')):
   with self.assertRaises(ValueError):jobs.jobs(jobs.HERE/'jobs-B.txt','B')
 def test_shared_drain_and_fault_root(self):
  from drain_gate import DEFAULT_DRAIN_ROOT
  self.assertEqual(screen.SHARED/'v3',DEFAULT_DRAIN_ROOT)
if __name__=='__main__':unittest.main()
