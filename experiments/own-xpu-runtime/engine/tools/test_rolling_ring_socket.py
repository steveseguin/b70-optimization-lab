from hashlib import sha256
import socket
import json
import tempfile
from pathlib import Path
import threading
import time
import unittest

from rolling_ring_driver import bridge
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
                assert index==state.get('provider_stage',0) and spec==2 and model.ring.committed in ((pos+1,) if index==0 else (pos,pos+1)) and all(p.ticket.tentative for p in model.ring.pending)
                accepted=state['all_states'][0]['accepted'];assert accepted.row==row and accepted.tentative==bool(m[3]);assert seq==model.sequence+1;model.sequence=seq;serial+=1;assert fixture==int(row.fixture>0) and pos==serial
                state['provider_inflight']=True
                if not state.get('capture_ready'):time.sleep(state.get('provider_delay',0))
                peer=mappings[-1];record=bytes(peer[codec.FINAL_OFFSET:codec.FINAL_OFFSET+360]);header=codec.FINAL_HEADER.unpack(record[:24])
                assert header[:4]==(codec.FINAL_MAGIC,1,360,count-1) and header[4]>0
                assert record[248:]==bytes(shared[codec.handoff_codec.HEADER_OFFSET:codec.handoff_codec.HEADER_OFFSET+112])
                raw=bytes(peer[codec.handoff_codec.HIDDEN_OFFSET:codec.handoff_codec.HIDDEN_OFFSET+16]);assert raw==bytes(shared[base.SLOT:base.SLOT+16])
                parent=wire.ROW_META.unpack(record[24:248]);assert parent[5]==row.parent and parent[7]+1==pos and parent[19]==row.before
                if state.get('capture_ready'):
                    from rolling_provider import capture_ready as cr
                    ready=base.REPLY.pack(cr.STATUS,-1,0,128,seq,int(index!=0),index,0,0.01,0,0,0)
                    identity=cr.CAPTURE.pack(cr.MAGIC,1,128,row.epoch,seq,row.identity,row.parent,
                        header[4],serial,row.request,sha256(record).digest())
                    if state.get('bad_capture_identity'):identity=identity[:-1]+bytes([identity[-1]^1])
                    packet=ready+identity
                    # Split both the fixed header and its identity body.
                    for begin,end in (() if state.get('skip_capture') else (((0,len(packet)),) if state.get('coalesced_capture') else ((0,7),(7,70),(70,151),(151,len(packet))))):
                        sock.sendall(packet[begin:end]);time.sleep(0.00001)
                    if state.get('duplicate_capture'):sock.sendall(packet)
                    time.sleep(state.get('provider_delay',0.004))
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
                if op==ring.ACCEPT:
                    if index==0 and state.get('provider_stage',0):
                        assert not state['all_states'][state['provider_stage']].get('provider_inflight',False), 'stage0 ACCEPT overwrote live provider seed'
                    state['accepted']=command
                    if index==0 and state.get('provider_stage',0):
                        from rolling_provider.remote import SEED_OFFSET,SEED_HEADER
                        fields=list(m);fields[14]=spec
                        shared[SEED_OFFSET:SEED_OFFSET+256]=SEED_HEADER.pack(0x52534331,1,256,0,seq,ack.physical,ack.committed)+wire.ROW_META.pack(*fields)
                    if final and state.get('provider_state'):
                        assert not state['provider_state'].get('provider_inflight',False), 'final ACCEPT replaced live provider parent'
                if op==ring.ABORT_SUFFIX:
                    assert state.get('provider')==provider_before
                    state.setdefault('survivals',[]).append((serial,ack.discarded))
                if op==ring.ROW:
                    output=ack.token if final and fixture else -1;extent=0 if final else 16;raw=b'' if final else bytes(ack.stream)
                    if raw:shared[:16]=raw
                    publication=list(m);publication[3]|=2;publication[14],publication[15],publication[20]=seq,extent,sha256(raw).digest()
                    shared[wire.ROW_OFFSET:wire.ROW_OFFSET+224]=wire.ROW_META.pack(*publication)
                    if final:
                        if state.get('provider_state',{}).get('provider_inflight',False):
                            state['overlapped_rows']=state.get('overlapped_rows',0)+1
                        if state.get('overwrite_hidden'):
                            shared[codec.handoff_codec.HIDDEN_OFFSET:codec.handoff_codec.HIDDEN_OFFSET+16]=b'Z'*16
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
            if op==27 and state.get('capture_ready'):state['provider_inflight']=False
            reply=base.REPLY.pack(0,output,0,extent,seq,0 if index==0 else 1,index,final,0.1,0,0,0)
            sock.sendall(reply[:7]);time.sleep(state.get('fragment_delay',0.00001))
            if op==27 and state.get('truncate_provider'):break
            sock.sendall(reply[7:])
            if op==27:state['provider_inflight']=False
    except Exception as error:errors.append(repr(error))
    finally:sock.close()


