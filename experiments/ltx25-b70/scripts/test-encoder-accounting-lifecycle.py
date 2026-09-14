#!/usr/bin/env python3
"""Real tiny-parameter ModelPatcher lifecycle checks; CPU only, no core edits."""

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

SOURCE = Path("/home/steve/src/ComfyUI-ltx25-baseline")
LANE = Path(__file__).resolve().parents[1]
PIN = "19e1058f4c445ef74047e77a23f9ca7684c1e4b6"
sys.path.insert(0, str(SOURCE))
sys.argv = [sys.argv[0], "--cpu", "--disable-dynamic-vram", "--disable-pinned-memory", "--disable-async-offload"]

import comfy.options
comfy.options.enable_args_parsing()
import torch
from torch import nn
import comfy.model_patcher as patcher_module
import comfy.ops

ModelPatcher = patcher_module.ModelPatcher
CPU = torch.device("cpu")

# Import only the previous CPU harness's pure helpers; its main is not run.
spec = importlib.util.spec_from_file_location("encoder_candidate_cpu_helpers", LANE / "scripts/test-encoder-candidates.py")
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
source_name = "comfy/model_patcher.py"
pinned_source = subprocess.check_output(["git", "-C", str(SOURCE), "show", f"{PIN}:{source_name}"], text=True)
if (SOURCE / source_name).read_text() != pinned_source:
    raise RuntimeError("Imported ModelPatcher differs from the pinned source; refuse a mixed identity")
patch_path = LANE / "patches/encoder-resident-accounting.patch"
candidate_source = helpers.apply_patch_in_memory({source_name: pinned_source}, patch_path.read_text())[source_name]
# The subclass uses the patched load method and all actual upstream lifecycle
# implementations/globals. The imported ModelPatcher class is never modified.
candidate_load = helpers.extract(candidate_source, "ModelPatcher", dict(vars(patcher_module)), "load")


class CandidatePatcher(ModelPatcher):
    load = candidate_load


class TinyModel(nn.Module):
    def __init__(self, mixed=False):
        super().__init__()
        self.layers = nn.ModuleList([
            comfy.ops.manual_cast.Linear(8, 8, bias=True, dtype=torch.bfloat16, device=CPU)
            for _ in range(4)
        ])
        if mixed:
            self.norm = nn.LayerNorm(8, dtype=torch.bfloat16, device=CPU)
        with torch.no_grad():
            for index, parameter in enumerate(self.parameters()):
                parameter.fill_((index + 1) / 128)

    def get_dtype(self):
        return torch.bfloat16

    def forward(self, x):
        for layer in self.layers:
            x = layer(x)
        if hasattr(self, "norm"):
            x = self.norm(x)
        return x


def make(candidate=True, mixed=False):
    return (CandidatePatcher if candidate else ModelPatcher)(TinyModel(mixed), CPU, CPU)


