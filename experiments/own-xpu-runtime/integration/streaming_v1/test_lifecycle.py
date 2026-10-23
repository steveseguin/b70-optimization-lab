"""Real streaming HTTP/service/codec and unchanged admission; synthetic owner.

The sixteen inherited lifecycle regressions run through this new lifecycle and
server using the actual pinned codec. Added tests exercise the stream path.
"""
import copy
import http.client
import json
from pathlib import Path
import socket
import struct
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import chat_codec as C
import chat_http
import session_lifecycle as canonical
import test_session_lifecycle as F
from streaming_v1 import engine as E, service as S, http as H, lifecycle as L


class Front(F.Front):
    def request(self,request_id,tokens,max_new,restore=None,on_token=None):
        if on_token is not None:
            self.state='running'
            for token in self.generated[:max_new]:on_token(token)
        return super().request(request_id,tokens,max_new,restore=restore)


class LifecycleTests(F.LifecycleTests):
    @classmethod
    def setUpClass(cls):
        cls.shared_codec=C.PinnedChatCodec()

    def setUp(self):
        super().setUp()
        self.codec=copy.copy(self.shared_codec)
        self.trusted['tokenizer_identity']=dict(self.codec.tokenizer_identity)
        self.trusted['geometry'].update(vocab=self.codec.vocab,eos=248044)
        self.front=Front(self.store,self.trusted)
        self.front.ready['vocab']=self.codec.vocab

    def attach(self,*,request_limit=2,idle=20,activity=100,guard=None):
        self.admission=L.RunAdmission(self.front,guard=guard or (lambda:self.guard_calls.append('guard')),
            request_limit=request_limit,idle_seconds=idle,absolute_deadline=200,
            last_native_activity=activity,native_idle_seconds=300,native_absolute_deadline=300,clock=self.clock)
        self.engine=E.StreamingCheckpointEngine(self.admission.front,self.store,root=self.store.root,
            expected_identity=self.trusted,admitted_contract='v1.2+p198',save_size_bound_bytes=65536,
            storage_available=lambda root:1000000,floor_bytes=1000)
        self.parking=F.parking.Parking(self.engine,self.codec.render,self.codec.encode,budget_bytes=524288,
            accepted_contracts={('experimental-postreply-front','v1.2+p198')})
        self.chat=S.StreamingChatService(self.engine,self.parking,self.codec,model='synthetic',
            native_stop_token_ids={248044,248046})
        self.life=L.StreamingSessionLifecycle(self.chat,self.admission,poll_seconds=.01)
        self.server=H.make_server(self.life.service)
        return self.life

    def stream_client(self):
        c=http.client.HTTPConnection(*self.server.server_address,timeout=2)
        body={'model':'synthetic','messages':[{'role':'user','content':'hi'}],
              'max_tokens':len(self.front.generated),'stream':True}
        c.request('POST','/v1/chat/completions',json.dumps(body).encode(),
                  {'Content-Type':'application/json','X-Ownrt-Session':'one'})
        return c

    def stream_request(self):
        c=self.stream_client()
        try:
            response=c.getresponse()
            return response.status,response.read()
        finally:c.close()

    def test_stream_soft_count_closes_once_after_save_and_done(self):
        self.front.generated=self.codec.encode('hello 🙂')+[248046]
        self.attach(request_limit=1);self.start()
        status,raw=self.stream_request()
        self.assertEqual(status,200);self.assertTrue(raw.endswith(b'data: [DONE]\n\n'))
        result=self.finish()['receipt']
        self.assertEqual(result['reason'],'request-limit')
        self.assertEqual(result['completed_requests'],1)
        self.assertEqual(self.front.completed_controls,1)
        self.assertEqual([x[0] for x in self.front.calls],['RUN','SAVE'])
        self.assertEqual(self.front.close_calls,1);self.assertEqual(self.life.state,'closed')
        self.assertIs(L.RunAdmission,canonical.RunAdmission)

    def test_expiry_during_codec_is_immediate_prerun_incident(self):
        # New HTTP performs a validation pass before proxy entry. Advance only
        # on the service's second render, preserving the inherited test's actual
        # inside-adapter expiry boundary instead of expiring before entry.
        self.attach(idle=10);original=self.codec.render;calls=0
        def delayed(messages):
            nonlocal calls
            calls+=1
            if calls==2:self.clock.value=111
            return original(messages)
        self.codec.render=delayed;self.parking.render=delayed
        self.start();self.assertEqual(self.request()[0],503)
        error=self.finish()['error']
        self.assertIn('late pre-RUN',str(error));self.assertIs(error,self.admission.failure)
        self.assertEqual(self.front.calls,[]);self.assertEqual(self.front.close_calls,0)
        self.assertIsNotNone(self.engine.halted_reason);self.assertIsNone(self.front.process.poll())

    def test_stream_expiry_during_http_prevalidation_closes_before_adapter(self):
        self.attach(idle=10);original=self.chat.validate
        def validate(payload):
            result=original(payload);self.clock.value=111;return result
        self.chat.validate=validate;self.start()
        status,raw=self.stream_request()
        self.assertEqual(status,200);self.assertNotIn(b'[DONE]',raw)
        self.assertEqual(self.finish()['receipt']['reason'],'idle')
        self.assertEqual(self.front.calls,[]);self.assertEqual(self.front.close_calls,1)
        self.assertIsNone(self.engine.halted_reason);self.assertIsNone(self.admission.failure)

    def test_stream_close_latch_waits_for_save_and_delivery(self):
        self.front.generated=self.codec.encode('a')+[248046]
        self.attach();entered,proceed=threading.Event(),threading.Event();original=self.front.save
        def save(*args):
            entered.set()
            if not proceed.wait(2):raise RuntimeError('test SAVE gate timeout')
            return original(*args)
        self.front.save=save;self.start();client=self.stream_client()
        try:
            response=client.getresponse();self.assertEqual(response.status,200)
            self.assertTrue(entered.wait(1));self.life.request_close()
            self.assertEqual(self.front.close_calls,0)
            self.assertTrue(self.life._in_service);self.assertTrue(self.life._in_handler)
            proceed.set();raw=response.read();self.assertTrue(raw.endswith(b'data: [DONE]\n\n'))
            self.assertEqual(self.finish()['receipt']['reason'],'requested')
            self.assertEqual([x[0] for x in self.front.calls],['RUN','SAVE'])
            self.assertEqual(self.front.close_calls,1)
        finally:proceed.set();client.close()

    def test_stream_late_prerun_expiry_is_incident_not_normal_close(self):
        self.front.generated=[1,2]
        def guard():self.clock.value=111
        self.attach(idle=10,guard=guard);self.start()
        status,raw=self.stream_request()
        self.assertEqual(status,200);self.assertNotIn(b'[DONE]',raw)
        error=self.finish()['error']
        self.assertIn('late pre-RUN',str(error));self.assertIs(error,self.admission.failure)
        self.assertEqual(self.front.calls,[]);self.assertEqual(self.front.close_calls,0)
        self.assertIsNotNone(self.engine.halted_reason)

    def test_stream_save_error_preserves_original_over_listener_cleanup(self):
        self.front.generated=self.codec.encode('a')+[248046]
        self.attach();original=OSError('original streaming SAVE failure')
        def save(*args):raise original
        self.front.save=save;close=self.server.server_close
        self.server.server_close=lambda:(_ for _ in ()).throw(OSError('cleanup secondary'))
        try:
            self.start();status,raw=self.stream_request()
            self.assertEqual(status,200);self.assertNotIn(b'[DONE]',raw)
            self.assertIs(self.finish()['error'],original)
            self.assertIs(self.admission.failure,original)
            self.assertEqual(self.front.close_calls,0);self.assertEqual(self.life.state,'incident')
            self.assertTrue(any('cleanup secondary' in x for x in original.__notes__))
        finally:self.server.server_close=close

    def test_stream_disconnect_is_normal_disposition_then_soft_close(self):
        self.front.generated=self.codec.encode('first more words after disconnect')+[248046]
        self.attach(request_limit=1)
        entered,proceed=threading.Event(),threading.Event();original=self.front.request
        def request(*args,**kwargs):
            observer=kwargs['on_token'];first=True
            def observe(token):
                nonlocal first
                observer(token)
                if first:
                    first=False;entered.set()
                    if not proceed.wait(2):raise RuntimeError('test token gate timeout')
            kwargs['on_token']=observe
            return original(*args,**kwargs)
        self.front.request=request;self.start();client=self.stream_client()
        try:
            self.assertTrue(entered.wait(1))
            client.sock.setsockopt(socket.SOL_SOCKET,socket.SO_LINGER,struct.pack('ii',1,0))
            client.close();proceed.set()
            result=self.finish()['receipt']
            self.assertTrue(result['passed']);self.assertEqual(self.front.close_calls,1)
            self.assertEqual([c[0] for c in self.front.calls],['RUN','SAVE'])
            self.assertIsNone(self.admission.failure);self.assertIsNone(self.engine.halted_reason)
            self.assertTrue(self.server.last_stream_receipt['native_complete'])
            self.assertIsNotNone(self.server.last_stream_receipt['delivery']['failed'])
            self.assertFalse(self.server.last_stream_receipt['terminal_offered'])
        finally:proceed.set();client.close()

    def test_stream_observer_exception_still_disposes_and_closes_normally(self):
        self.front.generated=self.codec.encode('a')+[248046]
        self.attach(request_limit=1);failure=OSError('observer only')
        offer=H.Delivery.offer
        def failing_offer(delivery,data):
            if b'"content":"a"' in data:raise failure
            return offer(delivery,data)
        with patch.object(H.Delivery,'offer',failing_offer):
            self.start();status,raw=self.stream_request()
            self.assertEqual(status,200);self.assertNotIn(b'[DONE]',raw)
            self.assertTrue(self.finish()['receipt']['passed'])
        self.assertIs(self.chat.last_stream_error,failure)
        self.assertIsNone(self.admission.failure);self.assertIsNone(self.engine.halted_reason)
        self.assertEqual([c[0] for c in self.front.calls],['RUN','SAVE'])
        self.assertEqual(self.front.close_calls,1)
        self.assertFalse(self.server.last_stream_receipt['stream_passed'])

    def test_unprintable_cleanup_cannot_replace_original_incident(self):
        class Unprintable(Exception):
            def __str__(self):raise RuntimeError('formatter failed')
        self.attach();original=OSError('native primary');close=self.server.server_close
        self.admission._fail(original)
        self.server.server_close=lambda:(_ for _ in ()).throw(Unprintable())
        try:
            self.start();self.assertIs(self.finish()['error'],original)
            self.assertEqual(self.front.close_calls,0)
            self.assertTrue(any('message unavailable' in note for note in original.__notes__))
        finally:self.server.server_close=close

    def test_stream_proxy_original_boundary_failure_captured(self):
        self.attach();original=OSError('stream boundary poll failure');count=0
        def poll():
            nonlocal count
            count+=1
            if count==2:raise original
            return None
        self.front.process.poll=poll;self.start()
        status,raw=self.stream_request()
        self.assertEqual(status,200);self.assertNotIn(b'[DONE]',raw)
        self.assertIs(self.finish()['error'],original);self.assertEqual(self.front.close_calls,0)

    def test_stream_proxy_serialization_error_is_retained(self):
        self.attach()
        self.chat._stream_complete=lambda *args:{'completion':{1},'stream_passed':True}
        self.start();status,raw=self.stream_request()
        self.assertEqual(status,200);self.assertNotIn(b'[DONE]',raw)
        error=self.finish()['error']
        self.assertIsInstance(error,TypeError);self.assertIs(error,self.admission.failure)
        self.assertFalse(self.front.calls);self.assertEqual(self.front.close_calls,0)

    def test_exact_new_server_and_pinned_dependencies(self):
        self.attach();old=chat_http.make_server(self.life.service)
        try:
            with self.assertRaisesRegex(L.LifecycleError,'exact serial streaming'):
                self.life.serve(old)
            self.assertFalse(self.life._used)
        finally:old.server_close()
        with self.assertRaisesRegex(L.LifecycleError,'exact serial HTTP'):
            canonical.SessionLifecycle.serve(self.life,self.server)
        self.assertFalse(self.life._used)
        with patch.object(L,'PINS',((canonical,L.HERE.parent/'session_lifecycle.py','0'*64),)):
            with self.assertRaisesRegex(L.LifecycleError,'dependency changed'):L.verify_dependencies()
        class DerivedService(S.StreamingChatService):pass
        alternate=object.__new__(DerivedService)
        with self.assertRaisesRegex(L.LifecycleError,'exact streaming'):
            L.StreamingSessionLifecycle(alternate,self.admission)
        self.life.request_close();self.start()
        self.assertTrue(self.finish()['receipt']['passed']);self.assertEqual(self.front.close_calls,1)


if __name__=='__main__':unittest.main(verbosity=2)
