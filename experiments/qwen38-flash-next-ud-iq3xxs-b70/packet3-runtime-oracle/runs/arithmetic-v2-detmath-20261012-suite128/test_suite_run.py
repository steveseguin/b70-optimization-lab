"""CPU-only prefix-gate and fixture-range regressions with sealed bytes."""
import json,shutil,tempfile,unittest
from pathlib import Path
import suite_run as r
class Gates(unittest.TestCase):
 def test_fixture_ranges(self):
  for n in (1,8,64,96,97,100,104,128):
   self.assertEqual(r.fixture_steps(n),list(range(1,min(n,8)+1))+list(range(97,min(n,104)+1)))
 def test_prefix_and_corruption(self):
  r.disk_guard()
  ref=r.SEALED/'incident-retrospective'
  with tempfile.TemporaryDirectory(prefix='.gate-tests.partial-',dir=r.HERE) as temp:
   d=Path(temp)
   shutil.copyfile(ref/'result.json',d/'result.json')
   for step in ref.glob('step*'):shutil.copytree(step,d/step.name)
   self.assertTrue(r.equality(d)['passed'])
   result=r.read(d/'result.json');result['tokens']+=[123]*64
   r.save(d/'result.json',result)
   self.assertTrue(r.equality(d)['passed'])
   result['tokens'][63]^=1;r.save(d/'result.json',result)
   with self.assertRaisesRegex(RuntimeError,'prefix tokens'):r.equality(d)
   result['tokens'][63]^=1;r.save(d/'result.json',result)
   f=d/'step8/layer-47.bf16';raw=bytearray(f.read_bytes());raw[-1]^=1;f.write_bytes(raw)
   with self.assertRaisesRegex(RuntimeError,'prefix fixture'):r.equality(d)
 def test_build_delta(self):
  old=(r.P17/'oracle.cpp').read_text()
  new=(r.HERE/'oracle128.cpp').read_text()
  self.assertIn('a.context=192',old);self.assertIn('a.context=256',new)
  self.assertIn('a.tokens<=128',new)
  b=r.read(r.HERE/'build-receipt.json')
  self.assertEqual(b['binary_sha256'],r.sha(r.HERE/'build/oracle'))
  self.assertFalse(b['device_executed'])
if __name__=='__main__':unittest.main()
