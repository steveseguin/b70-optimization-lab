#!/usr/bin/env python3
"""Synthetic sparse-capture tests; no tensor/native runtime or subprocess calls."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name('continuation_anchor_io.py')
SPEC = importlib.util.spec_from_file_location('continuation_anchor_io', SCRIPT)
anchor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(anchor)
WORDS = [0x00000000, 0x80000000, 0x00000001, 0x80000001,
         0x7f7fffff, 0xff7fffff, 0x3f800000, 0xbf800000]
PAYLOAD = struct.pack('<8I', *WORDS) * (anchor.FRAME_BYTES // 32)
PAYLOAD_SHA = hashlib.sha256(PAYLOAD).hexdigest()
IMAGE_BYTES = 25 * anchor.FRAME_BYTES
DATA_BYTES = 16 + IMAGE_BYTES + 8


def header():
    return {'__metadata__': {'fixture': 'synthetic sparse CPU test'},
            'before': {'dtype': 'U8', 'shape': [16], 'data_offsets': [0, 16]},
            'images': {'dtype': 'F32', 'shape': [25, 256, 256, 3],
                       'data_offsets': [16, 16 + IMAGE_BYTES]},
            'after': {'dtype': 'I64', 'shape': [1],
                      'data_offsets': [16 + IMAGE_BYTES, DATA_BYTES]}}


class AnchorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ltx-anchor-cpu-')
        self.path = Path(self.tmp.name) / 'synthetic.safetensors'

    def tearDown(self):
        self.tmp.cleanup()

    def fixture(self, value=None, raw_header=None, data_bytes=DATA_BYTES, payload=PAYLOAD):
        if raw_header is None:
            raw_header = json.dumps(header() if value is None else value, separators=(',', ':')).encode()
            raw_header += b' ' * (-len(raw_header) % 8)
        data_start = 8 + len(raw_header)
        with self.path.open('wb') as stream:
            stream.write(struct.pack('<Q', len(raw_header)))
            stream.write(raw_header)
            stream.truncate(data_start + data_bytes)
            if payload is not None:
                stream.seek(data_start + 16 + 24 * anchor.FRAME_BYTES)
                stream.write(payload)
        return data_start

    def test_extracts_only_frame24_from_nonzero_tensor_offset_exactly(self):
        data_start = self.fixture()
        sizes = []
        original = anchor._read_exact
        def tracking(stream, size):
            sizes.append(size)
            return original(stream, size)
        with mock.patch.object(anchor, '_read_exact', side_effect=tracking):
            payload, metadata = anchor.extract_anchor(self.path)
        self.assertEqual(payload, PAYLOAD)
        self.assertEqual(metadata['sha256'], PAYLOAD_SHA)
        self.assertEqual(metadata['source_byte_offset'], data_start + 16 + 24 * anchor.FRAME_BYTES)
        self.assertEqual(sizes, [8, data_start - 8, anchor.FRAME_BYTES])
        self.assertEqual(metadata['bytes_read'], sum(sizes))
        self.assertLess(sum(sizes), anchor.FRAME_BYTES + 4096)
        self.assertEqual(metadata['shape'], [1, 256, 256, 3])
        self.assertEqual(metadata['source_shape'], [25, 256, 256, 3])
        self.assertEqual(metadata['frame_index'], 24)
        self.assertFalse(metadata['whole_capture_hash_verified'])
        self.assertFalse(metadata['other_frames_finite_verified'])

    def test_preserves_signed_zero_subnormal_max_finite_and_outside_unit_interval(self):
        metadata = anchor.validate_anchor_bytes(PAYLOAD, PAYLOAD_SHA)
        self.assertTrue(metadata['finite'])
        self.assertEqual(metadata['transformation'], 'none')
        self.assertEqual(metadata['byte_order'], 'little')
        self.assertEqual(struct.unpack('<8I', PAYLOAD[:32]), tuple(WORDS))
        positive_zero = bytes(anchor.FRAME_BYTES)
        negative_zero = struct.pack('<I', 0x80000000) * (anchor.FRAME_BYTES // 4)
        self.assertNotEqual(anchor.validate_anchor_bytes(positive_zero, hashlib.sha256(positive_zero).hexdigest())['sha256'],
                            anchor.validate_anchor_bytes(negative_zero, hashlib.sha256(negative_zero).hexdigest())['sha256'])

    def test_nonfinite_exponent_bits_rejected_at_first_and_last_samples(self):
        for word in (0x7f800000, 0xff800000, 0x7fc00000, 0x7f800001, 0xffa00001):
            for index in (0, anchor.FRAME_BYTES - 4):
                payload = PAYLOAD[:index] + struct.pack('<I', word) + PAYLOAD[index + 4:]
                with self.subTest(word=hex(word), index=index), self.assertRaisesRegex(ValueError, 'nonfinite'):
                    anchor.validate_anchor_bytes(payload, hashlib.sha256(payload).hexdigest())

    def test_extract_rejects_nonfinite_anchor_but_does_not_inspect_other_frames(self):
        data_start = self.fixture()
        with self.path.open('r+b') as stream:
            stream.seek(data_start + 16)
            stream.write(struct.pack('<I', 0x7f800000))
        self.assertEqual(anchor.extract_anchor(self.path)[0], PAYLOAD)
        self.fixture(payload=struct.pack('<I', 0x7fc00000) + PAYLOAD[4:])
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            anchor.extract_anchor(self.path)

    def test_raw_payload_length_type_hash_syntax_and_hash_mismatch(self):
        for payload in (PAYLOAD[:-1], PAYLOAD + b'\0', b'', bytearray(PAYLOAD), memoryview(PAYLOAD), None):
            with self.subTest(type=type(payload).__name__), self.assertRaises(ValueError):
                anchor.validate_anchor_bytes(payload, PAYLOAD_SHA)
        for digest in ('0' * 64, PAYLOAD_SHA.upper(), PAYLOAD_SHA[:-1], 'z' * 64, None, 123):
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                anchor.validate_anchor_bytes(PAYLOAD, digest)

    def test_bounded_header_length_and_truncation(self):
        for raw in (b'', b'1234567', struct.pack('<Q', 1) + b'{}',
                    struct.pack('<Q', anchor.MAX_HEADER_BYTES + 1) + b'{}',
                    struct.pack('<Q', 1000) + b'{}'):
            self.path.write_bytes(raw)
            with self.subTest(raw=raw[:8]), self.assertRaises(ValueError):
                anchor.extract_anchor(self.path)
        self.fixture()
        with self.path.open('r+b') as stream:
            stream.truncate(self.path.stat().st_size - 1)
        with self.assertRaises(ValueError):
            anchor.extract_anchor(self.path)

    def test_duplicate_json_keys_invalid_utf8_and_nonstandard_json(self):
        for raw in (b'{"images":{},"images":{}}', b'{"x":{"dtype":"F32","dtype":"I32"}}',
                    b'{"__metadata__":{"x":"1","x":"2"}}', b'{"x":NaN}',
                    b'{"x":Infinity}', b'{"x":"\xff"}', b'[]', b' {}', b'{}junk'):
            self.fixture(raw_header=raw, data_bytes=0, payload=None)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                anchor.extract_anchor(self.path)

    def test_strict_images_dtype_shape_and_descriptor_fields(self):
        changes = [('dtype', 'I32'), ('dtype', 'F16'), ('dtype', 'UNKNOWN'),
                   ('shape', [25, 256, 768]), ('shape', [24, 256, 256, 3]),
                   ('shape', [25, 256, 256, True]), ('shape', [25.0, 256, 256, 3]),
                   ('shape', [25, -256, 256, 3]), ('shape', '25,256,256,3')]
        for field, value in changes:
            desc = header()
            desc['images'][field] = value
            self.fixture(desc)
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                anchor.extract_anchor(self.path)
        for action in ('missing', 'extra', 'wrong_descriptor', 'missing_images', 'bad_metadata'):
            desc = header()
            if action == 'missing': del desc['images']['dtype']
            elif action == 'extra': desc['images']['extra'] = 1
            elif action == 'wrong_descriptor': desc['images'] = []
            elif action == 'missing_images': del desc['images']
            else: desc['__metadata__']['fixture'] = 1
            self.fixture(desc)
            with self.subTest(action=action), self.assertRaises(ValueError):
                anchor.extract_anchor(self.path)

    def test_all_tensor_ranges_reject_overlap_holes_and_unindexed_bytes(self):
        for offsets in ([-1, IMAGE_BYTES - 1], [16, 15], [16, 17 + IMAGE_BYTES],
                        [True, 16 + IMAGE_BYTES], [16.0, 16 + IMAGE_BYTES], [16],
                        [17, 17 + IMAGE_BYTES], [15, 15 + IMAGE_BYTES],
                        [16, 2**64]):
            desc = header()
            desc['images']['data_offsets'] = offsets
            self.fixture(desc)
            with self.subTest(offsets=offsets), self.assertRaises(ValueError):
                anchor.extract_anchor(self.path)
        desc = header()
        desc['before']['data_offsets'] = [1, 17]
        self.fixture(desc)
        with self.assertRaisesRegex(ValueError, 'gap'):
            anchor.extract_anchor(self.path)
        desc = header()
        desc['after']['shape'] = [2]
        self.fixture(desc)
        with self.assertRaisesRegex(ValueError, 'byte count'):
            anchor.extract_anchor(self.path)
        self.fixture(data_bytes=DATA_BYTES + 1)
        with self.assertRaisesRegex(ValueError, 'trailing'):
            anchor.extract_anchor(self.path)

    def test_sparse_file_with_zero_size_metadata_tensor_is_supported(self):
        desc = header()
        desc['empty'] = {'dtype': 'F32', 'shape': [0], 'data_offsets': [16, 16]}
        self.fixture(desc)
        self.assertEqual(anchor.extract_anchor(self.path)[0], PAYLOAD)

    def test_changed_file_identity_and_short_frame_read_fail_closed(self):
        self.fixture()
        before = self.path.stat()
        altered = SimpleNamespace(**{name: getattr(before, name) for name in
            ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode')})
        altered.st_mtime_ns += 1
        with mock.patch.object(anchor.os, 'fstat', side_effect=[before, altered]):
            with self.assertRaisesRegex(ValueError, 'changed'):
                anchor.extract_anchor(self.path)
        original = anchor._read_exact
        def truncate_at_frame(stream, length):
            if length == anchor.FRAME_BYTES:
                with self.path.open('r+b') as writable:
                    writable.truncate(stream.tell() + length - 1)
            return original(stream, length)
        with mock.patch.object(anchor, '_read_exact', side_effect=truncate_at_frame):
            with self.assertRaisesRegex(ValueError, 'truncated'):
                anchor.extract_anchor(self.path)

    def test_no_runtime_imports(self):
        self.assertNotIn('torch', sys.modules)
        self.assertNotIn('numpy', sys.modules)
        self.assertNotIn('safetensors', sys.modules)
        self.assertFalse(any(name.startswith('comfy') for name in sys.modules))

    def test_rejects_nonregular_file_without_waiting_for_writer(self):
        anchor.os.mkfifo(self.path)
        with mock.patch.object(anchor.os, 'close', wraps=anchor.os.close) as close:
            with self.assertRaisesRegex(ValueError, 'regular file'):
                anchor.extract_anchor(self.path)
            self.assertEqual(close.call_count, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
