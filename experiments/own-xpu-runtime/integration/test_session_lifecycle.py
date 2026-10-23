"""Actual local HTTP + real adapter/policy; synthetic owner only."""
import http.client
import json
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch

import chat_http
from chat_http import make_server
from chat_service import ChatService
from checkpoint_engine import CheckpointEngine
from session_lifecycle import RunAdmission, SessionLifecycle, LifecycleError
from test_checkpoint_engine import Front as BaseFront, Store, identity, parking


class Clock:
    def __init__(self):self.value=100.
    def __call__(self):return self.value


class Codec:
    vocab=32;terminal_token_ids={0};tokenizer_identity={'source':'synthetic-test-only'}
    def render(self,messages):return messages[-1]['content']
    def encode(self,text):return [1,2]
    def decode(self,tokens):return 'reply'


class Process:
    def __init__(self):self.returncode=None
    def poll(self):return self.returncode


class Front(BaseFront):
    def __init__(self,store,trusted):
        super().__init__(store,trusted)
        self.completed_controls=0;self.process=Process();self.close_calls=0
        self.close_event=None;self.close_error=None
    def dispose(self,*args):
        event=super().dispose(*args);self.completed_controls+=1;return event
    def close(self,timeout=120):
        self.close_calls+=1
        if self.close_error:raise self.close_error
        self.process.returncode=0;self.state='closed'
        return self.close_event or dict(event='stopped',safe_to_exit=True,reason='quit',
            completed_requests=self.completed,completed_controls=self.completed_controls,
            discarded_pending=False,pending_request_id='')


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.clock=Clock();self.guard_calls=[];self.store=Store();self.trusted=identity()
        self.front=Front(self.store,self.trusted);self.codec=Codec()
        self.server=None;self.thread=None;self.outcome={}

    def attach(self, *, request_limit=2, idle=20, activity=100, guard=None):
        self.admission=RunAdmission(self.front,guard=guard or (lambda:self.guard_calls.append('guard')),
            request_limit=request_limit,idle_seconds=idle,absolute_deadline=200,
            last_native_activity=activity,native_idle_seconds=300,native_absolute_deadline=300,clock=self.clock)
        self.engine=CheckpointEngine(self.admission.front,self.store,root=self.store.root,
            expected_identity=self.trusted,admitted_contract='v1.2+p198',save_size_bound_bytes=8192,
            storage_available=lambda root:20000,floor_bytes=1000)
        self.parking=parking.Parking(self.engine,self.codec.render,self.codec.encode,budget_bytes=65536,
            accepted_contracts={('experimental-postreply-front','v1.2+p198')})
        self.chat=ChatService(self.engine,self.parking,self.codec,model='synthetic',native_stop_token_ids={0})
        self.life=SessionLifecycle(self.chat,self.admission,poll_seconds=.01)
        self.server=make_server(self.life.service)
        return self.life

    def start(self):
        def run():
            try:self.outcome['receipt']=self.life.serve(self.server)
            except BaseException as error:self.outcome['error']=error
        self.thread=threading.Thread(target=run,daemon=True);self.thread.start()

    def finish(self):
        self.thread.join(2);self.assertFalse(self.thread.is_alive());return self.outcome

    def tearDown(self):
        if self.thread and self.thread.is_alive():
            self.life.request_close();self.thread.join(2)
        if self.server:self.server.server_close()

    def request(self, payload=None, *, path='/v1/chat/completions'):
        c=http.client.HTTPConnection(*self.server.server_address,timeout=2)
        try:
            if path=='/health':c.request('GET',path)
            else:
                value=payload if payload is not None else {'model':'synthetic','messages':[{'role':'user','content':'hi'}],'max_tokens':2}
                c.request('POST',path,json.dumps(value).encode(),{'Content-Type':'application/json','X-Ownrt-Session':'one'})
            r=c.getresponse();return r.status,json.loads(r.read())
        finally:c.close()

    def test_initial_activity_is_not_extended_and_idle_quits_once(self):
        self.attach(activity=90,idle=5);self.start();result=self.finish()
        self.assertEqual(result['receipt']['reason'],'idle');self.assertEqual(self.front.close_calls,1)
        self.assertEqual(self.front.calls,[])
        self.life.request_close();self.life.request_close()
        with self.assertRaisesRegex(LifecycleError,'single use'):self.life.serve(self.server)
        self.assertEqual(self.front.close_calls,1)

    def test_request_limit_closes_after_normal_disposition(self):
        self.front.max_requests=1;self.attach(request_limit=1);self.start()
        self.assertEqual(self.request()[0],200)
        result=self.finish();self.assertTrue(result['receipt']['passed'])
        self.assertEqual([x[0] for x in self.front.calls],['RUN','SAVE'])
        self.assertEqual(self.front.close_calls,1);self.assertEqual(self.front.completed_controls,1)

    def test_invalid_and_health_do_not_refresh_native_activity(self):
        self.attach(activity=95,idle=10);self.start()
        self.assertEqual(self.request(path='/health')[0],200)
        self.clock.value=103
        self.assertEqual(self.request({'stream':True})[0],400)
        self.assertEqual(self.admission.last_native_activity,95)
        self.clock.value=106;result=self.finish()
        self.assertEqual(result['receipt']['reason'],'idle');self.assertEqual(self.front.calls,[])

    def test_close_latch_during_admitted_turn_waits_for_disposition(self):
        self.attach();entered=threading.Event();release=threading.Event();original=self.front.request
        def block(*args,**kwargs):
            entered.set();self.assertTrue(release.wait(1));return original(*args,**kwargs)
        self.front.request=block;self.start()
        client=http.client.HTTPConnection(*self.server.server_address,timeout=2)
        payload={'model':'synthetic','messages':[{'role':'user','content':'hi'}],'max_tokens':2}
        client.request('POST','/v1/chat/completions',json.dumps(payload).encode(),
                       {'Content-Type':'application/json','X-Ownrt-Session':'one'})
        self.assertTrue(entered.wait(1));self.life.request_close();self.assertEqual(self.front.close_calls,0)
        release.set();reply=client.getresponse();self.assertEqual(reply.status,200);reply.read();client.close()
        result=self.finish();self.assertEqual(result['receipt']['reason'],'requested')
        self.assertEqual([x[0] for x in self.front.calls],['RUN','SAVE']);self.assertEqual(self.front.close_calls,1)

    def test_expiry_during_body_is_before_adapter_and_closes_normally(self):
        self.attach(idle=10);self.start()
        c=http.client.HTTPConnection(*self.server.server_address,timeout=2)
        body=json.dumps({'model':'synthetic','messages':[{'role':'user','content':'hi'}],'max_tokens':2}).encode()
        c.putrequest('POST','/v1/chat/completions');c.putheader('Content-Length',str(len(body)))
        c.putheader('Content-Type','application/json');c.putheader('X-Ownrt-Session','one');c.endheaders()
        time.sleep(.02);self.clock.value=111;c.send(body)
        response=c.getresponse();self.assertEqual(response.status,503);response.read();c.close()
        self.assertEqual(self.finish()['receipt']['reason'],'idle');self.assertEqual(self.front.calls,[])
        self.assertIsNone(self.engine.halted_reason)

    def test_expiry_during_codec_is_immediate_prerun_incident(self):
        self.attach(idle=10)
        def delayed(messages):self.clock.value=111;return 'hi'
        self.codec.render=delayed;self.parking.render=delayed
        self.start();self.assertEqual(self.request()[0],503);error=self.finish()['error']
        self.assertIn('late pre-RUN',str(error));self.assertIs(error,self.admission.failure)
        self.assertEqual(self.front.calls,[]);self.assertEqual(self.front.close_calls,0)
        self.assertIsNotNone(self.engine.halted_reason);self.assertIsNone(self.front.process.poll())

    def test_native_idle_exit_already_queued_closes_from_ready(self):
        self.attach();self.front.process.returncode=0
        self.front.close_event=dict(event='stopped',safe_to_exit=True,reason='idle-timeout',completed_requests=0,
            completed_controls=0,discarded_pending=False,pending_request_id='')
        self.start();result=self.finish();self.assertEqual(result['receipt']['reason'],'native-exit')
        self.assertEqual(self.front.close_calls,1)

    def test_native_exit_race_preserves_original_error_no_close_or_retry(self):
        self.attach();original=RuntimeError('native stream ended before event');calls=[]
        def race(*args,**kwargs):calls.append(True);self.front.process.returncode=0;raise original
        self.front.request=race;self.start();self.assertEqual(self.request()[0],503)
        self.assertIs(self.finish()['error'],original);self.assertEqual(calls,[True]);self.assertEqual(self.front.close_calls,0)

    def test_runtime_error_swallowed_by_http_retained_over_cleanup_error(self):
        self.attach();original=OSError('native SAVE ambiguous')
        def failed(*args,**kwargs):raise original
        self.front.save=failed;real_close=self.server.server_close
        self.server.server_close=lambda:(_ for _ in ()).throw(OSError('listener cleanup'))
        try:
            self.start();self.assertEqual(self.request()[0],503)
            self.assertIs(self.finish()['error'],original);self.assertEqual(self.front.close_calls,0)
            self.assertTrue(any('listener cleanup' in note for note in original.__notes__))
        finally:self.server.server_close=real_close

    def test_guard_failure_before_close_retains_owner(self):
        original=RuntimeError('fault guard refused')
        def fail():raise original
        self.attach(guard=fail);self.life.request_close();self.start()
        self.assertIs(self.finish()['error'],original);self.assertEqual(self.front.close_calls,0)

    def test_exact_proxy_binding_and_exclusive_claim_required(self):
        self.attach()
        with self.assertRaisesRegex(LifecycleError,'already exclusively claimed'):
            RunAdmission(self.front,guard=lambda:None,request_limit=2,idle_seconds=10,absolute_deadline=200,
                         last_native_activity=100,native_idle_seconds=300,native_absolute_deadline=300,clock=self.clock)
        with self.assertRaisesRegex(LifecycleError,'already attached'):SessionLifecycle(self.chat,self.admission)
        with self.assertRaisesRegex(LifecycleError,'outside exclusive'):
            self.admission.front.request('bypass',[1,2],2)
        self.assertEqual(self.front.calls,[])

    def test_pre_service_owner_poll_error_is_original(self):
        self.attach();original=OSError('poll failed at admission');count=[0]
        def poll():
            count[0]+=1
            if count[0]==2:raise original
            return None
        self.front.process.poll=poll;self.start();self.assertEqual(self.request()[0],503)
        self.assertIs(self.finish()['error'],original);self.assertEqual(self.front.close_calls,0)

    def test_response_serialization_failure_is_retained(self):
        self.attach();self.chat._complete=lambda *args: {'bad':{1}}
        self.start();self.assertEqual(self.request()[0],503)
        error=self.finish()['error'];self.assertIsInstance(error,TypeError)
        self.assertIs(error,self.admission.failure);self.assertEqual(self.front.close_calls,0)

    def test_internal_http_halt_is_incident_after_completed_save(self):
        self.attach();reply=chat_http._Handler._reply
        def broken(handler,status,value):
            if status==200:raise OSError('internal response failure')
            return reply(handler,status,value)
        with patch.object(chat_http._Handler,'_reply',broken):
            self.start();self.assertEqual(self.request()[0],503)
            self.assertIn('HTTP intake halted',str(self.finish()['error']))
        self.assertEqual([x[0] for x in self.front.calls],['RUN','SAVE'])
        self.assertEqual(self.front.close_calls,0)

    def test_unexpected_existing_service_halt_refuses_clean_close(self):
        self.attach();self.engine.halted_reason='unobserved policy failure';self.start()
        self.assertIn('halted outside',str(self.finish()['error']));self.assertEqual(self.front.close_calls,0)

    def test_wrong_terminal_proof_never_becomes_success(self):
        self.attach();self.life.request_close()
        self.front.close_event={'event':'stopped','safe_to_exit':True,'completed_requests':1,'completed_controls':0,
                               'discarded_pending':False,'pending_request_id':'','reason':'quit'}
        self.start();self.assertIn('shutdown proof',str(self.finish()['error']))
        self.assertEqual(self.front.close_calls,1);self.assertEqual(self.life.state,'incident')


if __name__=='__main__':unittest.main(verbosity=2)
