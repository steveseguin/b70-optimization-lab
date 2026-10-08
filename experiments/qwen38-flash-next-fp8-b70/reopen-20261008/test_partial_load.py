"""Regression checks for the saved attempt-3 receipt interpretation."""
from pathlib import Path
import unittest
from analyze_partial_load import analyze

HERE = Path(__file__).resolve().parent
RUN = HERE/'runs/screen1b-mmap-calibrate-load-20261008-attempt3'


@unittest.skipUnless((RUN/'host-memory-samples.jsonl').exists(), 'saved attempt-3 samples required')
class PartialLoadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = analyze(RUN)

    def test_first_cause_is_rank1_memory_refusal(self):
        r = self.report
        self.assertEqual(r['first_refusal']['pid'], 477)
        self.assertEqual(r['first_cancel']['pid'], 477)
        self.assertEqual(r['refusal_observation']['pressure_bytes'], 80005660672)
        self.assertEqual(r['first_refusal']['next_bytes'], 2048)
        self.assertEqual(r['pre_failure_sample_peak']['pressure_bytes'], 78731689984)
        self.assertEqual(r['phase_summary']['failure_and_drain']['peak']['pressure_bytes'], 79478317056)

    def test_partial_allocations_do_not_become_full_load(self):
        r = self.report
        self.assertEqual(r['allocation_snapshot_files'], [])
        self.assertNotIn('PLE_index_complete', r['reached_events'])
        self.assertEqual(r['staging'], {'live': {}, 'peak_bytes':268431360})
        self.assertEqual(sum(p['completed_parameters'] for p in r['rank_progress'].values()), 164)
        self.assertEqual(r['prediction_comparison']['completed_expert_host_bytes'], 3740467200)

    def test_curve_uses_observed_bytes_and_separates_drain(self):
        r = self.report
        self.assertEqual(len(r['curve']), 364)
        for row in r['curve']:
            self.assertEqual(row['pressure_bytes']+row['mem_available_bytes'], 124179132416)
        self.assertEqual(r['curve'][-1]['phase'], 'failure_and_drain')
        self.assertEqual(r['prediction_comparison']['distance_to_illustrative_peak_bytes'], 7759341592)
