"""Full-tree typed comparison skips JSON work, never skips mutation detection."""
import copy
import marshal
import unittest
from unittest.mock import patch
import session
from test_session import Harness, SHA


class PlanGuardTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.addCleanup(self.h.close)
        self.a = session.StreamAuthority(self.h.run.parent/'plan.json', SHA, 'b'*64,
            self.h.run, self.h.state, 0, 49, 'two-way', self.h.anchor_kind,
            self.h.decoder_graph, self.h.levers, server_options={'storage_scan_mode':'background'})

    def test_initial_canonical_identity_still_verified(self):
        with patch.object(session, 'PLAN_SHA256', '0'*64):
            with self.assertRaisesRegex(RuntimeError, 'reviewed'):
                session.StreamAuthority(self.h.run.parent/'plan.json', SHA, 'b'*64,
                    self.h.run, self.h.state, 0, 49, server_options={'storage_scan_mode':'background'})

    def test_unchanged_tree_avoids_canonical_serialization(self):
        with patch.object(session, 'canonical', side_effect=AssertionError('canonical on stable plan')):
            for _ in range(35):
                self.a.healthy()

    def test_off_path_keeps_parent_canonical_check(self):
        with patch.object(session, 'canonical', wraps=session.canonical) as spy:
            self.h.a.healthy()
            spy.assert_called_once_with(self.h.a.plan)

    def test_top_level_mutation_detected(self):
        self.a.plan['schema'] = 'bad'
        with self.assertRaisesRegex(RuntimeError, 'plan/phase changed'):
            self.a.healthy()

    def test_deep_graph_mutation_detected(self):
        self.a.plan['setup'][0]['graph']['new-node'] = {'inputs':{'seed':12}}
        with self.assertRaisesRegex(RuntimeError, 'plan/phase changed'):
            self.a.healthy()

    def test_nested_deletion_detected(self):
        self.a.plan['qualification'].pop()
        with self.assertRaisesRegex(RuntimeError, 'plan/phase changed'):
            self.a.healthy()

    def test_reorder_semantically_same_tree_falls_back(self):
        self.a.plan = dict(reversed(list(self.a.plan.items())))
        with patch.object(session, 'canonical', wraps=session.canonical) as spy:
            self.a.healthy()
            spy.assert_called_once()

    def test_equivalent_clone_accepted(self):
        self.a.plan = copy.deepcopy(self.a.plan)
        self.a.healthy()

    def test_invalid_value_fails_closed(self):
        self.a.plan['schema'] = object()
        with self.assertRaises((TypeError, ValueError, RuntimeError)):
            self.a.healthy()

    def test_type_tags_distinguish_json_numeric_edge_cases(self):
        vals = [None, False, True, 0, 1, -1, 0.0, -0.0, 1.0, '', '0', [], {}, [0], [False]]
        blobs = [marshal.dumps({'x':v},2) for v in vals]
        self.assertEqual(len(set(blobs)),len(vals))

    def test_restored_value_passes_original_gate(self):
        saved = self.a.plan['schema']
        self.a.plan['schema'] = 'bad'
        with self.assertRaises(RuntimeError):
            self.a.healthy()
        self.a.plan['schema'] = saved
        self.a.healthy()

    def test_phase_check_remains_even_when_binary_equal(self):
        self.a.phase = 'bad'
        with self.assertRaisesRegex(RuntimeError, 'plan/phase changed'):
            self.a.healthy()


    def test_equal_python_bool_integer_mutation_still_refuses(self):
        self.assertEqual(self.a.plan['budget']['retries'], 0)
        self.a.plan['budget']['retries'] = False
        with self.assertRaisesRegex(RuntimeError, 'plan/phase changed'):
            self.a.healthy()

    def test_equal_python_integer_float_mutation_still_refuses(self):
        self.a.plan['budget']['retries'] = 0.0
        with self.assertRaisesRegex(RuntimeError, 'plan/phase changed'):
            self.a.healthy()

    def test_cycle_injection_fails_closed(self):
        self.a.plan['cycle'] = self.a.plan
        with self.assertRaises((ValueError, RuntimeError)):
            self.a.healthy()
