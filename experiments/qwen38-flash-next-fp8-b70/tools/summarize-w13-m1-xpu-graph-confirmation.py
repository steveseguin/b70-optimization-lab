#!/usr/bin/env python3
"""Summarize the frozen Qwen3.8 Flash-Next W13 N32 confirmation matrix."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
from typing import Any


LAYERS = (0, 47)
EP_RANKS = (0, 1, 2, 3)
SEEDS = (20260826, 20260827, 20260830)
CANDIDATE_CONFIG = {"W1_CONFIG": {"BLOCK_SIZE_N": 32}}
PROTECTED_W2 = {
    "BLOCK_SIZE_M": 16,
    "BLOCK_SIZE_N": 64,
    "BLOCK_SIZE_K": 128,
    "GROUP_SIZE_M": 1,
    "SPLIT_K": 1,
    "num_warps": 8,
    "num_stages": 4,
}
MODEL_PATH = "/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8"
MODEL_REVISION = "bcd9f01ddc9cff2316eb84281bebcd5b058bddce"
MODEL_INDEX_SHA256 = "0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6"
MODEL_CONFIG_SHA256 = "99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d"
GATE_SHA256 = "8828a3b42766a96f014299967af94cbde48410abd92d64183685dbf737ce05a1"
RUNTIME_SOURCE_RECEIPT = {
    "gate_sha256": GATE_SHA256,
    "torch_version": "2.11.0+xpu",
    "triton_version": "3.7.0",
    "vllm_version": "0.20.2rc1.dev13+g9557d9108.d20260620",
    "source_files": {
        "fused_moe": {
            "path": "/home/steve/src/vllm-current-main/vllm/model_executor/layers/fused_moe/fused_moe.py",
            "sha256": "4b376eb5e22e7972a1d70e4012999650ab961719d6309cbec27a6104fa64d0a0",
        },
        "triton_experts": {
            "path": "/home/steve/src/vllm-current-main/vllm/model_executor/layers/fused_moe/experts/triton_moe.py",
            "sha256": "b8a461b712b88cf6ab5ba4f49029fddce3a501f7ff909b276b6de04b808da4c2",
        },
        "modular_kernel": {
            "path": "/home/steve/src/vllm-current-main/vllm/model_executor/layers/fused_moe/modular_kernel.py",
            "sha256": "1e60aca6ed0dd4fcb46d577897ff1651f27a6130b3449d22265c0c791beec5d5",
        },
    },
}
LAYER_SHARDS = {
    0: {
        "model-00002-of-00131.safetensors": {
            "size": 1678209208,
            "sha256": "6841fe21fa8a8a7a693c585efe65cd2732889095b696da88bda0cb287366910b",
            "stat_identity": {
                "device": 2050,
                "inode": 1802503,
                "mtime_ns": 1787754541759779900,
                "ctime_ns": 1787754541796499200,
            },
        },
        "model-00003-of-00131.safetensors": {
            "size": 993901136,
            "sha256": "974a2a2ab551f8f1405a4955ab32a8721c68c73dd85b382491d9f0e6a34ee752",
            "stat_identity": {
                "device": 2050,
                "inode": 1802510,
                "mtime_ns": 1787754136121899500,
                "ctime_ns": 1787754136146451600,
            },
        },
    },
    47: {
        "model-00119-of-00131.safetensors": {
            "size": 1678211256,
            "sha256": "36008b48c4480085bfd1a81439d70d1029cfaf06cfdd037cec19b491a40659ec",
            "stat_identity": {
                "device": 2050,
                "inode": 960115,
                "mtime_ns": 1787777584386745100,
                "ctime_ns": 1787777584401268900,
            },
        },
        "model-00120-of-00131.safetensors": {
            "size": 1109903856,
            "sha256": "49e4f90d92f60f6489bfe6d3e5250d8fe879c5995ae72ce67379cc7187fa4b0a",
            "stat_identity": {
                "device": 2050,
                "inode": 960127,
                "mtime_ns": 1787777583721158000,
                "ctime_ns": 1787777583828473400,
            },
        },
    },
}


def read_last_json(path: Path) -> dict[str, Any]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not lines:
        raise ValueError(f"empty arm evidence: {path}")
    value = json.loads(lines[-1])
    if not isinstance(value, dict):
        raise ValueError(f"arm evidence is not an object: {path}")
    return value


def read_exit_code(path: Path) -> int:
    try:
        value = int(path.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError) as exc:
        raise ValueError(f"invalid or missing exit-code receipt: {path}") from exc
    if not 0 <= value <= 255:
        raise ValueError(f"exit-code receipt is out of range: {path}")
    return value


def expected_checkpoint_shards(layer: int) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "path": f"{MODEL_PATH}/{name}",
            "size": receipt["size"],
            "sha256": receipt["sha256"],
            "stat_identity": receipt["stat_identity"],
        }
        for name, receipt in LAYER_SHARDS[layer].items()
    }


def arm_contract(
    value: dict[str, Any],
    *,
    layer: int,
    rank: int,
    seed: int,
    expected_config: dict[str, Any],
    expected_authority: str | None,
    receipt_path: str,
    receipt_sha256: str,
) -> tuple[bool, float]:
    identity = value.get("identity", {})
    correctness = value.get("correctness", {})
    config = value.get("config_receipt", {})
    weights = value.get("weights", {})
    graph = value.get("graph", {})
    median = graph.get("event_median_us")
    timing_valid = (
        type(median) in (int, float) and math.isfinite(median) and median > 0.0
    )
    exact = (
        value.get("status") == "pass"
        and value.get("classification")
        == "qwen38_flash_next_w13_m1_xpu_graph_component"
        and identity.get("model_path") == MODEL_PATH
        and identity.get("model_revision") == MODEL_REVISION
        and identity.get("model_index_sha256") == MODEL_INDEX_SHA256
        and identity.get("model_config_sha256") == MODEL_CONFIG_SHA256
        and identity.get("layer") == layer
        and identity.get("ep_rank") == rank
        and identity.get("seed") == seed
        and identity.get("global_expert_range") == [rank * 128, rank * 128 + 127]
        and identity.get("checkpoint_shards") == expected_checkpoint_shards(layer)
        and identity.get("runtime_source_receipt") == RUNTIME_SOURCE_RECEIPT
        and config.get("requested") == expected_config
        and config.get("resolved_w2") == PROTECTED_W2
        and config.get("w2_unchanged") is True
        and weights.get("checkpoint_checksum_mode") == "frozen_receipt"
        and weights.get("checkpoint_receipt_path") == receipt_path
        and weights.get("checkpoint_receipt_sha256") == receipt_sha256
        and correctness.get("exact_replays") == 100
        and correctness.get("config_local_eager_graph_equal") is True
        and correctness.get("matches_control_authority") is True
        and correctness.get("unique_eager_hashes") == 100
        and correctness.get("unique_graph_hashes") == 100
        and correctness.get("control_authority_path") == expected_authority
        and graph.get("timing_input_index") == 0
        and timing_valid
    )
    return exact, float(median) if timing_valid else math.nan


def summarize(root: Path) -> dict[str, Any]:
    receipt_path = str((root / "checkpoint-receipt.json").resolve())
    receipt_sha256 = (
        (root / "checkpoint-receipt.sha256").read_text(encoding="utf-8").strip()
    )
    rows: list[dict[str, Any]] = []
    reductions: list[float] = []
    all_exact = True
    all_drift_ok = True
    positive_cells = 0

    for layer in LAYERS:
        for rank in EP_RANKS:
            for seed in SEEDS:
                cell = f"l{layer}-r{rank}-s{seed}"
                before_path = (root / f"{cell}-control-before.jsonl").resolve()
                candidate_path = root / f"{cell}-candidate.jsonl"
                after_path = root / f"{cell}-control-after.jsonl"
                exits = {
                    arm: read_exit_code(root / f"{cell}-{arm}.exit-code")
                    for arm in ("control-before", "candidate", "control-after")
                }
                values = {
                    "control-before": read_last_json(before_path),
                    "candidate": read_last_json(candidate_path),
                    "control-after": read_last_json(after_path),
                }
                before_exact, before_us = arm_contract(
                    values["control-before"],
                    layer=layer,
                    rank=rank,
                    seed=seed,
                    expected_config={},
                    expected_authority=None,
                    receipt_path=receipt_path,
                    receipt_sha256=receipt_sha256,
                )
                candidate_exact, candidate_us = arm_contract(
                    values["candidate"],
                    layer=layer,
                    rank=rank,
                    seed=seed,
                    expected_config=CANDIDATE_CONFIG,
                    expected_authority=str(before_path),
                    receipt_path=receipt_path,
                    receipt_sha256=receipt_sha256,
                )
                after_exact, after_us = arm_contract(
                    values["control-after"],
                    layer=layer,
                    rank=rank,
                    seed=seed,
                    expected_config={},
                    expected_authority=str(before_path),
                    receipt_path=receipt_path,
                    receipt_sha256=receipt_sha256,
                )
                identities_equal = (
                    values["control-before"].get("identity")
                    == values["candidate"].get("identity")
                    == values["control-after"].get("identity")
                )
                exact = (
                    all(value == 0 for value in exits.values())
                    and before_exact
                    and candidate_exact
                    and after_exact
                    and identities_equal
                )
                control_mean_us = statistics.mean((before_us, after_us))
                drift = 100.0 * abs(after_us - before_us) / control_mean_us
                reduction = 100.0 * (1.0 - candidate_us / control_mean_us)
                drift_ok = drift <= 2.0
                positive = reduction > 0.0
                all_exact = all_exact and exact
                all_drift_ok = all_drift_ok and drift_ok
                positive_cells += int(positive)
                reductions.append(reduction)
                rows.append(
                    {
                        "cell": cell,
                        "layer": layer,
                        "ep_rank": rank,
                        "seed": seed,
                        "control_before_us": before_us,
                        "candidate_us": candidate_us,
                        "control_after_us": after_us,
                        "control_bracket_mean_us": control_mean_us,
                        "control_drift_percent": drift,
                        "matched_latency_reduction_percent": reduction,
                        "exact": exact,
                        "control_drift_within_two_percent": drift_ok,
                        "positive": positive,
                        "exit_codes": exits,
                    }
                )

    median_reduction = statistics.median(reductions)
    worst_reduction = min(reductions)
    passed = (
        len(rows) == 24
        and all_exact
        and all_drift_ok
        and median_reduction >= 3.0
        and positive_cells >= 20
        and worst_reduction >= -2.0
    )
    return {
        "schema_version": 1,
        "status": "pass" if passed else "failed_closed",
        "classification": "qwen38_w13_m1_xpu_graph_confirmation",
        "scope": "layers0_47_ep_ranks0_3_three_seeds_matched_fresh_process_cac",
        "candidate_config": CANDIDATE_CONFIG,
        "checkpoint_receipt": {
            "path": receipt_path,
            "sha256": receipt_sha256,
        },
        "rows": rows,
        "gates": {
            "all_24_cells_exact": all_exact,
            "all_control_drifts_within_two_percent": all_drift_ok,
            "median_matched_reduction_percent": median_reduction,
            "median_reduction_at_least_three_percent": median_reduction >= 3.0,
            "positive_cells": positive_cells,
            "at_least_20_positive_cells": positive_cells >= 20,
            "worst_cell_reduction_percent": worst_reduction,
            "no_cell_regressed_more_than_two_percent": worst_reduction >= -2.0,
        },
        "aggregation": "matched candidate/control ratio within each cell",
        "raw_cross_rank_timings_pooled": False,
        "protected_results_changed": False,
    }


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
