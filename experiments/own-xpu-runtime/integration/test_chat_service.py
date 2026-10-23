"""Chat boundary tests; synthetic codec/owner, not model or rendering proof."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools/ctxkeeper'))
from parking import Parking
from chat_service import ChatRequestError, ChatService


class Codec:
    vocab = 100
    tokenizer_identity = {'synthetic': True}
    terminal_token_ids = {98, 99}

    def render(self, messages):
        return messages[-1]['content']

    def encode(self, text):
        return [ord(c) % 90 for c in text] or [1]

    def decode(self, tokens):
        return ''.join({1: ' ', 2: 'hello', 3: '\n', 4: 'é'}.get(i, '?') for i in tokens)


class Owner:
    vocab, context = 100, 32
    _identity = {'tokenizer_identity': Codec.tokenizer_identity, 'geometry': {'eos': 98}}

    def __init__(self):
        self.calls = []
        self.generated = [2, 99]
        self.failure = None

    def run_turn(self, parking, session, messages, **kwargs):
        self.calls.append((session, copy.deepcopy(messages), kwargs))
        if self.failure:
            raise self.failure
        self.saved_history = parking.prefix(messages) + self.generated
        return {'response': {'tokens': list(self.generated)}}


class ChatTests(unittest.TestCase):
    def setUp(self):
        self.owner, self.codec = Owner(), Codec()
        self.parking = Parking(self.owner, self.codec.render, self.codec.encode, budget_bytes=0)
        self.service = ChatService(self.owner, self.parking, self.codec, model='test-quantized',
                                   native_stop_token_ids={98, 99}, clock=lambda: 123)
        self.payload = {'model': 'test-quantized', 'messages': [{'role': 'user', 'content': 'hi'}], 'max_tokens': 4}

    def call(self):
        return self.service.complete(self.payload, session='conversation', request_id='r1')

    def test_terminal_only_removed_from_presentation(self):
        result = self.call()
        self.assertEqual(result['choices'][0]['message']['content'], 'hello')
        self.assertEqual(result['choices'][0]['finish_reason'], 'stop')
        self.assertEqual(result['usage'], {'prompt_tokens': 2, 'completion_tokens': 2, 'total_tokens': 4})
        self.assertEqual(self.owner.saved_history[-2:], [2, 99])
        self.assertEqual(result['id'], 'chatcmpl-r1')

    def test_cap_keeps_whitespace_and_unicode(self):
        self.owner.generated = [1, 2, 4, 3]
        result = self.call()
        self.assertEqual(result['choices'][0]['message']['content'], ' helloé\n')
        self.assertEqual(result['choices'][0]['finish_reason'], 'length')

    def test_terminal_at_cap_is_stop(self):
        self.owner.generated = [1, 2, 3, 98]
        self.assertEqual(self.call()['choices'][0]['finish_reason'], 'stop')

    def test_unsupported_options_refuse_before_run_and_do_not_halt(self):
        variants = [{'stream': True}, {'temperature': .7}, {'top_p': .9}, {'n': 2},
                    {'tools': []}, {'stop': ['x']}, {'model': 'wrong'}, {'max_tokens': True},
                    {'messages': [{'role': 'tool', 'content': 'x'}]},
                    {'messages': [{'role': 'user', 'content': ['image']}]},
                    {'messages': [{'role': 'user', 'content': '\ud800'}]}]
        base = copy.deepcopy(self.payload)
        for change in variants:
            with self.subTest(change=repr(change)):
                self.payload = base | change
                with self.assertRaises(ChatRequestError):
                    self.call()
        self.assertEqual(self.owner.calls, [])
        self.assertIsNone(self.service.halted_reason)
        self.payload = base
        self.call()

    def test_context_refuses_before_run(self):
        self.payload['max_tokens'] = 31
        with self.assertRaises(ChatRequestError):
            self.call()
        self.assertEqual(self.owner.calls, [])

    def test_codec_input_refusal_is_recoverable_before_run(self):
        original = self.codec.render
        def refuse(messages):
            raise ValueError('rendered text byte bound')
        self.codec.render = refuse
        with self.assertRaisesRegex(ChatRequestError, 'rendering or tokenization refused'):
            self.call()
        self.assertEqual(self.owner.calls, [])
        self.assertIsNone(self.service.halted_reason)
        self.codec.render = original
        self.call()

    def test_policy_codec_mismatch_refuses_before_run(self):
        self.parking.render = lambda messages: 'other'
        with self.assertRaises(ChatRequestError):
            self.call()
        self.assertEqual(self.owner.calls, [])

    def test_extra_codec_stop_id_cannot_hide_real_output(self):
        self.codec.terminal_token_ids = {2, 98, 99}
        with self.assertRaisesRegex(ChatRequestError, 'stop IDs changed'):
            self.call()
        with self.assertRaisesRegex(ChatRequestError, 'stop IDs differ'):
            ChatService(self.owner, self.parking, self.codec, model='test-quantized', native_stop_token_ids={98, 99})
        self.assertEqual(self.owner.calls, [])

    def test_stateful_wrapper_cannot_pass_one_matching_render(self):
        calls = []
        def changing(messages):
            calls.append(True)
            return 'hi' if len(calls) == 1 else 'different'
        self.parking.render = changing
        with self.assertRaisesRegex(ChatRequestError, 'callbacks changed'):
            self.call()
        self.assertEqual(calls, [])
        self.assertEqual(self.owner.calls, [])

    def test_coordinator_identifiers_cannot_be_paths(self):
        for session, request in (('../a', 'r1'), ('a', '../r')):
            with self.assertRaises(ChatRequestError):
                self.service.complete(self.payload, session=session, request_id=request)
        self.assertEqual(self.owner.calls, [])

    def test_runtime_error_halts_without_retry_or_completion(self):
        self.owner.failure = RuntimeError('ambiguous SAVE')
        with self.assertRaisesRegex(RuntimeError, 'ambiguous SAVE'):
            self.call()
        with self.assertRaisesRegex(RuntimeError, 'intake halted'):
            self.call()
        self.assertEqual(len(self.owner.calls), 1)

    def test_invalid_decoded_content_halts_without_success_response(self):
        for text in ({'not': 'text'}, '\ud800'):
            with self.subTest(text=repr(text)):
                self.setUp()
                self.codec.decode = lambda tokens: text
                with self.assertRaisesRegex(RuntimeError, 'codec completion'):
                    self.call()
                with self.assertRaisesRegex(RuntimeError, 'intake halted'):
                    self.call()

    def test_short_unterminated_or_internal_stop_halts(self):
        for generated in ([2], [99, 2]):
            with self.subTest(generated=generated):
                self.setUp()
                self.owner.generated = generated
                with self.assertRaisesRegex(RuntimeError, 'stop behavior'):
                    self.call()
                with self.assertRaisesRegex(RuntimeError, 'intake halted'):
                    self.call()
                self.assertEqual(len(self.owner.calls), 1)


if __name__ == '__main__':
    unittest.main()
