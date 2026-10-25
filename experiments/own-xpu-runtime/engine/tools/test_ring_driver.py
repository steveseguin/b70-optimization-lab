from hashlib import sha256
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import ring_driver as driver
from test_ring_coordinator import Worker,reference
from test_wavefront_driver import Guard,exact
from test_ring_wire import command
base,wire,ring=driver.base,driver.wire,driver.ring

def worker(sock,shared,index,count,prompt,state,errors,fault=None):
    model=Worker(index,count,0,prompt);state['worker']=model
    try:
        while (packet:=exact(sock,base.REQUEST.size)) is not None:
            op,token,position,fixture,spec,seq,stage,final=base.REQUEST.unpack(packet)
            assert stage==index and final==int(index==count-1)
            m=wire.ROW_META.unpack(bytes(shared[wire.ROW_OFFSET:wire.ROW_OFFSET+224]))
            assert m[:3]==(0x52494e47,1,224) and m[-1]==bytes(16)
            assert m[7:12]==(position,token,fixture,index,final)
            row=ring.Row(m[4],m[5],m[6],position,token,fixture,m[17],m[18],m[19])
            assert row.after==wire.append_prefix(row.before,position,token)
            source=None
            if op==ring.ROW and index:
                payload=bytes(shared[base.SLOT:base.SLOT+16]);assert m[12]==index-1 and m[13]>0 and m[14]==0 and m[15]==16
                source=ring.Publication(row,index-1,m[13],payload,m[20])
            else:assert m[12:16]==(-1,0,0,0) and m[20]==wire.EMPTY_SHA
            c=ring.Command(index,op,seq,row,bool(m[3]),0 if op==ring.ROW else spec,source)
            assert m[3] in (0,1) and (op!=ring.ROW or spec==m[3])
            ack=model.execute(c);output,extent=0,0
            if op==ring.ROW:
                output=ack.token if final and fixture else -1;extent=0 if final else 16
                data=b'' if final else bytes(ack.stream)
                if data:shared[:16]=data
                publication=list(m);publication[3]|=2;publication[14],publication[15],publication[20]=seq,extent,sha256(data).digest()
                shared[wire.ROW_OFFSET:wire.ROW_OFFSET+224]=wire.ROW_META.pack(*publication)
                time.sleep(0.0002 if not final else 0.004)
            else:
                raw=wire.ACK_META.pack(0x5241434b,1,128,int(op==ring.ABORT_SUFFIX),0,row.identity,
                    *(ack.discarded+(0,0))[:2],index,seq,spec,ack.physical,ack.committed,len(ack.discarded),ack.pending,0,bytes(48))
                shared[wire.ACK_OFFSET:wire.ACK_OFFSET+128]=raw
            reply=base.REPLY.pack(0,output,0,extent,seq,0 if index==0 else 1,index,final,0.1,0,0,0)
            if fault and op==ring.ROW:reply=fault(reply,shared)
            sock.sendall(reply[:7]);time.sleep(0.00002);sock.sendall(reply[7:])
    except Exception as error:errors.append(repr(error))
    finally:sock.close()

