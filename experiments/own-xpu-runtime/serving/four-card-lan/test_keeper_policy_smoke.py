#!/usr/bin/env python3
"""CPU-only tests; no network or inference."""
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('keeper_policy_smoke', HERE / 'keeper_policy_smoke.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def response(text='48151623'):
    return {'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': text}}],
            'usage': {'prompt_tokens': 42, 'completion_tokens': 3}}


class Tests(unittest.TestCase):
    def test_dry_run_never_creates_output(self):
        with tempfile.TemporaryDirectory(dir=HERE) as root:
            output = Path(root) / 'new'
            result = subprocess.run([sys.executable, str(HERE / 'keeper_policy_smoke.py'),
                                     '--output', str(output)], check=True, capture_output=True, text=True)
            self.assertEqual(json.loads(result.stdout)['requests'], 0)
            self.assertFalse(output.exists())

    def test_model_and_stream_are_pinned_and_usage_recorded(self):
        with tempfile.TemporaryDirectory() as root:
            observed = []
            def opener(request, timeout):
                observed.append((json.loads(request.data), timeout))
                return io.BytesIO(json.dumps(response()).encode())
            upstream = m.Upstream('http://localhost:1', root, opener=opener)
            upstream({'model': 'wrong-keeper', 'stream': True, 'stream_options': {}, 'messages': []})
            self.assertEqual(observed[0][0]['model'], m.MODEL)
            self.assertFalse(observed[0][0]['stream'])
            self.assertNotIn('stream_options', observed[0][0])
            self.assertEqual(upstream.rows[0]['usage']['prompt_tokens'], 42)

    def test_first_failure_latches_without_retry(self):
        with tempfile.TemporaryDirectory() as root:
            calls = []
            def fail(*a, **k):
                calls.append(True)
                raise OSError('fixture refusal')
            upstream = m.Upstream('http://localhost:1', root, opener=fail)
            for _ in range(2):
                with self.assertRaises(m.Halt):
                    upstream({'messages': []})
            self.assertEqual(len(calls), 1)
            self.assertNotIsInstance(m.Halt(), Exception)

    def test_call_budget_stops_before_network(self):
        with tempfile.TemporaryDirectory() as root:
            calls = []
            def opener(*a, **k):
                calls.append(True)
                return io.BytesIO(json.dumps(response()).encode())
            upstream = m.Upstream('http://localhost:1', root, max_calls=1, opener=opener)
            upstream({'messages': []})
            with self.assertRaises(m.Halt):
                upstream({'messages': []})
            self.assertEqual(len(calls), 1)

    def test_secondary_fact_is_archived_and_absent_from_notes(self):
        rows = [{'n': 2, 'text': '2026-10-26T05:00:00Z host=web-3 job=alpha-1 status=ok duration=2.0s checksum=12345678\n'
                                   '2026-10-26T05:00:01Z host=web-4 job=beta-2 status=ok duration=1.0s checksum=87654321'}]
        fact = m.secondary_fact(rows, '12345678 is already in notes')
        self.assertEqual(fact['checksum'], '87654321')
        self.assertEqual(fact['archived_message'], 2)

    def test_primary_notes_success_needs_no_natural_recall(self):
        checks = m.report_checks([{'response': response()}], {'cuts': 1}, [{'text': '48151623'}],
                                 {'correct': True, 'natural_recall_delta': 0},
                                 {'fact': {'checksum': '12345678'}, 'correct': True, 'recall_delta': 1})
        self.assertTrue(all(checks.values()))
        self.assertFalse(m.checksum_ok(response('1481516234'), '48151623'))

    def test_internal_recall_leak_fails(self):
        result = response()
        result['choices'][0]['message']['tool_calls'] = [{'function': {'name': 'recall'}}]
        self.assertFalse(m.report_checks([{'response': result}], {}, [], {}, {})['no_internal_recall_leak'])


if __name__ == '__main__':
    unittest.main()
