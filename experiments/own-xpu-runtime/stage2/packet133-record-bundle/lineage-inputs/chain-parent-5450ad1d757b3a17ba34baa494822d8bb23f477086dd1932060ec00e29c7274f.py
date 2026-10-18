"""Synthetic cleanup preserves every sealed artifact; never executes binaries."""
import contextlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import cleanup,storage
P=Path(__file__).resolve().parent
class Preservation(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='cleanup-bound-unit-',dir=P/'build');self.p=Path(self.tmp.name);self.b=self.p/'build';self.b.mkdir()
  self.artifact=self.b/'host-issue/host-issue-benchmark';self.artifact.parent.mkdir();self.artifact.write_bytes(b'ELF synthetic benchmark, never execute')
  self.seal=dict(passed=True,device_executed=False,artifacts_sha256={'host-issue/host-issue-benchmark':cleanup.digest(self.artifact)})
  (self.p/'build-receipt.json').write_text(json.dumps(self.seal))
  self.stack=contextlib.ExitStack();self.stack.enter_context(patch.multiple(cleanup,P=self.p,B=self.b));self.stack.enter_context(patch.multiple(storage,P=self.p,B=self.b))
 def tearDown(self):self.stack.close();self.tmp.cleanup()
 def test_cleanup_keeps_nested_bound_binary(self):
  scratch=self.b/'real-scratch';scratch.mkdir();(scratch/'receipt.json').write_text('{"passed":true}')
  with contextlib.redirect_stdout(io.StringIO()):cleanup.main()
  self.assertTrue(self.artifact.is_file());self.assertFalse(scratch.exists())
  report=json.loads((self.p/'scratch-cleanup.json').read_text());self.assertEqual(report['sealed_artifacts_preserved'],self.seal['artifacts_sha256']);self.assertIn('build/host-issue',report['preserved_artifact_directories'])
 def test_changed_bound_binary_refuses_before_deletion(self):
  self.artifact.write_bytes(b'changed')
  with self.assertRaisesRegex(AssertionError,'changed before cleanup'):cleanup.main()
  self.assertTrue(self.artifact.exists())
 def test_prefix_named_bound_directory_is_preserved(self):
  target=self.b/'real-bound/unit';target.parent.mkdir();target.write_bytes(b'bound');self.seal['artifacts_sha256']['real-bound/unit']=cleanup.digest(target)
  (self.p/'build-receipt.json').write_text(json.dumps(self.seal))
  with contextlib.redirect_stdout(io.StringIO()):cleanup.main()
  self.assertTrue(target.is_file())
 def test_outside_artifact_path_refused(self):
  self.seal['artifacts_sha256']['../outside']='0'*64
  with self.assertRaisesRegex(AssertionError,'unsafe sealed'):cleanup.sealed_artifacts(self.seal)
if __name__=='__main__':
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Preservation))
 (P/'cleanup-sealed-artifacts40-gates.json').write_text(json.dumps(dict(passed=r.wasSuccessful(),device_executed=False,runtime_executed=False,tests=r.testsRun,source_sha256={n:cleanup.digest(P/n) for n in ('cleanup.py','test_cleanup_sealed_artifacts40.py')}),indent=2)+'\n')
 raise SystemExit(not r.wasSuccessful())
