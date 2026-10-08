"""Attempt-1 regression: real CPU dispatch through the UVA construction path.

Only pinned allocation/platform interfaces and accelerator synchronization are
stubbed. The loader mode, slicing, copy arithmetic and staging ledger are real.
"""
import contextlib
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from test_overlay_cpu import HERE, guard, load_file

try:
    import torch
except ImportError:
    torch = None


@unittest.skipIf(torch is None, 'requires the existing CPU-capable torch interpreter')
class CopyDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load lazy dispatch support before patch.dict(sys.modules): restoring
        # that dict must not unload modules with registered Torch libraries.
        import torch._dynamo

    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.dict(os.environ, {
            'B70_SCREEN1B': '1', 'B70_SCREEN1B_STATE_DIR': str(self.root)}))
        self.stack.enter_context(patch.object(guard, '_cancelled', False))
        self.stack.enter_context(patch.object(guard, 'COPY_LIMIT', 64))
        self.stack.enter_context(patch.object(guard, 'memory', return_value={
            'MemTotal': 128 << 30, 'MemAvailable': 110 << 30}))
        self.sync = self.stack.enter_context(patch.object(guard, 'synchronize'))
        self.stack.enter_context(patch.object(guard, 'allocation_snapshot'))
        modules = {}
        for name, attrs in {
            'vllm': {'screen1b_guard': guard},
            'vllm.envs': {'VLLM_WEIGHT_OFFLOADING_DISABLE_UVA': False},
            'vllm.logger': {'init_logger': lambda _: types.SimpleNamespace(info=lambda *a: None)},
            'vllm.model_executor.offloader.base': {
                'BaseOffloader': object, 'should_pin_memory': lambda: True},
            'vllm.utils.gpu_sync_debug': {'gpu_sync_allowed': contextlib.nullcontext},
            'vllm.utils.mem_utils': {'format_gib': str},
            'vllm.utils.platform_utils': {'is_uva_available': lambda: True},
            'vllm.utils.torch_utils': {'get_accelerator_view_from_cpu_tensor': lambda p: p},
        }.items():
            module = types.ModuleType(name)
            module.__dict__.update(attrs)
            modules[name] = module
        self.stack.enter_context(patch.dict(sys.modules, modules))
        self.uva = load_file('screen1b_uva_dispatch_test',
                            HERE / 'overlay/vllm/model_executor/offloader/uva.py')
        empty_like = torch.empty_like

        def cpu_empty_like(tensor, **kwargs):
            self.assertEqual(kwargs.pop('pin_memory'), True)
            self.assertEqual(kwargs['device'], 'cpu')
            return empty_like(tensor, **kwargs)

        self.stack.enter_context(patch.object(torch, 'empty_like', side_effect=cpu_empty_like))
        self.stack.enter_context(patch.object(torch.Tensor, 'is_pinned', return_value=True))

    def reservations(self):
        rows = [json.loads(line) for line in
                (self.root / f'loader-{os.getpid()}.jsonl').read_text().splitlines()]
        return [row['bytes'] for row in rows if row['event'] == 'staging_reserved']

    def assert_drained(self):
        state = json.loads((self.root / 'staging-live.json').read_text())
        self.assertEqual(state['live'], {})
        self.assertLessEqual(state['peak_bytes'], 64)
        self.assertEqual(getattr(guard._local, 'depth', 0), 0)
        self.assertFalse(getattr(guard._local, 'copy_in_progress', False))

    def construct(self, shape):
        parameter = torch.nn.Parameter(
            torch.arange(shape[0] * shape[1], dtype=torch.float32, device='cpu').reshape(shape),
            requires_grad=False)

        @guard.guarded_load
        def load():
            return self.uva.UVAOffloader(1024)._make_cpu_data(parameter)

        result = load()
        self.assertTrue(torch.equal(result, parameter))
        self.assert_drained()
        self.assertFalse((self.root / 'STOP').exists())

    def test_uva_copy_at_exact_cap_inside_loader_mode(self):
        # Before the fix the outer reservation consumes the whole cap and
        # re-entry raises "no transient staging headroom" before any copy.
        self.construct((2, 4))
        self.assertEqual(self.reservations(), [64])
        self.assertEqual(self.sync.call_count, 2)  # one copy + loader drain

    def test_uva_copy_with_small_remainder_does_not_fragment_again(self):
        # As in attempt 1: row rounding leaves a tiny remainder. Previously
        # the same bytes were reserved again and split into many tiny copies.
        self.construct((5, 3))
        self.assertEqual(self.reservations(), [48, 48, 24])
        self.assertEqual(self.sync.call_count, 4)

    def test_ordinary_copy_still_guarded_after_explicit_copy(self):
        source = torch.arange(15, dtype=torch.float32, device='cpu').reshape(5, 3)
        target = torch.zeros((5, 3), dtype=torch.bfloat16, device='cpu')

        @guard.guarded_load
        def load():
            guard.bounded_copy(target, source)
            target.copy_(source, non_blocking=True)
            return target

        self.assertTrue(torch.equal(load(), source.to(torch.bfloat16)))
        self.assertEqual(self.reservations(), [54, 36, 54, 36])
        self.assert_drained()

    def test_failed_copy_releases_reservation_and_restores_dispatch_flag(self):
        source = torch.ones((2, 4), device='cpu')
        target = torch.zeros((2, 4), device='cpu')

        @guard.guarded_load
        def load():
            with patch.object(torch.Tensor, 'copy_', side_effect=RuntimeError('copy failed')):
                guard.bounded_copy(target, source)

        with self.assertRaisesRegex(RuntimeError, 'copy failed'):
            load()
        self.assert_drained()
        self.assertTrue((self.root / 'STOP').exists())


if __name__ == '__main__':
    unittest.main()
