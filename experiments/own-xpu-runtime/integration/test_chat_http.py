"""Real loopback sockets, synthetic service only; no owner/native execution."""
import json
import socket
import struct
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from chat_service import ChatRequestError
import chat_http as H


class Service:
    model = 'test-quantized'
    halted_reason = None

    def __init__(self):
        self.calls = []
        self.dispositions = []
        self.failure = None
        self.engine = SimpleNamespace(front=SimpleNamespace(state='ready'))
        self.started, self.proceed, self.finished = threading.Event(), threading.Event(), threading.Event()
        self.proceed.set()

    def complete(self, payload, **kwargs):
        self.calls.append((payload, kwargs))
        self.started.set()
        if not self.proceed.wait(2):
            raise RuntimeError('test synchronization timeout')
        if self.failure:
            raise self.failure
        if not isinstance(payload, dict) or payload.get('stream'):
            raise ChatRequestError('client bad option /private/path')
        self.dispositions.append('saved')
        self.finished.set()
        return {'id': 'chatcmpl-' + kwargs['request_id'], 'choices': [
            {'message': {'role': 'assistant', 'content': ' yes é\n'}}]}


def wire(body=b'{}', headers=None, path='/v1/chat/completions'):
    headers = ([(b'Content-Length', str(len(body)).encode()),
                (b'Content-Type', b'application/json'), (b'X-Ownrt-Session', b'chat-1')]
               if headers is None else headers)
    return b'POST ' + path.encode() + b' HTTP/1.1\r\nHost: localhost\r\n' + b''.join(
        k + b': ' + v + b'\r\n' for k, v in headers) + b'\r\n' + body


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.service = Service()
        self.server = H.make_server(self.service)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={'poll_interval': .01}, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.service.proceed.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.assertFalse(self.thread.is_alive())

    def exchange(self, request, *, eof=False):
        with socket.create_connection(self.server.server_address, timeout=2) as client:
            client.sendall(request)
            if eof:
                client.shutdown(socket.SHUT_WR)
            chunks = []
            while chunk := client.recv(65536):
                chunks.append(chunk)
        raw = b''.join(chunks)
        header, body = raw.split(b'\r\n\r\n', 1)
        self.assertTrue(header.startswith(b'HTTP/1.0 '))
        self.assertIn(b'Connection: close', header)
        return int(header.split()[1]), json.loads(body)

    def test_valid_unique_requests_and_metadata_routes(self):
        for _ in range(2):
            code, body = self.exchange(wire())
            self.assertEqual(code, 200)
            self.assertEqual(body['choices'][0]['message']['content'], ' yes é\n')
        ids = [call[1]['request_id'] for call in self.service.calls]
        self.assertEqual(len(set(ids)), 2)
        self.assertTrue(all(len(i) <= 64 and '/' not in i for i in ids))
        self.assertEqual(self.service.calls[0][1]['session'], 'chat-1')
        code, body = self.exchange(b'GET /v1/models HTTP/1.0\r\n\r\n')
        self.assertEqual((code, body['data'][0]['id']), (200, 'test-quantized'))
        code, body = self.exchange(b'GET /health HTTP/1.0\r\n\r\n')
        self.assertEqual((code, body['status']), (200, 'ready'))

    def test_invalid_framing_never_forwards(self):
        base = [(b'Content-Type', b'application/json'), (b'X-Ownrt-Session', b's1')]
        variants = [base, base + [(b'Content-Length', b'2'), (b'Content-Length', b'2')],
                    base + [(b'Content-Length', b'2,2')], base + [(b'Content-Length', b'+2')],
                    base + [(b'Content-Length', b'-1')], base + [(b'Content-Length', b'524289')],
                    base + [(b'Content-Length', b'2'), (b'Transfer-Encoding', b'identity')],
                    base + [(b'Content-Length', b'2'), (b'Transfer-Encoding', b'chunked')],
                    base + [(b'Content-Length', b'2'), (b'Expect', b'100-continue')],
                    base + [(b'Content-Length', b'2'), (b'Transfer-Encoding ', b'chunked')]]
        for headers in variants:
            with self.subTest(headers=headers):
                self.assertEqual(self.exchange(wire(headers=headers))[0], 400)
        self.assertEqual(len(self.service.calls), 0)

    def test_session_missing_duplicate_unicode_and_paths_refuse(self):
        base = [(b'Content-Length', b'2'), (b'Content-Type', b'application/json')]
        values = [[], [(b'X-Ownrt-Session', b'a')] * 2]
        values += [[(b'X-Ownrt-Session', v)] for v in
                   [b'../a', b'/tmp/a', b'a/b', b'a\\b', b'a.lock', b'a' * 40, b'', b'\xe9', b'a\r\n b']]
        for extra in values:
            self.assertEqual(self.exchange(wire(headers=base + extra))[0], 400)
        self.assertEqual(len(self.service.calls), 0)

    def test_bad_json_never_forwards(self):
        for body in [b'{', b'{"x":1,"x":2}', b'{"x":{"a":1,"a":2}}',
                     b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}', b'{"x":1e999}',
                     b'\xff', b'[' * 1100 + b']' * 1100]:
            with self.subTest(body=body[:40]):
                self.assertEqual(self.exchange(wire(body))[0], 400)
        self.assertEqual(len(self.service.calls), 0)

    def test_incomplete_body_refuses_and_intake_recovers(self):
        request = wire().replace(b'Content-Length: 2', b'Content-Length: 20')
        self.assertEqual(self.exchange(request, eof=True)[0], 400)
        self.assertEqual(len(self.service.calls), 0)
        self.assertEqual(self.exchange(wire())[0], 200)

    def test_dribbling_header_has_absolute_deadline(self):
        with patch.object(H, 'SOCKET_TIMEOUT', .15):
            with socket.create_connection(self.server.server_address, timeout=2) as client:
                client.sendall(b'POST /v1/chat/completions HTTP/1.1\r\nX-Dribble: ')
                started = time.monotonic()
                for _ in range(6):
                    time.sleep(.04)  # Every byte arrives before the idle timeout.
                    try:
                        client.sendall(b'a')
                    except OSError:
                        break
                raw = client.recv(65536)
                self.assertIn(b' 400 ', raw)
                self.assertLess(time.monotonic() - started, .8)
        self.assertEqual(len(self.service.calls), 0)
        self.assertEqual(self.exchange(wire())[0], 200)

    def test_header_byte_cap_and_http09_refuse(self):
        request = b'GET /health HTTP/1.0\r\n' + b'X: ' + b'a' * 65536 + b'\r\n\r\n'
        self.assertEqual(self.exchange(request)[0], 400)
        self.assertEqual(self.exchange(b'GET /health\r\n\r\n')[0], 400)
        self.assertEqual(len(self.service.calls), 0)

    def test_body_timeout_is_bounded_and_no_forward(self):
        with patch.object(H, 'SOCKET_TIMEOUT', .1):
            request = wire().replace(b'Content-Length: 2', b'Content-Length: 20')
            self.assertEqual(self.exchange(request)[0], 400)
        self.assertEqual(len(self.service.calls), 0)

    def test_chat_input_error_recoverable_no_private_error_text(self):
        code, body = self.exchange(wire(b'{"stream":true}'))
        self.assertEqual(code, 400)
        self.assertNotIn('/private', json.dumps(body))
        self.assertEqual(self.exchange(wire())[0], 200)
        self.assertEqual(self.service.dispositions, ['saved'])

    def test_runtime_failure_halts_intake_without_retry(self):
        self.service.failure = RuntimeError('/private/checkpoint failure')
        for _ in range(2):
            code, body = self.exchange(wire())
            self.assertEqual(code, 503)
            self.assertNotIn('/private', json.dumps(body))
        self.assertEqual(len(self.service.calls), 1)
        code, body = self.exchange(b'GET /health HTTP/1.0\r\n\r\n')
        self.assertEqual((code, body['status']), (503, 'halted'))
        self.assertEqual(self.service.dispositions, [])

    def test_service_halt_takes_precedence_over_input_error_type(self):
        def failed(payload, **kwargs):
            self.service.halted_reason = '/private/runtime-path'
            raise ChatRequestError('runtime wrapped as input')
        self.service.complete = failed
        code, body = self.exchange(wire())
        self.assertEqual(code, 503)
        self.assertNotIn('/private', json.dumps(body))

    def test_draining_front_never_accepts_another_request(self):
        self.service.engine.front.state = 'draining'
        self.assertEqual(self.exchange(wire())[0], 503)
        self.assertEqual(len(self.service.calls), 0)
        self.assertEqual(self.exchange(b'GET /health HTTP/1.0\r\n\r\n')[0], 503)

    def test_disconnect_does_not_cancel_normal_save(self):
        self.service.proceed.clear()
        client = socket.create_connection(self.server.server_address, timeout=2)
        client.sendall(wire())
        self.assertTrue(self.service.started.wait(1))
        client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
        client.close()
        self.service.proceed.set()
        self.assertTrue(self.service.finished.wait(1))
        self.assertEqual(self.exchange(wire())[0], 200)
        self.assertEqual(self.service.dispositions, ['saved', 'saved'])
        self.assertFalse(self.server.intake_halted)

    def test_only_literal_loopback_bind_and_fixed_timeout(self):
        for address in [('0.0.0.0', 0), ('localhost', 0), ('::1', 0), ('127.0.0.2', 0),
                        ('127.0.0.1', True), ('127.0.0.1', -1), ['127.0.0.1', 0]]:
            with self.assertRaises(ValueError):
                H.make_server(self.service, address)
        self.assertLessEqual(H.SOCKET_TIMEOUT, 10)

    def test_unknown_route_get_body_and_unsupported_method(self):
        self.assertEqual(self.exchange(wire(path='/other'))[0], 404)
        self.assertEqual(self.exchange(b'GET /health HTTP/1.0\r\nContent-Length: 2\r\n\r\n{}')[0], 400)
        self.assertEqual(self.exchange(b'DELETE /v1/chat/completions HTTP/1.0\r\n\r\n')[0], 400)
        self.assertEqual(len(self.service.calls), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
