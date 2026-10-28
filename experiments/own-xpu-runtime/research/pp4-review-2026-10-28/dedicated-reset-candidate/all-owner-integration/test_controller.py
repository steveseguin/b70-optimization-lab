"""Bounded actual-reader/controller boundary tests; no native Engine/model/GPU."""
import hashlib,importlib.util,json,struct,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
HERE=Path(__file__).resolve().parent
ENGINE=next(p/'engine' for p in HERE.parents if (p/'engine/tools/pipeline_driver.py').exists())
sys.path[:0]=[str(HERE/'overlay/tools'),str(ENGINE/'tools'),str(ENGINE/'planning')]
import dedicated_reset_suite as M
import reset_all as R
from rolling_provider.dedicated_transport import HEADER,MAGIC,VERSION

def write_bundle(path,n,offset=0,bad=False,alternate=False,bad_alternate=False):
 path.mkdir();parts=[];rows=[];buffers={};start=0
 for i in range(n+int(alternate)):
  name='alternate-x'+str(offset)if i==n else f'x{i+offset}';raw=struct.pack('<I',1 if (bad and i==0)or(bad_alternate and i==n)else 0);h=hashlib.sha256(raw).hexdigest();parts.append(raw);rows.append(f'{name}.bin\t{start}\t4\t{h}\n');buffers[name]=h;start+=4
 payload=b''.join(parts);index=('GSQ_STATE_BUNDLE_V1\n'+''.join(rows)).encode();state=json.dumps(dict(buffers=buffers,history0=0,history1=0)).encode()
 for name,data in [('state.bundle',payload),('state-index.tsv',index),('state.json',state)]: (path/name).write_bytes(data)
 (path/'state-seal.txt').write_text('GSQ_STATE_SEAL_V1\n'+str(len(payload))+'\n'+'\n'.join(hashlib.sha256(x).hexdigest()for x in (payload,index,state))+'\n')

