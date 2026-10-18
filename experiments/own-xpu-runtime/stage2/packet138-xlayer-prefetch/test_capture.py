"""CPU tests; fixture bytes never qualify as measured capture."""
import hashlib,json,resource,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import capture_inputs as C
import capture_worker as W
import run_capture as R
import capture_identity as I
from input_gate import validate_manifest

def fixture():
 row=b''.join(struct.pack('<III',i,0,2560) for i in range(10))+bytes(C.STRIDE-120)
 raw=row*(48*24);prompt=[3,7];out=list(range(100,148))
 meta=dict(schema='packet138.rank-capture.v1',diagnostic_only=True,rank=0,bytes=len(raw),stride=C.STRIDE,sha256=hashlib.sha256(raw).hexdigest(),steps=[dict(fixture=i+1,position=len(prompt)-1+i,input_token=prompt[-1] if not i else out[i-1]) for i in range(48)])
 return raw,meta,prompt,out
class Capture(unittest.TestCase):
 def test_valid(self):
  a,b,c,d=fixture();self.assertEqual(C.validate_rank(a,b,0,c,d),1152)
 def test_corruption(self):
  a,b,c,d=fixture()
  for data in (a[:-1],b'!'+a[1:]):
   with self.assertRaises(ValueError):C.validate_rank(data,b,0,c,d)
 def test_identity(self):
  a,b,c,d=fixture()
  with self.assertRaises(ValueError):C.validate_rank(a,b,1,c,d)
  b['steps'][12]['input_token']+=1
  with self.assertRaises(ValueError):C.validate_rank(a,b,0,c,d)
 def test_duplicate_route(self):
  a,b,c,d=fixture();a=a[:12]+a[:12]+a[24:];b['sha256']=hashlib.sha256(a).hexdigest()
  with self.assertRaises(ValueError):C.validate_rank(a,b,0,c,d)
 def test_missing_is_not_failure_verdict(self):
  with patch.object(C,'MANIFEST',Path('/definitely-missing-p138')):
   with self.assertRaisesRegex(ValueError,'pending'):C.require_ready()
 def test_inputs(self):
  r=validate_manifest(json.loads((I.P/'suite.snapshot.json').read_text()))
  self.assertEqual(len(r['prompts']),13)
  self.assertEqual(len({e['category'] for e in r['prompts'][1:]}),6)
 def test_memory(self):
  _,r=I.memory();self.assertEqual([x['target_layers'] for x in r['ranks']],[24,24])
 def test_watchdog(self):self.assertGreaterEqual(R.WATCHDOG['tp2'],4*R.EXPECTED_SECONDS[-1])
 def test_unit(self):
  R.unit_gate('0::/user.slice/user-1000.slice/user@1000.service/app.slice/screen-packet138-capture-B.service')
  with self.assertRaises(ValueError):R.unit_gate('0::/app.slice/arbitrary.service')
 def test_no_host_reads_in_loop(self):
  t=(I.P/'route_capture.hpp').read_text().split('void capture_flush')[0]
  for s in ('readback(','.wait(','upload('):self.assertNotIn(s,t)
 def test_drain_after_cancel(self):
  events=[]
  class T:
   def __init__(self,*a,**kw):pass
   def __enter__(self):events.append('permit');return self
   def __exit__(self,*a):events.append('release')
  class Transport:
   check=lambda self: (_ for _ in ()).throw(ValueError('cancelled'))
   def stop(self,*a):events.append('stop')
   def close(self,success):self.check();events.append('close')
  with patch.object(W,'Teardown',T):W.drain(Transport(),Path('/unused'),False,'cancelled')
  self.assertEqual(events,['permit','stop','close','release'])
 def test_drain_finish_interrupt(self):
  events=[]
  class T:
   def __init__(self,*a,**kw):pass
   def __enter__(self):events.append('permit');return self
   def __exit__(self,*a):events.append('release')
  class Transport:
   check=lambda self:None
   def stop(self,*a):events.append('stop')
   def close(self,success):
    if success:raise ValueError('stop during finish')
    self.check();events.append('close')
  with patch.object(W,'Teardown',T):
   with self.assertRaisesRegex(ValueError,'finish'):W.drain(Transport(),Path('/unused'),True)
  self.assertEqual(events,['permit','stop','close','release'])
if __name__=='__main__':unittest.main()
