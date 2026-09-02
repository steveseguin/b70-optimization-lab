#!/usr/bin/env python3
"""Run the frozen W13 component gate from an actual tuned-config folder."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASE_GATE_PATH = HERE / "w13-m1-xpu-graph-gate.py"
VERIFIER_PATH = HERE / "verify-moe-m1-w13-n32-selection.py"
BASE_GATE_SHA256 = "8828a3b42766a96f014299967af94cbde48410abd92d64183685dbf737ce05a1"
VERIFIER_SHA256 = "a464b0f6a46e9149b33e5ccca772bf21385532693e78b691ca010a7833be2e6f"
BASE_FOLDER = REPO / "experiments/qwen38-flash-next-fp8-b70/configs/moe-warps8-m1"
CANDIDATE_FOLDER = REPO / "experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32"
PHASE_PATCH = (
    REPO
    / "patches/qwen38-flash-next-fp8-b70/vllm/0021-Add-opt-in-per-phase-Triton-MoE-configs.patch"
)
VLLM_SOURCE = Path("/home/steve/src/vllm-current-main")
EXPECTED_CANDIDATE = {"W1_CONFIG": {"BLOCK_SIZE_N": 32}}


class FolderSelectionError(RuntimeError):
    """Raised when the runtime folder does not select the frozen treatment."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_exact(name: str, path: Path, expected: str):
    actual = sha256_file(path)
    if actual != expected:
        raise FolderSelectionError(f"{name} drifted: {actual}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise FolderSelectionError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_selection(
    *,
    role: str,
    folder: Path,
    base: dict[int, dict[str, Any]],
    candidate: dict[int, dict[str, Any]],
    actual_w1: dict[str, Any],
    actual_w2: dict[str, Any],
) -> dict[str, Any]:
    if role not in {"control", "candidate"}:
        raise FolderSelectionError(f"invalid folder role: {role}")
    expected_folder = BASE_FOLDER if role == "control" else CANDIDATE_FOLDER
    if folder.resolve() != expected_folder.resolve():
        raise FolderSelectionError(f"{role} folder differs from frozen path")
    expected_entry = base[1]
    expected_w1 = (
        expected_entry if role == "control" else expected_entry | {"BLOCK_SIZE_N": 32}
    )
    if actual_w1 != expected_w1 or actual_w2 != expected_entry:
        raise FolderSelectionError(
            f"{role} resolver output drifted: W13={actual_w1}, W2={actual_w2}"
        )
    selected = base if role == "control" else candidate
    if min(selected, key=lambda key: abs(key - 1)) != 1:
        raise FolderSelectionError("M1 did not select batch key 1")
    return {
        "selected_batch_key": 1,
        "m1": {"w13": actual_w1, "w2": actual_w2},
        "w2_unchanged": actual_w2 == expected_entry,
    }


