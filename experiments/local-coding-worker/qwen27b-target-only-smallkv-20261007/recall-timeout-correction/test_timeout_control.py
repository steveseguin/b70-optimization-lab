#!/usr/bin/env python3
"""Offline baseline/candidate controls; no HTTP or model calls."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent

def load(variant):
    path = HERE / ('check-fp8-practical-session.' + variant + '.py')
    spec = importlib.util.spec_from_file_location('wire_' + variant, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

BASE = load('baseline')
CANDIDATE = load('candidate')
EVENT = {'id': 'offline', 'choices': [{'index': 0, 'delta': {'content': 'ok'},
          'token_ids': [42], 'finish_reason': 'stop'}],
         'usage': {'prompt_tokens': 3, 'completion_tokens': 1,
                   'prompt_tokens_details': {'cached_tokens': 0}}}
LINES = [('data: ' + json.dumps(EVENT) + '\n').encode(), b'\n', b'data: [DONE]\n', b'\n']

class TimeoutControls(unittest.TestCase):
    def test_default120_rejects_late_stream_baseline_and_candidate(self):
        for module in (BASE, CANDIDATE):
            raw = io.BytesIO()
            with self.assertRaisesRegex(TimeoutError, 'request exceeded 120-second total stream limit'):
                module.consume_stream(LINES, raw, 0, lambda: 121)
            self.assertEqual(raw.getvalue(), LINES[0])

    def test_explicit420_accepts_same_stream_but_rejects_beyond420(self):
        result = CANDIDATE.consume_stream(LINES, io.BytesIO(), 0, lambda: 121, timeout_seconds=420)
        self.assertEqual(result['text'], 'ok')
        self.assertEqual(result['elapsed_s'], 121)
        raw = io.BytesIO()
        with self.assertRaisesRegex(TimeoutError, 'request exceeded 420-second total stream limit'):
            CANDIDATE.consume_stream(LINES, raw, 0, lambda: 421, timeout_seconds=420)
        self.assertEqual(raw.getvalue(), LINES[0])

    def test_exact_deadlines_keep_existing_strict_greater_than_behavior(self):
        self.assertEqual(CANDIDATE.consume_stream(LINES, io.BytesIO(), 0, lambda: 120)['text'], 'ok')
        self.assertEqual(CANDIDATE.consume_stream(LINES, io.BytesIO(), 0, lambda: 420, timeout_seconds=420)['text'], 'ok')

    def test_default_clock_call_sequence_and_payload_are_unchanged(self):
        observed = []
        for module in (BASE, CANDIDATE):
            calls = []
            def clock():
                calls.append(len(calls) + 1)
                return calls[-1]
            raw = io.BytesIO()
            result = module.consume_stream(LINES, raw, 0, clock)
            observed.append((calls, result, raw.getvalue()))
        self.assertEqual(observed[0], observed[1])

    def test_request_forwards_default_or_chosen_bound_to_socket_and_consumer(self):
        for options, expected in (({}, 120), ({'timeout_seconds': 420}, 420)):
            calls = []
            class Response:
                headers = {'Content-Type': 'text/event-stream'}
                def __enter__(self): return self
                def __exit__(self, *args): return False
            response = Response()
            def opener(request, timeout):
                calls.append(timeout)
                return response
            with tempfile.TemporaryDirectory(prefix='recall-timeout-control-') as directory:
                with mock.patch.object(CANDIDATE.time, 'perf_counter', return_value=17), \
                     mock.patch.object(CANDIDATE, 'consume_stream', return_value={'sentinel': True}) as consumer:
                    result = CANDIDATE.request_one('http://127.0.0.1:1', {}, Path(directory), opener, **options)
                    self.assertEqual(result, {'sentinel': True})
                    self.assertEqual(calls, [expected])
                    self.assertIs(consumer.call_args.args[0], response)
                    self.assertEqual(consumer.call_args.args[2], 17)
                    self.assertEqual(consumer.call_args.kwargs, {'timeout_seconds': expected})

    def test_invalid_timeout_rejected_before_io(self):
        invalid = (0, -1, float('inf'), float('-inf'), float('nan'), True, None, '420', 10**1000)
        for value in invalid:
            with self.subTest(value_type=type(value).__name__):
                raw = io.BytesIO()
                with self.assertRaisesRegex(ValueError, 'finite positive'):
                    CANDIDATE.consume_stream(LINES, raw, 0, lambda: 1, timeout_seconds=value)
                self.assertEqual(raw.getvalue(), b'')
                with tempfile.TemporaryDirectory(prefix='recall-timeout-invalid-') as directory:
                    opener = mock.Mock(side_effect=AssertionError('must not call network'))
                    with self.assertRaisesRegex(ValueError, 'finite positive'):
                        CANDIDATE.request_one('http://127.0.0.1:1', {}, Path(directory), opener,
                                              timeout_seconds=value)
                    opener.assert_not_called()
                    self.assertEqual(list(Path(directory).iterdir()), [])

if __name__ == '__main__':
    unittest.main()
