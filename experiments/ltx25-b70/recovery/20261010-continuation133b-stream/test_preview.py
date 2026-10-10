"""CPU tests (packet116): the preview writer behind the decode thread, the frame-anchor hand-off, the diagnostic.

The exactness claim of lever 1 is that moving the MP4 write off the chain cannot change
any tensor or the anchor. These tests check the pieces that claim rests on: the anchor
the next chunk is handed is byte-for-byte the frame hashed into the receipt, even while a
preview of the same images is being written (and even if the writer scribbles on its
copy); previews are never dropped and are written in order under back-pressure; the
MP4 name never shows a partial file; and the encoder calls are save_preview's.
"""
import ast
import hashlib
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stream_contract as c  # noqa: E402
import stream_preview as sp  # noqa: E402
import stream_receipts as rec  # noqa: E402

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None

SEALED_DECODE = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-112/'
                     'source/scripts/pipeline_decode_node.py')


def job(name, images=None, audio=None, path='/out/x.mp4'):
    return {'run_name': name, 'prompt_id': 'p-' + name, 'images': images, 'audio': audio, 'path': path,
            'relative': name + '/preview_00001_.mp4', 'includes_overlap_frame': True,
            'timing': {'submit': 1, 'decode_done': time.time_ns()}}


def fake_info(raw=b'mp4'):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


class Writer(unittest.TestCase):
    def test_in_order_backpressure_never_drops(self):
        gate = threading.Event()
        written, committed = [], []

        def save(j):
            gate.wait(5)
            written.append(j['run_name'])
            return fake_info()
        w = sp.StreamPreviewWriter(save, lambda j, r: committed.append(r), lambda j, e: None, maxsize=2)
        try:
            names = ['c%d' % i for i in range(6)]
            done = []

            def producer():
                for n in names:
                    done.append(w.submit(job(n)))
            t = threading.Thread(target=producer)
            t.start()
            time.sleep(0.3)
            # One in progress + two queued; the fourth submit is blocked (back-pressure), none dropped.
            self.assertEqual(len(done), 3)
            self.assertTrue(t.is_alive())
            gate.set()
            t.join(5)
            self.assertTrue(w.drain(5))
            self.assertEqual(written, names)
            self.assertEqual([r['run_name'] for r in committed], names)
            self.assertTrue(any(blocked > 0.1 for _, _, blocked in done))
            for r in committed:
                t_ = r['timing_ns']
                self.assertLessEqual(t_['decode_done'], t_['preview_queued'])
                self.assertLessEqual(t_['preview_queued'], t_['write_start'])
                self.assertLessEqual(t_['write_start'], t_['preview_written'])
            self.assertEqual(w.summary()['completed'], 6)
        finally:
            gate.set()
            w.close()

    def test_failure_latches_once_and_stops_later_writes(self):
        failures = []

        def save(j):
            if j['run_name'] == 'c1':
                raise OSError('disk')
            return fake_info()
        w = sp.StreamPreviewWriter(save, lambda j, r: r, lambda j, e: failures.append((j['run_name'], repr(e))))
        try:
            w.submit(job('c0'))
            w.submit(job('c1'))
            deadline = time.monotonic() + 5
            while w.failed is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertIn('c1', w.failed)
            self.assertFalse(w.drain(1))
            with self.assertRaises(sp.PreviewFailure):
                w.submit(job('c2'))
            self.assertEqual([f[0] for f in failures], ['c1'])
            self.assertIsNotNone(w.record('c0'))
            self.assertIsNone(w.record('c1'))
        finally:
            w.close()

    def test_submit_bound(self):
        gate = threading.Event()
        w = sp.StreamPreviewWriter(lambda j: (gate.wait(5), fake_info())[1], lambda j, r: r, lambda j, e: None,
                                   maxsize=1, submit_bound_s=0.6)
        try:
            w.submit(job('a'))
            w.submit(job('b'))
            time.sleep(0.1)
            with self.assertRaises(sp.PreviewFailure):
                w.submit(job('c'))
        finally:
            gate.set()
            w.close()


