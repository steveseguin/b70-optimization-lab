import hashlib,json,unittest
from pathlib import Path
import prepare
P=Path(__file__).resolve().parent
class Preparation(unittest.TestCase):
 def test_fixed_fixture_hashes(self):
  m=json.loads((P/'manifest.json').read_text());self.assertEqual([0,23,47],[c['layer'] for c in m['cases']]);self.assertEqual(52224,m['copied_bytes'])
  for c in m['cases']:
   for f in c['fixtures'].values():
    b=Path(f['path']).read_bytes();self.assertEqual(f['bytes'],len(b));self.assertEqual(f['sha256'],hashlib.sha256(b).hexdigest())
 def test_balanced_schedule_and_all_cases(self):
  s=prepare.schedule();self.assertEqual(84,len(s))
  for warm,n in [(True,4),(False,24)]:
   for case in range(3):
    rows=[r for r in s if r['warmup']==warm and r['case']==case];self.assertEqual(n,len(rows));self.assertEqual(n//2,sum(r['order']==['A','B'] for r in rows));self.assertEqual(n//2,sum(r['order']==['B','A'] for r in rows))
  for case in range(3):
   counts={}
   for n,r in enumerate(s[12:]):
    if r['case']==case:counts[(n%3,tuple(r['order']))]=counts.get((n%3,tuple(r['order'])),0)+1
   self.assertEqual([4]*6,sorted(counts.values()))
  self.assertEqual(s,json.loads((P/'manifest.json').read_text())['schedule'])
 def test_fixed_budget(self):
  self.assertEqual(106481664,3*(16711680+18677760+12288+5120*2+81920));self.assertLess(3*(16711680+18677760+12288)+84*2*5120,128*1024**2)
 def test_control_reuse_plan(self):
  import build
  c,commands,objects=build.plan(P/'build/not-created-plan');self.assertEqual(39,len(objects));self.assertIn('-ffp-contract=off',commands[0]);self.assertIn('-fno-fast-math',commands[0]);self.assertEqual(str(P/'runner.cpp'),commands[0][commands[0].index('-c')+1]);self.assertFalse((P/'build/not-created-plan').exists())
if __name__=='__main__':unittest.main(verbosity=2)
