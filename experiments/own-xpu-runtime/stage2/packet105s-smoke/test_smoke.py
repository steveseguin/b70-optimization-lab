"""CPU-only workload, exactness, receipt and lifecycle regression checks."""
import ast
import copy
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch, Mock
import smoke

smoke.verify_adapter()
from common import D, label, save


class SmokeTests(unittest.TestCase):
    def test_frozen_lifecycle_functions_unchanged(self):
        for filename, changed in [('screen.py', {'screen_main'}), ('tp2_worker.py', {'run'})]:
            original = ast.parse((smoke.WRAPPER / filename).read_text())
            adapted = ast.parse(smoke.adapted_source(filename))
            funcs = lambda tree: {n.name: ast.dump(n) for n in tree.body if isinstance(n, ast.FunctionDef)}
            before, after = funcs(original), funcs(adapted)
            self.assertEqual(before.keys(), after.keys())
            for name in before.keys() - changed:
                self.assertEqual(before[name], after[name], name)

    def test_adapter_refuses_unknown_source(self):
        with self.assertRaises(ValueError):
            smoke.once('missing', 'anchor', 'replacement')

    def test_grid_output_refused(self):
        with self.assertRaisesRegex(ValueError, 'grid outputs forbidden'):
            smoke.main(['--lane', 'B', '--output', str(smoke.OUTPUT.parent / 'grid'), '--plan'])

    def test_one_request_and_graceful_drain(self):
        worker = smoke.load_adapter('tp2_worker.py')
        manifest = D.oracle_inputs()
        tokens = D.CHECK.token_record(D.ORACLE / 'results' / smoke.PROMPT)[:64]
        self.assertEqual(len(tokens), 64)
        fake_pipeline = types.ModuleType('pipeline')
        fake_pipeline.parser = lambda: types.SimpleNamespace(parse_args=lambda argv: types.SimpleNamespace())
        fake_pipeline.Transport = type('Transport', (), {'__init__': lambda self, *a, **kw: None})
        fake_suite = types.ModuleType('suite')
        fake_suite.checker_module = Mock()
        fake_suite.admit_inputs = Mock(return_value={smoke.PROMPT: ('input', [1, 2])})
        fake_suite.reset = Mock(side_effect=lambda transport, dest: dest.mkdir(parents=True))
        fake_suite.run_request = Mock(return_value=dict(tokens=tokens, passed=True))
        fake_storage = types.ModuleType('storage')
        with tempfile.TemporaryDirectory(prefix='p105s-worker-test-') as tmp:
            root = Path(tmp)
            lineage = root / 'lineage'
            lineage.mkdir()
            for name in ('selection.json', 'memory-plan.json'):
                (lineage / name).write_text('{}')
            output = root / 'run'
            identity = dict(lineage=str(lineage), binary='unused', dispatch='unused',
                            timing='token', selection_sha256='unused', lane='B')
            placement = dict(draft_rank=1, target_split=32)
            with patch.dict('sys.modules', pipeline=fake_pipeline, suite=fake_suite, storage=fake_storage), \
                 patch('placement.verify_identity', return_value=(placement, Mock())), \
                 patch.object(worker.D, 'oracle_inputs', return_value=manifest), \
                 patch.object(worker, 'DeviceMonitor'), \
                 patch.object(worker, 'masked_environment', return_value={}), \
                 patch.object(worker, 'read', return_value=dict(passed=True)), \
                 patch.object(worker, 'drain') as drain:
                rc = worker.run(identity, output, 3600)
                self.assertEqual(rc, 0, (output / 'failure.json').read_text() if rc else '')
            fake_suite.run_request.assert_called_once()
            self.assertEqual(fake_suite.run_request.call_args.args[3], 64)
            self.assertEqual(len(fake_suite.admit_inputs.call_args.args[0]), 1)
            self.assertEqual(fake_suite.reset.call_count, 2)
            drain.assert_called_once()
            self.assertIs(drain.call_args.args[2], True)
            proof = json.loads((output / 'report-inputs.json').read_text())
            self.assertEqual(len(proof['requests']), 1)
            self.assertEqual(proof['incident64']['tokens_compared'], 64)

    def fixture(self, output):
        row = label(dict(prompt_id=smoke.PROMPT, passed=True, exact_oracle=True,
                         tokens=D.CHECK.token_record(D.ORACLE / 'results' / smoke.PROMPT)[:64]))
        receipt = output / 'run/incident64/receipt.json'
        receipt.parent.mkdir(parents=True)
        save(receipt, row)
        incident = dict(passed=True, tokens_compared=64, receipt_sha256=smoke.digest(receipt))
        timing = output / 'run/p105-transfers.jsonl'
        legs = [('hidden-export', 5120), ('hidden-import', 5120),
                ('best-export', 16), ('prefix-export', 16)]
        timing.write_text(''.join(json.dumps(dict(leg=leg, bytes=size, placement='compute',
            host_us=1, host_dependency_wait_us=1, prefix_submitted_before_publication=True)) + '\n'
            for leg, size in legs))
        return row, incident, timing

    def test_summary_exact_prefix_and_nonqualifying(self):
        with tempfile.TemporaryDirectory(prefix='p105s-summary-test-') as tmp:
            output = Path(tmp)
            row, incident, _ = self.fixture(output)
            result = smoke.smoke_summary([row], incident, output)
            self.assertEqual(result['request_count'], 1)
            self.assertFalse(result['realistic_final_gate']['passed'])
            self.assertFalse(result['speed_evidence_eligible'])
            bad = copy.deepcopy(row)
            bad['tokens'][0] += 1
            with self.assertRaisesRegex(ValueError, 'oracle mismatch'):
                smoke.smoke_summary([bad], incident, output)

    def test_missing_transfer_receipt_refused(self):
        with tempfile.TemporaryDirectory(prefix='p105s-transfer-test-') as tmp:
            output = Path(tmp)
            row, incident, timing = self.fixture(output)
            timing.write_text('\n'.join(timing.read_text().splitlines()[:-1]) + '\n')
            with self.assertRaisesRegex(ValueError, 'transfer receipts'):
                smoke.smoke_summary([row], incident, output)


if __name__ == '__main__':
    unittest.main()
