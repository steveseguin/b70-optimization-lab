#!/usr/bin/env python3
"""Synthetic contract checks for the inactive, stdlib-only exact comparer."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('stream_compare', SCRIPTS / 'compare-clip-streaming.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.make('a')
        self.make('b')

    def write(self, path, value):
        path.write_text(json.dumps(value, indent=2) + '\n')

    def mutate(self, relative, change):
        path = self.root / relative
        value = json.loads(path.read_text())
        change(value)
        self.write(path, value)

    def make(self, name, words=None, shape=None):
        words = [0x3f800000, 0, 1, 0xbf800000] if words is None else words
        shape = [len(words)] if shape is None else shape
        folder = self.root / 'output/validation' / name
        folder.mkdir(parents=True, exist_ok=True)
        payload = struct.pack('<' + 'I' * len(words), *words)
        header, summaries, pieces = {}, {}, []
        offset = 0
        for key in sorted(c.KEYS):
            header[key] = {'dtype': 'F32', 'shape': shape,
                           'data_offsets': [offset, offset + len(payload)]}
            summaries[key] = {'dtype': 'torch.float32', 'shape': shape,
                              'finite': True, 'sha256': hashlib.sha256(payload).hexdigest()}
            offset += len(payload)
            pieces.append(payload)
        raw = json.dumps(header).encode()
        (folder / 'tensors.safetensors').write_bytes(struct.pack('<Q', len(raw)) + raw + b''.join(pieces))
        self.write(folder / 'summary.json', {'deterministic_enabled': True,
                   'deterministic_warn_only': False, 'sample_rate': 48000, 'tensors': summaries})
        request = self.root / 'requests' / name
        request.mkdir(parents=True, exist_ok=True)
        prompt = {'1': {'class_type': 'Example', 'inputs': {'seed': 42}}}
        for key, value in {'prompt': prompt, 'submission': {'prompt_id': name},
                           'result': {'prompt_id': name, 'seconds': 1.2},
                           'identity': {'model_verification_sha256': 'a' * 64, 'pid': name},
                           'history': {'prompt': [0, name, prompt],
                                       'status': {'status_str': 'success', 'messages': []}}}.items():
            self.write(request / (key + '.json'), value)

    def compare(self, **kwargs):
        return c.compare_runs(self.root, 'a', 'b', **kwargs)

    def test_exact_distinct_execution_and_original_prompt_bytes(self):
        report = self.compare()
        self.assertEqual(report['status'], 'passed')
        self.assertTrue(report['eligible_for_live_gate'])
        self.assertEqual(set(report['comparisons']), c.KEYS)
        self.assertTrue(all(row['bitwise_equal'] for row in report['comparisons'].values()))
        self.assertEqual(report['executions'][0]['prompt_sha256'],
                         hashlib.sha256((self.root / 'requests/a/prompt.json').read_bytes()).hexdigest())
        self.assertNotEqual(report['executions'][0]['server_identity']['pid'],
                            report['executions'][1]['server_identity']['pid'])

    def test_signed_zero_fails_bytes_but_not_numeric_diagnostics(self):
        self.make('b', [0x3f800000, 0x80000000, 1, 0xbf800000])
        report = self.compare()
        self.assertEqual(report['status'], 'failed')
        for row in report['comparisons'].values():
            self.assertEqual((row['unequal_values'], row['max_abs_diff']), (0, 0))
            self.assertEqual(row['unequal_f32_bit_patterns'], 1)
            self.assertEqual(row['first_unequal_sample'], 1)

    def test_finite_opposite_extrema_overflow_diagnostic(self):
        self.make('a', [0x7f7fffff])
        self.make('b', [0xff7fffff])
        row = self.compare()['comparisons']['images']
        self.assertEqual(row['max_abs_diff_f32_bits'], '0x7f800000')
        self.assertEqual(row['unequal_values'], 1)

    def test_shape_mismatch_is_failed_report(self):
        self.make('b', shape=[2, 2])
        report = self.compare()
        self.assertEqual(report['status'], 'failed')
        self.assertTrue(all(row == {'bitwise_equal': False, 'same_layout': False}
                            for row in report['comparisons'].values()))

    def test_fault_and_offline_status(self):
        (self.root / 'FAULT.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'fault'):
            self.compare()
        report = self.compare(offline_evidence=True)
        self.assertEqual(report['status'], 'passed-offline-evidence')
        self.assertFalse(report['eligible_for_live_gate'])

    def test_fault_appearing_during_comparison(self):
        original = c.compare_archives
        def fault(*args):
            result = original(*args)
            (self.root / 'FAULT.json').write_text('{}')
            return result
        with patch.object(c, 'compare_archives', fault), self.assertRaisesRegex(ValueError, 'during comparison'):
            self.compare()

    def test_execution_identity_gates(self):
        cases = [('submission', lambda x: x.update(prompt_id='wrong')),
                 ('result', lambda x: x.update(prompt_id='wrong')),
                 ('prompt', lambda x: x.update(extra=1)),
                 ('history', lambda x: x['status'].update(status_str='error')),
                 ('history', lambda x: x['status'].update(messages=[['execution_cached', {'nodes': ['1']}]])),
                 ('identity', lambda x: x.update(model_verification_sha256='b' * 64))]
        for filename, change in cases:
            with self.subTest(filename=filename):
                self.make('b')
                self.mutate('requests/b/' + filename + '.json', change)
                with self.assertRaises(ValueError):
                    self.compare()
        self.make('b')
        with self.assertRaisesRegex(ValueError, 'distinct'):
            c.compare_runs(self.root, 'a', 'a')

    def test_summary_gates(self):
        cases = [lambda x: x.update(sample_rate=44100),
                 lambda x: x.update(deterministic_enabled=1),
                 lambda x: x.update(deterministic_warn_only=True),
                 lambda x: x['tensors']['images'].update(finite=False),
                 lambda x: x['tensors']['images'].update(sha256='0' * 64),
                 lambda x: x['tensors']['images'].update(shape=[2, 2]),
                 lambda x: x['tensors'].pop('waveform')]
        for index, change in enumerate(cases):
            with self.subTest(index=index):
                self.make('b')
                self.mutate('output/validation/b/summary.json', change)
                with self.assertRaises(ValueError):
                    self.compare()

    def test_nonfinite_raw_even_with_matching_hash(self):
        for word in (0x7f800000, 0xff800000, 0x7fc00001):
            with self.subTest(word=word):
                self.make('b', [word])
                with self.assertRaisesRegex(ValueError, 'nonfinite'):
                    self.compare()

    def test_json_restrictions_and_size(self):
        path = self.root / 'requests/b/result.json'
        for raw in ('{"seconds": 1, "seconds": 2}', '{"std": NaN}', '{"std": Infinity}',
                    ' ' * (c.MAX_JSON_BYTES + 1)):
            with self.subTest(raw=raw[:40]):
                path.write_text(raw)
                with self.assertRaises(ValueError):
                    c.read_json(path)

    def test_truncated_and_trailing_archive(self):
        path = self.root / 'output/validation/b/tensors.safetensors'
        for transform in (lambda b: b[:-1], lambda b: b + b'xxxx', lambda b: b[:7]):
            self.make('b')
            path.write_bytes(transform(path.read_bytes()))
            with self.assertRaises(ValueError):
                self.compare()

    def test_archive_changed_after_verification(self):
        _, a = c.execution(self.root, 'a')
        _, b = c.execution(self.root, 'b')
        path = Path(b['path'])
        path.write_bytes(path.read_bytes() + b'xxxx')
        with self.assertRaisesRegex(ValueError, 'changed after verification'):
            c.compare_archives(a, b)

    def test_malformed_tensor_descriptors(self):
        path = self.root / 'output/validation/b/tensors.safetensors'
        changes = [lambda h: h['images'].update(data_offsets=[0, 16]),
                   lambda h: h['images'].update(data_offsets=[20, 36]),
                   lambda h: h['images'].update(dtype='BF16'),
                   lambda h: h['images'].update(shape=[3]),
                   lambda h: h['images'].update(shape=[1] * 17),
                   lambda h: h['images'].update(shape=[0], data_offsets=[16, 16]),
                   lambda h: h['images'].update(shape=[True, 4]),
                   lambda h: h.pop('waveform')]
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                self.make('b')
                raw = path.read_bytes()
                size = struct.unpack('<Q', raw[:8])[0]
                header = json.loads(raw[8:8 + size])
                change(header)
                new = json.dumps(header).encode()
                path.write_bytes(struct.pack('<Q', len(new)) + new + raw[8 + size:])
                with self.assertRaises(ValueError):
                    self.compare()

    def test_multiblock_read_bound_and_boundary_mismatch(self):
        words = [0] * (c.READ_BYTES // 4 + 3)
        self.make('a', words)
        words[c.READ_BYTES // 4] = 1
        self.make('b', words)
        sizes = []
        original = c._read_exact
        def read(stream, size):
            sizes.append(size)
            return original(stream, size)
        with patch.object(c, '_read_exact', read):
            report = self.compare()
        self.assertLessEqual(max(sizes), c.READ_BYTES)
        self.assertEqual(report['comparisons']['images']['first_unequal_sample'], c.READ_BYTES // 4)
        self.assertEqual(report['comparisons']['images']['max_abs_diff_f32_bits'], '0x00000001')

    def test_existing_output_is_preserved(self):
        path = self.root / 'report.json'
        path.write_text('protected')
        with patch.object(sys, 'argv', ['compare', 'a', 'b', '--output', str(path)]), \
                self.assertRaisesRegex(ValueError, 'already exists'):
            c.main()
        self.assertEqual(path.read_text(), 'protected')


def main():
    output = Path(sys.argv[1])
    if output.exists():
        raise FileExistsError(output)
    transcript = io.StringIO()
    result = unittest.TextTestRunner(stream=transcript, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(CompareTests))
    sources = ('compare-clip-streaming.py', 'test-compare-clip-streaming.py', 'f32_difference.py',
               'finite_f32_bits.py', 'continuation_delivery.py', 'continuation_anchor_io.py')
    receipt = {'status': 'passed' if result.wasSuccessful() else 'failed',
               'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
               'source_sha256': {name: hashlib.sha256((SCRIPTS / name).read_bytes()).hexdigest() for name in sources},
               'torch_imported': 'torch' in sys.modules, 'live_qualification': False,
               'transcript': transcript.getvalue(), 'python': sys.version}
    with output.open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    print(transcript.getvalue(), end='')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
