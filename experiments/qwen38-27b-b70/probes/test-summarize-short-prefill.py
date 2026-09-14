#!/usr/bin/env python3
"""CPU-only negative gate tests for the prefill evidence collector."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/summarize-short-prefill.py'
spec = importlib.util.spec_from_file_location('summary', SOURCE)
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


def put(root, path, value):
    p = root / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value))


def fixture(root):
    references = {}
    for profile in summary.PROFILES:
        p = root / profile
        p.mkdir()
        for name in ('DONE', 'postflight-discovery.txt', 'postflight-health.log',
                     'postflight-final-journal.txt', 'stop.log'):
            (p / name).write_text('completed\n')
        put(p, 'identity.json', {'runtime_sha256': 'a' * 64})
        put(p, 'container-inspect.json', [])
        (p / 'runtime-sha256.txt').write_text('a' * 64 + '  utils.py\n')
        for arm in summary.ARMS:
            prompts = {k: [1] * int(k.rsplit('-', 1)[1]) for k in summary.KEYS}
            rows = []
            for key, ids in prompts.items():
                for repeat in range(3):
                    rows.append({'key': key, 'phase': 'measure', 'repeat': repeat,
                        'token_ids': [2] * 128, 'token_offsets_s': [1 + i / 100 for i in range(128)],
                        'usage': {'prompt_tokens': len(ids), 'completion_tokens': 128,
                                  'prompt_tokens_details': {'cached_tokens': 0}},
                        'ttft_s': 1, 'http_prompt_tokens_per_ttft_s': len(ids),
                        'server_prefill_s': 1, 'server_prefill_tokens_per_s': len(ids),
                        'decode_token_1_to_100_tps': 100, 'decode_after_ttft_tps': 100,
                        'raw_delta': {'vllm:request_prefill_time_seconds_count': 1,
                                      'vllm:request_prefill_time_seconds_sum': 1}})
            put(p, arm + '/summary.json', {'passed': True, 'prompts': prompts, 'rows': rows,
                'args': {'repeats': 3, 'max_tokens': 128, 'max_model_len': 1024}})
        for arm in ('baseline', 'candidate'):
            put(p, arm + '-strict/performance.json', {
                'realistic_final_gate': {'passed': True},
                'fresh_response_validity': {'valid': True, 'cached_tokens_all_zero': True},
                'rows': [{'prompt_id': str(i), 'prompt_class': str(i % 6), 'prompt_sha256': str(i),
                          'cached_tokens': 0, 'token_ids': [i] * 512, 'completion_tokens': 512,
                          'tok_s_1_100_intervals_after_ttft': 100} for i in range(12)]})
            put(p, arm + '-strict/canaries.json', {'pass_all': True})
            put(p, arm + '-strict/campaign-identity.json', {'suite_sha256': 'fixture',
                'performance_contract': {'max_tokens': 512, 'ignore_eos': False, 'complete_fixed_suite': True}})
        put(p, 'strict-comparison.json', {'comparison': {'exact_prompts': 12, 'total_prompts': 12},
                                         'qualification': {'strict_pair_qualified': True}})
        for kind in ('performance', 'canaries', 'campaign-identity'):
            filename = f'original-{profile}-{kind}.json'
            data = (p / f'baseline-strict/{kind}.json').read_bytes()
            (root / filename).write_bytes(data)
            references[filename] = {'source': f'prior-qualified/{profile}/{kind}.json',
                                    'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    put(root, 'original-reference-manifest.json', references)
    put(root, 'rowchunk-direct-output.json', {'passed': True, 'rows': [
        {'bit_differences': 0, 'repeat_bit_differences': {'baseline': 0, 'direct_out': 0},
         'speedup': 1.03} for _ in range(72)]})


class Gates(unittest.TestCase):
    def test_completed_negative_does_not_promote(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            d = summary.summarize(root)
            self.assertTrue(d['complete'])
            self.assertFalse(d['promotion_qualified'])
            self.assertFalse(d['profiles']['4b']['screen_speed_gate_passed'])

    def test_missing_profile_is_incomplete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            (root / '9b/DONE').unlink()
            self.assertFalse(summary.summarize(root)['complete'])

    def test_duplicate_and_divergent_rows_fail_closed(self):
        for mutation in ('duplicate', 'divergent', 'cached'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                fixture(root)
                path = root / '4b/candidate/summary.json'
                d = json.loads(path.read_text())
                if mutation == 'duplicate':
                    d['rows'][1] = d['rows'][0]
                elif mutation == 'divergent':
                    d['rows'][0]['token_ids'][0] = 3
                else:
                    d['rows'][0]['usage']['prompt_tokens_details']['cached_tokens'] = 1
                path.write_text(json.dumps(d))
                self.assertFalse(summary.summarize(root)['complete'])

    def test_original_output_or_manifest_tamper_fails(self):
        for mutation in ('original_output', 'manifest_hash'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                fixture(root)
                manifest_path = root / 'original-reference-manifest.json'
                manifest = json.loads(manifest_path.read_text())
                filename = 'original-4b-performance.json'
                if mutation == 'original_output':
                    path = root / filename
                    d = json.loads(path.read_text())
                    d['rows'][0]['token_ids'][0] = 999
                    path.write_text(json.dumps(d))
                    data = path.read_bytes()
                    manifest[filename].update(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
                else:
                    manifest[filename]['sha256'] = '0' * 64
                manifest_path.write_text(json.dumps(manifest))
                d = summary.summarize(root)
                self.assertFalse(d['complete'])
                self.assertIn('original reference', d['profiles']['4b']['error'])


if __name__ == '__main__':
    unittest.main()
