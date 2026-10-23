"""Serial streaming facade over the pinned engine/codec, with no HTTP owner.

Only trusted bounded, nonblocking observers are supported. Their return value
does not attest delivery; the transport must separately check its own status.
Observer exceptions retain normal SAVE/RELEASE, but prohibit a successful stream
result. Decode/native/storage failures halt intake. Nothing here emits DONE.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import time

import chat_service as canonical
from checkpoint_engine import EngineRefusal, valid_id
from streaming_v1 import engine as E, decoder as D

HERE = Path(__file__).resolve().parent
PINS = (
    (canonical, HERE.parent / 'chat_service.py', '368b904558ff1e28f32cd60821f4478538b0db25b3457a506e3f12d3769a4647'),
    (E, HERE / 'engine.py', '522b0cd8d212e5b8d4a9432acb771fa9f67d20b6873fb8fdfdcc587b183a89f5'),
    (D, HERE / 'decoder.py', '3b2ea358c86f423a38dbee16f36281c3cfbc27f08c0f65c6e23ad42d76aa35ac'),
)


def error_view(error):
    try:
        message = str(error)[:2048]
    except BaseException:
        message = '<exception message unavailable>'
    return {'type': type(error).__name__, 'message': message}


class StreamingChatService(canonical.ChatService):
    def __init__(self, engine, parking, codec, *, model, native_stop_token_ids, clock=time.time):
        for module, path, digest in PINS:
            canonical.require(Path(module.__file__).resolve() == path and
                              hashlib.sha256(path.read_bytes()).hexdigest() == digest,
                              'streaming service dependency changed')
        canonical.require(type(engine) is E.StreamingCheckpointEngine,
                          'exact streaming checkpoint engine required')
        E.verify_parent()
        D.verify_codec(codec)
        super().__init__(engine, parking, codec, model=model,
                         native_stop_token_ids=native_stop_token_ids, clock=clock)
        self.last_stream_error = None
        self._stream_active = False

    def validate(self, payload):
        canonical.require(type(payload) is dict, 'chat request must be an object')
        canonical.require(type(payload.get('stream', False)) is bool, 'stream must be boolean')
        return super().validate(dict(payload, stream=False))

    def complete(self, payload, *, session, request_id):
        with self._lock:
            canonical.require(not self._stream_active, 'reentrant stream request refused')
            canonical.require(type(payload) is dict and payload.get('stream', False) is False,
                              'use stream() for streaming requests')
            return super().complete(payload, session=session, request_id=request_id)

    def stream(self, payload, *, session, request_id, on_delta):
        """Return a canonical completion plus explicit observation success.

Completion is returned only after normal disposition, even on delivery failure.
No callback follows its first failure. A failed observer's remaining token bytes
are checked locally after RUN; those checks are never presented as live deltas.
The original observer error remains available as last_stream_error. Runtime
errors propagate unchanged and must be handled by the outer incident owner.
"""
        with self._lock:
            canonical.require(not self._stream_active, 'reentrant stream request refused')
            if self.halted_reason is not None:
                raise RuntimeError('chat intake halted: ' + self.halted_reason)
            canonical.require(callable(on_delta), 'bounded delta observer required')
            canonical.require(type(payload) is dict and payload.get('stream') is True,
                              'stream() requires stream:true')
            messages, maximum, prompt = self.validate(payload)
            canonical.require(self.parking.render == self.codec.render and self.parking.tokenize == self.codec.encode,
                              'parking codec callbacks changed')
            canonical.require(self.codec.terminal_token_ids == self._stop_ids, 'codec stop IDs changed')
            try:
                valid_id(request_id)
                self.parking.checkpoint_id(session, prompt)
            except (EngineRefusal, ValueError) as error:
                raise canonical.ChatRequestError(str(error)) from error
            canonical.require(self.parking.prefix(messages) == prompt,
                              'parking render differs from admitted chat codec')
            self.last_stream_error = None
            self._stream_active = True
            try:
                return self._stream_complete(messages, maximum, prompt, session, request_id, on_delta)
            except BaseException as error:
                self.last_stream_error = error
                self.halted_reason = error_view(error)['message'] or type(error).__name__
                raise
            finally:
                self._stream_active = False

    def _stream_complete(self, messages, maximum, prompt, session, request_id, on_delta):
        decoder = D.TokenDecoder(self.codec, maximum_tokens=maximum)
        created = int(self.clock())
        delivery_error = None

        def observe(token):
            nonlocal delivery_error
            delta = decoder.feed(token)
            if delta:
                try:
                    on_delta(delta)
                except BaseException as error:
                    delivery_error = error
                    raise

        result = self.engine.run_turn(self.parking, session, messages,
                                      request_id=request_id, max_new=maximum, on_token=observe)
        # Narrow copy of the pinned canonical output gates and completion shape.
        generated = result['response']['tokens']
        if (not generated or len(generated) > maximum or
                any(type(i) is not int or not 0 <= i < self.engine.vocab for i in generated)):
            raise RuntimeError('invalid native completion tokens')
        terminal = generated[-1] in self._stop_ids
        if any(i in self._stop_ids for i in generated[:-1]) or (len(generated) < maximum and not terminal):
            raise RuntimeError('native completion does not match admitted stop behavior')
        if decoder.failure is not None:
            raise decoder.failure
        if self.engine.last_observer_error is not None and delivery_error is None:
            raise self.engine.last_observer_error
        # Engine disabled observation on the first delivery exception. Validate
        # every remaining ID locally, without invoking that observer again.
        for token in generated[len(decoder.tokens):]:
            decoder.feed(token)
        tail = decoder.finish(generated)
        if tail and delivery_error is None:
            try:
                on_delta(tail)
            except BaseException as error:
                delivery_error = error
        text = decoder.text
        if type(text) is not str:
            raise RuntimeError('codec completion must be text')
        text.encode('utf-8')
        completion = {'id': 'chatcmpl-' + request_id, 'object': 'chat.completion',
                      'created': created, 'model': self.model,
                      'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': text},
                                   'finish_reason': 'stop' if terminal else 'length'}],
                      'usage': {'prompt_tokens': len(prompt), 'completion_tokens': len(generated),
                                'total_tokens': len(prompt) + len(generated)}}
        answer = {'completion': completion, 'stream_passed': delivery_error is None,
                  'observation': dict(result['observation'])}
        if delivery_error is not None:
            self.last_stream_error = delivery_error
            answer['error'] = error_view(delivery_error)
        return answer
