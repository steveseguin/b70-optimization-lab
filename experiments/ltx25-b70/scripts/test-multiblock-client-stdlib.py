#!/usr/bin/env python3
"""Offline schedule, graph, ownership and paired-timing checks; no requests/Torch."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('multiblock_screen_tested', SCRIPTS / 'run-multiblock-screen-v1.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class Contracts(unittest.TestCase):
    def test_closed_schedule_and_names(self):
        rows = client.schedule('multiblock-screen-01')
        self.assertEqual(len(rows), 32)
        self.assertEqual(len({r['run'] for r in rows}), 32)
        self.assertTrue(all(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', r['run']) for r in rows))
        self.assertEqual([r['mode'] for r in rows[:2]], ['original', 'original'])
        self.assertEqual([r['selection'] for r in rows if r['mode'] == 'compiled' and r['initialization']],
                         ['single24', 'boundary4', 'all48'])

    def test_selection_qualification_and_timeouts(self):
        rows = client.schedule('a' * 64)
        self.assertTrue(all(len(r['run']) <= 120 for r in rows))
        for selection in client.SELECTIONS:
            cold = [r for r in rows if r['selection'] == selection and r['mode'] == 'compiled' and r['initialization']]
            self.assertEqual(len(cold), 1)
            self.assertEqual(cold[0]['qualified_before'], 0)
            self.assertEqual(cold[0]['timeout_seconds'], client.COLD_TIMEOUTS[selection])
            triples = [r for r in rows if r['selection'] == selection and r['pair']]
            self.assertEqual(len(triples), 9)
            self.assertTrue(all(r['qualified_before'] == 2 and not r['initialization'] for r in triples))
            for fixture in ('boat', 'marble', 'bird'):
                self.assertEqual([r['mode'] for r in triples if r['fixture'] == fixture],
                                 ['restored', 'compiled', 'restored'])

    def test_unsafe_campaigns(self):
        for value in ('', 'a_b', '../a', '/a', 'A', 'a' * 65, 'a b', None):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                client.schedule(value)

    def test_all_sealed_templates_match(self):
        base = json.loads((SCRIPTS.parent / 'data/speed-resident-split-api.json').read_text())
        packet = client.ROOT / 'prepared-encoder-compiler-06'
        saved = copy.deepcopy(base)
        for selection in client.SELECTIONS:
            for mode in ('original', 'compiled', 'restored'):
                expected = client.expected_graph(base, mode, selection)
                actual = json.loads((packet / 'graphs' / f'multiblock-{selection}-{mode}.json').read_text())
                self.assertEqual(client.normalized(actual), client.normalized(expected))
        self.assertEqual(base, saved)
        with self.assertRaises(RuntimeError):
            client.expected_graph(base, 'eager', 'all48')

    def test_selection_and_numerical_graph_changes_remain_visible(self):
        base = json.loads((SCRIPTS.parent / 'data/speed-resident-split-api.json').read_text())
        original = client.expected_graph(base, 'compiled', 'all48')
        for node, key, value in [('422', 'selection', 'single24'), ('422', 'mode', 'original'),
                                 ('338', 'noise_seed', 999)]:
            other = copy.deepcopy(original)
            other[node]['inputs'][key] = value
            # Noise seeds are normalized by the legacy graph normalizer, then
            # separately compared with fixed fixtures in run_campaign.
            if key != 'noise_seed':
                self.assertNotEqual(client.normalized(other), client.normalized(original))

    def test_ownership_full_schedule(self):
        owners = {}
        seen = set()
        for row in client.schedule('screen'):
            selection = row['selection']
            candidate = None if row['mode'] == 'original' else list(client.SELECTIONS).index(selection) + 20
            if candidate is not None:
                seen.add(selection)
            client.validate_owner_continuity(owners, {'original_id': 1, 'selection': selection,
                'candidate_id': candidate, 'retained_candidate_count': len(seen)})
        self.assertEqual(len(owners), 4)

    def test_owner_mutations_rejected(self):
        owners = {'original': 1, 'single24': 20}
        good = {'original_id': 1, 'selection': 'single24', 'candidate_id': 20, 'retained_candidate_count': 1}
        for key, value in [('original_id', 2), ('candidate_id', 21), ('retained_candidate_count', 3),
                           ('selection', 'boundary4')]:
            changed = {**good, key: value}
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                client.validate_owner_continuity(dict(owners), changed)

    def test_paired_statistics_exclude_initialization(self):
        rows = client.schedule('screen')
        for row in rows:
            row['status'] = 'passed'
            row['profile'] = {'preview_ready_seconds': 100 if row['initialization'] else
                              (5 if row['mode'] == 'compiled' else 6)}
        results = client.paired_results(rows)
        for result in results.values():
            self.assertEqual(result['paired_samples'], 3)
            self.assertEqual(result['median_compiled_minus_control_mean_seconds'], -1)
        rows[4]['status'] = 'failed'
        self.assertEqual(client.paired_results(rows)['single24']['paired_samples'], 2)

    def test_invalid_pair_timing_rejected(self):
        rows = client.schedule('screen')
        for row in rows:
            row['status'] = 'passed'
            row['profile'] = {'preview_ready_seconds': 6}
        for invalid in (0, -1, float('inf'), float('nan'), True):
            rows[4]['profile']['preview_ready_seconds'] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(RuntimeError):
                client.paired_results(rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    report = {'passed': result.wasSuccessful(), 'tests': result.testsRun,
              'failures': len(result.failures), 'errors': len(result.errors),
              'torch_imported': 'torch' in sys.modules,
              'scope': 'stdlib-only client contracts; no endpoint access or requests',
              'source_sha256s': {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in (Path(__file__), SCRIPTS / 'run-multiblock-screen-v1.py')}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    raise SystemExit(not result.wasSuccessful() or report['torch_imported'])
