import unittest
from summary import summarise,sequence_summary
class MockTiming(unittest.TestCase):
 def records(self):
  out=[]
  for owner in (1,2):
   for candidate in ('current','rows4','staged'):
    for r in range(200):
     ns={'current':[100000],'rows4':[80000],'staged':[20000,30000]}[candidate]
     out.append(dict(owner=owner,shape='expert',**{'class':'expsgate'},candidate=candidate,frequency=48,repetition=r,passed=True,events=[dict(command_start_ns=1+i*1000000,command_end_ns=1+i*1000000+n) for i,n in enumerate(ns)]))
  return out
 def test_sum_not_span_and_sort(self):
  rows=summarise(self.records());self.assertEqual(rows[0]['candidate'],'staged');self.assertAlmostEqual(rows[0]['median_ms'],.05);self.assertAlmostEqual(rows[0]['ms_per_token_saved'],2.4)
 def test_missing(self):
  rows=self.records();rows.pop()
  with self.assertRaises(AssertionError):summarise(rows)
 def test_duplicate(self):
  rows=self.records();rows[-1]['repetition']=0
  with self.assertRaises(AssertionError):summarise(rows)
 def test_zero(self):
  rows=self.records();rows[0]['events'][0]['command_end_ns']=1
  with self.assertRaises(AssertionError):summarise(rows)
 def test_failed_excluded(self):
  rows=self.records();rows[0]['passed']=False
  with self.assertRaises(AssertionError):summarise(rows)
 def test_two_owners(self):
  with self.assertRaises(AssertionError):summarise([r for r in self.records() if r['owner']==1])
 def test_full_sequence(self):
  rows=[dict(tier=t,repetition=r,layers=48,waits=1,launch_groups=253,wall_ms=20) for t in range(7) for r in range(200)]
  self.assertEqual(len(sequence_summary(rows,True)),7)
  rows[-1]['launch_groups']=252
  with self.assertRaises(AssertionError):sequence_summary(rows,True)
 def test_full_sequence_missing(self):
  with self.assertRaises(AssertionError):sequence_summary([],True)
if __name__=='__main__':unittest.main()
