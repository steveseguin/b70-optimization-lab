#!/usr/bin/env python3
"""Real tiny CPU parameter/buffer diagnostics; no loaded runtime modifications."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
from contextlib import ExitStack

LANE = Path(__file__).resolve().parents[1]
def module(name, file):
    import sys
    spec = importlib.util.spec_from_file_location(name, file)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result
p = module('diagnostic_policy_fixture', LANE/'scripts/test-encoder-small-state-policy.py')
d = module('encoder_diagnostics', LANE/'scripts/encoder_diagnostics.py')
torch, CPU = p.base.torch, p.base.CPU
EXPECTED = d.SmallStateExpectation(13, 2, 180, 'cpu')


def clip(enabled=True, crop=False):
    patcher = p.make(enabled)
    patcher.model.ltx_crop_before_cpu = crop
    patcher.load(CPU, full_load=True)
    return types.SimpleNamespace(patcher=patcher, cond_stage_model=patcher.model)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root/'encoder-server-diagnostics-cpu'
        self.run.mkdir()
        (self.root/'model-verification.json').write_text('{"status":"passed"}')
        (self.run/'server-identity.json').write_text('{"fixture":"CPU only"}')
        self.env = patch.dict(os.environ, {'LTX_ENCODER_RUN_DIR': str(self.run)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.node = d.LTXEncoderPlacementCheck(expectation=EXPECTED, evidence_root=self.root)
    def test_metadata_reads_no_tensor_content_and_returns_same_conditioning(self):
        value = clip()
        before = p.base.hashes(value.patcher)
        conditioning = [[torch.arange(4), {'metadata': object()}]]
        forbidden = AssertionError('Tensor contents must not be read or copied')
        with ExitStack() as stack:
            for method in ('to', 'cpu', 'numpy', 'contiguous', 'clone', 'detach', 'data_ptr'):
                stack.enter_context(patch.object(torch.Tensor, method, side_effect=forbidden))
            for function in ('empty', 'zeros', 'ones', 'tensor', 'stack', 'cat'):
                stack.enter_context(patch.object(torch, function, side_effect=forbidden))
            result = self.node.check(value, conditioning, 'fixture-01', 'small_state')
        self.assertIs(result[0], conditioning)
        self.assertEqual(p.base.hashes(value.patcher), before)
        report = json.loads((self.run/'encoder-placement-fixture-01.json').read_text())
        self.assertTrue(report['passed'])
        self.assertEqual(report['inspection']['small_state']['total_bytes'], 180)
        self.assertEqual(report['inspection']['small_state']['rmsnorm_count'], 13)
        self.assertEqual(report['inspection']['small_state']['scalar_count'], 2)
    def test_control_reports_observed_cpu_placement_without_candidate_requirements(self):
        value = clip(False)
        result = d.placement_report(value, 'control-01', 'control')
        self.assertTrue(result['passed'])
        self.assertFalse(result['resident_gate_required'])
        self.assertTrue(all(r['device'] == 'cpu' for r in result['inspection']['small_state']['records']))
    def test_production_expectations_reject_cpu_fixture_and_record_failure(self):
        node = d.LTXEncoderPlacementCheck(evidence_root=self.root)
        with self.assertRaisesRegex(RuntimeError, 'placement gate failed'):
            node.check(clip(), [], 'wrong-device-01', 'small_state')
        result = json.loads((self.run/'encoder-placement-wrong-device-01.json').read_text())
        self.assertFalse(result['passed'])
        self.assertIn('small_state_inventory_mismatch', result['failures'])
        self.assertIn('small_state_placement_mismatch', result['failures'])
    def test_actual_dtype_and_option_mismatch_fail(self):
        value = clip(True, True)
        value.patcher.model.norm.weight.data = value.patcher.model.norm.weight.data.float()
        result = d.placement_report(value, 'dtype-01', 'small_state', EXPECTED)
        self.assertIn('crop_option_mismatch', result['failures'])
        self.assertIn('small_state_placement_mismatch', result['failures'])
        result = d.placement_report(clip(False), 'option-01', 'small_state', EXPECTED)
        self.assertIn('small_state_option_mismatch', result['failures'])
    def test_missing_accounting_marker_fails(self):
        value = clip()
        value.patcher.model._ltx_small_buffers_loaded = False
        result = d.placement_report(value, 'marker-01', 'small_state', EXPECTED)
        self.assertIn('small_state_accounting_marker_missing', result['failures'])
    def test_fault_bad_name_and_existing_receipt_reject(self):
        value = clip()
        for invalid in ('../escape', '-leading', 'Upper', 'with_under', 'x'*121):
            with self.assertRaises(ValueError):
                self.node.check(value, [], invalid, 'small_state')
        self.node.check(value, [], 'unique-01', 'small_state')
        before = (self.run/'encoder-placement-unique-01.json').read_bytes()
        with self.assertRaises(FileExistsError):
            self.node.check(value, [], 'unique-01', 'small_state')
        self.assertEqual((self.run/'encoder-placement-unique-01.json').read_bytes(), before)
        (self.root/'FAULT.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'Fault'):
            self.node.check(value, [], 'fault-01', 'small_state')
        self.assertFalse((self.run/'encoder-placement-fault-01.json').exists())
    def test_unload_receipt_keeps_owners_values_and_clears_accounting(self):
        value = clip()
        before_hash = p.base.hashes(value.patcher)
        before = d.begin_encoder_unload(value, 1, 2, 'small_state', 'control', root=self.root)
        value.patcher.detach()
        after = d.finish_encoder_unload(value, before, root=self.root)
        self.assertTrue(after['passed'])
        self.assertEqual(p.base.hashes(value.patcher), before_hash)
        self.assertEqual(after['after']['accounting']['reported_loaded_weight_bytes'], 0)
        self.assertFalse(after['after']['accounting']['small_buffers_loaded'])
        self.assertTrue((self.run/'encoder-unload-01-to-02.json').exists())
    def test_unload_gate_records_and_rejects_missing_detach(self):
        value = clip()
        before = d.begin_encoder_unload(value, 1, 2, 'small_state', 'control', root=self.root)
        with self.assertRaisesRegex(RuntimeError, 'unload gate failed'):
            d.finish_encoder_unload(value, before, root=self.root)
        receipt = json.loads((self.run/'encoder-unload-01-to-02.json').read_text())
        self.assertFalse(receipt['passed'])
        self.assertIn('unload_accounting_not_cleared', receipt['failures'])
    def test_additive_resident_hook_runs_through_all_variants(self):
        integration = module('diagnostic_resident_fixture', LANE/'scripts/test-encoder-runtime-integration.py')
        name = 'scripts/resident_node.py'
        integration.candidate = p.base.helpers.apply_patch_in_memory(
            integration.candidate, (LANE/'patches/resident-node-encoder-diagnostics.patch').read_text())
        old_context = d._context
        contexts = []
        def provide_fixture_identity(root):
            # Existing inactive integration fixture creates gate/run but no server.
            # Add only its synthetic identity, then use the real context checker.
            run = Path(os.environ['LTX_ENCODER_RUN_DIR'])
            if run.is_dir() and run.name.startswith('encoder-server-'):
                identity = run/'server-identity.json'
                if not identity.exists():
                    identity.write_text('{"fixture":"CPU integration only"}')
            result = old_context(root)
            contexts.append(result[0])
            return result
        with patch.object(d, '_context', side_effect=provide_fixture_identity):
            integration.Tests('test_resident_variants_unload_before_replacement_and_write_new_receipts').test_resident_variants_unload_before_replacement_and_write_new_receipts()
        # begin and finish each ran for control→crop→small_state→combined;
        # the final occupied receipt was rejected before any fourth unload.
        self.assertEqual(len(contexts), 6)

    def test_graph_api_has_no_expectation_override(self):
        self.assertEqual(set(self.node.INPUT_TYPES()['required']), {'clip', 'conditioning', 'run_name', 'encoder_variant'})
        self.assertNotIn('optional', self.node.INPUT_TYPES())

if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    files = [LANE/'scripts/encoder_diagnostics.py', LANE/'patches/resident-node-encoder-diagnostics.patch']
    print(json.dumps({'passed': result.wasSuccessful(), 'tests_run': result.testsRun,
                      'source_commit': p.base.PIN,
                      'artifact_sha256': {str(f.relative_to(LANE)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
                      'scope': 'Metadata-only CPU real tiny Gemma4; no GPU residency, latency or full-checkpoint proof'}, indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