class AtomicPublish(unittest.TestCase):
    def test_final_name_appears_complete_and_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            final = Path(tmp) / 'stream133b-s00000001' / 'preview_00001_.mp4'
            final.parent.mkdir()
            part = sp.temporary_name(final)
            self.assertEqual(part.parent, final.parent)
            self.assertNotRegex(part.name, r'^preview_[0-9]{5}_\.mp4$')   # never matches the client pattern
            part.write_bytes(b'abc' * 1000)
            info = sp.publish_exclusive(part, final)
            self.assertEqual(info, fake_info(b'abc' * 1000))
            self.assertFalse(part.exists())
            part.write_bytes(b'x')
            with self.assertRaises(FileExistsError):
                sp.publish_exclusive(part, final)
            self.assertEqual(final.read_bytes(), b'abc' * 1000)

    def test_encoder_calls_are_save_previews(self):
        """save_preview_atomic must call CreateVideo.execute and save_to with exactly the
        arguments of the sealed pipeline_decode_node.save_preview (only the path differs)."""
        def calls(tree, fn):
            node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == fn)
            out = {}
            for call in (n for n in ast.walk(node) if isinstance(n, ast.Call)):
                name = ast.unparse(call.func)
                if name.endswith('CreateVideo.execute') or name.endswith('.save_to'):
                    out[name.split('.')[-1]] = {k.arg: ast.unparse(k.value) for k in call.keywords}
            return out
        sealed = calls(ast.parse(SEALED_DECODE.read_text()), 'save_preview')
        ours = calls(ast.parse((HERE / 'stream_preview.py').read_text()), 'save_preview_atomic')
        self.assertEqual(set(sealed), {'execute', 'save_to'})
        self.assertEqual(ours, sealed)
        sealed_src = SEALED_DECODE.read_text()
        self.assertIn("file = f\"{filename}_{counter:05}_.mp4\"", sealed_src)
        self.assertIn("file = f\"{filename}_{counter:05}_.mp4\"", (HERE / 'stream_preview.py').read_text())


