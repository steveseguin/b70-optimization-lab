"""Actual isolated Provider socket codec; synthetic responder, no native engine."""
import importlib.util,json,socket,struct,sys,threading,unittest
from pathlib import Path
from types import SimpleNamespace
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'engine/planning'));sys.path.insert(0,str(ROOT/'engine/tools'))
s=importlib.util.spec_from_file_location('rolling_provider.reset_overlay',HERE/'overlay/planning/rolling_provider/dedicated_transport.py');M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
class Tests(unittest.TestCase):
 def case(self,bad=False):
  left,right=socket.socketpair();shared=bytearray(4*65536+4096+64);old=bytes.fromhex('a'*64);new=bytes.fromhex('b'*64)
  shared[:128]=M.HEADER.pack(M.MAGIC,M.VERSION,128,0,16,2,2,0,0,old,bytes(56))
  plan=dict(stages=[{},{}],speculative_depth=2,seconds=1,dedicated_reset_protocol='ownrt.dedicated-reset-request.v2')
  owner=SimpleNamespace(sock=left,shared=shared,guard=SimpleNamespace(check=lambda:None),plan=plan,sequence=7)
  provider=M.Provider(owner);provider.stream_bytes=16;provider.provider_serial=123
  d=dict(schema='ownrt.dedicated-reset-request.v2',role='provider',owner_index=0,global_sequence=8,previous_epoch=0,next_epoch=1,previous_request_sha256=old.hex(),next_request_sha256=new.hex(),oracle='')
  errors=[]
  def worker():
   try:
    raw=b''
    while len(raw)<32:raw+=right.recv(32-len(raw))
    self.assertEqual(M.base.REQUEST.unpack(raw),(11,0,0,0,0,8,M.MAGIC,M.VERSION))
    self.assertEqual(struct.unpack('<4IQ32s8s',shared[512:576]),(M.MAGIC,M.VERSION,64,8,1,new,bytes(8)))
    shared[:]=bytes(len(shared));shared[:128]=M.HEADER.pack(M.MAGIC,M.VERSION,128,0,16,2,2,0,1,new,bytes(56))
    reply=M.base.REPLY.pack(0,-1,0,0,9 if bad else 8,-1,M.MAGIC,M.VERSION,0.,0.,0.,0.)
    right.sendall(reply[:5]);right.sendall(reply[5:])
   except BaseException as e:errors.append(e)
  thread=threading.Thread(target=worker);thread.start()
  try:
   if bad:
    with self.assertRaises(Exception):provider.reset_request(d)
    self.assertTrue(plan['dedicated_reset_poisoned'])
   else:
    provider.reset_request(d);self.assertEqual(provider.sequence,8);self.assertEqual(owner.sequence,8);self.assertEqual(provider.provider_serial,0);self.assertFalse(any(shared[128:]))
  finally:thread.join(2);left.close();right.close()
  self.assertFalse(thread.is_alive());self.assertFalse(errors,errors)
 def test_actual_wire_and_header(self):self.case()
 def test_bad_reply_poison(self):self.case(True)
 def test_default_control_does_not_admit_reset(self):
  owner=SimpleNamespace(sock=None,shared=bytearray(4*65536+4096+64),guard=None,plan={},sequence=0);p=M.Provider(owner)
  with self.assertRaises(Exception):p.control(11)
if __name__=='__main__':unittest.main()
