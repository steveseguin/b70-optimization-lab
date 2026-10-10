"""CPU-only allocation, lifecycle, exactness and receipt gates; no native claim."""
import ast
import copy
from contextlib import nullcontext
from pathlib import Path
import types
import unittest
from unittest.mock import patch

import torch
import audio_residency132 as a
import residency123


class AudioVAE(torch.nn.Module):
    output_sample_rate = 48000
    def __init__(self):
        super().__init__()
        self.register_buffer('scale', torch.tensor([1.25]))
    def decode(self, samples): return samples * self.scale


def vae():
    return types.SimpleNamespace(device='xpu:2', output_device='cpu', disable_offload=True,
        first_stage_model=AudioVAE(), vae_dtype=torch.bfloat16, vae_output_dtype=lambda: torch.float32,
        process_output=lambda pixels: pixels)


class FakeTorch:
    def __init__(self, free=16*a.GIB):
        self.calls = []
        self.xpu = types.SimpleNamespace(synchronize=lambda card: self.calls.append(('sync', card)),
            mem_get_info=lambda card: (free, 32*a.GIB), device=lambda card: nullcontext())
    def __getattr__(self, key): return getattr(torch, key)


class AudioResidency132(unittest.TestCase):
    def test_legacy_default(self): self.assertEqual(a.launch({}), 'legacy')
    def test_explicit_modes(self):
        for mode in a.MODES: self.assertEqual(a.launch({a.ENV: mode}), mode)
    def test_invalid_modes(self):
        for mode in (None, True, 1, '', 'xpu:2', 'XPU2', ' xpu2'):
            with self.subTest(mode=mode), self.assertRaises(ValueError): a.launch({a.ENV: mode})
    def test_only_audio_moves(self):
        roles = residency123.roles('legacy', 'xpu2')
        self.assertEqual([r for r in roles if roles[r] != residency123.LEGACY_ROLES[r]], ['audio_vae'])
        self.assertEqual(roles['upsampler'], 'xpu:0')
    def test_off_roles_parent(self): self.assertEqual(residency123.roles('legacy', 'legacy'), residency123.LEGACY_ROLES)
    def test_double_move_refused(self):
        with self.assertRaises(ValueError): residency123.roles('xpu2', 'xpu2')
    def test_video_stays_three(self):
        self.assertEqual(a.vae_device('ltx-2.5-video-vae-bf16.safetensors', 'legacy', 'xpu2'), 'xpu:3')
    def test_audio_only_target_two(self):
        self.assertEqual(a.vae_device('ltx-2.5-audio-vae-bf16.safetensors', 'legacy', 'xpu2'), 'xpu:2')
    def test_undeclared_vae_refused(self):
        with self.assertRaises(RuntimeError): a.vae_device('other', 'legacy', 'xpu2')
    def test_legacy_reference_inert(self):
        self.assertIsNone(a.prepare_reference(object(), object(), 'audio', 'legacy'))
    def test_video_reference_inert(self):
        self.assertIsNone(a.prepare_reference(object(), object(), 'ltx-2.5-video-vae-bf16.safetensors', 'xpu2'))
    def test_reference_copy_weights_and_owner(self):
        v = vae(); original = v.first_stage_model
        row = a.prepare_reference(torch, v, 'ltx-2.5-audio-vae-bf16.safetensors', 'xpu2')
        self.assertIs(v.first_stage_model, original)
        self.assertEqual(row['device'], 'cpu')
        self.assertEqual(row['resident_bytes'], 4)
        self.assertEqual(a.assert_reference_released(v)['resident_bytes_on_xpu3'], 0)
        self.assertIsNot(getattr(v, a.REFERENCE_ATTRIBUTE)['model'].scale, original.scale)
    def test_reference_repeated_install_refused(self):
        v = self.prepared()
        with self.assertRaises(RuntimeError): a.prepare_reference(torch, v, 'ltx-2.5-audio-vae-bf16.safetensors', 'xpu2')
    def test_reference_wrong_target_refused(self):
        v = vae(); v.device = 'xpu:3'
        with self.assertRaises(RuntimeError): a.prepare_reference(torch, v, 'ltx-2.5-audio-vae-bf16.safetensors', 'xpu2')
    def test_workspace_exact_boundaries(self):
        for device, floor in (('xpu:2', 2*a.GIB), ('xpu:3', 9*a.GIB)):
            for before in (False, True):
                required = floor+a.SCREENING_BYTES+(a.WORKSPACE_BYTES+4 if before else 0)
                self.assertTrue(a.check_workspace(required, device, before, 4)['passed'])
                with self.assertRaises(RuntimeError): a.check_workspace(required-1, device, before, 4)
    def test_workspace_invalid_types(self):
        for free in (None, True, -1, 16.0*a.GIB):
            with self.subTest(free=free), self.assertRaises(RuntimeError): a.check_workspace(free, 'xpu:2', True)
    def test_workspace_synchronizes_only_target(self):
        t = FakeTorch(); a.workspace(t, 'xpu:2', True)
        self.assertEqual(t.calls, [('sync', 'xpu:2')])
    def test_compare_exact(self):
        wave = {'waveform': torch.tensor([1., -0.]), 'sample_rate': 48000}
        self.assertTrue(a.compare(torch, wave, wave)['equal'])
    def test_compare_signed_zero_mismatch(self):
        with self.assertRaisesRegex(RuntimeError, 'byte gate'):
            a.compare(torch, {'waveform': torch.tensor([-0.]), 'sample_rate': 48000},
                      {'waveform': torch.tensor([0.]), 'sample_rate': 48000})
    def test_compare_sample_rate_mismatch(self):
        wave = torch.zeros(1)
        with self.assertRaises(RuntimeError):
            a.compare(torch, {'waveform': wave, 'sample_rate': 48000}, {'waveform': wave, 'sample_rate': 24000})
    def test_missing_reference_refused(self):
        with self.assertRaises(RuntimeError): a.assert_reference_released(vae())
    def test_active_reference_refused(self):
        v = self.prepared(); getattr(v, a.REFERENCE_ATTRIBUTE)['active'] = True
        with self.assertRaises(RuntimeError): a.assert_reference_released(v)
    def test_failed_reference_refused(self):
        v = self.prepared(); getattr(v, a.REFERENCE_ATTRIBUTE)['failed'] = 'fault'
        with self.assertRaises(RuntimeError): a.assert_reference_released(v)
    def prepared(self):
        v = vae(); a.prepare_reference(torch, v, 'ltx-2.5-audio-vae-bf16.safetensors', 'xpu2'); return v
    def cpu_route(self):
        native = torch.Tensor.to
        def to(tensor, *args, **kwargs):
            if args and str(args[0]) == 'xpu:3': args = ('cpu',) + args[1:]
            if str(kwargs.get('device')) == 'xpu:3': kwargs['device'] = 'cpu'
            return native(tensor, *args, **kwargs)
        return patch.object(torch.Tensor, 'to', to)
    def decode(self, v, kind='qualify-eager', name='q0'):
        latent = torch.arange(8, dtype=torch.float32).reshape(1, 2, 4)
        with self.cpu_route():
            return a.decode(FakeTorch(), v, latent, lambda: {'waveform': latent*1.25, 'sample_rate': 48000}, kind, name)
    def test_native_reference_arithmetic_cpu_route(self):
        v = self.prepared(); audio, evidence = self.decode(v)
        self.assertTrue(evidence['cross_card']['equal'])
        self.assertEqual(evidence['reference_released']['calls'], 1)
        self.assertEqual(evidence['reference_released']['resident_bytes_on_xpu3'], 0)
        self.assertEqual(str(v.device), 'xpu:2')
    def test_three_references_then_no_postcapture_reference(self):
        v = self.prepared()
        for i in range(3): self.decode(v, name='q%d' % i)
        _, evidence = self.decode(v, kind='qualify-graph', name='g0')
        self.assertIsNone(evidence['cross_card']); self.assertIsNone(evidence['reference'])
        self.assertEqual(evidence['reference_released']['calls'], 3)
    def test_repeat_reference_refused(self):
        v = self.prepared(); self.decode(v)
        with self.assertRaisesRegex(RuntimeError, 'duplicated'): self.decode(v)
    def test_graph_before_three_controls_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'three cross-card'): self.decode(self.prepared(), kind='qualify-graph')
    def test_weight_tamper_refused(self):
        v = self.prepared(); getattr(v, a.REFERENCE_ATTRIBUTE)['model'].scale.add_(1)
        with self.assertRaisesRegex(RuntimeError, 'weights changed'): self.decode(v)
    def test_reference_oom_latches_without_retry(self):
        v = self.prepared(); state = getattr(v, a.REFERENCE_ATTRIBUTE)
        state['model'].decode = lambda samples: (_ for _ in ()).throw(RuntimeError('fake OOM'))
        with self.assertRaisesRegex(RuntimeError, 'fake OOM'): self.decode(v)
        self.assertIn('fake OOM', state['failed'])
        with self.assertRaisesRegex(RuntimeError, 'failed'): a.assert_reference_released(v)
    def record(self):
        audio, evidence = self.decode(self.prepared())
        return {'server_options': {'audio_residency': 'xpu2'}, 'audio_residency': 'xpu2', 'audio_device': 'xpu:2',
            'kind': 'qualify-eager', 'run_name': 'q0', 'prompt_id': 'p', 'sample_rate': 48000,
            'audio_residency_evidence': evidence, 'tensors': {'waveform': {
                'sha256': a._digest(torch, audio['waveform']), 'shape': list(audio['waveform'].shape), 'dtype': 'torch.float32'}}}
    def test_evidence_exact(self): self.assertTrue(a.validate_evidence(decode=self.record())['cross_card'])
    def test_evidence_off(self): self.assertFalse(a.validate_evidence(decode={})['enabled'])
    def test_evidence_pending(self):
        self.assertTrue(a.validate_evidence(receipt={'server_options': {'audio_residency': 'xpu2'}})['decode_pending'])
    def test_evidence_missing_ref_refused(self):
        d = self.record(); d['audio_residency_evidence']['reference'] = None
        with self.assertRaises(ValueError): a.validate_evidence(decode=d)
    def test_evidence_wave_hash_tamper_refused(self):
        d = self.record(); d['tensors']['waveform']['sha256'] = '0'*64
        with self.assertRaises(ValueError): a.validate_evidence(decode=d)
    def test_evidence_floor_tamper_refused(self):
        d = self.record(); d['audio_residency_evidence']['workspace']['before']['floor_bytes'] -= 1
        with self.assertRaises(ValueError): a.validate_evidence(decode=d)
    def test_evidence_resident_ref_refused(self):
        d = self.record(); d['audio_residency_evidence']['reference_released']['resident_bytes_on_xpu3'] = 4
        with self.assertRaises(ValueError): a.validate_evidence(decode=d)
    def test_evidence_timing_nan_refused(self):
        d = self.record(); d['audio_residency_evidence']['candidate_native_node_seconds'] = float('nan')
        with self.assertRaises(ValueError): a.validate_evidence(decode=d)
    def test_evidence_receipt_binding(self):
        d = self.record(); r = copy.deepcopy(d); r['run_name'] = 'other'
        with self.assertRaises(ValueError): a.validate_evidence(receipt=r, decode=d)
    def test_pinned_host_transform(self):
        path = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-131/source/custom_nodes/ltx_host_embedding_lab/__init__.py')
        result = a.transform_host(path.read_bytes()); ast.parse(result)
        self.assertEqual(result.count(b'audio_residency132.prepare_reference('), 1)
        self.assertIn(b'retarget_upsampler(upscaler, torch, AUX_RESIDENCY)', result)
        with self.assertRaises(RuntimeError): a.transform_host(result)
    def test_host_unpinned_refused(self):
        with self.assertRaises(RuntimeError): a.transform_host(b'pass\n')


if __name__ == '__main__': unittest.main()
