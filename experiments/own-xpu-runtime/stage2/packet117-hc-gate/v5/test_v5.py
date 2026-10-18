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
   row=copy.deepcopy(self.base);row['choices']['hc_gate']=candidate
   self.assertTrue(bracket.compatible([self.base,row,self.base,row,self.base]))
 def test_every_other_choice_frozen(self):
  for key in self.base['choices']:
   if key=='hc_gate':continue
   row=copy.deepcopy(self.base);row['choices'][key]='changed'
   with self.subTest(key=key),self.assertRaises(ValueError):bracket.compatible([self.base,row])
 def test_draft_frozen(self):
  for key in self.base['draft']:
   row=copy.deepcopy(self.base);row['draft'][key]='changed'
   with self.subTest(key=key),self.assertRaises(ValueError):bracket.compatible([self.base,row])
 def test_unregistered_candidate_refused(self):
  row=copy.deepcopy(self.base);row['choices']['hc_gate']='winner'
  with self.assertRaises(ValueError):bracket.compatible([self.base,row])
 def test_config_exact_hashes_and_order(self):
  with tempfile.TemporaryDirectory(prefix='p117-test-') as tmp:
   root=Path(tmp);(root/'lineage').mkdir()
   (root/'lineage/selection.json').write_text(json.dumps(self.base))
   with patch.object(bracket_config,'HERE',root),patch.object(bracket_config,'LINEAGE',root/'lineage'),patch.object(common,'HERE',root):
    bracket_config.prepare('p117')
    config=bracket.load_config(root/'configs/bracket.json')
    self.assertEqual(len(config['views']),5)
    row=json.loads((root/'lineage/candidate.json').read_text());row['choices']['hc_gate']='unknown'
    (root/'lineage/candidate.json').write_text(json.dumps(row))
    with self.assertRaisesRegex(ValueError,'selection changed'):bracket.load_config(root/'configs/bracket.json')
 def test_missing_seal_blocks_before_micro(self):
  with patch.object(cpu_seal,'verify',side_effect=ValueError('CPU seal missing')),patch.object(bracket_job,'micro_winner') as winner:
   with self.assertRaisesRegex(ValueError,'CPU seal missing'):
    bracket_job.main(['--lane','B','--output','/tmp/p117-not-created','--plan'])
   winner.assert_not_called()
 def test_missing_micro_blocks_before_device_screen(self):
  with patch.object(cpu_seal,'verify',return_value={}),patch.object(bracket_job,'micro_winner',side_effect=ValueError('no qualifying design')):
   with self.assertRaisesRegex(ValueError,'no qualifying design'):
    bracket_job.main(['--lane','B','--output','/tmp/p117-not-created'])
 def test_micro_uses_clean_python_boundary(self):
  with patch.object(bracket_job.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='{"passed":true,"qualified":["p117"]}',stderr='')) as run:
   self.assertEqual(bracket_job.micro_winner(),'p117')
   self.assertEqual(run.call_args.args[0],['/usr/bin/python3','-B',str(P.parent/'micro_gate.py'),'--require-qualified'])
 def test_micro_subprocess_refusal(self):
  with patch.object(bracket_job.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='',stderr='gate refused')):
   with self.assertRaisesRegex(ValueError,'qualification refused'):bracket_job.micro_winner()
 def test_micro_wrong_winner_refusal(self):
  with patch.object(bracket_job.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='{"passed":true,"qualified":[]}',stderr='')):
   with self.assertRaisesRegex(ValueError,'not qualified'):bracket_job.micro_winner()
 def test_runtime_imports_preserve_limits(self):
  before={k:resource.getrlimit(k) for k in common.module('p117_limits_for_test',P/'exec_limits.py').KINDS}
  __import__('screen');__import__('tp2_worker')
  self.assertEqual(before,{k:resource.getrlimit(k) for k in before})
 def test_packet111_baseline_changes_only_gate_label(self):
  parent=json.loads((P.parents[1]/'packet111-record-bundle/selection.json').read_text())
  parent['choices']['hc_gate']='production'
  self.assertEqual(self.base,parent)
 def test_native_gate_keeps_wide_mix_and_stage_scope(self):
  native=(P/'native-src/main.cpp').read_text()
  self.assertIn('stage==2&&sealed_selection.choices.at("hc_gate")=="p117"',native)
  self.assertIn('(dev(c),ids,stage,p.g.context,true,',native)
  self.assertIn('domain(selection->choices,"other_fusion",{"fused"})',(P/'native/engine_bracket.hpp').read_text())
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
