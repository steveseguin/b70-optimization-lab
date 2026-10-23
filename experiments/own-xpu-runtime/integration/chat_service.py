"""Text-only chat facade over an admitted owner; no HTTP or process lifecycle.

The coordinator owns the codec/engine/parking admission and private session ID.
Unsupported chat options refuse before RUN. Raw output IDs, including terminal
tokens, remain the checkpoint history; only the presented text omits a final
native stop token. No whitespace cleanup or approximate prefix reuse occurs.
"""
from __future__ import annotations

import copy
import threading
import time

from checkpoint_engine import EngineRefusal, valid_id


class ChatRequestError(ValueError):
    """Client input refused before owner intake; the owner remains usable."""


def require(value, message):
    if not value:
        raise ChatRequestError(message)


class ChatService:
    def __init__(self, engine, parking, codec, *, model: str, native_stop_token_ids, clock=time.time):
        require(type(model) is str and bool(model), 'explicit model name required')
        require(parking.engine is engine, 'parking belongs to another engine')
        require(codec.vocab == engine.vocab, 'codec vocabulary differs from admitted owner')
        # Model/binary admission belongs to CheckpointEngine; tokenizer admission
        # must independently match that trusted launch identity, not a checkpoint.
        require(codec.tokenizer_identity == engine._identity['tokenizer_identity'],
                'codec differs from admitted tokenizer identity')
        require(type(native_stop_token_ids) in (set, frozenset) and bool(native_stop_token_ids) and
                all(type(i) is int and 0 <= i < codec.vocab for i in native_stop_token_ids) and
                engine._identity['geometry']['eos'] in native_stop_token_ids,
                'independently admitted native stop IDs required')
        self._stop_ids = frozenset(native_stop_token_ids)
        require(codec.terminal_token_ids == self._stop_ids, 'codec stop IDs differ from native admission')
        require(parking.render == codec.render and parking.tokenize == codec.encode,
                'parking must use the admitted codec callbacks')
        self.engine, self.parking, self.codec = engine, parking, codec
        self.model, self.clock = model, clock
        self._lock = threading.RLock()
        self.halted_reason = None

    def validate(self, payload):
        require(type(payload) is dict, 'chat request must be an object')
        allowed = {'model', 'messages', 'max_tokens', 'temperature', 'top_p', 'n', 'stream'}
        require(not set(payload) - allowed, 'unsupported chat request fields')
        require(payload.get('model') == self.model, 'model does not match admitted owner')
        require(type(payload.get('stream', False)) is bool and payload.get('stream', False) is False,
                'streaming is not supported by this facade')
        require(type(payload.get('n', 1)) is int and payload.get('n', 1) == 1,
                'exactly one completion is supported')
        for key, wanted in (('temperature', 0), ('top_p', 1)):
            value = payload.get(key, wanted)
            require(type(value) in (int, float) and value == wanted,
                    'only deterministic greedy ' + key + '=' + str(wanted) + ' is supported')
        maximum = payload.get('max_tokens', 128)
        require(type(maximum) is int and 1 <= maximum <= 512, 'max_tokens must be 1..512')
        messages = payload.get('messages')
        require(type(messages) is list and 0 < len(messages) <= 64, '1..64 text messages required')
        total = 0
        for message in messages:
            require(type(message) is dict and set(message) == {'role', 'content'},
                    'each message requires only role and content')
            require(message['role'] in ('system', 'developer', 'user', 'assistant'),
                    'unsupported message role')
            require(type(message['content']) is str, 'message content must be text')
            try:
                total += len(message['content'].encode('utf-8'))
            except UnicodeError as error:
                raise ChatRequestError('message content must be valid UTF-8') from error
            require(total <= 65536, 'message text exceeds byte bound')
        require(messages[-1]['role'] == 'user', 'the last message must be a user turn')
        messages = copy.deepcopy(messages)
        try:
            tokens = self.codec.encode(self.codec.render(messages))
        except ValueError as error:
            raise ChatRequestError('message rendering or tokenization refused: ' + str(error)) from error
        require(type(tokens) is list and tokens and all(type(i) is int and 0 <= i < self.engine.vocab for i in tokens),
                'codec produced invalid prompt tokens')
        require(len(tokens) + maximum <= self.engine.context, 'prompt plus completion exceeds admitted context')
        return messages, maximum, tokens

    def complete(self, payload, *, session: str, request_id: str):
        """One trusted coordinator session, one RUN, one policy disposition.

        Client validation errors are recoverable. Runtime/storage errors propagate
        without a fabricated completion; the adapter retains its halted state.
        Session and request IDs are supplied by the coordinator, never inferred
        from an OpenAI user field or accepted as filesystem paths.
        """
        with self._lock:
            if self.halted_reason is not None:
                raise RuntimeError('chat intake halted: ' + self.halted_reason)
            messages, maximum, prompt = self.validate(payload)
            require(self.parking.render == self.codec.render and self.parking.tokenize == self.codec.encode,
                    'parking codec callbacks changed')
            require(self.codec.terminal_token_ids == self._stop_ids, 'codec stop IDs changed')
            try:
                valid_id(request_id)
                self.parking.checkpoint_id(session, prompt)
            except (EngineRefusal, ValueError) as error:
                raise ChatRequestError(str(error)) from error
            # Identifier admission cannot involve the model owner.
            require(self.parking.prefix(messages) == prompt, 'parking render differs from admitted chat codec')
            try:
                return self._complete(messages, maximum, prompt, session, request_id)
            except BaseException as error:
                self.halted_reason = str(error) or type(error).__name__
                raise

    def _complete(self, messages, maximum, prompt, session, request_id):
        # Ensure the policy uses this exact codec; mismatched callbacks must not
        # turn a validated chat request into a different native prompt.
        result = self.engine.run_turn(self.parking, session, messages,
                                      request_id=request_id, max_new=maximum)
        generated = result['response']['tokens']
        # A runtime protocol inconsistency is not a user error or a retry signal.
        if (not generated or len(generated) > maximum or
                any(type(i) is not int or not 0 <= i < self.engine.vocab for i in generated)):
            raise RuntimeError('invalid native completion tokens')
        terminal = generated[-1] in self._stop_ids
        if any(i in self._stop_ids for i in generated[:-1]) or (len(generated) < maximum and not terminal):
            raise RuntimeError('native completion does not match admitted stop behavior')
        text = self.codec.decode(generated[:-1] if terminal else generated)
        if type(text) is not str:
            raise RuntimeError('codec completion must be text')
        try:
            text.encode('utf-8')
        except UnicodeError as error:
            raise RuntimeError('codec completion must be valid UTF-8') from error
        return {'id': 'chatcmpl-' + request_id, 'object': 'chat.completion',
                'created': int(self.clock()), 'model': self.model,
                'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': text},
                             'finish_reason': 'stop' if terminal else 'length'}],
                'usage': {'prompt_tokens': len(prompt), 'completion_tokens': len(generated),
                          'total_tokens': len(prompt) + len(generated)}}
