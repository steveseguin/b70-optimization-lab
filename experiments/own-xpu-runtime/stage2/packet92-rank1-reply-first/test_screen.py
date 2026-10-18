import json,unittest,tempfile,subprocess
from unittest.mock import patch
from screen_jobs import jobs,command,choose,lanes,DIRECTIONS,WRAPPER,P,winner
from compare import confirmed,compare_direction
from bundle_selection import VIEWS,choices
from lane_admission import Reservation,admission_scope
class ScreenTest(unittest.TestCase):
 def rows(self,source,direction,rates=(40,42,41)):
  return [dict(choice=r['choice'],rate=v,exact=True,acceptance_counts=[(100,127)]*12) for r,v in zip(jobs(source,direction=direction),rates)]
 def test_directions(self):
  names=[]
  for direction in DIRECTIONS:
   source,other=lanes(direction)
   for lane in (source,other):
    rows=jobs(lane,'reply-first',direction);names += [r['out'] for r in rows]
    self.assertEqual([r['choice'] for r in rows],['production','reply-first','production'])
    for r in rows:self.assertIn('--plan',command(r,lane,plan=True));self.assertEqual(r['placement'],'1')
   def load(r,lane):return dict(choice=r['choice'],rate=42 if r['choice']=='reply-first' else 40,exact=True,acceptance_counts=[(100,127)]*12)
   with patch('compare.load',side_effect=load):
    self.assertEqual(winner(direction)['choice'],'reply-first');self.assertEqual(compare_direction(direction)['confirmation_lane'],other)
  self.assertEqual(len(names),len(set(names)))
  with self.assertRaises(ValueError):lanes('unknown')
 def test_quality_and_speed_refusals(self):
  for direction in DIRECTIONS:
   source,_=lanes(direction);grid=self.rows(source,direction);self.assertEqual(choose(grid)['choice'],'reply-first')
   for key in ('exact','rate','acceptance_counts','choice','missing','nan'):
    rows=[dict(r) for r in grid]
    if key=='exact':rows[0][key]=False
    if key=='rate':rows[2][key]=43
    if key=='acceptance_counts':rows[1][key]=[(99,127)]*12
    if key=='choice':rows[1][key]='unknown'
    if key=='missing':rows.pop()
    if key=='nan':rows[1]['rate']=float('nan')
    with self.subTest(key=key,direction=direction),self.assertRaises(ValueError):choose(rows)
    with self.subTest(key=key,direction=direction),self.assertRaises(ValueError):confirmed(grid,rows)
 def test_recheck_before_launch(self):
  import run_screens
  for direction in DIRECTIONS:
   _,other=lanes(direction)
   argv=['run_screens.py','--lane',other,'--direction',direction,'--authorized-device-window','--fault-review','unused']
   with patch('sys.argv',argv),patch.object(run_screens,'lane_gate'),patch.object(run_screens,'verify'),patch.object(run_screens.screen,'unit_gate'),patch.object(run_screens.screen,'unit_conditions'),patch.object(run_screens,'winner',side_effect=[{'choice':'reply-first'},{'choice':'unknown'}]),patch.object(run_screens.subprocess,'Popen') as launch:
    with self.assertRaisesRegex(ValueError,'confirmation selection differs'):run_screens.main()
    launch.assert_not_called()
 def test_selection_only_host_changes(self):
  base=choices('production');self.assertEqual(base,json.loads((P/'selection.json').read_text())['choices'])
  candidate=choices('reply-first');self.assertEqual({k for k in base if base[k]!=candidate[k]},{'host_retire'})
 def test_admission(self):
  for lane in ('A','B'):
   self.assertEqual(admission_scope(lane,'screen'),'lane-'+lane)
   with tempfile.TemporaryDirectory() as d:self.assertEqual(Reservation(lane,window='screen',root=P.__class__(d)).scope,'lane-'+lane)
 def test_worker_closed_environment(self):
  code='import sys;sys.path.insert(0,sys.argv[1]);import tp2_worker'
  subprocess.run(['/usr/bin/python3','-B','-c',code,str(WRAPPER)],env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'},stdin=subprocess.DEVNULL,check=True,timeout=30)
 def test_unchanged_memory(self):
  from memory_plans import plan
  from memory_gate import configuration
  for name in VIEWS:self.assertEqual(configuration(plan(name),4096,1,0),configuration(plan('production'),4096,1,0))
if __name__=='__main__':unittest.main()
