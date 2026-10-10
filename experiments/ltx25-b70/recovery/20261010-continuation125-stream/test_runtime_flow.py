"""CPU tests (packet117): the real integration.Runtime driven end to end by harness_runtime.py.

Packet117 cases: every lever on (the default) at 49, 97 and 121 frames; each lever alone and all off (116b
behaviour); the cone's per-chunk byte check (a cone anchor that differs from the display decode latches at
the graph chain's chunk 0, or in the repeat chain, and writes the anchor-decode latch); the graph chain's
dual check of the precomputed conditioning (a difference latches and writes the precompute latch); the
xpu:3-only floor of the precomputed encode; the decode thread's order (anchor, stage-A encode after the
commit, the go wait for the successor's sampler A, stage-B encode, display decode, audio); the encoder lock
(no two encodes ever overlap); and the xpu:3-only synchronisation of the encode guard.

Packet116 cases: the frame anchor's 116a hand-off (the receipt commits before the audio decode, hashes and
record; the next chunk starts beside them; gated chunks wait for their whole decode), the decoder-graph
modes (eager chain uncached, graph chain dual decode, repeat chain and stream replay), its two faults
(a dual-decode mismatch latches at the graph chain's first chunk; a repeat-chain-only difference fails
the verdict) with the decoder-graph latch file, LTX_DECODER_GRAPH=0, the sealed cross-packet reference
(the fake outputs must fail it), and an audio failure after the hand-off.


Each case runs the harness in its own process (fake ComfyUI/device modules, CPU tensors, files under
/dev/shm, every torch.xpu entry point raising). It covers setup, the nine qualification chunks, the
verdict (real qualification_gate over real capture files written by the decode thread through the real
capture guard), streaming with text reuse, a chain reset, all four anchor kinds (the guide through the
sealed native LTXVAddLatentGuide / LTXVCropGuides compiled on CPU), both lengths, and the latching
faults: a byte difference in the repeat chain, a decode-thread failure, a 97-frame geometry mismatch and
(mixed) a frame anchor whose bytes changed after its decode record.
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
        self.assertEqual(d['decode_threads'], ['ltx120-decode'])
        self.assertIsNone(d['latch'])
        self.assertGreater(d['registry_holds'], 0)
        chunks = d['chunks']
        self.assertEqual(len(chunks), 9 + stream_chunks)
        self.assertTrue(all(ch['decode_record'] and ch['preview_record'] for ch in chunks))
        self.assertEqual([ch['decode_sequence'] for ch in chunks], list(range(1, len(chunks) + 1)))
        size = {'latent': 40960, 'mixed': 40960, 'guide': 81920, 'frame': 786432}[anchor]
        self.assertTrue(all(ch['anchor_kind'] == anchor and ch['anchor_bytes'] == size for ch in chunks))
        dg = d['decoder_graph']
        self.assertEqual([ch['decoder']['mode'] for ch in chunks], ['eager'] * 3 + ['graph' if dg else 'eager'] *
                         (len(chunks) - 3))
        self.assertEqual([ch['decoder']['new_captures'] for ch in chunks], [0, 0, 0, 2 if dg else 0] +
                         [0] * (len(chunks) - 4))
        self.assertEqual([ch['decoder']['reference'] is not None for ch in chunks],
                         [False] * 3 + [bool(dg)] * 3 + [False] * (len(chunks) - 6))
        self.assertTrue(all(ch['decoder_graph'] == dg for ch in chunks))
        # Gated chunks wait for their whole decode; the others commit before it (116a / off-chain).
        for ch in chunks[:6]:
            self.assertEqual(ch['decode_state'], 'done')
            self.assertGreaterEqual(ch['timing_ns']['receipt_staged'], ch['decode_timing_ns']['record_staged'])
        for ch in chunks[6:]:
            self.assertEqual(ch['decode_state'], 'video_done' if anchor == 'frame' else 'queued')
        for ch in chunks:
            t, dt, pt = ch['timing_ns'], ch['decode_timing_ns'], ch['preview_timing_ns']
            order = [dt['decode_start'], dt['video_done'], dt['audio_done'], dt['hashed'], dt['record_staged'],
                     pt['record_written'], pt['preview_queued'], pt['preview_written']]
            self.assertEqual(order, sorted(order), ch['name'])
            if anchor == 'frame':
                self.assertTrue(dt['video_done'] == t['video_done'] <= t['anchor_ready'] == dt['anchor_ready'] <=
                                dt['audio_done'], ch['name'])
        self.assertTrue(all(len(ch['sharpness_frames']) == (7 if frames == 49 else 8) for ch in chunks))
        self.assertEqual(d['concurrent_encodes'], 0)                 # the encoder lock: never two encodes at once
        for ch in chunks[:6]:          # eager and graph chains: decode drained before every gated request
            self.assertEqual((ch['decode_at_start']['drained'], ch['decode_at_start']['pending']), (True, 0))
        g = d['geometry_record']
        self.assertTrue(g['matches'] and g['first_chunk'] == 'stream125-qeager-c000000' and g['frames'] == frames)
        self.assertEqual(d['verdict_file']['decoder_graph_failures'], [])
        self.assertEqual(d['decoder_graph_state']['frozen'], bool(dg))
        stream = [n for n in d['anchors_on_disk'] if '-s0' in n]
        # The two newest stream anchors are kept (mixed: the latent file and the decode thread's frame file).
        self.assertEqual(len(stream), 4 if anchor == 'mixed' else 2)
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

    def test_frame_anchor_116a_hands_off_after_the_video_decode_and_resets(self):
        d = harness('--frames', '49', '--anchor', 'frame', '--reset-at', '2', '--stream-chunks', '4',
                    '--anchor-decode', 'full', '--bencode-overlap', '0', '--prep-ahead', '0')
        chunks = self.common(d, 49, 'frame')
        self.assertTrue(all(ch['slot0_pin'] is None for ch in chunks))
        self.assertEqual([ch['delivery_new_frames'] for ch in chunks[9:]], [49, 48, 49, 48])
        stream = chunks[6:]
        # The receipt commits before the audio decode, the hashes and the record (the 0.25 s fake audio decode).
        for ch in stream:
            self.assertLess(ch['timing_ns']['receipt_staged'], ch['decode_timing_ns']['audio_done'])
            self.assertIsNone(ch['timing_s']['submit_to_decode_done'])
            self.assertIsNotNone(ch['timing_s']['video_done_to_anchor_ready'])
        # The next chunk starts while the previous chunk's audio/hash/record still run on the decode thread.
        overlaps = [nxt['timing_ns']['execution_start'] < cur['decode_timing_ns']['audio_done']
                    for cur, nxt in zip(stream, stream[1:]) if nxt['name'] != 'stream125-s00000000']
        self.assertTrue(all(overlaps) and overlaps, overlaps)
        self.assertTrue(any(ch['decode_at_start']['pending'] > 0 for ch in stream))
        self.assertEqual(d['encode_threads'], ['MainThread'])

    def test_frame_97_without_decoder_graph(self):
        d = harness('--frames', '97', '--anchor', 'frame', '--decoder-graph', '0', '--reuse', '0',
                    '--stream-chunks', '3')
        self.common(d, 97, 'frame', 3)
        self.assertEqual(d['decoder_graph_state']['decodes'], {'graph': 0, 'eager': 0})   # never installed
        self.assertFalse(d['decoder_graph_state']['frozen'])

    def test_decoder_graph_dual_decode_mismatch_latches_and_writes_the_latch(self):
        d = harness('--frames', '49', '--anchor', 'frame', '--inject', 'dg-diff', '--stream-chunks', '1')
        self.assertIn('Decode failed for stream125-qgraph-c000000', d['halted'])
        self.assertIn('graph decode differs from the uncached eager decode', d['halted'])
        self.assertIn('stream-decode-failure-stream125-qgraph-c000000.json', d['run_files'])
        latch = json.loads(d['latch'])
        self.assertEqual(latch['run_name'], 'stream125-qgraph-c000000')
        self.assertIn('LTX_DECODER_GRAPH=0', latch['rule'])
        self.assertNotIn('verdict', d)

    def test_decoder_graph_repeat_only_difference_fails_the_verdict_and_latches(self):
        d = harness('--frames', '49', '--anchor', 'frame', '--inject', 'dg-repeat-diff', '--stream-chunks', '1')
        self.assertFalse(d['verdict']['passed'])
        self.assertIn('Qualification failed', d['halted'])
        self.assertEqual(d['verdict_file']['decoder_graph_failures'],
                         ['Decoded tensors differ across chains on identical latents at chunk 1 (decoder graph)'])
        self.assertEqual(json.loads(d['latch'])['run_name'], 'qualify-verdict')

    def test_sealed_reference_refuses_outputs_that_differ(self):
        d = harness('--frames', '49', '--anchor', 'frame', '--reference', 'sealed', '--stream-chunks', '1')
        self.assertFalse(d['verdict']['passed'])
        self.assertTrue(all('packet-113 reference' in f for f in d['verdict']['failures']), d['verdict']['failures'])
        self.assertEqual(len(d['verdict']['failures']), 3)
        self.assertIsNone(d['latch'])        # a reference difference is not a decoder-graph mismatch by itself
        d = harness('--frames', '49', '--anchor', 'latent', '--reference', 'sealed', '--stream-chunks', '1')
        self.assertTrue(d['verdict']['passed'], d['verdict'])     # no reference for the latent variant

    def test_audio_failure_after_the_hand_off_latches_and_refuses_the_next_chunk(self):
        d = harness('--frames', '49', '--anchor', 'frame', '--inject', 'audio-fail', '--stream-chunks', '5')
        self.assertTrue(d['verdict']['passed'])
        self.assertIn('Decode failed for stream125-s00000002', d['halted'])
        self.assertIn('stream-decode-failure-stream125-s00000002.json', d['run_files'])
        names = [ch['name'] for ch in d['chunks']]
        self.assertNotIn('stream125-s00000004', names)
        s2 = [ch for ch in d['chunks'] if ch['name'] == 'stream125-s00000002']
        if s2:                                   # its receipt may have committed before the audio failed
            self.assertFalse(s2[0]['decode_record'] or s2[0]['preview_record'])

    # -- packet117 levers ---------------------------------------------------------------------------
    def levers_common(self, d, frames, levers=('cone', 1, 1), stream_chunks=4):
        chunks = self.common(d, frames, 'frame', stream_chunks)
        ad, bo, pa = levers
        self.assertEqual(d['levers'], list(levers))
        self.assertEqual(d['lever_latches'], {})
        modes = [ch['anchor_decode']['mode'] for ch in chunks]
        self.assertEqual(modes, ['full'] * 3 + [ad] * (len(chunks) - 3))
        for ch in chunks:
            self.assertEqual(ch['levers'], {'anchor_decode': ad, 'bencode_overlap': bo, 'prep_ahead': pa})
            if ch['anchor_decode']['mode'] == 'cone':
                self.assertIs(ch['anchor_decode']['equal'], True)
                self.assertEqual(ch['anchor_decode']['display_last_frame_sha256'], ch['last_frame_sha256'])
            src = ch['conditioning_sources']
            if ch['drop'] == 1:
                eager = ch['name'].startswith('stream125-qeager')
                self.assertEqual(src['A']['source'], 'precomputed' if pa and not eager else 'native', ch['name'])
                self.assertEqual(src['B']['source'], 'precomputed' if bo and not eager else 'native', ch['name'])
                graph = ch['name'].startswith('stream125-qgraph')
                for s, on in (('A', pa), ('B', bo)):
                    self.assertEqual(src[s]['dual_equal'], True if (graph and on) else None)
            else:
                self.assertIsNone(src)
        # Decode-thread order: anchor -> stage-A encode -> go -> stage-B encode -> display -> audio.
        for ch in chunks:
            t = ch['decode_timing_ns']
            seq = [t[k] for k in ('video_done', 'anchor_ready', 'precompute_a_start', 'precompute_a_done', 'go',
                                  'precompute_b_start', 'precompute_b_done', 'display_start', 'display_done',
                                  'audio_done') if t[k] is not None]
            self.assertEqual(seq, sorted(seq), ch['name'])
        # Stream form: the deferred work waits for the successor's sampler A (the next chunk's 344 event).
        stream = chunks[6:]
        for cur, nxt in zip(stream, stream[1:]):
            if cur['name'] in ('stream125-qrepeat-c000002',) or not (ad == 'cone' or bo):
                continue
            self.assertEqual(cur['schedule']['go'], 'sampler-a-start', cur['name'])
            self.assertGreaterEqual(cur['decode_timing_ns']['go'], nxt['timing_ns']['sampler_a_start'])
            if ad == 'cone':
                self.assertGreaterEqual(cur['decode_timing_ns']['display_start'], nxt['timing_ns']['sampler_a_start'])
            if pa:
                self.assertIs(cur['schedule']['commit'], True)
                self.assertGreaterEqual(cur['decode_timing_ns']['precompute_a_start'], cur['timing_ns']['receipt_staged'])
        encodes = d['encodes']
        self.assertTrue(all(thread in ('MainThread', 'ltx120-decode') for thread, _ in encodes))
        if pa or bo:
            self.assertIn('ltx120-decode', {thread for thread, _ in encodes})
            self.assertEqual(d['snap_calls'], ['sync:xpu:3', 'xpu:3'])      # the encode guard touches xpu:3 only
        else:
            self.assertEqual({thread for thread, _ in encodes}, {'MainThread'})
        return chunks

    def test_frame_all_levers_49(self):
        d = harness('--frames', '49', '--anchor', 'frame', '--stream-chunks', '4')
        chunks = self.levers_common(d, 49)
        self.assertEqual(d['verdict_file']['anchor_decode_failures'], [])
        self.assertEqual(d['verdict_file']['precompute_failures'], [])
        rows = d['verdict_file']['lever_rows']
        self.assertEqual([r['anchor_decode'] for r in rows], ['full'] * 3 + ['cone'] * 6)
        # The chain waited only for the (shorter) cone decode; the display decode followed off the chain.
        for ch in chunks[6:]:
            self.assertLess(ch['timing_ns']['receipt_staged'], ch['decode_timing_ns']['display_start'])

    def test_frame_all_levers_97_without_decoder_graph(self):
        d = harness('--frames', '97', '--anchor', 'frame', '--decoder-graph', '0', '--reuse', '0',
                    '--stream-chunks', '3')
        self.levers_common(d, 97, stream_chunks=3)

    def test_frame_all_levers_121(self):
        d = harness('--frames', '121', '--anchor', 'frame', '--stream-chunks', '3')
        self.levers_common(d, 121, stream_chunks=3)
        self.assertEqual(d['geometry_record']['decoded_shapes'], {'images': [121, 256, 256, 3],
                                                                  'waveform': [1, 2, 240480]})
        self.assertEqual(d['geometry_record']['latent_shapes'], {'video_latent': [1, 128, 16, 8, 8],
                                                                 'audio_latent': [1, 8, 126, 16],
                                                                 'stage_a_latent': [1, 128, 16, 4, 4]})

    def test_each_lever_alone_and_all_off(self):
        for levers in (('cone', 0, 0), ('full', 1, 0), ('full', 0, 1), ('full', 0, 0)):
            d = harness('--frames', '49', '--anchor', 'frame', '--stream-chunks', '3', '--anchor-decode', levers[0],
                        '--bencode-overlap', str(levers[1]), '--prep-ahead', str(levers[2]))
            self.levers_common(d, 49, levers, stream_chunks=3)

    def test_all_levers_through_a_chain_reset_at_97(self):
        d = harness('--frames', '97', '--anchor', 'frame', '--reset-at', '2', '--stream-chunks', '5')
        chunks = self.levers_common(d, 97, stream_chunks=5)
        by = {ch['name']: ch for ch in chunks}
        self.assertEqual([ch['delivery_new_frames'] for ch in chunks[9:]], [97, 96, 97, 96, 96])
        self.assertIsNone(by['stream125-s00000002']['conditioning_sources'])          # the reset is unanchored
        pre = by['stream125-s00000001']['precompute']                                   # prepared for the reset
        self.assertEqual(pre['B']['state'], 'cancelled')                               # nobody to consume it
        for stage in ('A', 'B'):                                                        # s3 used s2's encodes
            src = by['stream125-s00000003']['conditioning_sources'][stage]
            self.assertEqual((src['source'], src['precompute']['source_run_name'], src['precompute']['consumed_by']),
                             ('precomputed', 'stream125-s00000002', 'stream125-s00000003'))

    def test_cone_anchor_that_differs_latches_at_the_graph_chain(self):
        d = harness('--frames', '49', '--anchor', 'frame', '--inject', 'cone-diff', '--stream-chunks', '1')
        self.assertIn('Decode failed for stream125-qgraph-c000000', d['halted'])
        self.assertIn('Cone anchor decode', d['halted'])
        latch = d['lever_latches']['anchor-decode-118-refused.json']
        self.assertEqual(latch['run_name'], 'stream125-qgraph-c000000')
        self.assertIs(latch['detail']['equal'], False)
        self.assertNotIn('precompute-118-refused.json', d['lever_latches'])
        self.assertNotIn('verdict', d)

    def test_cone_difference_in_the_repeat_chain_latches(self):
        d = harness('--frames', '49', '--anchor', 'frame', '--inject', 'cone-repeat-diff', '--stream-chunks', '1')
        self.assertIn('Decode failed for stream125-qrepeat-c000001', d['halted'])
        self.assertEqual(d['lever_latches']['anchor-decode-118-refused.json']['run_name'], 'stream125-qrepeat-c000001')

    def test_precomputed_conditioning_that_differs_latches_in_the_graph_chain(self):
        d = harness('--frames', '49', '--anchor', 'frame', '--inject', 'pre-diff', '--stream-chunks', '1')
        self.assertIn('Precomputed stage-A conditioning differs from the native one (stream125-qgraph-c000001)',
                      d['halted'])
        latch = d['lever_latches']['precompute-118-refused.json']
        self.assertEqual(latch['run_name'], 'stream125-qgraph-c000001')
        self.assertIs(latch['detail']['dual_equal'], False)
        self.assertNotIn('anchor-decode-118-refused.json', d['lever_latches'])

    def test_precompute_floor_on_xpu3_latches(self):
        d = harness('--frames', '49', '--anchor', 'frame', '--inject', 'pre-floor', '--stream-chunks', '2')
        self.assertIn('P5: xpu:3 physical free', d['halted'])
        self.assertIn('precompute-118-refused.json', d['lever_latches'])

    def test_latent_97_without_reuse(self):
        d = harness('--frames', '97', '--anchor', 'latent', '--reuse', '0', '--reset-at', '3', '--stream-chunks', '4')
        chunks = self.common(d, 97, 'latent')
        self.assertFalse(any(ch['reused'] for ch in chunks))
        self.assertEqual([ch['delivery_new_frames'] for ch in chunks[9:]], [97, 96, 96, 97])
        self.assertEqual(d['geometry_record']['decoded_shapes'], {'images': [97, 256, 256, 3], 'waveform': [1, 2, 192480]})

    def test_mixed_49_stage_b_waits_for_the_decoded_frame(self):
        d = harness('--frames', '49', '--anchor', 'mixed', '--reuse', '1', '--stream-chunks', '4')
        chunks = self.common(d, 49, 'mixed')
        self.assertEqual(d['encode_during_decode'], 0)    # the VAE encode never runs beside the decode
        self.assertEqual(d['encode_threads'], ['MainThread'])
        anchored = [ch for ch in chunks if ch['drop'] == 1]
        self.assertEqual(len(anchored), 9)
        for ch in anchored:
            self.assertEqual(ch['slot0_pin'], {'A': True})
            self.assertIsNone(ch['guide_pin'])
            self.assertGreaterEqual(ch['frame_in']['waited_s'], 0)
        # Every anchored chunk consumed exactly its predecessor's decoded last frame.
        by_name = {ch['name']: ch for ch in chunks}
        for ch in anchored:
            self.assertEqual(ch['frame_in']['sha256'], by_name[ch['frame_in']['source_run_name']]['last_frame_sha256'])
        # Gated chunks drained the decode first; the repeat chain and the stream overlapped and waited.
        self.assertTrue(all(ch['frame_in']['waited_s'] < 0.05 for ch in anchored[:4]))
        self.assertTrue(any(ch['frame_in']['waited_s'] > 0 and ch['decode_at_start']['pending'] > 0
                            for ch in anchored[4:]))
        timing = chunks[10]['timing_s']
        self.assertIsNotNone(timing['frame_wait'])
        self.assertEqual([ch['delivery_new_frames'] for ch in chunks[9:]], [49, 48, 48, 48])

    def test_mixed_97_reset_without_reuse(self):
        d = harness('--frames', '97', '--anchor', 'mixed', '--reuse', '0', '--reset-at', '2', '--stream-chunks', '4')
        chunks = self.common(d, 97, 'mixed')
        self.assertEqual([ch['delivery_new_frames'] for ch in chunks[9:]], [97, 96, 97, 96])
        self.assertIsNone(chunks[11]['frame_in'])         # the reset chunk waits for nothing
        self.assertEqual(chunks[12]['frame_in']['source_run_name'], 'stream125-s00000002')

    def test_guide_49_delivers_every_frame(self):
        d = harness('--frames', '49', '--anchor', 'guide', '--reuse', '1', '--reset-at', '3', '--stream-chunks', '4')
        chunks = self.common(d, 49, 'guide')
        self.assertTrue(all(ch['drop'] == 0 and ch['delivery_new_frames'] == 49 for ch in chunks))
        guided = [ch for ch in chunks if ch['guide_pin'] is not None]
        self.assertEqual(len(guided), 8)                  # 2 per chain + s1, s2 (s3 is a reset)
        self.assertTrue(all(ch['guide_pin'] == {'A': True, 'B': True} and ch['slot0_pin'] is None for ch in guided))
        self.assertEqual(d['encode_threads'], [])          # no VAE encode in guide mode

    def test_guide_97(self):
        d = harness('--frames', '97', '--anchor', 'guide', '--reuse', '0', '--stream-chunks', '3')
        self.common(d, 97, 'guide', 3)

    def test_mixed_frame_anchor_tamper_latches(self):
        d = harness('--frames', '49', '--anchor', 'mixed', '--inject', 'frame-tamper', '--stream-chunks', '5')
        self.assertTrue(d['verdict']['passed'])
        self.assertEqual(d['halted'], 'Anchor bytes differ from the recorded hash')
        self.assertIn('stream-failure-stream125-s00000003.json', d['run_files'])

    def test_repeat_chain_difference_fails_the_verdict_and_latches(self):
        d = harness('--frames', '49', '--inject', 'repeat-diff', '--stream-chunks', '2', '--decoder-graph', '0')
        self.assertFalse(d['verdict']['passed'])
        self.assertEqual(d['verdict']['failures'], ["Eager/graph/repeat tensors differ at chunk 1: ['images']"])
        self.assertIsNone(d['latch'])                     # decoder graph off: no decoder-graph latch
        self.assertIn('Qualification failed', d['halted'])
        self.assertEqual(len(d['chunks']), 9)

    def test_decode_failure_latches_and_refuses_the_next_chunk(self):
        d = harness('--frames', '49', '--anchor', 'latent', '--inject', 'decode-fail', '--stream-chunks', '5')
        self.assertTrue(d['verdict']['passed'])
        self.assertIn('Decode failed for stream125-s00000002', d['halted'])
        self.assertIn('halted', d['stream_error'])
        self.assertIn('stream-decode-failure-stream125-s00000002.json', d['run_files'])
        last = d['chunks'][-1]
        self.assertEqual(last['name'], 'stream125-s00000002')
        self.assertFalse(last['decode_record'] or last['preview_record'])

    def test_97_geometry_mismatch_is_recorded_then_latches(self):
        d = harness('--frames', '97', '--inject', 'geometry', '--stream-chunks', '1')
        self.assertIn('Tensor geometry differs: waveform [1, 2, 192960]', d['halted'])
        self.assertIn('stream-geometry-mismatch-stream125-qeager-c000000.json', d['run_files'])
        self.assertIn('stream-halt.json', d['run_files'])


if __name__ == '__main__':
    unittest.main()


class Flow118(unittest.TestCase):
    """Packet123 cases: the snapshot inspector (walk and fingerprint, the dual policy, a disagreement, a mutation,
    a near-floor reading), the timing split in every receipt, and the decoder-graph pool cap."""

    def passed(self, d, stream_chunks=4):
        self.assertIsNone(d.get('error'), d.get('error'))
        self.assertTrue(d['verdict']['passed'], d['verdict'])
        self.assertIsNone(d['halted'])
        self.assertEqual(len(d['chunks']), 9 + stream_chunks)
        self.assertEqual(d['lever_latches'], {})

    def labels(self, ch):
        return [s['label'] for s in ch['snapshots']]

    def test_walk_mode_is_the_packet117_path_with_timing(self):
        d = harness('--frames', '49', '--anchor', 'frame', '--snapshot-mode', 'walk')
        self.passed(d)
        for ch in d['chunks']:
            self.assertEqual({s['mode'] for s in ch['snapshots']}, {'walk'})
            self.assertFalse(any(s['dual'] for s in ch['snapshots']))
            self.assertEqual(ch['server_options'], {'gc_interval_seconds': 10, 'display_worker': 'serial', 'run_write_allowance_bytes': 3 * 2**30, 'display_schedule': 'sampler-a', 'anchor_read_ahead': 0, 'snapshot_schedule': 'full', 'display_device': 'xpu:3', 'snapshot_mode': 'walk', 'decoder_graph_pool_cap_bytes': None, 'aux_residency': 'legacy', 'residency_qualification_id': '692796408498da76c250fe324d8f52b1557493438a8bf927751313dace53c9c2'})
        self.assertIsNone(d['snapshot_state']['ledger'])
        self.assertEqual(d['verdict_file']['snapshot_failures'], [])

    def test_fingerprint_policy_timing_split_and_turnaround(self):
        d = harness('--frames', '97', '--anchor', 'frame', '--stream-chunks', '22')
        self.passed(d, 22)
        by = {ch['name']: ch for ch in d['chunks']}
        for ch in d['chunks']:
            anchored = not ch['name'].endswith(('c000000', 's00000000'))
            want = ['request-before'] + (['A-before', 'A-after', 'B-before', 'B-after'] if anchored else []) + \
                ['request-after']
            self.assertEqual(self.labels(ch), want, ch['name'])
            seq = None if not ch['name'].startswith('stream125-s') else int(ch['name'][-8:])
            dual = seq is None or seq % 20 == 0
            self.assertEqual({s['dual'] for s in ch['snapshots']}, {dual}, ch['name'])
            split = ch['timing_s']['submit_split']
            tiles = [split[k] for k in ('precheck', 'comfy_validate_queue', 'queue_to_executor', 'authority_begin',
                                        'before_request_checks', 'request_before_snapshot', 'before_request_tail',
                                        'executor_to_first_node', 'first_node_to_condition_a', 'condition_a_lookup',
                                        'condition_a_tail', 'dispatch_to_sampler_a') if split[k] is not None]
            self.assertAlmostEqual(sum(tiles) + split['other'], split['total'], places=5)
            self.assertEqual(split['total'], ch['timing_s']['submit_to_sampler_start'])
            self.assertGreater(ch['authority_checks']['healthy_calls'], 0)
            self.assertIn('344', ch['node_starts'])
            if anchored:
                self.assertIsNotNone(split['stage_a_before_snapshot'])
                self.assertIsNotNone(ch['turnaround'])
                m = ch['turnaround']['marks_ns']
                self.assertTrue(m['receipt_staged'] <= m['commit'] <= m['commit_written'] <= m['submit'])
        self.assertEqual(by['stream125-s00000020']['snapshots'][0]['dual'], True)
        stats = d['snapshot_state']['ledger']['stats']
        self.assertEqual((stats['disagreements'], stats['fallback_walks'], stats['placement_fallbacks']), (0, 0, 0))
        self.assertGreater(stats['fingerprint'], 0)
        self.assertEqual(stats['agreements'], stats['dual_walks'])
        rows = d['verdict_file']['snapshot_rows']
        self.assertEqual(len(rows), 9)
        self.assertTrue(all(set(r['dual']) == {True} and set(r['agree']) == {True} for r in rows))

    def test_disagreement_latches_the_snapshot_latch(self):
        d = harness('--frames', '49', '--anchor', 'frame', '--inject', 'snap-diff')
        self.assertIsNotNone(d['halted'])
        self.assertIn('Snapshot fingerprint disagrees with the walk', d['halted'])
        latch = d['lever_latches']['snapshot-118-refused.json']
        self.assertEqual(latch['run_name'], 'stream125-qgraph-c000001')
        self.assertEqual(latch['schema'], 'ltx.stream118.lever-latch.v1')
        self.assertNotIn('precompute-118-refused.json', d['lever_latches'])

    def test_disagreement_injection_is_a_plain_refusal_in_walk_mode(self):
        d = harness('--frames', '49', '--anchor', 'frame', '--inject', 'snap-diff', '--snapshot-mode', 'walk')
        self.assertIn('Residence/ownership changed: video_vae', d['halted'])
        self.assertEqual(d['lever_latches'], {})

    def test_a_moved_tensor_halts_both_modes_alike(self):
        halts = {}
        for mode in ('walk', 'fingerprint'):
            d = harness('--frames', '49', '--anchor', 'frame', '--inject', 'snap-mutate', '--snapshot-mode', mode)
            halts[mode] = d['halted']
            self.assertEqual(d['lever_latches'], {})
            self.assertIn('stream-failure-stream125-s00000002.json', d['run_files'])
        self.assertEqual(halts['walk'], halts['fingerprint'])
        self.assertIn('Admitted tensor ownership changed', halts['walk'])

    def test_near_floor_reading_runs_the_walk_beside_the_fingerprint(self):
        d = harness('--frames', '49', '--anchor', 'frame', '--inject', 'snap-near', '--stream-chunks', '5')
        self.passed(d, 5)
        by = {ch['name']: ch for ch in d['chunks']}
        self.assertEqual({s['dual'] for s in by['stream125-s00000002']['snapshots']}, {False})
        s3 = by['stream125-s00000003']['snapshots']
        self.assertEqual(s3[0]['dual'], True)                      # the first near-floor reading triggers the walk
        self.assertTrue(all(s['dual'] for s in s3))
        self.assertLess(s3[0]['min_margin_bytes'], 2 ** 29)

    def test_pool_cap_captures_one_method_and_the_gate_passes(self):
        d = harness('--frames', '121', '--anchor', 'frame', '--pool-cap', '1.0')
        self.passed(d)
        pool = [r['pool'] for r in d['verdict_file']['decoder_graph_rows'] if r['run_name'].endswith('qgraph-c000000')]
        self.assertEqual(pool[0]['captured'], ['forward_pre_diffusion'])
        self.assertEqual(pool[0]['capped'], ['forward_diff_step'])
        self.assertEqual(pool[0]['cap_bytes'], 10 ** 9)
        for ch in d['chunks']:
            self.assertEqual(ch['server_options']['decoder_graph_pool_cap_bytes'], 10 ** 9)
