#!/usr/bin/env python3
"""Tests of the analysis only; not a runtime, controller or device quality gate."""
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('p126', HERE / 'simulate.py')
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


class DependencyTests(unittest.TestCase):
    def row(self, hit=True):
        return dict(A=12.8, B=13.3, D=1.6, D_next=1.6, R=0. if hit else .55,
                    C=0. if hit else 11.85, hit=hit, spec_start_offset_ms=0.,
                    unresolved_control_gaps_ms=.02)

    def test_current_hit_and_miss(self):
        self.assertAlmostEqual(model.simulate(self.row())[0], 14.92)
        self.assertAlmostEqual(model.simulate(self.row(False))[0], 25.72)

    def test_no_wait_reordering_does_not_erase_miss_work(self):
        for order in ('draft_before_publish', 'publish_before_draft', 'draft_before_merge'):
            self.assertAlmostEqual(model.simulate(self.row(), 0., order)[0], 14.92)
            self.assertAlmostEqual(model.simulate(self.row(False), 0., order)[0], 27.32)

    def test_unobserved_wait_changes_the_decision(self):
        for hit in (True, False):
            r = self.row(hit)
            self.assertAlmostEqual(model.simulate(r, 0.)[0], model.simulate(r, .6)[0])
        rows = [self.row()] * 4 + [self.row(False)]
        for r in rows:
            r['elapsed_ms'] = model.simulate(r)[0]
        low = model.summarize(rows, model.evaluate(rows, 0., 'publish_before_draft'))
        high = model.summarize(rows, model.evaluate(rows, .6, 'publish_before_draft'))
        self.assertLess(low['pooled_interval_rate_change_percent'], 0.)
        self.assertGreater(high['pooled_interval_rate_change_percent'], .5)

    def test_actual_next_draft_time_is_not_replaced_with_current(self):
        r = self.row()
        r['D_next'] += .15
        self.assertAlmostEqual(model.simulate(r, 0., 'publish_before_draft')[0], 15.07)

    def test_dependency_and_single_ccs_order_for_both_outcomes(self):
        for hit in (True, False):
            for wait in (0., .2, .6, 1.):
                for order in ('draft_before_publish', 'publish_before_draft', 'draft_before_merge'):
                    _, nodes = model.simulate(self.row(hit), wait, order)
                    for node in nodes.values():
                        for dep in node['dependencies']:
                            self.assertGreaterEqual(node['start'], nodes[dep]['end'])
                    d, h = nodes['speculative_D_next'], nodes['local_head']
                    self.assertTrue(d['end'] <= h['start'] or h['end'] <= d['start'])
                    self.assertGreaterEqual(nodes['verified']['start'], nodes['suffix_service']['end'])
                    self.assertGreaterEqual(nodes['verified']['start'], d['end'])
                    self.assertEqual(nodes['confirmed_D']['duration'], 0. if hit else 1.6)

    def test_frozen_method_bytes(self):
        for copy, source in [('p85_model.py', 'packet85-critical-path/model.py'),
                             ('p108_extract.py', 'packet108-attribution/extract.py')]:
            self.assertEqual((HERE/'method'/copy).read_bytes(), (HERE.parent/source).read_bytes())

    def test_caps_are_not_applied_on_import(self):
        source = (HERE/'simulate.py').read_text()
        import ast
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, (ast.Expr, ast.Assign)):
                self.assertNotIn('setrlimit', ast.unparse(node))

    def test_saved_decision_does_not_promote_an_assumed_wait(self):
        result = json.loads((HERE/'simulation.json').read_text())
        self.assertFalse(result['candidate_admitted'])
        self.assertFalse(result['device_executed'])
        self.assertFalse(result['submission_eligible'])
        self.assertEqual(result['script_sha256'], hashlib.sha256((HERE/'simulate.py').read_bytes()).hexdigest())
        for run in result['runs']:
            self.assertLess(run['current_DAG_max_error_ms'], 1e-7)
            self.assertTrue(all(s['is_measurement'] is False for s in run['scenarios']))
            self.assertEqual(run['conditional']['hit']['n'] + run['conditional']['miss']['n'], 1188)


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3, 8 * 1024**3))
    unittest.main(verbosity=2)
