#!/usr/bin/env python3
"""Summarize the W13-N32 actual-config-folder component qualification."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
from typing import Any


HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "summarize-w13-m1-xpu-graph-confirmation-a2.py"
EXPECTED_BASE_SHA256 = (
    "e61b13c08c6738d9e552c10a0f751ffe726216518dd419bc3b08b73667137113"
)
CONFIG_NAME = (
    "E=128,N=640,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,"
    "dtype=fp8_w8a8,block_shape=[128,128].json"
)
REPO = HERE.parents[2]
BASE_FOLDER = REPO / "experiments/qwen38-flash-next-fp8-b70/configs/moe-warps8-m1"
CANDIDATE_FOLDER = REPO / "experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32"
BASE_HASH = "91e5d8b692da3febbba7cb07ee4fdab319909da0c82c1fda95b92dc42d680464"
CANDIDATE_HASH = "a8f1f8982e3e1af80ff31b9e0a00afaacf1af1b3c401585109b4d60d3c8267be"
SOURCE_HASHES = {
    "fused_moe": "4b376eb5e22e7972a1d70e4012999650ab961719d6309cbec27a6104fa64d0a0",
    "triton_moe": "b8a461b712b88cf6ab5ba4f49029fddce3a501f7ff909b276b6de04b808da4c2",
    "modular_kernel": "1e60aca6ed0dd4fcb46d577897ff1651f27a6130b3449d22265c0c791beec5d5",
}
PHASE_PATCH_HASH = "ad820bad443bba32f15b114ea76b4deb4dade754fe1bc362faddfef07eb6c519"
VLLM_HEAD = "cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9"
VERIFIER_HASH = "a464b0f6a46e9149b33e5ccca772bf21385532693e78b691ca010a7833be2e6f"
BASE_GATE_HASH = "8828a3b42766a96f014299967af94cbde48410abd92d64183685dbf737ce05a1"
PROTECTED = {
    "BLOCK_SIZE_M": 16,
    "BLOCK_SIZE_N": 64,
    "BLOCK_SIZE_K": 128,
    "GROUP_SIZE_M": 1,
    "SPLIT_K": 1,
    "num_warps": 8,
    "num_stages": 4,
}


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != EXPECTED_BASE_SHA256:
        raise RuntimeError("A2 summarizer drifted")
    spec = importlib.util.spec_from_file_location("q38_w13_a2_summary", BASE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = load_base()


def receipt_contract(value: dict[str, Any], role: str) -> bool:
    receipt = value.get("folder_selection_receipt", {})
    folder = BASE_FOLDER if role == "control" else CANDIDATE_FOLDER
    expected_hash = BASE_HASH if role == "control" else CANDIDATE_HASH
    expected_w1 = PROTECTED if role == "control" else PROTECTED | {"BLOCK_SIZE_N": 32}
    return (
        receipt.get("status") == "pass"
        and receipt.get("classification")
        == "qwen38_w13_m1_config_folder_selection_receipt"
        and receipt.get("role") == role
        and receipt.get("environment", {}).get("VLLM_TUNED_CONFIG_FOLDER")
        == str(folder.resolve())
        and receipt.get("config", {}).get("path")
        == str((folder / CONFIG_NAME).resolve())
        and receipt.get("config", {}).get("sha256") == expected_hash
        and receipt.get("config", {}).get("base_sha256") == BASE_HASH
        and receipt.get("config", {}).get("candidate_sha256") == CANDIDATE_HASH
        and receipt.get("selected_batch_key") == 1
        and receipt.get("m1", {}).get("w13") == expected_w1
        and receipt.get("m1", {}).get("w2") == PROTECTED
        and receipt.get("w2_unchanged") is True
        and receipt.get("source_sha256") == SOURCE_HASHES
        and receipt.get("prerequisite", {}).get("vllm_head") == VLLM_HEAD
        and receipt.get("prerequisite", {}).get("phase_config_patch_sha256")
        == PHASE_PATCH_HASH
        and receipt.get("verifier_sha256") == VERIFIER_HASH
        and receipt.get("base_gate_sha256") == BASE_GATE_HASH
    )


def summarize(root: Path) -> dict[str, Any]:
    result = BASE.summarize(root)
    receipt_passes = 0
    for row in result["rows"]:
        cell = row["cell"]
        contracts = {
            "control-before": receipt_contract(
                BASE.BASE.read_last_json(root / f"{cell}-control-before.jsonl"),
                "control",
            ),
            "candidate": receipt_contract(
                BASE.BASE.read_last_json(root / f"{cell}-candidate.jsonl"),
                "candidate",
            ),
            "control-after": receipt_contract(
                BASE.BASE.read_last_json(root / f"{cell}-control-after.jsonl"),
                "control",
            ),
        }
        row["folder_selection_receipts"] = contracts
        row["folder_selection_exact"] = all(contracts.values())
        row["exact"] = row["exact"] and row["folder_selection_exact"]
        receipt_passes += sum(contracts.values())

    reductions = [row["matched_latency_reduction_percent"] for row in result["rows"]]
    all_exact = len(result["rows"]) == 8 and all(row["exact"] for row in result["rows"])
    drift_ok = all(row["control_drift_within_two_percent"] for row in result["rows"])
    positive = sum(row["positive"] for row in result["rows"])
    median = statistics.median(reductions)
    worst = min(reductions)
    passed = (
        all_exact
        and receipt_passes == 24
        and drift_ok
        and median >= 3.0
        and positive >= 7
        and worst >= -2.0
    )
    result.update(
        {
            "status": "pass" if passed else "failed_closed",
            "classification": "qwen38_w13_m1_config_folder_qualification_a1",
            "scope": "layers0_47_ep_ranks0_3_seed20260827_actual_folder_matched_fresh_process_cac",
            "source_receipt": {
                "base_summarizer_path": str(BASE_PATH.resolve()),
                "base_summarizer_sha256": EXPECTED_BASE_SHA256,
            },
        }
    )
    result["gates"].update(
        {
            "all_8_cells_exact": all_exact,
            "all_24_folder_selection_receipts_exact": receipt_passes == 24,
            "folder_selection_receipts_passed": receipt_passes,
            "all_control_drifts_within_two_percent": drift_ok,
            "median_matched_reduction_percent": median,
            "median_reduction_at_least_three_percent": median >= 3.0,
            "positive_cells": positive,
            "at_least_7_positive_cells": positive >= 7,
            "worst_cell_reduction_percent": worst,
            "no_cell_regressed_more_than_two_percent": worst >= -2.0,
        }
    )
    result["gates"].pop("all_24_cells_exact", None)
    result["gates"].pop("at_least_20_positive_cells", None)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.result_dir.resolve()
    result = summarize(root)
    (root / "summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
