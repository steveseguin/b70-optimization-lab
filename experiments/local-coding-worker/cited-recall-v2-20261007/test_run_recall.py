#!/usr/bin/env python3
"""Synthetic offline lifecycle controls; no model, endpoint or old answer use."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('recall_trial_under_test', HERE / 'run_recall.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def fixture():
    bundle = {'schema': 'lab.cited-recall.sources.v2',
              'questions': [{'id': f'FRESH_{i:02}', 'prompt': f'What is recorded for case {i}?'} for i in range(10)],
              'corpus': {f'S{i:02}': f'Synthetic document {i}.\n\n  Approved: café 雪.\n' for i in range(1, 5)}}
    refs = {'answers': [{'question_id': q['id'], 'answer': 'The synthetic approval is recorded.',
                        'citations': [{'doc_id': 'S01', 'start_line': 2, 'end_line': 3}]}
                       for q in bundle['questions']]}
    return bundle, refs


class RecallTests(unittest.TestCase):
    def trial(self, refs_change=None, token_delta=0, pre_stop=False, identity_bad=False,
              wire_error=False, response_change=None, terminate=False):
        bundle, refs = fixture()
        if refs_change: refs_change(refs)
        calls, endpoints, reads, timeout_values = [], [], [], []
        with tempfile.TemporaryDirectory(prefix='recall-v2-offline-') as temporary:
            root = Path(temporary); folder = root / 'harness'; folder.mkdir()
            pilot = root / 'pilot'; pilot.mkdir(); state = pilot / 'server'; state.mkdir()
            inputs = folder / 'evaluation/model-input'; inputs.mkdir(parents=True)
            # A forbidden file exists, but neither prompt generation nor trial may read it.
            key = folder / 'evaluation/answer-key.json'; key.write_text('DO NOT READ THIS KEY')
            source = json.dumps(bundle, ensure_ascii=False).encode()
            profile = {'base_url': 'http://127.0.0.1:18125', 'model': 'synthetic-never-called',
                       'max_input_tokens': 28000, 'max_output_tokens': 3072,
                       'generation': {'temperature': 0, 'top_p': 1, 'seed': 42}}
            profile_bytes = json.dumps(profile).encode()
            protocol = {'source_bundle_sha256': runner.digest(source),
                        'instructions_sha256': runner.digest(runner.SYSTEM.encode()),
                        'request_profile_sha256': runner.digest(profile_bytes),
                        'compiler_sha256': runner.digest(runner.COMPILER.read_bytes()),
                        'wire_sha256': runner.digest(runner.WIRE.read_bytes()),
                        'validator_sha256': runner.digest(runner.VALIDATOR.read_bytes()),
                        'messages_sha256': runner.digest(json.dumps(runner.messages_for(bundle), ensure_ascii=False,
                                                                  separators=(',', ':')).encode()),
                        'expected_input_tokens': 1000}
            if identity_bad: protocol['compiler_sha256'] = '0' * 64
            (inputs / 'source-bundle.json').write_bytes(source)
            (inputs / 'instructions.txt').write_bytes(runner.SYSTEM.encode())
            (folder / 'request-profile.json').write_bytes(profile_bytes)
            (folder / 'trial-protocol.json').write_text(json.dumps(protocol))
            if pre_stop: (state / 'STOP').write_text('existing stop')

            class FakeModel:
                def __init__(self, configuration, directory):
                    self.model, self.base, self.out = configuration['model'], configuration['base_url'], directory
                    directory.mkdir()
                    self.thinking = False
                    self.template_kwargs = {'enable_thinking': False}
                    self.sampling = configuration['generation']
                    self.opener = types.SimpleNamespace(open=None)
                    self.wire = types.SimpleNamespace(request_one=self.request)
                    self.metrics_wire = types.SimpleNamespace(metric_delta=lambda a, b, n: {'mock_only': True})

                def fetch(self, endpoint, payload=None):
                    endpoints.append(endpoint)
                    if endpoint == '/tokenize':
                        if payload['messages'] != runner.messages_for(bundle):
                            raise AssertionError('Prompt changed or source was truncated')
                        return io.StringIO(json.dumps({'count': 1000 + token_delta}))
                    if endpoint != '/metrics': raise AssertionError('Unexpected endpoint')
                    return io.BytesIO(b'mock metrics')

                def request(self, base, payload, directory, opener, *, timeout_seconds):
                    calls.append(copy.deepcopy(payload)); timeout_values.append(timeout_seconds)
                    runner.save(directory / 'request.json', payload)
                    runner.save(directory / 'response.sse', b'offline synthetic wire fixture\n')
                    if terminate:
                        # Invoke the actual handler registered by run_trial, without
                        # delivering a signal to the reviewer/test process.
                        handlers[runner.signal.SIGTERM](runner.signal.SIGTERM, None)
                    if wire_error: raise TimeoutError('synthetic stream deadline')
                    response = {'text': json.dumps(refs, ensure_ascii=False), 'prompt_tokens': 1000,
                                'cached_tokens': 0, 'finish_reasons': ['stop'],
                                'token_ids_available': True, 'token_ids': [11, 22], 'completion_tokens': 2}
                    if response_change: response_change(response)
                    return response

            original_read = Path.read_bytes
            handlers = {}
            def install_handler(number, handler):
                previous = handlers.get(number, 0)
                handlers[number] = handler
                return previous
            def audited_read(path):
                reads.append(str(path))
                if 'answer-key' in path.name or 'review-only' in path.parts:
                    raise AssertionError('Answer key must never be read')
                return original_read(path)

            with patch.object(runner, 'HERE', folder), patch.object(runner, 'PILOT', pilot), \
                    patch.object(runner, 'make_model', FakeModel), \
                    patch.object(runner, 'server_identity', return_value={'synthetic': True}), \
                    patch.object(runner.signal, 'signal', side_effect=install_handler), \
                    patch.object(runner.signal, 'alarm') as alarm, \
                    patch.object(Path, 'read_bytes', audited_read), \
                    patch.object(socket, 'socket', side_effect=AssertionError('Network forbidden')), \
                    contextlib.redirect_stdout(io.StringIO()):
                code = runner.run_trial()
            out = pilot / 'recall'
            result = json.loads((out / 'result.json').read_text())
            self.assertTrue((state / 'STOP').exists())
            if pre_stop: self.assertEqual((state / 'STOP').read_text(), 'existing stop')
            self.assertFalse(any('answer-key' in name for name in reads))
            self.assertEqual(handlers[runner.signal.SIGTERM], 0)
            saved = {f.relative_to(out).as_posix(): f.read_bytes() for f in out.rglob('*') if f.is_file()}
            return code, result, calls, endpoints, timeout_values, alarm.call_args_list, saved

    def test_one_complete_request_compiles_and_crosschecks_without_semantic_claim(self):
        code, result, calls, endpoints, timeouts, alarms, saved = self.trial()
        self.assertEqual(code, 0)
        self.assertEqual(result['status'], 'complete-awaiting-semantic-review')
        self.assertEqual(result['model_requests'], 1)
        self.assertFalse(result['model_quality_result'])
        self.assertEqual(result['semantic_grading'], 'pending-independent-review')
        self.assertEqual(len(calls), 1)
        self.assertEqual(endpoints, ['/tokenize', '/metrics', '/metrics'])
        self.assertEqual(timeouts, [420])
        self.assertIn(unittest.mock.call(420), alarms)
        compiled = json.loads(saved['compiled/compiled.json'])
        self.assertEqual(len(compiled['answers']), 10)
        self.assertEqual(compiled['answers'][0]['citations'][0]['quote'], '\n  Approved: café 雪.')
        self.assertEqual(json.loads(saved['mechanical-crosscheck.json'])['status'], 'passed')
        self.assertIn('requests/001/response.sse', saved)

    def test_model_quote_is_rejected_without_repair_or_second_request(self):
        def change(refs): refs['answers'][0]['citations'][0]['quote'] = 'invented'
        code, result, calls, _, _, _, saved = self.trial(refs_change=change)
        self.assertEqual(code, 1); self.assertEqual(len(calls), 1)
        self.assertIn('unknown fields', result['error'])
        self.assertNotIn('compiled/compiled.json', saved)
        self.assertIn('invented', saved['raw-refs.json'].decode())

    def test_missing_question_is_rejected_without_filling_it(self):
        code, result, calls, _, _, _, saved = self.trial(refs_change=lambda r: r['answers'].pop())
        self.assertEqual(code, 1); self.assertEqual(len(calls), 1)
        self.assertIn('missing or extra', result['error'])
        self.assertEqual(len(json.loads(saved['raw-refs.json'])['answers']), 9)
        self.assertNotIn('compiled/compiled.json', saved)

    def test_extra_citation_is_rejected_without_trimming_it(self):
        def change(refs): refs['answers'][0]['citations'] *= 3
        code, result, calls, _, _, _, saved = self.trial(refs_change=change)
        self.assertEqual(code, 1); self.assertEqual(len(calls), 1)
        self.assertIn('More than two citations', result['error'])
        self.assertEqual(len(json.loads(saved['raw-refs.json'])['answers'][0]['citations']), 3)
        self.assertNotIn('compiled/compiled.json', saved)

    def test_preexisting_stop_performs_no_network_or_generation(self):
        code, result, calls, endpoints, _, _, _ = self.trial(pre_stop=True)
        self.assertEqual(code, 1); self.assertEqual(calls, []); self.assertEqual(endpoints, [])
        self.assertEqual(result['model_requests'], 0)

    def test_token_count_mismatch_prevents_first_generation(self):
        code, result, calls, endpoints, _, _, _ = self.trial(token_delta=1)
        self.assertEqual(code, 1); self.assertEqual(calls, [])
        self.assertEqual(endpoints, ['/tokenize'])
        self.assertIn('CPU/server token counts disagree', result['error'])

    def test_protocol_identity_mismatch_prevents_tokenization(self):
        code, result, calls, endpoints, _, _, _ = self.trial(identity_bad=True)
        self.assertEqual(code, 1); self.assertEqual(calls, []); self.assertEqual(endpoints, [])
        self.assertIn('identity mismatch', result['error'])

    def test_stream_failure_stops_without_metrics_followup_or_retry(self):
        code, result, calls, endpoints, timeouts, _, saved = self.trial(wire_error=True)
        self.assertEqual(code, 1); self.assertEqual(len(calls), 1)
        self.assertEqual(endpoints, ['/tokenize', '/metrics']); self.assertEqual(timeouts, [420])
        self.assertIn('response.sse', ' '.join(saved))
        self.assertNotIn('raw-refs.json', saved)
        self.assertIn('synthetic stream deadline', result['error'])

    def test_missing_output_identity_stops_before_any_more_calls(self):
        code, result, calls, endpoints, _, _, _ = self.trial(response_change=lambda r: r.update(token_ids_available=False))
        self.assertEqual(code, 1); self.assertEqual(len(calls), 1)
        self.assertEqual(endpoints, ['/tokenize', '/metrics'])
        self.assertIn('Strict response', result['error'])

    def test_sigterm_preserves_partial_stream_result_and_stop(self):
        code, result, calls, endpoints, _, _, saved = self.trial(terminate=True)
        self.assertEqual(code, 1); self.assertEqual(len(calls), 1)
        self.assertEqual(endpoints, ['/tokenize', '/metrics'])
        self.assertIn('SIGTERM', result['error'])
        self.assertIn('requests/001/response.sse', saved)
        self.assertIn('result.json', saved)
        self.assertNotIn('raw-refs.json', saved)

    def test_prompt_preserves_all_lines_and_only_model_input(self):
        bundle, _ = fixture(); messages = runner.messages_for(bundle)
        for doc_id, text in bundle['corpus'].items():
            numbered = '\n'.join(f'{n:04d} | {line}' for n, line in enumerate(text.splitlines(), 1))
            self.assertIn(f'DOCUMENT {doc_id}\n{numbered}\nEND DOCUMENT {doc_id}', messages[1]['content'])
        self.assertEqual(messages[0]['content'], (HERE / 'evaluation/model-input/instructions.txt').read_bytes().decode('utf-8'))
        self.assertLess(messages[1]['content'].index('END DOCUMENT S04'),
                        messages[1]['content'].index('"questions"'))
        self.assertEqual(len(messages), 2)

    def test_actual_admission_requires_passed_boundary_gate(self):
        with tempfile.TemporaryDirectory(prefix='recall-v2-admission-') as temporary:
            root = Path(temporary); state = root / 'server'; state.mkdir()
            boundary = root / 'boundaries'; boundary.mkdir()
            (boundary / 'result.json').write_text('{"status":"failed"}')
            with self.assertRaisesRegex(RuntimeError, 'Boundary gate has not passed'):
                runner.server_identity(state)
            (boundary / 'result.json').write_text('{"status":"passed"}')
            (state / 'pid.json').write_text(json.dumps({'supervisor_pid': os.getpid()}))
            (state / 'container.json').write_text('{"id":"synthetic-no-container"}')
            identity = runner.server_identity(state)
            self.assertEqual(identity['supervisor_pid'], os.getpid())
            self.assertLess(identity['supervisor_age_seconds'], 720)


if __name__ == '__main__':
    unittest.main(verbosity=2)
