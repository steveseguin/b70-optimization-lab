"""Synthetic decision fixtures only; never device evidence."""
import unittest
from read_run import decision,overlap,union
class Reader(unittest.TestCase):
    def test_both_views_and_warm_controls(self):
        rates=dict(A0=1000,A1=30,A2=30,B0=31,B1=31)
        self.assertTrue(decision(rates)['performance_candidate'])
        rates['B1']=30.1
        self.assertFalse(decision(rates)['performance_candidate'])
        rates.update(B1=33,B0=33,A2=31)
        self.assertFalse(decision(rates)['performance_candidate'])
    def test_overlap_unions_not_double_counted(self):
        events=[dict(kind=k,start_ns=a,end_ns=b) for k,a,b in
                [('packed-H2D',1,10),('packed-H2D',2,8),('resident-gate',5,15),('resident-down',6,12)]]
        self.assertEqual(overlap([dict(events=events)]),5)
        self.assertEqual(union([(1,4),(3,6),(8,9)]),[[1,6],[8,9]])
if __name__=='__main__':unittest.main()
