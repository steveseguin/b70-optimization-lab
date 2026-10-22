import copy,json,sys,unittest
from pathlib import Path
from chain_adapter import P,O,ROOT
sys.path.insert(0,str(P))
import storage,bundle_selection
from stream_gate187 import check
from launch_identity import verify,UNIT
from confirm136 import LIBRARIES
class Policy(unittest.TestCase):
 def test_only_v3_and_static_delta(self):
  # packet187 = bundle 8 + packet153 static + packet186 V3: the only choice changes against packet136's record
  # selection are probe/snapshot_host/dense_scales (v5 keys), rank0_layers/boundary (V3) and the un-split head.
  old=json.loads((P.with_name('packet136-record-bundle')/'selection.json').read_text())
  new=json.loads((P/'selection.json').read_text())
  extra={k:new['choices'].pop(k) for k in ('snapshot_host','probe','dense_scales','rank0_layers','boundary')}
  self.assertEqual(extra,dict(snapshot_host='static',probe='off',dense_scales='expanded',rank0_layers='0-25',boundary='rank0'))
  self.assertEqual((old['choices'].pop('head'),new['choices'].pop('head')),('head-split-compute','production'))
  self.assertEqual(old,new);row=bundle_selection.selected();self.assertEqual((row['snapshot_host'],row['target_head'],row['v3']['boundary']),('static','production','rank0'))
  v3=P.with_name('packet186-twocard-v3')/'v5/lineage/v3'
  for leaf in ('selection.json','memory-plan.json','dispatch-speed6.json'):self.assertEqual((P/leaf).read_bytes(),(v3/leaf).read_bytes())
 def test_chain_transport_matches_engine_shared_extent(self):
  # packet155-chain-a stopped in W0p with `shared extent`: the chain created 3*SLOT+4096 bytes, v5 maps more.
  import re,chain_pipeline,pipeline
  text=(P/'v3-native/native-src/rank.hpp').read_text()
  line=next(l for l in text.splitlines() if 'constexpr size_t slot_bytes=' in l)
  env={};exec(line.replace('constexpr size_t ','').replace(', ',';').rstrip(';')+';',{},env)
  self.assertEqual(env['shared_bytes'],266304);self.assertEqual(chain_pipeline.SHARED,env['shared_bytes']);self.assertEqual(pipeline.SHARED,env['shared_bytes'])
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
