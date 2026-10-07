#!/usr/bin/env python3
"""Offline controls; real pinned VAE.decode AST, fake tensors and devices."""
import ast
from contextlib import nullcontext
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('native_safety', HERE / 'native_safety.py')
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
SOURCE = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99b/source/comfy/sd.py')


class OOM(RuntimeError):
    pass


class Tensor:
    shape = (1, 3, 4, 12, 20)
    ndim = 5
    def __getitem__(self, key): return self
    def to(self, *args, **kwargs): return self
    def copy_(self, other): return self
    def movedim(self, *args): return self


def decode_fixture(transformed=True, failure=None, reliable=False):
    raw = SOURCE.read_bytes()
    tree = ast.parse(S.transform_sd(raw) if transformed else raw)
    vae = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'VAE')
    fn = next(n for n in vae.body if isinstance(n, ast.FunctionDef) and n.name == 'decode')
    events = []
    def classify(exc):
        events.append('classify')
        if not isinstance(exc, OOM): raise exc
    mm = NS(cuda_device_context=lambda device: nullcontext(),
            load_models_gpu=lambda *a, **kw: events.append('load'),
            raise_non_oom=classify, OOM_EXCEPTION=OOM,
            soft_empty_cache=lambda: events.append('flush'))
    env = {'model_management': mm,
           'comfy': NS(model_management=mm, model_prefetch=NS(pause_malloc_graph=nullcontext)),
           'torch': NS(empty=lambda *a, **kw: Tensor()),
           'logging': NS(info=lambda *a: None, warning=lambda *a: None)}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SOURCE), 'exec'), env)
    def native(*a, **kw):
        events.append('native')
        if failure is not None: raise failure
        return Tensor()
    obj = NS(throw_exception_if_invalid=lambda: None, latent_dim=3, device='xpu:3',
             vae_dtype='bf16', memory_used_decode=lambda *a: 2 if reliable else 1,
             patcher=NS(get_free_memory=lambda d: 1), disable_offload=True,
             first_stage_model=NS(comfy_decode_estimate_is_reliable=reliable, decode=native),
             output_device='cpu', vae_output_dtype=lambda: 'fp32',
             process_output=lambda t: events.append('output'),
             extra_1d_channel=None, handles_tiling=True,
             spacial_compression_decode=lambda: 32,
             _tile_bounded_shape=lambda *a: Tensor.shape,
             _decode_tiled_owned=lambda *a, **kw: events.append('tile') or Tensor())
    return obj, lambda: env['decode'](obj, Tensor()), events


def controller(video=None, **overrides):
    objects = {r: NS() for r in S.ROLES}
    if video is not None: objects['video_vae'] = video
    expected = {r: 'c' * 64 for r in S.ROLES}
    snap = {'plan_sha256': 'a' * 64, 'runtime_sha256': 'b' * 64,
            'phase': 'native-reference', 'fault': False, 'text_graphs_captured': True,
            'window_qualified': True, 'sampler_routes': 0, 'decoder_replicas': 0,
            'residence': {r: {'object_id': id(o), 'device': S.ROLES[r],
                             'dtype': 'torch.bfloat16', 'fully_resident': True,
                             'ownership_sha256': expected[r]} for r, o in objects.items()},
            'physical_free_bytes': dict(S.PRE_BYTES),
            'peaks': {c: {'allocated': 1, 'reserved': 2, 'peak': 1} for c in S.CARDS}}
    calls = []
    def inspect(actual):
        assert all(actual[r] is objects[r] for r in S.ROLES)
        calls.append('inspect')
        return snap
    args = dict(plan_sha256='a' * 64, runtime_sha256='b' * 64,
                objects=objects, expected_residence=expected,
                synchronize=lambda c: calls.append(c), inspect=inspect,
                require_phase=lambda: calls.append('phase'))
    args.update(overrides)
    return S.NativeReferenceSafety(**args), snap, calls


class DecodeControls(unittest.TestCase):
    def test_source_pinned_and_double_transform_refused(self):
        raw = SOURCE.read_bytes()
        with self.assertRaises(S.SafetyRefusal): S.transform_sd(raw + b'\n')
        with self.assertRaises(S.SafetyRefusal): S.transform_sd(S.transform_sd(raw))

    def test_successful_arithmetic_and_flow_unchanged(self):
        a, run_a, events_a = decode_fixture(False)
        b, run_b, events_b = decode_fixture(True)
        ctl, _, _ = controller(b)
        out_a = run_a()
        with ctl.request('one'): out_b = run_b()
        self.assertEqual(type(out_a), type(out_b))
        self.assertEqual(events_a, events_b)
        self.assertNotIn('tile', events_b)

    def test_actual_and_estimated_oom_refuse_before_flush_or_tile(self):
        for estimated in (False, True):
            with self.subTest(estimated=estimated):
                obj, run, events = decode_fixture(failure=OOM('actual'), reliable=estimated)
                ctl, _, _ = controller(obj)
                with self.assertRaisesRegex(S.SafetyRefusal, 'tiled fallback forbidden'):
                    with ctl.request('one'): run()
                self.assertNotIn('flush', events)
                self.assertNotIn('tile', events)
                self.assertEqual('native' in events, not estimated)
                with self.assertRaises(S.SafetyRefusal): ctl.before('two')
                with self.assertRaises(S.SafetyRefusal): ctl.close()

    def test_unbound_object_preserves_original_fallback(self):
        for transformed in (False, True):
            obj, run, events = decode_fixture(transformed, failure=OOM('actual'))
            run()
            self.assertEqual(events.count('flush'), 1)
            self.assertEqual(events.count('tile'), 1)

    def test_non_oom_propagates_before_oom_callback_and_latches(self):
        obj, run, events = decode_fixture(failure=ValueError('bad input'))
        ctl, _, _ = controller(obj)
        with self.assertRaisesRegex(S.SafetyRefusal, 'bad input'):
            with ctl.request('one'): run()
        self.assertNotIn('flush', events)
        self.assertNotIn('tile', events)
        self.assertIsNotNone(ctl.failed)


