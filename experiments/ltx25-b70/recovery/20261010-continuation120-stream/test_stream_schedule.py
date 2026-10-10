"""Packet120 CPU tests of bounds, successor identity, immutable read-ahead, and real runtime flow."""
import hashlib
from pathlib import Path
import tempfile
import time
import unittest

import stream_schedule as s


class Options(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(s.launch_options({}), ('sampler-a', 0, 'full'))

    def test_all_modes(self):
        for mode in s.DISPLAY_SCHEDULES:
            self.assertEqual(s.launch_options({'LTX_DISPLAY_SCHEDULE': mode})[0], mode)

    def test_bad_display(self):
        with self.assertRaises(ValueError): s.launch_options({'LTX_DISPLAY_SCHEDULE': 'other'})

    def test_bad_ahead(self):
        with self.assertRaises(ValueError): s.launch_options({'LTX_ANCHOR_READ_AHEAD': 'yes'})

    def test_bad_snapshot(self):
        with self.assertRaises(ValueError): s.launch_options({'LTX_SNAPSHOT_SCHEDULE': 'none'})

    def test_walk_rejects_partial_sync(self):
        with self.assertRaises(ValueError):
            s.launch_options({'LTX_SNAPSHOT_SCHEDULE': 'a-xpu3-sync', 'LTX_SNAPSHOT_MODE': 'walk'})


class Barrier(unittest.TestCase):
    def test_matching_source_and_hash(self):
        b = s.SuccessorBarrier(); b.mark('source', 'hash', 'consumer', 'prompt', 42)
        row = b.wait('source', 'hash', time.monotonic() + .1, lambda: False)
        self.assertEqual(row['reason'], 'matching-successor-sampler-b-start')
        self.assertEqual(row['event']['consumer_run_name'], 'consumer')
        self.assertEqual(row['event']['sampler_b_start_ns'], 42)

    def test_same_hash_other_chain_cannot_release(self):
        b = s.SuccessorBarrier(); b.mark('other', 'hash', 'consumer', 'prompt', 42)
        self.assertEqual(b.wait('source', 'hash', time.monotonic(), lambda: False)['reason'], 'bound')

    def test_same_source_other_hash_cannot_release(self):
        b = s.SuccessorBarrier(); b.mark('source', 'other', 'consumer', 'prompt', 42)
        self.assertEqual(b.wait('source', 'hash', time.monotonic(), lambda: False)['reason'], 'bound')

    def test_expired_deadline_adds_no_second_wait(self):
        started = time.monotonic()
        row = s.SuccessorBarrier().wait('source', 'hash', started - 3, lambda: False)
        self.assertLess(time.monotonic() - started, .1)
        self.assertEqual(row['reason'], 'bound')

    def test_halt(self):
        row = s.SuccessorBarrier().wait('source', 'hash', time.monotonic() + 3, lambda: True)
        self.assertEqual(row['reason'], 'halted')

    def test_bounded_history(self):
        b = s.SuccessorBarrier()
        for i in range(50): b.mark(str(i), 'h', 'c', 'p', i)
        self.assertEqual(len(b.events), 16)


class ReadAhead(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ltx120-read-ahead-', dir='/dev/shm')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'anchor'
        self.path.write_bytes(b'frame')
        self.sha = hashlib.sha256(b'frame').hexdigest()
        self.reads = 0
        self.cache = s.AnchorReadAhead()

    def read(self, path, sha):
        self.reads += 1
        raw = Path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != sha: raise ValueError('bad hash')
        return raw

    def test_miss_native(self):
        self.assertEqual(self.cache.take(self.path, self.sha, self.read), (b'frame', 'native-miss'))

    def test_hit_no_reread(self):
        self.cache.prepare(self.path, self.sha, self.read)
        self.assertEqual(self.cache.take(self.path, self.sha, self.read), (b'frame', 'verified-read-ahead'))
        self.assertEqual(self.reads, 1)

    def test_changed_file_revalidated(self):
        self.cache.prepare(self.path, self.sha, self.read)
        self.path.write_bytes(b'wrong')
        with self.assertRaises(ValueError): self.cache.take(self.path, self.sha, self.read)

    def test_symlink_refused_on_hit(self):
        self.cache.prepare(self.path, self.sha, self.read)
        other = self.path.with_name('other'); self.path.rename(other); self.path.symlink_to(other)
        with self.assertRaises(ValueError): self.cache.take(self.path, self.sha, self.read)

    def test_replacement_matching_bytes_native(self):
        self.cache.prepare(self.path, self.sha, self.read)
        other = self.path.with_name('other'); other.write_bytes(b'frame'); other.replace(self.path)
        self.assertEqual(self.cache.take(self.path, self.sha, self.read)[1], 'native-file-changed')

    def test_mutable_loader_refused(self):
        with self.assertRaises(ValueError):
            self.cache.prepare(self.path, self.sha, lambda *a: bytearray(b'frame'))


class NativeDecoder(unittest.TestCase):
    def test_graph_cone_eager_display_frozen_native_bytes(self):
        from test_anchor_decode import (OverDecoderGraph, Budget, bits, latent, torch)
        helper = OverDecoderGraph()
        for dtype in (torch.float32, torch.bfloat16):
            vae, dg, cone, originals = helper.make(dtype)
            try:
                z = latent(51, 5, dtype)
                with Budget(mlp=1024), torch.inference_mode():
                    original = vae.decode(z)
                    with dg.graph_decode(), cone.cone_decode():
                        anchor = vae.decode(z)
                    display = vae.decode(z)
                    dg.freeze()
                    with dg.graph_decode(), cone.cone_decode():
                        repeat = vae.decode(z)
                    display_repeat = vae.decode(z)
                self.assertEqual(bits(original), bits(display))
                self.assertEqual(bits(display), bits(display_repeat))
                self.assertEqual(bits(original[:, :, -1]), bits(anchor[:, :, -1]))
                self.assertEqual(bits(anchor), bits(repeat))
                self.assertEqual(dg.signatures(), {'forward_pre_diffusion': 1, 'forward_diff_step': 0})
                self.assertEqual([r['method'] for r in dg.captures], ['forward_pre_diffusion'])
            finally:
                helper.close(vae, originals)


class RuntimeFlow(unittest.TestCase):
    def run_flow(self, *args):
        from test_runtime_flow import harness
        d = harness('--anchor', 'frame', '--stream-chunks', '4', '--decode-delay', '0.001',
                    '--audio-delay', '0.001', '--client-delay', '0.005', *args)
        self.assertIsNone(d.get('error'), d.get('error'))
        self.assertTrue(d['verdict']['passed'], d['verdict'])
        self.assertFalse(d['xpu_initialized'])
        self.assertIsNone(d['halted'])
        self.assertTrue(d['live_schedule_gate']['passed'], d['live_schedule_gate'])
        return d

    def test_sampler_b_matching_release_and_gated_no_wait(self):
        d = self.run_flow('--display-schedule', 'sampler-b')
        live = d['chunks'][6:]
        self.assertTrue(any(c['schedule']['display_release']['reason'] ==
                            'matching-successor-sampler-b-start' for c in live))
        for chunk in d['chunks'][3:6]:
            self.assertEqual(chunk['schedule']['display_release']['reason'], 'gated-no-wait')
        for chunk in live:
            release = chunk['schedule']['display_release']
            if release['event']:
                self.assertEqual(release['event']['source_run_name'], chunk['name'])
                self.assertLessEqual(release['event']['sampler_b_start_ns'],
                                     chunk['decode_timing_ns']['display_start'])

    def test_eager_display_graph_cone_gate(self):
        d = self.run_flow('--display-schedule', 'eager-display', '--pool-cap', '1.0')
        graph = d['chunks'][3]
        self.assertEqual(graph['decoder']['new_captures'], 1)
        self.assertEqual(graph['decoder']['signatures'], {'forward_pre_diffusion': 1, 'forward_diff_step': 0})
        self.assertTrue(graph['anchor_decode']['equal'])

    def test_read_ahead_and_reset(self):
        d = self.run_flow('--anchor-read-ahead', '1', '--reset-at', '2')
        self.assertTrue(any(c['anchor_read_source'] == 'verified-read-ahead' for c in d['chunks']))
        self.assertTrue(all(c['anchor_decode']['equal'] for c in d['chunks'][3:]))

    def test_all_off_native_reader(self):
        d = self.run_flow()
        self.assertTrue(all(c['anchor_read_source'] in (None, 'native') for c in d['chunks']))

    def test_reduced_barriers_only_at_eligible_live_a_sites(self):
        d = self.run_flow('--snapshot-schedule', 'a-xpu3-sync')
        reduced = []
        for chunk in d['chunks']:
            for row in chunk['snapshots']:
                self.assertEqual(row['memory_cards'], ['xpu:0', 'xpu:1', 'xpu:2', 'xpu:3'])
                if row['synchronized'] == ['xpu:3']:
                    self.assertIn('-s', chunk['name'])
                    self.assertIn(row['label'], ('A-before', 'A-after'))
                    self.assertFalse(row['dual'])
                    reduced.append(row)
        self.assertTrue(reduced)


if __name__ == '__main__': unittest.main()
