#!/usr/bin/env python3
"""Verify the default-off M1 W13-N32 tuned-map integration.

This helper performs no inference.  It binds the candidate map to the retained
M1 map, verifies that their sole semantic difference is the nested W13 N32
delta at key 1, and asks the live vLLM resolver to prove that W2, non-M1, and
legacy callers retain their prior configurations.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any


CONFIG_NAME = (
    "E=128,N=640,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,"
    "dtype=fp8_w8a8,block_shape=[128,128].json"
)
EXPECTED_BASE_CONFIG_SHA256 = (
    "91e5d8b692da3febbba7cb07ee4fdab319909da0c82c1fda95b92dc42d680464"
)
EXPECTED_CANDIDATE_CONFIG_SHA256 = (
    "a8f1f8982e3e1af80ff31b9e0a00afaacf1af1b3c401585109b4d60d3c8267be"
)
EXPECTED_FUSED_MOE_SHA256 = (
    "4b376eb5e22e7972a1d70e4012999650ab961719d6309cbec27a6104fa64d0a0"
)
EXPECTED_TRITON_MOE_SHA256 = (
    "b8a461b712b88cf6ab5ba4f49029fddce3a501f7ff909b276b6de04b808da4c2"
)
EXPECTED_MODULAR_KERNEL_SHA256 = (
    "1e60aca6ed0dd4fcb46d577897ff1651f27a6130b3449d22265c0c791beec5d5"
)
# Overlay heads whose MoE sources carry the per-phase config door. Later
# diagnostic commits (repeatability-trace records, Q38_ trace aliases, the
# VLLM_XPU_MKLDNN_DETERMINISTIC worker flag) leave the three hashed MoE files
# untouched, which validate_source() still proves independently.
EXPECTED_VLLM_HEADS = frozenset(
    {
        "cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9",
        "805cde592dfe198a82deaba52894ebfc0e4a4352",
        # + V2 runner CUDAGraphStat receipt (no MoE change)
        "2169dbfe38c2954edc5ae50e94f68d45be071b79",
        # 1b2a17c1: the exact-verify MTP1 selectors (serial GDN rows, row-wise
        # all-reduce, row-wise HC norm) on the 2169dbfe line; MoE map untouched.
        "1b2a17c1e7c41985d6a5e0eb324ada4775c25e60",
    }
)
EXPECTED_PHASE_CONFIG_PATCH_NAME = "0021-Add-opt-in-per-phase-Triton-MoE-configs.patch"
EXPECTED_PHASE_CONFIG_PATCH_SHA256 = (
    "ad820bad443bba32f15b114ea76b4deb4dade754fe1bc362faddfef07eb6c519"
)
EXPECTED_KEYS = (1, 4, 8, 16, 32, 64, 128)
W13_DELTA = {"BLOCK_SIZE_N": 32}


class IntegrationContractError(RuntimeError):
    """Raised when the integration is broader than the confirmed treatment."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_map(raw: Any, *, label: str) -> dict[int, dict[str, Any]]:
    if not isinstance(raw, dict):
        raise IntegrationContractError(f"{label} map must be an object")
    try:
        result = {int(key): value for key, value in raw.items()}
    except (TypeError, ValueError) as exc:
        raise IntegrationContractError(
            f"{label} map contains a noninteger key"
        ) from exc
    if tuple(sorted(result)) != EXPECTED_KEYS:
        raise IntegrationContractError(
            f"{label} map keys drifted: {tuple(sorted(result))}"
        )
    if not all(isinstance(value, dict) for value in result.values()):
        raise IntegrationContractError(f"{label} entries must be objects")
    return result


