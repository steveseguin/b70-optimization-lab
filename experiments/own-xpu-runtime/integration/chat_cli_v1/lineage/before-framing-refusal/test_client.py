"""CPU-only real sockets/codec/service; synthetic native and checkpoint store."""
from contextlib import contextmanager
import io
import json
import threading
import unittest
from unittest.mock import patch
from chat_cli_v1 import client as C
from streaming_v1 import http as H
from streaming_v1 import test_service as F


class ClientTests(unittest.TestCase):
    make = F.ServiceTests.make
    @classmethod
    def setUpClass(cls): F.ServiceTests.setUpClass.__func__(cls)

    @contextmanager
    def serving(self, service, release=None):
        server=H.make_server(service)
        thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.005});thread.start()
        try: yield 'http://127.0.0.1:'+str(server.server_address[1]),server
        finally:
            if release:release.set()
            server.shutdown();server.server_close();thread.join(2)
            self.assertFalse(thread.is_alive())

    def conversation(self,endpoint,**kw):
        return C.Conversation(endpoint,model='synthetic-owner-real-codec',session='cli-session',**kw)

    def test_actual_unicode_stream_ordinary_parity_and_multiturn_history(self):
        for stream in (True,False):
            service,engine,front,_=self.make();text='café 🙂\n'
            front.generated=[self.byte_ids[b] for b in text.encode()]+[248046]
            with self.serving(service) as (endpoint,server):
                chat=self.conversation(endpoint,stream=stream,maximum=32);seen=[]
                result=chat.ask('Say hello.',on_delta=seen.append)
                self.assertEqual(''.join(seen),text)
                self.assertEqual(result['usage']['completion_tokens'],len(front.generated))
                self.assertEqual([x[0] for x in front.calls],['RUN','SAVE'])
                self.assertEqual(chat.history,[{'role':'user','content':'Say hello.'},{'role':'assistant','content':text}])
                front.generated=self.codec.encode('yes')+[248046]
                chat.ask('Continue.')
                self.assertEqual(len(chat.history),4)
                self.assertEqual(list(front.calls[2][2]),self.codec.encode(self.codec.render(chat.history[:3])))
                changed=chat.history;changed[0]['content']='mutated'
                self.assertEqual(chat.history[0]['content'],'Say hello.')

    def test_delta_received_before_release_and_history_waits_for_terminal(self):
        service,engine,front,_=self.make(budget=0)
        front.generated=self.codec.encode('first')+[248046]
        entered,release,observed,finished=(threading.Event() for _ in range(4))
        original=front.release
        def delayed(*args,**kwargs):
            entered.set()
            if not release.wait(2):raise RuntimeError('fixture timeout')
            return original(*args,**kwargs)
        front.release=delayed;outcomes=[]
        with self.serving(service,release) as (endpoint,server):
            chat=self.conversation(endpoint,maximum=16)
            def ask():
                try:outcomes.append(chat.ask('Hello',on_delta=lambda text:observed.set()))
                except BaseException as error:outcomes.append(error)
                finally:finished.set()
            caller=threading.Thread(target=ask);caller.start()
            try:
                self.assertTrue(entered.wait(1));self.assertTrue(observed.wait(1))
                self.assertFalse(finished.is_set());self.assertEqual(chat.history,[])
            finally:release.set();caller.join(3)
            self.assertFalse(caller.is_alive());self.assertIsInstance(outcomes[0],dict)
            self.assertEqual([x[0] for x in front.calls],['RUN','RELEASE'])

    def test_context_refusal_has_no_native_request_no_history_no_retry(self):
        service,_,front,_=self.make()
        with self.serving(service) as (endpoint,server):
            chat=self.conversation(endpoint)
            with self.assertRaises(C.HTTPFailure) as raised:chat.ask('hello '*5000)
            self.assertEqual(raised.exception.status,400)
            self.assertEqual(front.calls,[]);self.assertEqual(chat.history,[])
            with self.assertRaisesRegex(C.Refusal,'halted'):chat.ask('short')
            self.assertEqual(front.calls,[])

    def test_save_failure_preserves_partial_and_halts_client(self):
        service,engine,front,_=self.make()
        front.generated=self.codec.encode('partial')+[248046];front.ambiguous_save=True
        with self.serving(service) as (endpoint,server):
            chat=self.conversation(endpoint);seen=[]
            with self.assertRaises(C.Refusal) as raised:chat.ask('Hello',on_delta=seen.append)
            self.assertEqual(''.join(seen),'partial')
            self.assertEqual(raised.exception.client_partial_response['partial_text'],'partial')
            self.assertEqual(chat.history,[]);self.assertIs(chat.failure,raised.exception)
            self.assertIsNotNone(engine.halted_reason)
            self.assertEqual([x[0] for x in front.calls],['RUN','SAVE'])

    def test_sink_disconnect_keeps_server_release(self):
        service,engine,front,_=self.make(budget=0)
        front.generated=self.codec.encode('hello')+[248046];original=BrokenPipeError('sink gone')
        with self.serving(service) as (endpoint,server):
            chat=self.conversation(endpoint)
            with self.assertRaises(BrokenPipeError) as raised:
                chat.ask('Hello',on_delta=lambda text:(_ for _ in ()).throw(original))
            self.assertIs(raised.exception,original);self.assertEqual(chat.history,[])
        self.assertEqual([x[0] for x in front.calls],['RUN','RELEASE']);self.assertIsNone(engine.halted_reason)

    def test_local_bounds_no_network_no_truncation(self):
        chat=self.conversation('http://127.0.0.1:1')
        with patch.object(C,'exchange') as transport:
            for text in ('a'*65537,'\x00'*12000):
                with self.assertRaises(C.Refusal):chat.ask(text)
            self.assertIsNone(chat.failure);self.assertEqual(chat.history,[])
            chat.turns=16
            with self.assertRaisesRegex(C.Refusal,'sixteen'):chat.ask('hello')
            transport.assert_not_called()
        for endpoint in ('http://localhost:80','https://127.0.0.1:80','http://127.0.0.1:80/x','http://user@127.0.0.1:80'):
            with self.assertRaises(C.Refusal):self.conversation(endpoint)

    def test_cli_one_shot_and_stdin_actual_server(self):
        for single in (True,False):
            service,_,front,_=self.make(budget=0);front.generated=self.codec.encode('yes')+[248046]
            with self.serving(service) as (endpoint,server):
                stdout,stderr=io.StringIO(),io.StringIO()
                args=['--endpoint',endpoint,'--model',service.model,'--session','demo','--max-tokens','16']
                if single:args+=['--prompt','hello']
                rc=C.main(args,stdin=io.StringIO('hello\n'),stdout=stdout,stderr=stderr)
                self.assertEqual(rc,0);self.assertEqual(stdout.getvalue(),'yes\n')
                self.assertIn('output tokens',stderr.getvalue())
                self.assertEqual([x[0] for x in front.calls],['RUN','RELEASE'])

    def test_cli_partial_failure_notice(self):
        stdout,stderr=io.StringIO(),io.StringIO()
        def failed(*args,**kwargs):kwargs['on_delta']('partial');raise OSError('gone')
        with patch.object(C.Conversation,'ask',side_effect=failed):
            rc=C.main(['--endpoint','http://127.0.0.1:1','--model','m','--session','s','--prompt','hi'],
                      stdin=io.StringIO(),stdout=stdout,stderr=stderr)
        self.assertEqual(rc,1);self.assertEqual(stdout.getvalue(),'partial');self.assertIn('partial/unconfirmed',stderr.getvalue())


