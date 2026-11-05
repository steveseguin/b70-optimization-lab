#!/usr/bin/env python3
"""CPU-only Pi protocol checks with a fake tokenizer and engine; no GPU work."""
import http.client
import json
import os
import tempfile
import threading
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from test_persistent_lifetime import S

C = S.CHAT
TOOLS = [{'type': 'function', 'function': {
    'name': 'bash', 'parameters': {'type': 'object', 'properties': {'command': {'type': 'string'}}},
}}]
CALL = '<tool_call>\n<function=bash>\n<parameter=command>\nprintf hello\n</parameter>\n</function>\n</tool_call>'


class FakeChat:
    def render(self, messages, thinking, tools=None, effort=None, generation=True):
        return ''.join(m['content'] for m in messages)

    def encode(self, text):
        return list(map(ord, text))

    def decode(self, ids):
        return ''.join(chr(i) for i in ids if i not in C.EOS and i != C.THINK_END)


CHAT = FakeChat()


class FakeEngine:
    t = None
    prefill_rows = 0
    native_seconds = 0
    continuation = False

    def __init__(self):
        self.lock = threading.Lock()
        self.count = 0

    def storage_ok(self):
        return None

    def activations(self):
        return 'f32'

    def generate(self, prompt, max_new, label, on_token=None, **options):
        self.count += 1
        ids = CHAT.encode('Ready.') + [C.EOS[1]]
        if on_token:
            for token in ids:
                on_token(token)
        return ids, {'request': self.count}


