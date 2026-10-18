import json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from screen_jobs import jobs,command,choose,winner,lanes,DIRECTIONS,GRIDS,grid_choices,WRAPPER,P
from compare import confirmed,compare_direction
from bundle_selection import VIEWS,choices
from lane_admission import Reservation,admission_scope
class ScreenTest(unittest.TestCase):
 def rows(self,jobs):
  return [dict(choice=r['choice'],rate=42 if r['choice']!='production' else 40,exact=True,acceptance_counts=[(100,127)]*12) for r in jobs]
 def test_jobs_all_namespaces(self):
  outputs=[]
  for grid in GRIDS:
   for direction in DIRECTIONS:
    source,other=lanes(direction)
    a=jobs(source,direction=direction,grid=grid);b=jobs(other,'exp-grid-prefetch',direction,grid)
    self.assertEqual([r['choice'] for r in a],grid_choices(grid))
    self.assertEqual([r['choice'] for r in b],['production','exp-grid-prefetch','production'])
    for row,lane in [(r,source) for r in a]+[(r,other) for r in b]:
     outputs.append(row['out']);cmd=command(row,lane,plan=True)
     self.assertEqual(cmd[2],str(WRAPPER/'screen.py'));self.assertIn('--plan',cmd);self.assertNotIn('--authorized-device-window',cmd)
  self.assertEqual(len(outputs),len(set(outputs)))
 def test_closed_views_refuse(self):
  for name in ('exp-scalecache','exp-gate-up-shared-input','exp-halfcache','hc-weightcache'):
   with self.assertRaises(ValueError):choices(name)
   with self.assertRaises(ValueError):jobs('A',grid=name)
   with self.assertRaises(ValueError):jobs('B',name)
 def test_winner_and_refusals(self):
  for grid in GRIDS:
   for direction in DIRECTIONS:
    source,other=lanes(direction);rows=self.rows(jobs(source,direction=direction,grid=grid))
    self.assertEqual(choose(rows,grid)['choice'],'exp-grid-prefetch')
    for mutation in ('inexact','slow','missing','reordered','acceptance','nonfinite'):
     copy=[dict(r) for r in rows]
     if mutation=='acceptance':copy[1]['acceptance_counts']=[(99,127)]*12
     if mutation=='inexact':copy[1]['exact']=False
     if mutation=='slow':copy[-1]['rate']=45
     if mutation=='missing':copy.pop()
     if mutation=='reordered':copy[0],copy[1]=copy[1],copy[0]
     if mutation=='nonfinite':copy[1]['rate']=float('nan')
     with self.subTest(grid=grid,direction=direction,mutation=mutation),self.assertRaises(ValueError):choose(copy,grid)
    confirm=self.rows(jobs(other,'exp-grid-prefetch',direction,grid))
    self.assertEqual(confirmed(rows,confirm,grid)['choice'],'exp-grid-prefetch')
    for mutation in ('wrong','inexact','acceptance','slow-first','slow-last','missing','nonfinite'):
     copy=[dict(r) for r in confirm]
     if mutation=='wrong':copy[1]['choice']='exp-scalecache'
     if mutation=='inexact':copy[0]['exact']=False
     if mutation=='acceptance':copy[1]['acceptance_counts']=[(99,127)]*12
     if mutation=='slow-first':copy[0]['rate']=43
     if mutation=='slow-last':copy[-1]['rate']=43
     if mutation=='missing':copy.pop()
     if mutation=='nonfinite':copy[1]['rate']=float('nan')
     with self.subTest(grid=grid,direction=direction,mutation=mutation),self.assertRaises(ValueError):confirmed(rows,copy,grid)
 def test_complete_comparison(self):
  for grid in GRIDS:
   for direction in DIRECTIONS:
    source,other=lanes(direction)
    with patch('compare.load',side_effect=lambda r,l:self.rows([r])[0]):
     self.assertEqual(winner(direction,grid)['choice'],'exp-grid-prefetch')
     result=compare_direction(direction,grid)
     self.assertEqual(result['source_lane'],source);self.assertEqual(result['confirmation_lane'],other)
     self.assertEqual(result['grid_name'],grid)
 def test_driver_rechecks_winner(self):
  import run_screens
  for direction in DIRECTIONS:
   _,other=lanes(direction)
   argv=['run_screens.py','--lane',other,'--direction',direction,'--authorized-device-window','--fault-review','unused']
   with patch('sys.argv',argv),patch.object(run_screens,'lane_gate'),patch.object(run_screens,'verify'),patch.object(run_screens.screen,'unit_gate'),patch.object(run_screens.screen,'unit_conditions'),patch.object(run_screens,'winner',side_effect=[{'choice':'exp-grid-prefetch'},{'choice':'production'}]),patch.object(run_screens.subprocess,'Popen') as launch:
    with self.assertRaisesRegex(ValueError,'confirmation selection differs'):run_screens.main()
    launch.assert_not_called()
 def test_choices(self):
  self.assertEqual(choices('production'),json.loads((P/'selection.json').read_text())['choices'])
  for name in VIEWS:
   c=choices(name);self.assertEqual(c['experts'],name if name!='production' else 'wide64');self.assertEqual(c['hc_gate'],'wide');self.assertEqual(c['packed_dense'],'production');self.assertEqual(c['recurrence'],'rec-parallel');self.assertEqual(c['host_retire'],'ordered')
 def test_admission(self):
  for lane in ('A','B'):
   self.assertEqual(admission_scope(lane,'screen'),'lane-'+lane)
   with tempfile.TemporaryDirectory() as d:self.assertEqual(Reservation(lane,window='screen',root=Path(d)).scope,'lane-'+lane)
 def test_closed_worker_import(self):
  code='import sys;sys.path.insert(0,sys.argv[1]);import tp2_worker;from lane_admission import admission_scope;assert admission_scope("A","screen")=="lane-A"'
  subprocess.run(['/usr/bin/python3','-B','-c',code,str(WRAPPER)],env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'},stdin=subprocess.DEVNULL,check=True,timeout=30)
class ConsumerBoundaryTest(unittest.TestCase):
 def test_parent_dispatch_and_promotion_consumers(self):
  code=r'''
import json,sys
from pathlib import Path
parent,packet=map(Path,sys.argv[1:]);sys.path.insert(0,str(parent))
import merge_dispatch,packet56_submission,p49d_k2
base=json.loads((parent/'bundle-selection.json').read_text())
dispatch=json.loads((packet/'dispatch-speed6.json').read_text());assert merge_dispatch.merge([dispatch])[0]==dispatch
s=json.loads((packet/'selection.json').read_text());b=dict(base)
s['choices']['experts']='exp-grid-prefetch';b['experts']='exp-grid-prefetch'
try:packet56_submission.validate_bundle(b,s)
except ValueError:pass
else:raise AssertionError('parent submission accepts unqualified prefetch')
try:p49d_k2.measured_coverage('/nonexistent/packet95-not-a-chain',s)
except ValueError:pass
else:raise AssertionError('legacy K2 accepts new choice map')
'''
  subprocess.run(['/usr/bin/python3','-B','-c',code,str(P.parent/'packet84-record-bundle'),str(P)],env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'},stdin=subprocess.DEVNULL,check=True,timeout=60)
 def test_memory_plan(self):
  from memory_plans import plan,DELTA
  from memory_gate import configuration
  for view in VIEWS:
   row=plan(view);self.assertEqual(set(row['placements']),{'1'})
   ranks=configuration(row,4096,1,0)['ranks'];base=configuration(plan('production'),4096,1,0)['ranks']
   for rank,(r,b) in enumerate(zip(ranks,base)):self.assertEqual(r['arena_device_bytes']-b['arena_device_bytes'],DELTA[view][rank])
  with self.assertRaises(ValueError):configuration(plan('exp-grid-prefetch'),4096,1,23)
if __name__=='__main__':unittest.main()