def validate_maps(
    base_raw: Any, candidate_raw: Any
) -> tuple[dict[int, dict[str, Any]], dict[int, dict[str, Any]]]:
    base = normalize_map(base_raw, label="base")
    candidate = normalize_map(candidate_raw, label="candidate")
    if any("W1_CONFIG" in value or "W2_CONFIG" in value for value in base.values()):
        raise IntegrationContractError("retained base unexpectedly has phase deltas")
    if candidate[1].get("W1_CONFIG") != W13_DELTA:
        raise IntegrationContractError("key 1 lacks the exact W13 N32 delta")
    if "W2_CONFIG" in candidate[1]:
        raise IntegrationContractError("key 1 must not change W2")

    flattened_m1 = copy.deepcopy(candidate[1])
    flattened_m1.pop("W1_CONFIG", None)
    if flattened_m1 != base[1]:
        raise IntegrationContractError("key 1 changes fields beyond W13 N32")
    for key in EXPECTED_KEYS[1:]:
        if candidate[key] != base[key]:
            raise IntegrationContractError(f"non-M1 key {key} changed")
        if "W1_CONFIG" in candidate[key] or "W2_CONFIG" in candidate[key]:
            raise IntegrationContractError(f"non-M1 key {key} has a phase delta")
    return base, candidate


def select_key(configs: dict[int, dict[str, Any]], requested_m: int) -> int:
    return min(configs, key=lambda key: abs(key - requested_m))


