import json,unittest
from pathlib import Path
from bundle_selection import VIEWS,selection
from screen_jobs import jobs,choose,command,WRAPPER
from memory_plans import ledger,EXTRA
import memory_gate
class ScreenTests(unittest.TestCase):
 def test_either_lane_full_grid(self):
  for lane in ('A','B'):
   j=jobs(lane);self.assertEqual([r['choice'] for r in j],list(VIEWS)+['production'])
   self.assertEqual(len({r['out'] for r in j}),5)
   for r in j:self.assertEqual(command(r,lane,plan=True)[2],str(WRAPPER/'screen.py'))
 def test_confirm_controls(self):
  for lane in ('A','B'):
   for c in VIEWS[1:]:self.assertEqual([r['choice'] for r in jobs(lane,c,'confirm')],['production',c,'production'])
 def rows(self):return [dict(choice=c,exact=True,rate=r,acceptance=.78) for c,r in zip(list(VIEWS)+['production'],[100,103,101,102,100.5])]
 def test_winner(self):self.assertEqual(choose(self.rows())['choice'],'q4-g32')
 def test_failed_candidate_refuses(self):
  r=self.rows();r[2]['exact']=False
  with self.assertRaises(ValueError):choose(r)
 def test_no_improvement_refuses(self):
  r=self.rows();r[-1]['rate']=104
  with self.assertRaises(ValueError):choose(r)
 def test_missing_acceptance_refuses(self):
  r=self.rows();r[1]['acceptance']=float('nan')
  with self.assertRaises(ValueError):choose(r)
 def test_memory_includes_copy(self):
  control=ledger('production');v=ledger('q4-g32');row=memory_gate.configuration(v,4096,1,0)['ranks'][1]
  self.assertEqual(row['draft_duplicate_head_bytes'],EXTRA)
  self.assertEqual(row['arena_device_bytes']-control['placements']['1']['capacities']['4096']['ranks'][1]['arena_device_bytes'],EXTRA)
  row['total_with_mtp_bytes']-=1
  with self.assertRaises(ValueError):memory_gate.configuration(v,4096,1,0)
 def test_target_choices_fixed(self):
  self.assertEqual(len({json.dumps(selection(n)['choices'],sort_keys=True) for n in VIEWS}),1)
 def test_coverage_minimal(self):
  p=Path(__file__).parent;c=json.loads((p/'coverage.json').read_text());h=json.loads((p.parent/'packet56-draft-prefix/calibration/selection.json').read_text())
  for row in c['rows']:
   n=row['rows'];covered=lambda stop:sum(v for k,v in h['histogram'].items() if int(k)<stop)
   self.assertGreaterEqual(covered(n)/h['tokens'],row['threshold']);self.assertLess(covered(n-256)/h['tokens'],row['threshold'])
if __name__=='__main__':unittest.main()
