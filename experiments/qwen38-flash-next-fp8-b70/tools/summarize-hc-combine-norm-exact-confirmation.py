#!/usr/bin/env python3
"""Summarize the frozen 12-cell HC combine+norm exact C/A/C gate."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import statistics
from typing import Any


SENTINELS = ("l0-attn", "l0-mlp", "l47-attn", "l47-mlp")
SEEDS = (20260826, 20260827, 20260830)
ARMS = ("control-before", "candidate", "control-after")
MODEL_PATH = "/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8"
MODEL_REVISION = "bcd9f01ddc9cff2316eb84281bebcd5b058bddce"
MODEL_INDEX_SHA256 = "0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6"
MODEL_CONFIG_SHA256 = "99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d"
AUTHORITY_SOURCE = (
    "/home/steve/src/vllm-current-main/vllm/models/qwen4_exp/amd/ops/hc.py"
)
AUTHORITY_SOURCE_SHA256 = (
    "a2ed67ce6240a150a75247097f0a49b4652d5bf1f5db1cdaf34ad5ec52faa8da"
)
CANDIDATE_CORE = str(Path(__file__).with_name("hc_combine_norm_exact_staged.py"))
CANDIDATE_CORE_SHA256 = (
    "4f07ca40099b16259ca6f82a226791732455dc9903b66c39691ba212f5d19354"
)
EXPECTED_SENTINELS = {
    "l0-attn": {
        "layer": 0,
        "role": "attn",
        "shard": "model-00001-of-00131.safetensors",
        "shard_size": 1040155912,
        "weight": "model.language_model.layers.0.attn_hyper_connection.hc_norm.weight",
        "weight_sha256": "0a3213d5fbfe4043a4800e3ca12cd05c3e7ced745f5aca03fc67ada75d169f98",
    },
    "l0-mlp": {
        "layer": 0,
        "role": "mlp",
        "shard": "model-00003-of-00131.safetensors",
        "shard_size": 993901136,
        "weight": "model.language_model.layers.0.mlp_hyper_connection.hc_norm.weight",
        "weight_sha256": "e1da29c3232c056fb6869275c5cbbe527d591b88dd967e747716e23f1a89a5bb",
    },
    "l47-attn": {
        "layer": 47,
        "role": "attn",
        "shard": "model-00118-of-00131.safetensors",
        "shard_size": 878004272,
        "weight": "model.language_model.layers.47.attn_hyper_connection.hc_norm.weight",
        "weight_sha256": "90c3284c07d7dfe2d81ba6ceae92d8b914591094fbefc2717b7505a78facb816",
    },
    "l47-mlp": {
        "layer": 47,
        "role": "mlp",
        "shard": "model-00120-of-00131.safetensors",
        "shard_size": 1109903856,
        "weight": "model.language_model.layers.47.mlp_hyper_connection.hc_norm.weight",
        "weight_sha256": "66863fc1e9cae0568b923baf5fce89002527f53fd721e89ab5c1968a7d297452",
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
        code = int(path.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError) as exc:
        raise ValueError(f"invalid exit receipt: {path}") from exc
    if not 0 <= code <= 255:
        raise ValueError(f"exit receipt out of range: {path}")
    return code


def normalized_identity(value: dict[str, Any]) -> dict[str, Any]:
    identity = dict(value.get("identity", {}))
    return identity


def arm_exact(
    value: dict[str, Any], *, sentinel: str, seed: int, arm: str, authority: str | None
) -> tuple[bool, float]:
    identity = value.get("identity", {})
    treatment = value.get("treatment", {})
    correctness = value.get("correctness", {})
    graph = value.get("graph", {})
    expected_sentinel = EXPECTED_SENTINELS[sentinel]
    weight = identity.get("weight", {})
    hashes = correctness.get("graph_hashes", [])
    hashes_valid = (
        isinstance(hashes, list)
        and len(hashes) == 100
        and len(set(hashes)) == 100
        and all(
            isinstance(item, str) and re.fullmatch(r"[0-9a-f]{64}", item)
            for item in hashes
        )
    )
    adversarial_hash = correctness.get("adversarial_pair_sha256")
    timing = graph.get("cycle_median_us")
    timing_valid = type(timing) in (int, float) and math.isfinite(timing) and timing > 0
    exact = (
        value.get("status") == "pass"
        and value.get("classification")
        == "qwen38_hc_combine_norm_exact_xpu_graph_component"
        and identity.get("model_path") == MODEL_PATH
        and identity.get("model_revision") == MODEL_REVISION
        and identity.get("model_index_sha256") == MODEL_INDEX_SHA256
        and identity.get("model_config_sha256") == MODEL_CONFIG_SHA256
        and identity.get("model_mount")
        == {"source": "/dev/sda2", "fstype": "fuseblk", "target": "/mnt/usb-models"}
        and identity.get("sentinel") == sentinel
        and identity.get("layer") == expected_sentinel["layer"]
        and identity.get("role") == expected_sentinel["role"]
        and identity.get("seed") == seed
        and weight.get("layer") == expected_sentinel["layer"]
        and weight.get("role") == expected_sentinel["role"]
        and weight.get("shard") == expected_sentinel["shard"]
        and weight.get("shard_path") == f"{MODEL_PATH}/{expected_sentinel['shard']}"
        and weight.get("shard_size") == expected_sentinel["shard_size"]
        and weight.get("weight") == expected_sentinel["weight"]
        and weight.get("weight_sha256") == expected_sentinel["weight_sha256"]
        and identity.get("authority_source") == AUTHORITY_SOURCE
        and identity.get("authority_source_sha256") == AUTHORITY_SOURCE_SHA256
        and identity.get("candidate_core") == CANDIDATE_CORE
        and identity.get("candidate_core_sha256") == CANDIDATE_CORE_SHA256
        and identity.get("shape")
        == {
            "residual": [1, 10240],
            "block_output": [1, 2560],
            "injection_logits": [1, 4],
            "norm_weight": [10240],
            "hc_count": 4,
        }
        and identity.get("dtype") == "bfloat16"
        and treatment.get("arm") == arm
        and treatment.get("sigmoid_changed") is False
        and treatment.get("rsqrt_changed") is False
        and treatment.get("arithmetic_order_changed") is False
        and treatment.get("explicit_bf16_combine_rounding_preserved") is True
        and correctness.get("calls_per_graph_cycle") == 95
        and correctness.get("exact_replays") == 100
        and correctness.get("both_outputs_exact_to_eager_authority") is True
        and correctness.get("unique_graph_hashes") == 100
        and hashes_valid
        and correctness.get("control_authority_path") == authority
        and correctness.get("matches_control_authority") is True
        and correctness.get("adversarial_bf16_passed") is True
        and isinstance(adversarial_hash, str)
        and re.fullmatch(r"[0-9a-f]{64}", adversarial_hash)
        and correctness.get("cached_affine_validated_before_capture") is True
        and graph.get("timing_excludes_input_copy_and_exactness_checks") is True
        and graph.get("warmups") == 10
        and graph.get("batches") == 9
        and graph.get("iterations_per_batch") == 50
        and timing_valid
    )
    return exact, float(timing) if timing_valid else math.nan


def summarize(root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    reductions: list[float] = []
    savings_us: list[float] = []
    all_exact = True
    all_drift_ok = True
    positive = 0
    worst_reduction = math.inf
    for sentinel in SENTINELS:
        for seed in SEEDS:
            cell = f"{sentinel}-s{seed}"
            before_path = (root / f"{cell}-control-before.jsonl").resolve()
            authority = str(before_path)
            values = {arm: read_last_json(root / f"{cell}-{arm}.jsonl") for arm in ARMS}
            exits = {
                arm: read_exit_code(root / f"{cell}-{arm}.exit-code") for arm in ARMS
            }
            before_exact, before_us = arm_exact(
                values["control-before"],
                sentinel=sentinel,
                seed=seed,
                arm="control-before",
                authority=None,
            )
            candidate_exact, candidate_us = arm_exact(
                values["candidate"],
                sentinel=sentinel,
                seed=seed,
                arm="candidate",
                authority=authority,
            )
            after_exact, after_us = arm_exact(
                values["control-after"],
                sentinel=sentinel,
                seed=seed,
                arm="control-after",
                authority=authority,
            )
            hashes_equal = (
                values["control-before"]["correctness"]["graph_hashes"]
                == values["candidate"]["correctness"]["graph_hashes"]
                == values["control-after"]["correctness"]["graph_hashes"]
            )
            adversarial_hashes_equal = (
                values["control-before"]["correctness"]["adversarial_pair_sha256"]
                == values["candidate"]["correctness"]["adversarial_pair_sha256"]
                == values["control-after"]["correctness"]["adversarial_pair_sha256"]
            )
            identities_equal = (
                normalized_identity(values["control-before"])
                == normalized_identity(values["candidate"])
                == normalized_identity(values["control-after"])
            )
            exact = (
                all(code == 0 for code in exits.values())
                and before_exact
                and candidate_exact
                and after_exact
                and hashes_equal
                and adversarial_hashes_equal
                and identities_equal
            )
            control_us = statistics.mean((before_us, after_us))
            drift = 100.0 * abs(after_us - before_us) / control_us
            saved_us = control_us - candidate_us
            reduction = 100.0 * saved_us / control_us
            drift_ok = drift <= 2.0
            all_exact = all_exact and exact
            all_drift_ok = all_drift_ok and drift_ok
            positive += int(reduction > 0)
            reductions.append(reduction)
            savings_us.append(saved_us)
            worst_reduction = min(worst_reduction, reduction)
            rows.append(
                {
                    "cell": cell,
                    "sentinel": sentinel,
                    "seed": seed,
                    "control_before_us": before_us,
                    "candidate_us": candidate_us,
                    "control_after_us": after_us,
                    "control_bracket_mean_us": control_us,
                    "saved_us": saved_us,
                    "matched_reduction_percent": reduction,
                    "control_drift_percent": drift,
                    "exact": exact,
                    "control_drift_within_two_percent": drift_ok,
                    "exit_codes": exits,
                }
            )
    median_reduction = statistics.median(reductions)
    median_saved_us = statistics.median(savings_us)
    material = median_reduction >= 5.0 or median_saved_us >= 1000.0
    passed = (
        len(rows) == 12
        and all_exact
        and all_drift_ok
        and material
        and positive >= 10
        and worst_reduction >= -2.0
    )
    return {
        "schema_version": 1,
        "status": "pass" if passed else "failed_closed",
        "classification": "qwen38_hc_combine_norm_exact_confirmation",
        "scope": "four_real_norm_sentinels_three_seeds_95_call_graph_cycle_cac",
        "rows": rows,
        "gates": {
            "all_12_cells_exact": all_exact,
            "all_control_drifts_within_two_percent": all_drift_ok,
            "median_matched_reduction_percent": median_reduction,
            "median_saved_us": median_saved_us,
            "material_five_percent_or_one_ms": material,
            "positive_cells": positive,
            "at_least_10_positive_cells": positive >= 10,
            "worst_cell_reduction_percent": worst_reduction,
            "no_cell_regressed_more_than_two_percent": worst_reduction >= -2.0,
        },
        "aggregation": "matched candidate/control bracket within each sentinel/seed",
        "cross_cell_raw_timings_pooled": False,
        "endpoint_or_speed_claim_authorized": False,
        "protected_results_changed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.result_dir.resolve())
    destination = args.result_dir / "summary.json"
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite summary: {destination}")
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
