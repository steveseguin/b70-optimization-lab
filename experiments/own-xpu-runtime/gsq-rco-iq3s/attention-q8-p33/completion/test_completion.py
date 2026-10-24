import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
O=load(P/'once.py','completion_test_once');S=O.S;V=S.V;C=S.C
T=load(O.L/'baseline/test_suite.py','completion_frozen_fixtures')
class Completion(unittest.TestCase):
 def refs(self):
  return {f'prompt-{i:02d}-{mode}':dict(mode=mode,prompt_tokens=p['tokens'],result={'tokens':[2]*128},state_sha256={'0':{'state':'exact'},'1':{'state':'exact'}}) for i,p in enumerate(S.manifest()['prompts']) for mode in p['order']}
 def invoke(self,t,reset,controller,state):
  plan=dict(lifetime_seconds=7200,manifest_sha256=S.sha(S.MANIFEST),adapter={'binary_sha256':V.BINARY_SHA},completion_manifest_sha256=S.sha(P/'manifest.json'),verified_prefix_sha256=V.PRIOR_SHA)
  with patch.object(S.A,'reset',reset),patch.object(S.A.BASE,'NativeController',controller),patch.object(S.A,'state_hashes',state),patch.object(S,'storage_guard'),patch.object(C,'bind_references'),patch.object(C,'REFERENCES',self.refs()):return S.run_attached(t,plan)
 def test_only_missing_five_and_resets(self):
  with tempfile.TemporaryDirectory() as tmp:
   args=T.SuiteTests().fixture(tmp);out=self.invoke(*args);self.assertTrue(out['passed']);self.assertEqual(12,len(args[0].calls));self.assertEqual(12,len(args[0].resets));self.assertEqual(5,len(out['prompts']));self.assertEqual(10,out['measured_requests'])
   names=[a['name'] for p in out['prompts'] for a in p['arms']];expected=[f'prompt-{i:02d}-{mode}' for i in range(7,12) for mode in (['none','mtp'] if i%2==0 else ['mtp','none'])];self.assertEqual(expected,names)
   self.assertEqual(10,len(list(Path(tmp).glob('prompt-*/baseline-exact.json'))));self.assertFalse((Path(tmp)/'prompt-00-none').exists())
 def test_first_missing_mismatch_stops_before_second_arm(self):
  with tempfile.TemporaryDirectory() as tmp:
   t,reset,controller,state=T.SuiteTests().fixture(tmp)
   with self.assertRaisesRegex(ValueError,'baseline'):self.invoke(t,reset,controller,lambda _:{'wrong':'state'})
   self.assertEqual(3,len(t.calls));self.assertEqual('mtp',t.calls[-1][0]);self.assertFalse((Path(tmp)/'prompt-07-none').exists())
 def test_prefix_and_source_authority(self):
  r=V.prerequisites(V.BINARY_SHA);self.assertEqual(14,r['verified_prior_arms'])
  with self.assertRaisesRegex(ValueError,'binary'):V.prerequisites('0'*64)
 def test_storage_forecast(self):
  m=json.loads((P/'manifest.json').read_text());self.assertEqual(3075861364,13*S.PER_REQUEST+64*1024**2);self.assertEqual(13*2113,m['forecast_bin_files']);self.assertLess(m['forecast_bin_files']+m['metadata_file_allowance'],57045);self.assertEqual(12,S.CAP)
 def test_exact_exception_class_and_units(self):
  self.assertIs(O.O.O.S,S);self.assertIs(O.O.O.S.A.RetainedOwner,S.A.RetainedOwner)
  for module in (O.O,O.O.O,O.M):self.assertEqual(O.CONTROL,module.CONTROL);self.assertEqual(O.EVIDENCE,module.EVIDENCE);self.assertEqual(O.UNIT,module.UNIT)
if __name__=='__main__':unittest.main(verbosity=2)
