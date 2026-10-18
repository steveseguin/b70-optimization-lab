"""CPU-only selection/refusal checks; no native program or device is opened."""
import ast,copy,json,resource,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import bracket,bracket_config,common,cpu_seal,bracket_job

P=Path(__file__).resolve().parent

class V5Tests(unittest.TestCase):
 def setUp(self):
  self.base=json.loads((P/'lineage/selection.json').read_text())
 def test_each_registered_candidate_same_layout(self):
  for candidate in bracket_config.VALUES:
   row=copy.deepcopy(self.base);row['choices']['down_warm']=candidate
   self.assertTrue(bracket.compatible([self.base,row,self.base,row,self.base]))
 def test_every_other_choice_frozen(self):
  for key in self.base['choices']:
   if key=='down_warm':continue
   row=copy.deepcopy(self.base);row['choices'][key]='changed'
   with self.subTest(key=key),self.assertRaises(ValueError):bracket.compatible([self.base,row])
 def test_draft_frozen(self):
  for key in self.base['draft']:
   row=copy.deepcopy(self.base);row['draft'][key]='changed'
   with self.subTest(key=key),self.assertRaises(ValueError):bracket.compatible([self.base,row])
 def test_unregistered_candidate_refused(self):
  row=copy.deepcopy(self.base);row['choices']['down_warm']='winner'
  with self.assertRaises(ValueError):bracket.compatible([self.base,row])
 def test_config_exact_hashes_and_order(self):
  with tempfile.TemporaryDirectory(prefix='p119-test-') as tmp:
   root=Path(tmp);(root/'lineage').mkdir()
   (root/'lineage/selection.json').write_text(json.dumps(self.base))
   with patch.object(bracket_config,'HERE',root),patch.object(bracket_config,'LINEAGE',root/'lineage'),patch.object(common,'HERE',root):
    bracket_config.prepare('p119')
    config=bracket.load_config(root/'configs/bracket.json')
    self.assertEqual(len(config['views']),5)
    row=json.loads((root/'lineage/candidate.json').read_text());row['choices']['down_warm']='unknown'
    (root/'lineage/candidate.json').write_text(json.dumps(row))
    with self.assertRaisesRegex(ValueError,'selection changed'):bracket.load_config(root/'configs/bracket.json')
 def test_missing_seal_blocks_before_micro(self):
  with patch.object(cpu_seal,'verify',side_effect=ValueError('CPU seal missing')),patch.object(bracket_job,'micro_winner') as winner:
   with self.assertRaisesRegex(ValueError,'CPU seal missing'):
    bracket_job.main(['--lane','B','--output','/tmp/p119-not-created','--plan'])
   winner.assert_not_called()
 def test_missing_micro_blocks_before_device_screen(self):
  with patch.object(cpu_seal,'verify',return_value={}),patch.object(bracket_job,'micro_winner',side_effect=ValueError('no qualifying design')):
   with self.assertRaisesRegex(ValueError,'no qualifying design'):
    bracket_job.main(['--lane','B','--output','/tmp/p119-not-created'])
 def test_micro_uses_clean_python_boundary(self):
  with patch.object(bracket_job.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='{"passed":true,"qualified":["p119"]}',stderr='')) as run:
   self.assertEqual(bracket_job.micro_winner(),'p119')
   self.assertEqual(run.call_args.args[0],['/usr/bin/python3','-B',str(P.parent/'micro_gate.py'),'--require-qualified'])
 def test_micro_subprocess_refusal(self):
  with patch.object(bracket_job.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='',stderr='gate refused')):
   with self.assertRaisesRegex(ValueError,'qualification refused'):bracket_job.micro_winner()
 def test_micro_wrong_winner_refusal(self):
  with patch.object(bracket_job.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='{"passed":true,"qualified":[]}',stderr='')):
   with self.assertRaisesRegex(ValueError,'not qualified'):bracket_job.micro_winner()
 def test_runtime_imports_preserve_limits(self):
  before={k:resource.getrlimit(k) for k in common.module('p119_limits_for_test',P/'exec_limits.py').KINDS}
  __import__('screen');__import__('tp2_worker')
  self.assertEqual(before,{k:resource.getrlimit(k) for k in before})
 def test_packet118_baseline_adds_only_warm_dimension(self):
  parent=json.loads((P.parents[1]/'packet118-record-bundle/selection.json').read_text())
  parent['choices']['down_warm']='production'
  self.assertEqual(self.base,parent)
 def test_native_switch_domain_is_warm_only(self):
  native=(P/"native/engine_bracket.hpp").read_text()
  self.assertIn('key!="down_warm"',native)
  self.assertIn('domain(selection->choices,"down_warm",{"production","p119"})',native)
  self.assertIn('domain(selection->choices,"hc_gate",{"wide"})',native)
 def test_drain_sleep_clamped(self):
  self.assertIn("self.sleep(max(0.0, min(.25, until - self.now())))",(P/"conditions.py").read_text())
 def test_retained_artifacts_missing_or_changed_refused(self):
  with tempfile.TemporaryDirectory(prefix='p119-artifact-') as tmp:
   root=Path(tmp)
   names=('build/device/own-rt-iq3','build/full-shape/fixture','build/reset-bytes/fixture','shape.tar.gz','protocol-native')
   for name in names:
    path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'bound')
   digest=common.sha(root/names[0]);binary={str(root/'protocol-native'):digest}
   rows={'build':{'artifacts':{names[0]:digest}},'full-shape':{'binary_sha256':digest,'runs':[{'artifact':{'path':str(root/'shape.tar.gz'),'sha256':digest,'members':1,'all_original_bytes_verified':True}}],'startup_runs':[]},'reset-bytes':{'binary_sha256':digest},'protocol':{'binaries':binary,'runs':[{'binaries':binary}]}}
   with patch.object(cpu_seal,'HERE',root):
    self.assertEqual(len(cpu_seal.receipt_artifacts(rows)),5)
    for name in names:
     path=root/name
     path.write_bytes(b'altered')
     with self.subTest(artifact=name),self.assertRaisesRegex(ValueError,'artifact changed'):cpu_seal.receipt_artifacts(rows)
     path.unlink()
     with self.subTest(missing=name),self.assertRaisesRegex(ValueError,'artifact changed'):cpu_seal.receipt_artifacts(rows)
     path.write_bytes(b'bound')
 def test_runtime_dependency_closure_changes_refused(self):
  entries=cpu_seal.external_runtime_sources()
  dependency=str((P.parents[1]/'packet56-draft-prefix/pipeline.py').relative_to(common.ROOT))
  self.assertIn(dependency,entries)
  wrapper=P.parents[1]/'screen/v4-lanes/wrapper-seal.json'
  row=common.read(wrapper);row['sources'][dependency]='0'*64
  with patch.object(cpu_seal,'read',return_value=row),self.assertRaisesRegex(ValueError,'sealed file changed'):
   cpu_seal.external_runtime_sources()
 def test_all_python_sources_parse(self):
  for p in P.glob('*.py'):
   with self.subTest(path=p.name):ast.parse(p.read_text(),filename=str(p))

if __name__=='__main__':
 from build_engine import limits,save,sha,ROOT
 limits()
 result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(V5Tests))
 save(P/'evidence/policy.json',dict(passed=result.wasSuccessful(),device_executed=False,tests=result.testsRun,
  sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'test_v5.py',P/'bracket.py',P/'bracket_job.py',P/'bracket_config.py')}))
 raise SystemExit(not result.wasSuccessful())