class PiProtocolTests(unittest.TestCase):
    @contextmanager
    def serving(self, engine=None):
        engine = engine or FakeEngine()
        state = S.State()
        state.phase = 'ready'
        state.fault = lambda error: self.fail(str(error))
        server = S.Server(('127.0.0.1', 0), S.make_handler(state, engine, CHAT, None))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield engine, server.server_address
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def get(self, address, path):
        conn = http.client.HTTPConnection(*address, timeout=5)
        try:
            conn.request('GET', path)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def request(self, **extra):
        return C.parse({'messages': [{'role': 'user', 'content': 'Hello'}],
                        'tools': TOOLS, 'stream': True, **extra}, CHAT)

    def stream(self, req, ids):
        stream = C.Streamer(req, CHAT)
        live = [delta for token in ids for delta in stream.feed(token)]
        tail, finish = stream.finish(ids)
        self.assertFalse(stream.mismatch)
        expected = C.completion(req, ids, {}, CHAT)['choices'][0]
        for field in ('content', 'reasoning_content'):
            self.assertEqual(''.join(v for k, v in live + tail if k == field),
                             expected['message'].get(field) or '')
        self.assertEqual(finish, expected['finish_reason'])
        return live, tail, finish

    def test_plain_answer_streams_with_tools_present(self):
        live, tail, _ = self.stream(self.request(), CHAT.encode('Working now.\n') + [C.EOS[1]])
        self.assertGreater(len(live), 2)

    def test_tool_markup_never_leaks_as_live_content(self):
        req = self.request()
        stream = C.Streamer(req, CHAT)
        live = []
        ids = CHAT.encode('Checking. \n' + CALL) + [C.EOS[1]]
        for token in ids:
            live.extend(stream.feed(token))
            self.assertNotIn('<', ''.join(v for k, v in live if k == 'content'))
        tail, finish = stream.finish(ids)
        self.assertEqual(''.join(v for k, v in live if k == 'content'), 'Checking.')
        self.assertEqual(finish, 'tool_calls')
        calls = dict(tail)['tool_calls']
        self.assertEqual(json.loads(calls[0]['function']['arguments']), {'command': 'printf hello'})
        self.assertFalse(stream.mismatch)

    def test_false_tag_prefix_eventually_streams(self):
        self.stream(self.request(), CHAT.encode('a <tool_box> is plain text') + [C.EOS[1]])

    def test_incomplete_tool_call_keeps_canonical_final_text(self):
        self.stream(self.request(), CHAT.encode('Preparing <tool_call><function=bash>'))

    def test_thinking_and_answer_stream_with_tools(self):
        req = self.request(reasoning_effort='medium')
        ids = CHAT.encode('Consider this.') + [C.THINK_END] + CHAT.encode('\n\nReady.') + [C.EOS[1]]
        live, _, _ = self.stream(req, ids)
        self.assertTrue(any(k == 'reasoning_content' for k, _ in live))
        self.assertTrue(any(k == 'content' for k, _ in live))

    def test_stop_sequence_spanning_tokens_is_preserved(self):
        self.stream(self.request(stop=['END']), CHAT.encode('Answer END hidden') + [C.EOS[1]])

    def test_tool_choice_none_remains_plain_text(self):
        self.stream(self.request(tool_choice='none'), CHAT.encode(CALL) + [C.EOS[1]])

    def test_context_budget_includes_output_and_rejects_full_prompt(self):
        with patch.object(C, 'CONTEXT', 131072):
            req = C.parse({'messages': [{'role': 'user', 'content': 'x' * 131070}], 'max_tokens': 8192}, CHAT)
            self.assertEqual(req['max_new'], 2)
            with self.assertRaisesRegex(C.RequestError, 'context is 131072'):
                C.parse({'messages': [{'role': 'user', 'content': 'x' * 131072}]}, CHAT)

    def test_profile_effort_mapping_activates_selected_level(self):
        root = Path(__file__).resolve().parent / 'pi'
        model = json.loads((root / 'models.json').read_text())['providers']['sc117']['models'][0]
        settings = json.loads((root / 'settings.json').read_text())
        self.assertEqual(model['contextWindow'], 131072)
        self.assertEqual(model['compat']['thinkingFormat'], 'openai')
        self.assertTrue(model['compat']['supportsReasoningEffort'])
        self.assertTrue(settings['compaction']['enabled'])
        for level, effort in model['thinkingLevelMap'].items():
            req = self.request(reasoning_effort=effort)
            self.assertEqual(req['thinking'], level != 'off')
        self.assertEqual(settings['defaultThinkingLevel'], 'medium')

    def test_unknown_model_is_rejected_before_engine(self):
        engine = FakeEngine()
        state = S.State()
        state.phase = 'ready'
        state.fault = lambda error: self.fail(str(error))
        server = S.Server(('127.0.0.1', 0), S.make_handler(state, engine, CHAT, None))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for model in ('does-not-exist', C.MODEL_ID + '-keeper', C.MODEL_ID):
                conn = http.client.HTTPConnection(*server.server_address, timeout=5)
                body = {'model': model, 'messages': [{'role': 'user', 'content': 'Hello'}]}
                conn.request('POST', '/v1/chat/completions', json.dumps(body), {'Content-Type': 'application/json'})
                response = conn.getresponse()
                data = json.loads(response.read())
                conn.close()
                if model == C.MODEL_ID:
                    self.assertEqual(response.status, 200)
                else:
                    self.assertEqual(response.status, 400)
                    self.assertIn('unknown model', data['error']['message'])
                    self.assertEqual(engine.count, 0)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_health_reports_persistence_context_and_continuation(self):
        with patch.object(C, 'CONTEXT', 131072), self.serving() as (engine, address):
            status, health = self.get(address, '/health')
            self.assertEqual(status, 200)
            self.assertTrue(health['persistent'])
            self.assertFalse(health['continuation'])
            self.assertEqual(health['context_length'], 131072)
            engine.native_seconds = 172800
            engine.continuation = True
            status, health = self.get(address, '/v1/health')
            self.assertEqual(status, 200)
            self.assertFalse(health['persistent'])
            self.assertTrue(health['continuation'])

    def test_client_configs_are_exact_files_and_paths_are_restricted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = {'models': {'providers': {'test': {'models': []}}},
                      'settings': {'compaction': {'enabled': True}}}
            for name, value in values.items():
                (root / (name + '.json')).write_text(json.dumps(value))
            with patch.dict(os.environ, {'SC117_CLIENT_CONFIG_DIR': directory}), self.serving() as (_, address):
                for name, value in values.items():
                    status, body = self.get(address, '/client-config/pi/' + name + '.json')
                    self.assertEqual((status, body), (200, value))
                for path in ('/client-config/pi/other.json', '/client-config/pi/../settings.json'):
                    self.assertEqual(self.get(address, path)[0], 404)

    def test_client_config_endpoint_disabled_without_directory(self):
        with patch.dict(os.environ, {'SC117_CLIENT_CONFIG_DIR': ''}), self.serving() as (_, address):
            self.assertEqual(self.get(address, '/client-config/pi/models.json')[0], 404)

    def test_invalid_request_types_do_not_call_or_halt_engine(self):
        with self.serving() as (engine, address):
            for body in ([], 'hello', None, 42, {'model': [], 'messages': []},
                         {'messages': [{'role': 'user', 'content': 'x'}], 'stream_options': 'wrong'}):
                conn = http.client.HTTPConnection(*address, timeout=5)
                try:
                    conn.request('POST', '/v1/chat/completions', json.dumps(body), {'Content-Type': 'application/json'})
                    response = conn.getresponse()
                    error = json.loads(response.read())
                    self.assertEqual(response.status, 400)
                    self.assertIn('error', error)
                finally:
                    conn.close()
            self.assertEqual(engine.count, 0)
            self.assertEqual(self.get(address, '/health')[1]['status'], 'ready')


class HostedRetentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.control = self.root / 'control'
        self.output = self.root / 'output'
        self.control.mkdir()
        self.output.mkdir()
        self.engine = S.Engine(self.control, self.root / 'evidence', types.SimpleNamespace())
        self.engine.t = types.SimpleNamespace(out=self.output)
        self.keep = self.root / 'unrelated'
        self.keep.mkdir()
        (self.keep / 'precious.txt').write_text('preserve this')

    def request_directory(self, number=1):
        request = self.output / f'req-{number:06d}'
        for rank in (0, 1):
            target = request / f'rank{rank}'
            target.mkdir(parents=True)
            (target / 'timings.jsonl').write_text('{"timing":1}\n')
            (target / 'tp-exchange.json').write_text('{"passed":true}\n')
            (target / 'other.bin').write_bytes(b'payload')
        return request

    def test_hosted_retention_does_not_accumulate_timing_copies(self):
        with patch.dict(os.environ, {'SC117_RETAIN_TIMINGS': '0'}):
            for number in range(1, 4):
                request = self.request_directory(number)
                size = sum(p.stat().st_size for p in request.rglob('*') if p.is_file())
                self.assertEqual(self.engine.release(request), size)
                self.assertFalse(request.exists())
        self.assertFalse((self.control / 'tp-evidence').exists())
        self.assertEqual((self.keep / 'precious.txt').read_text(), 'preserve this')

    def test_lab_retention_keeps_requested_details_and_removes_request(self):
        request = self.request_directory()
        with patch.dict(os.environ, {'SC117_RETAIN_TIMINGS': '1'}):
            self.assertGreater(self.engine.release(request), 0)
        self.assertFalse(request.exists())
        kept = self.control / 'tp-evidence'
        self.assertEqual(len(list(kept.iterdir())), 4)
        for rank in (0, 1):
            self.assertEqual((kept / f'req-000001-rank{rank}-timings.jsonl').read_text(), '{"timing":1}\n')
            self.assertEqual((kept / f'req-000001-rank{rank}-tp-exchange.json').read_text(), '{"passed":true}\n')

    def test_retention_rejects_unrelated_or_wrongly_named_directory(self):
        sibling = self.output / 'not-a-request'
        sibling.mkdir()
        for path in (self.keep, sibling):
            with self.assertRaisesRegex(RuntimeError, 'retention path'):
                self.engine.release(path)
            self.assertTrue(path.exists())
        self.assertEqual((self.keep / 'precious.txt').read_text(), 'preserve this')

    def test_root_retention_removes_only_named_state_dumps(self):
        targets = ['rank0/state-2147483647', 'rank1/state-2147483647', 'rank0/draft-final-state']
        for name in targets:
            path = self.output / name
            path.mkdir(parents=True)
            (path / 'state.bin').write_bytes(b'state')
        log = self.output / 'rank0/native.log'
        log.write_text('keep native log')
        other_request = self.request_directory()
        with patch.dict(os.environ, {'SC117_RETAIN_TIMINGS': '0'}):
            self.assertEqual(self.engine.release(self.output), 15)
        self.assertEqual(log.read_text(), 'keep native log')
        self.assertTrue(other_request.exists())
        self.assertTrue(self.output.is_dir())
        self.assertFalse(any((self.output / name).exists() for name in targets))

    def test_empty_previous_is_noop(self):
        self.assertEqual(self.engine.release(None), 0)


if __name__ == '__main__':
    unittest.main()