class Tests(unittest.TestCase):
 def test_cold_full_bytes_mapping_and_mutation(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);plan=dict(context=4096);guard=SimpleNamespace(check=lambda:None)
   stages=[]
   for i,n in enumerate((1000,1065)):
    out=root/f't{i}';out.mkdir();s=SimpleNamespace(spec=dict(id=i,native_output=str(out)),pending_rows=(),physical=0,committed=0,command_pending=None,transmit=b'',received=b'')
    def command(op,position,s=s,n=n,i=i):
     write_bundle(Path(s.dedicated_native_output if hasattr(s,'dedicated_native_output')else s.spec['native_output'])/f'state-{position}',n,0 if i==0 else 1000,getattr(s,'bad',False),alternate=True,bad_alternate=getattr(s,'bad_alternate',False))
     native=Path(getattr(s,'dedicated_native_output',s.spec['native_output']));name='x'+str(0 if i==0 else 1000)
     (native/'pipeline-stage.json').write_text(json.dumps(dict(inactive_alternate_banks=[name])))
     (native/'launch-plan.json').write_text(json.dumps(dict(buffers=[dict(name=name,bytes=4)])))
     (Path(getattr(s,'dedicated_native_output',s.spec['native_output']))/'request-state-inventory.json').write_text(json.dumps(dict(launch_extent=32,alternate_launch_extent=32,poisoned=False)))
    s.command=command;stages.append(s)
   out=root/'provider';out.mkdir();provider=SimpleNamespace(owner=SimpleNamespace(spec=dict(native_output=str(out))),sequence=0)
   def control(op):
    provider.sequence+=1;write_bundle(Path(getattr(provider,'dedicated_native_output',str(out)))/f'provider-dump-{provider.sequence}',73)
   provider.control=control
   cold=M.Cold(plan,guard)
   # Existing quiescence helper validates transport buffers; isolate only its
   # frontier prerequisite here, while all sealed reader work is real.
   old=R.target_reset.quiescent;R.target_reset.quiescent=lambda s:None
   try:
    proof=cold(stages,provider,root);self.assertEqual(proof['target_canonical_sources'],2065);self.assertEqual(proof['inactive_bank_sources'],2)
    for s in stages:s.dedicated_native_output=str(root/f'next{s.spec["id"]}');Path(s.dedicated_native_output).mkdir()
    provider.dedicated_native_output=str(root/'nextp');Path(provider.dedicated_native_output).mkdir()
    second=root/'second';second.mkdir();proof=cold(stages,provider,second)
    self.assertEqual(proof['full_payload_bytes_compared'],4*(2065+73+2));self.assertFalse((Path(stages[0].dedicated_native_output)/f'state-{M.SENTINEL}'/'state.bundle').exists())
    for s in stages:s.dedicated_native_output=str(root/f'bad{s.spec["id"]}');Path(s.dedicated_native_output).mkdir()
    stages[0].bad_alternate=True;provider.dedicated_native_output=str(root/'badp');Path(provider.dedicated_native_output).mkdir()
    bad=root/'badproof';bad.mkdir()
    with self.assertRaisesRegex(ValueError,'source mapping'):cold(stages,provider,bad)
   finally:R.target_reset.quiescent=old
 def test_real_transition_all_ack_cold_then_first_op15(self):
  for fail_cold in (True,False):
   with tempfile.TemporaryDirectory()as td:
    root=Path(td);out=root/'controller';out.mkdir();native=root/'provider';native.mkdir();target=root/'target';target.mkdir()
    plan=dict(dedicated_reset_protocol=R.PROTOCOL,context=4096,prefill_rows=256,dedicated_prefill_slots=4,stages=[{}],speculative_depth=3)
    extent,header=M.base.prefill_layout(256,16,4);events=[]
    stage=SimpleNamespace(spec=dict(id=0),shared=bytearray(32),prefill=bytearray(extent),stream_bytes=16,start_async=lambda:events.append('target-rebound'),sock=SimpleNamespace(settimeout=lambda x:None))
    provider=SimpleNamespace(owner=SimpleNamespace(spec=dict(native_output=str(native))),sequence=3,command_pending=None,transmit=b'',received=b'',plan=plan,start_async=lambda:events.append('provider-rebound'),sock=SimpleNamespace(settimeout=lambda x:None))
    selected=dict(suite_sha256='a'*64,prompt_sha256='c'*64,prompt_index=1,prompt_tokens=3)
    def target_reset(*a,**kw):events.append('target-ack');return [dict(native_output=str(target))]
    def provider_reset(d):
     events.append('provider-ack');dest=Path(d['destination']);dest.mkdir()
     raw=(native/'reset-4.json').read_bytes()
     value=dict(schema='ownrt.dedicated-provider-reset.v1',passed=True,global_sequence=4,next_epoch=1,next_request_sha256='b'*64,prompt_sha256='c'*64,suite_sha256='a'*64,prompt_index=1,metadata_sha256=hashlib.sha256(raw).hexdigest(),provider_serial=0,bulk_closed=False,bulk_used=False,allocation_inventory_before_sha256='d'*64,allocation_inventory_after_sha256='d'*64)
     (dest/'provider-reset.json').write_text(json.dumps(value))
    provider.reset_request=provider_reset
    def cold(*args):
     self.assertEqual(events,['target-ack','provider-ack']);self.assertFalse(any(stage.prefill));events.append('cold')
     if fail_cold:raise ValueError('cold mismatch')
     return dict(passed=True,target_canonical_sources=2065,provider_canonical_sources=73,full_payload_bytes_compared=100)
    old=(R.authority,R.target_reset.reset,R.target_reset.quiescent)
    R.authority=lambda *a:selected;R.target_reset.reset=target_reset;R.target_reset.quiescent=lambda *a:None
    try:
     call=lambda:R.transition([stage],provider,plan,None,out,previous_epoch=0,previous_request='e'*64,epoch=1,request='b'*64,prompt_index=1,cold_verify=cold)
     if fail_cold:
      with self.assertRaisesRegex(ValueError,'cold mismatch'):call()
      self.assertFalse(any(stage.prefill));self.assertTrue(plan['dedicated_reset_poisoned']);self.assertNotIn('target-rebound',events)
     else:
      call();self.assertEqual(bytes(stage.prefill[:len(header)]),header);self.assertFalse(any(stage.prefill[len(header):]))
      plan.update(persistent_requests=True,epoch=1,request_sha256='b'*64)
      provider.shared=bytearray(HEADER.pack(MAGIC,VERSION,128,0,16,1,3,0,1,bytes.fromhex('b'*64),bytes(56)));provider.stream_bytes=16
      M.admit_drive([stage],provider,plan,1);events.append('OP15')
      self.assertEqual(events,['target-ack','provider-ack','cold','target-rebound','provider-rebound','OP15'])
    finally:R.authority,R.target_reset.reset,R.target_reset.quiescent=old
 def test_twelve_context_loop_reuses_same_owners(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);payload=root/'state.bundle';payload.write_bytes(b'cold')
   rows=[dict(id=f'case{i}',prompt_tokens=[i,1,2],max_new=512)for i in range(12)]
   manifest={f'prompt_{i}_path':str(root/f'prompt{i}')for i in range(12)};mp=root/'manifest';mp.write_text(json.dumps(manifest))
   plan=dict(dedicated_reset_protocol=R.PROTOCOL,persistent_requests=True,dedicated_requests=rows,request_sha256='a'*64,prompt_tokens=rows[0]['prompt_tokens'],context=4096,vocab=97,dedicated_prompt_manifest=str(mp),dedicated_reset_payload_bounds={'0':4,'provider':4})
   stage=SimpleNamespace(spec=dict(id=0,native_output=str(root)))
   provider=SimpleNamespace(owner=SimpleNamespace(spec={}))
   old=(M.forecast,M.Cold,R.authority,R.transition);calls=[]
   def auth(p,i):return dict(suite_sha256='f'*64,prompt_tokens=3,prompt_sha256=hashlib.sha256(struct.pack('<3i',*rows[i]['prompt_tokens'])).hexdigest())
   class Cold:
    baseline=dict(state={'0':dict(path=str(root)), 'provider':dict(path=str(root))})
    def __init__(self,*a):pass
    def __call__(self,*a):return dict(passed=True)
   def transition(stages,p,process,guard,out,**kw):
    self.assertIs(stages[0],stage);self.assertIs(p,provider);calls.append(('reset',kw['epoch']))
    process['dedicated_reset_ready']=(kw['epoch'],kw['request'],auth(process,kw['prompt_index'])['prompt_sha256'])
   def drive(stages,p,request,guard,out,epoch):
    self.assertIs(stage.plan,p.plan);self.assertIs(p.owner.plan,request);self.assertIs(stages[0],stage)
    self.assertEqual(request.pop('dedicated_reset_ready'),(epoch,request['request_sha256'],auth(plan,epoch)['prompt_sha256']))
    self.assertEqual(request['dedicated_prefill_prompt'],manifest[f'prompt_{epoch}_path']);calls.append(('drive',epoch))
    return dict(actual_output_ids=[epoch])
   M.forecast=lambda p:None;M.Cold=Cold;R.authority=auth;R.transition=transition
   try:
    result=M.run([stage],provider,plan,SimpleNamespace(check=lambda:None),root,SimpleNamespace(drive=drive))
    self.assertEqual(result['requests'],12);self.assertEqual(calls,[('drive',0)]+[x for i in range(1,12)for x in [('reset',i),('drive',i)]])
   finally:M.forecast,M.Cold,R.authority,R.transition=old
 def test_repeated_a_provider_and_outputs(self):
  for fault in (None,'outputs','provider'):
   with tempfile.TemporaryDirectory()as td:
    root=Path(td);initial=root/'baseline';initial.mkdir();(initial/'state.bundle').write_bytes(b'cold')
    rows=[dict(id=f'case{i}',prompt_tokens=[i,1,2],max_new=512)for i in range(12)]
    mp=root/'manifest';mp.write_text(json.dumps({f'prompt_{i}_path':str(root/f'prompt{i}')for i in range(12)}))
    plan=dict(dedicated_reset_protocol=R.PROTOCOL,persistent_requests=True,dedicated_requests=rows,dedicated_request_indices=[0,1,0],request_sha256='a'*64,prompt_tokens=rows[0]['prompt_tokens'],context=4096,vocab=97,dedicated_prompt_manifest=str(mp),dedicated_reset_payload_bounds={'0':4,'provider':4})
    troot=root/'target';troot.mkdir();proot=root/'provider';proot.mkdir()
    stage=SimpleNamespace(spec=dict(id=0,native_output=str(troot)))
    provider=SimpleNamespace(owner=SimpleNamespace(spec=dict(native_output=str(proot))),sequence=0)
    def command(op,position):write_bundle(Path(getattr(stage,'dedicated_native_output',str(troot)))/f'state-{position}',1)
    stage.command=command
    def control(op):
     provider.sequence+=1
     write_bundle(Path(getattr(provider,'dedicated_native_output',str(proot)))/f'provider-dump-{provider.sequence}',73,bad=fault=='provider'and provider.plan['epoch']==2)
    provider.control=control
    old=(M.forecast,M.Cold,R.authority,R.transition)
    def auth(p,i):return dict(suite_sha256='f'*64,prompt_tokens=3,prompt_sha256=hashlib.sha256(struct.pack('<3i',*rows[i]['prompt_tokens'])).hexdigest())
    class Cold:
     baseline=dict(state={'0':dict(path=str(initial)),'provider':dict(path=str(initial))})
     def __init__(self,*a):pass
     def __call__(self,*a):return dict(passed=True)
    def transition(stages,p,process,guard,out,**kw):
     process['dedicated_reset_ready']=(kw['epoch'],kw['request'],auth(process,kw['prompt_index'])['prompt_sha256'])
     stage.dedicated_native_output=str(root/f'target{kw["epoch"]}');Path(stage.dedicated_native_output).mkdir()
     provider.dedicated_native_output=str(root/f'provider{kw["epoch"]}');Path(provider.dedicated_native_output).mkdir()
    def drive(stages,p,request,guard,out,epoch):request.pop('dedicated_reset_ready');return dict(output_ids=[10 if fault=='outputs'and epoch==2 else 9])
    M.forecast=lambda p:None;M.Cold=Cold;R.authority=auth;R.transition=transition
    try:
     call=lambda:M.run([stage],provider,plan,SimpleNamespace(check=lambda:None),root,SimpleNamespace(drive=drive))
     if fault:
      with self.assertRaisesRegex(ValueError,'output IDs'if fault=='outputs'else'source mapping'):call()
     else:
      self.assertEqual(call()['requests'],3);proof=json.loads((root/'request-02/repeated-a-proof.json').read_text());self.assertEqual(proof['bytes_compared_by_owner'],{'0':4,'provider':292});self.assertTrue(proof['actual_output_ids_equal'])
    finally:M.forecast,M.Cold,R.authority,R.transition=old
 def test_inventory_only_two_cache_fields(self):
  a=dict(launch_extent=32,alternate_launch_extent=32,history=0)
  M.inventory(a,dict(a,launch_extent=64),4096)
  with self.assertRaises(ValueError):M.inventory(a,dict(a,history=1),4096)
  with self.assertRaises(ValueError):M.inventory(a,dict(a,launch_extent=33),4096)
 def test_first_op15_requires_header_and_one_shot_barrier(self):
  # Calls the real drive admission function then a fake OP15 sink; no native
  # kernel claim. Missing header/partial reset readiness cannot reach sink.
  plan=dict(persistent_requests=True,epoch=1,request_sha256='b'*64,prefill_rows=256,dedicated_prefill_slots=4,speculative_depth=3)
  extent,header=M.base.prefill_layout(256,16,4);stage=SimpleNamespace(prefill=bytearray(extent),stream_bytes=16)
  provider=SimpleNamespace(stream_bytes=16,shared=bytearray(HEADER.pack(MAGIC,VERSION,128,0,16,1,3,0,1,bytes.fromhex('b'*64),bytes(56))))
  old=R.authority;R.authority=lambda p,i:dict(prompt_sha256='c'*64)
  issued=[]
  try:
   plan['dedicated_reset_ready']=(1,'b'*64,'c'*64)
   with self.assertRaisesRegex(ValueError,'geometry'):M.admit_drive([stage],provider,plan,1)
   self.assertFalse(issued)
   # All ACK + cold proof prerequisite is the readiness tuple. Publishing the
   # production header occurs afterward; the first OP15 sees exact geometry.
   stage.prefill[:len(header)]=header;plan['dedicated_reset_ready']=(1,'b'*64,'c'*64)
   M.admit_drive([stage],provider,plan,1);issued.append(15);self.assertEqual(issued,[15])
   with self.assertRaisesRegex(ValueError,'one-shot'):M.admit_drive([stage],provider,plan,1)
   stage.prefill[-1]=1;plan['dedicated_reset_ready']=(1,'b'*64,'c'*64)
   with self.assertRaisesRegex(ValueError,'geometry'):M.admit_drive([stage],provider,plan,1)
  finally:R.authority=old
if __name__=='__main__':unittest.main()
