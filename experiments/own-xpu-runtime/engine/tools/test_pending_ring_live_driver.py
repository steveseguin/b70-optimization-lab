from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import pending_ring_live_driver as pending
from test_ring_coordinator import Worker,reference
from test_wavefront_driver import Guard,exact
from test_ring_live_driver import hidden,reference_rows
from test_ring_live_wire import final_fixture
base,codec,wire,ring=pending.base,pending.codec,pending.wire,pending.ring

def worker(sock,shared,mappings,index,count,prompt,state,errors):
    model=Worker(index,count,0,prompt);state['worker']=model;serial=0;final_tokens={}
    try:
        while (packet:=exact(sock,base.REQUEST.size)) is not None:
            op,token,pos,fixture,spec,seq,stage,final=base.REQUEST.unpack(packet)
            assert stage==index and final==int(index==count-1)
            m=wire.ROW_META.unpack(bytes(shared[wire.ROW_OFFSET:wire.ROW_OFFSET+224]))
            row=ring.Row(m[4],m[5],m[6],m[7],m[8],m[9],m[17],m[18],m[19]);assert row.token==token and row.position==pos and m[3] in (0,1)
            output=extent=0
            if op==27:
                assert index==0 and spec==2 and model.ring.committed==pos+1 and all(p.ticket.tentative for p in model.ring.pending)
                assert state['accepted'].row==row and state['accepted'].tentative==bool(m[3]);assert seq==model.sequence+1;model.sequence=seq;serial+=1;assert fixture==int(row.fixture>0) and pos==serial
                peer=mappings[-1];record=bytes(peer[codec.FINAL_OFFSET:codec.FINAL_OFFSET+360]);header=codec.FINAL_HEADER.unpack(record[:24])
                assert header[:4]==(codec.FINAL_MAGIC,1,360,count-1) and header[4]>0
                assert record[248:]==bytes(shared[codec.handoff_codec.HEADER_OFFSET:codec.handoff_codec.HEADER_OFFSET+112])
                raw=bytes(peer[codec.handoff_codec.HIDDEN_OFFSET:codec.handoff_codec.HIDDEN_OFFSET+16]);assert raw==bytes(shared[base.SLOT:base.SLOT+16])
                parent=wire.ROW_META.unpack(record[24:248]);assert parent[5]==row.parent and parent[7]+1==pos and parent[19]==row.before
                first=(token+pos*7)%97 if fixture else -1;second=(first+(pos+1)*7)%97 if fixture else -1
                batch=codec.PROPOSAL.pack(0x44525032,1,192,2+fixture,0,seq,row.identity,row.parent,header[4],serial,
                       pos,pos,2,2 if fixture else 0,first,second,0,1,row.request,row.after,sha256(raw).digest())
                shared[codec.PROPOSAL_OFFSET:codec.PROPOSAL_OFFSET+192]=batch;output,extent=first,192
                state['provider']=(serial,row.identity,token,bytes(batch));state.setdefault('borrows',[]).append((pos,len(model.ring.pending)))
            else:
                assert fixture==row.fixture
                source=None
                if op==ring.ROW and index:
                    raw=bytes(shared[base.SLOT:base.SLOT+16]);source=ring.Publication(row,index-1,m[13],raw,m[20])
                command=ring.Command(index,op,seq,row,bool(m[3]),0 if op==ring.ROW else spec,source)
                provider_before=state.get('provider');ack=model.execute(command)
                if op==ring.ACCEPT:state['accepted']=command
                if op==ring.ABORT_SUFFIX:
                    assert state.get('provider')==provider_before
                    state.setdefault('survivals',[]).append((serial,ack.discarded))
                if op==ring.ROW:
                    output=ack.token if final and fixture else -1;extent=0 if final else 16;raw=b'' if final else bytes(ack.stream)
                    if raw:shared[:16]=raw
                    publication=list(m);publication[3]|=2;publication[14],publication[15],publication[20]=seq,extent,sha256(raw).digest()
                    shared[wire.ROW_OFFSET:wire.ROW_OFFSET+224]=wire.ROW_META.pack(*publication)
                    if final:
                        if state.get('force_final_position')==pos:output=state['force_final_token']
                        shared[codec.FINAL_OFFSET+16:codec.FINAL_OFFSET+24]=bytes(8);final_tokens[row.identity]=output
                else:
                    assert op in (ring.ACCEPT,ring.ABORT_SUFFIX)
                    shared[wire.ACK_OFFSET:wire.ACK_OFFSET+128]=wire.ACK_META.pack(0x5241434b,1,128,int(op==ring.ABORT_SUFFIX),0,row.identity,*(ack.discarded+(0,0))[:2],index,seq,spec,ack.physical,ack.committed,len(ack.discarded),ack.pending,0,bytes(48))
                    if final:
                        raw=hidden(token,pos,index)
                        handoff=codec.handoff_codec.HEADER.pack(codec.handoff_codec.MAGIC,1,16,pos,index,count,spec,seq,token,
                              final_tokens[row.identity] if fixture else -1,int(fixture>0),0,sha256(raw).hexdigest().encode())
                        parent=list(m);parent[14]=spec
                        record=codec.FINAL_HEADER.pack(codec.FINAL_MAGIC,1,360,index,seq)+wire.ROW_META.pack(*parent)+handoff
                        shared[codec.handoff_codec.HIDDEN_OFFSET:codec.handoff_codec.HIDDEN_OFFSET+16]=raw
                        shared[codec.FINAL_OFFSET:codec.FINAL_OFFSET+360]=record
            reply=base.REPLY.pack(0,output,0,extent,seq,0 if index==0 else 1,index,final,0.1,0,0,0)
            sock.sendall(reply[:7]);time.sleep(0.00001);sock.sendall(reply[7:])
    except Exception as error:errors.append(repr(error))
    finally:sock.close()

