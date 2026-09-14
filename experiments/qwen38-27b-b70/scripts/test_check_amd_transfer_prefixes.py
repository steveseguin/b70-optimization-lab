"""CPU-only checks for the prefix screen's evidence and fail-fast contracts."""
import argparse
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('prefix_screen', Path(__file__).with_name('check-amd-transfer-prefixes.py'))
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class PrefixScreenTests(unittest.TestCase):
    def setUp(self):
        self.case = {'prompt_id': 'p', 'prompt_class': 'prose', 'prompt_sha256': 'x',
                     'prompt_tokens': 7, 'expected_token_ids': list(range(64)),
                     'expected_finish_reason': 'length', 'request': {'prompt': 'x'}}
        self.response = {'choices': [{'token_ids': list(range(64)), 'finish_reason': 'length'}],
                         'usage': {'completion_tokens': 64, 'prompt_tokens': 7,
                                   'prompt_tokens_details': {'cached_tokens': 0}}}

    def test_complete_prefix_and_natural_early_stop(self):
        self.assertTrue(m.compare_response(self.case, self.response)['passed'])
        self.case.update(expected_token_ids=[0, 1], expected_finish_reason='stop')
        self.response['choices'][0].update(token_ids=[0, 1], finish_reason='stop')
        self.response['usage']['completion_tokens'] = 2
        self.assertTrue(m.compare_response(self.case, self.response)['passed'])

    def test_late_wrong_token_is_retained(self):
        self.response['choices'][0]['token_ids'][-1] = 900
        result = m.compare_response(self.case, self.response)
        self.assertFalse(result['passed'])
        self.assertEqual(result['first_mismatch_index'], 63)
        self.assertEqual(result['actual_token_ids'][-1], 900)

    def test_missing_nonzero_and_boolean_cache_rejected(self):
        for details in ({}, {'cached_tokens': 1}, {'cached_tokens': False}):
            with self.subTest(details=details):
                response = copy.deepcopy(self.response)
                response['usage']['prompt_tokens_details'] = details
                with self.assertRaises((ValueError, KeyError)):
                    m.compare_response(self.case, response)

    def test_wrong_input_count_and_incomplete_ids_rejected(self):
        for field, value in [('prompt_tokens', 8), ('completion_tokens', 65)]:
            with self.subTest(field=field):
                response = copy.deepcopy(self.response)
                response['usage'][field] = value
                with self.assertRaises(ValueError):
                    m.compare_response(self.case, response)
        self.response['choices'][0]['token_ids'][0] = '0'
        with self.assertRaises(ValueError):
            m.compare_response(self.case, self.response)

    def test_early_termination_cannot_pass_matching_short_prefix(self):
        self.response['choices'][0].update(token_ids=list(range(63)), finish_reason='stop')
        self.response['usage']['completion_tokens'] = 63
        self.assertFalse(m.compare_response(self.case, self.response)['passed'])

    def test_failure_stops_after_one_request_and_saves_raw(self):
        self.response['choices'][0]['token_ids'][-1] = 900
        raw = json.dumps(self.response).encode()
        reply = io.BytesIO(raw)
        reply.status = 200
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'new'
            args = argparse.Namespace(output_dir=output, suite=Path('suite'),
                                      reference_performance=Path('reference'), model='m',
                                      base_url='http://unused/v1', timeout=1, check_only=False)
            with patch.object(m, 'load_plan', return_value={'selected': [self.case] * 6}), \
                    patch.object(m.urllib.request, 'urlopen', return_value=reply) as post:
                self.assertEqual(m.run(args), 1)
            self.assertEqual(post.call_count, 1)
            self.assertEqual((output / '00-p/response.raw').read_bytes(), raw)
            self.assertTrue((output / '00-p/comparison.json').is_file())
            summary = json.loads((output / 'summary.json').read_text())
            self.assertEqual(summary['requests_sent'], 1)
            self.assertFalse(summary['passed'])
            self.assertFalse(summary['realistic_final_gate']['passed'])

    def test_existing_output_directory_is_not_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileExistsError):
                m.run(argparse.Namespace(output_dir=Path(directory)))


if __name__ == '__main__':
    unittest.main()
