#!/usr/bin/env python3
"""CPU-only fixture/proxy checks; fake local upstream, no inference endpoint."""
import http.client
import http.server
import importlib.util
import json
import hashlib
from pathlib import Path
import tempfile
import threading
import unittest

SPEC = importlib.util.spec_from_file_location('pi_smoke', Path(__file__).with_name('pi_smoke.py'))
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)


class Fake(http.server.BaseHTTPRequestHandler):
    payload = b''
    calls = 0
    def log_message(self, *args): pass
    def do_POST(self):
        self.rfile.read(int(self.headers['Content-Length']))
        type(self).calls += 1
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Content-Length', str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)


class SmokeTests(unittest.TestCase):
    def test_grader_refuses_zero_discovered_tests_even_with_exit_zero(self):
        self.assertEqual(P.grade_outcome(0, 'TAP version 13\n1..0\n# tests 0\n# pass 0\n', 'sum'),
                         {'passed': False, 'test_count': 0})
        self.assertEqual(P.grade_outcome(0, 'TAP version 13\n1..1\n# tests 1\n# pass 1\n', 'sum'),
                         {'passed': True, 'test_count': 1})
        self.assertFalse(P.grade_outcome(1, '# tests 1\n# fail 1\n', 'sum')['passed'])
        self.assertFalse(P.grade_outcome(0, 'no recognized test summary', 'sum')['passed'])
        self.assertTrue(P.grade_outcome(0, 'Ran 11 tests in 0.01s\n\nOK (skipped=1)', 'notesdelta')['passed'])
    def test_notesdelta_fixture_changes_only_unique_value_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'smoke'
            P.prepare(out, P.MODEL, False, 'notesdelta')
            original = (P.REPO / 'tools/ctxkeeper/notesdelta.py').read_bytes()
            changed = (out / 'work/notesdelta.py').read_bytes()
            self.assertEqual(changed, original.replace(b'return int(nums[-1].replace', b'return int(nums[0].replace', 1))
            self.assertIn(b'len(nums[-1]) <= 24', changed)
            manifest = json.loads((out / 'manifest.json').read_text())
            for name in ('test_notesdelta.py', 'sync_notesdelta.py'):
                self.assertEqual(hashlib.sha256((out / 'work' / name).read_bytes()).hexdigest(),
                                 manifest['fixture_source_sha256'][name])

    def test_prepare_is_fresh_and_uses_isolated_dummy_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'smoke'
            P.prepare(out, P.MODEL, False)
            settings = json.loads((out / 'home/.pi/agent/settings.json').read_text())
            self.assertEqual(settings['defaultThinkingLevel'], 'medium')
            self.assertFalse(settings['compaction']['enabled'])
            self.assertFalse(settings['retry']['enabled'])
            self.assertEqual(settings['retry']['provider']['maxRetries'], 0)
            self.assertIn('total = value', (out / 'work/sum.mjs').read_text())
            with self.assertRaises(FileExistsError): P.prepare(out, P.MODEL, False)
            model = P.models('http://localhost:12345', P.MODEL, False)['providers']['sc117-smoke']['models'][0]
            self.assertEqual(model['maxTokens'], 4096)
            self.assertEqual(model['compat']['thinkingFormat'], 'openai')
            self.assertTrue(model['compat']['supportsReasoningEffort'])
            self.assertEqual(model['thinkingLevelMap']['medium'], 'medium')

    def test_focused_reads_only_adds_hashed_guidance_to_notesdelta(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline, focused = Path(tmp) / 'baseline', Path(tmp) / 'focused'
            P.prepare(baseline, P.MODEL, False, 'notesdelta')
            P.prepare(focused, P.MODEL, False, 'notesdelta', focused_reads=True)
            self.assertEqual((baseline / 'prompt.txt').read_bytes(), (focused / 'prompt.txt').read_bytes())
            for name in ('notesdelta.py', 'test_notesdelta.py', 'sync_notesdelta.py'):
                self.assertEqual((baseline / 'work' / name).read_bytes(), (focused / 'work' / name).read_bytes())
            self.assertFalse((baseline / 'work/AGENTS.md').exists())
            manifest = json.loads((focused / 'manifest.json').read_text())
            guidance = (focused / 'work/AGENTS.md').read_text()
            self.assertEqual(guidance, manifest['fixture_guidance']['text'])
            expected = hashlib.sha256(guidance.encode()).hexdigest()
            self.assertEqual(manifest['fixture_guidance']['sha256'], expected)
            self.assertEqual(manifest['fixture_source_sha256']['AGENTS.md'], expected)
            self.assertIn('line-limited reads', guidance)
            self.assertIn('Keep all required test runs and correctness checks', guidance)
            with self.assertRaises(ValueError):
                P.prepare(Path(tmp) / 'wrong-fixture', P.MODEL, False, focused_reads=True)

    def test_compaction_fixture_has_small_budget_and_five_separate_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'smoke'
            P.prepare(out, P.MODEL, True)
            self.assertEqual(len(list((out / 'work').glob('log-part-*.txt'))), 5)
            config = P.models('http://localhost:12345', P.MODEL, True)
            self.assertEqual(config['providers']['sc117-smoke']['models'][0]['contextWindow'], 16384)
            settings = json.loads((out / 'home/.pi/agent/settings.json').read_text())
            self.assertEqual(settings['compaction']['reserveTokens'], 8192)
            self.assertIn('log-part-4.txt', (out / 'prompt.txt').read_text())
            self.assertIn('Do not read part 5', (out / 'prompt.txt').read_text())
            self.assertIn('log-part-5.txt', (out / 'prompt-phase2.txt').read_text())
            self.assertNotIn('48151623', (out / 'prompt-phase2.txt').read_text())
            self.assertIn('48151623', (out / 'work/log-part-1.txt').read_text())

    def proxy_case(self, payload, expect_error):
        Fake.payload, Fake.calls = payload, 0
        upstream = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Fake)
        ut = threading.Thread(target=upstream.serve_forever, daemon=True); ut.start()
        with tempfile.TemporaryDirectory() as tmp:
            recorder = P.Recorder(Path(tmp), f'http://127.0.0.1:{upstream.server_port}', 1)
            proxy = http.server.ThreadingHTTPServer(('127.0.0.1', 0), recorder.handler())
            pt = threading.Thread(target=proxy.serve_forever, daemon=True); pt.start()
            try:
                def request():
                    conn = http.client.HTTPConnection('127.0.0.1', proxy.server_port, timeout=5)
                    conn.request('POST', '/v1/chat/completions', json.dumps({'stream': True}), {'Content-Type': 'application/json'})
                    resp = conn.getresponse(); code, body = resp.status, resp.read(); conn.close()
                    return code, body
                code, body = request()
                self.assertEqual(code, 200); self.assertEqual(body, payload)
                self.assertEqual(bool(recorder.rows[0]['error']), expect_error)
                self.assertEqual(request()[0], 503)
                self.assertEqual(Fake.calls, 1)
                return recorder.rows[0]
            finally:
                proxy.shutdown(); proxy.server_close(); pt.join()
                upstream.shutdown(); upstream.server_close(); ut.join()

    def test_continuous_compaction_prepares_one_original_five_log_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'smoke'
            P.prepare(out, P.MODEL, True, continuous=True)
            prompt = (out / 'prompt.txt').read_text()
            self.assertIn('log-part-1.txt through log-part-5.txt in order', prompt)
            self.assertIn('Fix sum.mjs so node --test test_sum.mjs passes.', prompt)
            self.assertIn('repeat it in your final answer', prompt)
            self.assertNotIn('48151623', prompt)
            self.assertFalse((out / 'prompt-phase2.txt').exists())
            manifest = json.loads((out / 'manifest.json').read_text())
            self.assertEqual(manifest['compaction'], 'pi-client-16384-continuous')

    def test_continuous_grade_requires_compaction_then_tools_and_final_fact(self):
        events = []
        def tool(name, args):
            ident = str(len(events))
            events.extend([{'type': 'tool_execution_start', 'toolCallId': ident, 'toolName': name, 'args': args},
                           {'type': 'tool_execution_end', 'toolCallId': ident, 'toolName': name, 'isError': False}])
        for i in range(1, 5): tool('read', {'path': f'/work/log-part-{i}.txt'})
        compact = {'type': 'compaction_end', 'reason': 'threshold', 'aborted': False,
                   'result': {'summary': 'Retain checksum 48151623.'}}
        events.append(compact)
        tool('read', {'path': '/work/log-part-5.txt'})
        tool('edit', {'path': 'sum.mjs'})
        tool('bash', {'command': 'node --test test_sum.mjs'})
        events.append({'type': 'message_end', 'message': {'role': 'assistant', 'content': [
            {'type': 'text', 'text': 'Fixed. Tests pass. Checksum 48151623.'}]}})
        checks, _ = P.event_checks(events, True, continuous=True)
        self.assertTrue(all(checks.values()), checks)
        self.assertNotIn('threshold_compaction_before_phase2', checks)
        no_compact = [e for e in events if e is not compact]
        late = no_compact + [compact]
        self.assertFalse(P.event_checks(late, True, True)[0]['threshold_compaction_before_final'])
        after_tools = no_compact[:-1] + [compact, no_compact[-1]]
        self.assertFalse(P.event_checks(after_tools, True, True)[0]['edit_and_bash_after_compaction'])
        compact['errorMessage'] = 'summary failed'
        self.assertFalse(P.event_checks(events, True, True)[0]['client_compaction_succeeded'])

    def test_sse_thinking_tools_usage_and_request_cap(self):
        row = self.proxy_case(b'data: {"choices":[{"delta":{"reasoning_content":"Let me check","tool_calls":[{}]}}]}\n\n'
                             b'data: {"choices":[{"delta":{"content":"Answer"}}]}\n\n'
                             b'data: {"choices":[],"usage":{"prompt_tokens_details":{"cached_tokens":64}}}\n\n'
                             b'data: [DONE]\n\n', False)
        self.assertEqual(row['reasoning_chunks'], 1)
        self.assertEqual(row['tool_chunks'], 1)
        self.assertEqual(row['content_chunks'], 1)
        self.assertLessEqual(row['first_delta_seconds'], row['first_reasoning_seconds'])
        self.assertLessEqual(row['first_reasoning_seconds'], row['first_content_seconds'])
        self.assertLessEqual(row['first_content_seconds'], row['done_seconds'])
        self.assertLessEqual(row['done_seconds'], row['wall_seconds'])
        self.assertEqual(row['usage']['prompt_tokens_details']['cached_tokens'], 64)

    def test_sse_error_halts_future_upstream_calls(self):
        self.proxy_case(b'data: {"error":{"message":"test fault"}}\n\n', True)

    def test_compaction_grade_requires_end_success_tools_five_reads_and_final_fact(self):
        events = []
        def tool(name, args):
            ident = str(len(events))
            events.extend([{'type': 'tool_execution_start', 'toolCallId': ident, 'toolName': name, 'args': args},
                           {'type': 'tool_execution_end', 'toolCallId': ident, 'toolName': name, 'isError': False}])
        for i in range(1, 5): tool('read', {'path': f'/work/log-part-{i}.txt'})
        events += [{'type': 'compaction_start', 'reason': 'threshold'},
                   {'type': 'compaction_end', 'reason': 'threshold', 'aborted': False,
                    'result': {'summary': 'Keep checksum 48151623.'}}]
        self.assertTrue(P.phase1_ready(events))
        events[-1]['reason'] = 'overflow'
        self.assertFalse(P.phase1_ready(events))
        events[-1]['reason'] = 'threshold'
        events.append({'type': 'smoke_phase_start', 'phase': 2})
        tool('read', {'path': '/work/log-part-5.txt'})
        tool('edit', {'path': 'sum.mjs'})
        tool('bash', {'command': 'node --test'})
        events += [{'type': 'message_end', 'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': 'Fixed. Checksum 48151623.'}]}}]
        checks, details = P.event_checks(events, True)
        self.assertTrue(all(checks.values()), checks)
        self.assertEqual(details['log_reads'], [f'log-part-{i}.txt' for i in range(1, 6)])
        without_end = [e for e in events if e['type'] != 'compaction_end']
        self.assertFalse(P.event_checks(without_end, True)[0]['client_compaction_succeeded'])
        late_compaction = [e for e in events if e.get('type') != 'compaction_end'] + [events[9]]
        self.assertFalse(P.event_checks(late_compaction, True)[0]['threshold_compaction_before_phase2'])
        events[9]['errorMessage'] = 'summary failed'
        self.assertFalse(P.event_checks(events, True)[0]['client_compaction_succeeded'])
        events[-1]['message']['content'][0]['text'] = 'Fixed.'
        self.assertFalse(P.event_checks(events, True)[0]['checksum_in_final_answer'])
        events = [e for e in events if not (e.get('type') == 'tool_execution_start' and e.get('args', {}).get('path') == '/work/log-part-5.txt')]
        self.assertFalse(P.event_checks(events, True)[0]['all_five_logs_read'])


if __name__ == '__main__': unittest.main()
