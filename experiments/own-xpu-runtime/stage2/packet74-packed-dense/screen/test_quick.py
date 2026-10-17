import contextlib,io,unittest
import jobs,run,winner,screen
class QuickTests(unittest.TestCase):
 def test_orders_and_gaps(self):
  grids=[('A','jobs-A.txt',5)]+[('B',f'jobs-B-{c}.txt',3) for c in jobs.CANDIDATES]
  for lane,name,n in grids:
   rows=jobs.jobs(jobs.HERE/name,lane);commands=[];gaps=[]
   with contextlib.redirect_stdout(io.StringIO()):run.run_jobs(rows,lane,'/review',lambda c:commands.append(c) or 0,gaps.append)
   self.assertEqual(len(commands),n);self.assertEqual(gaps,[90]*(n-1))
 def test_no_retry(self):
  rows=jobs.jobs(jobs.HERE/'jobs-A.txt','A');calls=[]
  with contextlib.redirect_stdout(io.StringIO()),self.assertRaises(ValueError):run.run_jobs(rows,'A','/review',lambda c:calls.append(c) or 75,lambda n:self.fail('gap'))
  self.assertEqual(len(calls),1)
 def test_winner_quality_control_and_tie(self):
  rows=[dict(choice=c,rate=r,exact=True) for c,r in zip(jobs.ORDERS['A'],[10,11,12,12,10.5])]
  self.assertEqual(winner.choose(rows)['choice'],'dense-packed')
  rows[-1]['rate']=12
  with self.assertRaises(ValueError):winner.choose(rows)
  rows[-1]['rate']=10;rows[1]['exact']=False
  with self.assertRaises(ValueError):winner.choose(rows)
 def test_shared_drain(self):
  from drain_gate import DEFAULT_DRAIN_ROOT
  self.assertEqual(screen.SHARED/'v3',DEFAULT_DRAIN_ROOT)
if __name__=='__main__':unittest.main()
