from hashlib import sha256
import json
from pathlib import Path
import socket
import struct
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import ring_live_driver as live
from test_ring_coordinator import Worker,reference
from test_wavefront_driver import Guard,exact
from test_ring_live_wire import final_fixture
base,codec,wire,ring=live.base,live.codec,live.wire,live.ring

def hidden(token,pos,final):return struct.pack('<4i',token,pos,final,42)

def reference_rows(prompt,outputs,count):
    inputs=prompt+outputs[:-1];pairs=[];depths=[]
    for p in range(1,len(inputs)):
        head=p>=len(prompt)-1;first=(inputs[p]+p*7)%97 if head else -1;digest=sha256(hidden(inputs[p-1],p-1,count-1)).hexdigest()
        pairs.append(dict(position=p,token=inputs[p],head=head,proposal=first,hidden_sha256=digest))
        if head:depths.append(dict(seed_position=p,confirmed_token=inputs[p],raw_hidden_sha256=digest,guesses=[first,(first+(p+1)*7)%97]))
    return dict(schema='ownrt.recursive-provider-reference.v1',passed=True,prompt_tokens=len(prompt),output_tokens=len(outputs),
        target_prompt_token_sha256=sha256(json.dumps(prompt,separators=(',',':')).encode()).hexdigest(),target_output_ids=outputs,
        canonical_draft_input_identity=dict(model_sha256='a'*64,context=128,vocab=97,arithmetic='F32-target/BF16-draft',draft_experts='fp8'),
        canonical_pairs=pairs,canonical_true_pairs=len(pairs),canonical_draft_position=len(pairs),head_pairs=len(depths),depth2_rows=depths,
        expected_recursive_captures=len(depths),expected_recursive_restores=len(depths))

def worker(sock,shared,mappings,index,count,prompt,state,errors):
    model=Worker(index,count,0,prompt);state['worker']=model;serial=0;final_tokens={}
    try:
        while (packet:=exact(sock,base.REQUEST.size)) is not None:
            op,token,pos,fixture,spec,seq,stage,final=base.REQUEST.unpack(packet)
            assert stage==index and final==int(index==count-1)
            m=wire.ROW_META.unpack(bytes(shared[wire.ROW_OFFSET:wire.ROW_OFFSET+224]))
            row=ring.Row(m[4],m[5],m[6],m[7],m[8],m[9],m[17],m[18],m[19]);assert row.token==token and row.position==pos and not m[3]
            output=extent=0
            if op==27:
                assert index==0 and spec==2 and not model.ring.pending and model.ring.committed==pos+1
                assert seq==model.sequence+1;model.sequence=seq;serial+=1;assert fixture==int(row.fixture>0) and pos==serial
                peer=mappings[-1];record=bytes(peer[codec.FINAL_OFFSET:codec.FINAL_OFFSET+360]);header=codec.FINAL_HEADER.unpack(record[:24])
                assert header[:4]==(codec.FINAL_MAGIC,1,360,count-1) and header[4]>0
                assert record[248:]==bytes(shared[codec.handoff_codec.HEADER_OFFSET:codec.handoff_codec.HEADER_OFFSET+112])
                raw=bytes(peer[codec.handoff_codec.HIDDEN_OFFSET:codec.handoff_codec.HIDDEN_OFFSET+16]);assert raw==bytes(shared[base.SLOT:base.SLOT+16])
                parent=wire.ROW_META.unpack(record[24:248]);assert parent[5]==row.parent and parent[7]+1==pos and parent[19]==row.before
                first=(token+pos*7)%97 if fixture else -1;second=(first+(pos+1)*7)%97 if fixture else -1
                batch=codec.PROPOSAL.pack(0x44525032,1,192,2+fixture,0,seq,row.identity,row.parent,header[4],serial,
                       pos,pos,2,2 if fixture else 0,first,second,0,1,row.request,row.after,sha256(raw).digest())
                shared[codec.PROPOSAL_OFFSET:codec.PROPOSAL_OFFSET+192]=batch;output,extent=first,192
            else:
                assert fixture==row.fixture
                source=None
                if op==ring.ROW and index:
                    raw=bytes(shared[base.SLOT:base.SLOT+16]);source=ring.Publication(row,index-1,m[13],raw,m[20])
                command=ring.Command(index,op,seq,row,False,0 if op==ring.ROW else spec,source);ack=model.execute(command)
                if op==ring.ROW:
                    output=ack.token if final and fixture else -1;extent=0 if final else 16;raw=b'' if final else bytes(ack.stream)
                    if raw:shared[:16]=raw
                    publication=list(m);publication[3]|=2;publication[14],publication[15],publication[20]=seq,extent,sha256(raw).digest()
                    shared[wire.ROW_OFFSET:wire.ROW_OFFSET+224]=wire.ROW_META.pack(*publication)
                    if final:shared[codec.FINAL_OFFSET+16:codec.FINAL_OFFSET+24]=bytes(8);final_tokens[row.identity]=output
                else:
                    assert op==ring.ACCEPT
                    shared[wire.ACK_OFFSET:wire.ACK_OFFSET+128]=wire.ACK_META.pack(0x5241434b,1,128,0,0,row.identity,0,0,index,seq,spec,ack.physical,ack.committed,0,ack.pending,0,bytes(48))
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

