"""Real integration flow with CPU tensor/device fakes; no sockets or GPU access."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent

class BackgroundRuntime(unittest.TestCase):
    def test_background_matches_request_bytes_and_qualifies(self):
        summaries = {}
        for mode in ('request', 'background'):
            process = subprocess.run([sys.executable, '-B', str(HERE / 'harness_runtime.py'),
                '--frames', '49', '--anchor', 'frame', '--decoder-graph', '0',
                '--stream-chunks', '3', '--decode-delay', '0.01', '--audio-delay', '0.01'],
                capture_output=True, text=True, timeout=900,
                env=dict(os.environ, LTX_STORAGE_SCAN_MODE=mode, OMP_NUM_THREADS='2',
                         MKL_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1'))
            self.assertEqual(process.returncode, 0, process.stderr[-3000:])
            value = json.loads(process.stdout.strip().splitlines()[-1])
            self.assertIsNone(value.get('error'), value.get('error'))
            self.assertIsNone(value.get('stream_error'), value.get('stream_error'))
            self.assertIsNone(value.get('halted'))
            self.assertTrue(value['verdict']['passed'])
            self.assertFalse(value['xpu_initialized'])
            self.assertEqual(len(value['chunks']), 12)
            self.assertTrue(all(row['server_options']['storage_scan_mode'] == mode for row in value['chunks']))
            summaries[mode] = value
        for before, after in zip(summaries['request']['chunks'], summaries['background']['chunks']):
            self.assertEqual(before['name'], after['name'])
            self.assertEqual(before['decoded_tensors'], after['decoded_tensors'])
            self.assertEqual(before['anchor_bytes'], after['anchor_bytes'])
            self.assertEqual(before['delivery_new_frames'], after['delivery_new_frames'])
