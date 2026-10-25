"""CPU-only checks of evidence acceptance; no tokenizer, weights, or endpoint."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('run_suite', Path(__file__).with_name('run_suite.py'))
SUITE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUITE)


def response():
    return {'usage': {'prompt_tokens_details': {'cached_tokens': 0}},
            'choices': [{'message': {'content': 'answer'}, 'finish_reason': 'length'}],
            'ownrt': {'output_tokens': 11, 'decode_wall_ms': 500, 'decode_tok_s': 20,
                      'prompt_wall_ms': 30, 'mtp': {'hits': 7, 'guesses': 10, 'misses': 3},
                      'output_token_ids': list(range(11)), 'activations': 'f32'}}


class EvidenceTests(unittest.TestCase):
    def test_missing_cache_metadata_rejected_at_each_level(self):
        for usage in (None, {}, {'prompt_tokens_details': None}, {'prompt_tokens_details': {}}):
            res = response()
            res['usage'] = usage
            with self.subTest(usage=usage), self.assertRaisesRegex(ValueError, 'explicit cached_tokens'):
                SUITE.response_row(res, 'example', [1, 2], 0.6)
        res = response()
        del res['usage']
        with self.assertRaisesRegex(ValueError, 'explicit cached_tokens'):
            SUITE.response_row(res, 'example', [1, 2], 0.6)

    def test_nonzero_and_malformed_cache_metadata_rejected(self):
        for cached in (1, 25, -1, None, False, 0.0, '0'):
            res = response()
            res['usage']['prompt_tokens_details']['cached_tokens'] = cached
            with self.subTest(cached=cached), self.assertRaisesRegex(ValueError, 'integer 0'):
                SUITE.response_row(res, 'example', [1, 2], 0.6)

    def test_explicit_zero_and_full_response_accounting_preserved(self):
        row = SUITE.response_row(response(), 'example', [1, 2], 0.6)
        self.assertEqual(row['cached_tokens'], 0)
        self.assertEqual((row['decode_event_count'], row['decode_numerator'], row['decode_wall_ms']), (11, 10, 500))
        self.assertEqual(row['recomputed_decode_tok_s'], 20)
        self.assertIn('not first-99', row['decode_window'])

    def test_missing_duration_and_mismatched_rate_rejected(self):
        for duration, rate in ((None, 20), (0, 20), (float('nan'), 20), (500, 22)):
            res = response()
            res['ownrt'].update(decode_wall_ms=duration, decode_tok_s=rate)
            with self.subTest(duration=duration, rate=rate), self.assertRaises(ValueError):
                SUITE.response_row(res, 'example', [1, 2], 0.6)

    def test_even_median_averages_middle_rates(self):
        rows = [{'decode_tok_s': x, 'mtp': {'hits': 1, 'guesses': 2}} for x in [40, 10, 30, 20]]
        summary = SUITE.summarize(rows, 'test', 'unused')
        self.assertEqual(summary['median_decode_tok_s'], 25)
        self.assertEqual(summary['pooled_acceptance'], 0.5)
        self.assertIn('not a certified benchmark', summary['scope'])

    def test_capture_failure_prevents_next_http_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'suite-manifest.json').write_text(json.dumps({'prompts': [{'prompt_id': 'one'}, {'prompt_id': 'two'}]}))
            for prompt in ('one', 'two'):
                (root / prompt).mkdir()
                (root / prompt / 'tokens.txt').write_text('1 2')
            chat = SimpleNamespace(tok=SimpleNamespace(decode=lambda *a, **k: '<|im_start|>user\nhello<|im_end|>'))
            api = SimpleNamespace(Chat=lambda: chat, parse=lambda *a: {'prompt_ids': [1, 2]})
            captured = []
            def stop(row, res):
                captured.append((row, res))
                raise ValueError('capture failed')
            with patch.object(SUITE, 'SUITE', root), patch.object(SUITE, 'load', return_value=api), \
                    patch.object(SUITE.urllib.request, 'urlopen', return_value=io.StringIO(json.dumps(response()))) as http:
                with self.assertRaisesRegex(ValueError, 'capture failed'):
                    SUITE.main(on_result=stop, argv=['--label', 'test', '--out', str(root / 'result.json')])
            self.assertEqual(http.call_count, 1)
            self.assertEqual(captured[0][0]['cached_tokens'], 0)
            self.assertEqual(captured[0][0]['prompt_id'], 'one')
            self.assertFalse((root / 'result.json').exists())


if __name__ == '__main__':
    unittest.main()
