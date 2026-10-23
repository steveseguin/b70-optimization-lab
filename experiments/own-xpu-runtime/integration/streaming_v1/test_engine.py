"""Synthetic native/store seams only, including canonical engine regressions."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_checkpoint_engine as F
from streaming_v1 import engine as E

class Front(F.Front):
    def request(self,request_id,tokens,max_new,restore=None,on_token=None):
        self.state='running'
        output=self.generated[:max_new]
        for token in output[:-1] if getattr(self,'omit_last_event',False) else output:
            if on_token:on_token(token)
        if getattr(self,'native_failure',None) is not None:raise self.native_failure
        return super().request(request_id,tokens,max_new,restore=restore)

class EngineTests(F.EngineTests):
    def make(self,**overrides):
        trusted=F.identity();store=F.Store();front=Front(store,trusted)
        args=dict(root=store.root,expected_identity=trusted,admitted_contract='v1.2+p198',save_size_bound_bytes=8192,
                  storage_available=lambda root:20000,floor_bytes=1000);args.update(overrides)
        return E.StreamingCheckpointEngine(front,store,**args),front,store,trusted

    def test_tokens_observed_during_run_before_disposition(self):
        engine,front,store,_=self.make();seen=[]
        def observe(token):
            self.assertEqual(front.state,'running');self.assertIsNone(front.pending)
            self.assertFalse(front.saved_tokens);seen.append(token)
        result=engine.run_turn(self.policy(engine),'s',self.messages(),request_id='a',max_new=2,on_token=observe)
        self.assertEqual(seen,[3,4]);self.assertEqual(front.saved_tokens,[[1,2,3,4]])
        self.assertEqual(result['observation'],dict(enabled=True,observed_tokens=2,callback_calls_completed=2,observer_failed=False))
        self.assertIs(engine.front,front);self.assertIs(engine.store,store)

    def test_observer_failure_does_not_skip_save_and_is_reset_next_turn(self):
        for failure in (RuntimeError('sink failed'),KeyboardInterrupt('observer interrupted')):
            engine,front,_,_=self.make();calls=[]
            def observe(token):calls.append(token);raise failure
            result=engine.run_turn(self.policy(engine),'s',self.messages(),request_id='a',max_new=2,on_token=observe)
            self.assertEqual(calls,[3]);self.assertEqual([c[0] for c in front.calls],['RUN','SAVE'])
            self.assertIs(engine.last_observer_error,failure);self.assertTrue(result['observation']['observer_failed'])
            self.assertEqual(result['response']['tokens'],[3,4]);self.assertIsNone(engine.halted_reason)
            engine.run_turn(self.policy(engine,0),'s2',self.messages(),request_id='b',max_new=2)
            self.assertIsNone(engine.last_observer_error)

    def test_observer_failure_still_releases_final_and_same_id_no_save(self):
        for same_id in (False,True):
            engine,front,_,_=self.make();front.max_requests=1;policy=self.policy(engine,0)
            if same_id:policy.park=lambda *args:object()
            def observe(token):raise BrokenPipeError('disconnected')
            result=engine.run_turn(policy,'s',self.messages(),request_id='last',max_new=2,on_token=observe)
            self.assertEqual([c[0] for c in front.calls],['RUN','RELEASE'])
            self.assertEqual(front.state,'draining');self.assertTrue(result['release']['final_request'])

    def test_native_or_save_failure_remains_primary_after_observer_failure(self):
        for phase in ('native','save'):
            engine,front,_,_=self.make();observer_error=ValueError('observer')
            if phase=='native':front.native_failure=OSError('native original')
            else:front.ambiguous_save=True
            def observe(token):raise observer_error
            with self.assertRaisesRegex(OSError,'native original|lost SAVE acknowledgement'):
                engine.run_turn(self.policy(engine),'s',self.messages(),request_id='a',max_new=2,on_token=observe)
            self.assertIs(engine.last_observer_error,observer_error);self.assertIsNotNone(engine.halted_reason)
            self.assertNotIn('RELEASE',[c[0] for c in front.calls])

    def test_observer_receipt_cannot_raise_from_exception_string(self):
        class Unprintable(Exception):
            def __str__(self):raise RuntimeError('string refused')
        engine,front,_,_=self.make()
        def observe(token):raise Unprintable()
        result=engine.run_turn(self.policy(engine),'s',self.messages(),request_id='a',max_new=2,on_token=observe)
        self.assertEqual(result['observation']['error']['message'],'<exception message unavailable>')
        self.assertEqual(front.state,'ready')

    def test_token_frame_mismatch_is_native_incident_not_delivery_error(self):
        engine,front,_,_=self.make();front.omit_last_event=True
        with self.assertRaisesRegex(E.parent.EngineRefusal,'token frames'):
            engine.run_turn(self.policy(engine),'s',self.messages(),request_id='a',max_new=2,on_token=lambda token:None)
        self.assertIsNotNone(engine.halted_reason);self.assertEqual([c[0] for c in front.calls],['RUN'])

    def test_changed_parent_pin_refuses_before_construction(self):
        with patch.object(E,'PARENT_SHA','0'*64):
            with self.assertRaisesRegex(E.parent.EngineRefusal,'exact canonical'):self.make()

if __name__=='__main__':unittest.main()
