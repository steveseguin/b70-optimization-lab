#!/usr/bin/env python3
"""Offline refusal controls for the real boundary main; never contact a server."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BoundaryGateTests(unittest.TestCase):
    def control(self, mutation=None, initial_stop=False, count_delta=0,
                stop_before_generation=False, stop_after_generation=False):
        gate = load('boundary_gate_under_test', 'check_boundaries.py')
        protocol = json.loads((HERE / 'boundary-protocol.json').read_text())
        calls = []
        with tempfile.TemporaryDirectory(prefix='boundary-offline-control-') as temporary:
            root = Path(temporary)
            state = root / 'server'; state.mkdir()
            out = root / 'result'
            if initial_stop: (state / 'STOP').write_text('already stopping')

            class FakeModel:
                def __init__(self, base, model, directory, **kwargs):
                    self.base, self.model, self.out = base, model, directory
                    self.out.mkdir()
                    self.thinking = False
                    self.template_kwargs = {'enable_thinking': False}
                    self.sampling = {'temperature': 0, 'top_p': 1, 'seed': 42}
                    self.opener = types.SimpleNamespace(open=None)
                    self.wire = types.SimpleNamespace(request_one=self.request)
                    self.metrics_wire = types.SimpleNamespace(metric_delta=lambda before, after, count: {'mock': True})
                    self.current_count = None
                    self.tokenizations = 0

                def fetch(self, endpoint, payload=None):
                    if endpoint == '/tokenize':
                        case = protocol['cases'][protocol['order'][self.tokenizations]]
                        self.tokenizations += 1
                        self.current_count = case['input_tokens']
                        if payload['messages'] != case['messages']:
                            raise AssertionError('Gate changed the frozen prompt')
                        return io.StringIO(json.dumps({'count': self.current_count + count_delta}))
                    if endpoint != '/metrics':
                        raise AssertionError('Unexpected endpoint: ' + endpoint)
                    if stop_before_generation: (state / 'STOP').write_text('operator stop')
                    return io.BytesIO(b'offline mock metrics')

                def request(self, base, payload, directory, opener):
                    calls.append(copy.deepcopy(payload))
                    response = {'text': 'LAB42', 'prompt_tokens': self.current_count,
                                'cached_tokens': 0, 'completion_tokens': 2,
                                'token_ids_available': True, 'token_ids': [42, self.current_count]}
                    if mutation: mutation(response, len(calls))
                    if stop_after_generation: (state / 'FAULT.json').write_text('{}')
                    return response

            with patch.object(gate, 'LocalModel', FakeModel), \
                    patch.object(gate.sys, 'argv', ['check_boundaries.py', '--out', str(out), '--server-state', str(state)]), \
                    patch.object(gate.signal, 'signal'), patch.object(gate.signal, 'alarm'), \
                    patch.object(socket, 'socket', side_effect=AssertionError('Network prohibited in offline controls')), \
                    contextlib.redirect_stdout(io.StringIO()):
                code = gate.main()
            result = json.loads((out / 'result.json').read_text())
            return code, result, calls, (state / 'STOP').exists()

    def refusal(self, expected_error, expected_calls, **kwargs):
        code, result, calls, stopped = self.control(**kwargs)
        self.assertEqual(code, 1)
        self.assertEqual(result['status'], 'failed')
        self.assertIn(expected_error, result['error'])
        self.assertEqual(len(calls), expected_calls)
        self.assertTrue(stopped)

    def test_valid_all_eight_frozen_requests(self):
        code, result, calls, stopped = self.control()
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 8)
        self.assertFalse(stopped)
        self.assertTrue(all(row['status'] == 'passed' for row in result['requests']))
        self.assertTrue(all(p['return_token_ids'] and p['max_tokens'] == 16 for p in calls))
        self.assertTrue(all(p['chat_template_kwargs'] == {'enable_thinking': False} for p in calls))
        self.assertEqual(calls[:4], calls[4:])

    def test_preexisting_stop_refuses_all_requests(self):
        self.refusal('stopped, stopping or faulted', 0, initial_stop=True)

    def test_stop_between_tokenization_and_generation(self):
        self.refusal('stopped, stopping or faulted', 0, stop_before_generation=True)

    def test_fault_after_response_stops_remaining_cases(self):
        self.refusal('stopped, stopping or faulted', 1, stop_after_generation=True)

    def test_cpu_server_token_count_disagreement(self):
        self.refusal('token count differs', 0, count_delta=1)

    def test_generation_token_count_disagreement(self):
        self.refusal('Prompt accounting/cache mismatch', 1,
                     mutation=lambda r, n: r.update(prompt_tokens=r['prompt_tokens'] + 1))

    def test_bad_marker(self):
        self.refusal('Marker output differs', 1, mutation=lambda r, n: r.update(text='LAB43'))

    def test_missing_token_ids(self):
        self.refusal('Complete token identities required', 1,
                     mutation=lambda r, n: r.update(token_ids_available=False, token_ids=[]))

    def test_incomplete_token_ids(self):
        self.refusal('Complete token identities required', 1,
                     mutation=lambda r, n: r.update(token_ids=[42]))

    def test_nonzero_cache(self):
        self.refusal('Prompt accounting/cache mismatch', 1, mutation=lambda r, n: r.update(cached_tokens=1))

    def test_repeat_identity_drift(self):
        def mutate(response, number):
            if number == 5: response['token_ids'] = [43, response['prompt_tokens']]
        self.refusal('different output token IDs', 5, mutation=mutate)

    def test_memory_inputs_complete_and_bound_to_new_profile(self):
        memory = load('memory_input_under_test', 'run-memory.py')
        protocol, questions, documents, messages = memory.prompt()
        self.assertEqual(len(questions['questions']), 10)
        self.assertEqual(set(documents), {f'D{i:02}' for i in range(1, 6)})
        self.assertEqual(set(protocol['model_visible_sha256']),
                         {'questions.json', *[f'corpus/D{i:02}.txt' for i in range(1, 6)]})
        for ident, text in documents.items():
            expected = '\n'.join(f'{n:04d} | {line}' for n, line in enumerate(text.splitlines(), 1))
            self.assertIn('DOCUMENT ' + ident + '\n' + expected + '\nEND DOCUMENT ' + ident,
                          messages[1]['content'])
        self.assertEqual(protocol['worker_profile_sha256'], hashlib.sha256((HERE / 'worker-profile.json').read_bytes()).hexdigest())
        self.assertEqual(str(memory.OUT), '/home/steve/worker-qwen27b-pilot-20261007/memory')
        self.assertEqual(protocol['network_wall_time_limit_s'], 420)
        self.assertEqual(protocol['context_limit'], 33024)
        self.assertLessEqual(protocol['input_limit'] + protocol['output_limit'], protocol['context_limit'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
