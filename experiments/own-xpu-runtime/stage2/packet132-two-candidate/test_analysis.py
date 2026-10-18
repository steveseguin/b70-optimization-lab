import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from analyze import P, metrics, validate_rows, validate_capture, costs


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

    def test_incomplete_capture_cannot_be_scored(self):
        rule = json.loads((P/'inputs/preregistration.json').read_text())
        rows, sources = [], []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for i, source in enumerate(rule['sources']):
                r = row(str(i+1), 0, 1, 2, 2, 1)
                r.update(draft_prefix_rows=80128, position=14, next_input_token=7, source_path=source['path'])
                rows.append(r)
                sources.append(dict(source, source_commit=rule['source_commit'], tokens=[7]*16,
                                    generated_token_cap=24, full_token_count=100, excerpt_start=50))
                directory = root/f'doc-{i}'
                (directory/'target').mkdir(parents=True)
                target = dict(arithmetic='iq3-p49-split32-v1', device_executed=False, status='eos',
                              error='', tokens=[2])
                (directory/'target/result.json').write_text(json.dumps(target))
                (directory/'draft-receipt.json').write_text(json.dumps(dict(count=1, device_executed=False)))
            raw = ''.join(json.dumps(r)+'\n' for r in rows).encode()
            (root/'rows.jsonl').write_bytes(raw)
            (root/'rows.json').write_text(json.dumps(rows))
            (root/'inputs.json').write_text(json.dumps(dict(sources=sources, preregistration_sha256=hashlib.sha256((P/'inputs/preregistration.json').read_bytes()).hexdigest())))
            complete = dict(device_executed=False, rows=5, rows_sha256=hashlib.sha256(raw).hexdigest())
            (root/'completion.json').write_text(json.dumps(complete))
            self.assertTrue(validate_capture(root/'rows.json', rows)['complete'])
            target['status'] = 'token-cap'
            (root/'doc-0/target/result.json').write_text(json.dumps(target))
            with self.assertRaises(AssertionError):
                validate_capture(root/'rows.json', rows)
            (root/'completion.json').unlink()
            with self.assertRaises(FileNotFoundError):
                validate_capture(root/'rows.json', rows)


if __name__ == '__main__':
    unittest.main()
