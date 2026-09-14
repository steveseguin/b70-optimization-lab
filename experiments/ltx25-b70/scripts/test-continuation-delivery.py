#!/usr/bin/env python3
"""Bounded synthetic delivery tests, standard library only; no subprocesses."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS))
import continuation_delivery as delivery

FRAME_BYTES = 786432
ZEROS = bytes(65536)


def prefix(index):
    return struct.pack('<8I', index, 0x80000000, 0x00000001, 0x80000001,
                       0x7f7fffff, 0xff7fffff, 0x40000000, 0xc0000000)


def zeros_into(digest, count):
    while count:
        take = min(count, len(ZEROS))
        digest.update(ZEROS[:take])
        count -= take


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ltx-delivery-cpu-')
        self.root = Path(self.tmp.name) / 'continuation-fixture'
        self.root.mkdir()
        self.capture = self.root / 'tensors.safetensors'
        self.summary = self.root / 'summary.json'
        self.header = {}
        offset = 0
        reports = {}
        self.frame_hashes = []
        for name in sorted(delivery.SHAPES):
            length = delivery.BYTE_LENGTHS[name]
            self.header[name] = {'dtype': 'F32', 'shape': list(delivery.SHAPES[name]),
                                 'data_offsets': [offset, offset + length]}
            offset += length
            digest = hashlib.sha256()
            if name == 'images':
                for index in range(25):
                    word = prefix(index)
                    digest.update(word)
                    zeros_into(digest, FRAME_BYTES - len(word))
                    frame = hashlib.sha256(word)
                    zeros_into(frame, FRAME_BYTES - len(word))
                    self.frame_hashes.append(frame.hexdigest())
            else:
                zeros_into(digest, length)
            reports[name] = {'dtype': 'torch.float32', 'shape': list(delivery.SHAPES[name]),
                             'finite': True, 'sha256': digest.hexdigest()}
        raw = json.dumps(self.header, separators=(',', ':')).encode()
        raw += b' ' * (-len(raw) % 8)
        self.data_start = len(raw) + 8
        with self.capture.open('wb') as stream:
            stream.write(struct.pack('<Q', len(raw)))
            stream.write(raw)
            stream.truncate(self.data_start + offset)
            for index in range(25):
                stream.seek(self.data_start + self.header['images']['data_offsets'][0] + index * FRAME_BYTES)
                stream.write(prefix(index))
        self.report = {'run_name': self.root.name, 'sample_rate': 48000,
                       'deterministic_enabled': True, 'deterministic_warn_only': False,
                       'tensors': reports}
        self.write_summary()

    def tearDown(self):
        self.tmp.cleanup()

    def write_summary(self):
        self.summary.write_text(json.dumps(self.report))

    def verify(self):
        return delivery.verify_capture(self.capture, self.summary)

    def mutate(self, name='images', frame=24, word=0x00000002):
        offset = self.data_start + self.header[name]['data_offsets'][0]
        if name == 'images':
            offset += frame * FRAME_BYTES
        with self.capture.open('r+b') as stream:
            stream.seek(offset)
            stream.write(struct.pack('<I', word))

    def test_full_verification_four_hashes_anchor_and_honest_scope(self):
        receipt = self.verify()
        self.assertTrue(receipt['complete'])
        self.assertTrue(receipt['strict_determinism_reported'])
        self.assertFalse(receipt['runtime_identity_verified'])
        self.assertFalse(receipt['original_reference_parity_verified'])
        self.assertFalse(receipt['deterministic_replay_verified'])
        self.assertFalse(receipt['delivery_complete'])
        self.assertEqual(receipt['run_name'], self.root.name)
        self.assertEqual(receipt['summary_file_sha256'], hashlib.sha256(self.summary.read_bytes()).hexdigest())
        self.assertEqual(receipt['frame_sha256'], self.frame_hashes)
        self.assertEqual(receipt['anchor_sha256'], self.frame_hashes[24])
        _, anchor_metadata = delivery.anchor_io.extract_anchor(self.capture)
        self.assertEqual(receipt['anchor_sha256'], anchor_metadata['sha256'])
        for name, report in self.report['tensors'].items():
            self.assertEqual(receipt['tensors'][name]['sha256'], report['sha256'])
            self.assertEqual(receipt['tensors'][name]['shape'], report['shape'])

    def test_exact_25_then24_frames_no_clipping_or_conversion(self):
        receipt = self.verify()
        for chunk_index, first in ((0, 0), (1, 1), (12, 1)):
            count = 0
            for index, payload in enumerate(delivery.iter_delivery_frames(self.capture, receipt, chunk_index), first):
                self.assertIs(type(payload), bytes)
                self.assertEqual(len(payload), FRAME_BYTES)
                self.assertEqual(payload[:32], prefix(index))
                self.assertEqual(hashlib.sha256(payload).hexdigest(), self.frame_hashes[index])
                count += 1
            self.assertEqual(count, 25 - first)
        self.assertFalse(receipt['delivery_complete'])

    def test_actual_read_requests_never_exceed64k_in_verification_or_delivery(self):
        import contextlib
        original = delivery._open_regular
        sizes = []
        opened = []
        class Tracked:
            def __init__(self, stream): self.stream = stream
            def read(self, length):
                sizes.append(length)
                return self.stream.read(length)
            def seek(self, *args): return self.stream.seek(*args)
            def fileno(self): return self.stream.fileno()
        @contextlib.contextmanager
        def wrapped(path):
            with original(path) as (stream, identity):
                opened.append(stream)
                yield Tracked(stream), identity
        with mock.patch.object(delivery, '_open_regular', side_effect=wrapped):
            receipt = self.verify()
            for _ in delivery.iter_delivery_frames(self.capture, receipt, 1): pass
        self.assertTrue(sizes)
        self.assertLessEqual(max(sizes), 65536)
        self.assertTrue(all(stream.closed for stream in opened))

    def test_cancel_close_does_not_read_remaining_frames_or_claim_completion(self):
        import contextlib
        receipt = self.verify()
        original = delivery._open_regular
        opened = []
        @contextlib.contextmanager
        def wrapped(path):
            with original(path) as (stream, identity):
                opened.append(stream)
                yield stream, identity
        with mock.patch.object(delivery, '_open_regular', side_effect=wrapped), \
             mock.patch.object(delivery, '_read_exact', wraps=delivery._read_exact) as reads:
            iterator = delivery.iter_delivery_frames(self.capture, receipt, 1)
            self.assertEqual(next(iterator)[:32], prefix(1))
            count_before_close = reads.call_count
            iterator.close()
            self.assertEqual(reads.call_count, count_before_close)
            self.assertTrue(opened[0].closed)
            self.assertFalse(receipt['delivery_complete'])
            unopened = delivery.iter_delivery_frames(self.capture, receipt, 0)
            unopened.close()
            self.assertEqual(len(opened), 1)

    def test_corrupt_last_frame_is_rejected_before_any_receipt_is_returned(self):
        self.mutate(frame=24)
        with self.assertRaisesRegex(ValueError, 'images: summary SHA256 mismatch'):
            self.verify()

    def test_nonfinite_is_rejected_even_when_summary_hash_matches(self):
        self.mutate(name='audio_latent', word=0xff800000)
        digest = hashlib.sha256(struct.pack('<I', 0xff800000))
        zeros_into(digest, delivery.BYTE_LENGTHS['audio_latent'] - 4)
        self.report['tensors']['audio_latent']['sha256'] = digest.hexdigest()
        self.write_summary()
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            self.verify()

    def test_summary_wrong_hash_shape_dtype_names_flags_and_run_rejected(self):
        original = copy.deepcopy(self.report)
        cases = [('run_name', 'other-run'), ('deterministic_enabled', False),
                 ('deterministic_warn_only', True), ('sample_rate', 44100)]
        for key, value in cases:
            self.report = copy.deepcopy(original)
            self.report[key] = value
            self.write_summary()
            with self.subTest(key=key), self.assertRaises(ValueError): self.verify()
        for key, value in [('sha256', '0' * 64), ('shape', [1, 128, 4, 4, 16]),
                           ('dtype', 'torch.bfloat16'), ('finite', False)]:
            self.report = copy.deepcopy(original)
            self.report['tensors']['video_latent'][key] = value
            self.write_summary()
            with self.subTest(key=key), self.assertRaises(ValueError): self.verify()
        self.report = copy.deepcopy(original)
        del self.report['tensors']['waveform']
        self.write_summary()
        with self.assertRaises(ValueError): self.verify()

    def test_header_bad_dtype_shape_and_truncated_source_rejected(self):
        with self.capture.open('rb') as stream:
            raw = stream.read(self.data_start)
        for old, new in ((b'"F32"', b'"I32"'), (b'[1,8,26,16]', b'[1,8,16,26]')):
            changed = raw.replace(old, new, 1)
            self.assertNotEqual(changed, raw)
            with self.capture.open('r+b') as stream: stream.write(changed)
            with self.assertRaises(ValueError): self.verify()
            with self.capture.open('r+b') as stream: stream.write(raw)
        with self.capture.open('r+b') as stream: stream.truncate(self.capture.stat().st_size - 1)
        with self.assertRaises(ValueError): self.verify()

    def test_receipt_requires_all_verified_frame_hashes_shapes_and_dtypes(self):
        original = self.verify()
        cases = [('complete', False), ('frame_sha256', self.frame_hashes[:-1]),
                 ('frame_sha256', ['bad'] * 25), ('anchor_sha256', '0' * 64),
                 ('byte_order', 'big')]
        for key, value in cases:
            receipt = copy.deepcopy(original)
            receipt[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                next(delivery.iter_delivery_frames(self.capture, receipt, 0))
        for key, value in [('dtype', 'float16'), ('shape', [25, 128, 512, 3]), ('byte_offset', 0)]:
            receipt = copy.deepcopy(original)
            receipt['tensors']['images'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                next(delivery.iter_delivery_frames(self.capture, receipt, 0))
        for index in (-1, True, 0.0):
            with self.assertRaises(ValueError): next(delivery.iter_delivery_frames(self.capture, original, index))

    def test_mutation_after_verification_or_between_yields_fails_closed(self):
        receipt = self.verify()
        iterator = delivery.iter_delivery_frames(self.capture, receipt, 1)
        next(iterator)
        self.mutate(frame=24)
        with self.assertRaisesRegex(ValueError, 'changed'): next(iterator)
        with self.assertRaisesRegex(ValueError, 'identity'):
            next(delivery.iter_delivery_frames(self.capture, receipt, 1))

    def test_mutation_during_verification_cannot_return_partial_success(self):
        original = delivery._finite
        changed = False
        def mutate_after_scan(data, name):
            nonlocal changed
            original(data, name)
            if not changed:
                self.mutate(name='waveform')
                changed = True
        with mock.patch.object(delivery, '_finite', side_effect=mutate_after_scan):
            with self.assertRaisesRegex(ValueError, 'changed'):
                self.verify()

    def test_frame_hash_catches_bad_bytes_even_if_identity_check_is_bypassed(self):
        receipt = self.verify()
        iterator = delivery.iter_delivery_frames(self.capture, receipt, 1)
        next(iterator)
        self.mutate(frame=24)
        with mock.patch.object(delivery, '_unchanged'):
            for _ in range(22): next(iterator)
            with self.assertRaisesRegex(ValueError, 'frame24'): next(iterator)

    def test_generator_reopens_and_binds_header_not_just_receipt_ranges(self):
        receipt = self.verify()
        with self.capture.open('r+b') as stream:
            stream.seek(8)
            raw = stream.read(self.data_start - 8)
            # Same JSON data, different whitespace: correct semantic ranges but
            # a distinct header must still fail the exact header hash binding.
            self.assertTrue(raw.endswith(b' '))
            changed = raw[:-1] + b'\n'
            stream.seek(8)
            stream.write(changed)
        receipt['source_file_identity'] = delivery.anchor_io._file_identity(self.capture.stat())
        with self.assertRaisesRegex(ValueError, 'header changed'):
            next(delivery.iter_delivery_frames(self.capture, receipt, 0))

    def test_last_yield_is_not_successful_exhaustion(self):
        receipt = self.verify()
        iterator = delivery.iter_delivery_frames(self.capture, receipt, 1)
        for _ in range(24): next(iterator)
        self.mutate(frame=0)
        with self.assertRaisesRegex(ValueError, 'changed'): next(iterator)
        self.assertFalse(receipt['delivery_complete'])

    def test_no_tensor_or_runtime_imports(self):
        for name in ('torch', 'numpy', 'safetensors'):
            self.assertNotIn(name, sys.modules)
        self.assertFalse(any(name.startswith('comfy') for name in sys.modules))


if __name__ == '__main__':
    unittest.main(verbosity=2)
