"""Follow-up values must stay bound to their measured setup and preserve history."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'sync_prefill_followup_profiles', ROOT / 'tools/sync-prefill-followup-profiles.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
R304 = 'sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2'


def fixture_summary():
    profiles = {}
    for index, (key, (_, _, cards, depth, quant)) in enumerate(MODULE.PACKAGES.items()):
        profiles[key] = {
            'complete': True, 'quality_exact': True, 'promotion_qualified': False,
            'identity': {'tensor_parallel_size': cards, 'speculative_tokens': depth,
                         'quantization': quant, 'parent_image': R304},
            'points': [{'prompt_tokens': length, 'samples': 18,
                        'mean_controls': {'server_prefill_tokens_per_s': 1234.5 + index * 100 + length},
                        'candidate': {'server_prefill_tokens_per_s': 999999}}
                       for length in (256, 512)],
        }
    return {'complete': True, 'promotion_qualified': False, 'profiles': profiles}


class FollowupProjection(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(MODULE, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.summary = fixture_summary()
        self.write_summary()

    def write_summary(self):
        path = self.root / MODULE.SOURCE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.summary))

    def run_sync(self, check=False):
        with patch('sys.argv', ['sync-prefill-followup-profiles.py'] + (['--check'] if check else [])):
            with contextlib.redirect_stdout(io.StringIO()):
                MODULE.main()

    def test_wrong_setup_identity_fails(self):
        original = copy.deepcopy(self.summary)
        for key in MODULE.PACKAGES:
            for field, wrong in [('tensor_parallel_size', 4), ('speculative_tokens', 0),
                                 ('quantization', 'FP8'), ('parent_image', 'sha256:wrong-runtime')]:
                with self.subTest(profile=key, field=field):
                    self.summary = copy.deepcopy(original)
                    self.summary['profiles'][key]['identity'][field] = wrong
                    self.write_summary()
                    with self.assertRaises(ValueError):
                        MODULE.profiles()

    def test_incomplete_or_failed_quality_cannot_be_published(self):
        for field in ('complete', 'quality_exact'):
            with self.subTest(field=field):
                self.summary = fixture_summary()
                self.summary['profiles']['4b-tp2'][field] = False
                self.write_summary()
                with self.assertRaises(ValueError):
                    MODULE.profiles()

    def test_baseline_rates_and_each_topology_remain_separate(self):
        projected = MODULE.profiles()
        self.assertEqual(set(projected), set(MODULE.PACKAGES))
        self.assertEqual(len({p['id'] for p in projected.values()}), 3)
        for key, result in projected.items():
            with self.subTest(profile=key):
                expected = self.summary['profiles'][key]
                self.assertFalse(result['promotion_qualified'])
                self.assertEqual(result['measurement_kind'], 'server_prefill')
                self.assertEqual(result['operating_profile']['image_id'], R304)
                self.assertEqual(result['operating_profile']['tensor_parallel_size'],
                                 expected['identity']['tensor_parallel_size'])
                self.assertEqual([p['value'] for p in result['points']],
                                 [p['mean_controls']['server_prefill_tokens_per_s']
                                  for p in expected['points']])

    def test_actual_homepage_has_exactly_the_three_selected_matches(self):
        html = (ROOT / 'index.html').read_text()
        rows = re.findall(r'<tr\b[^>]*>.*?</tr>', html, re.S)
        matched = []
        for key in MODULE.PACKAGES:
            matches = [row for row in rows if MODULE.row_matches(key, row)]
            with self.subTest(profile=key):
                self.assertEqual(len(matches), 1)
                self.assertIn('model-prefill', matches[0])
            matched.extend(matches)
        self.assertEqual(len(set(matched)), 3)

    def test_sync_preserves_existing_profiles_and_nonselected_homepage_rows(self):
        html = (ROOT / 'index.html').read_text()
        (self.root / 'index.html').write_text(html)
        manifest_path = self.root / MODULE.DATA / 'evidence/manifest.json'
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(json.dumps({'archives': [{'archive': 'baseline.tar.gz'}],
                                             'source_files': [{'repository_path': 'tools/retained-client.py'}]}))
        old_profiles = [
            {'id': 'decode-history', 'metric': 'decode', 'points': [{'value': 91.25}]},
            {'id': 'short-prompt-server-prefill-control', 'metric': 'prefill',
             'operating_profile': {'tensor_parallel_size': 99}, 'points': [{'value': 2222}]},
        ]
        package_paths = []
        for package, _, _, _, _ in MODULE.PACKAGES.values():
            path = self.root / 'packages' / package / 'package.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'id': package, 'dependencies': ['preserve/history.json'],
                                        'performance_profiles': copy.deepcopy(old_profiles),
                                        'unrelated': {'label': 'Keep this résumé'}}))
            package_paths.append(path)
        original_rows = re.findall(r'<tr\b[^>]*>.*?</tr>', html, re.S)
        self.run_sync()
        updated_rows = re.findall(r'<tr\b[^>]*>.*?</tr>', (self.root / 'index.html').read_text(), re.S)
        self.assertEqual(len(original_rows), len(updated_rows))
        changed = []
        for before, after in zip(original_rows, updated_rows):
            keys = [key for key in MODULE.PACKAGES if MODULE.row_matches(key, before)]
            if not keys:
                self.assertEqual(before, after)
                continue
            self.assertEqual(len(keys), 1)
            changed.append(keys[0])
            self.assertIn(f'data-prefill-profile="{keys[0]}"', after)
            strip_prefill = lambda text: re.sub(
                r'<td\b[^>]*class="[^"]*model-prefill[^"]*"[^>]*>.*?</td>', '', text, flags=re.S)
            self.assertEqual(strip_prefill(before), strip_prefill(after))
        self.assertEqual(set(changed), set(MODULE.PACKAGES))
        for path in package_paths:
            result = json.loads(path.read_text())
            self.assertEqual(result['performance_profiles'][:2], old_profiles)
            self.assertEqual(len(result['performance_profiles']), 3)
            self.assertEqual(result['dependencies'][0], 'preserve/history.json')
            self.assertEqual(result['unrelated'], {'label': 'Keep this résumé'})
        paths = package_paths + [self.root / 'index.html']
        saved = {path: path.read_bytes() for path in paths}
        self.run_sync(check=True)
        self.run_sync()
        self.assertEqual(saved, {path: path.read_bytes() for path in paths})


if __name__ == '__main__':
    unittest.main()