def resolve_phase_entry(
    entry: dict[str, Any], *, requested_m: int, enable_phase_configs: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Small independent authority for the frozen resolver contract."""
    raw = copy.deepcopy(entry)
    w1_delta = raw.pop("W1_CONFIG", None)
    w2_delta = raw.pop("W2_CONFIG", None)
    if not enable_phase_configs or requested_m != 1:
        return raw, raw.copy()
    w1 = raw | (w1_delta or {})
    w2 = raw | (w2_delta or {})
    return w1, w2


def expected_resolution(
    base: dict[int, dict[str, Any]],
    candidate: dict[int, dict[str, Any]],
    requested_m: int,
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    candidate_key = select_key(candidate, requested_m)
    base_key = select_key(base, requested_m)
    if candidate_key != base_key:
        raise IntegrationContractError("candidate changes nearest-key selection")
    w1, w2 = resolve_phase_entry(
        candidate[candidate_key], requested_m=requested_m, enable_phase_configs=True
    )
    if requested_m == 1:
        if w1 != base[base_key] | W13_DELTA or w2 != base[base_key]:
            raise IntegrationContractError("M1 phase resolution is not W13-only N32")
    elif w1 != base[base_key] or w2 != base[base_key]:
        raise IntegrationContractError(f"M={requested_m} behavior changed")
    return candidate_key, w1, w2


def read_bound_map(path: Path, expected_sha256: str, *, label: str) -> Any:
    if path.name != CONFIG_NAME:
        raise IntegrationContractError(f"{label} config filename drifted")
    if sha256_file(path) != expected_sha256:
        raise IntegrationContractError(f"{label} config hash drifted")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_source(vllm_source: Path) -> dict[str, str]:
    paths = {
        "fused_moe": vllm_source / "vllm/model_executor/layers/fused_moe/fused_moe.py",
        "triton_moe": vllm_source
        / "vllm/model_executor/layers/fused_moe/experts/triton_moe.py",
        "modular_kernel": vllm_source
        / "vllm/model_executor/layers/fused_moe/modular_kernel.py",
    }
    expected = {
        "fused_moe": EXPECTED_FUSED_MOE_SHA256,
        "triton_moe": EXPECTED_TRITON_MOE_SHA256,
        "modular_kernel": EXPECTED_MODULAR_KERNEL_SHA256,
    }
    actual = {name: sha256_file(path) for name, path in paths.items()}
    if actual != expected:
        raise IntegrationContractError(f"vLLM source contract drifted: {actual}")
    return actual


def validate_prerequisite(
    vllm_source: Path, phase_config_patch: Path
) -> dict[str, str]:
    if phase_config_patch.name != EXPECTED_PHASE_CONFIG_PATCH_NAME:
        raise IntegrationContractError("per-phase config patch filename drifted")
    patch_sha256 = sha256_file(phase_config_patch)
    if patch_sha256 != EXPECTED_PHASE_CONFIG_PATCH_SHA256:
        raise IntegrationContractError("per-phase config patch hash drifted")
    try:
        head = subprocess.run(
            ["git", "-C", str(vllm_source), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise IntegrationContractError("could not resolve vLLM source head") from exc
    if head not in EXPECTED_VLLM_HEADS:
        raise IntegrationContractError(f"vLLM prerequisite head drifted: {head}")
    return {
        "vllm_head": head,
        "phase_config_patch": str(phase_config_patch),
        "phase_config_patch_sha256": patch_sha256,
    }


def build_receipt(
    base_config_file: Path,
    candidate_config_file: Path,
    vllm_source: Path,
    phase_config_patch: Path,
) -> dict[str, Any]:
    base_config_file = base_config_file.resolve()
    candidate_config_file = candidate_config_file.resolve()
    vllm_source = vllm_source.resolve()
    phase_config_patch = phase_config_patch.resolve()
    if os.environ.get("VLLM_TUNED_CONFIG_FOLDER") != str(candidate_config_file.parent):
        raise IntegrationContractError(
            "live tuned-config folder differs from candidate"
        )

    base_raw = read_bound_map(
        base_config_file, EXPECTED_BASE_CONFIG_SHA256, label="base"
    )
    candidate_raw = read_bound_map(
        candidate_config_file,
        EXPECTED_CANDIDATE_CONFIG_SHA256,
        label="candidate",
    )
    base, candidate = validate_maps(base_raw, candidate_raw)
    source_hashes = validate_source(vllm_source)
    prerequisite = validate_prerequisite(vllm_source, phase_config_patch)

    expected_by_m = {
        requested_m: expected_resolution(base, candidate, requested_m)
        for requested_m in range(1, 513)
    }

    from vllm.model_executor.layers.fused_moe.fused_moe import (
        get_moe_configs,
        try_get_optimal_moe_config,
        try_get_optimal_moe_gemm_configs,
    )

    get_moe_configs.cache_clear()
    shapes = ((128, 1280, 2560), (128, 2560, 640))
    for requested_m, (_, expected_w1, expected_w2) in expected_by_m.items():
        actual_w1, actual_w2 = try_get_optimal_moe_gemm_configs(
            *shapes, 10, "fp8_w8a8", requested_m, [128, 128]
        )
        if actual_w1 != expected_w1 or actual_w2 != expected_w2:
            raise IntegrationContractError(
                f"official phase resolver drifted at M={requested_m}"
            )
    legacy = try_get_optimal_moe_config(*shapes, 10, "fp8_w8a8", 1, [128, 128])
    if legacy != base[1]:
        raise IntegrationContractError("legacy M1 caller inherited a phase delta")

    key, w1, w2 = expected_by_m[1]
    return {
        "schema_version": 1,
        "status": "pass",
        "classification": "qwen38_m1_w13_n32_static_integration_receipt",
        "candidate_scope": "xpu_block_fp8_modular_m1_w13_only",
        "selected_batch_key": key,
        "m1": {"w13": w1, "w2": w2},
        "preservation": {
            "all_integer_m_2_through_512_match_retained_map": True,
            "legacy_m1_matches_retained_map": True,
            "w2_matches_retained_m1": True,
            "non_m1_map_entries_semantically_equal": True,
        },
        "config": {
            "base_path": str(base_config_file),
            "base_sha256": EXPECTED_BASE_CONFIG_SHA256,
            "candidate_path": str(candidate_config_file),
            "candidate_sha256": EXPECTED_CANDIDATE_CONFIG_SHA256,
        },
        "source_sha256": source_hashes,
        "prerequisite": prerequisite,
        "not_inference_evidence": True,
    }


def write_exclusive(path: Path, payload: dict[str, Any]) -> None:
    path = path.resolve()
    if path.exists():
        raise IntegrationContractError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-config-file", type=Path, required=True)
    parser.add_argument("--candidate-config-file", type=Path, required=True)
    parser.add_argument("--vllm-source", type=Path, required=True)
    parser.add_argument("--phase-config-patch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_exclusive(
        args.output,
        build_receipt(
            args.base_config_file,
            args.candidate_config_file,
            args.vllm_source,
            args.phase_config_patch,
        ),
    )


if __name__ == "__main__":
    main()
