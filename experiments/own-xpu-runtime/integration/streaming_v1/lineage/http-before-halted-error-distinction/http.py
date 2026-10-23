"""Experimental serial loopback SSE; no owner startup or live admission.

The frozen nonstream adapter supplies bounded header parsing and GET routes.
The explicit subclass cannot pass the old lifecycle's exact server-type gate.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

import chat_http as parent
from chat_service import ChatRequestError
from streaming_v1.delivery import Delivery, sse_event

PARENT = Path(__file__).resolve().parents[1] / 'chat_http.py'
PARENT_SHA = '50ea09e9453c1d8424f169d13f1aa9cdc878e37061e1b8ccca3119097a2b9718'


def verify_parent():
    if (Path(parent.__file__).resolve() != PARENT or
            hashlib.sha256(PARENT.read_bytes()).hexdigest() != PARENT_SHA):
        raise RuntimeError('streaming HTTP requires the pinned canonical adapter')


class StreamingServer(parent._Server):
    def __init__(self, service, address):
        super().__init__(service, address)
        self.RequestHandlerClass = StreamingHandler
        self.last_stream_receipt = None


class StreamingHandler(parent._Handler):
    def _payload(self):
        # Narrow copy of the pinned parent's admission parser. All inherited
        # header/framing bounds still apply before a body is read.
        length = self._framing(body=True)
        sessions = self.headers.get_all('X-Ownrt-Session', [])
        if (len(sessions) != 1 or parent._SESSION.fullmatch(sessions[0]) is None
                or sessions[0].endswith('.lock')):
            raise parent._InputError('invalid session')
        content_types = self.headers.get_all('Content-Type', [])
        if (len(content_types) != 1 or content_types[0].lower() not in
                ('application/json', 'application/json; charset=utf-8')):
            raise parent._InputError('JSON content type required')
        deadline = time.monotonic() + parent.SOCKET_TIMEOUT
        parts, remaining = [], length
        while remaining:
            timeout = deadline - time.monotonic()
            if timeout <= 0:
                raise parent._InputError('body deadline')
            self.connection.settimeout(min(parent.SOCKET_TIMEOUT, timeout))
            chunk = self.rfile.read1(min(remaining, 65536))
            if not chunk:
                raise parent._InputError('incomplete body')
            parts.append(chunk)
            remaining -= len(chunk)
        payload = json.loads(b''.join(parts).decode('utf-8'), object_pairs_hook=parent._pairs,
                             parse_constant=parent._constant, parse_float=parent._float)
        pending = [(payload, 0)]
        while pending:
            value, depth = pending.pop()
            if depth > 64:
                raise parent._InputError('JSON nesting bound')
            if isinstance(value, dict):
                pending.extend((v, depth + 1) for v in value.values())
            elif isinstance(value, list):
                pending.extend((v, depth + 1) for v in value)
        return payload, sessions[0]

    def do_POST(self):
        if self.path != '/v1/chat/completions':
            self._reply(404, {'error': {'message': 'route not found'}})
            return
        if self.server.intake_state() != 'ready':
            self._reply(503, {'error': {'message': 'chat intake unavailable'}})
            return
        try:
            payload, session = self._payload()
        except (ValueError, UnicodeError, RecursionError, OSError):
            self._reply(400, {'error': {'message': 'request refused'}})
            return
        streaming = type(payload) is dict and payload.get('stream') is True
        try:
            # Refuse bad payloads before committing an SSE status/header. The
            # service revalidates under its own serial lock before native RUN.
            self.server.service.validate(payload)
        except ChatRequestError:
            self._reply(400, {'error': {'message': 'chat request refused'}})
            return
        except Exception:
            self.server.intake_halted = True
            self._reply(503, {'error': {'message': 'chat intake unavailable'}})
            return
        request_id = self.server.next_request_id()
        if not streaming:
            try:
                result = self.server.service.complete(payload, session=session, request_id=request_id)
                self._reply(200, result)
            except ChatRequestError:
                self._reply(400, {'error': {'message': 'chat request refused'}})
            except Exception:
                self.server.intake_halted = True
                self._reply(503, {'error': {'message': 'chat intake unavailable'}})
            return
        self._stream(payload, session, request_id)

    def _stream(self, payload, session, request_id):
        self.close_connection = True
        self.connection.setblocking(False)
        delivery = Delivery(self.connection)
        created = int(time.time())
        model, response_id = self.server.service.model, 'chatcmpl-' + request_id

        def chunk(delta, *, finish=None, usage=None):
            value = dict(id=response_id, object='chat.completion.chunk', created=created, model=model,
                         choices=[dict(index=0, delta=delta, finish_reason=finish)])
            if usage is not None:
                value['usage'] = usage
            return sse_event(value)

        result = None
        native_complete = False
        terminal_offered = False
        try:
            if not delivery.offer(b'HTTP/1.0 200 OK\r\nContent-Type: text/event-stream; charset=utf-8\r\n'
                                  b'Cache-Control: no-cache\r\nConnection: close\r\n\r\n'):
                return  # No native request yet.
            if not delivery.offer(chunk({'role': 'assistant', 'content': ''})):
                return
            result = self.server.service.stream(payload, session=session, request_id=request_id,
                on_delta=lambda text: delivery.offer(chunk({'content': text})))
            native_complete = True  # stream returns only after SAVE/RELEASE.
            completion = result['completion']
            if completion['id'] != response_id or completion['model'] != model:
                raise RuntimeError('stream response identity changed')
            if result['stream_passed'] is True and delivery.failed is None:
                if delivery.offer(chunk({}, finish=completion['choices'][0]['finish_reason'],
                                        usage=completion['usage'])):
                    terminal_offered = delivery.offer(b'data: [DONE]\n\n')
            else:
                delivery.abandon('stream observer failed' if delivery.failed is None else delivery.failed)
            # Only this post-disposition phase may wait for a slow socket.
            delivery.finish_delivery()
        except Exception:
            self.server.intake_halted = True
            delivery.abandon('stream runtime failure')
            # Never append a JSON error or false DONE to a partial event stream.
        finally:
            self.server.last_stream_receipt = dict(native_complete=native_complete,
                stream_passed=result is not None and result.get('stream_passed') is True,
                terminal_offered=terminal_offered, delivery=delivery.receipt(),
                peer_receipt_proven=False)


def make_server(service, address=('127.0.0.1', 0)):
    verify_parent()
    if (type(address) is not tuple or len(address) != 2 or address[0] != '127.0.0.1'
            or type(address[1]) is not int or not 0 <= address[1] <= 65535):
        raise ValueError('literal IPv4 loopback and valid port required')
    if (type(getattr(service, 'model', None)) is not str or
            not all(callable(getattr(service, name, None)) for name in ('validate', 'complete', 'stream'))):
        raise ValueError('explicit streaming chat service required')
    return StreamingServer(service, address)
