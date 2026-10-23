"""Synthetic adapter fixtures only: no native tools, processes or device work."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import threading
import unittest

from checkpoint_engine import CheckpointEngine, EngineRefusal
from native_checkpoint_store import CheckpointSnapshot

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('parking', ROOT/'tools/ctxkeeper/parking.py')
parking = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = parking
spec.loader.exec_module(parking)


def digest(data): return hashlib.sha256(data).hexdigest()


def identity():
    return dict(model={'identity_tsv_sha256':'a'*64}, engine={'binary_sha256':'b'*64,'profile':'tp1-full512'},
                geometry={'context':4096,'vocab':32,'eos':0}, dtypes={'state':'synthetic-test-only'},
                tokenizer_identity={'source':'synthetic-test-only'}, label='experimental-postreply-front',
                contract='v1.2+p198', qualified_by={'device_gates':[]})


def snapshot(cid, visible, trusted):
    """Mutually consistent synthetic envelope; never claims native/device evidence."""
    processed = visible[:-1]; raw = struct.pack('<'+'i'*len(processed), *processed)
    pending = struct.pack('<i',visible[-1])
    manifest = dict(copy.deepcopy(trusted), format='ownrt.session-checkpoint.v1',checkpoint_id=cid,
        operations=['append'],sampler={'mode':'greedy-argmax','state':None},
        token_state=dict(length=len(processed),position=len(processed),prompt_length=1,
                         tokens_sha256=digest(raw),next_token=visible[-1],
                         token_history=[processed[-2] if len(processed)>1 else 0,processed[-1]]),
        blobs=[dict(name='next_token',bytes=4,sha256=digest(pending))], measurements={'save_bytes':4})
    data=json.dumps(manifest).encode()
    inspected=dict(schema='ownrt.checkpoint-inspect.v1',ok=True,error=None,device_required=False,mode='metadata',
        manifest_sha256=digest(data),manifest=manifest,checkpoint_id=cid,label=manifest['label'],contract=manifest['contract'],
        verified=dict(manifest_seal=True,fields_tsv_cross_check=True,file_set_closed=True,tokens=None,
                      semantic_blob_checks=None,blobs_verified=None,blob_bytes_verified=None))
    return CheckpointSnapshot(cid,json.dumps(inspected).encode(),0,b'',data,raw,pending,len(data)+len(raw)+len(pending)+128)


class Store:
    root=Path('/synthetic-admitted-checkpoints')
    binary_sha256='b'*64
    def __init__(self): self.saved={};self.calls=[];self.delete_status='ok'
    def snapshot(self,cid): self.calls.append(('snapshot',cid));return self.saved.get(cid)
    def delete(self,cid):
        self.calls.append(('delete',cid))
        if self.delete_status=='ok': return 'ok' if self.saved.pop(cid,None) is not None else 'missing'
        return self.delete_status


class Front:
    def __init__(self,store,trusted):
        self.store,self.trusted=store,trusted;self.state='ready';self.pending=None
        self.ready=dict(protocol='ownrt.request-front.v2',experimental=True,context=4096,vocab=32,model_loads=1)
        self.operations=set();self.calls=[];self.completed=0;self.max_requests=8
        self.generated=[3,4];self.saved_tokens=[];self.bad_ack=False;self.ambiguous_save=False
    def request(self,request_id,tokens,max_new,restore=None):
        self.calls.append(('RUN',request_id,tuple(tokens),restore));self.completed+=1
        output=self.generated[:max_new];self.visible=tokens+output
        self.pending=dict(request_id=request_id,visible_tokens=len(self.visible),pending_token=output[-1],processed_tokens=len(self.visible)-1)
        self.state='awaiting-disposition'
        return dict(tokens=list(output),completion={'save_pending':True})
    def dispose(self,operation,event):
        self.operations.add(operation);rid=self.pending['request_id'];self.pending=None
        self.state='draining' if self.completed==self.max_requests else 'ready'
        return dict(event=event,operation_id=operation,request_id=rid,request_disposed=True,request_quiesced=True,
                    final_request=self.completed==self.max_requests)
    def save(self,operation,cid,tokens):
        self.calls.append(('SAVE',cid));self.saved_tokens.append(tokens)
        saved=snapshot(cid,tokens,self.trusted);self.store.saved[cid]=saved
        event=self.dispose(operation,'checkpoint-saved');event.update(checkpoint_id=cid,manifest_sha256=digest(saved.manifest_bytes))
        if self.bad_ack:event['manifest_sha256']='0'*64
        if self.ambiguous_save:raise OSError('lost SAVE acknowledgement')
        return event
    def release(self,operation):
        self.calls.append(('RELEASE',operation));return self.dispose(operation,'request-released')


class EngineTests(unittest.TestCase):
    def make(self,**overrides):
        trusted=identity();store=Store();front=Front(store,trusted)
        args=dict(root=store.root,expected_identity=trusted,admitted_contract='v1.2+p198',save_size_bound_bytes=8192,
                  storage_available=lambda root:20000,floor_bytes=1000)
        args.update(overrides)
        return CheckpointEngine(front,store,**args),front,store,trusted

    def policy(self,engine,budget=65536):
        return parking.Parking(engine,lambda messages:messages,lambda messages:list(messages[0]['tokens']),budget_bytes=budget,
                               accepted_contracts={('experimental-postreply-front','v1.2+p198')})

    @staticmethod
    def messages(tokens=(1,2)):return [{'role':'user','tokens':list(tokens)}]

    def test_constructor_requires_explicit_complete_trusted_admission(self):
        for change in (dict(admitted_contract='v1.2+p181'),dict(expected_identity={}),dict(save_size_bound_bytes=True),
                       dict(save_size_bound_bytes=0),dict(root=Path('/another-root')),dict(floor_bytes=-1)):
            with self.subTest(change=change),self.assertRaises(EngineRefusal):self.make(**change)
        engine,front,store,trusted=self.make();trusted['engine']['binary_sha256']='c'*64
        self.assertEqual(engine.identity()['engine'],'b'*64)

    def test_inspect_keeps_native_identity_and_actual_storage_bytes(self):
        engine,front,store,trusted=self.make();saved=snapshot('s',[1,2,3,4],trusted);store.saved['s']=saved
        metadata=engine.inspect('s')
        self.assertEqual(metadata['label'],'experimental-postreply-front')
        self.assertEqual(metadata['contract'],'v1.2+p198')
        self.assertEqual(metadata['storage_bytes'],saved.storage_bytes)
        self.assertEqual(metadata['token_state']['length'],4)
        self.assertFalse(front.calls);self.assertIsNone(engine.inspect('missing'))

    def test_wrong_snapshot_identity_poisoned_without_native_run(self):
        engine,front,store,trusted=self.make();wrong=copy.deepcopy(trusted);wrong['engine']['binary_sha256']='c'*64
        store.saved['s']=snapshot('s',[1,2,3],wrong)
        with self.assertRaises(ValueError):engine.inspect('s')
        with self.assertRaisesRegex(EngineRefusal,'halted'):engine.generate([1,2],2,request_id='later')
        self.assertFalse(front.calls)

    def test_run_turn_saves_exact_visible_reply_once(self):
        engine,front,store,_=self.make();result=engine.run_turn(self.policy(engine),'session',self.messages(),request_id='a',max_new=2)
        self.assertEqual([c[0] for c in front.calls],['RUN','SAVE'])
        self.assertEqual(front.saved_tokens,[[1,2,3,4]])
        self.assertIsNotNone(result['parked']);self.assertIsNone(result['release'])
        self.assertEqual(front.state,'ready')

    def test_no_save_budget_and_non_none_same_id_hit_release(self):
        for hit in (False,True):
            engine,front,store,_=self.make();policy=self.policy(engine,budget=0)
            sentinel=object()
            if hit:policy.park=lambda *a:sentinel  # Existing same-ID policy hit makes no SAVE call.
            result=engine.run_turn(policy,'s',self.messages(),request_id='a',max_new=2)
            self.assertEqual([c[0] for c in front.calls],['RUN','RELEASE'])
            self.assertIs(result['parked'],sentinel if hit else None)
            self.assertEqual(front.state,'ready')

    def test_final_no_save_releases_into_draining(self):
        engine,front,store,_=self.make();front.max_requests=1
        result=engine.run_turn(self.policy(engine,0),'s',self.messages(),request_id='last',max_new=2)
        self.assertTrue(result['release']['final_request']);self.assertEqual(front.state,'draining')

    def test_restore_is_append_plan_only_then_consumed_by_matching_run(self):
        engine,front,store,trusted=self.make();store.saved['s']=snapshot('s',[1,2,3,4],trusted)
        plan=engine.restore('s',[1,2,3,4,5]);self.assertFalse(front.calls)
        self.assertEqual((plan['restored'],plan['appended']),(4,1))
        engine.generate([1,2,3,4,5],2,request_id='append');self.assertEqual(front.calls[0][-1],'s')
        engine.save('after-append',[1,2,3,4,5,3,4])
        self.assertEqual(front.saved_tokens[-1],[1,2,3,4,5,3,4])
        engine.generate([6,7],2,request_id='fresh');self.assertIsNone(front.calls[-1][-1])

    def test_same_generation_resume_or_changed_plan_refuses_before_run(self):
        for mode in ('omitted-pending','different-tokens','changed-snapshot'):
            engine,front,store,trusted=self.make();store.saved['s']=snapshot('s',[1,2,3,4],trusted)
            with self.subTest(mode=mode),self.assertRaises((ValueError,EngineRefusal)):
                if mode=='omitted-pending':engine.restore('s',[1,2,3])
                else:
                    engine.restore('s',[1,2,3,4,5])
                    if mode=='changed-snapshot':store.saved['s']=snapshot('s',[1,2,3,4,6],trusted)
                    engine.generate([1,2,3,4,6] if mode=='different-tokens' else [1,2,3,4,5],2,request_id='a')
            self.assertFalse(front.calls)

    def test_headroom_and_wrong_save_history_refuse_before_save(self):
        for mode in ('headroom','history','existing'):
            engine,front,store,trusted=self.make(storage_available=lambda root:9000 if mode=='headroom' else 20000)
            engine.generate([1,2],2,request_id='a')
            if mode=='existing':store.saved['s']=snapshot('s',[1,2,3,4],trusted)
            with self.subTest(mode=mode),self.assertRaises(EngineRefusal):
                engine.save('s',[1,2,3,5] if mode=='history' else [1,2,3,4])
            self.assertEqual([c[0] for c in front.calls],['RUN'])
            with self.assertRaisesRegex(EngineRefusal,'halted'):engine.release()

    def test_bad_ack_or_ambiguous_save_halts_without_retry_or_release(self):
        for attribute in ('bad_ack','ambiguous_save'):
            engine,front,store,_=self.make();setattr(front,attribute,True);policy=self.policy(engine)
            with self.subTest(attribute=attribute),self.assertRaises((EngineRefusal,OSError)):
                engine.run_turn(policy,'s',self.messages(),request_id='a',max_new=2)
            self.assertEqual([c[0] for c in front.calls],['RUN','SAVE'])
            self.assertEqual(policy.total_bytes(),8192)
            with self.assertRaisesRegex(EngineRefusal,'halted'):
                engine.run_turn(policy,'s',self.messages(),request_id='b',max_new=2)

    def test_policy_exception_leaves_pending_for_coordinator_without_release(self):
        engine,front,store,_=self.make();policy=self.policy(engine)
        def failed(*args):raise RuntimeError('policy failed')
        policy.park=failed
        with self.assertRaisesRegex(RuntimeError,'policy failed'):
            engine.run_turn(policy,'s',self.messages(),request_id='a',max_new=2)
        self.assertEqual([c[0] for c in front.calls],['RUN']);self.assertEqual(front.state,'awaiting-disposition')
        self.assertIsNotNone(engine.halted_reason)

    def test_delete_in_use_is_typed_normal_outcome(self):
        engine,front,store,_=self.make();store.delete_status='in_use'
        self.assertEqual(engine.delete('s'),'in_use');self.assertIsNone(engine.halted_reason)
        self.assertFalse(front.calls)

    def test_owner_mutex_covers_policy_disposition(self):
        engine,front,store,_=self.make();first=self.policy(engine,0);second=self.policy(engine,0)
        entered,allow,second_attempt=threading.Event(),threading.Event(),threading.Event();errors=[]
        def wait_policy(*args):entered.set();self.assertTrue(allow.wait(2));return None
        first.park=wait_policy
        def run(policy,rid):
            try:
                if rid=='b':second_attempt.set()
                engine.run_turn(policy,rid,self.messages(),request_id=rid,max_new=2)
            except BaseException as e:errors.append(e)
        one=threading.Thread(target=run,args=(first,'a'));two=threading.Thread(target=run,args=(second,'b'))
        one.start();self.assertTrue(entered.wait(2));two.start();self.assertTrue(second_attempt.wait(2))
        self.assertEqual([c[0] for c in front.calls],['RUN'])
        allow.set();one.join(2);two.join(2)
        self.assertFalse(one.is_alive() or two.is_alive());self.assertFalse(errors)
        self.assertEqual([c[0] for c in front.calls],['RUN','RELEASE','RUN','RELEASE'])


if __name__=='__main__':unittest.main()