class DriverTests(unittest.TestCase):
    def test_lifecycle_injection_and_hash_bound_ring_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp);plan={'output':tmp}
            def execute(plan,admission,unit,**kwargs):
                self.assertIs(kwargs['stage_type'],driver.RingStage)
                self.assertIs(kwargs['driver'],driver.drive)
                self.assertTrue(kwargs['scripted_proposals'])
                base.save(output/'plan.json',plan)
                base.save(output/'result.json',{'passed':True,'mode':'verified-wavefront'})
            with patch.object(driver.lifecycle,'execute',side_effect=execute):driver.execute(plan,{},'fixture')
            result=json.loads((output/'ring-result.json').read_text())
            self.assertEqual(result['mode'],'scripted-target-only-ring')
            self.assertEqual(result['lifecycle_result_sha256'],base.digest(output/'result.json'))
            self.assertEqual(result['plan_sha256'],base.digest(output/'plan.json'))
            self.assertEqual(json.loads((output/'result.json').read_text())['mode'],'verified-wavefront')
    def fixture(self,count,misses=(),requirements=(1,2),fault=None):
        prompt=[3,5,8,11];_,outputs=reference(prompt,12,(96,))
        plan=dict(prompt_tokens=prompt,max_new=12,context=128,vocab=97,eos_token_ids=[96],request_sha256=sha256(b'fixture').hexdigest(),
                  scripted_proposal_tokens=outputs,force_miss_positions=list(misses),required_miss_depths=list(requirements),
                  require_two_row_abort=bool(requirements),verify_restore=True)
        stages,threads,states,errors=[],[],[],[];guard=Guard()
        try:
            for i in range(count):
                s=driver.RingStage.__new__(driver.RingStage);s.sock,peer=socket.socketpair()
                s.shared=bytearray(base.SHARED);s.stream_bytes=16;s.sequence=0;s.spec=dict(id=i,first=i==0,final=i==count-1);s.guard=guard;s.plan=plan
                state={};t=threading.Thread(target=worker,args=(peer,s.shared,i,count,prompt,state,errors,fault),daemon=True)
                stages.append(s);threads.append(t);states.append(state);t.start()
            with tempfile.TemporaryDirectory() as tmp:
                result=driver.drive(stages,plan,guard,Path(tmp))
                events=[json.loads(line) for line in (Path(tmp)/'schedule.jsonl').read_text().splitlines()]
                model_events=[e for e in events if e['event']!='native-reply']
                self.assertEqual(model_events,json.loads(json.dumps(result['events'])))
                self.assertEqual(model_events[-1]['event'],'drained')
            self.assertFalse(errors);inputs,_=reference(prompt,12,(96,))
            for state in states:self.assertEqual(state['worker'].ring.physical['history'],inputs)
            self.assertEqual(result['output_ids'],outputs);return result
        finally:
            for s in stages:s.sock.close()
            for t in threads:t.join(timeout=2)
    def test_fragmented_sockets_two_four_six_miss_depths_suffix(self):
        for count in (2,4,6):
            with self.subTest(count=count):
                result=self.fixture(count,(4,5,7))
                self.assertEqual({r['depth'] for r in result['ring']['rejected_rows'].values()},{1,2})
                self.assertTrue(result['ring']['two_row_stage0_restores'])
    def test_all_hits_without_mandatory_miss_claim(self):self.fixture(4,requirements=())
    def test_bad_publication_refused_before_followup(self):
        def corrupt(reply,shared):shared[wire.ROW_OFFSET+40]^=1;return reply
        with self.assertRaisesRegex(ValueError,'published row'):self.fixture(2,requirements=(),fault=corrupt)
    def test_stale_wire_reply_refused(self):
        def corrupt(reply,shared):
            values=list(base.REPLY.unpack(reply));values[4]+=1;return base.REPLY.pack(*values)
        with self.assertRaisesRegex(ValueError,'stale sequence'):self.fixture(2,requirements=(),fault=corrupt)
    def test_resolution_requires_original_tentative(self):
        s=driver.RingStage.__new__(driver.RingStage);s.sock,peer=socket.socketpair();s.guard=Guard();s.sequence=11
        s.spec=dict(id=0,final=False);s.shared=bytearray(base.SHARED);s.stream_bytes=16;s.start_async();s.pending_rows=[command()]
        try:
            c=ring.Command(0,ring.ACCEPT,12,s.pending_rows[0].row,False,11)
            with self.assertRaisesRegex(ValueError,'original ROW flags'):s.issue(c)
            self.assertIsNone(s.command_pending)
        finally:s.sock.close();peer.close()
    def test_truncated_reply_refuses_without_retiring_request(self):
        s=driver.RingStage.__new__(driver.RingStage);s.sock,peer=socket.socketpair();s.guard=Guard();s.sequence=10
        s.spec=dict(id=0,first=True,final=False);s.shared=bytearray(base.SHARED);s.stream_bytes=16;s.plan={'vocab':97}
        s.start_async();c=command();s.issue(c)
        try:
            s.write_ready();self.assertEqual(len(exact(peer,base.REQUEST.size)),base.REQUEST.size)
            peer.sendall(b'\0'*7);peer.shutdown(socket.SHUT_WR)
            self.assertIsNone(s.read_ready())
            with self.assertRaisesRegex(ValueError,'channel closed'):s.read_ready()
            self.assertIs(s.command_pending,c)
            self.assertEqual(s.pending_rows,[])
        finally:s.sock.close();peer.close()
    def test_plan_caps_pins_and_no_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);receipt=p/'receipt.json';config=p/'config.json'
            receipt.write_text(json.dumps({'sources':{'pipeline/ring/'+n+'.hpp':'fixture' for n in ('stage_ring','wire','checkpoint_ring','engine_backend','dispatcher')}}))
            config.write_text(json.dumps(dict(ring=True,build_receipt=str(receipt),scripted_proposal_tokens=[1]*12,force_miss_positions=[4,7])))
            plan=dict(stages=[{'argv':[]} for _ in range(4)],pins={},max_new=12,vocab=97,prompt_tokens=[3,5,8,11],context=128,eos=96,model_identity_sha256='a'*64)
            with patch.object(base,'make_plan',return_value=plan):result=driver.make_plan(config)
            self.assertTrue(all('--pipeline-ring' in s['argv'] for s in result['stages']));self.assertFalse(result['speed_claim'])
            self.assertIn(str(wire.PLANNING/'ring_coordinator.py'),result['pins']);receipt.write_text('{"sources":{}}')
            with patch.object(base,'make_plan',return_value=plan),self.assertRaisesRegex(ValueError,'ring build'):driver.make_plan(config)
