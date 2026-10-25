import hashlib
import json
import socket
import struct
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from pathlib import Path

import live_wavefront_driver as live
from test_wavefront_driver import Guard, exact
base, wave, codec = live.base, live.wave, live.codec


def worker(sock, shared, index, count, state, errors, misses, initial_sequence=0):
    sequence, pending, snapshot, expected_next = initial_sequence, None, None, None
    try:
        while (packet := exact(sock, base.REQUEST.size)) is not None:
            op, token, position, fixture, spec, seq, stage, final = base.REQUEST.unpack(packet)
            sequence += 1
            assert seq == sequence and stage == index and final == int(index == count - 1)
            output, extent = 0, 0
            if op == codec.STEP:
                assert index == 0 and pending is None and spec == 0
                h = codec.decode(shared[codec.HEADER_OFFSET:codec.HEADER_OFFSET+codec.HEADER.size],
                                 shared[base.SLOT:base.SLOT+16],stream_bytes=16,stages=count,vocab=97)
                assert position == len(state['pairs']) + 1 == h.position + 1
                assert not h.head or token == h.next_token
                assert struct.unpack('<4i',h.hidden)==(456,h.input_token,h.position,count-1)
                state['pairs'].append((position,token,fixture))
                output = (token*7+position+4+int(position+1 in misses))%97 if fixture else -1
            elif op == wave.schedule.ROW:
                assert pending is None and position == len(state['tokens'])
                if final:
                    assert not spec
                    if fixture > 1: assert token == expected_next
                if index:
                    assert struct.unpack('<4i',shared[base.SLOT:base.SLOT+16])==(123,token,position,index-1)
                snapshot = list(state['tokens']) if spec else None
                state['tokens'].append(token)
                output = (token*7+position+4)%97 if final and fixture else 0
                pending=(seq,token,position,fixture,spec,output)
                if not final:
                    shared[:16]=struct.pack('<4i',123,token,position,index)
                    output,extent=-1,16
                time.sleep(0.00015*(1+(position+index)%4))
            elif op in (wave.schedule.COMMIT,wave.schedule.ABORT):
                assert pending and pending[:4]==(spec,token,position,fixture)
                if op == wave.schedule.ABORT:
                    assert pending[4] and snapshot is not None
                    state['tokens']=snapshot
                    state['aborts']+=1
                elif final:
                    if fixture: expected_next=pending[5]
                    hidden=struct.pack('<4i',456,token,position,index)
                    output,extent=pending[5] if fixture else -1,16
                    header=codec.HEADER.pack(codec.MAGIC,1,16,position,index,count,spec,seq,
                                             token,output,int(fixture>0),0,
                                             hashlib.sha256(hidden).hexdigest().encode())
                    shared[codec.HEADER_OFFSET:codec.HEADER_OFFSET+codec.HEADER.size]=header
                    shared[codec.HIDDEN_OFFSET:codec.HIDDEN_OFFSET+16]=hidden
                pending,snapshot=None,None
            else: raise AssertionError('unexpected op')
            reply=base.REPLY.pack(0,output,0,extent,seq,0 if index==0 else 1,index,final,0.1,0,0,0)
            sock.sendall(reply[:9]); time.sleep(0.00003); sock.sendall(reply[9:])
    except Exception as error: errors.append(repr(error))
    finally: sock.close()


