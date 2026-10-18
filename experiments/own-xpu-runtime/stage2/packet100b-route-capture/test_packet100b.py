"""CPU-only rejection and orchestration tests; fixtures never qualify a route run."""
import ast,copy,hashlib,json,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import capture_inputs as capture
import capture_identity as identity
import qualification
import run_capture

def fixture():
 prompt=[1,2,3];outputs=list(range(100,164));raw=bytearray()
 for step in range(64):
  for layer in range(24):
   for slot in range(10):raw.extend(struct.pack('<III',(17*step+13*layer+slot)%512,0,2560))
 meta=dict(schema='packet100b.rank-routes.v1',diagnostic_only=True,rank=0,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
  steps=[dict(fixture=i+1,position=len(prompt)-1+i,input_token=prompt[-1] if i==0 else outputs[i-1]) for i in range(64)])
 return bytes(raw),meta,prompt,outputs

def timings(ratio=.8):
 rows=[]
 for route in range(2):
  for name in ('down-interleave','down-tile16'):
   rows.append(dict(kind='correctness',view=name,route=route,fp32_exact=True,bf16_exact=True,status_exact=True,rows=2560,columns=640,count=10,experts=512))
   for rep in range(40):
    for pos in range(2):
     view=name if pos^(rep&1) else 'production'
     rows.append(dict(kind='sample',pair=name,view=view,route=route,repeat=rep,position=pos,event_ns=1000 if view=='production' else 1000*ratio,rows=2560,columns=640,count=10,experts=512,wg=64,sg=32,scrub_bytes=536870912,diagnostic_only=True))
 rows.append(dict(kind='summary',passed=True,drained=True,diagnostic_only=True,rows=2560,columns=640,count=10,experts=512,route_count=2))
 return rows

