import unittest
import screen_jobs as S
from compare import confirmed
def row(name,rate=100,exact=True,acceptance=1):return dict(choice=name,rate=rate,exact=exact,acceptance_counts=[(acceptance,2)]*12)
class Screens(unittest.TestCase):
 def test_single_candidate_isolated_names(self):
  seen=set()
  for name in S.VIEWS[1:]:
   for lane in ('A','B'):
    jobs=S.jobs(lane,choice=name,direction='B-grid',qualified=(name,))
    self.assertEqual([x['choice'] for x in jobs],['production',name,'production'])
    for j in jobs:self.assertNotIn(j['out'],seen);seen.add(j['out'])
 def test_no_full_grid(self):
  with self.assertRaises(ValueError):S.jobs('B',qualified=S.VIEWS[1:])
 def test_A_is_confirm(self):
  self.assertEqual(S.lanes('B-grid'),('B','A'))
  with self.assertRaises(ValueError):S.lanes('A-grid')
 def test_controls_and_acceptance(self):
  name=S.VIEWS[1];grid=[row('production'),row(name,101),row('production')]
  self.assertEqual(S.choose(grid,(name,))['choice'],name)
  self.assertEqual(confirmed(grid,grid,(name,))['choice'],name)
  for bad in (row(name,99),row(name,101,False),row(name,101,True,2)):
   with self.assertRaises(ValueError):S.choose([grid[0],bad,grid[2]],(name,))
   with self.assertRaises(ValueError):confirmed(grid,[grid[0],bad,grid[2]],(name,))
 def test_down_not_admitted(self):self.assertNotIn('down-byte-slm',S.VIEWS)
if __name__=='__main__':unittest.main()
