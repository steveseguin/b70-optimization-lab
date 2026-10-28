from hashlib import sha256
import socket
import json
import tempfile
from pathlib import Path
import threading
import time
import unittest

import socket_bridge as bridge
from test_ring_coordinator import Worker,reference,target
from test_wavefront_driver import Guard,exact
from test_ring_live_driver import hidden
base,codec,ring=bridge.base,bridge.codec,bridge.ring
wire=bridge.pending.wire

def worker(sock,shared,mappings,index,count,prompt,state,errors):
    model=Worker(index,count,0,prompt,sequence=state.get("wire",0));state['worker']=model;serial=0;final_tokens={}
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
                state['provider_inflight']=True;time.sleep(state.get('provider_delay',0));peer=mappings[-1];record=bytes(peer[codec.FINAL_OFFSET:codec.FINAL_OFFSET+360]);header=codec.FINAL_HEADER.unpack(record[:24])
                assert header[:4]==(codec.FINAL_MAGIC,1,360,count-1) and header[4]>0
                assert record[248:]==bytes(shared[codec.handoff_codec.HEADER_OFFSET:codec.handoff_codec.HEADER_OFFSET+112])
                raw=bytes(peer[codec.handoff_codec.HIDDEN_OFFSET:codec.handoff_codec.HIDDEN_OFFSET+16]);assert raw==bytes(shared[base.SLOT:base.SLOT+16])
                parent=wire.ROW_META.unpack(record[24:248]);assert parent[5]==row.parent and parent[7]+1==pos and parent[19]==row.before
                first=(target(token,pos)+int(pos in state.get('miss_first',())))%97 if fixture else -1;second=(target(first,pos+1)+int(pos in state.get('miss_second',())))%97 if fixture else -1
                batch=codec.PROPOSAL.pack(0x44525032,1,192,2+fixture,0,seq,row.identity,row.parent,header[4],serial,
                       pos,pos,2,2 if fixture else 0,first,second,0,1,row.request,row.after,sha256(raw).digest())
                if state.get('bad_provider_serial'):
                    fields=list(codec.PROPOSAL.unpack(batch));fields[9]+=1;batch=codec.PROPOSAL.pack(*fields)
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
                        if state.get('bad_final_marker'):shared[codec.FINAL_OFFSET+16]^=1
            reply=base.REPLY.pack(0,output,0,extent,seq,0 if index==0 else 1,index,final,0.1,0,0,0)
            sock.sendall(reply[:7]);time.sleep(state.get('fragment_delay',0.00001))
            if op==27 and state.get('truncate_provider'):break
            sock.sendall(reply[7:])
            if op==27:state['provider_inflight']=False
    except Exception as error:errors.append(repr(error))
    finally:sock.close()


def exercise(count, *, maximum=16, first_options=None, final_options=None, cancel=False, wire_seed=500, trace_limit=None):
    prompt=[3,5,8,11]
    plan=dict(rolling_depth2_prototype=True,use_proposals=True,prompt_tokens=prompt,max_new=maximum,
        context=128,vocab=97,eos_token_ids=[96],request_sha256=sha256(b'rolling-wire').hexdigest(),verify_restore=True)
    if trace_limit is not None:plan['coordinator_trace_limit']=trace_limit
    stages=[];threads=[];states=[];errors=[];mappings=[bytearray(base.SHARED) for _ in range(count)]
    guard=Guard()
    with tempfile.TemporaryDirectory() as temporary:
        output=Path(temporary)
        try:
            for i in range(count):
                stage=bridge.Stage.__new__(bridge.Stage);stage.sock,peer=socket.socketpair();stage.shared=mappings[i]
                stage.sequence=wire_seed;stage.stream_bytes=16;stage.spec=dict(id=i,first=i==0,final=i==count-1)
                stage.guard=guard;stage.plan=plan
                state=dict(wire=wire_seed,fragment_delay=0.00002*(count-i))
                if i==0:state.update(first_options or {})
                if i==count-1:state.update(final_options or {})
                thread=threading.Thread(target=worker,args=(peer,stage.shared,mappings,i,count,prompt,state,errors),daemon=True)
                stages.append(stage);threads.append(thread);states.append(state);thread.start()
            stop=(lambda:states[0].get('provider_inflight',False) and len(states[0].get('borrows',[]))>=3) if cancel else None
            result=bridge.drive(stages,plan,guard,output,stop_requested=stop)
            assert not errors,errors
            import json
            result['logged_events']=[json.loads(line) for line in (output/'schedule.jsonl').read_text().splitlines()]
            result['batches']=[json.loads(line) for line in (output/'provider-batches.jsonl').read_text().splitlines()]
            result['records']=[json.loads(line) for line in (output/'final-records.jsonl').read_text().splitlines()]
            return result,states
        finally:
            for stage in stages:stage.sock.close()
            for thread in threads:thread.join(timeout=2)


