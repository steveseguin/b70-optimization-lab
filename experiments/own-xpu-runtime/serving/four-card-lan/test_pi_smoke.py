#!/usr/bin/env python3
"""CPU-only fixture/proxy checks; fake local upstream, no inference endpoint."""
import http.client
import http.server
import importlib.util
import json
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

    def test_compaction_fixture_has_small_budget_and_five_separate_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'smoke'
            P.prepare(out, P.MODEL, True)
            self.assertEqual(len(list((out / 'work').glob('log-part-*.txt'))), 5)
            config = P.models('http://localhost:12345', P.MODEL, True)
            self.assertEqual(config['providers']['sc117-smoke']['models'][0]['contextWindow'], 8192)
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


if __name__ == '__main__': unittest.main()
