"""CPU policy, selection and immutable runtime-boundary checks."""
import ast,copy,json,resource,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import bracket,bracket_config,common,cpu_seal,bracket_job
P=Path(__file__).resolve().parent
class Tests(unittest.TestCase):
 def setUp(self):self.base=json.loads((P/'lineage/selection.json').read_text())
 def test_only_schedule_changes(self):
  row=copy.deepcopy(self.base);row['choices']['token_input']='both';self.assertTrue(bracket.compatible([self.base,row,self.base,row,self.base]))
  for section in ('choices','draft'):
   for key in self.base[section]:
    if section=='choices' and key=='token_input':continue
    bad=copy.deepcopy(row);bad[section][key]='changed'
    with self.subTest(section=section,key=key),self.assertRaises(ValueError):bracket.compatible([self.base,bad])
 def test_bad_schedule(self):
  row=copy.deepcopy(self.base);row['choices']['token_input']='unknown'
  with self.assertRaises(ValueError):bracket.compatible([self.base,row])
 def test_configs(self):
  for kind,count in [('smoke',1),('bracket',5)]:
   row=bracket.load_config(P/'configs'/(kind+'.json'));self.assertEqual(len(row['views']),count)
 def test_missing_seal_before_any_screen(self):
  with patch.object(cpu_seal,'verify',side_effect=ValueError('missing seal')),patch.object(bracket_job,'smoke_gate') as smoke:
   with self.assertRaisesRegex(ValueError,'missing seal'):bracket_job.main(['--kind','bracket','--lane','B','--output','/tmp/p137-no-write','--plan'])
   smoke.assert_not_called()
 def test_bracket_requires_smoke(self):
  with patch.object(cpu_seal,'verify',return_value={}),patch('readiness.verify_ready',return_value={}),patch.object(bracket_job,'smoke_gate',side_effect=ValueError('missing smoke')):
   with self.assertRaisesRegex(ValueError,'missing smoke'):bracket_job.main(['--kind','bracket','--lane','B','--output','/tmp/p137-no-write'])
 def test_bundle7_exact_baseline(self):
  parent=json.loads((P.parents[1]/'packet124c-record-bundle/selection.json').read_text());parent['choices']['token_input']='production';self.assertEqual(parent,self.base)
 def test_imports_preserve_limits(self):
  before={k:resource.getrlimit(k) for k in common.module('limit_kinds',P/'exec_limits.py').KINDS}
  __import__('screen');__import__('tp2_worker')
  self.assertEqual(before,{k:resource.getrlimit(k) for k in before})
 def test_native_domain_and_byte_capture(self):
  native=(P/'native/engine_bracket.hpp').read_text();self.assertIn('key!="token_input"',native);self.assertIn('{"production","both"}',native)
  self.assertIn('capture()==control_capture',(P/'native/full_shape_entry.cpp').read_text())
 def test_watchdog(self):
  import screen
  self.assertGreaterEqual(screen.WATCHDOG['tp2'],4*1200)
 def test_frozen_arithmetic_objects(self):
  build=common.read(P/'evidence/build.json')
  for row in build['commands']:
   if not row['name'].endswith('-link'):continue
   new=[Path(x).name for x in row['command'] if x.endswith('.o') and str(P/'build') in x]
   self.assertEqual(sorted(new),['entry-main.o','p49d_submit.o'])
 def test_all_python_parses(self):
  for f in [*P.glob('*.py'),*P.parent.glob('*.py')]:
   with self.subTest(path=f.name):ast.parse(f.read_text())
 def test_retained_artifacts_fail_closed(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);f=root/'a';f.write_bytes(b'one');digest=common.sha(f)
   common.verify_map(root,{'a':digest});f.write_bytes(b'two')
   with self.assertRaises(ValueError):common.verify_map(root,{'a':digest})
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 from build_engine import limits,save,sha,ROOT
 limits();result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 save(P/'evidence/policy.json',dict(passed=result.wasSuccessful(),device_executed=False,tests=result.testsRun,sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'test_v5.py',P/'bracket.py',P/'bracket_config.py',P/'bracket_job.py']}))
 raise SystemExit(not result.wasSuccessful())
