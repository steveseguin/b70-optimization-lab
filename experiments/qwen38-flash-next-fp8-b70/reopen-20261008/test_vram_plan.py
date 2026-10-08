"""Attempt-6 budget, historical preservation and admission regressions; CPU only."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import apply_overlay
import memory_plan
import screen
import vram_plan as v
from placement_plan import v5


class VramPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads((v.HERE/'placement-certified-v5.json').read_text())
        cls.census = [json.loads((v.HERE.parent/f'data/20260907-tp4-mtp1-a315-routing-census-rank{r}.json').read_text()) for r in range(4)]
        cls.placement, cls.receipt = v.expanded_placement(cls.original, cls.census)
        cls.command = screen.launch(SimpleNamespace(mode='calibrate-load', port=19988), Path('/tmp/attempt6-unused'))

    def test_preserve_certified_bytes_and_reproducible_additions(self):
        self.assertEqual(hashlib.sha256((v.HERE/'placement-certified-v5.json').read_bytes()).hexdigest(),
                         'f3f4812cfae2f4f704e75cc9b47a4031a476f846b353e3def23141b9d9c05f96')
        self.assertEqual(self.placement, json.loads((v.HERE/v.PLACEMENT).read_text()))
        for rank in range(4):
            self.assertEqual(sum(map(len, self.placement[str(rank)].values())), 2600)
            for layer in range(48):
                device, host = v5.row_plan(self.placement, rank, layer)
                self.assertTrue(set(self.original[str(rank)].get(str(layer), [])).issubset(host))
                self.assertEqual(sorted(device+host), list(range(128)))
                self.assertTrue(device)

    def test_missing_census_refuses(self):
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            v.expanded_placement(self.original, [{}, *self.census[1:]])

    def test_infeasible_placement_refuses(self):
        with self.assertRaisesRegex(ValueError, 'infeasible'):
            v.expanded_placement(self.original, self.census, 6144)

    def test_launch_budget_and_mtp1_calibration_identity(self):
        ident = memory_plan.launch_identity(self.command)
        self.assertEqual(ident['gpu_memory_utilization'], '0.90')
        self.assertEqual(ident['placement'], '/screen-package/'+v.PLACEMENT)
        self.assertEqual(ident['kv_bytes_per_rank'], 376569856)
        wrong = self.command.copy()
        wrong[wrong.index('0.90')] = '0.92'
        with self.assertRaisesRegex(ValueError, 'utilization'):
            memory_plan.launch_identity(wrong)

    def test_full_header_budget_and_no_false_admission(self):
        p = memory_plan.build_prediction(self.command)
        self.assertEqual(p['final_pins_bytes_per_rank'], [14171275264]*4)
        self.assertEqual(sum(p['replication_aware_weight_census_before_offload'].values()), 35842011128)
        self.assertGreater(p['illustrative_host_peak_bytes'], 97_000_000_000)
        self.assertEqual(p['illustrative_components']['pinned_allocator_rounding_bytes'], 24_249_237_504)
        for row in p['vram_planning_scenario']['ranks']:
            self.assertGreaterEqual(row['utilization_headroom_bytes'], v.GIB)
            self.assertGreaterEqual(row['total_used_utilization_headroom_bytes'], v.GIB)
            self.assertGreaterEqual(row['predicted_free_bytes'], 4*v.GIB)
            self.assertGreaterEqual(row['resident_weight_floor_bytes']+row['static_replication_scales_allowance_bytes'], 22744641528)
        self.assertIsNone(p['host_peak_bytes'])
        self.assertEqual(p['vram_peak_bytes_per_rank'], [None]*4)
        with self.assertRaisesRegex(RuntimeError, 'Memory admission refused'):
            memory_plan.enforce_prediction(p)

    def test_workspace_geometry_drift_refuses(self):
        spec = json.loads((v.HERE/'memory-bounds.json').read_text())['attempt6_vram_scenario']
        identity = memory_plan.launch_identity(self.command)
        identity['max_num_batched_tokens'] = 4352
        with self.assertRaisesRegex(ValueError, 'chunk64'):
            v.scenario([0]*4, spec, identity)

    def test_new_support_inputs_are_sealed(self):
        manifest = apply_overlay.verify_package()
        for name in (v.PLACEMENT, 'vram_plan.py', 'placement_plan.py'):
            self.assertIn(name, manifest['support_files'])

    def test_graph_geometry_drift_refuses(self):
        spec = json.loads((v.HERE/'memory-bounds.json').read_text())['attempt6_vram_scenario']
        identity = memory_plan.launch_identity(self.command)
        identity['compilation']['cudagraph_capture_sizes'] = [1, 2048]
        with self.assertRaisesRegex(ValueError, 'capture sizes'):
            v.scenario([0]*4, spec, identity)


if __name__ == '__main__':
    unittest.main()
