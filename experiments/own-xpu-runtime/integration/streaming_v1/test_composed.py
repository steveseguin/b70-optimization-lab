"""Real local sockets/service/codec/engine; intercepted native/store only.

Recorded tokens are replayed, not generated. The tests establish Python stack
composition and ordering, not device correctness, admission or performance.
"""
from contextlib import contextmanager
import json
from pathlib import Path
import socket
import struct
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chat_codec as C
from streaming_v1 import http as H
from streaming_v1 import test_service as F
from test_chat_http import wire


class ComposedTests(unittest.TestCase):
    make = F.ServiceTests.make
    payload = F.ServiceTests.payload

    @classmethod
    def setUpClass(cls):
        F.ServiceTests.setUpClass.__func__(cls)

    @contextmanager
    def serving(self, service, releases=()):
        server=H.make_server(service)
        thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01})
        thread.start()
        try:
            yield server
        finally:
            for event in releases:event.set()
            server.shutdown()
            server.server_close()
            thread.join(2)
            self.assertFalse(thread.is_alive(),'test HTTP handler retained')

    @contextmanager
    def client(self, server, payload):
        connection=socket.create_connection(server.server_address,timeout=2)
        try:
            connection.sendall(wire(json.dumps(payload,ensure_ascii=False).encode()))
            yield connection
        finally:
            connection.close()

    def receive(self, client):
        parts=[]
        while part:=client.recv(65536):parts.append(part)
        return b''.join(parts)

    def events(self, raw):
        header,body=raw.split(b'\r\n\r\n',1)
        self.assertIn(b'200 OK',header)
        self.assertIn(b'text/event-stream',header)
        lines=[line[6:] for line in body.splitlines() if line.startswith(b'data: ')]
        done=[i for i,line in enumerate(lines) if line==b'[DONE]']
        records=[json.loads(line) for line in lines if line!=b'[DONE]']
        return records,done,lines

    def test_recorded_p199_six_outputs_over_sse_match_nonstream_and_usage(self):
        packet=C.HERE.parent/'stage2/packet199-chat-parking'
        rows=json.loads((packet/'evidence/device-p199-chat-A-a/http-requests.json').read_text())
        vectors={row['name']:row for row in json.loads((packet/'vectors.json').read_text())['rows']}
        for row in rows:
            with self.subTest(name=row['name']):
                service,engine,front,_=self.make(budget=0 if row['name']=='final-b-no-park' else 524288)
                front.generated=row['tokens']
                vector=vectors[row['name']]
                payload=vector['http']['body']|{'model':service.model,'stream':True}
                with self.serving(service) as server:
                    with self.client(server,payload) as client:raw=self.receive(client)
                    events,done,lines=self.events(raw)
                    self.assertEqual(done,[len(lines)-1])
                    self.assertEqual(sum(e['choices'][0]['finish_reason'] is not None for e in events),1)
                    self.assertEqual([x[0] for x in front.calls],['RUN','RELEASE' if row['name']=='final-b-no-park' else 'SAVE'])
                    self.assertEqual(list(front.calls[0][2]),vector['prompt_tokens'])
                    self.assertEqual(front.visible,vector['prompt_tokens']+row['tokens'])
                    text=''.join(e['choices'][0]['delta'].get('content','') for e in events)
                    self.assertEqual(text,row['response']['choices'][0]['message']['content'])
                    self.assertEqual(events[-1]['usage'],row['response']['usage'])
                    self.assertEqual(events[-1]['choices'][0]['finish_reason'],row['response']['choices'][0]['finish_reason'])
                    self.assertTrue(server.last_stream_receipt['native_complete'])
                    self.assertTrue(server.last_stream_receipt['terminal_offered'])
                    with self.client(server,payload|{'stream':False}) as client:ordinary=self.receive(client)
                    normal=json.loads(ordinary.split(b'\r\n\r\n',1)[1])
                    self.assertEqual(normal['choices'][0]['message']['content'],text)
                    self.assertEqual(normal['usage'],events[-1]['usage'])
                    self.assertEqual(front.completed,2)
                    self.assertEqual(sum(c[0] in ('SAVE','RELEASE') for c in front.calls),2)
                    self.assertIsNone(front.pending);self.assertIsNone(engine.halted_reason)

    def test_sse_content_arrives_before_save_or_release_then_terminal_after(self):
        for budget in (0,524288):
            with self.subTest(budget=budget):
                service,_,front,_=self.make(budget=budget)
                front.generated=self.codec.encode('a')+[248046]
                entered,proceed=threading.Event(),threading.Event()
                method='save' if budget else 'release';original=getattr(front,method)
                def gated(*args):
                    entered.set()
                    if not proceed.wait(2):raise RuntimeError('test disposition gate timeout')
                    return original(*args)
                setattr(front,method,gated)
                with self.serving(service,(proceed,)) as server:
                    with self.client(server,self.payload(len(front.generated))) as client:
                        with client.makefile('rb') as stream:
                            headers=[]
                            while (line:=stream.readline())!=b'\r\n':
                                self.assertTrue(line);headers.append(line)
                            role=stream.readline();self.assertEqual(stream.readline(),b'\n')
                            early=stream.readline();self.assertEqual(stream.readline(),b'\n')
                            self.assertTrue(entered.wait(1))
                            self.assertEqual(json.loads(early[6:])['choices'][0]['delta']['content'],'a')
                            self.assertNotIn(b'[DONE]',role+early)
                            self.assertEqual([c[0] for c in front.calls],['RUN'])
                            self.assertEqual(front.state,'awaiting-disposition')
                            proceed.set();rest=stream.read()
                            self.assertTrue(rest.endswith(b'data: [DONE]\n\n'))
                            final=json.loads(rest.splitlines()[0][6:])
                            self.assertEqual(final['choices'][0]['finish_reason'],'stop')
                            self.assertEqual(final['usage']['completion_tokens'],len(front.generated))
                            self.assertEqual([c[0] for c in front.calls],['RUN',method.upper()])

    def test_byte_split_unicode_over_real_socket_preserves_stable_prefixes(self):
        service,_,front,_=self.make(budget=0)
        expected=' café 🙂 e\u0301\n'
        front.generated=[self.byte_ids[b] for b in expected.encode()]+[248046]
        with self.serving(service) as server:
            with self.client(server,self.payload(len(front.generated))) as client:raw=self.receive(client)
            events,done,lines=self.events(raw);text=''
            for event in events:
                text+=event['choices'][0]['delta'].get('content','')
                self.assertTrue(expected.startswith(text))
            self.assertEqual(text,expected);self.assertNotIn('�',text)
            self.assertEqual(done,[len(lines)-1])
            self.assertEqual(events[-1]['usage']['completion_tokens'],len(front.generated))
            self.assertEqual([c[0] for c in front.calls],['RUN','RELEASE'])

    def test_native_save_failure_has_no_terminal_or_done_and_halts_next_http(self):
        service,engine,front,_=self.make()
        front.generated=self.codec.encode('a')+[248046];front.ambiguous_save=True
        with self.serving(service) as server:
            with self.client(server,self.payload(len(front.generated))) as client:raw=self.receive(client)
            events,done,_=self.events(raw)
            self.assertFalse(done)
            self.assertTrue(all(e['choices'][0]['finish_reason'] is None for e in events))
            self.assertTrue(server.intake_halted);self.assertIsNotNone(service.halted_reason)
            self.assertIsNotNone(engine.halted_reason)
            self.assertFalse(server.last_stream_receipt['native_complete'])
            self.assertEqual([c[0] for c in front.calls],['RUN','SAVE'])
            with self.client(server,self.payload(len(front.generated))) as client:refused=self.receive(client)
            self.assertIn(b'503',refused.split(b'\r\n',1)[0])
            self.assertEqual(front.completed,1)

    def test_peer_disconnect_during_native_run_preserves_engine_disposition(self):
        for budget in (0,524288):
            with self.subTest(budget=budget):
                service,engine,front,_=self.make(budget=budget)
                front.generated=[self.byte_ids[b] for b in b'early then more tokens']+[248046]
                entered,proceed=threading.Event(),threading.Event()
                original=front.request
                def gated(request_id,tokens,max_new,restore=None,on_token=None):
                    calls=0
                    def observe(token):
                        nonlocal calls
                        on_token(token);calls+=1
                        if calls==1:
                            entered.set()
                            if not proceed.wait(2):raise RuntimeError('test RUN gate timeout')
                    return original(request_id,tokens,max_new,restore=restore,on_token=observe)
                front.request=gated
                with self.serving(service,(proceed,)) as server:
                    with self.client(server,self.payload(len(front.generated))) as client:
                        self.assertTrue(entered.wait(1))
                        self.assertEqual(front.state,'running')
                        client.setsockopt(socket.SOL_SOCKET,socket.SO_LINGER,struct.pack('ii',1,0))
                        client.close();proceed.set()
                    # shutdown waits for the admitted handler, without another RUN.
                    server.shutdown()
                    self.assertEqual([c[0] for c in front.calls],['RUN','SAVE' if budget else 'RELEASE'])
                    self.assertIsNone(front.pending);self.assertEqual(front.state,'ready')
                    self.assertIsNone(engine.halted_reason);self.assertIsNone(service.halted_reason)
                    self.assertFalse(server.intake_halted)
                    self.assertTrue(server.last_stream_receipt['native_complete'])
                    self.assertFalse(server.last_stream_receipt['terminal_offered'])
                    self.assertIsNotNone(server.last_stream_receipt['delivery']['failed'])


if __name__=='__main__':unittest.main()
