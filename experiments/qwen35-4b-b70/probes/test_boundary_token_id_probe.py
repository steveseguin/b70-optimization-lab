"""Offline API-contract and end-to-end failure-propagation tests."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('probe', Path(__file__).with_name('boundary-token-id-probe.py'))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def response(prompt, got):
    return {'choices': [{'token_ids': got, 'finish_reason': 'length'}],
            'usage': {'prompt_tokens': len(prompt), 'completion_tokens': len(got),
                      'prompt_tokens_details': {'cached_tokens': 0}}}


class ProbeTests(unittest.TestCase):
    def test_contract_rejects_truncation_missing_ids_cache_and_prompt_changes(self):
        for mutate in [lambda r: r['choices'][0].pop('token_ids'),
                       lambda r: r['choices'][0].update(token_ids=[5]),
                       lambda r: r['usage'].update(prompt_tokens=99),
                       lambda r: r['usage']['prompt_tokens_details'].update(cached_tokens=1),
                       lambda r: r.update(prompt_token_ids=[99])]:
            r = response([1, 2], [5, 6])
            mutate(r)
            with self.assertRaises(ValueError):
                probe.validate_response(r, [1, 2], 2)
        self.assertEqual(probe.validate_response(response([1, 2], [5, 6]), [1, 2], 2)['token_ids'], [5, 6])

    def test_oracle_compare_exact_prefixes_and_failure_evidence(self):
        prompts = []
        def fake(base, path, payload, timeout):
            if path == '/tokenize':
                return {'tokens': list(range(1, 300))}
            prompt = payload['prompt']
            self.assertTrue(all(type(x) is int for x in prompt))
            prompts.append(prompt)
            # A deterministic continuation depending only on absolute position.
            return response(prompt, list(range(len(prompt) + 1, len(prompt) + payload['max_tokens'] + 1)))
        with tempfile.TemporaryDirectory() as directory, patch.object(probe, 'post', side_effect=fake), contextlib.redirect_stdout(io.StringIO()):
            oracle = str(Path(directory) / 'oracle.json')
            output = str(Path(directory) / 'compare.json')
            common = ['--base', 'http://mock', '--model', 'mock', '--lengths', '8,14', '--concurrency', '1,4']
            self.assertEqual(probe.main(common + ['--mode', 'oracle', '--out', oracle]), 0)
            compare = common + ['--mode', 'compare', '--oracle', oracle, '--out', output]
            self.assertEqual(probe.main(compare), 0)
            data = json.loads(Path(output).read_text())
            self.assertEqual(len(data['rows']), 32)
            self.assertEqual(data['cases'][-1]['prompt_ids'], list(range(1, 256)))
            self.assertTrue(data['passed'])
            with patch.object(probe, 'post', side_effect=TimeoutError('test timeout')):
                self.assertEqual(probe.main(compare), 1)
            failed = json.loads(Path(output).read_text())
            self.assertFalse(failed['passed'])
            self.assertEqual(len(failed['rows']), 32)
            self.assertIn('TimeoutError', failed['rows'][0]['error'])


if __name__ == '__main__':
    unittest.main()
