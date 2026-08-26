#!/usr/bin/env python3
"""Read-only validator for the current-f01e TP4/MTP1 partial depth result."""

from __future__ import annotations

import hashlib, json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp4-mtp1-f16-eager-depth-expansion-20260826-r1")
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp1-f16-eager-depth-expansion-r1-result.json"
DEPTHS = [2048, 4096, 8192, 16384, 24576, 32768]
VALID = [4096, 8192, 16384, 24576, 32768]
PROTECTED = [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144]

load = lambda path: json.loads(path.read_text())
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def need(value, message):
    if not value: raise RuntimeError(message)


def validate():
    result = load(RESULT)
    for binding in result["tracked_inputs"].values():
        path = REPO / binding["path"]
        need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")
    terminal, arm, quality = (load(ROOT / name) for name in ("terminal-receipt.json", "arm-result.json", "quality.json"))
    for key, name in (("terminal_receipt_sha256", "terminal-receipt.json"), ("arm_result_sha256", "arm-result.json"), ("quality_sha256", "quality.json"), ("model_verification_sha256", "model-verification.json"), ("rank_cache_isolation_sha256", "rank-cache-isolation.txt")):
        need(digest(ROOT / name) == result["cleanup"][key], f"{name} changed")
    need((ROOT / "rank-cache-isolation.txt").read_text() == "graph-off: no compile artifacts\n", "rank-cache receipt changed")
    need(terminal["terminal"] and terminal["state"] == "partial-depth-expansion" and terminal["runner_return_code"] == 37, "terminal classification changed")
    need(arm["state"] == "partial-depth-expansion" and arm["frozen_same_topology_oracle_depths"] == VALID, "per-depth authority changed")
    need(arm["failed_or_quarantined_depths"] == [2048] and arm["passed_acceptance_count"] == 6 and arm["passed_same_topology_target_count"] == 5, "partial counts changed")
    need(all(arm[key] for key in ("objective_quality_passed", "same_topology_baseline_passed", "parent_8k_match_passed", "cleanup_passed", "tp4_worker_topology_passed", "rank_cache_isolation_passed")), "native gates weakened")
    usages = [case["usage"] for case in quality["exact_cases"]] + [run["usage"] for run in quality["repeat_case"]["runs"]] + [quality["long_context_case"]["usage"]]
    need(quality["pass_all"] and quality["baseline_match_all"] and len(usages) == 16 and all(x["prompt_tokens_details"]["cached_tokens"] == 0 for x in usages), "quality changed")
    verification = load(ROOT / "model-verification.json")
    need(verification["status"] == "verified" and len(verification["files"]) == 19 and all(x["ok"] and x["paths_coherent"] and x["direct_mode"] == "odirect" for x in verification["files"]), "model verification weakened")
    receipts = {x["depth"]: x for x in arm["depth_receipts"]}
    need(not receipts[2048]["per_depth_valid"] and receipts[2048]["verification"]["same_topology_target_verification"]["first_divergence"]["one_based"] == 90, "2K quarantine changed")
    need(all(receipts[d]["per_depth_valid"] for d in VALID), "valid depth changed")
    compact = {x["x"]: x for x in result["valid_points"]}
    for depth in DEPTHS:
        path = ROOT / "exact-depth" / f"depth-{depth}.json"
        raw = load(path)
        need(raw == load(ROOT / "exact-depth" / f"depth-{depth}.stdout.json") and raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), f"raw depth changed: {depth}")
        if depth in VALID:
            need((compact[depth]["decode_tok_s"], compact[depth]["output_token_ids_sha256"], compact[depth]["raw_sha256"]) == (raw["metric_window"]["conventional_99_interval_tok_s"], raw["response"]["output_token_ids_sha256"], digest(path)), f"compact point changed: {depth}")
    need(result["adjudication"]["prior_8k_site_value_retained"] == 13.709857016920843 and result["valid_points"][1]["site_action"].startswith("retain-existing"), "8K replacement contract changed")
    authority = result["authority"]
    need(authority["new_site_measured_cells"] == 4 and authority["new_site_quarantined_cells"] == 1 and authority["zero_context_cells"] == 0, "site authority widened")
    need(not authority["headline_or_protected_replacement"] and not authority["existing_8k_speed_replacement"] and authority["protected_decode_values_unchanged"] == PROTECTED, "protected authority changed")
    return {"status": "pass", "measured_new": 4, "retained_8k": True, "quarantined": [2048], "x0": "missing"}


if __name__ == "__main__": print(json.dumps(validate(), indent=2, sort_keys=True))
