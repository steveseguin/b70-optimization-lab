import copy,json,sys,unittest
from pathlib import Path
from chain_adapter import P,O,ROOT
sys.path.insert(0,str(P))
import storage,bundle_selection
from stream_gate155 import check
from launch_identity import verify,UNIT
from confirm136 import LIBRARIES
class Policy(unittest.TestCase):
 def test_only_static_delta(self):
  old=json.loads((P.with_name('packet136-record-bundle')/'selection.json').read_text())
  new=json.loads((P/'selection.json').read_text());new['choices'].pop('snapshot_host');new['choices'].pop('probe')
  self.assertEqual(old,new);self.assertEqual(bundle_selection.selected()['snapshot_host'],'static')
 def test_bound_native(self):
  from reuse_build import verify_native
  verify_native()
 def test_storage_measurement(self):
  rows=json.loads((P/'storage-measurements.json').read_text())['windows']
  self.assertEqual(set(rows),set(storage.CHAIN_WINDOWS))
  for name,r in rows.items():
   self.assertLessEqual(storage.chain_window_bytes(name),3*r['measured_generated_upper_bound_bytes'])
   self.assertGreaterEqual(storage.chain_window_bytes(name),r['measured_generated_upper_bound_bytes'])
  self.assertEqual(storage.FREE_FLOOR,25_000_000_000)
 def test_storage_boundary(self):
  extra=300_000_000
  self.assertEqual(storage.budget(25_500_000_000+extra,100_000_000,extra,extra)['free_floor_bytes'],25_000_000_000)
  with self.assertRaises(RuntimeError):storage.budget(25_000_000_000+extra-1,100_000_000,extra,extra)
 def test_record_floor(self):
  sys.path.insert(0,str(O));from submission_evidence import require_new_record
  for r in (58.798109,58.79,float('nan'),float('inf')):
   with self.assertRaises(ValueError):require_new_record(r)
  require_new_record(58.798110)
 def test_unit(self):
  env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2',LD_LIBRARY_PATH=LIBRARIES)
  row=verify('0::/user.slice/user@1000.service/app.slice/'+UNIT,env);self.assertEqual(row['lane'],'A')
  with self.assertRaises(AssertionError):verify('0::/user@1000.service/packet136-chain-a.service',env)
  with self.assertRaises(AssertionError):verify('0::/user@1000.service/'+UNIT,dict(env,EXTRA='1'))
 def request(self):return dict(passed=True,oracle_check=dict(passed=True),tokens=[1,2],token_timestamps=[90000.,90001.],rank_trace=[dict(rank=0,op=1),dict(rank=1,op=1)],cached_tokens=0,arithmetic='iq3-p49-split32-v1')
 def test_no_wall_clock_proof_limit(self):
  r=self.request();r['token_timestamps']=[1.,1000000.];self.assertTrue(check(r)['passed'])
 def test_missing_stream(self):
  r=self.request();r['rank_trace']=[]
  with self.assertRaises(ValueError):check(r)
 def test_bad_clock(self):
  r=self.request();r['token_timestamps']=[1.,1.]
  with self.assertRaises(ValueError):check(r)
 def test_exactness_failure(self):
  r=self.request();r['oracle_check']['passed']=False
  with self.assertRaises(ValueError):check(r)
if __name__=='__main__':unittest.main()