def weight_hashes(patcher):
    return {name: hashlib.sha256(parameter.detach().contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()
            for name, parameter in patcher.model.named_parameters()}


def evaluate(patcher):
    with torch.inference_mode():
        return patcher.model(torch.arange(16, dtype=torch.bfloat16).reshape(2, 8) / 16).clone()


def marked_loaded_bytes(patcher):
    return sum(sum(p.numel() * p.element_size() for p in module.parameters(recurse=False))
               for module in patcher.model.modules() if getattr(module, "comfy_patched_weights", False))


class LifecycleTests(unittest.TestCase):
    # Each real Linear owns 144 bytes. 433 admits two modules plus a cast
    # reserve. CPU load/offload use the same physical device, so the counters
    # describe lifecycle bookkeeping; they cannot prove XPU residency.
    budget = 433

    def assert_cpu(self, patcher):
        self.assertTrue(all(p.device.type == "cpu" for p in patcher.model.parameters()))

    def test_actual_partial_load_repeats_preserve_bytes_and_output(self):
        candidate = make()
        hashes, output = weight_hashes(candidate), evaluate(candidate)
        candidate.load(CPU, lowvram_model_memory=self.budget)
        self.assertEqual(candidate.loaded_size(), 288)
        for _ in range(5):
            candidate.partially_load(CPU, extra_memory=0.1)
            self.assertEqual(candidate.loaded_size(), marked_loaded_bytes(candidate))
            self.assertEqual(candidate.loaded_size(), 288)
            self.assertEqual(weight_hashes(candidate), hashes)
            self.assertTrue(torch.equal(evaluate(candidate), output))
        self.assert_cpu(candidate)

    def test_original_real_parameters_reproduce_counter_disagreement(self):
        control = make(candidate=False)
        hashes = weight_hashes(control)
        control.load(CPU, lowvram_model_memory=self.budget)
        control.partially_load(CPU, extra_memory=0.1)
        self.assertLess(control.loaded_size(), marked_loaded_bytes(control))
        self.assertEqual(weight_hashes(control), hashes)

    def test_partial_unload_then_full_reload(self):
        candidate = make()
        hashes, output = weight_hashes(candidate), evaluate(candidate)
        candidate.load(CPU, lowvram_model_memory=self.budget)
        self.assertEqual(candidate.partially_unload(CPU, memory_to_free=1), 144)
        self.assertEqual(candidate.loaded_size(), 144)
        self.assertEqual(candidate.loaded_size(), marked_loaded_bytes(candidate))
        candidate.partially_load(CPU, extra_memory=0.1)
        self.assertEqual(candidate.loaded_size(), 144)
        candidate.partially_load(CPU, extra_memory=1e9)
        self.assertEqual(candidate.loaded_size(), candidate.model_size())
        self.assertEqual(weight_hashes(candidate), hashes)
        self.assertTrue(torch.equal(evaluate(candidate), output))

    def test_detach_and_reload_preserve_parameters(self):
        candidate = make()
        hashes, output = weight_hashes(candidate), evaluate(candidate)
        candidate.load(CPU, lowvram_model_memory=self.budget)
        candidate.detach()
        self.assertEqual(candidate.loaded_size(), 0)
        self.assertEqual(marked_loaded_bytes(candidate), 0)
        self.assertEqual(weight_hashes(candidate), hashes)
        candidate.partially_load(CPU, extra_memory=self.budget)
        self.assertEqual(candidate.loaded_size(), 288)
        self.assertTrue(torch.equal(evaluate(candidate), output))

    def test_uuid_change_applies_patch_like_upstream_full_load(self):
        candidate, control = make(), make(candidate=False)
        base_hashes = weight_hashes(candidate)
        candidate.load(CPU, lowvram_model_memory=self.budget)
        old_uuid = candidate.patches_uuid
        delta = torch.full_like(candidate.model.layers[0].weight, 1 / 128)
        for patcher in (candidate, control):
            accepted = patcher.add_patches({"layers.0.weight": (delta,)})
            self.assertEqual(accepted, ["layers.0.weight"])
        self.assertNotEqual(candidate.patches_uuid, old_uuid)
        candidate.partially_load(CPU, extra_memory=1e9, force_patch_weights=True)
        control.patch_model(CPU)
        self.assertEqual(candidate.model.current_weight_patches_uuid, candidate.patches_uuid)
        self.assertEqual(weight_hashes(candidate), weight_hashes(control))
        self.assertTrue(torch.equal(evaluate(candidate), evaluate(control)))
        self.assertNotEqual(weight_hashes(candidate), base_hashes)
        candidate.detach()
        self.assertEqual(weight_hashes(candidate), base_hashes)

    def test_forced_patch_reload_does_not_apply_delta_twice(self):
        candidate = make()
        base_hashes = weight_hashes(candidate)
        delta = torch.full_like(candidate.model.layers[0].weight, 1 / 128)
        candidate.add_patches({"layers.0.weight": (delta,)})
        candidate.partially_load(CPU, extra_memory=1e9, force_patch_weights=True)
        hashes, output = weight_hashes(candidate), evaluate(candidate)
        for _ in range(2):
            candidate.partially_load(CPU, extra_memory=1e9, force_patch_weights=True)
            self.assertEqual(weight_hashes(candidate), hashes)
            self.assertTrue(torch.equal(evaluate(candidate), output))
            self.assertEqual(candidate.loaded_size(), candidate.model_size())
        candidate.detach()
        self.assertEqual(weight_hashes(candidate), base_hashes)

    def test_mixed_leaf_module_partial_and_full_lifecycle(self):
        candidate = make(mixed=True)
        hashes, output = weight_hashes(candidate), evaluate(candidate)
        candidate.load(CPU, lowvram_model_memory=self.budget)
        for _ in range(3):
            candidate.partially_load(CPU, extra_memory=0.1)
            self.assertEqual(candidate.loaded_size(), marked_loaded_bytes(candidate))
            self.assertEqual(weight_hashes(candidate), hashes)
            self.assertTrue(torch.equal(evaluate(candidate), output))
        candidate.partially_unload(CPU, memory_to_free=1)
        candidate.partially_load(CPU, extra_memory=1e9)
        self.assertEqual(candidate.loaded_size(), candidate.model_size())
        candidate.detach()
        self.assertEqual(weight_hashes(candidate), hashes)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LifecycleTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"source_commit": PIN,
                      "patch_sha256": hashlib.sha256(patch_path.read_bytes()).hexdigest(),
                      "tests_run": result.testsRun, "passed": result.wasSuccessful(),
                      "evidence_scope": "Real BF16 CPU parameters and actual ModelPatcher lifecycle; no GPU residency proof"}, indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
