#!/usr/bin/env python3
"""Offline confirmation-admission/order tests; no Torch, endpoint or raw tensors."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
SOURCE = LANE / 'scripts/run-na-axis-confirm.py'
spec = importlib.util.spec_from_file_location('confirm_client_test', SOURCE)
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)
admit = client.admission_helpers
ROOT = client.ROOT
SERVER = ROOT / 'encoder-server-na-axis-10'
PACKET = ROOT / 'prepared-encoder-na-axis-10'
PREREG = json.loads((ROOT / admit.CAMPAIGN / 'preregistration.json').read_text())
PROGRESS = json.loads((ROOT / admit.CAMPAIGN / 'progress.json').read_text())
IDENTITY = json.loads((SERVER / 'server-identity.json').read_text())
BASE = json.loads((LANE / 'data/speed-resident-split-api.json').read_text())
SOURCES = client.source_identity(PACKET)


def actual_admission(root=ROOT, server=SERVER):
    return admit.admit(root, server, IDENTITY, BASE, PREREG['decoder_contract'], SOURCES, client.prior)


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actual = actual_admission()

    def test_actual_completed_screen_admission(self):
        self.assertEqual(self.actual['status'], 'completed-screen-admitted')
        self.assertEqual(self.actual['prior_requests'], 11)
        self.assertEqual(self.actual['prior_scoped_decodes'], 9)
        self.assertEqual(len(self.actual['discovery']['route']['calls']), 24)
        self.assertEqual(self.actual['identity']['pid'], 84255)
        self.assertEqual(self.actual['progress_sha256'], admit.PROGRESS_SHA)
        admit.verify_bindings(ROOT, self.actual, client.prior)

    def test_incomplete_wrong_schedule_owner_or_process(self):
        for kind in ('status', 'count', 'schedule', 'component', 'pid', 'boot', 'ticks', 'client'):
            progress, prereg, identity = copy.deepcopy(PROGRESS), copy.deepcopy(PREREG), copy.deepcopy(IDENTITY)
            if kind == 'status':
                progress['status'] = 'running'
            elif kind == 'count':
                progress['rows'].pop()
            elif kind == 'schedule':
                progress['rows'][4]['mode'] = 'axis-cache'
            elif kind == 'component':
                progress['rows'][5]['components']['generation'] += 1
            elif kind == 'pid':
                identity['pid'] += 1
            elif kind == 'boot':
                identity['boot_id'] = 'another-boot'
            elif kind == 'ticks':
                identity['proc_start_ticks'] = '1'
            else:
                prereg['client_sha256'] = 'changed'
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                admit.validate_progress(progress, prereg, identity, client.prior)

    def test_prior_oracle_binding_failures(self):
        row = PROGRESS['rows'][3]
        parity = json.loads((ROOT / admit.CAMPAIGN / (row['run'] + '-parity.json')).read_text())
        execution = parity['executions'][1]
        kwargs = dict(identity=IDENTITY, prompt_id=execution['prompt_id'],
                      prompt_sha=execution['prompt_sha256'], reference=row['reference'])
        admit.validate_parity(parity, row, **kwargs)
        for kind in ('unequal', 'layout', 'missing-output', 'wrong-prompt', 'wrong-graph', 'wrong-fixture', 'wrong-process'):
            changed = copy.deepcopy(parity)
            if kind == 'unequal':
                changed['comparisons']['images']['bitwise_equal'] = False
            elif kind == 'layout':
                changed['comparisons']['waveform']['same_layout'] = False
            elif kind == 'missing-output':
                del changed['comparisons']['audio_latent']
            elif kind == 'wrong-prompt':
                changed['executions'][1]['prompt_id'] = 'unrelated'
            elif kind == 'wrong-graph':
                changed['executions'][1]['prompt_sha256'] = 'changed'
            elif kind == 'wrong-fixture':
                changed['executions'][0]['name'] = 'another-reference'
            else:
                changed['executions'][1]['server_identity']['pid'] += 1
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                admit.validate_parity(changed, row, **kwargs)

    def test_end_to_end_changed_files_and_extra_attempts_rejected(self):
        with tempfile.TemporaryDirectory(prefix='na-confirm-admission-') as tmp:
            root = Path(tmp)
            paths = set(self.actual['evidence_sha256s']) | {
                str((SERVER / 'server-identity.json').relative_to(ROOT)),
                str((SERVER / 'components-01-split-control.json').relative_to(ROOT))}
            for relative in paths:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            server = root / SERVER.name
            actual_admission(root, server)
            for relative, mutate in [
                (Path(admit.CAMPAIGN) / 'progress.json', lambda value: value.update(status='running')),
                (Path('output/validation') / PROGRESS['rows'][3]['run'] / 'summary.json',
                 lambda value: value.update(deterministic_warn_only=True)),
                (Path(SERVER.name) / ('na-axis-' + PROGRESS['rows'][3]['run']) / 'result.json',
                 lambda value: value['owners'].update(decoder=999)),
            ]:
                path = root / relative
                old = path.read_bytes()
                value = json.loads(old)
                mutate(value)
                path.write_text(json.dumps(value))
                with self.subTest(path=str(relative)), self.assertRaises(RuntimeError):
                    actual_admission(root, server)
                with self.assertRaises(RuntimeError):
                    admit.verify_bindings(root, self.actual, client.prior)
                path.write_bytes(old)
            extra = server / 'na-axis-unregistered-attempt'
            extra.mkdir()
            with self.assertRaises(RuntimeError):
                actual_admission(root, server)
            extra.rmdir()
            (root / 'FAULT.json').write_text('{}')
            with self.assertRaises(RuntimeError):
                actual_admission(root, server)

    def test_balanced18_schedule_and_linear_drift_sign(self):
        rows = client.schedule('na-axis-confirm-01')
        self.assertEqual(len(rows), 18)
        self.assertEqual(len({row['run'] for row in rows}), 18)
        self.assertTrue(all(row['run'].startswith(f'na-axis-confirm-01-r{i:02d}-') for i, row in enumerate(rows, 1)))
        for fixture in ('boat', 'marble', 'bird'):
            modes = [row['mode'] for row in rows if row['fixture'] == fixture]
            self.assertEqual(modes.count('original'), 3)
            self.assertEqual(modes.count('axis-cache'), 3)
        for i, row in enumerate(rows):
            effect = -0.1 if row['mode'] == 'axis-cache' else 0
            row.update(status='passed', preview_ready_seconds=6 + i * .01 + effect,
                       decoder_node_seconds=.65 + i * .001 + effect)
        result = client.paired_results(rows)
        self.assertEqual(result['paired_samples'], 6)
        for triple in result['triples']:
            for metric in triple['metrics'].values():
                self.assertAlmostEqual(metric['cache_minus_original'], -.1)
        self.assertAlmostEqual(result['median_triplet_preview_delta'], -.1)
        for metric in result['fixture_mean_cache_minus_original'].values():
            self.assertAlmostEqual(metric['preview_ready_seconds'], -.1)
        rows[0]['mode'] = 'axis-cache'
        with self.assertRaises(RuntimeError):
            client.paired_results(rows)

    def test_unchanged_graph_and_gate_helpers(self):
        def functions(path):
            return {node.name: ast.dump(node) for node in ast.parse(path.read_text()).body if isinstance(node, ast.FunctionDef)}
        current = functions(SOURCE)
        previous = functions(LANE / 'scripts/run-na-axis-screen-v2.py')
        for name in ('expected_graph', 'normalized', 'validate_node_info', 'source_identity', 'validate_source_closure'):
            self.assertEqual(current[name], previous[name])
        self.assertEqual(hashlib.sha256((LANE / 'scripts/run-na-axis-screen-v2.py').read_bytes()).hexdigest(), admit.CLIENT_SHA)
        self.assertEqual(hashlib.sha256((LANE / 'scripts/ltx_na_axis_receipts.py').read_bytes()).hexdigest(), client.VALIDATOR_SHA)
        for row in client.schedule('cpu-confirm'):
            graph = client.expected_graph(BASE, row['mode'])
            self.assertNotIn('422', graph)
            self.assertTrue(all(graph[n]['inputs']['model'] == ['420', 0] for n in ('388', '391')))

    def test_numbered_retention_requires_parity(self):
        campaign = 'na-axis-confirm-01'
        rows = client.schedule(campaign)
        runs = {row['run'] for row in rows}
        with tempfile.TemporaryDirectory(prefix='na-confirm-retention-') as tmp:
            root = Path(tmp)
            for row in rows:
                run = row['run']
                relative = Path('output/validation') / run / 'tensors.safetensors'
                path = root / relative
                path.parent.mkdir(parents=True)
                path.write_bytes(b'test bytes')
                entry = client.retention.inventory(root, campaign, runs, run, relative)
                with self.assertRaises(RuntimeError):
                    client.retention.delete_owned(root, campaign, runs, entry, parity_passed=False, receipts=root / 'deletions.jsonl')
                self.assertTrue(path.exists())
                client.retention.delete_owned(root, campaign, runs, entry, parity_passed=True, receipts=root / 'deletions.jsonl')
                self.assertFalse(path.exists())

    def test_stdlib_only(self):
        self.assertNotIn('torch', sys.modules)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps({'status': 'passed' if result.wasSuccessful() else 'failed', 'tests': result.testsRun,
        'client_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'admission_helper_sha256': hashlib.sha256((LANE / 'scripts/ltx_na_axis_confirmation.py').read_bytes()).hexdigest(),
        'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'prior_progress_sha256': admit.PROGRESS_SHA, 'torch_imported': 'torch' in sys.modules,
        'native_requests': 0, 'scope': 'Saved evidence and temporary JSON/file mutations only; no live endpoint or tensor work'}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
