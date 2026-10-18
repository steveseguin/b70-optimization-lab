import json,subprocess,sys,unittest,resource
from pathlib import Path
from unittest.mock import patch
import bundle_selection as b
from kd_reference import project
P=Path(__file__).resolve().parent
class Packet124Tests(unittest.TestCase):
 def test_exactly_one(self):
  self.assertEqual(len(b.views()),2)
  self.assertEqual({v[-1] for v in b.views().values()},{'production','interleave'})
  fixed=json.loads((P/'fixed-base.json').read_text())
  for v in b.views().values():
   row=dict(zip(b.KEYS,v));self.assertEqual({k:row[k] for k in fixed},fixed)
   self.assertLess(len(b.name(*v)+'--placement-1'),256)
   s=b.selection(v);ref=project(s)
   self.assertEqual(ref['draft'],s['draft']);self.assertEqual(ref['choices']['other_fusion'],'production');self.assertEqual(ref['choices']['head'],'production')
 def test_largest_vram(self):
  from memory_plans import plan
  base=plan(b.aliases()['base']);both=plan(b.aliases()['both'])
  a=base['placements']['1']['capacities']['4096']['ranks'];z=both['placements']['1']['capacities']['4096']['ranks']
  self.assertEqual([zz['arena_device_bytes']-aa['arena_device_bytes'] for aa,zz in zip(a,z)],[0,0])
  self.assertTrue(all(x['arena_margin_passed'] and x['allocation_margin_passed'] for x in z))
 def test_submission_both(self):
  import packet56_submission as s
  for v in b.views().values():
   row=dict(zip(b.KEYS,v),name=b.name(*v),placement='1',draft='draft-hc',miss='batch',draft_rank=1,target_split=0,layer_boundary=24)
   s.validate_bundle(row,b.selection(v));note=s.submission_notes(row)
   self.assertIn('other_fusion='+row['other_fusion'],note);self.assertIn('target_head='+row['target_head'],note);self.assertLessEqual(len(note),2000)
 def test_exec_rejects_inherited_cap(self):
  code="import resource;resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));import exec_limits;exec_limits.check(exec_limits.snapshot())"
  p=subprocess.run([sys.executable,'-B','-c',code],cwd=P,stdin=subprocess.DEVNULL,capture_output=True,text=True)
  self.assertNotEqual(p.returncode,0);self.assertIn('refuses finite RLIMIT_AS',p.stderr)
 def test_exec_observes_actual_popen_boundary(self):
  import exec_limits
  baseline=exec_limits.snapshot();events=[]
  with patch.object(subprocess,'Popen',return_value=None):
   exec_limits.install(lambda argv,limits:events.append(limits))
   subprocess.Popen(['/not-executed/own-rt-iq3','--authorized-device-window'])
  self.assertEqual(events,[baseline])
if __name__=='__main__':unittest.main()
