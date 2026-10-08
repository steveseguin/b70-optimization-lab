"""CPU regression gates for observed phases and the missed host size classes."""
import json
from pathlib import Path
import unittest

import analyze_host_budget as a

HERE = Path(__file__).resolve().parent


class HostBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reports = {n: a.analyze(HERE/f'runs/screen1b-mmap-calibrate-load-20261008-attempt{n}')
                       for n in (4, 5, 6)}
        cls.placement = json.loads((HERE/'placement-attempt6-v5.json').read_text())
        cls.contract = json.loads((HERE/'memory-contract.json').read_text())
        cls.budget = a.build_budget(cls.reports[6], cls.placement, cls.contract)

    def test_size_class_edges_and_empty(self):
        self.assertEqual([a.rounded(n) for n in (0, 1, 1024, 1025)], [0, 1, 1024, 2048])
        for n in (-1, 1.5, True):
            with self.assertRaises(ValueError):
                a.rounded(n)
        # One extra expert doubles BOTH allocations at this real boundary.
        self.assertEqual(sum(a.rounded(41*w)-a.rounded(40*w) for w in a.ROW.values()), 192*2**20)

    def test_attempt5_has_no_load_and_cannot_prove_shadow_saving(self):
        report = self.reports[5]
        self.assertNotIn('load_begin', report['reached_events'])
        self.assertEqual(report['rank_progress'], [])
        self.assertIsNone(report['first_refusal'])

    def test_attempt4_did_not_allocate_large_expert_pins_or_ple(self):
        peak = self.reports[4]['peak']
        self.assertEqual(peak['expert_payload_bytes'], 4_507_238_400)
        self.assertEqual(peak['GPUActive'], 74_062_659_584)
        self.assertEqual(peak['ple_bound_ranks'], 0)

    def test_attempt6_progress_is_allocations_not_loaded_checkpoint_bytes(self):
        ranks = self.reports[6]['rank_progress']
        self.assertEqual([r['parameters'] for r in ranks], [96, 78, 84, 96])
        self.assertEqual([r['ple_bound'] for r in ranks], [False, False, False, True])
        self.assertEqual(self.reports[6]['allocation_snapshot_files'], [])
        self.assertNotIn('allocation_snapshot', self.reports[6]['reached_events'])
        self.assertEqual(self.reports[6]['staging'], {'live': {}, 'peak_bytes':268431360})

    def test_peak_attribution_matches_rounded_experts_not_raw_bytes(self):
        peak = self.reports[6]['peak']
        self.assertEqual(peak['expert_payload_bytes'], 46_959_820_800)
        self.assertEqual(peak['expert_reserved_assumption_bytes'], 68_451_041_280)
        self.assertEqual(self.budget['anchor_unattributed_gpu_bytes'], 1_390_067_712)
        startup = self.reports[6]['phase_peaks']['startup_or_init_device']['GPUActive']
        self.assertLess(abs(self.budget['anchor_unattributed_gpu_bytes']-startup), 10_000_000)

    def test_budget_does_not_add_rss_or_gpuactive_twice(self):
        b = self.budget
        self.assertEqual(b['plateau_scenario_bytes'], 100_623_034_450)
        self.assertEqual(b['loading_scenario_bytes']-b['plateau_scenario_bytes'], 256*2**20)
        self.assertGreater(b['plateau_scenario_bytes'], b['exact_watchdog_pressure_line_bytes'])
        self.assertFalse(b['qualified'])
        self.assertFalse(b['launch_prepared'])

    def test_size_class_alternative_preserves_rank0_and_has_real_vram_cost(self):
        b = self.budget
        alternatives = b['boundary_alternatives']
        self.assertEqual([r['rank'] for r in alternatives], [1, 2, 3])
        self.assertEqual([r['moved_rows'] for r in alternatives], [62, 64, 62])
        self.assertEqual(sum(r['host_reserved_saving_bytes'] for r in alternatives), 6_744_440_832)
        self.assertEqual(sum(r['vram_growth_bytes'] for r in alternatives), 924_057_600)
        with self.assertRaises(ValueError):
            a.boundary_alternative(self.placement, 0)

    def test_no_fabricated_ready_or_checkpoint_progress(self):
        report = self.reports[6]
        self.assertEqual(report['first_refusal']['next_bytes'], 196_608_000)
        self.assertTrue(all(s['phase'] != 'ready' for s in report['curve']))
        self.assertEqual(report['curve'][-1]['phase'], 'cancellation_and_drain')


if __name__ == '__main__':
    unittest.main()
