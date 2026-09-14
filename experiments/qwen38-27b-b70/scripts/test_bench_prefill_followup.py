"""CPU-only failure and evidence checks for the bounded prefill client."""
import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('followup', Path(__file__).with_name('bench-prefill-followup.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class FakeEndpoint:
    def __init__(self, mismatch=False, cached=0, missing_metrics=False):
        self.count = self.tokens = 0
        self.tokenizations = []
        self.mismatch, self.cached, self.missing_metrics = mismatch, cached, missing_metrics

    def fetch(self, base, path, payload=None, timeout=600):
        if path == '/tokenize':
            self.tokenizations.append(payload)
            return io.BytesIO(json.dumps({'tokens': list(range(2500))}).encode())
        if path == '/metrics':
            text = '' if self.missing_metrics else (
                f'vllm:request_prefill_time_seconds_count {self.count}\n'
                f'vllm:request_prefill_time_seconds_sum {self.count * .25}\n'
                f'vllm:prompt_tokens_total {self.tokens}\n')
            return io.BytesIO(text.encode())
        if path != '/v1/completions':
            raise AssertionError(path)
        self.count += 1
        self.tokens += len(payload['prompt'])
        ids = list(range(payload['max_tokens']))
        if self.mismatch and self.count > 2:
            ids[-1] = 9999
        events = [{'choices': [{'index': 0, 'token_ids': [x]}]} for x in ids]
        events.append({'choices': [], 'usage': {
            'prompt_tokens': len(payload['prompt']), 'completion_tokens': len(ids),
            'prompt_tokens_details': {'cached_tokens': self.cached}}})
        return io.BytesIO((''.join('data: ' + json.dumps(x) + '\n' for x in events)
                           + 'data: [DONE]\n').encode())


class FollowupTests(unittest.TestCase):
    def run_client(self, root, endpoint):
        args = argparse.Namespace(base_url='http://fake', model='test', out=root / 'out',
                                  corpus=m.CORPUS_PATH, baseline=None, lengths='256,512',
                                  max_model_len=1024, max_tokens=128, repeats=3, timeout=1)
        with patch.object(m, 'fetch', endpoint.fetch), contextlib.redirect_stdout(io.StringIO()):
            m.run(args)
        return json.loads((args.out / 'summary.json').read_text())

    def test_success_retains_unrepeated_sources_raw_receipts_and_separate_warmups(self):
        with tempfile.TemporaryDirectory() as temp:
            root, endpoint = Path(temp), FakeEndpoint()
            result = self.run_client(root, endpoint)
            self.assertTrue(result['passed'])
            self.assertEqual(len(result['rows']), 18)
            self.assertEqual(len(result['warmups']), 2)
            self.assertEqual(result['by_length']['512']['samples'], 9)
            self.assertEqual(result['by_length']['512']['server_prefill_tokens_per_s'], 2048)
            corpus = m.load_corpus(m.CORPUS_PATH)
            self.assertEqual([p['prompt'] for p in endpoint.tokenizations],
                             [p['text'] for p in corpus['sources']])
            self.assertTrue(all(p['add_special_tokens'] is False for p in endpoint.tokenizations))
            self.assertEqual(len(list((root / 'out').glob('*-sse.jsonl'))), 20)
            self.assertEqual(len(list((root / 'out').glob('*-metrics-after.txt'))), 20)
            self.assertEqual((root / 'out/corpus.json').read_bytes(), m.CORPUS_PATH.read_bytes())

    def test_full_output_mismatch_fails_and_preserves_failed_row(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, 'full numeric output mismatch'):
                self.run_client(root, FakeEndpoint(mismatch=True))
            result = json.loads((root / 'out/summary.json').read_text())
            self.assertFalse(result['passed'])
            self.assertEqual(result['rows'][-1]['token_ids'][-1], 9999)
            self.assertIn('mismatch', result['error'])

    def test_cached_request_fails_closed_with_raw_sse(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, 'cached_tokens'):
                self.run_client(root, FakeEndpoint(cached=256))
            self.assertTrue((root / 'out/warmup-prose-256-0-sse.jsonl').exists())
            self.assertFalse(json.loads((root / 'out/summary.json').read_text())['passed'])

    def test_missing_server_histogram_cannot_become_http_proxy(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'server-prefill histogram'):
                self.run_client(Path(temp), FakeEndpoint(missing_metrics=True))

    def test_class_balancing_and_incomplete_coverage(self):
        rows, prompts = [], {}
        for name, values in zip(m.CLASSES, ((1, 2, 100), (3, 4, 5), (6, 7, 8))):
            prompts[f'{name}-512'] = [1] * 512
            for repeat, value in enumerate(values):
                rows.append(dict(key=f'{name}-512', repeat=repeat,
                                 **{field: value for field in m.FIELDS}))
        result = m.aggregate(rows, prompts, [512], 3)
        self.assertEqual(result['512']['server_prefill_tokens_per_s'], 4)
        with self.assertRaisesRegex(ValueError, 'incomplete repeat coverage'):
            m.aggregate(rows[:-1], prompts, [512], 3)

    def test_corrupted_corpus_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            corpus = json.loads(m.CORPUS_PATH.read_text())
            corpus['sources'][0]['text'] += ' changed'
            path = Path(temp) / 'corpus.json'
            path.write_text(json.dumps(corpus))
            with self.assertRaisesRegex(ValueError, 'text hash differs'):
                m.load_corpus(path)


if __name__ == '__main__':
    unittest.main()
