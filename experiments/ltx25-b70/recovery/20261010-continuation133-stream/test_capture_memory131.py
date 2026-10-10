"""CPU native-decoder tests of the real capture_check hook; no XPU backend.

Memory counters and capture/replay are the existing CPU fakes. These tests
prove hook order, refusal propagation and unchanged arithmetic proofs, not
native145 memory fit. Runtime owns the halt after any propagated refusal.
"""
import unittest
from unittest.mock import Mock

import test_pool_cap as fixture
import stream_decoder_graph as graph

torch = fixture.torch
METHOD = 'forward_pre_diffusion'


class CaptureMemoryHook(unittest.TestCase):
    def controller(self):
        value = fixture.Capped(None)
        self.addCleanup(value.close)
        self.assertEqual(next(value.vae.parameters()).device.type, 'cpu')
        return value

    def forward(self, value, seed=23):
        with torch.inference_mode(), value.ctl.graph_decode():
            return value.vae.decoder.forward_pre_diffusion(fixture.latent(seed))

    def test_callback_brackets_capture_and_receives_completed_proofs(self):
        value = self.controller()
        events = []
        def check(method, record=None):
            events.append((method, record))
            self.assertEqual(method, METHOD)
            if record is None:
                self.assertEqual(value.backend.captures, [])
                self.assertEqual(value.ctl.captures, [])
            else:
                self.assertIs(record, value.ctl.captures[-1])
                self.assertEqual(len(value.backend.captures), 1)
                self.assertTrue(any(row['moved'] for row in record['sensitivity']))
                self.assertEqual(record['memory_after']['reserved_bytes'] -
                                 record['memory_before']['reserved_bytes'], value.backend.growth)
        value.ctl.capture_check = check
        got = self.forward(value)
        self.assertEqual(got.device.type, 'cpu')
        self.assertEqual(len(events), 2)
        self.assertIsNone(events[0][1])
        self.assertEqual(events[1][1]['method'], METHOD)
        self.assertEqual(len(value.ctl.captures), 1)

    def test_method_refusal_precedes_reference_warmup_and_capture(self):
        value = self.controller()
        original = value.ctl.graphed[METHOD].original
        value.ctl.graphed[METHOD].original = Mock(wraps=original)
        value.backend.warmup = Mock(wraps=value.backend.warmup)
        value.backend.memory = Mock(wraps=value.backend.memory)
        def only_other(method, record=None):
            graph.require(method == 'forward_diff_step', 'method mismatch')
        value.ctl.capture_check = Mock(side_effect=only_other)
        with self.assertRaisesRegex(graph.DecoderGraphRefusal, 'method mismatch'):
            self.forward(value)
        value.ctl.capture_check.assert_called_once_with(METHOD)
        value.ctl.graphed[METHOD].original.assert_not_called()
        value.backend.warmup.assert_not_called()
        value.backend.memory.assert_not_called()
        self.assertEqual(value.backend.captures, [])
        self.assertEqual(value.ctl.captures, [])
        self.assertEqual(value.ctl.signatures()[METHOD], 0)
        self.assertEqual(value.ctl.capped, [])

    def test_postcapture_refusal_propagates_without_retry_or_fallback(self):
        value = self.controller()
        events = []
        def refuse_after(method, record=None):
            events.append((method, record))
            if record is not None:
                raise graph.DecoderGraphRefusal('capture exceeded reserve')
        value.ctl.capture_check = refuse_after
        with self.assertRaisesRegex(graph.DecoderGraphRefusal, 'capture exceeded reserve'):
            self.forward(value)
        self.assertEqual(len(events), 2)
        self.assertEqual(len(value.backend.captures), 1)
        self.assertEqual(len(value.ctl.captures), 1)
        self.assertEqual(value.ctl.pool_growth, 0)  # failure never publishes successful admission
        self.assertEqual(value.ctl.replays[METHOD], 0)
        self.assertEqual(value.ctl.capped, [])
        self.assertEqual(value.ctl.capped_calls[METHOD], 0)
        self.assertFalse(value.ctl.capturing)
        self.assertFalse(value.ctl.active())
        # The runtime receives this exception and latches; tests do not retry it.

    def test_hook_is_not_rerun_for_existing_signature_replay(self):
        value = self.controller()
        value.ctl.capture_check = Mock()
        first = self.forward(value)
        second = self.forward(value)
        self.assertEqual(fixture.bits(first), fixture.bits(second))
        self.assertEqual(value.ctl.capture_check.call_count, 2)
        self.assertEqual(len(value.backend.captures), 1)
        self.assertEqual(value.ctl.replays[METHOD], 1)

    def test_off_keeps_eager_exact_capture_and_input_sensitive_replay(self):
        value = self.controller()
        self.assertFalse(hasattr(value.ctl, 'capture_check'))
        with torch.inference_mode():
            expected = [value.vae.decoder.forward_pre_diffusion(fixture.latent(seed))
                        for seed in (23, 24)]
        actual = [self.forward(value, seed) for seed in (23, 24)]
        self.assertEqual([fixture.bits(x) for x in actual], [fixture.bits(x) for x in expected])
        self.assertNotEqual(fixture.bits(actual[0]), fixture.bits(actual[1]))
        self.assertTrue(any(row['moved'] for row in value.ctl.captures[0]['sensitivity']))
        self.assertEqual(len(value.backend.captures), 1)

    def test_hook_cannot_bypass_existing_replay_exactness_proofs(self):
        value = self.controller()
        value.backend.tamper = True
        value.ctl.capture_check = Mock()
        with self.assertRaises(graph.DecoderGraphRefusal):
            self.forward(value)
        value.ctl.capture_check.assert_called_once_with(METHOD)
        self.assertEqual(len(value.backend.captures), 1)
        self.assertEqual(value.ctl.captures, [])
        self.assertEqual(value.ctl.capped, [])


if __name__ == '__main__':
    unittest.main()
