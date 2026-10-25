"""CPU-only checks of evidence acceptance; no tokenizer, weights, or endpoint."""
import importlib.util
from pathlib import Path
import unittest

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


if __name__ == '__main__':
    unittest.main()
