"""CPU-only ownership, routing, lifetime and rejection checks."""
import sys
import unittest
from pathlib import Path

SOURCE = Path("/home/steve/src/ComfyUI-ltx25-baseline")
sys.path.insert(0, str(SOURCE))
sys.argv = [sys.argv[0], "--cpu", "--disable-dynamic-vram"]
import comfy.options
comfy.options.enable_args_parsing()
import torch
from torch import nn
from comfy.model_patcher import ModelPatcher
from comfy.patcher_extension import CallbacksMP, WrappersMP
from ltx_layer_shard import (
    CACHE_KEY, KEY, CompressedTimestep, LTXLayerShardedPatcher,
    _BlockRoute, _forward_transfers, _move, _tensors,
)


class TinyDiffusion(nn.Module):
    def __init__(self):
        super().__init__()
        self.transformer_blocks = nn.ModuleList([nn.Linear(3, 3, dtype=torch.bfloat16) for _ in range(4)])
        self.proj = nn.Linear(3, 3, dtype=torch.bfloat16)


class TinyModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.diffusion_model = TinyDiffusion()

    def get_dtype(self):
        return torch.bfloat16


def fresh():
    return ModelPatcher(TinyModel(), torch.device("cpu"), torch.device("cpu"))


def install_cpu(patcher):
    return LTXLayerShardedPatcher.install(patcher, torch.device("cpu"), torch.device("cpu"), 2)


class ShardTests(unittest.TestCase):
    def test_ownership_exactness_and_clone(self):
        patcher = fresh()
        original = {id(t): t.detach().clone() for t in _tensors(patcher.model)}
        blocks = tuple(patcher.model.diffusion_model.transformer_blocks)
        install_cpu(patcher)
        shard, = patcher.get_additional_models_with_key(KEY)
        primary_ids = {id(t) for t in _tensors(patcher.model)}
        secondary_ids = {id(t) for t in _tensors(shard.model)}
        self.assertFalse(primary_ids & secondary_ids)
        self.assertEqual(primary_ids | secondary_ids, set(original))
        self.assertEqual(tuple(patcher.model.diffusion_model.transformer_blocks), blocks)
        for t in _tensors(patcher.model) + _tensors(shard.model):
            self.assertTrue(torch.equal(t, original[id(t)]))
        identity = patcher.model.diffusion_model._ltx_layer_shard_identity
        self.assertEqual(identity["primary_bytes"] + identity["secondary_bytes"], identity["original_bytes"])
        clone = patcher.clone()
        self.assertIs(clone.model, patcher.model)
        self.assertIs(clone.get_additional_models_with_key(KEY)[0].model, shard.model)
        clone.verify_placement()
        with self.assertRaises(RuntimeError):
            install_cpu(patcher)
        with self.assertRaises(RuntimeError):
            patcher.clone(force_deepcopy=True)

    def test_existing_block_arithmetic_unchanged(self):
        patcher = install_cpu(fresh())
        blocks = patcher.model.diffusion_model.transformer_blocks
        routes = patcher.model_options["transformer_options"]["patches_replace"]["dit"]
        x = torch.ones((1, 3), dtype=torch.bfloat16)
        expected = x
        for block in blocks:
            expected = block(expected)

        def execute(*args):
            actual = x
            options = args[5]
            for i, block in enumerate(blocks):
                result = routes[("double_block", i)](
                    {"img": (actual, actual), "transformer_options": options},
                    {"original_block": lambda a, b=block: {"img": (b(a["img"][0]), a["img"][1])}})
                actual = result["img"][0]
            return actual

        actual = _forward_transfers(execute, None, None, None, None, None, {})
        self.assertTrue(torch.equal(actual, expected))

    def test_compressed_timestep_and_transfer_cache(self):
        data = torch.arange(24, dtype=torch.float32).reshape(1, 2, 12)
        source = CompressedTimestep(data, 4, per_frame=True)
        cpu = _move(source, torch.device("cpu"), {})
        self.assertEqual(cpu.patches_per_frame, 4)
        self.assertEqual(cpu.num_frames, 2)
        self.assertTrue(torch.equal(cpu.expand(), source.expand()))
        # Meta performs no accelerator work; exercise the actual transfer branch.
        cache = {}
        moved = _move({"compressed": source, "same": data}, torch.device("meta"), cache)
        self.assertIs(moved["compressed"].data, moved["same"])
        self.assertEqual(moved["compressed"].data.dtype, data.dtype)
        self.assertEqual(moved["compressed"].expand().shape, source.expand().shape)
        self.assertIs(cache[(id(data), torch.device("meta"))][0], data)

    def test_forward_cache_cleared_on_exception(self):
        original_options = {"sample_sigmas": torch.ones(2)}
        observed = []

        def fail(*args):
            cache = args[5][CACHE_KEY]
            observed.append(cache)
            cache["temporary"] = torch.ones(5)
            raise ValueError("deliberate CPU test")

        with self.assertRaises(ValueError):
            _forward_transfers(fail, None, None, None, None, None, original_options)
        self.assertEqual(observed, [{}])
        self.assertNotIn(CACHE_KEY, original_options)

    def test_wrong_placement_rejected(self):
        patcher = install_cpu(fresh())
        shard, = patcher.get_additional_models_with_key(KEY)
        shard.load_device = torch.device("xpu:1")
        with self.assertRaises(RuntimeError):
            patcher.verify_placement()

    def test_detach_then_native_load_keeps_ownership(self):
        patcher = install_cpu(fresh())
        shard, = patcher.get_additional_models_with_key(KEY)
        for part in (patcher, shard):
            part.load(torch.device("cpu"), full_load=True)
            self.assertEqual(part.loaded_size(), part.model_size())
        patcher.verify_placement()
        for part in (patcher, shard):
            part.detach()
            self.assertEqual(part.loaded_size(), 0)
        self.assertEqual(len(tuple(patcher.model.diffusion_model.transformer_blocks)), 4)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
