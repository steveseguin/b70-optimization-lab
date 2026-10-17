import json,os,subprocess,tempfile,unittest
from pathlib import Path
from screen_jobs import jobs,command,choose,WRAPPER,P
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
  rows=[dict(choice=c,rate=r,exact=True) for c,r in zip(list(VIEWS)+['production'],(40,42,41,45,44,41))]
  self.assertEqual(choose(rows)['choice'],'small-combined')
  for mutation in ('inexact','slow','missing','reordered'):
   copy=[dict(r) for r in rows]
   if mutation=='inexact':copy[2]['exact']=False
   if mutation=='slow':copy[-1]['rate']=45
   if mutation=='missing':copy.pop()
   if mutation=='reordered':copy[1],copy[2]=copy[2],copy[1]
   with self.assertRaises(ValueError):choose(copy)
 def test_choices(self):
  self.assertEqual(choices('production'),json.loads((P/'selection.json').read_text())['choices'])
  for name in VIEWS:
   c=choices(name);self.assertEqual(c['experts'],'wide64');self.assertEqual(c['packed_dense'],'production')
  with self.assertRaises(ValueError):choices('unknown')
 def test_admission(self):
  for lane in ('A','B'):
   self.assertEqual(admission_scope(lane,'screen'),'lane-'+lane)
   with tempfile.TemporaryDirectory() as d:self.assertEqual(Reservation(lane,window='screen',root=Path(d)).scope,'lane-'+lane)
 def test_closed_worker_import(self):
  code='import sys;sys.path.insert(0,sys.argv[1]);import tp2_worker;from lane_admission import admission_scope;assert admission_scope("A","screen")=="lane-A"'
  subprocess.run(['/usr/bin/python3','-B','-c',code,str(WRAPPER)],env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'},stdin=subprocess.DEVNULL,check=True,timeout=30)
if __name__=='__main__':unittest.main()
