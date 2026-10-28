"""CPU wire-shaped dedicated bulk tests; no native/model/device qualification."""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import socket
import struct
from tempfile import TemporaryDirectory
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from rolling_provider import dedicated_prefill as P,prefill
from rolling_provider.dedicated import DedicatedCoordinator
from rolling_provider.dedicated_transport import Provider,MAGIC,VERSION,base

class Guard:
    def check(self):pass

def model(stages=2,prompt=None):
    return DedicatedCoordinator(stages=stages,request=sha256(b'bulk-wire').digest(),epoch=0,
        prompt=prompt or [i%90 for i in range(520)],max_new=4,context=1024,vocab=97,eos_token_ids=[96],
        stream_bytes=32,speculative_depth=3)

def record(m,role,start,count,sequence,stream=32,raw_sha=bytes(32)):
    rows=256;parity=(start//rows)%2;prompt=m.prompt
    fields=(P.CHUNK_MAGIC,1,1280,sequence,role,0 if role==1 else len(m.stages)-1,len(m.stages),parity,start,count,rows,
        stream,15,sequence,prompt[start+count] if role==1 else 0xffffffff,0,m.epoch,m.request,
        sha256(struct.pack(f'<{len(prompt)}i',*prompt)).digest(),m.proposals.hashes[start],m.proposals.hashes[start+count],
        bytes(32) if role==1 else raw_sha,bytes(24))
    tokens=tuple(prompt[start:start+count])+tuple([0]*(256-count)) if role==1 else tuple([0]*256)
    return P.RECORD.pack(*fields)+P.TOKENS.pack(*tokens)

def ack(m,start,count,sequence,seed,final,raw_sha):
    return P.ACK.pack(P.ACK_MAGIC,1,256,sequence,start,count,(start//256)%2,256,32,len(m.stages),sequence,sequence,
        start+count+1,1,0,0,m.epoch,start+count,m.request,sha256(struct.pack(f'<{len(m.prompt)}i',*m.prompt)).digest(),
        sha256(seed).digest(),sha256(final).digest(),raw_sha,bytes(16))

class BulkTests(unittest.TestCase):
    def test_request_clock_includes_model_setup_and_bulk(self):
        from rolling_provider import dedicated_transport as T
        clock=[99.]
        def now():
            clock[0]+=1
            return clock[0]
        done=NS(done=True,events=[],emitted=[4,5],frontier=10,stop_reason=None,
            provider_jobs={},provider=NS(serial=9,reset_allowed=lambda:True),
            cancelled_provider_incomplete=False)
        def construct(**kwargs):
            clock[0]+=3
            return done
        def bulk(*args,**kwargs):
            clock[0]+=20
            return dict(prefill_positions=10,prefill_draft_replay=9)
        def owner():
            # Hashable sockets stand in for idle transports; no protocol claim.
            class Socket:
                def settimeout(self,_):pass
            return NS(sock=Socket(),stream_bytes=32,sequence=0,start_async=lambda:None,
                command_pending=None,transmit=b'',received=b'',pending_rows=[],physical=0,committed=0)
        stages=[owner(),owner()];provider=owner()
        plan=dict(rolling_depth2=True,use_proposals=True,dedicated_bulk_prefill=True,
            request_sha256='00'*32,prompt_tokens=list(range(12)),max_new=2,context=64,
            vocab=97,eos_token_ids=[96],speculative_depth=3)
        with TemporaryDirectory() as td, patch.object(T.time,'monotonic',side_effect=now), \
             patch.object(T,'DedicatedCoordinator',side_effect=construct),patch.object(P,'run',side_effect=bulk):
            result=T.drive(stages,provider,plan,Guard(),td)
            self.assertEqual(result['emitted_elapsed_seconds'],[24.,25.])
            self.assertEqual(result['scheduler_wall_seconds'],26.)
            self.assertEqual(result['emitted_elapsed_seconds'][1]-result['emitted_elapsed_seconds'][0],1.)

    def test_record_every_source_field_and_token_tail_bound(self):
        m=model();raw=record(m,1,512,6,3)
        args=dict(role=1,stage=0,stages=2,start=512,count=6,rows=256,stream=32,parity=0,sequence=3,
            epoch=0,request=m.request,prompt_sha=sha256(struct.pack('<520i',*m.prompt)).digest(),before=m.proposals.hashes[512],
            after=m.proposals.hashes[518],prompt=m.prompt,raw_sha=bytes(32))
        self.assertEqual(P.chunk_record(raw,**args),sha256(raw).digest())
        # Every actual metadata field, including zero reserves and publication sequence, is bound.
        for i in range(23):
            values=list(P.RECORD.unpack(raw[:256]));v=values[i];values[i]=(v+1 if type(v)is int else bytes([v[0]^1])+v[1:])
            corrupt=P.RECORD.pack(*values)+raw[256:]
            with self.assertRaises(ValueError):P.chunk_record(corrupt,**args)
        corrupt=bytearray(raw);corrupt[-1]=1
        with self.assertRaises(ValueError):P.chunk_record(bytes(corrupt),**args)
    def test_prompt_hash_and_path_identity(self):
        with TemporaryDirectory() as td:
            m=model();path=Path(td)/'prompt.i32';raw=struct.pack('<520i',*m.prompt);path.write_bytes(raw)
            plan=dict(prompt_tokens=m.prompt,dedicated_prefill_prompt=str(path),dedicated_prefill_prompt_sha256=sha256(raw).hexdigest())
            self.assertEqual(P.prompt_source(plan)[0],raw)
            path.write_bytes(raw[:-4])
            with self.assertRaises(ValueError):P.prompt_source(plan)
    def run_prefix(self,bad_ack=False):
        m=model();client,server=socket.socketpair();self.addCleanup(client.close);self.addCleanup(server.close)
        owner=NS(sock=client,shared=bytearray(base.SHARED),guard=Guard(),plan={},sequence=0)
        provider=Provider(owner);provider.stream_bytes=32
        stages=[];server_errors=[]
        class Target:
            def __init__(self,index):
                self.index=index;self.prefill_rows=256;self.stream_bytes=32;self.sequence=0;self.shared=bytearray(base.SHARED)
                self.prefill=bytearray(prefill.map_bytes(256,32));self.physical=self.committed=0
            def command(self,op,count,start,parity):
                self.sequence+=1
                if self.index==0:
                    data=bytes([start//256+1])*(count*32)
                    prefill.region(self.prefill,'forward',parity,256,32,count)[:]=data
                    raw=record(m,1,start,count,self.sequence)
                else:
                    data=bytes(prefill.region(self.prefill,'forward',parity,256,32,count))
                    prefill.region(self.prefill,'reverse',parity,256,32,count)[:]=data
                    raw=record(m,2,start,count,self.sequence,raw_sha=sha256(data).digest())
                off=P.RECORD_OFFSET+parity*1280;self.prefill[off:off+1280]=raw
                return (0,-1,0,count*32,self.sequence,0 if self.index==0 else 1,self.index,int(self.index==1),0.,0.,0.,0.)
        stages=[Target(0),Target(1)]
        def server_loop():
            try:
                for sequence,start,count in ((1,0,256),(2,256,256),(3,512,6)):
                    raw=b''
                    while len(raw)<32:raw+=server.recv(32-len(raw))
                    self.assertEqual(base.REQUEST.unpack(raw),(28,count,start,(start//256)%2,0,sequence,MAGIC,VERSION))
                    off=P.RECORD_OFFSET+((start//256)%2)*1280;seed=bytes(stages[0].prefill[off:off+1280]);final=bytes(stages[1].prefill[off:off+1280])
                    data=bytes(prefill.region(stages[-1].prefill,'reverse',(start//256)%2,256,32,count))
                    a=ack(m,start,count,sequence,seed,final,sha256(data).digest())
                    if bad_ack:a=bytes([a[0]^1])+a[1:]
                    provider.shared[1024:1280]=a
                    reply=base.REPLY.pack(0,-1,0,256,sequence,-1,MAGIC,VERSION,0.,0.,0.,0.)
                    server.sendall(reply[:5]);server.sendall(reply[5:])
                    if bad_ack:return
            except BaseException as error:server_errors.append(error)
        thread=threading.Thread(target=server_loop);thread.start()
        with TemporaryDirectory() as td:
            path=Path(td)/'prompt.i32';raw=struct.pack('<520i',*m.prompt);path.write_bytes(raw)
            plan=dict(dedicated_bulk_prefill=True,prefill_rows=256,prompt_tokens=m.prompt,
                dedicated_prefill_prompt=str(path),dedicated_prefill_prompt_sha256=sha256(raw).hexdigest())
            if bad_ack:
                with self.assertRaisesRegex(ValueError,'ACK'):P.run(stages,provider,m,plan,td)
                self.assertEqual(m.frontier,0);self.assertFalse(m.rows);self.assertTrue(provider.prefill_bulk_busy)
            else:
                result=P.run(stages,provider,m,plan,td)
                self.assertEqual(result['prefill_positions'],518);self.assertEqual(result['prefill_chunks'],3)
                self.assertEqual((m.frontier,m.provider.serial,m.provider.next_seed,m.provider_sequence),(518,518,519,3))
                self.assertEqual([s.sequence for s in m.stages],[3,3]);self.assertFalse(m.provider_jobs)
                log=[json.loads(x) for x in (Path(td)/'dedicated-prefill.jsonl').read_text().splitlines()]
                self.assertEqual([x['count'] for x in log],[256,256,6]);self.assertEqual(len(bytes.fromhex(log[-1]['provider_ack_hex'])),256)
                # Native-shaped CPU trace fixture for strict ingestion; not model proof.
                native_chunks=[];native_pairs=[]
                for entry in log:
                    a=P.ACK.unpack(bytes.fromhex(entry['provider_ack_hex']))
                    native_chunks.append(dict(epoch=a[16],request=a[18].hex(),sequence=a[3],start=a[4],count=a[5],serial=a[17],
                        prompt_sha256=a[19].hex(),seed_record_sha256=a[20].hex(),final_record_sha256=a[21].hex(),raw_sha256=a[22].hex()))
                for position in range(1,519):
                    sequence=(position-1)//256+1
                    native_pairs.append(dict(position=position,token=m.prompt[position],head=False,provider_serial=position,
                        hidden_bytes=32,hidden_sha256=sha256(bytes([sequence])*32).hexdigest(),command_sequence=sequence))
                pairpath=Path(td)/'native-pairs.jsonl';chunkpath=Path(td)/'native-chunks.jsonl'
                pairpath.write_text(''.join(json.dumps(x)+'\n' for x in native_pairs));chunkpath.write_text(''.join(json.dumps(x)+'\n' for x in native_chunks))
                proof=P.prefix_evidence(Path(td)/'dedicated-prefill.jsonl',pairpath,chunkpath,m)
                self.assertEqual(proof['actual_native_pairs'],native_pairs)
                for key,value in (('head',True),('token',96),('command_sequence',2),('provider_serial',True)):
                    bad=[dict(x) for x in native_pairs];bad[0][key]=value
                    pairpath.write_text(''.join(json.dumps(x)+'\n' for x in bad))
                    with self.assertRaisesRegex(ValueError,'canonical prefix pair'):P.prefix_evidence(Path(td)/'dedicated-prefill.jsonl',pairpath,chunkpath,m)
                pairpath.write_text(''.join(json.dumps(x)+'\n' for x in native_pairs))
                native_chunks[0]['raw_sha256']='0'*64;chunkpath.write_text(''.join(json.dumps(x)+'\n' for x in native_chunks))
                with self.assertRaisesRegex(ValueError,'native chunk receipt'):P.prefix_evidence(Path(td)/'dedicated-prefill.jsonl',pairpath,chunkpath,m)
                # First real seam command remains positionbulk, next actual seedbulk+1.
                commands=m.commands();self.assertTrue(commands);self.assertEqual(commands[0].row.position,518)
        thread.join(2);self.assertFalse(thread.is_alive());self.assertFalse(server_errors,server_errors)
    def test_two_parities_partial_tail_and_two_row_seam(self):self.run_prefix()
    def test_bad_actual_ack_never_adopts_or_reuses_owner(self):self.run_prefix(True)
    def test_actual_native_emitted_terminal_wire(self):
        # Files emitted by the actual C++ run_loop CPU test, not Python fixtures.
        root=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/pp4-review-2026-10-28/dedicated-gate/bulk-candidate/native-wire-fixture')
        f=json.loads((root/'fixture.json').read_text());prompt=f['prompt_tokens']
        self.assertEqual((root/'prompt').read_bytes(),struct.pack(f'<{len(prompt)}i',*prompt))
        self.assertEqual(sha256((root/'prompt').read_bytes()).hexdigest(),f['prompt_sha256'])
        m=DedicatedCoordinator(stages=f['stages'],request=bytes.fromhex(f['request']),epoch=f['epoch'],prompt=prompt,
            max_new=4,context=64,vocab=f['vocab'],eos_token_ids=[127],stream_bytes=f['stream_bytes'],speculative_depth=3)
        raw_ack=(root/'ack-3.bin').read_bytes();raw_sha=P.ACK.unpack(raw_ack)[-2]
        common=dict(stages=f['stages'],start=f['start'],count=f['count'],rows=f['rows'],stream=f['stream_bytes'],
            parity=f['parity'],epoch=f['epoch'],request=m.request,prompt_sha=bytes.fromhex(f['prompt_sha256']),
            before=m.proposals.hashes[f['start']],after=m.proposals.hashes[f['start']+f['count']],prompt=prompt,raw_sha=raw_sha)
        seed=P.chunk_record((root/'seed-record-3.bin').read_bytes(),role=1,stage=0,sequence=3,**common)
        final=P.chunk_record((root/'final-record-3.bin').read_bytes(),role=2,stage=2,sequence=3,**common)
        self.assertEqual(P.chunk_ack(raw_ack,sequence=3,start=8,count=1,parity=0,rows=4,stream=16,stages=3,
            seed_sequence=3,final_sequence=3,epoch=0,request=m.request,prompt_sha=bytes.fromhex(f['prompt_sha256']),
            seed_sha=seed,final_sha=final,raw_sha=raw_sha),9)
        self.assertEqual(base.REPLY.unpack((root/'reply-3.bin').read_bytes()),(0,-1,0,256,3,-1,MAGIC,VERSION,0.,0.,0.,0.))

    def test_adoption_without_native_receipt_refused(self):
        m=model()
        with self.assertRaisesRegex(ValueError,'authenticated'):m.adopt_prefill(518)

if __name__=='__main__':unittest.main()
