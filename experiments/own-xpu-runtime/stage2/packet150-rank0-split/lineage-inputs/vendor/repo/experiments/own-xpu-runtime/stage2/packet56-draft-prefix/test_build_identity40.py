"""Synthetic compiler-input binding tests; no compiler/runtime/device executes."""
import json,os,tempfile,unittest
from pathlib import Path
import build_identity40 as b
class Mirrors(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='mirror-unit-',dir=b.B);self.p=Path(self.tmp.name);self.build=self.p/'build';self.build.mkdir()
  for name in b.GENERATORS:(self.p/name).write_text('# synthetic '+name+'\n')
  self.src=self.p/'source.hpp';self.src.write_text('current source\n')
  self.target=self.build/'checked/source.hpp';self.target.parent.mkdir();self.target.write_text('stale source\n')
 def tearDown(self):self.tmp.cleanup()
 def sources(self):return {'source.hpp':b.sha(self.src),**{n:b.sha(self.p/n) for n in b.GENERATORS}}
 def kernel(self):
  content='checked: '+self.src.read_text()
  if self.target.read_text()!=content:self.target.write_text(content)
  return {self.src:self.target}
 def validation(self,dest):
  dest.mkdir(parents=True,exist_ok=True);(dest/'device_validation.hpp').write_text('validation: '+self.src.read_text())
 def refresh(self,**kw):return b.regenerate_mirrors(self.p,self.build,kernel=kw.get('kernel',self.kernel),validation=self.validation,sources=self.sources)
 def row(self,proof):return dict(mirror_second_refresh_unchanged=True,dependency_graph_noop=True,mirror_sha256=proof['actual_sha256'],mirror_regeneration=proof,mirror_generator_sha256=proof['generator_sha256'])
 def test_stale_mirror_regenerated_before_binding(self):
  before=b.sha(self.target);proof=self.refresh();self.assertNotEqual(before,b.sha(self.target));self.assertIn('checked/source.hpp',proof['changed']);self.assertTrue(b.verify_mirror_receipt(self.row(proof),self.p,self.build))
 def test_source_metadata_alone_never_certifies_stale_mirror(self):
  proof=self.refresh();row=self.row(proof);self.target.write_text('stale source restored\n');row['source_sha256']=self.sources()
  with self.assertRaisesRegex(ValueError,'actual compiler mirrors'):b.verify_mirror_receipt(row,self.p,self.build)
 def test_overlay_change_invalidates_proof(self):
  row=self.row(self.refresh());(self.p/'kernel_overlay.py').write_text('changed')
  with self.assertRaisesRegex(ValueError,'generator/overlay'):b.verify_mirror_receipt(row,self.p,self.build)
 def test_second_generation_is_content_and_mtime_noop(self):
  self.refresh();files=b.mirror_files(self.build);before={str(p):p.stat().st_mtime_ns for p in files};proof=self.refresh()
  self.assertEqual(proof['changed'],[]);self.assertEqual(before,{str(p):p.stat().st_mtime_ns for p in files})
 def test_all_host_validation_outputs_bound(self):
  proof=self.refresh()
  for mode in ('gnu-host','icpx-host','asan'):self.assertIn(mode+'/validation/device_validation.hpp',proof['actual_sha256'])
 def test_generation_source_race_refused(self):
  def changed():
   result=self.kernel();self.src.write_text('changed while regenerating');return result
  with self.assertRaisesRegex(ValueError,'source changed'):self.refresh(kernel=changed)
 def test_missing_or_outside_mapping_refused(self):
  for target in (self.build/'absent.hpp',self.src):
   with self.subTest(target=target),self.assertRaisesRegex(ValueError,'missing/outside'):self.refresh(kernel=lambda:{self.src:target})
 def test_legacy_metadata_or_noop_false_refused(self):
  for row in ({'source_sha256':self.sources()},dict(self.row(self.refresh()),dependency_graph_noop=False)):
   with self.assertRaises(ValueError):b.verify_mirror_receipt(row,self.p,self.build)
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Mirrors))
 row=dict(passed=result.wasSuccessful(),device_executed=False,compiler_executed=False,tests=result.testsRun,source_sha256={n:b.sha(b.P/n) for n in ('build_identity40.py','test_build_identity40.py')})
 (b.P/'build-mirror-regression-gates.json').write_text(json.dumps(row,indent=2)+'\n')
 raise SystemExit(not result.wasSuccessful())