class LiveTests(unittest.TestCase):
    def test_live_plan_removes_legacy_probe_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); manifest=p/'draft.tsv';manifest.write_text('fixture')
            receipt=p/'receipt.json';receipt.write_text(json.dumps({'sources':{'pipeline/live_draft.hpp':'fixture'}}))
            adapter=p/'adapter.json';adapter.write_text(json.dumps({'rank_argv':[['--draft-mtp','--draft-fault','none','--draft-manifest',str(manifest),'--draft-model','/model','--draft-experts','fp8']]}))
            config=p/'config.json';config.write_text(json.dumps({'live_draft':True,'build_receipt':str(receipt),'adapter_plan':str(adapter)}))
            plan={'pins':{},'eos':96,'vocab':97,'stages':[{'first':i==0,'argv':['--draft-rank','0'],
                    'environment':{'OWNRT_DRAFT_DEPTH_PROBE':'0','OWNRT_DRAFT_DEPTH_VERIFY':'0'}} for i in range(4)]}
            with patch.object(base,'make_plan',return_value=plan): result=live.make_plan(config)
            for stage in result['stages']:
                self.assertNotIn('OWNRT_DRAFT_DEPTH_PROBE',stage['environment'])
                self.assertNotIn('OWNRT_DRAFT_DEPTH_VERIFY',stage['environment'])
                self.assertEqual('--draft-mtp' in stage['argv'],stage['first'])

    def fixture(self,count,misses,max_new=12,eos=96,prompt=None,use_proposals=True,
                eos_token_ids=None, initial_sequence=0):
        prompt=prompt or [3,5,8,11]
        inputs=list(prompt); outputs=[]
        for _ in range(max_new):
            token=(inputs[-1]*7+len(inputs)+3)%97; outputs.append(token)
            if token in (eos_token_ids or [eos]) or len(outputs)==max_new: break
            inputs.append(token)
        plan=dict(prompt_tokens=prompt,max_new=max_new,vocab=97,eos=eos,seconds=15,
                  stages=[{} for _ in range(count)],use_proposals=use_proposals,
                  eos_token_ids=eos_token_ids)
        stages,threads,states,errors=[],[],[],[]; guard=Guard()
        try:
            for i in range(count):
                s=live.LiveStage.__new__(live.LiveStage); s.sock,peer=socket.socketpair()
                s.spec=dict(id=i,first=i==0,final=i==count-1)
                s.shared=bytearray(base.SHARED); s.sequence=initial_sequence; s.stream_bytes=16;s.guard=guard;s.plan=plan
                state=dict(tokens=[],pairs=[],aborts=0)
                t=threading.Thread(target=worker,args=(peer,s.shared,i,count,state,errors,misses,initial_sequence),daemon=True)
                stages.append(s);states.append(state);threads.append(t);t.start()
            with tempfile.TemporaryDirectory() as tmp:
                result=live.drive(stages,plan,guard,Path(tmp),
                                  initial_sequences=tuple(s.sequence for s in stages) if initial_sequence else None)
            self.assertEqual(result['output_ids'],outputs)
            self.assertTrue(all(s['tokens']==inputs for s in states))
            self.assertEqual(states[0]['pairs'],[(p,inputs[p],int(p+1>=len(prompt))) for p in range(1,len(inputs))])
            self.assertEqual(result['draft_pairs'],len(inputs)-1)
            return states
        finally:
            for s in stages:s.sock.close()
            for t in threads:t.join(timeout=2)
            self.assertFalse(any(t.is_alive() for t in threads)); self.assertEqual(errors,[])

    def test_live_true_pairs_and_miss_rollback(self):
        for count in (2,4,6):
            for misses in (set(),{5,8,11},set(range(4,16))):
                with self.subTest(count=count,misses=misses):
                    states=self.fixture(count,misses)
                    if misses:self.assertGreater(sum(s['aborts'] for s in states),0)

    def test_prompt_bootstrap_eos_and_cap(self):
        self.fixture(4,set(),max_new=1)
        self.fixture(4,{5,6},eos=84)
        self.fixture(2,set(),prompt=[7],max_new=1)
        self.fixture(2,{2,3},prompt=[7],max_new=8)

    def test_sequential_true_pair_reference_never_speculates(self):
        for count in (2,4):
            states=self.fixture(count,set(range(4,16)),use_proposals=False)
            self.assertTrue(all(s['aborts']==0 for s in states))

    def test_secondary_eos_drains_speculation_with_nonzero_wire_sequence(self):
        for count in (2,4,6):
            self.fixture(count,{4,5},eos_token_ids=[96,14],initial_sequence=500)


if __name__=='__main__':unittest.main()