class SocketBridgeTests(unittest.TestCase):
    def test_fragmented_actual_codecs_two_four_six_shared_wire_and_misses(self):
        for count in (2,4,6):
            with self.subTest(count=count):
                result,states=exercise(count,first_options=dict(miss_first=(3,9),miss_second=(6,11),provider_delay=0.0004))
                inputs,outputs=reference([3,5,8,11],16,(96,))
                self.assertEqual(result['output_ids'],outputs)
                self.assertEqual(result['provider_serial'],len(inputs)-1)
                self.assertFalse(result['cancelled'])
                for state in states:self.assertEqual(state['worker'].ring.physical['history'],inputs)
                self.assertTrue(states[0].get('survivals'))
                self.assertEqual({r['depth'] for r in result['rejected_proposals']},{1,2})
                self.assertTrue(all(batch['speculative_target_use'] for batch in result['batches']))
                self.assertTrue(all(batch['sequence']>500 for batch in result['batches']))
                records={r['row']:r for r in result['records']}
                for batch in result['batches']:
                    parent=records[batch['parent_row']]
                    self.assertEqual((batch['final_commit'],batch['parent_hidden_sha256']),(parent['sequence'],parent['hidden_sha256']))
                    raw=bytes.fromhex(parent['record_hex'])
                    self.assertEqual(len(raw),360)
                    self.assertEqual(sha256(raw).hexdigest(),parent['record_sha256'])
                model_events=[e for e in result['logged_events'] if e['event'] not in ('native-reply','issued-proposal')]
                self.assertEqual(model_events,json.loads(json.dumps(result['events'])))
                self.assertEqual(result['events'][-1]['event'],'drained')

    def test_measured_trace_is_bounded_with_exact_omissions_and_same_schedule(self):
        full,_=exercise(4,maximum=32)
        limit=20
        bounded,_=exercise(4,maximum=32,trace_limit=limit)
        logged=bounded['logged_events']
        self.assertLessEqual(len(logged),limit)
        summary=logged[-1]
        self.assertEqual(summary['event'],'coordinator-trace-summary')
        self.assertEqual(summary['retained'],len(logged)-1)
        self.assertEqual(summary['omitted'],bounded['coordinator_trace']['attempts']-summary['retained'])
        self.assertGreater(summary['omitted'],0)
        for key in ('output_ids','input_position','provider_serial','issued_proposals','rejected_proposals'):
            self.assertEqual(bounded[key],full[key],key)
        self.assertEqual(summary['retained'],bounded['coordinator_trace']['retained'])
        self.assertEqual(summary['omitted'],bounded['coordinator_trace']['omitted'])
        self.assertFalse(any(e['event']=='coordinator-trace-summary' for e in full['logged_events']))

    def test_cancel_while_fragmented_provider_reply_pending_drains_all_owners(self):
        for count in (2,4,6):
            result,states=exercise(count,cancel=True,first_options=dict(provider_delay=0.002,fragment_delay=0.0004))
            self.assertTrue(result['cancelled'])
            for state in states:
                self.assertFalse(state['worker'].ring.pending)
                self.assertEqual(state['worker'].ring.committed,result['input_position'])

    def test_bad_provider_serial_truncated_reply_and_final_marker_refused(self):
        for options,final,match in (({'bad_provider_serial':True},{},'provider batch'),
                                   ({'truncate_provider':True},{},'channel closed'),
                                   ({},{'bad_final_marker':True},'record header')):
            with self.subTest(options=options,final=final),self.assertRaisesRegex(ValueError,match):
                exercise(4,first_options=options,final_options=final)

    def test_oracle_configuration_refused_without_owner_or_socket_use(self):
        with tempfile.TemporaryDirectory() as tmp,self.assertRaisesRegex(ValueError,'no reference'):
            bridge.drive([],dict(rolling_depth2_prototype=True,use_proposals=True,recursive_reference='/unused'),Guard(),Path(tmp))

if __name__=='__main__':unittest.main()
