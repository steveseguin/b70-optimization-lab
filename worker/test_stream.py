"""CPU-only fixtures for the worker reasoning/action boundary."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error

spec = importlib.util.spec_from_file_location('worker_stream_under_test', Path(__file__).with_name('stream.py'))
stream = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stream)


def fixture(chunks, *, finish='stop', done=True, cached=0, ids=True, reported=None):
    lines = []
    for index, delta in enumerate(chunks):
        choice = {'index': 0, 'delta': delta}
        if ids:
            choice['token_ids'] = [100 + index]
        lines += [('data: ' + json.dumps({'id': 'fixture', 'choices': [choice]}) + '\n').encode(), b'\n']
    usage = {'prompt_tokens': 12, 'completion_tokens': len(chunks) if reported is None else reported,
             'prompt_tokens_details': {'cached_tokens': cached}}
    lines += [('data: ' + json.dumps({'choices': [{'index': 0, 'delta': {}, 'finish_reason': finish}], 'usage': usage}) + '\n').encode(), b'\n']
    if done:
        lines += [b'data: [DONE]\n', b'\n']
    return lines


class StreamTests(unittest.TestCase):
    def parse(self, chunks, **options):
        self.raw = io.BytesIO()
        ticks = iter(range(10000))
        lines = fixture(chunks, **options)
        result = stream.consume_stream(lines, self.raw, 0, timeout_seconds=1000, clock=lambda: next(ticks))
        self.assertEqual(self.raw.getvalue(), b''.join(lines))
        return result

    def test_split_inline_boundary_never_executes_reasoning_fence(self):
        chunks = [{'content': '```bash\nrm important\n```\nThink'},
                  {'content': '</thi'}, {'content': 'nk>\n\n'},
                  {'content': '```bash\necho safe\n```'}]
        result = self.parse(chunks)
        self.assertEqual(result['answer_content'].strip(), '```bash\necho safe\n```')
        self.assertIn('rm important', result['reasoning_content'])
        self.assertNotIn('rm important', result['answer_content'])
        self.assertGreater(result['http_answer_ttft_s'], result['http_ttft_s'])
        self.assertEqual(result['token_ids'], [100, 101, 102, 103])

    def test_optional_opening_and_literal_tags_in_final_code(self):
        result = self.parse([{'content': '<think>careful</think>\n```bash\necho "</think><think>"\n```'}])
        self.assertEqual(result['reasoning_content'], 'careful')
        self.assertEqual(result['answer_content'], '\n```bash\necho "</think><think>"\n```')

    def test_separate_reasoning_preserves_final_code_tags(self):
        result = self.parse([{'reasoning_content': '```bash\necho wrong\n```'},
                             {'content': '```bash\necho "</think>"\n```'}])
        self.assertEqual(result['reasoning_format'], 'separated')
        self.assertNotIn('wrong', result['answer_content'])
        self.assertIn('wrong', result['reasoning_content'])

    def test_alternative_reasoning_field(self):
        result = self.parse([{'reasoning': 'inspect'}, {'content': '```bash\necho done\n```'}])
        self.assertEqual(result['reasoning_content'], 'inspect')

    def test_empty_explicit_separate_reasoning(self):
        result = self.parse([{'reasoning_content': ''}, {'content': 'answer'}])
        self.assertEqual(result['reasoning_format'], 'separated')
        self.assertEqual(result['reasoning_content'], '')

    def test_missing_close_or_answer_refused(self):
        for content in ['```bash\necho unsafe\n```', '<think>unfinished', 'thought</think>\n ']:
            with self.subTest(content=content), self.assertRaises(ValueError):
                self.parse([{'content': content}])

    def test_mixed_format_refused(self):
        for content in ['<think>again</think>answer', 'implicit thought</think>answer',
                        '```bash\necho wrong\n```\n</think>\n```bash\necho right\n```']:
            with self.subTest(content=content), self.assertRaisesRegex(ValueError, 'mixed'):
                self.parse([{'reasoning': 'separate'}, {'content': content}])

    def test_truncated_and_length_stopped_refused(self):
        for options in [{'done': False}, {'finish': 'length'}, {'finish': 'tool_calls'}]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.parse([{'content': 'thought</think>answer'}], **options)

    def test_token_completeness_and_usage_required(self):
        for options in [{'ids': False}, {'reported': 2}, {'reported': True}, {'cached': 1}, {'cached': None}, {'cached': False}]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.parse([{'content': 'thought</think>answer'}], **options)

    def test_elapsed_timeout_keeps_received_bytes(self):
        raw = io.BytesIO()
        with self.assertRaises(TimeoutError):
            stream.consume_stream([b'data: {}\n'], raw, 0, timeout_seconds=1, clock=lambda: 2)
        self.assertEqual(raw.getvalue(), b'data: {}\n')

    def test_http_error_no_retry_and_evidence_retained(self):
        calls = []
        def fail(request, **kwargs):
            calls.append((request, kwargs))
            raise urllib.error.HTTPError(request.full_url, 503, 'busy', {'X-Fixture': 'yes'}, io.BytesIO(b'busy body'))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(urllib.error.HTTPError):
                stream.request_one('http://127.0.0.1:18124', {'model': 'fixture'}, tmp, opener=fail)
            self.assertEqual(len(calls), 1)
            self.assertEqual((Path(tmp) / 'response.sse').read_bytes(), b'busy body')
            self.assertEqual(json.loads((Path(tmp) / 'request.json').read_text()), {'model': 'fixture'})
            self.assertEqual(json.loads((Path(tmp) / 'response-headers.json').read_text()), {'X-Fixture': 'yes'})

    def test_success_request_url_headers_and_payload(self):
        class Response(io.BytesIO):
            headers = {'Content-Type': 'text/event-stream'}
        seen = []
        def open_fixture(request, **kwargs):
            seen.append((request, kwargs))
            return Response(b''.join(fixture([{'content': 'thought</think>answer'}])))
        with tempfile.TemporaryDirectory() as tmp:
            result = stream.request_one('http://127.0.0.1:18124/v1', {'model': 'fixture'}, tmp, opener=open_fixture, timeout_seconds=90)
            self.assertEqual(result['answer_content'], 'answer')
            self.assertEqual(seen[0][0].full_url, 'http://127.0.0.1:18124/v1/chat/completions')
            self.assertEqual(seen[0][1], {'timeout': 90})
            self.assertEqual(len(seen), 1)


if __name__ == '__main__':
    unittest.main()
