"""CPU fake peers, real Stage/Provider framing; no native/model qualification."""
from hashlib import sha256
import json
from pathlib import Path
import socket
import struct
import tempfile
import threading
from types import SimpleNamespace as NS
import unittest
from rolling_provider import dedicated_prefill as P,prefill,transport
from unittest.mock import patch
from rolling_provider.dedicated import DedicatedCoordinator
from rolling_provider.dedicated_transport import Provider,MAGIC,VERSION,base
from test_dedicated_prefill import record as record_v1,ack as ack_v1

def record(m,role,start,count,sequence,stream=32,raw_sha=bytes(32),slots=2):
    raw=record_v1(m,role,start,count,sequence,stream,raw_sha);fields=list(P.RECORD.unpack(raw[:256]))
    fields[1]=prefill.geometry(slots)[1];fields[7]=(start//256)%slots;fields[15]=4 if slots==4 else 0
    return P.RECORD.pack(*fields)+raw[256:]

def ack(m,start,count,sequence,seed,final,raw_sha,slots=2):
    fields=list(P.ACK.unpack(ack_v1(m,start,count,sequence,seed,final,raw_sha)))
    fields[1]=prefill.geometry(slots)[1];fields[6]=(start//256)%slots;fields[14]=4 if slots==4 else 0
    return P.ACK.pack(*fields)

class Guard:
    def __init__(self):self.failed=None
    def check(self):
        if self.failed:raise ValueError(self.failed)
    def fail(self,reason):self.failed=reason

class PipelineTest(unittest.TestCase):
    def exercise(self,failure=None,pipeline=True,targets=3,slots=2):
        final_index=targets-1
        length=2307 if slots==4 else 1677;bulk=length-2
        prompt=[i%90 for i in range(length)]
        m=DedicatedCoordinator(stages=targets,request=sha256(b'pipeline').digest(),epoch=0,prompt=prompt,
            max_new=4,context=4096,vocab=97,eos_token_ids=[96],stream_bytes=32,speculative_depth=3)
        guard=Guard();errors=[];threads=[];sockets=[];stages=[];operations=[];lock=threading.Lock()
        # Force provider0 to retain parity0 while stage0/1/2 finish opposite parity1.
        second_final=threading.Event();provider_zero=threading.Event()
        def pair():
            a,b=socket.socketpair();a.settimeout(.05);b.settimeout(.05);sockets.extend((a,b));return a,b
        def read(sock):
            raw=b''
            while len(raw)<32:
                guard.check()
                try:part=sock.recv(32-len(raw))
                except socket.timeout:continue
                if not part:raise ValueError('peer closed')
                raw+=part
            return base.REQUEST.unpack(raw)
        def send(sock,raw):
            for first,last in ((0,1),(1,7),(7,31),(31,len(raw))):sock.sendall(raw[first:last])
        def target_loop(i,sock):
            try:
                for k,start in enumerate(range(0,bulk,256)):
                    count=min(256,bulk-start);parity=k%slots;seq=k+1
                    self.assertEqual(read(sock),(15,count,start,parity,0,seq,i,int(i==final_index)))
                    position=start+count-1
                    row=transport.ring.Row(m.epoch,position+1,position,position,prompt[position],0,m.request,m.proposals.hashes[position],m.proposals.hashes[position+1])
                    expected=prefill.verified_metadata(transport.pending.wire,row,i,i==final_index)
                    offmeta=transport.pending.wire.ROW_OFFSET
                    self.assertEqual(bytes(stages[i].shared[offmeta:offmeta+len(expected)]),expected)
                    with lock:operations.append((i,k,'start'))
                    if i==0:
                        self.assertEqual(struct.unpack(f'<{count}i',stages[i].prefill[prefill.geometry(slots)[2]:prefill.geometry(slots)[2]+4*count]),tuple(prompt[start:start+count]))
                        data=bytes([seq])*(count*32)
                    else:
                        data=bytes(prefill.region(stages[i].prefill,'forward',parity,256,32,count,slots=slots))
                        self.assertEqual(data,bytes([seq])*(count*32))
                    out='forward' if i==0 else 'reverse'
                    prefill.region(stages[i].prefill,out,parity,256,32,count,slots=slots)[:]=data
                    if i in (0,final_index):
                        raw=record(m,1 if i==0 else 2,start,count,seq,raw_sha=sha256(data).digest(),slots=slots)
                        off=P.RECORD_OFFSET+parity*1280;stages[i].prefill[off:off+1280]=raw
                    send(sock,base.REPLY.pack(0,-1,0,count*32,seq,0 if i==0 else 1,i,int(i==final_index),0.,0.,0.,0.))
                    with lock:operations.append((i,k,'complete'))
                    # Release provider0 only after the real fragmented reply is
                    # sent AND its completion observation is recorded.
                    if i==final_index and k==slots-1:second_final.set()
            except BaseException as e:
                if not guard.failed:errors.append(e);guard.fail(str(e))
        for i in range(targets):
            client,server=pair();s=transport.Stage.__new__(transport.Stage)
            s.sock=client;s.shared=bytearray(base.SHARED);s.prefill=bytearray(prefill.map_bytes(256,32,slots));s.prefill_slots=slots
            s.prefill_rows=256;s.stream_bytes=32;s.sequence=0;s.guard=guard;s.plan=dict(seconds=3)
            s.spec=dict(id=i,first=i==0,final=i==final_index);s.physical=s.committed=0;stages.append(s)
        client,server=pair();provider=Provider(NS(sock=client,shared=bytearray(base.SHARED),guard=guard,plan=dict(seconds=3),sequence=0));provider.stream_bytes=32
        def provider_loop():
            try:
                for k,start in enumerate(range(0,bulk,256)):
                    count=min(256,bulk-start);parity=k%slots;seq=k+1
                    self.assertEqual(read(server),(28,count,start,parity,0,seq,MAGIC,VERSION))
                    if k==0 and failure=='cancel':
                        provider_zero.set()
                        while not guard.failed:threading.Event().wait(.005)
                        return
                    if k==0 and pipeline:
                        provider_zero.set();self.assertTrue(second_final.wait(2),'opposite parity target completion blocked')
                        self.assertEqual(stages[0].sequence,slots,'next chunk cannot overwrite retained slot')
                    off=P.RECORD_OFFSET+parity*1280
                    seed=bytes(stages[0].prefill[off:off+1280]);final=bytes(stages[final_index].prefill[off:off+1280])
                    data=bytes(prefill.region(stages[final_index].prefill,'reverse',parity,256,32,count,slots=slots))
                    a=ack(m,start,count,seq,seed,final,sha256(data).digest(),slots=slots)
                    if failure=='ack' and k==0:a=bytes([a[0]^1])+a[1:]
                    if failure=='source' and k==0:stages[0].prefill[off]^=1
                    provider.shared[1024:1280]=a
                    send(server,base.REPLY.pack(0,-1,0,256,seq,-1,MAGIC,VERSION,0.,0.,0.,0.))
                    with lock:operations.append((targets,k,'complete'))
                    if failure:return
            except BaseException as e:
                if not guard.failed:errors.append(e);guard.fail(str(e))
        for i in range(targets):threads.append(threading.Thread(target=target_loop,args=(i,sockets[i*2+1]),daemon=True))
        threads.append(threading.Thread(target=provider_loop,daemon=True))
        for thread in threads:thread.start()
        try:
            with tempfile.TemporaryDirectory() as td:
                path=Path(td)/'prompt';raw=struct.pack(f'<{length}i',*prompt);path.write_bytes(raw)
                plan=dict(dedicated_prefill_slots=slots,dedicated_bulk_prefill=True,dedicated_prefill_pipeline=pipeline,prefill_rows=256,prompt_tokens=prompt,
                    dedicated_prefill_prompt=str(path),dedicated_prefill_prompt_sha256=sha256(raw).hexdigest())
                if failure:
                    with self.assertRaisesRegex(ValueError,'ACK|publication|interrupted'):
                        P.run(stages,provider,m,plan,td,stop_requested=lambda:failure=='cancel' and provider_zero.is_set())
                    self.assertEqual(m.frontier,0);self.assertLessEqual(stages[0].sequence,slots)
                else:
                    if pipeline is False:plan.pop('dedicated_prefill_pipeline')
                    result=P.run(stages,provider,m,plan,td)
                    self.assertEqual((m.frontier,m.provider.serial,m.provider.next_seed),(bulk,bulk,bulk+1))
                    log=[json.loads(s) for s in (Path(td)/'dedicated-prefill.jsonl').read_text().splitlines()]
                    self.assertEqual([r['count'] for r in log],[256]*9+[1] if slots==4 else [256]*6+[139])
                    self.assertEqual([r['target_sequences'] for r in log],[[i]*targets for i in range(1,(bulk+255)//256+1)])
                    self.assertEqual(result['prefill_chunks'],(bulk+255)//256)
                    if pipeline:
                        self.assertEqual(result['prefill_timing']['peak_unfinished_chunks'],slots)
                        self.assertLess(operations.index((final_index,slots-1,'complete')),operations.index((targets,0,'complete')))
                    else:self.assertFalse((Path(td)/'dedicated-prefill-pipeline.jsonl').exists())
                    # Strict existing ingestion consumes unchanged journal. These
                    # peer-generated traces are explicitly CPU-shaped, not GPU proof.
                    chunks=[];pairs=[]
                    for j in log:
                        a=P.ACK.unpack(bytes.fromhex(j['provider_ack_hex']))
                        chunks.append(dict(epoch=a[16],request=a[18].hex(),sequence=a[3],start=a[4],count=a[5],serial=a[17],prompt_sha256=a[19].hex(),seed_record_sha256=a[20].hex(),final_record_sha256=a[21].hex(),raw_sha256=a[22].hex()))
                    for p in range(1,bulk+1):
                        seq=(p-1)//256+1;pairs.append(dict(position=p,token=prompt[p],head=False,provider_serial=p,hidden_bytes=32,hidden_sha256=sha256(bytes([seq])*32).hexdigest(),command_sequence=seq))
                    cp=Path(td)/'chunks';pp=Path(td)/'pairs'
                    cp.write_text(''.join(json.dumps(x)+'\n' for x in chunks));pp.write_text(''.join(json.dumps(x)+'\n' for x in pairs))
                    self.assertEqual(P.prefix_evidence(Path(td)/'dedicated-prefill.jsonl',pp,cp,m,slots=slots)['positions'],bulk)
        finally:
            guard.fail(guard.failed or 'test cleanup')
            for thread in threads:thread.join(1)
            for sock in sockets:sock.close()
        self.assertTrue(all(not t.is_alive() for t in threads));self.assertFalse(errors,errors)
    def test_optin_strict_boolean_and_three_targets(self):
        from rolling_provider import dedicated_prefill_pipeline as Q
        with self.assertRaisesRegex(ValueError,'two/three-target'):
            Q.run([None],None,None,dict(dedicated_prefill_pipeline=True),'.',source={})
        m=NS(prompt=list(range(260)),frontier=0,rows={})
        owners=[NS(prefill_rows=256,stream_bytes=32,sequence=0)]*3
        provider=NS(provider_serial=0,sequence=0,stream_bytes=32)
        for invalid in (1,0,'true',None):
            with patch.object(P,'prompt_source',return_value=(b'',dict(sha256='00'*32))):
                with self.assertRaisesRegex(ValueError,'must be boolean'):
                    P.run(owners,provider,m,dict(dedicated_bulk_prefill=True,prefill_rows=256,dedicated_prefill_pipeline=invalid),'.')
    def test_real_fragmented_sockets_partial_tail_and_reordered_actors(self):self.exercise()
    def test_bad_full_ack_stops_without_adoption_or_parity_reuse(self):self.exercise('ack')
    def test_four_slots_three_targets_wrap_twice(self):self.exercise(slots=4)
    def test_four_slots_two_targets_wrap_twice(self):self.exercise(targets=2,slots=4)
    def test_four_slots_failed_ack_no_reuse(self):self.exercise('ack',slots=4)
    def test_four_slots_overwrite_refused(self):self.exercise('source',slots=4)
    def test_four_slots_cancel_drains(self):self.exercise('cancel',slots=4)
    def test_two_target_final_reverse_partialtail_and_leases(self):self.exercise(targets=2)
    def test_two_target_failed_ack_no_adoption(self):self.exercise('ack',targets=2)
    def test_two_target_overwrite_no_parity_reuse(self):self.exercise('source',targets=2)
    def test_two_target_cancel_drains_workers(self):self.exercise('cancel',targets=2)
    def test_cancellation_drains_socket_workers_without_adoption(self):self.exercise('cancel')
    def test_source_overwrite_before_ack_refused(self):self.exercise('source')
    def test_sequential_default_behavior_unchanged(self):self.exercise(pipeline=False)

if __name__=='__main__':unittest.main()