class AdmissionControls(unittest.TestCase):
    def test_exact_threshold_and_fresh_synchronized_post_floor(self):
        ctl, snap, calls = controller()
        with ctl.request('one'):
            snap['physical_free_bytes'] = {c: 2 * S.GIB for c in S.CARDS}
        self.assertEqual(calls, ['phase', *S.CARDS, 'inspect'] * 2)
        self.assertEqual([r['event'] for r in ctl.receipts], ['before', 'after'])
        snap['physical_free_bytes']['xpu:0'] = 0
        self.assertEqual(ctl.receipts[0]['snapshot']['physical_free_bytes']['xpu:0'], 8 * S.GIB)
        self.assertEqual(S.PRE_BYTES, dict(zip(S.CARDS, (8*S.GIB, 8*S.GIB, 2*S.GIB, 9*S.GIB))))
        ctl.close()
        self.assertIs(getattr(ctl.objects['video_vae'], S.ATTRIBUTE), ctl)
        with self.assertRaises(S.SafetyRefusal): ctl.before('two')

    def test_closed_reference_still_refuses_native_vae_oom(self):
        obj, run, events = decode_fixture(failure=OOM('late optimized native decode'))
        ctl, _, _ = controller(obj)
        with ctl.request('reference-complete'): pass
        ctl.close()
        with self.assertRaisesRegex(S.SafetyRefusal, 'tiled fallback forbidden'): run()
        self.assertNotIn('flush', events)
        self.assertNotIn('tile', events)

    def test_each_low_card_refuses_and_never_retries_inspection(self):
        for card in S.CARDS:
            ctl, snap, calls = controller()
            snap['physical_free_bytes'][card] -= 1
            with self.assertRaises(S.SafetyRefusal): ctl.before('one')
            before = len(calls)
            snap['physical_free_bytes'] = dict(S.PRE_BYTES)
            with self.assertRaises(S.SafetyRefusal): ctl.before('two')
            self.assertEqual(len(calls), before)

    def test_bad_snapshots_refuse(self):
        mutations = [lambda s: s.update(plan_sha256='d' * 64),
                     lambda s: s.update(runtime_sha256='d' * 64),
                     lambda s: s.update(phase='timing'),
                     lambda s: s.update(fault=True),
                     lambda s: s.update(text_graphs_captured=False),
                     lambda s: s.update(window_qualified=False),
                     lambda s: s.update(sampler_routes=1),
                     lambda s: s.update(decoder_replicas=1),
                     lambda s: s['residence']['video_vae'].update(object_id=0),
                     lambda s: s['residence']['text_secondary'].update(device='cpu'),
                     lambda s: s['residence']['sampler_primary'].update(dtype='torch.float16'),
                     lambda s: s['residence']['upsampler'].update(fully_resident=False),
                     lambda s: s['residence']['audio_vae'].update(ownership_sha256='d' * 64),
                     lambda s: s['physical_free_bytes'].pop('xpu:3'),
                     lambda s: s['peaks']['xpu:0'].update(peak=False)]
        for mutate in mutations:
            ctl, snap, _ = controller()
            mutate(snap)
            with self.assertRaises(S.SafetyRefusal): ctl.before('one')

    def test_nonfinite_bool_negative_counts_refuse(self):
        for value in (True, float('nan'), float('inf'), -1, '7000000000', None):
            ctl, snap, _ = controller()
            snap['physical_free_bytes']['xpu:0'] = value
            with self.assertRaises(S.SafetyRefusal): ctl.before('one')

    def test_post_floor_failure_and_body_failure_latch(self):
        ctl, snap, _ = controller()
        with self.assertRaises(S.SafetyRefusal):
            with ctl.request('one'): snap['physical_free_bytes']['xpu:1'] = 2 * S.GIB - 1
        self.assertIsNotNone(ctl.failed)
        ctl, _, _ = controller()
        with self.assertRaises(S.SafetyRefusal):
            with ctl.request('one'): raise RuntimeError('sampler failure')
        self.assertIsNotNone(ctl.failed)

    def test_inspector_synchronizer_phase_errors_latch(self):
        def fail(*args): raise RuntimeError('inspection unavailable')
        for key in ('inspect', 'synchronize', 'require_phase'):
            ctl, _, _ = controller(**{key: fail})
            with self.assertRaises(S.SafetyRefusal): ctl.before('one')
            self.assertIsNotNone(ctl.failed)

    def test_duplicate_overlap_binding_tamper_and_invalid_identity_refuse(self):
        ctl, _, _ = controller()
        with ctl.request('one'): pass
        with self.assertRaises(S.SafetyRefusal): ctl.before('one')
        ctl, _, _ = controller()
        ctl.before('one')
        with self.assertRaises(S.SafetyRefusal): ctl.before('two')
        ctl, _, _ = controller()
        delattr(ctl.objects['video_vae'], S.ATTRIBUTE)
        with self.assertRaises(S.SafetyRefusal): ctl.before('one')
        with self.assertRaises(S.SafetyRefusal): controller(plan_sha256='not-bound')


if __name__ == '__main__':
    unittest.main()
