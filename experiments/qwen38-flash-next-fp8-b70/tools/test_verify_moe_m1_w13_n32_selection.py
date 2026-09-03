#!/usr/bin/env python3
"""CPU-only tests for the W13-N32 tuned-map integration verifier."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


TOOL = Path(__file__).with_name("verify-moe-m1-w13-n32-selection.py")
SPEC = importlib.util.spec_from_file_location("q38_w13_n32_selection", TOOL)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = ROOT / "experiments/qwen38-flash-next-fp8-b70/configs"
BASE = CONFIG_ROOT / "moe-warps8-m1" / MODULE.CONFIG_NAME
CANDIDATE = CONFIG_ROOT / "moe-m1-w13-n32" / MODULE.CONFIG_NAME
VLLM_SOURCE = Path("/home/steve/src/vllm-current-main")
PHASE_CONFIG_PATCH = (
    ROOT
    / "patches/qwen38-flash-next-fp8-b70/vllm/0021-Add-opt-in-per-phase-Triton-MoE-configs.patch"
)


def maps() -> tuple[dict, dict]:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    return base, candidate


class W13N32SelectionTests(unittest.TestCase):
    def test_tracked_maps_have_one_exact_semantic_nested_difference(self) -> None:
        base_raw, candidate_raw = maps()
        base, candidate = MODULE.validate_maps(base_raw, candidate_raw)
        changed = []
        for key in MODULE.EXPECTED_KEYS:
            if base[key] != candidate[key]:
                changed.append(key)
        self.assertEqual(changed, [1])
        self.assertEqual(candidate[1]["W1_CONFIG"], {"BLOCK_SIZE_N": 32})

    def test_m1_changes_only_w13_and_preserves_w2(self) -> None:
        base, candidate = MODULE.validate_maps(*maps())
        key, w13, w2 = MODULE.expected_resolution(base, candidate, 1)
        self.assertEqual(key, 1)
        self.assertEqual(w13, base[1] | {"BLOCK_SIZE_N": 32})
        self.assertEqual(w2, base[1])

    def test_every_integer_non_m1_shape_preserves_retained_behavior(self) -> None:
        base, candidate = MODULE.validate_maps(*maps())
        for requested_m in range(2, 513):
            key, w13, w2 = MODULE.expected_resolution(base, candidate, requested_m)
            self.assertEqual(key, MODULE.select_key(base, requested_m))
            self.assertEqual(w13, base[key])
            self.assertEqual(w2, base[key])

    def test_legacy_or_disabled_phase_resolution_is_flat(self) -> None:
        base, candidate = MODULE.validate_maps(*maps())
        w13, w2 = MODULE.resolve_phase_entry(
            candidate[1], requested_m=1, enable_phase_configs=False
        )
        self.assertEqual(w13, base[1])
        self.assertEqual(w2, base[1])

    def test_phase_config_prerequisite_is_exact(self) -> None:
        receipt = MODULE.validate_prerequisite(VLLM_SOURCE, PHASE_CONFIG_PATCH)
        self.assertIn(receipt["vllm_head"], MODULE.EXPECTED_VLLM_HEADS)
        self.assertEqual(
            receipt["phase_config_patch_sha256"],
            MODULE.EXPECTED_PHASE_CONFIG_PATCH_SHA256,
        )

    def test_rejects_w2_or_non_m1_changes(self) -> None:
        base, candidate = maps()
        with self.subTest("W2"):
            changed = copy.deepcopy(candidate)
            changed["1"]["W2_CONFIG"] = {"BLOCK_SIZE_N": 32}
            with self.assertRaises(MODULE.IntegrationContractError):
                MODULE.validate_maps(base, changed)
        with self.subTest("M4"):
            changed = copy.deepcopy(candidate)
            changed["4"]["num_warps"] = 8
            with self.assertRaises(MODULE.IntegrationContractError):
                MODULE.validate_maps(base, changed)

    def test_receipt_writer_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_text("old\n", encoding="utf-8")
            with self.assertRaisesRegex(MODULE.IntegrationContractError, "overwrite"):
                MODULE.write_exclusive(path, {"status": "new"})


if __name__ == "__main__":
    unittest.main()
