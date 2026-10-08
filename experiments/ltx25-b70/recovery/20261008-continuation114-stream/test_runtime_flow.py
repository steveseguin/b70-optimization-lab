"""CPU tests (packet114): the real integration.Runtime driven end to end by harness_runtime.py.

Each case runs the harness in its own process (fake ComfyUI/device modules, CPU tensors, files under
/dev/shm, every torch.xpu entry point raising). It covers setup, the nine qualification chunks, the
verdict (real qualification_gate over real capture files written by the decode thread through the real
capture guard), streaming with text reuse, a chain reset, both anchor kinds, both lengths, and the
three latching faults: a byte difference in the repeat chain, a decode-thread failure and a 97-frame
geometry mismatch.
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def harness(*args):
    out = subprocess.run([sys.executable, '-B', str(HERE / 'harness_runtime.py'), *args], capture_output=True,
                         text=True, timeout=900, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    lines = out.stdout.strip().splitlines()
    if not lines:
        raise AssertionError('harness produced no summary: ' + out.stderr[-3000:])
    return json.loads(lines[-1])


class Flow(unittest.TestCase):
    def common(self, d, frames, anchor, stream_chunks=4):
        self.assertIsNone(d.get('error'), d.get('error'))
        self.assertTrue(d['verdict']['passed'], d['verdict'])
        self.assertIsNone(d['halted'])
        self.assertFalse(d['xpu_initialized'])
        self.assertTrue(d['decoder_drained'] and d['preview_drained'])
        self.assertEqual(d['captures'], 9)
        self.assertEqual(d['decode_threads'], ['ltx114-decode'])
        self.assertGreater(d['registry_holds'], 0)
        chunks = d['chunks']
        self.assertEqual(len(chunks), 9 + stream_chunks)
        self.assertTrue(all(ch['decode_record'] and ch['preview_record'] for ch in chunks))
        self.assertEqual([ch['decode_sequence'] for ch in chunks], list(range(1, len(chunks) + 1)))
        size = 40960 if anchor == 'latent' else 786432
        self.assertTrue(all(ch['anchor_kind'] == anchor and ch['anchor_bytes'] == size for ch in chunks))
        for ch in chunks[:6]:          # eager and graph chains: decode drained before every gated request
            self.assertEqual((ch['decode_at_start']['drained'], ch['decode_at_start']['pending']), (True, 0))
        g = d['geometry_record']
        self.assertTrue(g['matches'] and g['first_chunk'] == 'stream114-qeager-c000000' and g['frames'] == frames)
        stream = [n for n in d['anchors_on_disk'] if '-s0' in n]
        self.assertEqual(len(stream), 2)                  # two newest stream anchors kept
        return chunks

    def test_latent_49_text_reuse_overlap_and_backpressure(self):
        d = harness('--frames', '49', '--anchor', 'latent', '--reuse', '1', '--stream-chunks', '4')
        chunks = self.common(d, 49, 'latent')
        self.assertEqual([ch['reused'] for ch in chunks], [False, False, False, False, True, False, False, True, False,
                                                           False, True, False, True])
        # The repeat chain and the stream overlap the previous decode (latent anchor only).
        self.assertTrue(any(ch['decode_at_start']['pending'] > 0 for ch in chunks[6:]))
        self.assertTrue(all(ch['slot0_pin'] == {'A': True, 'B': True} for ch in chunks
                            if ch['delivery_new_frames'] == 48))
        self.assertEqual([ch['delivery_new_frames'] for ch in chunks[9:]], [49, 48, 48, 48])
        timing = chunks[10]['timing_s']
        self.assertIsNone(timing['submit_to_decode_done'])
        self.assertIsNotNone(timing['submit_to_anchor_ready'])
        self.assertEqual(set(timing['sampler_a_split']), {'sampler_a', 'separate_to_upsampler',
                                                          'upsampler_to_condition_b', 'condition_b_to_concat',
                                                          'concat_to_sampler_b'})

    def test_frame_anchor_waits_for_its_decode_and_resets(self):
        d = harness('--frames', '49', '--anchor', 'frame', '--reset-at', '2', '--stream-chunks', '4')
        chunks = self.common(d, 49, 'frame')
        self.assertTrue(all(ch['decode_at_start']['pending'] == 0 for ch in chunks))   # decode stays on the chain
        self.assertTrue(all(ch['slot0_pin'] is None for ch in chunks))
        self.assertEqual([ch['delivery_new_frames'] for ch in chunks[9:]], [49, 48, 49, 48])
        self.assertIsNotNone(chunks[10]['timing_s']['submit_to_decode_done'])

    def test_latent_97_without_reuse(self):
        d = harness('--frames', '97', '--anchor', 'latent', '--reuse', '0', '--reset-at', '3', '--stream-chunks', '4')
        chunks = self.common(d, 97, 'latent')
        self.assertFalse(any(ch['reused'] for ch in chunks))
        self.assertEqual([ch['delivery_new_frames'] for ch in chunks[9:]], [97, 96, 96, 97])
        self.assertEqual(d['geometry_record']['decoded_shapes'], {'images': [97, 256, 256, 3], 'waveform': [1, 2, 192480]})

    def test_repeat_chain_difference_fails_the_verdict_and_latches(self):
        d = harness('--frames', '49', '--inject', 'repeat-diff', '--stream-chunks', '2')
        self.assertFalse(d['verdict']['passed'])
        self.assertEqual(d['verdict']['failures'], ["Eager/graph/repeat tensors differ at chunk 1: ['images']"])
        self.assertIn('Qualification failed', d['halted'])
        self.assertEqual(len(d['chunks']), 9)

    def test_decode_failure_latches_and_refuses_the_next_chunk(self):
        d = harness('--frames', '49', '--inject', 'decode-fail', '--stream-chunks', '5')
        self.assertTrue(d['verdict']['passed'])
        self.assertIn('Decode failed for stream114-s00000002', d['halted'])
        self.assertIn('halted', d['stream_error'])
        self.assertIn('stream-decode-failure-stream114-s00000002.json', d['run_files'])
        last = d['chunks'][-1]
        self.assertEqual(last['name'], 'stream114-s00000002')
        self.assertFalse(last['decode_record'] or last['preview_record'])

    def test_97_geometry_mismatch_is_recorded_then_latches(self):
        d = harness('--frames', '97', '--inject', 'geometry', '--stream-chunks', '1')
        self.assertIn('Tensor geometry differs: waveform [1, 2, 192960]', d['halted'])
        self.assertIn('stream-geometry-mismatch-stream114-qeager-c000000.json', d['run_files'])
        self.assertIn('stream-halt.json', d['run_files'])


if __name__ == '__main__':
    unittest.main()
