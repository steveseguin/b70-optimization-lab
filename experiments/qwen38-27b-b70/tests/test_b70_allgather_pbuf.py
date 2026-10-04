"""CPU-only check of the persistent-buffer allgather overlay: same sums as the shipped overlay, buffers reused for
small shapes, fresh for large ones, refusal when both overlays are enabled. Stubs vLLM and torch.distributed."""
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class Stub:
    def __init__(self):
        self.gathers = []


def install_stubs(peer_scale):
    """A fake two-rank group: the peer's tensor is `x * peer_scale`."""
    class XpuCommunicator:
        world_size = 2
        device_group = object()

        def all_reduce(self, input_):
            raise AssertionError('original all_reduce must not be called for world size 2')

    logger = types.SimpleNamespace(warning=lambda *a, **k: None)
    mods = {
        'vllm': types.ModuleType('vllm'), 'vllm.logger': types.ModuleType('vllm.logger'),
        'vllm.distributed': types.ModuleType('vllm.distributed'),
        'vllm.distributed.device_communicators': types.ModuleType('vllm.distributed.device_communicators'),
        'vllm.distributed.device_communicators.xpu_communicator': types.ModuleType('xpu_communicator'),
    }
    mods['vllm.logger'].init_logger = lambda name: logger
    mods['vllm.distributed.device_communicators.xpu_communicator'].XpuCommunicator = XpuCommunicator
    mods['vllm.distributed.device_communicators'].xpu_communicator = mods['vllm.distributed.device_communicators.xpu_communicator']
    sys.modules.update(mods)
    seen = []

    def all_gather_into_tensor(out, x, group=None):
        seen.append(id(out))
        out[0].copy_(x); out[1].copy_(x * peer_scale)

    import torch.distributed as dist
    dist.all_gather_into_tensor = all_gather_into_tensor
    return XpuCommunicator, seen


class PbufTest(unittest.TestCase):
    def setUp(self):
        for key in ('B70_ALLGATHER_PBUF', 'B70_ALLGATHER_ALLREDUCE', 'B70_ALLGATHER_PBUF_MAX_ROWS'):
            os.environ.pop(key, None)

    def test_same_sums_and_reuse(self):
        cls, seen = install_stubs(peer_scale=3.0)
        os.environ['B70_ALLGATHER_PBUF'] = '1'
        load('pbuf', HERE / 'overlays/b70-allgather-pbuf/b70_allgather_pbuf.py').register()
        comm = cls()
        torch.manual_seed(0)
        small = [torch.randn(6, 5120, dtype=torch.float16) for _ in range(5)] + [torch.randn(1, 5120, dtype=torch.float16) for _ in range(3)]
        outs = [comm.all_reduce(x) for x in small]
        for x, y in zip(small, outs):
            self.assertTrue(torch.equal(y, x + x * 3.0))          # exactly gathered[0] + gathered[1]
        self.assertEqual(len(set(seen[:5])), 1)                   # one buffer for the five 6x5120 calls
        self.assertEqual(len(set(seen[5:8])), 1)                  # one for the three 1x5120 calls
        self.assertNotEqual(seen[0], seen[5])
        first = outs[0].clone()
        comm.all_reduce(small[1])                                 # reusing the buffer must not disturb an earlier result
        self.assertTrue(torch.equal(outs[0], first))
        big = torch.randn(4096, 8, dtype=torch.float16)
        before = len(seen)
        a, b = comm.all_reduce(big), comm.all_reduce(big)
        self.assertTrue(torch.equal(a, big + big * 3.0) and torch.equal(a, b))
        self.assertEqual(len(seen), before + 2)                   # large inputs take the fresh-buffer path

    def test_refuses_both_overlays(self):
        install_stubs(peer_scale=1.0)
        os.environ['B70_ALLGATHER_PBUF'] = '1'
        os.environ['B70_ALLGATHER_ALLREDUCE'] = '1'
        with self.assertRaises(RuntimeError):
            load('pbuf2', HERE / 'overlays/b70-allgather-pbuf/b70_allgather_pbuf.py').register()

    def test_off_by_default(self):
        cls, _ = install_stubs(peer_scale=1.0)
        load('pbuf3', HERE / 'overlays/b70-allgather-pbuf/b70_allgather_pbuf.py').register()
        self.assertFalse(getattr(cls, '_b70_allgather_pbuf', False))


if __name__ == '__main__':
    unittest.main()
