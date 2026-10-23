"""Real local HTTP/SSE sockets and an intercepted service; no native owner."""
import json
import socket
import struct
import threading
import unittest
from types import SimpleNamespace

from chat_service import ChatRequestError
from streaming_v1.http import make_server
from test_chat_http import wire


class Service:
    model = 'test-quantized'
    halted_reason = None

    def __init__(self):
        self.engine = SimpleNamespace(front=SimpleNamespace(state='ready'))
        self.started, self.proceed, self.finished = (threading.Event() for _ in range(3))
        self.proceed.set()
        self.calls = 0
        self.disposed = False
        self.fail = False
        self.observer_failed = False

    def validate(self, payload):
        if type(payload) is not dict or payload.get('temperature', 0) != 0:
            raise ChatRequestError('bad request')
        if type(payload.get('stream', False)) is not bool:
            raise ChatRequestError('bad stream')

    def completion(self, request_id):
        return dict(id='chatcmpl-' + request_id, model=self.model,
                    choices=[dict(message=dict(role='assistant', content='early 雪 late'), finish_reason='length')],
                    usage=dict(prompt_tokens=4, completion_tokens=3, total_tokens=7))

    def complete(self, payload, *, session, request_id):
        self.calls += 1
        self.disposed = True
        return self.completion(request_id)

    def stream(self, payload, *, session, request_id, on_delta):
        self.calls += 1
        on_delta('early 雪')
        self.started.set()
        if not self.proceed.wait(2):
            raise RuntimeError('fixture timeout')
        if self.fail:
            raise RuntimeError('native failure')
        on_delta(' late')
        self.disposed = True
        self.finished.set()
        return dict(completion=self.completion(request_id), stream_passed=not self.observer_failed)


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.service = Service()
        self.server = make_server(self.service)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={'poll_interval': .01})
        self.thread.start()

    def tearDown(self):
        self.service.proceed.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.assertFalse(self.thread.is_alive())

    def client(self, payload=None, raw=None):
        client = socket.create_connection(self.server.server_address, timeout=2)
        self.addCleanup(client.close)
        client.sendall(raw if raw is not None else wire(json.dumps(payload or {}).encode()))
        return client

    def receive(self, client):
        parts = []
        while chunk := client.recv(65536): parts.append(chunk)
        return b''.join(parts)

    def test_true_early_sse_and_done_only_after_disposition(self):
        self.service.proceed.clear()
        client = self.client({'stream': True})
        stream = client.makefile('rb')
        self.addCleanup(stream.close)
        headers = []
        while (line := stream.readline()) != b'\r\n': headers.append(line)
        self.assertIn(b'200', headers[0])
        self.assertTrue(any(b'text/event-stream' in x for x in headers))
        first = stream.readline(); self.assertEqual(stream.readline(), b'\n')
        early = stream.readline(); self.assertEqual(stream.readline(), b'\n')
        self.assertIn('early 雪', early.decode())
        self.assertNotIn(b'[DONE]', first + early)
        self.assertFalse(self.service.disposed)
        self.service.proceed.set()
        rest = stream.read()
        self.assertTrue(self.service.disposed)
        events = [json.loads(line[6:]) for line in (first + early + rest).splitlines()
                  if line.startswith(b'data: ') and line != b'data: [DONE]']
        self.assertEqual(''.join(e['choices'][0]['delta'].get('content', '') for e in events), 'early 雪 late')
        self.assertEqual(events[-1]['usage']['completion_tokens'], 3)
        self.assertEqual(events[-1]['choices'][0]['finish_reason'], 'length')
        self.assertTrue(rest.endswith(b'data: [DONE]\n\n'))
        self.assertTrue(self.server.last_stream_receipt['native_complete'])

    def test_invalid_stream_request_is_json_400_before_service(self):
        raw = self.receive(self.client({'stream': True, 'temperature': 1}))
        self.assertIn(b'400', raw.split(b'\r\n')[0])
        self.assertNotIn(b'text/event-stream', raw)
        self.assertEqual(self.service.calls, 0)

    def test_native_failure_never_sends_done_and_halts_intake(self):
        self.service.fail = True
        raw = self.receive(self.client({'stream': True}))
        self.assertIn(b'early', raw)
        self.assertNotIn(b'[DONE]', raw)
        self.assertNotIn(b'"finish_reason":"length"', raw)
        self.assertTrue(self.server.intake_halted)
        self.assertFalse(self.server.last_stream_receipt['native_complete'])

    def test_observer_failure_after_disposition_has_no_false_done(self):
        self.service.observer_failed = True
        raw = self.receive(self.client({'stream': True}))
        self.assertTrue(self.service.disposed)
        self.assertNotIn(b'[DONE]', raw)
        self.assertFalse(self.server.intake_halted)
        self.assertTrue(self.server.last_stream_receipt['native_complete'])

    def test_reader_disconnect_does_not_skip_service_disposition(self):
        self.service.proceed.clear()
        client = self.client({'stream': True})
        self.assertTrue(self.service.started.wait(1))
        client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
        client.close()
        self.service.proceed.set()
        self.assertTrue(self.service.finished.wait(1))
        # Wait for handler completion without issuing another model request.
        self.server.shutdown(); self.thread.join(2)
        self.assertTrue(self.service.disposed)
        self.assertFalse(self.server.intake_halted)
        self.assertTrue(self.server.last_stream_receipt['native_complete'])
        self.assertIsNotNone(self.server.last_stream_receipt['delivery']['failed'])

    def test_nonstream_and_bounded_parser_remain_available(self):
        raw = self.receive(self.client({'stream': False}))
        header, body = raw.split(b'\r\n\r\n', 1)
        self.assertIn(b'200', header)
        self.assertEqual(json.loads(body)['choices'][0]['message']['content'], 'early 雪 late')
        before = self.service.calls
        raw = self.receive(self.client(raw=wire(b'{"stream":true,"stream":false}')))
        self.assertIn(b'400', raw.split(b'\r\n')[0])
        self.assertEqual(self.service.calls, before)

    def test_loopback_only_and_distinct_server_type(self):
        import chat_http
        self.assertIsNot(type(self.server), chat_http._Server)
        for address in [('0.0.0.0', 0), ('localhost', 0), ('127.0.0.1', True)]:
            with self.assertRaises(ValueError): make_server(self.service, address)



if __name__ == '__main__': unittest.main()
