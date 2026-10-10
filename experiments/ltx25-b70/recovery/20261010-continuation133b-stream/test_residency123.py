import ast
from pathlib import Path
import types
import unittest

import residency123 as r


class Tensor:
    device = 'cpu'
    dtype = 'torch.bfloat16'
    def numel(self): return r.UPSCALER_BYTES // 2
    def element_size(self): return 2


def patcher():
    t = Tensor()
    return types.SimpleNamespace(load_device='xpu:0', loaded_size=lambda: 0,
        is_dynamic=lambda: False, model=types.SimpleNamespace(parameters=lambda: [t], buffers=lambda: [])), t


class ResidencyTests(unittest.TestCase):
    def test_default_legacy(self): self.assertEqual(r.launch({}), 'legacy')
    def test_explicit_legacy(self): self.assertEqual(r.launch({r.ENV: 'legacy'}), 'legacy')
    def test_explicit_xpu2(self): self.assertEqual(r.launch({r.ENV: 'xpu2'}), 'xpu2')
    def test_unknown_mode(self):
        for value in ['', 'XPU2', 'xpu:2', None, 1, True, ' legacy']:
            with self.subTest(value=value), self.assertRaises(ValueError): r.launch({r.ENV: value})
    def test_legacy_exact_roles(self): self.assertEqual(r.roles('legacy'), r.LEGACY_ROLES)
    def test_only_two_roles_move(self):
        self.assertEqual({k for k in r.roles('xpu2') if r.roles('xpu2')[k] != r.LEGACY_ROLES[k]}, {'upsampler', 'audio_vae'})
    def test_roles_copy(self):
        result = r.roles('legacy'); result['video_vae'] = 'cpu'
        self.assertEqual(r.roles('legacy')['video_vae'], 'xpu:3')
    def test_video_stays(self): self.assertEqual(r.vae_device('ltx-2.5-video-vae-bf16.safetensors', 'xpu2'), 'xpu:3')
    def test_audio_moves(self): self.assertEqual(r.vae_device('ltx-2.5-audio-vae-bf16.safetensors', 'xpu2'), 'xpu:2')
    def test_audio_legacy(self): self.assertEqual(r.vae_device('ltx-2.5-audio-vae-bf16.safetensors', 'legacy'), 'xpu:3')
    def test_unknown_vae(self):
        with self.assertRaises(RuntimeError): r.vae_device('different.safetensors', 'legacy')
    def test_retarget_retains_owner_and_weights(self):
        p, t = patcher(); model = p.model
        got = r.retarget_upsampler(p, types.SimpleNamespace(device=str), 'xpu2')
        self.assertEqual(p.load_device, 'xpu:2'); self.assertIs(p.model, model)
        self.assertIs(p.model.parameters()[0], t); self.assertEqual(t.device, 'cpu')
        self.assertEqual(got['tensor_bytes'], r.UPSCALER_BYTES)
    def test_legacy_does_not_touch_patcher(self):
        self.assertFalse(r.retarget_upsampler(object(), object(), 'legacy')['changed'])
    def test_refuse_already_loaded(self):
        p, _ = patcher(); p.loaded_size = lambda: 1
        with self.assertRaises(RuntimeError): r.retarget_upsampler(p, types.SimpleNamespace(device=str), 'xpu2')
    def test_refuse_dynamic(self):
        p, _ = patcher(); p.is_dynamic = lambda: True
        with self.assertRaises(RuntimeError): r.retarget_upsampler(p, types.SimpleNamespace(device=str), 'xpu2')
    def test_refuse_wrong_source_device(self):
        p, _ = patcher(); p.load_device = 'xpu:1'
        with self.assertRaises(RuntimeError): r.retarget_upsampler(p, types.SimpleNamespace(device=str), 'xpu2')
    def test_refuse_loaded_tensor(self):
        p, t = patcher(); t.device = 'xpu:0'
        with self.assertRaises(RuntimeError): r.retarget_upsampler(p, types.SimpleNamespace(device=str), 'xpu2')
    def test_refuse_dtype_change(self):
        p, t = patcher(); t.dtype = 'torch.float16'
        with self.assertRaises(RuntimeError): r.retarget_upsampler(p, types.SimpleNamespace(device=str), 'xpu2')
    def test_refuse_empty(self):
        p, _ = patcher(); p.model.parameters = lambda: []
        with self.assertRaises(RuntimeError): r.retarget_upsampler(p, types.SimpleNamespace(device=str), 'xpu2')
    def test_refuse_byte_change(self):
        p, t = patcher(); t.numel = lambda: 1
        with self.assertRaises(RuntimeError): r.retarget_upsampler(p, types.SimpleNamespace(device=str), 'xpu2')
    def test_refuse_parent_hash_host(self):
        with self.assertRaises(RuntimeError): r.transform_host(b'import torch\n')
    def test_refuse_parent_hash_safety(self):
        with self.assertRaises(RuntimeError): r.transform_native_safety(b'ROLES = {}\n')
    def test_actual_parent_transforms_parse_and_bind(self):
        parent = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-122/source')
        host = r.transform_host((parent/'custom_nodes/ltx_host_embedding_lab/__init__.py').read_bytes())
        safety = r.transform_native_safety((parent/'scripts/native_safety.py').read_bytes())
        ast.parse(host); ast.parse(safety)
        self.assertIn(b'residency123.retarget_upsampler(upscaler, torch, AUX_RESIDENCY)', host)
        self.assertIn(b'ROLES = residency123.roles(residency123.launch())', safety)
        with self.assertRaises(RuntimeError): r.transform_host(host)
        with self.assertRaises(RuntimeError): r.transform_native_safety(safety)
    def test_workspace_before_boundary(self):
        self.assertTrue(r.check_aux_free(int(4.75*r.GIB), True)['passed'])
        with self.assertRaises(RuntimeError): r.check_aux_free(int(4.75*r.GIB)-1, True)
    def test_workspace_after_boundary(self):
        self.assertTrue(r.check_aux_free(int(2.75*r.GIB), False)['passed'])
        with self.assertRaises(RuntimeError): r.check_aux_free(int(2.75*r.GIB)-1, False)
    def test_workspace_bad_sample(self):
        for v in [True, 4.75*r.GIB, -1, None]:
            with self.subTest(value=v), self.assertRaises(RuntimeError): r.check_aux_free(v, True)
    def test_legacy_guard_no_device_calls(self): self.assertIsNone(r.guard_aux(object(), 'audio', True, 'legacy'))
    def test_guard_exact_device_order(self):
        calls = []
        xpu = types.SimpleNamespace(synchronize=lambda dev: calls.append(('sync', dev)),
            mem_get_info=lambda dev: (calls.append(('free', dev)) or (5*r.GIB, 32*r.GIB)))
        got = r.guard_aux(types.SimpleNamespace(xpu=xpu), 'audio', True, 'xpu2')
        self.assertEqual(calls, [('sync', 'xpu:2'), ('free', 'xpu:2')]); self.assertTrue(got['passed'])
    def test_guard_unknown_owner(self):
        with self.assertRaises(RuntimeError): r.guard_aux(object(), 'video', True, 'xpu2')
    def test_guard_invalid_before(self):
        with self.assertRaises(RuntimeError): r.check_aux_free(5*r.GIB, 1)
    def test_actual_upsampler_transform(self):
        parent = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-122/source')
        raw = r.transform_upsampler_node((parent/'comfy_extras/nodes_lt_upsampler.py').read_bytes())
        ast.parse(raw)
        self.assertEqual(raw.count(b'guard_aux('), 2)
        self.assertIn(b'upscale_model._ltx123_aux_workspace', raw)
        with self.assertRaises(RuntimeError): r.transform_upsampler_node(raw)


if __name__ == '__main__': unittest.main()
