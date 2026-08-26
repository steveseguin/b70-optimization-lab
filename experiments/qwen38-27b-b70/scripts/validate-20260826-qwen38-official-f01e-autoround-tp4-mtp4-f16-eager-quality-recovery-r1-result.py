#!/usr/bin/env python3
"""Read-only validator for the current-f01e TP4/MTP4 quality recovery result."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp4-mtp4-f16-eager-quality-recovery-20260826-r1")
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp4-f16-eager-quality-recovery-r1-result.json"
PUBLISHED = [4096, 16384, 24576]
RECOVERY_DEPTHS = [4096, 8192, 16384, 24576]
PROTECTED = [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144]


def load(path: Path):
    return json.loads(path.read_text())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def need(value, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def validate():
    result = load(RESULT)
    for binding in result["tracked_inputs"].values():
        path = REPO / binding["path"]
        need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")

    terminal = load(ROOT / "terminal-receipt.json")
    arm = load(ROOT / "arm-result.json")
    quality = load(ROOT / "quality.json")
    for key, name in (
        ("terminal_receipt_sha256", "terminal-receipt.json"),
        ("arm_result_sha256", "arm-result.json"),
        ("quality_sha256", "quality.json"),
        ("model_verification_sha256", "model-verification.json"),
        ("rank_cache_isolation_sha256", "rank-cache-isolation.txt"),
    ):
        need(digest(ROOT / name) == result["cleanup"][key], f"{name} changed")
    need((ROOT / "rank-cache-isolation.txt").read_text() == "graph-off: no compile artifacts\n", "rank-cache receipt changed")

    need(terminal["terminal"] and terminal["state"] == "passed-quality-clean-recovery" and terminal["runner_return_code"] == 0, "terminal classification changed")
    need(arm["state"] == "passed-quality-clean-recovery", "arm classification changed")
    need(arm["frozen_same_topology_oracle_depths"] == PUBLISHED, "publication depths changed")
    need(arm["failed_or_quarantined_depths"] == [8192], "8K recovery quarantine changed")
    need((arm["passed_depth_count"], arm["passed_acceptance_count"], arm["passed_same_topology_target_count"]) == (4, 4, 3), "recovery counts changed")
    need(all(arm[key] for key in ("objective_quality_passed", "same_topology_baseline_passed", "parent_8k_match_passed", "cleanup_passed", "tp4_worker_topology_passed", "rank_cache_isolation_passed")), "global gate weakened")

    usages = [case["usage"] for case in quality["exact_cases"]] + [run["usage"] for run in quality["repeat_case"]["runs"]] + [quality["long_context_case"]["usage"]]
    need(quality["pass_all"] and quality["baseline_match_all"], "quality changed")
    need(len(quality["exact_cases"]) == 7 and len(quality["repeat_case"]["runs"]) == 8 and len(quality["repeat_case"]["unique_hashes"]) == 1, "quality coverage changed")
    need(quality["long_context_case"]["pass"] and len(quality["baseline_comparisons"]) == 24, "quality detail changed")
    need(len(usages) == 16 and all(item["prompt_tokens_details"]["cached_tokens"] == 0 for item in usages), "quality cache state changed")

    verification = load(ROOT / "model-verification.json")
    need(verification["status"] == "verified" and len(verification["files"]) == 19, "model verification changed")
    need(all(item["ok"] and item["paths_coherent"] and item["direct_mode"] == "odirect" for item in verification["files"]), "model verification weakened")

    receipts = {item["depth"]: item for item in arm["depth_receipts"]}
    need(sorted(receipts) == RECOVERY_DEPTHS, "recovery depth set changed")
    need(all(receipts[depth]["per_depth_valid"] and receipts[depth]["target_parity_passed"] for depth in PUBLISHED), "published parity changed")
    eight = receipts[8192]
    divergence = eight["verification"]["same_topology_target_verification"]["first_divergence"]
    need(not eight["per_depth_valid"] and not eight["target_parity_passed"] and eight["verification"]["parent_8k_match"]["passed"], "8K classification changed")
    need(divergence == {"zero_based": 98, "one_based": 99, "candidate": 411, "target": 579}, "8K divergence changed")

    compact = {point["x"]: point for point in result["published_points"]}
    need(sorted(compact) == PUBLISHED, "published result points widened")
    for depth in RECOVERY_DEPTHS:
        path = ROOT / "exact-depth" / f"depth-{depth}.json"
        raw = load(path)
        need(raw == load(ROOT / "exact-depth" / f"depth-{depth}.stdout.json"), f"stdout receipt mismatch: {depth}")
        need(raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), f"exact-depth gate changed: {depth}")
        if depth in PUBLISHED:
            point = compact[depth]
            need((point["decode_tok_s"], point["output_token_ids_sha256"], point["raw_sha256"]) == (raw["metric_window"]["conventional_99_interval_tok_s"], raw["response"]["output_token_ids_sha256"], digest(path)), f"compact point changed: {depth}")

    states = {item["x"]: item for item in result["retained_structural_states"]}
    need(states[0]["state"] == "missing" and states[2048]["state"] == "quarantined" and states[8192]["state"] == "quarantined" and states[32768]["state"] == "closed", "structural classification changed")
    need(all("decode_tok_s" not in item for item in states.values()), "diagnostic speed leaked")
    prior = load(REPO / result["tracked_inputs"]["prior_depth_diagnostic"]["path"])
    need(2048 in prior["authority"]["target_parity_failed_depths"] and 32768 in prior["authority"]["exact_fatal_depths"], "prior structural evidence changed")
    sentinel = load(REPO / result["tracked_inputs"]["prior_8k_quarantine"]["path"])
    need(sentinel["status"] == "quarantined-target-parity-failed" and sentinel["target_failure"]["first_divergence"]["one_based"] == 99, "prior 8K quarantine changed")

    authority = result["authority"]
    need((authority["new_site_measured_cells"], authority["new_site_quarantined_cells"], authority["new_site_closed_cells"]) == (3, 1, 1), "site authority widened")
    need(authority["diagnostic_speed_cells"] == 0 and authority["zero_context_cells"] == 0, "diagnostic or x0 authority widened")
    need(not authority["headline_or_protected_replacement"] and not authority["existing_8k_speed_replacement"], "protected authority changed")
    need(authority["protected_decode_values_unchanged"] == PROTECTED, "protected values changed")
    return {"status": "pass", "measured_new": PUBLISHED, "quarantined": [2048, 8192], "closed": [32768], "x0": "missing"}


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2, sort_keys=True))
