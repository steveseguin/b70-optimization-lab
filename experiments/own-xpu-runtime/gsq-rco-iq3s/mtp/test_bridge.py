import copy
import unittest
from bridge import C, M, SyntheticTransport, exercise, reference


class BridgeTests(unittest.TestCase):
    prompt = [1,2,3,4,2]

    def test_accept_reject_mixed_exact_target_state(self):
        for mode in ('hit','miss','mixed'):
            with self.subTest(mode=mode):
                r = exercise(self.prompt, 40, mode)
                self.assertGreater(r['stats']['guesses'], 0)
                self.assertEqual(r['rollbacks'], r['stats']['misses'])
                self.assertGreater(r['stats']['hits' if mode=='hit' else 'misses'], 0)

    def test_confirmed_index_and_cache_sequence(self):
        rows = [exercise(self.prompt, 40, m) for m in ('hit','miss','mixed','missing')]
        for r in rows[1:]:
            self.assertEqual(r['provider_inputs'], rows[0]['provider_inputs'])
            self.assertEqual(r['draft_cache_inputs'], rows[0]['draft_cache_inputs'])
        for i, r in enumerate(rows[0]['provider_inputs']):
            self.assertEqual((r['confirmed_position'],r['hidden_position'],r['draft_position']),
                             (i+1,i,i))

    def test_invalid_publications_never_speculate(self):
        for mode in ('missing','garbage','stale-position','stale-sequence'):
            with self.subTest(mode=mode):
                r = exercise(self.prompt, 12, mode)
                self.assertEqual(r['stats']['guesses'], 0)
                self.assertEqual(r['rollbacks'], 0)

    def test_pre_and_late_provider_failure_disable_once(self):
        for mode, appended in [('pre-error',0),('late-error',1)]:
            r = exercise(self.prompt, 12, mode)
            self.assertTrue(r['disabled'])
            self.assertEqual(len(r['draft_cache_inputs']),appended)
            self.assertEqual(r['stats']['guesses'],0)

    def test_transport_error_not_silently_retried(self):
        _, r = reference(self.prompt, 12)
        b = SyntheticTransport(self.prompt+r['tokens'], 'transport-error')
        with self.assertRaisesRegex(RuntimeError,'synthetic transport error'):
            C.Controller(b,C.Draft('mtp')).run(self.prompt,12)
        self.assertEqual(len(b.provider_inputs),1)

    def test_terminal_discards_pending_speculation(self):
        _, ref = reference(self.prompt,8)
        r = exercise(self.prompt,8,'miss',(ref['tokens'][0],))
        self.assertEqual(r['tokens'],ref['tokens'][:1])

    def test_single_output_and_capacity_boundary_sequences(self):
        for n in (1,2,31,32,33):
            exercise(self.prompt,n,'mixed')

    def test_inherited_script_state_regressions(self):
        # Reuse the existing test method itself; no rewritten target transitions.
        suite=M.StateMachine('test_long_random')
        suite.test_long_random()


if __name__ == '__main__':
    unittest.main()
