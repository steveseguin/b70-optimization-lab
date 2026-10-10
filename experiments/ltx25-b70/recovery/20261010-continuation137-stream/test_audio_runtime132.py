"""Real integration on explicit CPU device/reference fakes, never XPU proof."""
import os
import unittest
from unittest.mock import patch

from test_runtime_flow import harness


class AudioRuntime132(unittest.TestCase):
    def run_audio(self, graph, *extra):
        with patch.dict(os.environ, {'LTX_CONE_GRAPH_MEMORY': 'replica-release' if graph else 'off',
                                     'LTX_DISPLAY_REPLICA_TRANSIENT_GIB': '5.640625',
                                     'LTX_CONE_CAPTURE_RESERVE': 'parent'}):
            return harness('--frames', '145', '--anchor', 'frame', '--decoder-graph', str(graph),
                '--display-device', 'xpu:2', '--display-schedule', 'eager-display',
                '--audio-residency', 'xpu2', '--stream-chunks', '1',
                '--decode-delay', '0.001', '--audio-delay', '0.001', *extra)

    def check(self, data):
        self.assertIsNone(data.get('error'), data.get('error'))
        self.assertIsNone(data.get('halted'), data.get('halted'))
        self.assertTrue(data['verdict']['passed'])
        self.assertFalse(data['xpu_initialized'])
        self.assertEqual(data['captures'], 9)
        self.assertEqual(len(data['chunks']), 10)
        for index, row in enumerate(data['chunks']):
            evidence = row['audio_residency_evidence']
            self.assertEqual(row['audio_device'], 'xpu:2')
            self.assertEqual(row['server_options']['aux_residency'], 'legacy')
            self.assertEqual(evidence['reference_released']['resident_bytes_on_xpu3'], 0)
            self.assertEqual(evidence['reference_released']['calls'], min(index+1, 3))
            if index < 3:
                self.assertTrue(evidence['cross_card']['equal'])
                self.assertEqual(evidence['cross_card']['waveform_sha256'],
                                 row['decoded_tensors']['waveform']['sha256'])
            else:
                self.assertIsNone(evidence['cross_card'])
                self.assertIsNone(evidence['reference'])
        hashes = [row['decoded_tensors']['waveform']['sha256'] for row in data['chunks'][:9]]
        self.assertEqual(hashes[:3], hashes[3:6]); self.assertEqual(hashes[:3], hashes[6:9])

    def test_three_native_controls_nine_qualified_outputs_graph_on(self): self.check(self.run_audio(1))
    def test_isolated_audio_timing_diagnostic_graph_off(self): self.check(self.run_audio(0))
    def test_cross_card_audio_difference_halts(self):
        data = self.run_audio(1, '--inject', 'audio-cross-diff')
        self.assertTrue(data.get('error') or data.get('halted'))
        self.assertIn('cross-card waveform byte gate failed', str(data))
        self.assertFalse(data.get('verdict', {}).get('passed', False))


if __name__ == '__main__': unittest.main()
