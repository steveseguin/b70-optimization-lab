#!/usr/bin/env python3
"""Summarize the frozen Qwen3.8 Flash-Next W13 graph discovery census."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
from typing import Any


CANDIDATES: dict[str, dict[str, dict[str, int]]] = {
    "w13-warps4": {"W1_CONFIG": {"num_warps": 4}},
    "w13-n32": {"W1_CONFIG": {"BLOCK_SIZE_N": 32}},
    "w13-n128": {"W1_CONFIG": {"BLOCK_SIZE_N": 128}},
    "w13-n256": {"W1_CONFIG": {"BLOCK_SIZE_N": 256}},
    "w13-k64": {"W1_CONFIG": {"BLOCK_SIZE_K": 64}},
    "w13-stage5": {"W1_CONFIG": {"num_stages": 5}},
}

PROTECTED_W2 = {
    "BLOCK_SIZE_M": 16,
    "BLOCK_SIZE_N": 64,
    "BLOCK_SIZE_K": 128,
    "GROUP_SIZE_M": 1,
    "SPLIT_K": 1,
    "num_warps": 8,
    "num_stages": 4,
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


def arm_contract(
    value: dict[str, Any],
    *,
    expected_config: dict[str, Any],
    expected_authority: str | None,
) -> tuple[bool, float]:
    correctness = value.get("correctness", {})
    receipt = value.get("config_receipt", {})
    graph = value.get("graph", {})
    median = graph.get("event_median_us")
    valid_timing = (
        type(median) in (int, float) and math.isfinite(median) and median > 0.0
    )
    exact = (
        value.get("status") == "pass"
        and value.get("classification")
        == "qwen38_flash_next_w13_m1_xpu_graph_component"
        and receipt.get("requested") == expected_config
        and receipt.get("resolved_w2") == PROTECTED_W2
        and receipt.get("w2_unchanged") is True
        and correctness.get("exact_replays") == 100
        and correctness.get("config_local_eager_graph_equal") is True
        and correctness.get("matches_control_authority") is True
        and correctness.get("unique_eager_hashes") == 100
        and correctness.get("unique_graph_hashes") == 100
        and correctness.get("control_authority_path") == expected_authority
        and graph.get("timing_input_index") == 0
        and valid_timing
    )
    return exact, float(median) if valid_timing else math.nan


def summarize(root: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    rows: dict[str, Any] = {}
    common_identity: dict[str, Any] | None = None
    for name, candidate_config in CANDIDATES.items():
        before_path = (root / f"{name}-control-before.jsonl").resolve()
        candidate_path = root / f"{name}-candidate.jsonl"
        after_path = root / f"{name}-control-after.jsonl"
        before_exit = read_exit_code(root / f"{name}-control-before.exit-code")
        candidate_exit = read_exit_code(root / f"{name}-candidate.exit-code")
        after_exit = read_exit_code(root / f"{name}-control-after.exit-code")
        if before_exit != 0 or after_exit != 0:
            raise ValueError(f"{name} control process did not exit zero")
        before = read_last_json(before_path)
        candidate_error = None
        if candidate_exit != 0:
            candidate = {}
            candidate_error = f"candidate process exited {candidate_exit}"
        else:
            try:
                candidate = read_last_json(candidate_path)
            except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
                candidate = {}
                candidate_error = str(exc)
        after = read_last_json(after_path)

        identities = [before.get("identity"), after.get("identity")]
        identity_match = identities[0] == identities[1]
        if candidate:
            identity_match = (
                identity_match and candidate.get("identity") == identities[0]
            )
        else:
            identity_match = False
        if common_identity is None:
            if not isinstance(identities[0], dict):
                raise ValueError("first control has no identity")
            common_identity = identities[0]
        elif identities[0] != common_identity:
            raise ValueError(f"{name} control identity drifted across brackets")

        before_exact, before_us = arm_contract(
            before, expected_config={}, expected_authority=None
        )
        candidate_exact, candidate_us = arm_contract(
            candidate,
            expected_config=candidate_config,
            expected_authority=str(before_path),
        )
        after_exact, after_us = arm_contract(
            after, expected_config={}, expected_authority=str(before_path)
        )
        exact = before_exact and candidate_exact and after_exact and identity_match
        if not before_exact or not after_exact:
            raise ValueError(f"{name} control bracket failed its contract")
        control_mean_us = statistics.mean((before_us, after_us))
        control_drift_percent = 100.0 * abs(after_us - before_us) / control_mean_us
        reduction_percent = (
            100.0 * (1.0 - candidate_us / control_mean_us) if candidate_exact else None
        )
        candidate_us_value = candidate_us if candidate_exact else None
        qualified = (
            exact
            and control_drift_percent <= 2.0
            and reduction_percent is not None
            and reduction_percent >= 3.0
        )
        rows[name] = {
            "candidate_config": candidate_config,
            "control_before_us": before_us,
            "candidate_us": candidate_us_value,
            "control_after_us": after_us,
            "control_bracket_mean_us": control_mean_us,
            "control_drift_percent": control_drift_percent,
            "latency_reduction_percent": reduction_percent,
            "exact": exact,
            "candidate_error": candidate_error,
            "exit_codes": {
                "control_before": before_exit,
                "candidate": candidate_exit,
                "control_after": after_exit,
            },
            "control_drift_within_two_percent": control_drift_percent <= 2.0,
            "qualified_discovery_positive": qualified,
            "evidence": {
                "control_before": str(before_path),
                "candidate": str(candidate_path.resolve()),
                "control_after": str(after_path.resolve()),
            },
        }

    qualified_names = [
        name for name, row in rows.items() if row["qualified_discovery_positive"]
    ]
    qualified_names.sort(
        key=lambda name: rows[name]["latency_reduction_percent"], reverse=True
    )
    winner = qualified_names[0] if qualified_names else None
    summary = {
        "schema_version": 1,
        "status": "complete",
        "classification": "qwen38_w13_m1_xpu_graph_discovery_census",
        "scope": "layer0_ep_rank0_seed20260827_matched_fresh_process_cac",
        "identity": common_identity,
        "rows": rows,
        "qualified_candidates": qualified_names,
        "discovery_winner": winner,
        "confirmation_authorized": winner is not None,
        "raw_rank_timings_pooled": False,
        "protected_results_changed": False,
    }
    if winner is None:
        return summary, None

    confirmation = {
        "schema_version": 1,
        "status": "frozen_not_executed",
        "classification": "qwen38_w13_graph_confirmation_packet",
        "trigger": {
            "discovery_winner": winner,
            "candidate_config": CANDIDATES[winner],
            "discovery_reduction_percent": rows[winner]["latency_reduction_percent"],
            "discovery_summary": str((root / "summary.json").resolve()),
        },
        "identity": common_identity,
        "matrix": {
            "layers": [0, 47],
            "ep_ranks": [0, 1, 2, 3],
            "seeds": [20260826, 20260827, 20260830],
            "cells": 24,
            "fresh_process_arms_per_cell": [
                "control-before",
                "candidate",
                "control-after",
            ],
            "total_processes": 72,
            "authority_binding": (
                "candidate and control-after consume that cell's one-line "
                "control-before JSON"
            ),
        },
        "gates": {
            "exact_all_cells": True,
            "maximum_control_drift_percent_each_cell": 2.0,
            "minimum_median_matched_reduction_percent": 3.0,
            "minimum_positive_cells": 20,
            "maximum_single_cell_regression_percent": 2.0,
            "raw_cross_rank_timings_may_be_pooled": False,
            "aggregation": "matched candidate/control ratio within each cell",
        },
        "execution": {
            "authorized_now": False,
            "next_step": (
                "freeze a separate confirmation runner and layer-47 shard hashes; "
                "review before GPU execution"
            ),
        },
        "protected_results_changed": False,
    }
    return summary, confirmation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.result_dir.resolve()
    summary, confirmation = summarize(root)
    summary_path = root / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    if confirmation is not None:
        confirmation_path = root / "confirmation-packet.json"
        confirmation_path.write_text(
            json.dumps(confirmation, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        summary["confirmation_packet"] = str(confirmation_path)
        summary_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(summary, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