class LiveDriverTests(unittest.TestCase):
    def test_existing_guarded_lifecycle_injected_and_truthful_result_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp);plan={'output':tmp}
            def execute(plan,admission,unit,**kwargs):
                self.assertIs(kwargs['stage_type'],live.LiveStage)
                self.assertIs(kwargs['driver'],live.drive)
                self.assertFalse(kwargs['scripted_proposals'])
                base.save(output/'plan.json',plan)
                base.save(output/'result.json',{'passed':True,'mode':'verified-wavefront'})
            with patch.object(live.target.lifecycle,'execute',side_effect=execute):live.execute(plan,{},'fixture')
            result=json.loads((output/'ring-live-result.json').read_text())
            self.assertEqual(result['mode'],'quiescent-ring-live-depth2')
            self.assertTrue(result['actual_provider']);self.assertFalse(result['speculative_target_use'])
            self.assertEqual(result['lifecycle_result_sha256'],base.digest(output/'result.json'))
            self.assertEqual(result['plan_sha256'],base.digest(output/'plan.json'))

    def test_provider_rejects_wrong_reply_owner_or_truncated_reply_before_retirement(self):
        for truncated in (False, True):
            stage=live.LiveStage.__new__(live.LiveStage);stage.sock,peer=socket.socketpair()
            stage.guard=Guard();stage.spec=dict(id=0,first=True,final=False);stage.sequence=4
            stage.shared=bytearray(base.SHARED);stage.stream_bytes=16;stage.plan=dict(vocab=97,context=64)
            stage.start_async();stage.physical=stage.committed=2
            _,_,_,command=final_fixture()
            try:
                stage.issue_provider(command);stage.write_ready();request=base.REQUEST.unpack(exact(peer,base.REQUEST.size))
                self.assertEqual(request,(27,11,1,1,2,5,0,0))
                reply=base.REPLY.pack(0,18,0,192,5,0,1,0,0,0,0,0)
                if truncated:
                    peer.sendall(reply[:7]);peer.shutdown(socket.SHUT_WR)
                    self.assertIsNone(stage.read_ready())
                    with self.assertRaisesRegex(ValueError,'channel closed'):stage.read_ready()
                else:
                    peer.sendall(reply)
                    with self.assertRaisesRegex(ValueError,'wire owner identity'):stage.read_ready()
                self.assertEqual(stage.provider_serial,0);self.assertIs(stage.command_pending,command)
            finally:stage.sock.close();peer.close()

    def test_plan_binds_draft_manifest_and_rejects_other_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);prompt=[3,5,8,11];_,outputs=reference(prompt,12,(96,))
            manifest=root/'draft.tsv';manifest.write_text('authenticated fixture')
            ref=reference_rows(prompt,outputs,4)
            ref['canonical_draft_input_identity']['draft_model_sha256']=base.digest(manifest)
            reference_path=root/'reference.json';reference_path.write_text(json.dumps(ref))
            adapter=root/'adapter.json';adapter.write_text(json.dumps({'rank_argv':[['--draft-mtp','--draft-fault','none',
                '--draft-manifest',str(manifest),'--draft-model','/fixture','--draft-experts','fp8']]}))
            capabilities=['pipeline/ring/'+n+'.hpp' for n in ('stage_ring','wire','checkpoint_ring','engine_backend','dispatcher')]
            capabilities+=['pipeline/recursive_provider/'+n for n in ('batch.hpp','draft_runtime_extension.inc','final_event.hpp','peer.hpp')]
            capabilities+=['pipeline/live_draft.hpp','pipeline/operator_state.hpp']
            receipt=root/'receipt.json';receipt.write_text(json.dumps({'sources':dict.fromkeys(capabilities,'fixture')}))
            config=root/'config.json';config.write_text(json.dumps(dict(ring_live_draft=True,recursive_reference=str(reference_path),
                build_receipt=str(receipt),adapter_plan=str(adapter),eos_token_ids=[96])))
            def base_plan():return dict(prompt_tokens=prompt,max_new=12,context=128,vocab=97,model_identity_sha256='a'*64,
                eos=96,pins={},output=str(root/'run'),stages=[dict(id=i,first=i==0,final=i==3,argv=[],environment={}) for i in range(4)])
            with patch.object(base,'make_plan',side_effect=lambda _:base_plan()):plan=live.make_plan(config)
            self.assertFalse(plan['use_proposals']);self.assertFalse(plan['draft_training'])
            self.assertEqual(plan['draft_model_sha256'],base.digest(manifest))
            for s in plan['stages']:
                self.assertEqual('--draft-mtp' in s['argv'],s['first'])
                self.assertEqual('--pipeline-ring-final-shared' in s['argv'],s['first'])
                self.assertNotIn('OWNRT_DRAFT_DEPTH_PROBE',s['environment'])
            manifest.write_text('different draft')
            with patch.object(base,'make_plan',side_effect=lambda _:base_plan()),self.assertRaisesRegex(ValueError,'draft manifest identity'):
                live.make_plan(config)
    def test_real_sockets_actual_provider_two_four_six_and_no_target_speculation(self):
        for count in (2,4,6):
            with self.subTest(count=count),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);prompt=[3,5,8,11];inputs,outputs=reference(prompt,12,(96,));ref=root/'reference.json';ref.write_text(json.dumps(reference_rows(prompt,outputs,count)))
                output=root/'output';output.mkdir();plan=dict(prompt_tokens=prompt,max_new=12,context=128,vocab=97,model_identity_sha256='a'*64,
                    eos_token_ids=[96],request_sha256=sha256(b'fixture').hexdigest(),recursive_reference=str(ref),verify_restore=False)
                guard=Guard();stages=[];threads=[];states=[];errors=[];memories=[bytearray(base.SHARED) for _ in range(count)]
                try:
                    for i in range(count):
                        s=live.LiveStage.__new__(live.LiveStage);s.sock,peer=socket.socketpair();s.shared=memories[i];s.stream_bytes=16;s.sequence=0
                        s.spec=dict(id=i,first=i==0,final=i==count-1);s.guard=guard;s.plan=plan;state={}
                        t=threading.Thread(target=worker,args=(peer,s.shared,memories,i,count,prompt,state,errors),daemon=True)
                        stages.append(s);states.append(state);threads.append(t);t.start()
                    result=live.drive(stages,plan,guard,output);self.assertFalse(errors);self.assertEqual(result['output_ids'],outputs)
                    self.assertEqual(result['provider_pairs'],len(inputs)-1);self.assertEqual(result['recursive_head_pairs'],len(outputs))
                    for state in states:self.assertEqual(state['worker'].ring.physical['history'],inputs)
                    rows=[json.loads(x) for x in (output/'provider-batches.jsonl').read_text().splitlines()]
                    self.assertEqual(len(rows),len(inputs)-1);self.assertTrue(all(not p['speculative_target_use'] for p in rows))
                    self.assertTrue(any(p['guesses'][0]!=outputs[p['seed_position']-len(prompt)+1] for p in rows if p['guesses']))
                finally:
                    for s in stages:s.sock.close()
                    for t in threads:t.join(timeout=2)
    def test_reference_prompt_geometry_rejections(self):
        prompt=[3,5,8,11];_,outputs=reference(prompt,12,(96,));r=reference_rows(prompt,outputs,4)
        plan=dict(prompt_tokens=prompt,max_new=12,model_identity_sha256='a'*64,context=128,vocab=97);live.validate_reference(r,plan)
        for key,value in [('context',4096),('max_new',13),('prompt_tokens',[4,5,8,11]),('model_identity_sha256','b'*64)]:
            bad=dict(plan);bad[key]=value
            with self.assertRaises(ValueError):live.validate_reference(r,bad)
        for field,value in [('token',96),('head',True),('hidden_sha256','broken')]:
            bad=json.loads(json.dumps(r));bad['canonical_pairs'][0][field]=value
            with self.assertRaises(ValueError):live.validate_reference(bad,plan)
        bad=json.loads(json.dumps(r));bad['depth2_rows'][0]['guesses'][0]^=1
        with self.assertRaises(ValueError):live.validate_reference(bad,plan)
    def test_bounded_json_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'large.json';p.write_bytes(b' '*1025)
            with self.assertRaises(ValueError):live.load_json(p,1024)