@unittest.skipIf(torch is None, 'torch not importable')
class AnchorHandOff(unittest.TestCase):
    def test_next_chunk_anchor_is_the_hashed_frame_while_preview_writes(self):
        """The receipt hashes images (and anchor_out = sha of images[last]); the provider of the next
        chunk rebuilds the tensor from the verified anchor file. Both must be the same bytes, even
        with a preview writer concurrently holding and scribbling on its own copy."""
        g = c.geometry(49)
        last = g['anchor_frame_index']
        gen = torch.Generator().manual_seed(113)
        images = torch.rand(*g['tensor_shapes']['images'], generator=gen, dtype=torch.float32)
        waveform = torch.rand(*g['tensor_shapes']['waveform'], generator=gen)
        audio = {'waveform': waveform, 'sample_rate': c.SAMPLE_RATE}
        images_sha = hashlib.sha256(images.contiguous().view(torch.uint8).numpy()).hexdigest()
        frame_sha = hashlib.sha256(images[last:last + 1].contiguous().view(torch.uint8).numpy()).hexdigest()
        seen = {}
        started = threading.Event()

        def save(j):
            seen['sha'] = hashlib.sha256(j['images'].contiguous().view(torch.uint8).numpy()).hexdigest()
            seen['aliases'] = j['images'].data_ptr() == images.data_ptr() or \
                j['audio']['waveform'].data_ptr() == waveform.data_ptr()
            started.set()
            j['images'].mul_(0.0).add_(7.0)          # an adversarial writer cannot reach the source
            j['audio']['waveform'].zero_()
            time.sleep(0.2)
            return fake_info()
        w = sp.StreamPreviewWriter(save, lambda j, r: r, lambda j, e: None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                raw = sp.anchor_bytes(torch, images, last)
                anchor = rec.write_anchor(Path(tmp), 'stream133b-s00000004', raw, 49)
                p_images, p_audio = sp.private_copy(images, audio)
                w.submit(job('stream133b-s00000004', p_images, p_audio))
                self.assertTrue(started.wait(5))
                # Next chunk's provider path (integration.provide_anchor) while the writer runs.
                loaded = rec.read_anchor(anchor['path'], anchor['sha256'])
                tensor = sp.load_anchor_tensor(torch, loaded, c.ANCHOR_SHAPE)
                self.assertTrue(w.drain(5))
            self.assertEqual(anchor['sha256'], frame_sha)
            self.assertEqual(hashlib.sha256(loaded).hexdigest(), frame_sha)
            self.assertEqual(tensor.contiguous().view(torch.uint8).numpy().tobytes(), raw)
            self.assertTrue(torch.equal(tensor.view(torch.int32), images[last:last + 1].view(torch.int32)))
            # The source tensors are untouched by the writer; the writer saw the same bytes.
            self.assertEqual(hashlib.sha256(images.contiguous().view(torch.uint8).numpy()).hexdigest(), images_sha)
            self.assertEqual(seen['sha'], images_sha)
            self.assertFalse(seen['aliases'])
            self.assertFalse(bool((waveform == 0).all()))
        finally:
            w.close()

    def test_diagnostic_matches_reference_and_sees_a_border(self):
        g = c.geometry(49)
        last = g['anchor_frame_index']
        gen = torch.Generator().manual_seed(7)
        images = torch.rand(*g['tensor_shapes']['images'], generator=gen) * 0.2 + 0.4
        images[last, :16, :, 0] = 1.0                 # a saturated red top border
        images[last, :, -16:, 2] = 0.0
        ours = sp.anchor_diagnostic(torch, images, last)
        ref = rec.border_diagnostic_reference(sp.anchor_bytes(torch, images, last))
        self.assertEqual(set(ours), set(ref))
        for k, v in ref.items():
            if isinstance(v, float):
                self.assertAlmostEqual(ours[k], v, places=5)
            else:
                self.assertEqual(ours[k], v)
        self.assertGreater(ours['border_to_centre_chroma_ratio'], 2.0)
        self.assertGreater(ours['border_clipped_fraction'], 0.1)
        self.assertEqual(ours['centre_clipped_fraction'], 0.0)
        self.assertEqual((ours['border_pixels'], ours['centre_pixels']), (256 * 256 - 224 * 224, 128 * 128))
        rec.validate_diagnostic(ours)
        self.assertLess(len(json.dumps(ours)), 1024)


class Sharpness(unittest.TestCase):
    """Packet116 seam diagnostic: Laplacian variance of decoded frames, torch (float64) vs the stdlib reference."""
    def test_matches_reference_and_ranks_blur(self):
        for frames in c.FRAME_CHOICES:
            g = c.geometry(frames)
            gen = torch.Generator().manual_seed(11)
            images = torch.rand(*g['tensor_shapes']['images'], generator=gen)
            # Blur frames 0-2 (box filter): the profile must see them as softer than the middle frame.
            for i in (0, 1, 2):
                f = images[i]
                images[i] = (f + f.roll(1, 0) + f.roll(-1, 0) + f.roll(1, 1) + f.roll(-1, 1)) / 5
            ours = sp.sharpness_profile(torch, images, frames)
            rec.validate_sharpness(ours, frames)
            self.assertEqual(ours['frames'], g['sharpness_frames'])
            for i in (0, frames // 2):
                raw = images[i].contiguous().view(torch.uint8).numpy().tobytes()
                self.assertAlmostEqual(ours['laplacian_variance'][str(i)], rec.sharpness_reference(raw), places=7)
            self.assertLess(ours['relative_to_reference']['0'], 0.5)
            self.assertEqual(ours['relative_to_reference'][str(frames // 2)], 1.0)
            self.assertEqual(ours['first_frames_min_relative'],
                             min(ours['relative_to_reference'][str(i)] for i in (0, 1, 2, 5)))
            self.assertEqual(ours['last_frame_relative'], ours['relative_to_reference'][str(frames - 1)])
        flat = torch.full([49, 256, 256, 3], 0.5)
        profile = sp.sharpness_profile(torch, flat, 49)
        self.assertEqual(profile['laplacian_variance']['0'], 0.0)
        self.assertIsNone(profile['relative_to_reference']['0'])      # no reference sharpness: no ratio
        with self.assertRaises(ValueError):
            rec.validate_sharpness(dict(profile, frames=[0]), 49)


class PreviewRecord(unittest.TestCase):
    def test_record_schema_and_binding(self):
        t = {'submit': 1, 'video_done': 2, 'anchor_ready': 2, 'audio_done': 3, 'decode_done': 3, 'hashed': 4,
             'record_written': 5, 'preview_queued': 6, 'write_start': 7, 'preview_written': 8}
        r = {'schema': rec.PREVIEW_SCHEMA, 'run_name': 'stream133b-s00000001', 'prompt_id': 'p',
             'path': '/o/stream133b-s00000001/preview_00001_.mp4', 'relative_to_output_directory': 'x',
             'sha256': 'a' * 64, 'bytes': 10, 'container': 'mp4', 'written': True, 'order': 'fifo',
             'timing_ns': t}
        rec.validate_preview_record(r)
        receipt = {'run_name': 'stream133b-s00000001', 'prompt_id': 'p', 'timing_ns': {'decode_done': None},
                   'preview': {'path': r['path']}}
        rec.validate_preview_record(r, receipt)
        for mutate in (lambda x: x.__setitem__('bytes', 0), lambda x: x['timing_ns'].__setitem__('write_start', 9),
                       lambda x: x['timing_ns'].__setitem__('record_written', 7),
                       lambda x: x.__setitem__('written', False)):
            x = json.loads(json.dumps(r))
            mutate(x)
            with self.assertRaises(ValueError):
                rec.validate_preview_record(x)
        with self.assertRaises(ValueError):
            rec.validate_preview_record(r, dict(receipt, prompt_id='q'))


class IntegrationWiring(unittest.TestCase):
    """Source-level checks of the server wiring that CPU tests cannot execute."""
    def setUp(self):
        self.src = (HERE / 'integration.py').read_text()

    def test_decode_thread_hands_the_preview_off_after_its_record(self):
        out = self.src[self.src.index('    def output('):self.src.index('    def _conditioning_policy')]
        self.assertNotIn('save_preview', out.replace('_save_preview', ''))      # no inline write
        self.assertNotIn('self.preview.submit', out)                            # the decode thread does it
        dec = self.src[self.src.index('    def _decode_job('):self.src.index('    def inspect_state')]
        order = [dec.index(s) for s in ("self.write('receipts/decode-'", 'private_copy(', 'self.preview.submit(')]
        self.assertEqual(order, sorted(order))
        self.assertIn("'timing': {'submit': timing['submit'], 'video_done': timing['video_done']", dec)
        self.assertIn("'record_written': record_written}", dec)
        self.assertLess(dec.index("record_written = time.time_ns()"), dec.index('self.preview.submit('))

    def test_verdict_waits_for_previews_and_fault_includes_writer(self):
        self.assertIn('self.preview.drain(PREVIEW_DRAIN_BOUND_S)', self.src)
        self.assertIn('self.preview.failed is not None', self.src[self.src.index('def fault'):][:400])
        self.assertIn('self.decoder.failed is not None', self.src[self.src.index('def fault'):][:400])


if __name__ == '__main__':
    unittest.main()
