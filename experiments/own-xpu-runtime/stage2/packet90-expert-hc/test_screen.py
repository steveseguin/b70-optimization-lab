import json,os,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from screen_jobs import jobs,command,choose,winner,lanes,DIRECTIONS,WRAPPER,P
from compare import confirmed,compare_direction
from bundle_selection import VIEWS,choices
from lane_admission import Reservation,admission_scope
class ScreenTest(unittest.TestCase):
 def test_grid(self):
  self.assertEqual([r['choice'] for r in jobs('A')],list(VIEWS)+['production'])
  for c in VIEWS[1:]:
   rows=jobs('B',c);self.assertEqual([r['choice'] for r in rows],['production',c,'production'])
   for row in rows:
    cmd=command(row,'B',plan=True);self.assertEqual(cmd[2],str(WRAPPER/'screen.py'))
    self.assertEqual(row['placement'],'1');self.assertIn('--plan',cmd);self.assertNotIn('--authorized-device-window',cmd)
 def test_winner(self):
  rows=[dict(choice=c,rate=r,exact=True,acceptance_counts=[(100,127)]*12) for c,r in zip(list(VIEWS)+['production'],(40,42,43,41))]
  self.assertEqual(choose(rows)['choice'],'hc-weightcache')
  for mutation in ('inexact','slow','missing','reordered','acceptance'):
   copy=[dict(r) for r in rows]
   if mutation=='acceptance':copy[1]['acceptance_counts']=[(99,127)]*12
   if mutation=='inexact':copy[2]['exact']=False
   if mutation=='slow':copy[-1]['rate']=45
   if mutation=='missing':copy.pop()
   if mutation=='reordered':copy[1],copy[2]=copy[2],copy[1]
   with self.assertRaises(ValueError):choose(copy)
 def test_both_directions(self):
  outputs=[]
  for direction in DIRECTIONS:
   source,other=lanes(direction)
   grid=jobs(source,direction=direction)
   self.assertEqual([r['choice'] for r in grid],list(VIEWS)+['production'])
   confirmation=jobs(other,'hc-weightcache',direction)
   self.assertEqual([r['choice'] for r in confirmation],['production','hc-weightcache','production'])
   outputs.extend(r['out'] for r in grid+confirmation)
   def loaded(row,lane):
    self.assertIn('-'+direction+'-'+lane+'-',row['out'])
    return dict(choice=row['choice'],exact=True,rate={'production':40,'exp-halfcache':41,'hc-weightcache':42}[row['choice']],acceptance_counts=[(100,127)]*12)
   with patch('compare.load',side_effect=loaded):
    self.assertEqual(winner(direction)['choice'],'hc-weightcache')
    result=compare_direction(direction)
    self.assertEqual(result['source_lane'],source)
    self.assertEqual(result['confirmation_lane'],other)
    self.assertEqual(result['winner']['choice'],'hc-weightcache')
  self.assertEqual(len(outputs),len(set(outputs)))
  self.assertEqual(jobs('A'),jobs('A',direction='A-grid'))
  with self.assertRaises(ValueError):lanes('C-grid')
 def test_confirmation_refusals_both_directions(self):
  for direction in DIRECTIONS:
   source,other=lanes(direction)
   grid=[dict(choice=r['choice'],rate=rate,exact=True,acceptance_counts=[(100,127)]*12) for r,rate in zip(jobs(source,direction=direction),(40,42,43,41))]
   baseline=[dict(choice=r['choice'],rate=rate,exact=True,acceptance_counts=[(100,127)]*12) for r,rate in zip(jobs(other,'hc-weightcache',direction),(40,43,41))]
   self.assertEqual(confirmed(grid,baseline)['choice'],'hc-weightcache')
   for mutation in ('different-winner','inexact','acceptance','slow-first','slow-last','missing','nonfinite'):
    rows=[dict(r) for r in baseline]
    if mutation=='different-winner':rows[1]['choice']='exp-halfcache'
    if mutation=='inexact':rows[0]['exact']=False
    if mutation=='acceptance':rows[1]['acceptance_counts']=[(99,127)]*12
    if mutation=='slow-first':rows[0]['rate']=43
    if mutation=='slow-last':rows[-1]['rate']=44
    if mutation=='missing':rows.pop()
    if mutation=='nonfinite':rows[1]['rate']=float('nan')
    with self.subTest(direction=direction,mutation=mutation),self.assertRaises(ValueError):confirmed(grid,rows)
 def test_driver_rechecks_winner_both_directions(self):
  import run_screens
  for direction in DIRECTIONS:
   _,other=lanes(direction)
   argv=['run_screens.py','--lane',other,'--direction',direction,'--authorized-device-window','--fault-review','unused']
   with patch('sys.argv',argv),patch.object(run_screens,'lane_gate'),patch.object(run_screens,'verify'),patch.object(run_screens.screen,'unit_gate'),patch.object(run_screens.screen,'unit_conditions'),patch.object(run_screens,'winner',side_effect=[{'choice':'hc-weightcache'},{'choice':'exp-halfcache'}]),patch.object(run_screens.subprocess,'Popen') as launch:
    with self.assertRaisesRegex(ValueError,'confirmation selection differs'):run_screens.main()
    launch.assert_not_called()
 def test_choices(self):
  self.assertEqual(choices('production'),json.loads((P/'selection.json').read_text())['choices'])
  for name in VIEWS:
   c=choices(name);self.assertEqual(c['experts'],'exp-halfcache' if name=='exp-halfcache' else 'wide64');self.assertEqual(c['hc_gate'],'hc-weightcache' if name=='hc-weightcache' else 'wide');self.assertEqual(c['packed_dense'],'production')
  with self.assertRaises(ValueError):choices('unknown')
 def test_admission(self):
  for lane in ('A','B'):
   self.assertEqual(admission_scope(lane,'screen'),'lane-'+lane)
   with tempfile.TemporaryDirectory() as d:self.assertEqual(Reservation(lane,window='screen',root=Path(d)).scope,'lane-'+lane)
 def test_closed_worker_import(self):
  code='import sys;sys.path.insert(0,sys.argv[1]);import tp2_worker;from lane_admission import admission_scope;assert admission_scope("A","screen")=="lane-A"'
  subprocess.run(['/usr/bin/python3','-B','-c',code,str(WRAPPER)],env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'},stdin=subprocess.DEVNULL,check=True,timeout=30)

class ConsumerBoundaryTest(unittest.TestCase):
 def test_parent_dispatch_and_promotion_consumers(self):
  # Execute the frozen consumers under their own import root. They must not
  # silently turn screen selections into chain/promotion qualification.
  code=r'''
import json,sys
from pathlib import Path
parent,packet=map(Path,sys.argv[1:]);sys.path.insert(0,str(parent))
import merge_dispatch,packet56_submission,p49d_k2
base=json.loads((parent/'bundle-selection.json').read_text())
dispatch=json.loads((packet/'dispatch-speed6.json').read_text())
assert merge_dispatch.merge([dispatch])[0]==dispatch
for name in ('exp-halfcache','hc-weightcache'):
 s=json.loads((packet/'selection.json').read_text());b=dict(base)
 if name=='exp-halfcache':s['choices']['experts']=name;b['experts']=name
 else:s['choices']['hc_gate']=name;b['hc']=name
 try:packet56_submission.validate_bundle(b,s)
 except ValueError:pass
 else:raise AssertionError('parent submission accepts unqualified cache')
 try:p49d_k2.measured_coverage('/nonexistent/packet90-not-a-chain',s)
 except ValueError:pass
 else:raise AssertionError('legacy K2 accepts new choice map')
print('unchanged dispatch passes; unqualified K2/submission views refuse')
'''
  subprocess.run(['/usr/bin/python3','-B','-c',code,str(P.parent/'packet84-record-bundle'),str(P)],env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'},stdin=subprocess.DEVNULL,check=True,timeout=60)
 def test_memory_plan_layout_delta(self):
  from memory_plans import plan,DELTA
  from memory_gate import configuration
  for view in VIEWS:
   row=plan(view);self.assertEqual(set(row['placements']),{'1'})
   ranks=configuration(row,4096,1,0)['ranks'];base=configuration(plan('production'),4096,1,0)['ranks']
   for rank,(r,b) in enumerate(zip(ranks,base)):self.assertEqual(r['arena_device_bytes']-b['arena_device_bytes'],DELTA[view][rank])
  with self.assertRaises(ValueError):configuration(plan('exp-halfcache'),4096,1,23)

if __name__=='__main__':unittest.main()
