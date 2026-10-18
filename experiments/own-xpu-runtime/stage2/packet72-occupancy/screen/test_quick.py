import contextlib,io,unittest
import jobs,run,winner,screen
class QuickTests(unittest.TestCase):
 def test_orders_and_gaps(self):
  for lane,n in [('A',4),('B',3)]:
   rows=jobs.jobs(jobs.HERE/f'jobs-{lane}.txt',lane);commands=[];gaps=[]
   with contextlib.redirect_stdout(io.StringIO()):run.run_jobs(rows,lane,'/review',lambda c:commands.append(c) or 0,gaps.append)
   self.assertEqual(len(commands),n);self.assertEqual(gaps,[90]*(n-1))
   self.assertGreaterEqual(screen.WATCHDOG['tp2'],4*210)
 def test_failure_never_retries(self):
  rows=jobs.jobs(jobs.HERE/'jobs-A.txt','A');calls=[]
  with contextlib.redirect_stdout(io.StringIO()),self.assertRaises(ValueError):run.run_jobs(rows,'A','/review',lambda c:calls.append(c) or 75,lambda n:self.fail('gap'))
  self.assertEqual(len(calls),1)
 def test_winner_uses_both_aliases_and_refuses_bad_quality(self):
  rows=[dict(choice=c,rate=r,exact=True) for c,r in zip(jobs.ORDERS['A'],[10,11,12,10])]
  self.assertEqual(winner.choose(rows)['rate'],11.5)
  rows[2]['rate']=8
  with self.assertRaises(ValueError):winner.choose(rows)
  rows[2]['rate']=12;rows[2]['exact']=False
  with self.assertRaises(ValueError):winner.choose(rows)
 def test_shared_drain_and_fault_root(self):
  from drain_gate import DEFAULT_DRAIN_ROOT
  self.assertEqual(screen.SHARED/'v3',DEFAULT_DRAIN_ROOT)
if __name__=='__main__':unittest.main()
