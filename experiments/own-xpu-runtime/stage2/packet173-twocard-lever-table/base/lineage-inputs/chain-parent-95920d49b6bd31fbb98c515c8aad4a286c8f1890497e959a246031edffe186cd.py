"""Lightweight positive and tamper checks using retained miniature CPU evidence."""
import copy
import json
import unittest
from unittest.mock import patch
import real_cross_placement_gate as gate


class CrossPlacement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads((gate.P/'cpu-merged-gates.json').read_text())

    def setUp(self):
        self.data = copy.deepcopy(self.fixture)
        self.rows = [r for r in self.data['rows'] if r['name'].endswith('-native-none')]

    def run_check(self):
        return gate.check(self.data, development_mini=True)

    def test_complete_matrix(self):
        result = self.run_check()
        self.assertTrue(result['passed'])
        self.assertEqual((result['cases'], result['same_capacity_pairs'], result['semantic_buffer_count']), (6, 3, 17))

    def test_elapsed_time_is_not_semantic(self):
        self.rows[0]['stats']['redo_ms'] += 100000
        self.assertTrue(self.run_check()['passed'])

    def test_incomplete_campaign(self):
        self.data['completed'] = False
        with self.assertRaises(AssertionError): self.run_check()

    def test_duplicate_matrix_entry(self):
        self.rows[0]['context'] = self.rows[-1]['context']
        self.rows[0]['draft_rank'] = self.rows[-1]['draft_rank']
        with self.assertRaises(AssertionError): self.run_check()

    def test_changed_guess(self):
        self.rows[-1]['guess_sequence'][0] += 1
        with self.assertRaisesRegex(AssertionError, 'guesses differ'): self.run_check()

    def test_changed_decision_count(self):
        self.rows[-1]['stats']['hits'] += 1
        with self.assertRaisesRegex(AssertionError, 'decision counts'): self.run_check()

    def test_changed_same_capacity_cache(self):
        self.rows[-1]['signature']['draft_state']['blk.0.qsa.keys.bin'] = '0'*64
        with self.assertRaisesRegex(AssertionError, 'same-capacity'): self.run_check()

    def altered_retained(self, change):
        original = gate.retained_draft
        def altered(row):
            state, trace, hashes = original(row)
            if row['context'] == 32768 and row['draft_rank'] == 1:
                change(state, trace)
            return state, trace, hashes
        return patch.object(gate, 'retained_draft', side_effect=altered)

    def test_wrong_next_cache_position(self):
        with self.altered_retained(lambda state, trace: state.update(position=state['position']+1)):
            with self.assertRaises(AssertionError): self.run_check()

    def test_missing_cache_step(self):
        with self.altered_retained(lambda state, trace: trace.pop()):
            with self.assertRaisesRegex(AssertionError, 'progression'): self.run_check()

    def test_changed_fixed_semantic_buffer(self):
        def change(state, trace): state['mutable_sha256']['card0:draft:merge.hidden'] = '0'*64
        with self.altered_retained(change):
            with self.assertRaisesRegex(AssertionError, 'semantic state'): self.run_check()

    def test_changed_archive_binding(self):
        self.rows[-1]['scratch_archive']['sha256'] = '0'*64
        with self.assertRaisesRegex(AssertionError, 'archive hash'): self.run_check()


if __name__ == '__main__':
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(CrossPlacement))
    receipt = dict(passed=result.wasSuccessful(), device_executed=False, checks=result.testsRun,
        errors=len(result.errors), failures=len(result.failures),
        input_receipt_sha256=gate.sha(gate.P/'cpu-merged-gates.json'),
        source_sha256={name: gate.sha(gate.P/name) for name in
            ('real_cross_placement_gate.py', 'test_real_cross_placement_gate.py', 'mtp.hpp', 'native_controller.hpp')})
    (gate.P/'real-cross-placement-tests.json').write_text(json.dumps(receipt, indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
