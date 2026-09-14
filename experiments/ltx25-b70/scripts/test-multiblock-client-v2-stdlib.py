#!/usr/bin/env python3
"""Packet07 all48 client/receipt source contracts; no requests or native imports."""
import argparse
import ast
import io
from types import SimpleNamespace
from unittest.mock import patch
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('multiblock_screen_v2_tested', SCRIPTS / 'run-multiblock-screen-v2.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class Contracts(unittest.TestCase):
    def test_closed_schedule_and_names(self):
        rows = client.schedule('multiblock-screen-02')
        self.assertEqual(len(rows), 12)
        self.assertEqual(len({r['run'] for r in rows}), 12)
        self.assertTrue(all(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', r['run']) for r in rows))
        self.assertEqual([r['mode'] for r in rows[:2]], ['original', 'original'])
        self.assertEqual([r['selection'] for r in rows if r['mode'] == 'compiled' and r['initialization']],
                         ['all48'])

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

    def test_inherited_packet06_templates_match(self):
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
        self.assertEqual(len(owners), 2)

    def test_owner_mutations_rejected(self):
        owners = {'original': 1, 'all48': 20}
        good = {'original_id': 1, 'selection': 'all48', 'candidate_id': 20, 'retained_candidate_count': 1}
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
        self.assertEqual(client.paired_results(rows)['all48']['paired_samples'], 2)

    def test_invalid_pair_timing_rejected(self):
        rows = client.schedule('screen')
        for row in rows:
            row['status'] = 'passed'
            row['profile'] = {'preview_ready_seconds': 6}
        for invalid in (0, -1, float('inf'), float('nan'), True):
            rows[4]['profile']['preview_ready_seconds'] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(RuntimeError):
                client.paired_results(rows)


class SuccessorContracts(unittest.TestCase):
    def test_helper_math_and_gates_unchanged(self):
        previous = ast.parse((SCRIPTS / 'ltx_multiblock_receipts.py').read_text())
        current = ast.parse((SCRIPTS / 'ltx_multiblock_receipts_v2.py').read_text())
        previous_functions = [n for n in previous.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
        current_functions = [n for n in current.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
        self.assertEqual([ast.dump(n) for n in previous_functions], [ast.dump(n) for n in current_functions])

    def test_existing_identity_and_quality_paths_unchanged(self):
        old = ast.parse((SCRIPTS / 'run-multiblock-screen-v1.py').read_text())
        new = ast.parse((SCRIPTS / 'run-multiblock-screen-v2.py').read_text())
        for name in ('identity_binding', 'expected_graph', 'normalized', 'validate_owner_continuity', 'paired_results', 'parse_args', 'main'):
            before = next(n for n in old.body if isinstance(n, ast.FunctionDef) and n.name == name)
            after = next(n for n in new.body if isinstance(n, ast.FunctionDef) and n.name == name)
            self.assertEqual(ast.dump(before), ast.dump(after), name)
        before = next(n for n in old.body if isinstance(n, ast.FunctionDef) and n.name == 'run_campaign')
        after = next(n for n in new.body if isinstance(n, ast.FunctionDef) and n.name == 'run_campaign')
        class NormalizeScope(ast.NodeTransformer):
            def visit_Constant(self, node):
                if node.value == 12:
                    node.value = 32
                if node.value == 'all48 adjacent-state reuse; original/compiled/restored in one process, control encoder':
                    node.value = 'single24, boundary4, all48; original/compiled/restored in one process, control encoder'
                return node
        self.assertEqual(ast.dump(before), ast.dump(NormalizeScope().visit(after)))

    def test_check_only_avoids_endpoint_and_lock(self):
        args = SimpleNamespace(campaign='check-only', packet=client.ROOT / 'prepared-encoder-compiler-06',
            server_run=client.ROOT / 'encoder-server-adjacent-check-never-created',
            manifest_sha256=client.PACKET_SHA, check_only=True)
        with patch.object(client, 'parse_args', return_value=args), \
             patch.object(client, 'load', return_value=object()), \
             patch.object(client, 'prepared_sources') as prepared, \
             patch.object(client, 'run_campaign', side_effect=AssertionError('native path')) as execute, \
             patch.object(client, 'identity_binding', side_effect=AssertionError('endpoint')) as identity, \
             patch.object(client.fcntl, 'flock', side_effect=AssertionError('lock')) as lock, \
             patch('sys.stdout', new_callable=io.StringIO) as output:
            client.main()
            self.assertEqual(json.loads(output.getvalue())['native_requests'], 0)
            prepared.assert_called_once()
            execute.assert_not_called()
            identity.assert_not_called()
            lock.assert_not_called()

    def test_required_cli_and_all48_only(self):
        with self.assertRaises(SystemExit), patch('sys.stderr', new_callable=io.StringIO):
            client.parse_args([])
        args = client.parse_args(['--campaign', 'adjacent-screen', '--packet', '/packet',
            '--manifest-sha256', 'a' * 64, '--server-run', '/server', '--check-only'])
        self.assertTrue(args.check_only)
        self.assertEqual(client.SELECTIONS, {'all48': tuple(range(48))})
        self.assertEqual(len(client.schedule(args.campaign)), 12)


# Reuse the frozen synthetic receipt fixture suite with the successor helper.
# These fixtures cover all helper-supported selections; the client only submits all48.
assert hashlib.sha256((SCRIPTS / 'test-ltx-multiblock-receipts.py').read_bytes()).hexdigest() == '019d9646c34d3d2a2310f04ec8b4677500763a2d9cd1b5843f6dfd966b394741'
receipt_spec = importlib.util.spec_from_file_location('multiblock_receipt_suite_v2', SCRIPTS / 'test-ltx-multiblock-receipts.py')
receipt_suite = importlib.util.module_from_spec(receipt_spec)
receipt_spec.loader.exec_module(receipt_suite)
new_spec = importlib.util.spec_from_file_location('new_multiblock_receipts_v2', SCRIPTS / 'ltx_multiblock_receipts_v2.py')
new_receipts = importlib.util.module_from_spec(new_spec)
new_spec.loader.exec_module(new_receipts)
receipt_suite.receipts = new_receipts


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls)
        for cls in (Contracts, SuccessorContracts, receipt_suite.Contracts))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {'passed': result.wasSuccessful(), 'tests': result.testsRun,
              'failures': len(result.failures), 'errors': len(result.errors),
              'torch_imported': 'torch' in sys.modules,
              'scope': 'stdlib-only all48 client and receipt contracts; no endpoint access or requests',
              'packet_manifest_sha256': client.PACKET_SHA,
              'source_sha256s': {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (Path(__file__), SCRIPTS / 'run-multiblock-screen-v2.py',
                            SCRIPTS / 'ltx_multiblock_receipts_v2.py', SCRIPTS / 'test-ltx-multiblock-receipts.py')}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    raise SystemExit(not result.wasSuccessful() or report['torch_imported'])
