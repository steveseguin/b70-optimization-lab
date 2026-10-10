"""CPU evidence for copy/budget/qualification. No cross-card claim."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import nullcontext
import display_replica as replica


class Options(unittest.TestCase):
    def test_default_off(self):
        self.assertEqual(replica.launch_device({}), 'xpu:3')

    def test_only_two_choices(self):
        for device in ('cpu', 'xpu:0', '', 'xpu:2 '):
            with self.assertRaises(RuntimeError):
                replica.launch_device({'LTX_DISPLAY_DEVICE': device})

    def test_scope(self):
        replica.validate_scope('xpu:3', 49, 'latent', 'full', 'sampler-a')
        replica.validate_scope('xpu:2', 121, 'frame', 'cone', 'eager-display')
        for values in ((49, 'frame', 'cone', 'eager-display'), (121, 'latent', 'cone', 'eager-display'),
                       (121, 'frame', 'full', 'eager-display'), (121, 'frame', 'cone', 'sampler-a')):
            with self.assertRaises(RuntimeError):
                replica.validate_scope('xpu:2', *values)

    def test_budget_at_floor(self):
        self.assertEqual(replica.budget(6*replica.GIB)['margin_bytes'], 0)
        with self.assertRaises(RuntimeError):
            replica.budget(6*replica.GIB-1)

    def test_budget_counts_resident_before_allocation(self):
        with self.assertRaises(RuntimeError):
            replica.budget(6*replica.GIB, 1)
        self.assertEqual(replica.budget(6*replica.GIB+123, 123)['margin_bytes'], 0)

    def test_bad_budget(self):
        for free in (True, -1, 1.1, None):
            with self.assertRaises(RuntimeError):
                replica.budget(free)


class NativeCopy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import cpu_decoder
        cls.native = cpu_decoder
        cls.torch = cpu_decoder.load()[0]
        cls.torch.set_num_threads(4)

    def check_dtype(self, dtype):
        t = self.torch
        source = self.native.tiny_vae(seed=9, dtype=dtype)
        clone = replica.clone_decoder_only(t, source, 'cpu')
        self.assertIsNone(clone.encoder)
        self.assertIsNotNone(source.encoder)
        self.assertEqual(len(replica.tensors(clone)), len(replica.tensors(source)))  # fake encoder has no weights
        for (_, old), (_, new) in zip(replica.tensors(source), replica.tensors(clone)):
            self.assertNotEqual(old.data_ptr(), new.data_ptr())
            self.assertTrue(t.equal(old.view(t.uint8), new.view(t.uint8)))
        latent = t.randn((1, 128, 2, 1, 1), generator=t.Generator().manual_seed(4), dtype=dtype)
        with t.inference_mode():
            a, b = source.decode(latent), clone.decode(latent)
        self.assertTrue(replica.compare(t, a, b)['equal'])
        self.assertFalse(t.xpu.is_initialized())

    def test_native_fp32_decoder_clone(self):
        self.check_dtype(self.torch.float32)

    def test_native_bf16_decoder_clone(self):
        self.check_dtype(self.torch.bfloat16)

    def test_rejects_graph_method_before_copy(self):
        source = self.native.tiny_vae()
        source.decoder.forward_pre_diffusion = lambda x: x
        with self.assertRaisesRegex(RuntimeError, 'precede'):
            replica.clone_decoder_only(self.torch, source, 'cpu')

    def test_copy_under_executor_inference_retains_version_counters(self):
        source = self.native.tiny_vae()
        with self.torch.inference_mode():
            clone = replica.clone_decoder_only(self.torch, source, 'cpu')
            baseline = replica.facts(clone)
        self.assertTrue(baseline)
        self.assertTrue(all(not tensor.is_inference() for _, tensor in replica.tensors(clone)))

    def test_full_image_check_rejects_non_anchor_change(self):
        t = self.torch
        a = t.zeros((3, 2, 2, 3), dtype=t.float32)
        b = a.clone()
        b[0, 0, 0, 0] = 1
        self.assertFalse(replica.compare(t, a, b)['equal'])
        self.assertTrue(t.equal(a[-1], b[-1]))

    def test_facts_detect_mutation(self):
        source = self.native.tiny_vae()
        before = replica.facts(source)
        with self.torch.no_grad():
            next(source.parameters()).add_(1)
        self.assertNotEqual(before, replica.facts(source))

    def wrapper(self, free):
        """Actual replica postprocessing, CPU model and context; no device constructor."""
        t = self.torch
        model = t.nn.Module()
        model.register_buffer('value', t.linspace(-2, 2, 72).reshape(1, 3, 2, 3, 4))
        model.encoder = None
        model.decode = lambda samples: model.value
        obj = replica.ResidentDisplay.__new__(replica.ResidentDisplay)
        obj.torch, obj.model, obj.device = t, model, 'cpu'
        obj.baseline, obj.free_bytes, obj.calls = replica.facts(model), free, 0
        obj.counters = lambda: {'allocated': 1, 'reserved': 2, 'peak_allocated': 2}
        obj.native = SimpleNamespace(vae_dtype=t.bfloat16, output_device='cpu', vae_output_dtype=lambda: t.float32,
            process_output=lambda x: x.add_(1.0).div_(2.0).clamp_(0.0, 1.0))
        return obj

    def test_native_output_copy_normalization_and_layout(self):
        t = self.torch
        obj = self.wrapper(lambda: 8*replica.GIB)
        saved = obj.model.value.clone()
        latent = t.zeros((1, 128, 16, 8, 8))
        with patch.object(t.xpu, 'device', side_effect=lambda *_: nullcontext()):
            actual = obj.decode(latent)
        expected = saved.clone().add_(1).div_(2).clamp_(0, 1).movedim(1, -1).reshape(2, 3, 4, 3)
        self.assertTrue(replica.compare(t, actual, expected)['equal'])
        self.assertTrue(t.equal(saved, obj.model.value))
        self.assertEqual(obj.calls, 1)

    def test_post_decode_floor_failure(self):
        t = self.torch
        free = iter((8*replica.GIB, 2*replica.GIB-1))
        obj = self.wrapper(lambda: next(free))
        with patch.object(t.xpu, 'device', side_effect=lambda *_: nullcontext()):
            with self.assertRaisesRegex(RuntimeError, 'crossed'):
                obj.decode(t.zeros((1, 128, 16, 8, 8)))

    def test_allocator_growth_over_reservation_refuses(self):
        t = self.torch
        obj = self.wrapper(lambda: 8*replica.GIB)
        counters = iter(({'allocated': 1, 'reserved': 2, 'peak_allocated': 2},
                         {'allocated': 1, 'reserved': 2, 'peak_allocated': 5*replica.GIB}))
        obj.counters = lambda: next(counters)
        with patch.object(t.xpu, 'device', side_effect=lambda *_: nullcontext()):
            with self.assertRaisesRegex(RuntimeError, 'transient allowance'):
                obj.decode(t.zeros((1, 128, 16, 8, 8)))

    def test_facts_detect_storage_swap_without_version_bump(self):
        source = self.native.tiny_vae()
        before = replica.facts(source)
        p = next(source.parameters())
        version = p._version
        p.data = p.detach().clone()
        self.assertEqual(version, p._version)
        self.assertNotEqual(before, replica.facts(source))

    def test_unregistered_tensor_rejected(self):
        source = self.native.tiny_vae()
        source.decoder.unregistered_cache = self.torch.zeros(3)
        with self.assertRaisesRegex(RuntimeError, 'Unregistered'):
            replica.clone_decoder_only(self.torch, source, 'cpu')


if __name__ == '__main__':
    unittest.main()