def resolve_folder_receipt(
    role: str, folder: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    verifier = load_exact("q38_w13_n32_verifier", VERIFIER_PATH, VERIFIER_SHA256)
    gate = load_exact("q38_w13_component_gate", BASE_GATE_PATH, BASE_GATE_SHA256)
    expected_folder = BASE_FOLDER if role == "control" else CANDIDATE_FOLDER
    folder = folder.resolve()
    if os.environ.get("VLLM_TUNED_CONFIG_FOLDER") != str(folder):
        raise FolderSelectionError("VLLM_TUNED_CONFIG_FOLDER does not match --folder")
    if folder != expected_folder.resolve():
        raise FolderSelectionError("selected folder differs from frozen role")

    base_path = BASE_FOLDER / verifier.CONFIG_NAME
    candidate_path = CANDIDATE_FOLDER / verifier.CONFIG_NAME
    base_raw = verifier.read_bound_map(
        base_path, verifier.EXPECTED_BASE_CONFIG_SHA256, label="base"
    )
    candidate_raw = verifier.read_bound_map(
        candidate_path,
        verifier.EXPECTED_CANDIDATE_CONFIG_SHA256,
        label="candidate",
    )
    base, candidate = verifier.validate_maps(base_raw, candidate_raw)
    source_hashes = verifier.validate_source(VLLM_SOURCE)
    prerequisite = verifier.validate_prerequisite(VLLM_SOURCE, PHASE_PATCH)

    from vllm.model_executor.layers.fused_moe.fused_moe import (
        get_moe_configs,
        try_get_optimal_moe_gemm_configs,
    )

    get_moe_configs.cache_clear()
    shapes = ((128, 1280, 2560), (128, 2560, 640))
    actual_w1, actual_w2 = try_get_optimal_moe_gemm_configs(
        *shapes, 10, "fp8_w8a8", 1, [128, 128]
    )
    selected = validate_selection(
        role=role,
        folder=folder,
        base=base,
        candidate=candidate,
        actual_w1=actual_w1,
        actual_w2=actual_w2,
    )
    requested = (
        {}
        if role == "control"
        else {
            "W1_CONFIG": {
                key: value
                for key, value in actual_w1.items()
                if base[1].get(key) != value
            }
        }
    )
    if requested not in ({}, EXPECTED_CANDIDATE):
        raise FolderSelectionError(f"resolved delta is not frozen: {requested}")
    receipt = {
        "schema_version": 1,
        "status": "pass",
        "classification": "qwen38_w13_m1_config_folder_selection_receipt",
        "role": role,
        "environment": {"VLLM_TUNED_CONFIG_FOLDER": str(folder)},
        "config": {
            "path": str(folder / verifier.CONFIG_NAME),
            "sha256": (
                verifier.EXPECTED_BASE_CONFIG_SHA256
                if role == "control"
                else verifier.EXPECTED_CANDIDATE_CONFIG_SHA256
            ),
            "base_sha256": verifier.EXPECTED_BASE_CONFIG_SHA256,
            "candidate_sha256": verifier.EXPECTED_CANDIDATE_CONFIG_SHA256,
        },
        **selected,
        "source_sha256": source_hashes,
        "prerequisite": prerequisite,
        "verifier_sha256": VERIFIER_SHA256,
        "base_gate_sha256": BASE_GATE_SHA256,
    }
    return receipt, {"gate": gate, "requested": requested}


def parse_args() -> tuple[argparse.Namespace, str, Path]:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--folder-role", choices=("control", "candidate"), required=True
    )
    parser.add_argument("--tuned-config-folder", type=Path, required=True)
    parser.add_argument("--candidate-config-json", required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--layer", type=int, choices=range(48), required=True)
    parser.add_argument("--ep-rank", type=int, choices=range(4), required=True)
    parser.add_argument("--control-authority-json", type=Path)
    parser.add_argument("--checkpoint-receipt-json", type=Path, required=True)
    parser.add_argument("--checkpoint-receipt-sha256", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--hidden-scale", type=float, required=True)
    parser.add_argument("--capture-warmups", type=int, required=True)
    parser.add_argument("--timing-warmups", type=int, required=True)
    parser.add_argument("--timing-batches", type=int, required=True)
    parser.add_argument("--iterations-per-batch", type=int, required=True)
    args = parser.parse_args()
    return args, args.folder_role, args.tuned_config_folder


def main() -> None:
    args, role, folder = parse_args()
    declared = json.loads(args.candidate_config_json)
    expected_declared = {} if role == "control" else EXPECTED_CANDIDATE
    if declared != expected_declared:
        raise FolderSelectionError("runner role/config declaration mismatch")
    receipt, resolved = resolve_folder_receipt(role, folder)
    gate = resolved["gate"]
    del args.folder_role, args.tuned_config_folder
    args.candidate_config_json = json.dumps(
        resolved["requested"], separators=(",", ":"), sort_keys=True
    )
    result = gate.run(args)
    result["folder_selection_receipt"] = receipt
    print(json.dumps(result, sort_keys=True, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
