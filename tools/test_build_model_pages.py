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
    def test_video_observation_stays_scoped_and_missing_points_stay_missing(self):
        package = {
            'id': 'video-example', 'name': 'Video example', 'status': 'candidate',
            'guide': 'repro/video-example/README.md', 'hardware': {'cards': 4},
            'library': {'model_family': 'Example', 'modalities': ['video'],
                        'featured_metric': None, 'benchmark_status': 'Strict headline pending: full-window repeat needed.'},
            'video_measurements': {
                'scope': 'Early window only; 52 chunks, before maintenance.',
                'evidence': 'results/video.md', 'headline_row_label': '145 frames',
                'rows': [
                    {'label': 'Earlier setup', 'period_seconds': None, 'new_video_seconds': 6,
                     'samples': None, 'status': 'No retained timing', 'evidence': 'results/earlier.md'},
                    {'label': '145 frames', 'period_seconds': 5.2415, 'new_video_seconds': 6,
                     'samples': 52, 'status': 'Early-window observation', 'evidence': 'data/video.json'},
                ],
            },
        }
        output = MODULE.page(package, [package])
        self.assertIn('Strict headline pending: full-window repeat needed.', output)
        self.assertIn('>5.24</a>', output)
        self.assertIn('seconds per 6 seconds of new video', output)
        self.assertIn('Early window only; 52 chunks, before maintenance.', output)
        self.assertIn('<td>5.2415</td>', output)
        self.assertIn('<td>Not measured</td><td>6</td><td>Not measured</td>', output)
        self.assertIn('href="' + MODULE.GITHUB + 'data/video.json"', output)
        self.assertIn('No projection', output)
        self.assertNotIn('data-ml-measured=', output)
        self.assertNotIn('Tokens are pieces of words', output)
        self.assertNotIn('writing speed', output)
        self.assertNotIn('Writing speed and waiting time', output)
        self.assertIn('Several video streams at once', output)
        self.assertLess(output.index('>5.24</a>'), output.index('<div class="actions">'))
        self.assertEqual(output.count('id="video-observations"'), 1)
        self.assertIn('a short window does not prove sustained playback', output)

    def test_video_highlight_requires_explicit_measured_row(self):
        measurements = {'scope': 'Test scope', 'evidence': 'results/video.md',
                        'rows': [{'label': 'Unmeasured', 'period_seconds': None,
                                  'status': 'Pending', 'evidence': 'results/video.md'}],
                        'headline_row_label': 'Unmeasured'}
        output = MODULE.video_observations(measurements)
        self.assertNotIn('class="big', output)
        self.assertIn('Not measured', output)

    def test_metric_label_uses_declared_unit(self):
        library = {'featured_metric': {'value': 5.24, 'unit': 's/chunk'}}
        self.assertEqual(MODULE.metric_text(library), '5.2 s/chunk')

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