class PendingTests(unittest.TestCase):
    def test_pending_codec_preserves_original_tentative_only_after_actual_accept(self):
        _,_,_,canonical=final_fixture();seed=replace(canonical.seed,tentative=True)
        command=pending.pending_codec.PendingProviderCommand(canonical.sequence,seed,canonical.parent,canonical.serial,
                    accepted_sequence=4,target_physical=3,target_committed=2,pending_rows=(3,))
        raw=pending.pending_codec.seed_metadata(command,accepted_row=seed,accepted_sequence=4,stream_bytes=16)
        self.assertEqual(wire.ROW_META.unpack(raw)[3],1)
        with self.assertRaises(ValueError):codec.seed_metadata(command,stream_bytes=16)
        for changed in (replace(command,accepted_sequence=3),replace(command,pending_rows=(3,3)),replace(command,target_physical=2)):
            with self.assertRaises(ValueError):pending.pending_codec.seed_metadata(changed,accepted_row=seed,accepted_sequence=4,stream_bytes=16)
        with self.assertRaises(ValueError):pending.pending_codec.seed_metadata(command,accepted_row=replace(seed,tentative=False),accepted_sequence=4,stream_bytes=16)

    def test_two_slot_then_older_accept_one_slot_actual_truth_two_four_six(self):
        for count in (2,4,6):
            with self.subTest(count=count),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);prompt=[3,5,8,11];inputs,outputs=reference(prompt,12,(96,))
                ref=root/'reference.json';ref.write_text(json.dumps(reference_rows(prompt,outputs,count)))
                output=root/'output';output.mkdir()
                plan=dict(prompt_tokens=prompt,max_new=12,context=128,vocab=97,model_identity_sha256='a'*64,
                    eos_token_ids=[96],request_sha256=sha256(b'fixture').hexdigest(),recursive_reference=str(ref),verify_restore=True,
                    pending_cases=[{'kind':'two-row-abort','seed_position':6},{'kind':'accept-then-one-row-abort','seed_position':7}],
                    expected_pending_borrows={'1':1,'2':2})
                guard=Guard();stages=[];threads=[];states=[];errors=[];memories=[bytearray(base.SHARED) for _ in range(count)]
                try:
                    for i in range(count):
                        s=pending.PendingStage.__new__(pending.PendingStage);s.sock,peer=socket.socketpair();s.shared=memories[i];s.stream_bytes=16;s.sequence=0
                        s.spec=dict(id=i,first=i==0,final=i==count-1);s.guard=guard;s.plan=plan;state={}
                        t=threading.Thread(target=worker,args=(peer,s.shared,memories,i,count,prompt,state,errors),daemon=True)
                        stages.append(s);states.append(state);threads.append(t);t.start()
                    result=pending.drive(stages,plan,guard,output)
                    self.assertFalse(errors);self.assertEqual(result['output_ids'],outputs)
                    self.assertEqual(result['provider_pairs'],len(inputs)-1)
                    self.assertEqual([(p,n) for p,n in states[0]['borrows'] if n],[(6,2),(7,2),(8,1)])
                    self.assertEqual([(p,len(ids)) for p,ids in states[0]['survivals']],[(6,2),(8,1)])
                    for state in states:self.assertEqual(state['worker'].ring.physical['history'],inputs)
                    pairs=[json.loads(x) for x in (output/'provider-batches.jsonl').read_text().splitlines()]
                    accepted=[p for p in pairs if p['original_seed_tentative']]
                    self.assertEqual([p['seed_position'] for p in accepted],[8])
                    self.assertEqual(accepted[0]['pending_depth'],1)
                    events=[json.loads(x) for x in (output/'schedule.jsonl').read_text().splitlines()]
                    aborts=[e for e in events if e['event']=='target-verified-suffix-abort']
                    self.assertTrue(all(e['actual_target_token']!=e['rejected_token'] for e in aborts))
                    old=[e for e in events if e['event']=='older-accepted-with-one-pending'][0]
                    self.assertEqual(old['physical'],old['committed']+1)
                finally:
                    for s in stages:s.sock.close()
                    for t in threads:t.join(timeout=2)

    def test_scripted_wrong_input_must_actually_be_rejected_before_abort(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);prompt=[3,5,8,11];inputs,outputs=reference(prompt,12,(96,))
            ref=root/'reference.json';ref.write_text(json.dumps(reference_rows(prompt,outputs,2)))
            out=root/'output';out.mkdir()
            plan=dict(prompt_tokens=prompt,max_new=12,context=128,vocab=97,model_identity_sha256='a'*64,
                eos_token_ids=[96],request_sha256=sha256(b'fixture').hexdigest(),recursive_reference=str(ref),verify_restore=True,
                pending_cases=[{'kind':'two-row-abort','seed_position':6},{'kind':'accept-then-one-row-abort','seed_position':7}],
                expected_pending_borrows={'1':1,'2':2})
            guard=Guard();stages=[];threads=[];states=[];errors=[];memories=[bytearray(base.SHARED) for _ in range(2)]
            try:
                for i in range(2):
                    stage=pending.PendingStage.__new__(pending.PendingStage);stage.sock,peer=socket.socketpair()
                    stage.shared=memories[i];stage.stream_bytes=16;stage.sequence=0;stage.spec=dict(id=i,first=i==0,final=i==1)
                    stage.guard=guard;stage.plan=plan
                    state={} if i==0 else {'force_final_position':6,'force_final_token':(inputs[7]+1)%97}
                    thread=threading.Thread(target=worker,args=(peer,stage.shared,memories,i,2,prompt,state,errors),daemon=True)
                    stages.append(stage);states.append(state);threads.append(thread);thread.start()
                with self.assertRaisesRegex(ValueError,'actual target must reject'):
                    pending.drive(stages,plan,guard,out)
                self.assertFalse(errors)
                self.assertEqual(len(states[0]['worker'].ring.pending),2)
                self.assertNotIn('survivals',states[0])
                self.assertFalse((out/'pending-provider-coverage.json').exists())
            finally:
                for stage in stages:stage.sock.close()
                for thread in threads:thread.join(timeout=2)

    def test_plan_distinct_flags_request_and_capabilities(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);receipt=root/'receipt.json';config=root/'config.json'
            caps=['pipeline/recursive_provider/'+n for n in ('pending_survival.inc','survival_identity.hpp','survival_writer.inc')]
            receipt.write_text(json.dumps({'sources':dict.fromkeys(caps,'fixture')}))
            config.write_text(json.dumps(dict(pending_provider_gate=True,build_receipt=str(receipt),pending_cases=[
                {'kind':'two-row-abort','seed_position':6},{'kind':'accept-then-one-row-abort','seed_position':7}])))
            def baseline(_):return dict(prompt_tokens=[3,5,8,11],max_new=12,request_sha256='a'*64,pins={},
                stages=[dict(first=i==0,argv=['--pipeline-ring-request-sha256','a'*64]) for i in range(4)])
            with patch.object(pending.live,'make_plan',side_effect=baseline):plan=pending.make_plan(config)
            self.assertNotEqual(plan['request_sha256'],'a'*64)
            self.assertEqual(plan['expected_pending_borrows'],{'1':1,'2':2})
            for s in plan['stages']:
                self.assertIn('--pipeline-ring-pending-provider',s['argv'])
                self.assertIn('--pipeline-ring-verify-restore',s['argv'])
                self.assertEqual('--pipeline-ring-verify-provider-survival' in s['argv'],s['first'])
            receipt.write_text('{"sources":{}}')
            with patch.object(pending.live,'make_plan',side_effect=baseline),self.assertRaisesRegex(ValueError,'survival capability'):
                pending.make_plan(config)

if __name__=='__main__':unittest.main()
