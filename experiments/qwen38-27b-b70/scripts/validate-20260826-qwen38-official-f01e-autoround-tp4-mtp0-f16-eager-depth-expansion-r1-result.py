#!/usr/bin/env python3
"""Read-only validator for the current-f01e TP4/MTP0 depth result."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp4-mtp0-f16-eager-depth-expansion-20260826-r1")
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp0-f16-eager-depth-expansion-r1-result.json"
DEPTHS = [2048, 4096, 8192, 16384, 24576, 32768]
PROTECTED = [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144]


def load(path: Path):
    return json.loads(path.read_text())


def digest(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def need(value, message):
    if not value:
        raise RuntimeError(message)


def validate():
    result = load(RESULT)
    need(result["status"] == "passed-quality-clean-with-cross-topology-caveat", "result status changed")
    for binding in result["tracked_inputs"].values():
        path = REPO / binding["path"]
        need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")

    terminal = load(ROOT / "terminal-receipt.json")
    arm = load(ROOT / "arm-result.json")
    quality = load(ROOT / "quality.json")
    need(digest(ROOT / "terminal-receipt.json") == result["cleanup"]["terminal_receipt_sha256"], "terminal changed")
    need(digest(ROOT / "arm-result.json") == result["cleanup"]["arm_result_sha256"], "arm changed")
    need(digest(ROOT / "quality.json") == result["cleanup"]["quality_sha256"], "quality changed")
    need(terminal["terminal"] and terminal["runner_return_code"] == 0, "campaign not terminal-passed")
    need(arm["state"] == "passed-quality-clean-depth-expansion-with-comparison-caveat", "arm state changed")
    need(arm["passed_depth_count"] == 6 and arm["frozen_same_topology_oracle_depths"] == DEPTHS, "depth authority changed")
    need(arm["objective_quality_passed"] and arm["parent_8k_match_passed"] and arm["cleanup_passed"], "native gates changed")
    need(arm["tp4_worker_topology_passed"] and arm["rank_cache_isolation_passed"], "topology/cache changed")
    need(arm["passed_cross_topology_comparison_count"] == 5, "comparison count changed")

    need(quality["pass_all"] and quality["baseline_match_all"], "quality failed")
    usages = [case["usage"] for case in quality["exact_cases"]] + [run["usage"] for run in quality["repeat_case"]["runs"]] + [quality["long_context_case"]["usage"]]
    need(len(quality["exact_cases"]) == 7 and quality["repeat_case"]["repeats"] == 8 and len(usages) == 16, "quality cardinality changed")
    need(all(usage["prompt_tokens_details"]["cached_tokens"] == 0 for usage in usages), "quality cache reuse appeared")

    points = []
    for depth in DEPTHS:
        path = ROOT / "exact-depth" / f"depth-{depth}.json"
        raw = load(path)
        need(raw == load(ROOT / "exact-depth" / f"depth-{depth}.stdout.json"), f"stdout differs: {depth}")
        need(raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), f"depth failed: {depth}")
        usage = raw["response"]["usage"]
        need(usage["prompt_tokens"] == depth and usage["completion_tokens"] == 128 and usage["prompt_tokens_details"]["cached_tokens"] == 0, f"usage changed: {depth}")
        points.append((depth, raw["metric_window"]["conventional_99_interval_tok_s"], raw["response"]["output_token_ids_sha256"], digest(path)))
    expected = [(p["x"], p["decode_tok_s"], p["output_token_ids_sha256"], p["raw_sha256"]) for p in result["points"]]
    need(points == expected, "compact points differ from raw")

    comparisons = {item["depth"]: item["verification"]["cross_topology_comparison"] for item in arm["depth_receipts"]}
    need(not comparisons[2048]["passed"] and comparisons[2048]["first_divergence"]["one_based"] == 90, "2K caveat changed")
    need(all(comparisons[d]["passed"] for d in DEPTHS[1:]), "4K-32K parity changed")
    need(result["points"][2]["site_action"] == "retain-existing-9.647242826428695-cell", "8K preservation changed")

    authority = result["authority"]
    need(authority["new_site_cells"] == 5 and authority["retained_existing_site_cells"] == 1 and authority["zero_context_cells"] == 0, "site authority widened")
    need(not authority["headline_or_protected_replacement"] and not authority["existing_8k_speed_replacement"], "replacement enabled")
    need(authority["protected_decode_values_unchanged"] == PROTECTED, "protected values changed")
    return {"status": "pass", "raw_cells": 6, "new_site_cells": 5, "retained_8k": True, "x0": "missing"}


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2, sort_keys=True))
