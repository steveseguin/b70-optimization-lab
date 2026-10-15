"""Fail closed if historical model evidence covers anything beyond fixture TUs."""
import copy,json,unittest
from pathlib import Path
from fixture_delta import verify_sources,compiled_sources,P
class Delta(unittest.TestCase):
 def setUp(self):
  self.old=json.loads((P/'cpu-real-gates.json').read_text())['build']['compiled_sources_sha256'];self.now=compiled_sources()
 def test_current(self):self.assertEqual(len(verify_sources(self.old,self.now)),5)
 def test_snapshot_tamper(self):
  k=next(n for n in self.now if n.endswith('/strict_snapshot.hpp'));self.now[k]='0'*64
  with self.assertRaisesRegex(AssertionError,'outside fixture'):verify_sources(self.old,self.now)
 def test_p39_plan_tamper(self):
  k=next(n for n in self.now if n.endswith('/p39_plan.hpp'));self.now[k]='0'*64
  with self.assertRaisesRegex(AssertionError,'outside fixture'):verify_sources(self.old,self.now)
 def test_decode_change(self):
  k=next(n for n in self.now if n.endswith('/main.cpp'));self.now[k]='0'*64
  with self.assertRaisesRegex(AssertionError,'outside fixture'):verify_sources(self.old,self.now)
 def test_owner_change(self):
  k=next(n for n in self.now if n.endswith('/owner.cpp'));self.now[k]='0'*64
  with self.assertRaisesRegex(AssertionError,'outside fixture'):verify_sources(self.old,self.now)
 def test_fixture_transplant(self):
  k=next(n for n in self.now if n.endswith('/p39_fixture.cpp'));self.now[k]='0'*64
  with self.assertRaisesRegex(AssertionError,'outside fixture'):verify_sources(self.old,self.now)
 def test_abi_change(self):
  k=next(n for n in self.now if n.endswith('/owner_api.hpp'));self.now[k]='0'*64
  with self.assertRaisesRegex(AssertionError,'outside fixture'):verify_sources(self.old,self.now)
 def test_missing_source(self):
  self.now.pop(next(iter(self.now)))
  with self.assertRaisesRegex(AssertionError,'closure'):verify_sources(self.old,self.now)
 def test_added_source(self):
  self.now['unregistered.cpp']='0'*64
  with self.assertRaisesRegex(AssertionError,'closure'):verify_sources(self.old,self.now)
if __name__=='__main__':unittest.main()
