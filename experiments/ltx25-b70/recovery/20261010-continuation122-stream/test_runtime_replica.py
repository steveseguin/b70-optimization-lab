"""Run the real integration/qualification on CPU fakes, enabled and failing."""
import unittest
from test_runtime_flow import harness


def run(*args):
    return harness('--frames', '121', '--anchor', 'frame', '--display-schedule', 'eager-display',
                   '--display-device', 'xpu:2', '--stream-chunks', '2', '--audio-delay', '0.01',
                   '--decode-delay', '0.01', *args)


class ReplicaFlow(unittest.TestCase):
    def test_three_chains_and_live_cross_card_anchor(self):
        d = run()
        self.assertIsNone(d.get('error'), d.get('error'))
        self.assertTrue(d['verdict']['passed'], d['verdict'])
        self.assertEqual(len(d['verdict_file']['display_replica_rows']), 9)
        self.assertFalse(d['xpu_initialized'])
        self.assertEqual(d['decode_threads'], ['ltx120-decode'])
        self.assertEqual([r['display_device'] for r in d['chunks']], ['xpu:3']*3+['xpu:2']*8)
        self.assertTrue(all(r['display_replica']['equal'] is True for r in d['chunks'][:9]))
        self.assertTrue(all(r['anchor_decode']['equal'] is True for r in d['chunks'][3:]))

    def failure(self, inject):
        d = run('--inject', inject)
        self.assertTrue(d.get('error') or d.get('halted'), d)
        self.assertIn('display-replica-120-refused.json', d['lever_latches'], d)

    def test_eager_control_non_anchor_difference_latches(self):
        self.failure('replica-diff')

    def test_repeat_chain_non_anchor_difference_latches(self):
        self.failure('replica-repeat-diff')

    def test_floor_refuses_before_decode(self):
        self.failure('replica-floor')

    def test_live_anchor_difference_latches(self):
        self.failure('replica-live-diff')


if __name__ == '__main__':
    unittest.main()
