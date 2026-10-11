"""Production wrappers with CPU native-op doubles; no XPU qualification claim."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

import torch

from test_boundary import BoundaryTests, extract

HERE = Path(__file__).resolve().parent
LANE = HERE.parent
FIX = LANE / "overlay-fix-router-padding"
ROUTERS = "vllm/model_executor/layers/fused_moe/router"
NAMES = ("fused_topk_router.py", "fused_topk_bias_router.py")
BAD_HASH = "2b6e99ee899e1515e0cc44b220424cd9da6906b39490504bdcca2236755db51c"


def wrappers(path, mask, *, xpu=True, skip=True, context=True):
    """Execute actual helpers/wrappers. Model only the native padding contract."""
    def topk(weights, ids, source_rows, logits, renormalize, *args, **kwargs):
        # Same deterministic CPU routing on each arm, including tied logits.
        probs = logits.softmax(-1)
        values, indices = probs.topk(ids.shape[1], dim=-1)
        if renormalize:
            values = values / values.sum(-1, keepdim=True)
        padding = kwargs.get("is_padding")
        if padding is not None:
            values = values.masked_fill(padding[:, None], 0)
            indices = indices.masked_fill(padding[:, None], -1)
        weights.copy_(values)
        ids.copy_(indices)
        source_rows.copy_(torch.arange(ids.numel()).view_as(ids))

    ns = dict(torch=torch, os=os,
              current_platform=types.SimpleNamespace(is_xpu=lambda: xpu),
              envs=types.SimpleNamespace(VLLM_MOE_SKIP_PADDING=skip),
              is_forward_context_available=lambda: context,
              get_forward_context=lambda: types.SimpleNamespace(is_padding=mask),
              ops=types.SimpleNamespace(topk_softmax=topk))
    extract(path, "_get_padding_mask", ns)
    extract(path, "vllm_topk_softmax", ns)
    return ns


def route(ns, logits):
    shape = (len(logits), 10)
    weights = torch.empty(shape, dtype=torch.float32)
    ids = torch.empty(shape, dtype=torch.int32)
    source = torch.empty_like(ids)
    ns["vllm_topk_softmax"](weights, ids, source, logits, True)
    return weights, ids


def checked_native_addresses(ids):
    # 0.1.14.1 E=512 path: only `id >= num_experts` is skipped;
    # _count_and_sort_expert_tokens then accesses cumsum_buffer[id].
    for expert in ids.flatten().tolist():
        if expert >= 512:
            continue
        if expert < 0:
            raise IndexError(f"native cumsum_buffer[{expert}] precedes allocation")


class RouterPadding(unittest.TestCase):
    def test_profile_reproduces_all_four_receipt_hashes_and_fix(self):
        logits = torch.arange(64 * 512, dtype=torch.float32).reshape(64, 512) % 37
        for name in NAMES:
            with self.subTest(router=name), patch.dict(os.environ, B70_SCREEN1B="1"):
                mask = torch.ones(64, dtype=torch.bool)
                before = wrappers(FIX / "base-runtime" / ROUTERS / name, mask)
                after = wrappers(LANE / "overlay" / ROUTERS / name, mask)
                weights, ids = route(before, logits)
                self.assertEqual(hashlib.sha256(ids.numpy().tobytes()).hexdigest(), BAD_HASH)
                self.assertTrue(torch.equal(weights, torch.zeros_like(weights)))
                with self.assertRaisesRegex(IndexError, r"cumsum_buffer\[-1\]"):
                    checked_native_addresses(ids)
                fixed_weights, fixed_ids = route(after, logits)
                checked_native_addresses(fixed_ids)
                self.assertTrue(((fixed_ids >= 0) & (fixed_ids < 512)).all())
                self.assertTrue(torch.isfinite(fixed_weights).all())
                self.assertTrue(mask.all())  # Never mutate shared InputBatch state.

    def test_mixed_padding_preserves_active_ids_weights_and_ordered_output(self):
        generator = torch.Generator().manual_seed(1105)
        logits = torch.randn(64, 512, generator=generator)
        mask = torch.arange(64) % 3 == 0
        expert_output = torch.randn(512, 17, generator=generator)
        for name in NAMES:
            with self.subTest(router=name), patch.dict(os.environ, B70_SCREEN1B="1"):
                w0, i0 = route(wrappers(FIX / "base-runtime" / ROUTERS / name, mask), logits)
                w1, i1 = route(wrappers(LANE / "overlay" / ROUTERS / name, mask), logits)
                self.assertEqual(i0[~mask].numpy().tobytes(), i1[~mask].numpy().tobytes())
                self.assertEqual(w0[~mask].numpy().tobytes(), w1[~mask].numpy().tobytes())
                # EP maps all 512 globals into four consecutive 128-row shards.
                for rank in range(4):
                    mapping = torch.full((512,), -1, dtype=torch.int32)
                    mapping[rank*128:(rank+1)*128] = torch.arange(128)
                    self.assertTrue(torch.equal(mapping[i0[~mask]], mapping[i1[~mask]]))
                out0 = (expert_output[i0[~mask]] * w0[~mask, :, None]).sum(1)
                out1 = (expert_output[i1[~mask]] * w1[~mask, :, None]).sum(1)
                self.assertEqual(out0.numpy().tobytes(), out1.numpy().tobytes())
                checked_native_addresses(i1)

    def test_unpadded_inputs_bit_identical_including_ties(self):
        for name in NAMES:
            for mask in (None, torch.zeros(64, dtype=torch.bool)):
                with self.subTest(router=name, mask=mask is None), patch.dict(os.environ, B70_SCREEN1B="1"):
                    logits = torch.zeros(64, 512)
                    old = route(wrappers(FIX / "base-runtime" / ROUTERS / name, mask), logits)
                    new = route(wrappers(LANE / "overlay" / ROUTERS / name, mask), logits)
                    for a, b in zip(old, new):
                        self.assertEqual(a.numpy().tobytes(), b.numpy().tobytes())

    def test_scope_and_upstream_mask_semantics(self):
        mask = torch.tensor([False, True, True])
        for name in NAMES:
            path = LANE / "overlay" / ROUTERS / name
            for screen, xpu, skip, context in (
                ("0", True, True, True), ("1", False, True, True),
                ("0", True, False, True), ("0", True, True, False),
                ("1", True, True, True), ("1", True, False, True),
            ):
                with self.subTest(router=name, screen=screen, xpu=xpu, skip=skip, context=context), patch.dict(os.environ, B70_SCREEN1B=screen):
                    got = wrappers(path, mask, xpu=xpu, skip=skip, context=context)["_get_padding_mask"](2)
                    if (screen == "1" and xpu) or not skip or not context:
                        self.assertIsNone(got)
                    else:
                        self.assertTrue(torch.equal(got, mask[:2]))

    def test_no_other_router_arithmetic_changes(self):
        for name in NAMES:
            before = ast.parse((FIX / "base-runtime" / ROUTERS / name).read_text())
            after = ast.parse((LANE / "overlay" / ROUTERS / name).read_text())
            # Strip only the two added imports and the new first guard.
            after.body = [n for n in after.body if not (
                isinstance(n, ast.Import) and [a.name for a in n.names] == ["os"]
                or isinstance(n, ast.ImportFrom) and n.module == "vllm.platforms")]
            helper = next(n for n in after.body if isinstance(n, ast.FunctionDef) and n.name == "_get_padding_mask")
            helper.body.pop(0)
            self.assertEqual(ast.dump(before), ast.dump(after))

    def test_production_fix_seal_and_exact_patch_replay(self):
        spec = importlib.util.spec_from_file_location("padding_fix_builder", FIX / "build_patch.py")
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        for rel, raw in builder.artifacts().items():
            self.assertEqual((FIX / rel).read_bytes(), raw, rel)
        with tempfile.TemporaryDirectory(prefix="moe-router-patch-") as scratch:
            scratch = Path(scratch)
            pins = json.loads((FIX / "patch-manifest.json").read_text())["files"]
            for rel in pins:
                old = builder.before_bytes(rel)
                if old is not None:
                    path = scratch / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(old)
            subprocess.run(["git", "apply", "--check", str(FIX / "router-padding.patch")], cwd=scratch, check=True)
            subprocess.run(["git", "apply", str(FIX / "router-padding.patch")], cwd=scratch, check=True)
            for rel, pin in pins.items():
                raw = (scratch / rel).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), pin["after_sha256"])
                self.assertEqual(raw, (LANE / rel).read_bytes())


class StrictBoundaryAfterFix(BoundaryTests):
    # Reuse fixture setup only; inherited tests stay in their original suite.
    def test_fixed_profile_passes_unchanged_router_boundary_every_rank(self):
        logits = torch.zeros(64, 512)
        with patch.dict(os.environ, B70_SCREEN1B="1"):
            _, ids = route(wrappers(LANE / "overlay" / ROUTERS / NAMES[0], torch.ones(64, dtype=torch.bool)), logits)
        for rank in range(4):
            self.b.rank = rank
            mapping = torch.full((512,), -1, dtype=torch.int32)
            mapping[128*rank:128*(rank+1)] = torch.arange(128)
            state = self.b.router(ids, mapping, 16, 512)
            self.assertEqual(state["routes"], ids.flatten().tolist())


# Only this additional case; avoid duplicating the inherited boundary battery.
for _name in list(dir(StrictBoundaryAfterFix)):
    if _name.startswith("test_") and _name != "test_fixed_profile_passes_unchanged_router_boundary_every_rank":
        setattr(StrictBoundaryAfterFix, _name, None)
del BoundaryTests