def exercise(count, *, maximum=16, first_options=None, final_options=None, cancel=False, wire_seed=500, provider_stage=0):
    prompt=[3,5,8,11]
    plan=dict(rolling_depth2=True,use_proposals=True,prompt_tokens=prompt,max_new=maximum,
        context=128,vocab=97,eos_token_ids=[96],request_sha256=sha256(b'rolling-wire').hexdigest(),verify_restore=True)
    if (first_options or {}).get('capture_ready'):plan['capture_ready_overlap']=True
    if provider_stage:plan['provider_stage']=provider_stage
    plan['stages']=[dict(id=i) for i in range(count)]
    stages=[];threads=[];states=[];errors=[];mappings=[bytearray(base.SHARED) for _ in range(count)]
    guard=Guard()
    with tempfile.TemporaryDirectory() as temporary:
        output=Path(temporary)
        try:
            for i in range(count):
                stage=bridge.Stage.__new__(bridge.Stage);stage.sock,peer=socket.socketpair();stage.shared=mappings[i]
                stage.sequence=wire_seed;stage.stream_bytes=16;stage.spec=dict(id=i,first=i==0,final=i==count-1)
                stage.guard=guard;stage.plan=plan
                state=dict(wire=wire_seed,fragment_delay=0.00002*(count-i),provider_stage=provider_stage,all_states=states)
                if i==provider_stage:state.update(first_options or {})
                if i==count-1:
                    state.update(final_options or {})
                    if plan.get('capture_ready_overlap'):state['provider_state']=states[provider_stage]
                thread=threading.Thread(target=worker,args=(peer,stage.shared,mappings,i,count,prompt,state,errors),daemon=True)
                stages.append(stage);threads.append(thread);states.append(state);thread.start()
            stop=(lambda:states[provider_stage].get('provider_inflight',False) and len(states[provider_stage].get('borrows',[]))>=3) if cancel else None
            result=bridge.drive(stages,plan,guard,output,stop_requested=stop)
            assert not errors,errors
            import json
            result['logged_events']=[json.loads(line) for line in (output/'schedule.jsonl').read_text().splitlines()]
            result['batches']=[json.loads(line) for line in (output/'provider-batches.jsonl').read_text().splitlines()]
            result['records']=[json.loads(line) for line in (output/'final-records.jsonl').read_text().splitlines()]
            result['commands']=[json.loads(line) for line in (output/'commands.jsonl').read_text().splitlines()]
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
                outstanding={};seen=set()
                for item in result['commands']:
                    key=(item['stage'],item['sequence'])
                    self.assertEqual(item['schema'],'ownrt.rolling-command.v1')
                    if item['event']=='issued':
                        self.assertNotIn(item['stage'],outstanding)
                        self.assertNotIn(key,seen);seen.add(key);outstanding[item['stage']]=item
                        request=base.REQUEST.unpack(bytes.fromhex(item['request_hex']))
                        self.assertEqual((request[0],request[5],request[6]),(item['op'],item['sequence'],item['stage']))
                        self.assertEqual(len(bytes.fromhex(item['metadata_hex'])),224)
                    else:
                        original=outstanding.pop(item['stage'])
                        self.assertEqual((item['sequence'],item['row'],item['tentative'],item['row_ticket']),
                            (original['sequence'],original['row'],original['tentative'],original['row_ticket']))
                        reply=base.REPLY.unpack(bytes.fromhex(item['reply_hex']))
                        self.assertEqual((reply[4],reply[6]),(item['sequence'],item['stage']))
                        if item['op']==27:
                            raw=bytes.fromhex(item['metadata_hex']);batch=item['provider']
                            self.assertEqual(len(raw),192)
                            self.assertEqual(sha256(raw).hexdigest(),batch['proposal_sha256'])
                            self.assertEqual(raw.hex(),batch['proposal_hex'])
                            self.assertEqual(sha256(bytes.fromhex(item['reply_hex'])).hexdigest(),batch['reply_sha256'])
                self.assertFalse(outstanding)

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
            bridge.drive([],dict(rolling_depth2=True,use_proposals=True,recursive_reference='/unused'),Guard(),Path(tmp))



class CaptureReadySocketTests(unittest.TestCase):
    def test_fragmented_capture_overlap_owned_hidden_misses_and_accept_fence(self):
        for count in (2,4,6):
            with self.subTest(stages=count):
                result,states=exercise(count,first_options=dict(capture_ready=True,
                    provider_delay=.006,miss_first=(5,9),miss_second=(7,11),coalesced_capture=count==2),
                    final_options=dict(overwrite_hidden=True))
                self.assertGreater(states[-1].get('overlapped_rows',0),0)
                self.assertEqual(result['output_ids'],reference([3,5,8,11],16,[96])[1])
                self.assertTrue(any(x['event']=='parent-captured' for x in result['commands']))

    def test_capture_cancel_drains_provider_before_final_accept(self):
        result,states=exercise(4,cancel=True,first_options=dict(capture_ready=True,provider_delay=.008),
            final_options=dict(overwrite_hidden=True))
        self.assertTrue(result['cancelled'])
        for state in states:self.assertFalse(state['worker'].ring.pending)

    def test_capture_identity_and_duplicate_refused(self):
        for flag in ('bad_capture_identity','duplicate_capture','skip_capture'):
            with self.subTest(flag=flag),self.assertRaises(ValueError):
                exercise(4,first_options=dict(capture_ready=True,provider_delay=.004,**{flag:True}))

if __name__=='__main__':unittest.main()
