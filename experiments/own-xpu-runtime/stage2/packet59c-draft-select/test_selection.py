#!/usr/bin/env python3
"""Reject ambiguous selections in both Python sealing and native init."""
import copy,hashlib,json,subprocess,tempfile,time,unittest
from pathlib import Path
from p59c_selection import P,DEPENDENCIES,KEYS,GROUPS,profiles,selection,read,sha,save
from p59c_cpu_gate import constraints
B=P/'build'
class SelectionTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=B,prefix='selection-tests-');self.path=Path(self.temp.name)/'selection.json'
 def tearDown(self):self.temp.cleanup()
 def check(self,config,valid,raw=None,digest=None):
  self.path.write_text(json.dumps(config) if raw is None else raw)
  python_ok=True
  try:read(self.path)
  except (ValueError,AssertionError):python_ok=False
  if digest is None:self.assertEqual(python_ok,valid)
  r=subprocess.run([str(B/'p59c-route-fixture'),'--selection',str(self.path),digest if digest is not None else sha(self.path)],capture_output=True,text=True,timeout=10)
  self.assertEqual(r.returncode==0,valid,r.stderr)
 def test_every_profile(self):
  for name,value in profiles().items():
   with self.subTest(name=name):self.check(value,True)
 def test_production_defaults_and_partition(self):
  self.assertEqual(len(KEYS),40);self.assertEqual(len(DEPENDENCIES),10)
  self.assertEqual(set(selection()['draft'].values()),{'production'})
  self.assertEqual(set.union(*GROUPS.values()),KEYS);self.assertEqual(sum(map(len,GROUPS.values())),len(KEYS))
 def test_fusion_requires_its_producer(self):
  for key in DEPENDENCIES:
   with self.subTest(key=key):
    value=copy.deepcopy(selection());value['draft'][key]='packet59';self.check(value,False)
 def test_missing_key(self):
  value=copy.deepcopy(selection());del value['draft']['qgate'];self.check(value,False)
 def test_unknown_key(self):
  value=copy.deepcopy(selection());value['draft']['surprise']='production';self.check(value,False)
 def test_unknown_value(self):
  value=copy.deepcopy(selection());value['draft']['qgate']='fastest';self.check(value,False)
 def test_target_change(self):
  value=copy.deepcopy(selection());value['choices']['route']='production';self.check(value,False)
 def test_schema(self):
  value=copy.deepcopy(selection());value['schema']='packet49d.selection.v1';self.check(value,False)
 def test_duplicate_draft_key(self):
  value=copy.deepcopy(selection());raw=json.dumps(value).replace('"qgate": "production"','"qgate": "production", "qgate": "packet59"');self.check(value,False,raw)
 def test_duplicate_top_level(self):
  value=copy.deepcopy(selection());raw=json.dumps(value).replace('"draft":','"schema": "packet59c.selection.v1", "draft":');self.check(value,False,raw)
 def test_trailing_bytes(self):self.check(selection(),False,json.dumps(selection())+'garbage')
 def test_unknown_field(self):
  value=copy.deepcopy(selection());value['extra']=None;self.check(value,False)
 def test_hash_mismatch(self):self.check(selection(),False,digest='0'*64)
 def test_hash_required(self):self.check(selection(),False,digest='')
if __name__=='__main__':
 constraints();start=time.monotonic();suite=unittest.defaultTestLoader.loadTestsFromTestCase(SelectionTests);result=unittest.TextTestRunner(verbosity=2).run(suite)
 save(P/'selection-tests.json',{'passed':result.wasSuccessful(),'device_executed':False,'tests':result.testsRun,'profile_subtests':len(profiles()),'fusion_subtests':len(DEPENDENCIES),'failures':len(result.failures),'errors':len(result.errors),'seconds':time.monotonic()-start,'binary_sha256':sha(B/'p59c-route-fixture'),'sources':{n:sha(P/n) for n in ('test_selection.py','p59c_selection.py','p59c_select.hpp','p49d_submit.cpp','p49d_submit.hpp')}})
 raise SystemExit(not result.wasSuccessful())
