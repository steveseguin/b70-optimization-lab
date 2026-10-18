"""CPU-only selection/refusal checks; no native program or device is opened."""
import ast,copy,json,resource,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import bracket,bracket_config,common,cpu_seal,bracket_job

P=Path(__file__).resolve().parent

class V5Tests(unittest.TestCase):
 def setUp(self):
  self.base=json.loads((P/'lineage/selection.json').read_text())
 def test_each_registered_candidate_same_layout(self):
  for candidate in bracket_config.VALUES:
   row=copy.deepcopy(self.base);row['choices']['expert_kernels']=candidate
   self.assertTrue(bracket.compatible([self.base,row,self.base,row,self.base]))
 def test_every_other_choice_frozen(self):
  for key in self.base['choices']:
   if key=='expert_kernels':continue
   row=copy.deepcopy(self.base);row['choices'][key]='changed'
   with self.subTest(key=key),self.assertRaises(ValueError):bracket.compatible([self.base,row])
 def test_draft_frozen(self):
  for key in self.base['draft']:
   row=copy.deepcopy(self.base);row['draft'][key]='changed'
   with self.subTest(key=key),self.assertRaises(ValueError):bracket.compatible([self.base,row])
 def test_unregistered_candidate_refused(self):
  row=copy.deepcopy(self.base);row['choices']['expert_kernels']='winner'
  with self.assertRaises(ValueError):bracket.compatible([self.base,row])
 def test_config_exact_hashes_and_order(self):
  with tempfile.TemporaryDirectory(prefix='p115-test-') as tmp:
   root=Path(tmp);(root/'lineage').mkdir()
   (root/'lineage/selection.json').write_text(json.dumps(self.base))
   with patch.object(bracket_config,'HERE',root),patch.object(bracket_config,'LINEAGE',root/'lineage'),patch.object(common,'HERE',root):
    bracket_config.prepare('e3-next')
    config=bracket.load_config(root/'configs/bracket.json')
    self.assertEqual(len(config['views']),5)
    row=json.loads((root/'lineage/candidate.json').read_text());row['choices']['expert_kernels']='e5-shared'
    (root/'lineage/candidate.json').write_text(json.dumps(row))
    with self.assertRaisesRegex(ValueError,'selection changed'):bracket.load_config(root/'configs/bracket.json')
 def test_missing_seal_blocks_before_micro(self):
  with patch.object(cpu_seal,'verify',side_effect=ValueError('CPU seal missing')),patch.object(bracket_job,'micro_winner') as winner:
   with self.assertRaisesRegex(ValueError,'CPU seal missing'):
    bracket_job.main(['--lane','B','--output','/tmp/p115-not-created','--plan'])
   winner.assert_not_called()
 def test_missing_micro_blocks_before_device_screen(self):
  with patch.object(cpu_seal,'verify',return_value={}),patch.object(bracket_job,'micro_winner',side_effect=ValueError('no qualifying design')):
   with self.assertRaisesRegex(ValueError,'no qualifying design'):
    bracket_job.main(['--lane','B','--output','/tmp/p115-not-created'])
 def test_runtime_imports_preserve_limits(self):
  before={k:resource.getrlimit(k) for k in common.module('p115_limits_for_test',P/'exec_limits.py').KINDS}
  __import__('screen');__import__('tp2_worker')
  self.assertEqual(before,{k:resource.getrlimit(k) for k in before})
 def test_all_python_sources_parse(self):
  for p in P.glob('*.py'):
   with self.subTest(path=p.name):ast.parse(p.read_text(),filename=str(p))

if __name__=='__main__':unittest.main()
