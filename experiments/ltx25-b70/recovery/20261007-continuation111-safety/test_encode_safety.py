"""Execute actual VAE.encode AST using fake tensors; no Torch/device imports."""
import ast
from contextlib import nullcontext
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

import encode_safety as S

SOURCE = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-duration-full-110/source/comfy/sd.py')
OLD_TEST = Path(__file__).resolve().parent.parent / '20261007-duration110-runtime/test_native_safety.py'
spec = importlib.util.spec_from_file_location('inherited_safety_controls', OLD_TEST)
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)


class Tensor:
    shape = (1, 3, 1, 384, 640)
    ndim = 5
    def __getitem__(self, key): return self
    def __setitem__(self, key, value): pass
    def to(self, *args, **kwargs): return self
    def movedim(self, *args): return self


def fixture(transformed=True, failure=None, load_failure=None, chunked=False):
    raw = SOURCE.read_bytes()
    tree = ast.parse(S.transform_sd(raw) if transformed else raw)
    vae = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'VAE')
    fn = next(n for n in vae.body if isinstance(n, ast.FunctionDef) and n.name == 'encode')
    events = []
    def classify(exc):
        events.append('classify')
        if not isinstance(exc, T.OOM): raise exc
    def load(*args, **kwargs):
        events.append('load')
        if load_failure is not None: raise load_failure
    mm = NS(cuda_device_context=lambda _: nullcontext(), load_models_gpu=load,
            raise_non_oom=classify, soft_empty_cache=lambda: events.append('flush'))
    env = {'model_management': mm, 'comfy': NS(model_management=mm),
           'torch': NS(empty=lambda *a, **kw: Tensor()),
           'logging': NS(warning=lambda *a: events.append('warning'))}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SOURCE), 'exec'), env)
    def native(*args, **kwargs):
        events.append('native-chunked' if kwargs else 'native')
        if failure is not None: raise failure
        return Tensor()
    obj = NS(throw_exception_if_invalid=lambda: None, vae_encode_crop_pixels=lambda x: x,
             latent_dim=3, not_video=False, device='xpu:3', vae_dtype='bf16',
             memory_used_encode=lambda *a: 1, patcher=NS(get_free_memory=lambda _: 2),
             disable_offload=True, process_input=lambda x: x,
             first_stage_model=NS(encode=native, comfy_has_chunked_io=chunked),
             output_device='cpu', vae_output_dtype=lambda: 'fp32', handles_tiling=True,
             format_encoded=None,
             _encode_tiled_owned=lambda *a, **kw: events.append('tile') or Tensor())
    return obj, lambda: env['encode'](obj, Tensor()), events


class Controls(unittest.TestCase):
    def test_source_drift_and_double_transform_refused(self):
        raw = SOURCE.read_bytes()
        for value in (raw + b'\n', S.transform_sd(raw), None):
            with self.assertRaises(ValueError): S.transform_sd(value)

    def test_success_path_identical_and_decode_unchanged(self):
        for chunked in (False, True):
            a, ra, ea = fixture(False, chunked=chunked)
            b, rb, eb = fixture(True, chunked=chunked)
            ctl, _, _ = T.controller(b)
            out = ra()
            with ctl.request('one'): self.assertIs(type(out), type(rb()))
            self.assertEqual(ea, eb)
        def vae_decode(raw):
            tree = ast.parse(raw)
            cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'VAE')
            fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'decode')
            return b''.join(raw.splitlines(keepends=True)[fn.lineno-1:fn.end_lineno])
        raw = SOURCE.read_bytes()
        before = vae_decode(raw)
        self.assertGreater(len(before), 1000)
        self.assertIn(b'_ltx_native_reference_safety.reject_oom', before)
        self.assertEqual(before, vae_decode(S.transform_sd(raw)))

    def test_encode_or_load_oom_latches_before_warning_flush_or_tile(self):
        for kwargs in ({'failure': T.OOM('encode')}, {'load_failure': T.OOM('load')},
                       {'failure': T.OOM('chunked'), 'chunked': True}):
            obj, run, events = fixture(**kwargs)
            ctl, _, _ = T.controller(obj)
            with self.assertRaisesRegex(T.S.SafetyRefusal, 'tiled fallback forbidden'):
                with ctl.request('one'): run()
            for forbidden in ('warning', 'flush', 'tile'): self.assertNotIn(forbidden, events)
            with self.assertRaises(T.S.SafetyRefusal): ctl.before('two')

    def test_non_oom_propagates_and_latches(self):
        obj, run, events = fixture(failure=ValueError('encode shape'))
        ctl, _, _ = T.controller(obj)
        with self.assertRaisesRegex(T.S.SafetyRefusal, 'encode shape'):
            with ctl.request('one'): run()
        self.assertIsNotNone(ctl.failed)
        for forbidden in ('warning', 'flush', 'tile'): self.assertNotIn(forbidden, events)

    def test_unbound_behavior_preserved_but_not_admitted(self):
        # This source delta is not an authorization guard. Runtime must refuse
        # unbound encode BEFORE entry. Historical unbound behavior is unchanged.
        for transformed in (False, True):
            _, run, events = fixture(transformed, failure=T.OOM('unbound'))
            run()
            self.assertEqual(events.count('tile'), 1)
            self.assertEqual(events.count('flush'), 1)

    def test_closed_controller_still_refuses_encode_oom(self):
        obj, run, events = fixture(failure=T.OOM('late'))
        ctl, _, _ = T.controller(obj)
        with ctl.request('one'): pass
        ctl.close()
        with self.assertRaisesRegex(T.S.SafetyRefusal, 'tiled fallback forbidden'): run()
        self.assertNotIn('tile', events)


if __name__ == '__main__': unittest.main()
