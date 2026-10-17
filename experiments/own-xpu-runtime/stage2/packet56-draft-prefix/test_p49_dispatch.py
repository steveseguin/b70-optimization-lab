"""Synthetic admission metadata only; no timings here are lab measurements."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import p49_dispatch as d


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.pinned = json.loads((d.P/'dispatch-speed6.json').read_text())
        self.registry = json.loads((d.P/'k2-class-registry.json').read_text())['classes']
        self.summary = dict(passed=True, failures=[], classes={}, final_dispatch=self.pinned)
        for name, entry in self.registry.items():
            part = dict(variants={arm: dict(repetitions=200, execution_sum=dict(count=200)) for arm in ('packet18', 'specialised')},
                        bytes_equal=True, candidate_available=True, candidate_failures=[], rotation_errors=[])
            candidates = entry.get('candidates', [entry.get('candidate_implementation', 'specialised')])
            self.summary['classes'][name] = dict(incumbent=entry.get('incumbent', entry.get('baseline_implementation', 'packet18')),
                                                  comparisons={candidate: copy.deepcopy(part) for candidate in candidates})

    def test_all_pinned_choices_covered(self):
        rows = d.verify_coverage(self.summary, self.pinned, self.registry)
        self.assertEqual(len(rows), 65)
        self.assertEqual(sum(row['measured_class'] is None for row in rows), 2)

    def test_changed_output_candidate_refuses(self):
        self.summary['classes']['gemv:expsdown']['comparisons']['p33.down.bank']['bytes_equal'] = False
        with self.assertRaisesRegex(ValueError, 'fresh K2 exactness'):
            d.verify_coverage(self.summary, self.pinned, self.registry)

    def test_missing_pinned_candidate_refuses(self):
        del self.summary['classes']['gemv:expsdown']['comparisons']['p33.down.bank']
        with self.assertRaisesRegex(ValueError, 'not measured'):
            d.verify_coverage(self.summary, self.pinned, self.registry)

    def test_partial_or_failed_campaign_refuses(self):
        self.summary['passed'] = False
        with self.assertRaises(ValueError):
            d.verify_coverage(self.summary, self.pinned, self.registry)
        self.summary['passed'] = True
        self.summary['classes']['gemv:expsdown']['comparisons']['p33.down.bank']['variants']['specialised']['repetitions'] = 199
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            d.verify_coverage(self.summary, self.pinned, self.registry)

    def test_raw_recommendation_is_retained(self):
        with tempfile.TemporaryDirectory() as directory, patch('p49d_k2.measured_coverage',return_value={'passed':True}) as coverage:
            root = Path(directory)
            raw_summary = json.dumps(self.summary).encode()
            recommendation = json.dumps(dict(self.pinned, gemv=dict(self.pinned['gemv'], expsdown='r5'))).encode()
            (root/'summary.json').write_bytes(raw_summary)
            (root/'dispatch-measured.json').write_bytes(recommendation)
            updated, policy = d.pin_production_dispatch(root, self.summary,round3_root=root/'round3')
            self.assertEqual((root/'summary-k2-measured.json').read_bytes(), raw_summary)
            self.assertEqual((root/'dispatch-k2-recommendation.json').read_bytes(), recommendation)
            self.assertEqual((root/'dispatch-measured.json').read_bytes(), (d.P/'dispatch-speed6.json').read_bytes())
            self.assertIn('production_dispatch_policy', updated)
            with self.assertRaises(ValueError):
                d.pin_production_dispatch(root, self.summary,round3_root=root/'round3')


if __name__ == '__main__':
    unittest.main()
