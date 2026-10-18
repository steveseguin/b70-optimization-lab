import math
import unittest
from analyze import metrics, validate_rows, costs


def row(prompt, index, top1, top2, actual, margin):
    return dict(prompt_id=prompt, source_index=int(prompt), generated_index=index,
                top1=top1, top2=top2, target_token=actual, margin=margin,
                prefix_probability=.5)


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.scenario = dict(extra_half_ms=4, rescued_miss_ms=15,
                             per_cycle_policy_ms=.02, rescued_state_selection_ms=0)
        self.rows = [row('1', 0, 1, 2, 2, .25), row('1', 1, 1, 2, 1, 2),
                     row('2', 0, 1, 2, 3, .25), row('2', 1, 1, 2, 2, .25)]

    def test_never_has_no_collection_cost(self):
        m = metrics(self.rows, dict(feature='never', tau=None), self.scenario)
        self.assertEqual(m['gain_percent'], 0)
        self.assertEqual(m['finite_gain_percent'], 0)
        self.assertEqual(m['baseline_acceptance'], .25)

    def test_rescue_is_membership_not_two_emitted_tokens(self):
        m = metrics(self.rows, dict(feature='margin', tau=1), self.scenario)
        self.assertEqual((m['flags'], m['rescued_misses'], m['flagged_misses']), (3, 2, 3))
        self.assertEqual(m['acceptance_with_two_candidates'], .75)
        self.assertAlmostEqual(m['projected_ms'], 17.4 + (3*4-2*15)/4 + .02)
        self.assertAlmostEqual(m['projected_tok_s'], 1000/m['projected_ms'])

    def test_delayed_cost_and_prompt_boundaries(self):
        m = metrics(self.rows, dict(feature='margin', tau=1), self.scenario)
        self.assertEqual(m['finite_intervals'], 2)
        # First prompt: rescue at 0, no flag at 1 = -15.
        # Second prompt: no rescue at 0, flag at 1 = +4.
        self.assertAlmostEqual(m['finite_delta_ms'], (-15+4)/2+.02)

    def test_threshold_is_strict(self):
        m = metrics(self.rows, dict(feature='margin', tau=.25), self.scenario)
        self.assertEqual(m['flags'], 0)
        self.assertGreater(m['delta_ms'], 0)  # enabled collection still costs

    def test_five_sources_no_duplicates_or_gaps(self):
        rows = [row(str(i), 0, 1, 2, 2, 1) for i in range(1, 6)]
        validate_rows(rows)
        with self.assertRaises(AssertionError):
            validate_rows(rows + [rows[0]])
        rows[0]['generated_index'] = 1
        with self.assertRaises(AssertionError):
            validate_rows(rows)

    def test_cost_classes_exclude_idle_and_head(self):
        budget, scenarios = costs()
        self.assertFalse(budget['overhead_gate_passed'])
        self.assertAlmostEqual(budget['expert_gate_down_ms'], 2.39176)
        self.assertAlmostEqual(budget['target_half_compute_ms'], 11.36252)
        self.assertAlmostEqual(budget['redo_compute_ms'] + budget['restore_compute_ms'], 11.56410)
        self.assertAlmostEqual(scenarios[0]['extra_half_ms'], 4.1539459375)


if __name__ == '__main__':
    unittest.main()
