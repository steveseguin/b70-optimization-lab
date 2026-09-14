"""Public chart labels must preserve measurement meaning without lab shorthand."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('build_model_pages', ROOT / 'tools/build-model-pages.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HumanPages(unittest.TestCase):
    def test_internal_run_names_are_not_public_labels(self):
        profile = {'label': 'R187 FP8 TP2 MTP0 HTTP decode over exact active context', 'metric': 'decode'}
        self.assertEqual(MODULE.public_profile_label(profile), 'Writing speed · 2 GPUs · no draft')

    def test_draft_depth_does_not_invent_gpu_count(self):
        for depth in (0, 1, 4):
            profile = {'label': f'R139 MTP{depth} effective prompt throughput', 'metric': 'prefill'}
            self.assertNotIn('GPU', MODULE.public_profile_label(profile))
        profile = {'label': 'R139 TP2 MTP1 effective prompt throughput', 'metric': 'prefill'}
        self.assertIn('2 GPUs', MODULE.public_profile_label(profile))

    def test_draft_sweep_is_not_labeled_as_fixed_depth(self):
        profile = {'label': 'Strict TP2 decode with and without MTP2', 'metric': 'decode', 'x_metric': 'speculative_tokens'}
        label = MODULE.public_profile_label(profile)
        self.assertIn('2 GPUs', label)
        self.assertIn('different draft lengths', label)
        self.assertNotIn('2-token draft', label)

    def test_raw_zero_context_is_not_zero_input(self):
        profile = {'label': 'Q4_K_M raw pp2048 with F16 KV', 'metric': 'prefill'}
        self.assertEqual(MODULE.public_x_label(profile), 'Tokens already in memory')
        self.assertIn('2,048 new tokens', MODULE.public_profile_scope(profile))
        self.assertIn('Zero means empty memory', MODULE.public_profile_scope(profile))

    def test_ttft_proxy_is_not_presented_as_server_prefill(self):
        profile = {'label': 'Prefill over prompt length', 'metric': 'prefill', 'scope': 'Approximate prompt tokens divided by TTFT, averaged across four independent one-B70 lanes.'}
        self.assertIn('estimated from first-token wait', MODULE.public_profile_label(profile))
        self.assertIn('differs from server prefill', MODULE.public_profile_scope(profile))

    def test_engine_sequences_are_not_labeled_as_http_users(self):
        profile = {'label': 'Accepted-stack aggregate', 'metric': 'aggregate_decode',
                   'x_metric': 'concurrent_sequences', 'scope': 'Raw-engine measurements.'}
        self.assertIn('Parallel sequences', MODULE.public_x_label(profile))
        self.assertIn('Engine test', MODULE.public_profile_scope(profile))
        self.assertNotIn('users', MODULE.public_profile_scope(profile))

    def test_queued_requests_and_answer_variation_remain_explicit(self):
        profile = {'label': 'Queued Q8_0 TP1 HTTP aggregate decode',
                   'metric': 'aggregate_decode', 'x_metric': 'concurrent_sequences',
                   'scope': 'Eight active slots; excess requests queued. Output is batch-shape-dependent.'}
        self.assertIn('including waiting', MODULE.public_x_label(profile))
        self.assertIn('Up to 8 users', MODULE.public_profile_scope(profile))
        self.assertIn('Answers can change', MODULE.public_profile_scope(profile))

    def test_graph_preserves_exact_hover_values(self):
        profile = {'label': 'R187 TP2 MTP1 decode', 'metric': 'decode', 'unit': 'tok/s', 'points': [{'context_tokens': 128, 'value': 1.23456}, {'context_tokens': 512, 'value': 2.34567}]}
        output = MODULE.svg_profile(profile)
        self.assertIn('128; 1.23456 tok/s</title>', output)
        self.assertIn('tabindex="0"', output)
        self.assertNotIn('R187', output)

    def test_prefill_highlights_keep_each_measured_setup_and_exclude_proxies(self):
        import copy
        packages = json.loads((ROOT / 'packages/catalog.json').read_text())['packages']
        package = copy.deepcopy(next(p for p in packages if p['id'] == 'qwen35-4b-w4a16-b70'))
        base = next(p for p in package['performance_profiles'] if p.get('measurement_kind') == 'server_prefill')
        second = copy.deepcopy(base)
        second.update(id='followup-tp2', public_label='Reading speed · 2 GPUs · 3-token draft')
        second['operating_profile']['tensor_parallel_size'] = 2
        second['operating_profile']['max_model_len'] = 4096
        for point in second['points']:
            point['value'] = 1234.5
        proxy = copy.deepcopy(second)
        proxy.update(id='http-proxy', measurement_kind='http_ttft_proxy')
        for point in proxy['points']:
            point['value'] = 987.6
        package['performance_profiles'] = [base, second, proxy]
        output = MODULE.page(package, packages)
        section = output.split('<h2 id="prefill">')[1].split('<details')[0]
        self.assertEqual(section.count('input tokens/s'), 2)
        self.assertIn('1 GPU(s)', section)
        self.assertIn('2 GPU(s)', section)
        self.assertIn('1,024-token capacity', section)
        self.assertIn('4,096-token capacity', section)
        self.assertNotIn('987.6', section)

    def test_catalog_profiles_and_accessible_tables_render(self):
        packages = json.loads((ROOT / 'packages/catalog.json').read_text())['packages']
        for package in packages:
            output = MODULE.page(package, packages)
            self.assertEqual(output.count('<details'), output.count('</details>'))
            for profile in package.get('performance_profiles', []):
                self.assertNotRegex(MODULE.public_profile_label(profile), r'\bR\d{2,}')
                for point in profile.get('points', []):
                    self.assertIn(f'<td>{point["value"]}</td>', output)


if __name__ == '__main__':
    unittest.main()
