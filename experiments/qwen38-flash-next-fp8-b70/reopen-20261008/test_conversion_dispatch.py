"""Attempt-2 staging classification with real CPU ATen and emulated transport."""
import contextlib
import gc
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_overlay_cpu import guard
from worker_init_rehearsal import cpu_transport

try:
    import torch
except ImportError:
    torch = None


@unittest.skipIf(torch is None, 'requires the existing CPU-capable torch interpreter')
class ConversionDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch._dynamo

    def setUp(self):
        stack = self.stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        stack.enter_context(patch.dict(os.environ, {'B70_SCREEN1B':'1', 'B70_SCREEN1B_STATE_DIR':str(self.root)}))
        stack.enter_context(patch.object(guard, '_cancelled', False))
        stack.enter_context(patch.object(guard, 'COPY_LIMIT', 64))
        stack.enter_context(patch.object(guard, 'memory', return_value={'MemTotal':128<<30, 'MemAvailable':110<<30}))
        stack.enter_context(patch.object(guard, 'synchronize'))
        stack.enter_context(patch.object(guard, 'allocation_snapshot', lambda model: None))
        self.transport, self.wrap, _ = cpu_transport(torch, 2)
        self.source = torch.arange(32, dtype=torch.float32, device='cpu')

    def convert(self, source, **kwargs):
        @guard.guarded_load
        def load():
            return torch.ops.aten._to_copy.default(source, **kwargs)
        with self.transport():
            return load()

    def test_device_dtype_conversion_has_no_host_staging(self):
        out = self.convert(self.wrap(self.source), dtype=torch.bfloat16)
        self.assertTrue(torch.equal(out.elem, self.source.to(torch.bfloat16)))
        self.assertFalse((self.root/'staging-live.json').exists())

    def test_explicit_same_device_conversion_has_no_host_staging(self):
        for device in ('xpu:2', 'xpu'):
            out = self.convert(self.wrap(self.source), device=torch.device(device), dtype=torch.bfloat16)
            self.assertTrue(torch.equal(out.elem, self.source.to(torch.bfloat16)))
        self.assertFalse((self.root/'staging-live.json').exists())

    def test_device_to_host_still_refuses_oversized_conversion(self):
        with self.assertRaisesRegex(guard.LoadCancelled, 'conversion exceeds'):
            self.convert(self.wrap(self.source), device=torch.device('cpu'))

    def test_host_to_device_still_refuses_oversized_conversion(self):
        with self.assertRaisesRegex(guard.LoadCancelled, 'conversion exceeds'):
            self.convert(self.source, device=torch.device('xpu:2'))

    def test_cross_device_conversion_still_refuses_oversized_conversion(self):
        with self.assertRaisesRegex(guard.LoadCancelled, 'conversion exceeds'):
            self.convert(self.wrap(self.source), device=torch.device('xpu:3'))

    def test_host_dtype_conversion_still_refuses_oversized_conversion(self):
        with self.assertRaisesRegex(guard.LoadCancelled, 'conversion exceeds'):
            self.convert(self.source, dtype=torch.bfloat16)

    def test_meta_metadata_has_no_payload_or_staging(self):
        for source in (self.source, self.wrap(self.source)):
            out = self.convert(source, device=torch.device('meta'))
            self.assertEqual(out.device.type, 'meta')
            self.assertEqual(out.shape, self.source.shape)
        self.assertFalse((self.root/'staging-live.json').exists())

    def test_cancellation_still_blocks_device_only_conversion(self):
        (self.root/'STOP').write_text('test')
        with self.assertRaises(guard.LoadCancelled):
            self.convert(self.wrap(self.source), dtype=torch.bfloat16)

    def test_small_host_conversion_retains_reservation_until_storage_dies(self):
        out = self.convert(self.source[:4], dtype=torch.bfloat16)
        state = lambda: json.loads((self.root/'staging-live.json').read_text())
        self.assertEqual(sum(v['bytes'] for v in state()['live'].values()), 24)
        del out
        gc.collect()
        self.assertEqual(state()['live'], {})


if __name__ == '__main__':
    unittest.main()