class ParserTests(unittest.TestCase):
    def frames(self):
        base={'id':'chatcmpl-h'+'a'*32+'-'+'b'*16,'object':'chat.completion.chunk','created':123,'model':'m'}
        def frame(delta,reason=None,**extra):
            return base|{'choices':[{'index':0,'delta':delta,'finish_reason':reason}]}|extra
        return [frame({'role':'assistant','content':''}),frame({'content':'é🙂'}),
                frame({},'stop',usage={'prompt_tokens':10,'completion_tokens':3,'total_tokens':13})]
    def raw(self,events=None):
        return b''.join(b'data: '+json.dumps(e,ensure_ascii=False).encode()+b'\n\n' for e in events or self.frames())+b'data: [DONE]\n\n'
    def parse(self,raw):
        class Socket:
            def __init__(self):self.timeouts=[]
            def settimeout(self,t):self.timeouts.append(t)
        class Reply:
            status=200
            def __init__(self):self.fp=io.BytesIO(raw)
            def getheader(self,name):return 'text/event-stream; charset=utf-8'
            def read1(self,n):return self.fp.read(min(n,1))
        sock=Socket();seen=[]
        result=C.read_sse(Reply(),maximum=8,receive_socket=sock,model='m',on_delta=seen.append,deadline=C.time.monotonic()+2)
        return result,sock,seen
    def test_byte_split_unicode_and_retained_socket_timeout(self):
        result,sock,seen=self.parse(self.raw())
        self.assertEqual(seen,['é🙂']);self.assertTrue(result['done']);self.assertGreater(len(sock.timeouts),10)
        self.assertTrue(all(0<t<=2 for t in sock.timeouts))
    def test_malformed_frames_partial_and_bounds(self):
        drift=self.frames();drift[1]['created']=124
        cases=[self.raw().replace(b'\xc3\xa9',b'\xff'),self.raw().replace(b'"created": 123',b'"created": 123, "created": 123',1),
               self.raw(drift),self.raw().replace(b'data: [DONE]\n\n',b''),self.raw()+b'x',
               self.raw().replace(b'data: [DONE]\n\n',b'data: {}\n\n'),b'data: '+b'x'*8193+b'\n\n']
        for raw in cases:
            with self.subTest(size=len(raw)):
                with self.assertRaises((C.Refusal,UnicodeError)) as raised:self.parse(raw)
                self.assertFalse(raised.exception.client_partial_response['sse_validated'])
                self.assertLessEqual(len(raised.exception.client_partial_response['raw_sse_base64']),4*((C.SSE_LIMIT+2)//3))
    def test_usage_arithmetic_and_bounds(self):
        body=self.parse(self.raw())[0]['body'];self.assertIs(C.validate_completion(body,'m',8),body)
        for usage in ({'prompt_tokens':10,'completion_tokens':3,'total_tokens':14},
                      {'prompt_tokens':True,'completion_tokens':3,'total_tokens':4},
                      {'prompt_tokens':4096,'completion_tokens':3,'total_tokens':4099}):
            with self.assertRaises(C.Refusal):C.validate_completion(body|{'usage':usage},'m',8)
    def test_response_close_preserves_original_detached_socket_error(self):
        original=OSError('original receive');closed=[]
        class Response:
            status=200
            def getheader(self,name):return 'text/event-stream; charset=utf-8'
            def read1(self,n):raise original
            def close(self):closed.append('response');raise OSError('secondary close')
        class Socket:
            def settimeout(self,t):pass
        class Connection:
            def __init__(self,*a,**kw):self.sock=Socket()
            def request(self,*a,**kw):pass
            def getresponse(self):self.sock=None;return Response()
            def close(self):closed.append('connection')
        with patch.object(C.http.client,'HTTPConnection',Connection):
            with self.assertRaises(OSError) as raised:
                C.exchange('http://127.0.0.1:1',{'model':'m','stream':True,'max_tokens':8},'s',lambda x:None)
        self.assertIs(raised.exception,original);self.assertEqual(closed,['response','connection'])
        self.assertTrue(any('secondary close' in n for n in original.__notes__))


class DeadlineTests(unittest.TestCase):
    def test_slow_header_absolute_deadline(self):
        tick=[0.0]
        class File:
            def read1(self,n):tick[0]+=.4;return b'H'
            def flush(self):pass
            def close(self):pass
        class Socket:
            def makefile(self,*args,**kwargs):return File()
            def settimeout(self,t):self.timeout=t
        response=C.DeadlineResponse(Socket(),deadline=1.0)
        with patch.object(C.time,'monotonic',lambda:tick[0]):
            with self.assertRaisesRegex(C.Refusal,'header deadline'):response.begin()
        self.assertLess(tick[0],1.5);response.close()

    def test_slow_partial_line_body_deadline_preserves_bytes(self):
        tick=[0.0]
        class Reply:
            status=200
            def getheader(self,name):return 'text/event-stream; charset=utf-8'
            def read1(self,n):tick[0]+=.4;return b'd'
        class Socket:
            def settimeout(self,t):pass
        with patch.object(C.time,'monotonic',lambda:tick[0]):
            with self.assertRaisesRegex(C.Refusal,'deadline') as raised:
                C.read_sse(Reply(),maximum=8,receive_socket=Socket(),model='m',on_delta=lambda x:None,deadline=1)
        self.assertEqual(C.base64.b64decode(raised.exception.client_partial_response['raw_sse_base64']),b'ddd')
        self.assertLess(tick[0],1.5)

    def test_aggregate_header_bound(self):
        class Socket:
            def makefile(self,*args,**kwargs):return io.BytesIO(b'HTTP/1.0 200 OK\r\n'+b'X: '+b'a'*65000+b'\r\nY: '+b'b'*1000+b'\r\n\r\n')
            def settimeout(self,t):pass
        response=C.DeadlineResponse(Socket(),deadline=C.time.monotonic()+5)
        with self.assertRaisesRegex(C.Refusal,'aggregate header'):response.begin()
        response.close()

if __name__=='__main__':unittest.main()