class CaptureTests(unittest.TestCase):
 def test_complete(self):
  rows=capture.validate_rank(*fixture()[:2],0,*fixture()[2:])
  self.assertEqual(len(rows),1536);self.assertEqual(rows[-1]['offset'],184200)
 def test_truncation(self):
  raw,meta,prompt,out=fixture()
  with self.assertRaises(ValueError):capture.validate_rank(raw[:-1],meta,0,prompt,out)
 def test_changed_bytes(self):
  raw,meta,prompt,out=fixture()
  with self.assertRaises(ValueError):capture.validate_rank(bytes([raw[0]^1])+raw[1:],meta,0,prompt,out)
 def test_wrong_rank(self):
  raw,meta,prompt,out=fixture()
  with self.assertRaises(ValueError):capture.validate_rank(raw,meta,1,prompt,out)
 def test_wrong_accepted_token(self):
  raw,meta,prompt,out=fixture();meta['steps'][20]['input_token']+=1
  with self.assertRaises(ValueError):capture.validate_rank(raw,meta,0,prompt,out)
 def test_missing_step(self):
  raw,meta,prompt,out=fixture();meta['steps'].pop()
  with self.assertRaises(ValueError):capture.validate_rank(raw,meta,0,prompt,out)
 def test_invalid_expert(self):
  raw,meta,prompt,out=fixture();raw=struct.pack('<I',512)+raw[4:];meta['sha256']=hashlib.sha256(raw).hexdigest()
  with self.assertRaises(ValueError):capture.validate_rank(raw,meta,0,prompt,out)
 def test_wrong_down_shape(self):
  raw,meta,prompt,out=fixture();raw=raw[:8]+struct.pack('<I',1280)+raw[12:];meta['sha256']=hashlib.sha256(raw).hexdigest()
  with self.assertRaises(ValueError):capture.validate_rank(raw,meta,0,prompt,out)
 def test_duplicate_expert(self):
  raw,meta,prompt,out=fixture();raw=raw[:12]+raw[:12]+raw[24:];meta['sha256']=hashlib.sha256(raw).hexdigest()
  with self.assertRaises(ValueError):capture.validate_rank(raw,meta,0,prompt,out)
 def test_pending_capture_refuses(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(capture,'MANIFEST',Path(tmp)/'missing'):
   with self.assertRaisesRegex(ValueError,'pending'):capture.require_ready()
 def test_pending_qualification_refuses(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(qualification,'MICRO',Path(tmp)):
   with self.assertRaisesRegex(ValueError,'pending'):qualification.require_qualified()
 def test_micro_unchanged_15_percent(self):
  self.assertEqual(len(qualification.analyzer()(timings(.85),2)['qualified']),2)
  self.assertEqual(qualification.analyzer()(timings(.851),2)['qualified'],[])
 def test_micro_wrong_order(self):
  rows=timings();rows[1]['position']=1
  with self.assertRaises(ValueError):qualification.analyzer()(rows,2)
 def test_micro_one_bad_stratum(self):
  rows=timings()
  for row in rows:
   if row.get('kind')=='sample' and row['route']==1 and row['view']=='down-interleave':row['event_ns']=900
  self.assertEqual(qualification.analyzer()(rows,2)['qualified'],['down-tile16'])
 def test_micro_one_bad_order(self):
  rows=timings()
  for row in rows:
   if row.get('kind')=='sample' and row['repeat']%2 and row['view']=='down-interleave':row['event_ns']=900
  self.assertEqual(qualification.analyzer()(rows,2)['qualified'],['down-tile16'])
 def test_micro_missing_timing(self):
  rows=timings();rows.pop(1)
  with self.assertRaises(ValueError):qualification.analyzer()(rows,2)
 def test_micro_inexact(self):
  rows=timings();rows[0]['fp32_exact']=False
  with self.assertRaises(ValueError):qualification.analyzer()(rows,2)
 def test_memory_unchanged_caps(self):
  gate,config=identity.memory()
  self.assertEqual([r['target_layers'] for r in config['ranks']],[24,24])
  ledger=json.loads((identity.P/'memory-plan.json').read_text());ledger['arena_limit_bytes']+=1
  with self.assertRaises(ValueError):gate.configuration(ledger,4096,1,0)
 def test_memory_before_lease(self):
  events=[]
  class RefuseLease:
   def __init__(self,*args,**kwargs):events.append('lease');raise RuntimeError('end test')
  with patch.object(run_capture,'lane_gate'),patch.object(run_capture,'sealed'),patch.object(run_capture,'storage_budget'),patch.object(run_capture.fault_review,'validate'),patch.object(run_capture.S,'journal',return_value=('',0)),patch.object(run_capture,'memory_admit',side_effect=lambda _:events.append('memory')),patch.object(run_capture,'Reservation',RefuseLease),patch('cpu_seal.verify'):
   with self.assertRaisesRegex(RuntimeError,'end test'):run_capture.main(['--run','--authorized-device-window','--fault-review','unused'])
  self.assertEqual(events,['memory','lease'])
 def test_memory_failure_prevents_lease(self):
  with patch.object(run_capture,'lane_gate'),patch.object(run_capture,'sealed'),patch.object(run_capture,'storage_budget'),patch.object(run_capture.fault_review,'validate'),patch.object(run_capture.S,'journal',return_value=('',0)),patch.object(run_capture,'memory_admit',side_effect=ValueError('memory')),patch.object(run_capture,'Reservation') as lease,patch('cpu_seal.verify'):
   with self.assertRaisesRegex(ValueError,'memory'):run_capture.main(['--run','--authorized-device-window','--fault-review','unused'])
   lease.assert_not_called()
 def test_plan_takes_precedence(self):
  with patch.object(run_capture,'screen_main',return_value=0) as plan,patch.object(run_capture,'lane_gate') as lane:
   self.assertEqual(run_capture.main(['--plan','--run']),0);plan.assert_called_once();lane.assert_not_called()
 def test_grid_adapter_keeps_frozen_driver(self):
  text=(identity.P/'run_grid.py').read_text()
  self.assertIn("BASE/'run_screens.py'",text);self.assertIn('jobs.qualified_candidates=lambda:require_qualified(P)',text)
 def test_header_has_only_boundary_read(self):
  text=(identity.P/'route_capture.hpp').read_text();hot=text[:text.index('void capture_flush')]
  self.assertNotIn('readback(',hot);self.assertNotIn('wait(',hot);self.assertNotIn('upload(',hot)

if __name__=='__main__':unittest.main()
