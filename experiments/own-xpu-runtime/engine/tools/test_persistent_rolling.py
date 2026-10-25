"""Real fragmented socket/codec cold-reset tests; no device/process creation."""
from hashlib import sha256
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import persistent_rolling_suite as suite
import persistent_rolling_driver as driver
from test_rolling_ring_socket import bridge,base,codec,ring,wire,Worker,reference,target,hidden,Guard,exact

def worker(sock,shared,mappings,index,count,prompt,state,errors):
    model=Worker(index,count,0,prompt,sequence=state.get("wire",0));state['worker']=model;serial=0;final_tokens={};epoch=0;request=state['request'];reset_index=0
    try:
        while (packet:=exact(sock,base.REQUEST.size)) is not None:
            op,token,pos,fixture,spec,seq,stage,final=base.REQUEST.unpack(packet)
            assert stage==index and final==int(index==count-1)
            if op in (4,5):
                assert seq==model.sequence+1;model.sequence=seq
                assert not model.ring.pending and model.ring.committed==model.ring.physical['position']
                if op==5:break
                state.setdefault('dumps',[]).append(dict(marker=pos,epoch=epoch,serial=serial,
                    history=list(model.ring.physical['history'])))
                sock.sendall(base.REPLY.pack(0,0,0,0,seq,0 if index==0 else 1,index,final,0,0,0,0))
                continue
            if op==11:
                assert token==pos==fixture==spec==0 and seq==model.sequence+1
                assert not model.ring.pending and model.ring.physical['position']==model.ring.committed
                path=state['native']/f'reset-{seq}.json';raw=path.read_bytes();d=json.loads(raw)
                assert d['schema']=='ownrt.ring-reset-request.v1' and d['previous_epoch']==epoch and d['next_epoch']==epoch+1
                assert d['previous_request_sha256']==request and d['stage_id']==index and d['global_sequence']==seq
                assert d['oracle']==''
                previous_position=model.ring.committed
                epoch=d['next_epoch'];request=d['next_request_sha256'];reset_index+=1
                model=Worker(index,count,epoch,state['prompts'][reset_index-1],sequence=seq);state['worker']=model
                serial=0;final_tokens={};state.pop('accepted',None);state.pop('provider',None)
                shared[:]=bytes(len(shared));destination=Path(d['destination']);destination.mkdir(parents=True)
                if state.get('stale_shared'):shared[codec.FINAL_OFFSET+16]=1
                receipt=dict(d,schema='ownrt.ring-reset.v1',passed=True,check_policy=state['policy'],
                    target_position=0,target_physical=0,target_committed=0,target_pending=0,
                    draft_position=0 if index==0 else None,provider_serial=0 if index==0 else None,
                    context_extent=32,alternate_extent=32,draft_context_extent=32 if index==0 else None,
                    pending_ticket=False,sticky_error=0,allocation_ids_preserved=True,counters_reset=True,
                    trace_reset=True,shared_publication_invalidated=True,reset_index=reset_index,
                    metadata_sha256=sha256(raw).hexdigest(),allocation_inventory_before_sha256='a'*64,
                    allocation_inventory_after_sha256='a'*64,previous_target_position=previous_position,
                    cold_state_byte_verified=False,provider_cold_host_sha256='c'*64 if index==0 else '',
                    provider_cold_sequence_sha256='d'*64 if index==0 else '')
                receipt.update(state.get('bad_reset_receipt',{}))
                if reset_index==2 and state.get('change_inventory'):
                    receipt['allocation_inventory_before_sha256']=receipt['allocation_inventory_after_sha256']='b'*64
                (destination/'ring-reset.json').write_text(json.dumps(receipt))
                state.setdefault('resets',[]).append(receipt)
                packet=base.REPLY.pack(0,0,0,0,seq,0 if index==0 else 1,index,final,0,0,0,0)
                if state.get('bad_reset_sequence'):packet=base.REPLY.pack(0,0,0,0,seq+1,0 if index==0 else 1,index,final,0,0,0,0)
                sock.sendall(packet[:3]);time.sleep(.0001)
                if state.get('truncate_reset'):break
                sock.sendall(packet[3:]);continue
            assert state.get('resets'), 'no ROW before cold reset'
            state.setdefault('issued_epochs',[]).append((epoch,seq,op))
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
                batch=codec.PROPOSAL.pack(0x44525032,1,192,2+fixture,epoch,seq,row.identity,row.parent,header[4],serial,
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
                    shared[wire.ACK_OFFSET:wire.ACK_OFFSET+128]=wire.ACK_META.pack(0x5241434b,1,128,int(op==ring.ABORT_SUFFIX and state['policy']=='qualification'),epoch,row.identity,*(ack.discarded+(0,0))[:2],index,seq,spec,ack.physical,ack.committed,len(ack.discarded),ack.pending,0,bytes(48))
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
    except Exception as error:
        import traceback
        errors.append(traceback.format_exc())
    finally:sock.close()


def exercise(count, *, policy='qualification', first_options=None, second_prompt=None, final_options=None,
             on_cleanup=None, eos=None):
    prompt=[3,5,8,11]
    requests=[dict(id='first',prompt_tokens=prompt,max_new=16),
              dict(id='second',prompt_tokens=second_prompt or prompt,max_new=16)]
    stages=[];threads=[];states=[];errors=[];mappings=[bytearray(base.SHARED) for _ in range(count)]
    guard=Guard();guard.obs=type('Observer',(),{'observe':lambda self:{}})()
    guard.validate=lambda *_:None
    with tempfile.TemporaryDirectory() as temporary:
        output=Path(temporary)
        eos=[96] if eos is None else eos
        inputs=dict(schema='ownrt.persistent-rolling-inputs.v1',model_identity_sha256='a'*64,
            activation_dtype='F32',eos_token_ids=eos,prompts=requests)
        path=output/'inputs.json';path.write_text(json.dumps(inputs))
        plan=dict(rolling_depth2=True,use_proposals=True,persistent_requests=True,
            prompt_tokens=prompt,max_new=16,context=128,vocab=97,eos_token_ids=eos,
            request_sha256=sha256(b'persistent-wire').hexdigest(),verify_restore=policy=='qualification',
            check_policy=policy,suite=str(path),suite_sha256=base.digest(path),suite_prompt_count=2,
            model_identity_sha256='a'*64,draft_model_sha256='b'*64,draft_experts='fp8',
            activation_dtype='F32',dump_each=True,seconds=10)
        try:
            for i in range(count):
                stage=bridge.Stage.__new__(bridge.Stage);stage.sock,peer=socket.socketpair();stage.shared=mappings[i]
                native=output/f'stage{i}/native';native.mkdir(parents=True)
                stage.sequence=500;stage.stream_bytes=16
                stage.spec=dict(id=i,first=i==0,final=i==count-1,native_output=str(native),
                    argv=['--pipeline-ring-persistent-requests'])
                stage.guard=guard;stage.plan=plan
                state=dict(wire=500,native=native,request=plan['request_sha256'],policy=policy,
                    fragment_delay=.00002*(count-i),prompts=[r['prompt_tokens'] for r in requests])
                if i==0:state.update(first_options or {})
                if i==count-1:state.update(final_options or {})
                thread=threading.Thread(target=worker,args=(peer,stage.shared,mappings,i,count,prompt,state,errors),daemon=True)
                stages.append(stage);threads.append(thread);states.append(state);thread.start()
            result=suite.run(stages,plan,guard,output)
            assert not errors,errors
            journals=[]
            for index,row in enumerate(requests):
                directory=output/f"request-{index:02d}-{row['id']}"
                journals.append({name:[json.loads(line) for line in (directory/name).read_text().splitlines()]
                    for name in ('reset-commands.jsonl','commands.jsonl','tokens.jsonl','provider-batches.jsonl')})
            return result,states,journals
        except Exception as error:
            if errors:raise RuntimeError('\n'.join(errors)) from error
            raise
        finally:
            for stage in stages:stage.sock.close()
            for thread in threads:thread.join(timeout=2)
            if on_cleanup:on_cleanup(states)


class PersistentSocketTests(unittest.TestCase):
    def test_two_real_fragmented_cold_requests_two_four_six_and_global_sequence(self):
        for count in (2,4,6):
            with self.subTest(count=count):
                result,states,journals=exercise(count,first_options=dict(miss_first=(3,9),miss_second=(6,11)))
                inputs,outputs=reference([3,5,8,11],16,(96,))
                self.assertEqual([r['output_ids'] for r in result['requests']],[outputs,outputs])
                self.assertNotEqual(*[r['request_sha256'] for r in result['requests']])
                self.assertEqual([r['epoch'] for r in result['requests']],[1,2])
                first,second=result['requests']
                self.assertEqual(second['previous_sequences'],first['post_dump_sequences'])
                self.assertEqual(second['initial_sequences'],[v+1 for v in first['post_dump_sequences']])
                for state in states:
                    self.assertEqual([r['next_epoch'] for r in state['resets']],[1,2])
                    self.assertEqual([d['history'] for d in state['dumps']],[inputs,inputs])
                    self.assertEqual(state['worker'].ring.physical['history'],inputs)
                self.assertEqual([d['serial'] for d in states[0]['dumps']],[len(inputs)-1]*2)
                for index,journal in enumerate(journals):
                    self.assertEqual(len(journal['reset-commands.jsonl']),2*count)
                    self.assertEqual({r['row']['epoch'] for r in journal['commands.jsonl']},{index+1})
                    self.assertEqual({r['row']['request'] for r in journal['commands.jsonl']},
                        {result['requests'][index]['request_sha256']})
                    self.assertTrue(all(r['sequence']>result['requests'][index]['initial_sequences'][r['stage']]
                        for r in journal['commands.jsonl']))
                self.assertEqual(result['cached_tokens'],0)
                self.assertFalse(result['speed_claim'])

    def test_different_second_prompt_and_measured_policy_preserve_target_answers(self):
        for count in (2,4,6):
            result,states,_=exercise(count,policy='measured',second_prompt=[7,2,14],
                first_options=dict(miss_first=(3,9),miss_second=(6,11)))
            inputs,outputs=reference([7,2,14],16,(96,))
            self.assertEqual(result['requests'][1]['output_ids'],outputs)
            self.assertEqual(states[0]['dumps'][1]['history'],inputs)
            self.assertFalse(result['diagnostic_only'])
            self.assertEqual({r['check_policy'] for s in states for r in s['resets']},{'measured'})

    def test_reset_corruption_or_truncation_never_reaches_target_row(self):
        for bad in ({'bad_reset_sequence':True},{'truncate_reset':True},
                    {'bad_reset_receipt':{'provider_serial':7}},
                    {'bad_reset_receipt':{'shared_publication_invalidated':False}},
                    {'bad_reset_receipt':{'metadata_sha256':'0'*64}},
                    {'bad_reset_receipt':{'allocation_inventory_after_sha256':'b'*64}},
                    {'bad_reset_receipt':{'check_policy':'measured'}},{'stale_shared':True}):
            retained=[]
            with self.subTest(bad=bad),self.assertRaises((ValueError,RuntimeError)):
                exercise(2,first_options=bad,on_cleanup=lambda states:retained.extend(states))
            self.assertTrue(retained)
            self.assertFalse(any(s.get('issued_epochs') for s in retained))

    def test_partial_all_owner_reset_failure_does_not_start_first_request(self):
        retained=[]
        with self.assertRaises(ValueError):
            exercise(4,final_options={'bad_reset_receipt':{'target_pending':1}},
                     on_cleanup=lambda states:retained.extend(states))
        self.assertTrue(all(len(s.get('resets',()))==1 for s in retained))
        self.assertFalse(any(s.get('issued_epochs') for s in retained))

    def test_reset_requires_empty_wire_and_both_target_frontiers(self):
        for values in ({'command_pending':object()},{'received':b'partial'},
                       {'transmit':b'unsent'},{'pending_rows':[object()]},
                       {'physical':4,'committed':3}):
            stage=type('Stage',(),values)()
            with self.subTest(values=values),self.assertRaisesRegex(ValueError,'reset|prompt'):
                suite.quiescent([stage])

    def test_cross_request_allocation_change_refused_before_new_row(self):
        retained=[]
        with self.assertRaisesRegex(ValueError,'between requests'):
            exercise(4,first_options={'change_inventory':True},on_cleanup=lambda s:retained.extend(s))
        self.assertTrue(all(len(s['resets'])==2 for s in retained))
        self.assertEqual({epoch for s in retained for epoch,_,_ in s['issued_epochs']},{1})

    def test_secondary_eos_single_output_drain_then_cold_reset(self):
        for count in (2,4,6):
            result,states,_=exercise(count,eos=[96,84])
            self.assertEqual([r['output_ids'] for r in result['requests']],[[84],[84]])
            self.assertTrue(all(r['timing']['decode_tokens_per_second'] is None for r in result['requests']))
            self.assertIsNone(result['decode_median_tokens_per_second'])
            self.assertEqual([d['serial'] for d in states[0]['dumps']],[3,3])

    def test_epoch_hook_refuses_mismatch_before_socket_or_output_use(self):
        plan=dict(rolling_depth2=True,use_proposals=True,epoch=2)
        stages=[type('Stage',(),{'stream_bytes':16})() for _ in range(2)]
        with self.assertRaisesRegex(ValueError,'epoch'):
            bridge.drive(stages,plan,None,None,epoch=1)


class PersistentPlanTests(unittest.TestCase):
    def fixture(self,folder,policy='qualification',maximum=32):
        from test_rolling_ring_driver import DriverTests
        path,config,manifest,baseline=DriverTests().fixture(folder)
        receipt=Path(config['build_receipt']);data=json.loads(receipt.read_text())
        data['sources'].update({'pipeline/ring/persistent_reset.inc':'fixture',
                               'pipeline/ring/reset_descriptor.hpp':'fixture'})
        receipt.write_text(json.dumps(data))
        inputs=dict(schema='ownrt.persistent-rolling-inputs.v1',model_identity_sha256='a'*64,
            activation_dtype='F32',eos_token_ids=[96,95],prompts=[dict(id=n,prompt_tokens=[3,5,8,11],max_new=maximum)
                for n in ('first','second')])
        suite_path=folder/'inputs.json';suite_path.write_text(json.dumps(inputs))
        config.update(persistent_requests=True,check_policy=policy,admitted_max_new=maximum,max_new=maximum,
            suite=str(suite_path),suite_sha256=base.digest(suite_path),suite_prompt_count=2,dump_each=True,
            measured_policy_admitted=policy=='measured',verify_restore=policy=='qualification',
            verify_recursive_restore=policy=='qualification',verify_provider_survival=policy=='qualification')
        path.write_text(json.dumps(config))
        def underlying(p):
            value=baseline(p);value.update(max_new=maximum,context=4096,activation_dtype='F32');return value
        return path,config,inputs,underlying

    def test_fixed_policy_capabilities_independent_draft_and_runtime_only_inputs(self):
        for policy,maximum in (('qualification',32),('measured',512)):
            with tempfile.TemporaryDirectory() as tmp:
                path,config,inputs,baseline=self.fixture(Path(tmp),policy,maximum)
                with patch.object(base,'make_plan',side_effect=baseline):plan=driver.make_plan(path)
                self.assertEqual(plan['check_policy'],policy)
                self.assertEqual(plan['admitted_max_new'],maximum)
                for stage in plan['stages']:
                    self.assertEqual(base.option(stage['argv'],'--pipeline-ring-check-policy'),policy)
                    self.assertEqual('--pipeline-ring-verify-restore' in stage['argv'],policy=='qualification')
                self.assertIn(str(Path(suite.__file__).resolve()),plan['pins'])
                inputs['prompts'][0]['expected_output_ids']=[1]
                sp=Path(config['suite']);sp.write_text(json.dumps(inputs));config['suite_sha256']=base.digest(sp)
                path.write_text(json.dumps(config))
                with patch.object(base,'make_plan',side_effect=baseline),self.assertRaisesRegex(ValueError,'expected'):
                    driver.make_plan(path)

    def test_missing_reset_capability_policy_toggle_and_implicit512_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,config,_,baseline=self.fixture(Path(tmp))
            for change in ({'admitted_max_new':512},{'check_policy':'measured'}, {'persistent_requests':False}):
                path.write_text(json.dumps(dict(config,**change)))
                with patch.object(base,'make_plan') as planner,self.assertRaises(ValueError):driver.make_plan(path)
                planner.assert_not_called()
            path.write_text(json.dumps(config));rp=Path(config['build_receipt']);r=json.loads(rp.read_text())
            del r['sources']['pipeline/ring/persistent_reset.inc'];rp.write_text(json.dumps(r))
            with patch.object(base,'make_plan',side_effect=baseline),self.assertRaisesRegex(ValueError,'capability'):
                driver.make_plan(path)

    def test_lifecycle_failure_stays_failed_and_uses_one_existing_owner_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan=dict(output=tmp,check_policy='qualification')
            base.save(Path(tmp)/'plan.json',plan)
            def failed(*args,**kwargs):
                self.assertIs(kwargs['stage_type'],bridge.Stage)
                self.assertIs(kwargs['driver'],suite.run)
                self.assertFalse(kwargs['scripted_proposals'])
                base.save(Path(tmp)/'result.json',dict(passed=False,error='fixture',live_pids=[]))
                raise ValueError('fixture')
            with patch.object(driver.live.target.lifecycle,'execute',side_effect=failed) as execute:
                with self.assertRaisesRegex(ValueError,'fixture'):driver.execute(plan,{},'fixture-unit')
            execute.assert_called_once()
            result=json.loads((Path(tmp)/'persistent-rolling-result.json').read_text())
            self.assertFalse(result['passed'])
            self.assertEqual(result['lifecycle_result_sha256'],base.digest(Path(tmp)/'result.json'))

    def test_small_context_is_refused_before_native_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,config,_,baseline=self.fixture(Path(tmp))
            def small(p):
                plan=baseline(p);plan['context']=16;return plan
            with patch.object(base,'make_plan',side_effect=small),self.assertRaisesRegex(ValueError,'at least32'):
                driver.make_plan(path)


if __name__=='__main__':unittest.main()

