"""Tiny filesystem/guard tests; never imports or invokes an operating runner."""
import ast,hashlib,importlib.util,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('iq4_ack_test',P/'handshake.py');H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)
class Startup(unittest.TestCase):
 def data(self,d,nonce='a'*32):
  message=f'GSQ_NATIVE_BACKEND_READY_V1 12 34 {nonce}\n'.encode();(d/'backend-ready.txt').write_bytes(message)
  holders=[dict(pid=12,node='renderD130')];snap=dict(holders={'12':dict(start_ticks=34)})
  return message,holders,snap
 def test_positive_bound_ack_and_durable_sample(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);message,holders,snap=self.data(d)
   self.assertTrue(H.publish_ack(d,(12,34),holders,{'renderD130'},snap,{'MainPID':'12'}))
   self.assertEqual((d/'backend-ack.txt').read_bytes(),message)
   r=json.loads((d/'backend-contact.json').read_text());self.assertEqual(r['ready_sha256'],hashlib.sha256(message).hexdigest());self.assertEqual(r['snapshot'],snap)
   self.assertFalse((d/'backend-ack.partial').exists())
 def test_missing_ready_waits_without_ack(self):
  with tempfile.TemporaryDirectory() as tmp:self.assertFalse(H.publish_ack(Path(tmp),(12,34),[],set(),{},{}))
 def test_absent_or_wrong_physical_contact_refused(self):
  for mode in ('none','other_node','other_pid','other_start'):
   with tempfile.TemporaryDirectory() as tmp:
    d=Path(tmp);_,h,s=self.data(d)
    if mode=='none':h=[]
    elif mode=='other_node':h[0]['node']='renderD129'
    elif mode=='other_pid':h[0]['pid']=99;s['holders']['99']=dict(start_ticks=34)
    else:s['holders']['12']['start_ticks']=35
    with self.assertRaises(AssertionError):H.publish_ack(d,(12,34),h,{'renderD130'},s,{})
    self.assertFalse((d/'backend-ack.txt').exists())
 def test_wrong_pid_and_malformed_challenge_refused(self):
  for identity,nonce in [((13,34),'a'*32),((12,35),'a'*32),((12,34),'g'*32),((12,34),'a'*31)]:
   with tempfile.TemporaryDirectory() as tmp:
    d=Path(tmp);_,h,s=self.data(d,nonce)
    with self.assertRaises(AssertionError):H.publish_ack(d,identity,h,{'renderD130'},s,{})
    self.assertFalse((d/'backend-ack.txt').exists())
 def test_stale_ack_preserved_no_overwrite(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);_,h,s=self.data(d);(d/'backend-ack.txt').write_bytes(b'old challenge')
   with self.assertRaises(AssertionError):H.publish_ack(d,(12,34),h,{'renderD130'},s,{})
   self.assertEqual((d/'backend-ack.txt').read_bytes(),b'old challenge')
 def test_sample_write_failure_does_not_grant_ack(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);_,h,s=self.data(d)
   with patch.object(H.json,'dump',side_effect=OSError('evidence failure')):
    with self.assertRaises(OSError):H.publish_ack(d,(12,34),h,{'renderD130'},s,{})
   self.assertFalse((d/'backend-ack.txt').exists())
 def test_native_order_lifetime_and_timeout_cleanup_source(self):
  s=(P/'runner.cpp').read_text();create=s.index('auto owner=make_sycl_device(card,true)');owned=s.index('d=std::make_unique<Device>(std::move(owner))');ack=s.index('await_backend_ack(out)');alloc=s.index('Harness h(*d',ack);setup=s.index('h.setup(',alloc);timed=s.index('h.timed(',setup)
  self.assertTrue(create<owned<ack<alloc<setup<timed)
  self.assertIn('backend=owner.get()',s[create:owned]);self.assertIn('try{backend->synchronize();}catch',s);self.assertIn('report();hold_for_supervisor();',s)
  h=(P/'startup.hpp').read_text();self.assertIn('guard();need(std::chrono::steady_clock::now()<until',h);self.assertIn('std::chrono::seconds(60)',h);self.assertIn('got==message',h);self.assertIn('same(st,pathstat)',h)
  self.assertNotIn('/dev/dri',h);self.assertNotIn('make_sycl_device',h)
 def test_coordinator_guard_order_and_required_terminal_ack(self):
  s=(P/'once.py').read_text();ast.parse(s)
  guard='if first_error is None and observation_complete and native_holders and not backend_acknowledged:'
  self.assertIn(guard,s);self.assertLess(s.index("(STAGE/'monitor.json').write_text"),s.index('ACK.publish_ack('))
  self.assertIn('observed_native_target_fd and backend_acknowledged and exact_result(result)',s)
  self.assertIn('STAGE.parent.stat().st_dev==R.stat().st_dev',s)
if __name__=='__main__':unittest.main(verbosity=2)
