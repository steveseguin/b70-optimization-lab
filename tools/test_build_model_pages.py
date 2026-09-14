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
