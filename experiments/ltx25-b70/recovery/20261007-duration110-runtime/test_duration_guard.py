"""CPU-only source/metadata controls; fake tensors, no Torch or GPU imports."""
import ast
import ctypes
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('duration_guard_tested', HERE / 'duration_guard.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
PARENT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99b')
CAPTURE = PARENT / 'source/scripts/capture_node.py'
GEOMETRY = PARENT / 'source/scripts/ltx_output_size_98.py'
SERIALIZER = Path('/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/safetensors')


class Tensor:
    dtype, device, layout = 'torch.float32', 'cpu', 'torch.strided'
    def __init__(self, shape):
        self.shape = tuple(shape)
        self.finite = self.contiguous = True
    def is_contiguous(self): return self.contiguous
    def element_size(self): return 4
    def numel(self): return math.prod(self.shape)


def tensors(shapes):
    return {k: Tensor(v) for k, v in shapes.items()}


def report(ts, name):
    return {'run_name': name, 'sample_rate': 48000,
            'tensors': {k: {'shape': list(t.shape), 'dtype': t.dtype, 'finite': t.finite,
                            'sha256': 'e' * 64, 'min': 0., 'max': 1., 'std': .1} for k, t in ts.items()}}


class Tests(unittest.TestCase):
    def setUp(self):
        roles = ['full'] * 20 + ['setup'] * 2 + ['fill'] * 4 + ['full'] * 10 + ['fill'] * 4 + ['full'] * 10
        self.rows = [{'name': 'capture-%02d' % i, 'role': role, 'graph_sha256': hashlib.sha256(str(i).encode()).hexdigest()}
                     for i, role in enumerate(roles)]
        self.active = {}
        self.guard = d.CaptureGuard('a' * 64, self.rows, lambda: dict(self.active))
    def bind(self, i):
        row = self.rows[i]
        self.active = {'name': row['name'], 'prompt_id': 'prompt-%d' % i,
                       'graph_sha256': row['graph_sha256'], 'plan_sha256': 'a' * 64}
        return row['name']
    def call(self, i, shapes=None):
        name = self.bind(i)
        shapes = shapes or (d.FULL_SHAPES if self.rows[i]['role'] == 'full' else d.FILL_SHAPES)
        ts = tensors(shapes)
        return self.guard.validate(ts, report(ts, name), name)
    def advance(self, n):
        for i in range(n): self.call(i)

    def test_exact50_capture_budget_and_fill_bound(self):
        for i in range(50):
            evidence = self.call(i)
            if self.rows[i]['role'] != 'full':
                self.assertLessEqual(evidence['file_bound'], 1024**2)
            if self.rows[i]['role'] == 'setup':
                self.assertEqual(evidence['charged_bytes'], d.FULL_FILE_BOUND)
        final = self.guard.receipt()
        self.assertEqual(final['captures_reserved'], 50)
        self.assertEqual(final['reserved_bytes'], 42 * 146230536 + 8 * 1024**2)
        overhead = 1024**3 + 512*1024**2 + 192*1024**2
        self.assertLess(final['reserved_bytes'] + overhead, d.WRITE_ALLOWANCE)
        self.assertIsNone(final['failed'])
        json.dumps(final, allow_nan=False)

    def test_setup_full_and_stage_a_fill_both_allowed_but_charged_full(self):
        self.advance(20)
        e = self.call(20, d.FULL_SHAPES)
        self.assertEqual(e['charged_bytes'], d.FULL_FILE_BOUND)
        e = self.call(21, {**d.FILL_SHAPES, 'video_latent': d.STAGE_A})
        self.assertEqual(e['charged_bytes'], d.FULL_FILE_BOUND)
        self.assertEqual(e['actual_shape_kind'], 'fill')

    def test_role_cannot_be_supplied_by_filename_or_active_callback(self):
        name = self.bind(0)
        self.active['role'] = 'fill'
        ts = tensors(d.FILL_SHAPES)
        with self.assertRaisesRegex(d.GuardError, 'role/shape'):
            self.guard.validate(ts, report(ts, name), name)
        self.assertEqual(self.guard.receipt()['captures_reserved'], 0)

    def test_full_output_on_fill_row_refused_before_charge(self):
        self.advance(22)
        with self.assertRaisesRegex(d.GuardError, 'role/shape'):
            self.call(22, d.FULL_SHAPES)
        self.assertEqual(self.guard.receipt()['captures_reserved'], 22)

    def test_individually_valid_fields_cannot_form_mixed_tuple(self):
        with self.assertRaisesRegex(d.GuardError, 'role/shape'):
            self.call(0, {**d.FULL_SHAPES, 'waveform': d.FILL_SHAPES['waveform']})

    def test_nonfinite_and_wrong_dtype_rejected_without_conversion(self):
        for mutate in ('finite', 'dtype', 'report_dtype', 'stat_nan', 'shape', 'sample_rate', 'keys', 'layout', 'device', 'contiguous'):
            with self.subTest(mutate=mutate):
                self.setUp()
                name = self.bind(0)
                ts = tensors(d.FULL_SHAPES)
                r = report(ts, name)
                if mutate == 'finite': r['tensors']['images']['finite'] = False
                if mutate == 'dtype': ts['images'].dtype = 'torch.bfloat16'
                if mutate == 'report_dtype': r['tensors']['images']['dtype'] = 'torch.float64'
                if mutate == 'stat_nan': r['tensors']['images']['std'] = float('nan')
                if mutate == 'shape': ts['audio_latent'].shape = (1, 8, 26, 16)
                if mutate == 'sample_rate': r['sample_rate'] = 16000
                if mutate == 'keys': ts['extra'] = Tensor((1,))
                if mutate == 'layout': ts['images'].layout = 'torch.sparse_coo'
                if mutate == 'device': ts['images'].device = 'xpu:0'
                if mutate == 'contiguous': ts['images'].contiguous = False
                with self.assertRaises(d.GuardError): self.guard.validate(ts, r, name)
                self.assertEqual(self.guard.receipt()['captures_reserved'], 0)
                self.assertIsNotNone(self.guard.receipt()['failed'])

    def test_authority_plan_graph_prompt_and_order_bound(self):
        for field in ('name', 'graph_sha256', 'plan_sha256', 'prompt_id'):
            with self.subTest(field=field):
                self.setUp()
                name = self.bind(0)
                self.active[field] = ''
                ts = tensors(d.FULL_SHAPES)
                with self.assertRaises(d.GuardError): self.guard.validate(ts, report(ts, name), name)
        self.setUp()
        with self.assertRaises(d.GuardError): self.call(1)

    def test_authority_change_during_validation_refused(self):
        name = self.bind(0)
        ts = tensors(d.FULL_SHAPES)
        calls = []
        def active():
            calls.append(1)
            return {**self.active, 'prompt_id': 'changed' if len(calls) > 1 else 'original'}
        self.guard.active_request = active
        with self.assertRaisesRegex(d.GuardError, 'changed during'):
            self.guard.validate(ts, report(ts, name), name)

    def test_no_retry_or_refund_and_callback_error_propagates(self):
        self.call(0)
        with self.assertRaises(d.GuardError): self.call(0)
        self.assertEqual(self.guard.receipt()['reserved_bytes'], d.FULL_FILE_BOUND)
        with self.assertRaisesRegex(d.GuardError, 'already failed'): self.call(1)
        self.setUp()
        error = RuntimeError('original authority failure')
        def broken(): raise error
        self.guard.active_request = broken
        with self.assertRaises(RuntimeError) as caught: self.call(0)
        self.assertIs(caught.exception, error)

    def test_fifty_first_registered_capture_refused_before_any_tensor_or_write(self):
        extra = dict(self.rows[-1], name='unregistered-fifty-first', graph_sha256='f'*64)
        with self.assertRaisesRegex(d.GuardError, 'Exactly50'):
            d.CaptureGuard('a'*64, self.rows + [extra], lambda: {})

    def test_entire_placeholder_bound_includes_header(self):
        self.assertEqual(sum(math.prod(s) * 4 for s in d.FULL_SHAPES.values()), 146164992)
        self.assertEqual(sum(math.prod(s) * 4 for s in d.FILL_SHAPES.values()) + d.HEADER_BOUND, 952648)
        self.assertLess(d.header_size_bound(d.FULL_SHAPES), 1024)

    def test_geometry_transform_has_new_shape_contract_and_no_old_oracle(self):
        raw = GEOMETRY.read_bytes()
        out = d.transform_geometry(raw)
        ns = {}
        with patch.dict(os.environ, {'LTX_OUTPUT_SIZE': '640x384'}): exec(compile(out, '<geometry>', 'exec'), ns)
        self.assertEqual(ns['TOKENS'], (420, 1680))
        self.assertEqual(ns['latent_shape'](1), d.STAGE_A)
        self.assertEqual(ns['latent_shape'](2), d.FULL_SHAPES['video_latent'])
        self.assertEqual(ns['image_shape'](), d.FULL_SHAPES['images'])
        self.assertEqual((ns['AUDIO_LATENTS'], ns['AUDIO_SAMPLES']), (51, 96480))
        with self.assertRaises(RuntimeError): ns['require_reference_size']()
        self.assertIn("'frame_count': FRAMES", out.decode())
        self.assertIn("'audio_latent_shape': list(a.shape)", out.decode())
        with patch.dict(os.environ, {'LTX_OUTPUT_SIZE': '256x256'}):
            with self.assertRaises(RuntimeError): exec(compile(out, '<geometry>', 'exec'), {})
        with self.assertRaises(d.GuardError): d.transform_geometry(raw + b'\n')

    def test_capture_source_all_three_mirrors_and_exact_pins(self):
        raw = CAPTURE.read_bytes()
        results = [d.transform_capture(path, raw) for path in d.CAPTURE_PATHS]
        self.assertTrue(all(out == results[0] for out in results))
        with self.assertRaises(d.GuardError): d.transform_capture('unregistered.py', raw)
        with self.assertRaises(d.GuardError): d.transform_capture(d.CAPTURE_PATHS[0], raw + b'\n')
        tree = ast.parse(results[0])
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'capture')
        statements = [ast.unparse(n) for n in method.body]
        guard_index = next(i for i, s in enumerate(statements) if 'require_capture_prewrite' in s)
        mkdir_index = next(i for i, s in enumerate(statements) if s.startswith('out.mkdir('))
        save_index = next(i for i, s in enumerate(statements) if s.startswith('save_file('))
        self.assertLess(guard_index, mkdir_index)
        self.assertLess(mkdir_index, save_index)
        original = next(n for n in ast.walk(ast.parse(raw)) if isinstance(n, ast.FunctionDef) and n.name == 'capture')
        old_loop = next(n for n in original.body if isinstance(n, ast.For))
        new_loop = next(n for n in method.body if isinstance(n, ast.For))
        self.assertEqual(ast.dump(old_loop), ast.dump(new_loop))

    def test_transformed_writer_refuses_before_directory_or_save(self):
        # Execute only the transformed method, with fake original tensor ops.
        tree = ast.parse(d.transform_capture(d.CAPTURE_PATHS[0], CAPTURE.read_bytes()))
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'capture')
        class Fake(Tensor):
            def detach(self): return self
            def cpu(self): return self
            def contiguous(self): return self
            def view(self, _): return self
            def numpy(self): return self
            def tobytes(self): return b'fake-payload'
            def min(self): return 0.
            def max(self): return 1.
            def float(self): return self
            def std(self): return .1
        class Finite:
            def __init__(self, value): self.value = value
            def all(self): return self.value
        # Tensor's metadata .contiguous attribute shadows the fake method; use
        # an explicit alternate bool for this instrumented original writer.
        Fake.__init__ = lambda self, shape: setattr(self, 'shape', tuple(shape))
        Fake.is_contiguous = lambda self: True
        Fake.finite = True
        fake_torch = types.SimpleNamespace(uint8='uint8', isfinite=lambda tensor: Finite(tensor.finite),
                     are_deterministic_algorithms_enabled=lambda: True,
                     is_deterministic_algorithms_warn_only_enabled=lambda: False)
        for mode in ('wrong-dtype', 'nonfinite', 'accepted'):
            self.setUp()
            name = self.bind(0)
            ts = {k: Fake(shape) for k, shape in d.FULL_SHAPES.items()}
            if mode == 'wrong-dtype': ts['images'].dtype = 'torch.bfloat16'
            if mode == 'nonfinite': ts['images'].finite = False
            calls = []
            with tempfile.TemporaryDirectory() as tmp:
                env = {'Path': Path, 'folder_paths': types.SimpleNamespace(get_output_directory=lambda: tmp),
                       'torch': fake_torch, 'hashlib': hashlib, 'json': json,
                       'save_file': lambda *args: calls.append(args),
                       'ltx_duration_guard': types.SimpleNamespace(require_capture_prewrite=self.guard.validate)}
                exec(compile(ast.Module(body=[method], type_ignores=[]), '<capture>', 'exec'), env)
                args = (None, ts['images'], {'samples': ts['video_latent']}, {'samples': ts['audio_latent']},
                        {'waveform': ts['waveform'], 'sample_rate': 48000}, name)
                if mode == 'accepted':
                    env['capture'](*args)
                    self.assertEqual(len(calls), 1)
                    self.assertTrue((Path(tmp) / 'validation' / name / 'summary.json').exists())
                else:
                    with self.assertRaises(d.GuardError): env['capture'](*args)
                    self.assertEqual(calls, [])
                    self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_pinned_actual_serializer_header_without_torch(self):
        sources = {name: (SERIALIZER / name).read_bytes() for name in d.SERIALIZER_SHA256}
        self.assertEqual(d.serializer_binding(sources), d.SERIALIZER_SHA256)
        with self.assertRaises(d.GuardError): d.serializer_binding({**sources, 'torch.py': sources['torch.py'] + b'\n'})
        # Four tiny F32 payloads exercise the installed Rust header serializer;
        # no tensor library, model data, file output or large allocation.
        sys.path.insert(0, str(SERIALIZER.parent))
        try:
            import safetensors
            buffers = {name: ctypes.create_string_buffer(4) for name in d.FULL_SHAPES}
            tiny = {name: safetensors.TensorSpec(dtype='float32', shape=[1],
                    data_ptr=ctypes.addressof(buffer), data_len=4) for name, buffer in buffers.items()}
            raw = safetensors.serialize(tiny)
        finally:
            sys.path.pop(0)
        length = struct.unpack('<Q', raw[:8])[0]
        header = json.loads(raw[8:8 + length])
        self.assertEqual(set(header), set(d.FULL_SHAPES))
        self.assertTrue(all(set(row) == {'dtype', 'shape', 'data_offsets'} for row in header.values()))
        self.assertEqual(length % 8, 0)
        self.assertLessEqual(8 + length, d.header_size_bound({k: (1,) for k in d.FULL_SHAPES}))
        self.assertNotIn('torch', sys.modules)

    def test_missing_configuration_refuses_prewrite(self):
        with patch.object(d, '_guard', None):
            with self.assertRaisesRegex(d.GuardError, 'not configured'):
                d.require_capture_prewrite({}, {}, 'capture-00')

    def test_no_slot_or_byte_budget_extension(self):
        self.advance(50)
        with self.assertRaisesRegex(d.GuardError, 'allowance exhausted'):
            self.call(49)
        self.assertEqual(self.guard.receipt()['captures_reserved'], 50)
        self.setUp()
        with patch.object(d, 'RAW_CAPTURE_BUDGET', d.FULL_FILE_BOUND - 1):
            with self.assertRaisesRegex(d.GuardError, 'byte allowance'):
                self.call(0)
        self.assertEqual(self.guard.receipt()['captures_reserved'], 0)


if __name__ == '__main__': unittest.main()
