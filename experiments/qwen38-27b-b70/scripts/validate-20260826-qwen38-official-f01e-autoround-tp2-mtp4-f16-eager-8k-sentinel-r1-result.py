#!/usr/bin/env python3
"""Read-only validator for the TP2/MTP4 exact-8K structural quarantine."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-8k-sentinel-20260826-r1")
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-8k-sentinel-r1-result.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def need(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def validate(root: Path = ROOT, result_path: Path = RESULT) -> dict:
    result = load(result_path)
    need(result["status"] == "quarantined-target-parity-failed", "wrong result state")

    for binding in result["tracked_inputs"].values():
        path = REPO / binding["path"]
        need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")
    for name, expected in result["identity"]["raw_sha256"].items():
        need(digest(root / name) == expected, f"identity changed: {name}")

    container = load(root / "container-inspect.json")[0]
    args = container["Config"]["Cmd"]
    env = container["Config"]["Env"]

    def arg(name: str) -> str:
        return args[args.index(name) + 1]

    need(arg("--tensor-parallel-size") == "2" and arg("--gpu-memory-utilization") == "0.60", "TP2 changed")
    need("--enforce-eager" in args and "--kv-cache-dtype" not in args and "--compilation-config" not in args, "eager/F16 changed")
    need(json.loads(arg("--speculative-config")) == {"method": "qwen3_next_mtp", "num_speculative_tokens": 4}, "MTP4 changed")
    need("ZE_AFFINITY_MASK=0,1" in env and not any(item.startswith("ONEAPI_DEVICE_SELECTOR=") for item in env), "GPU selection changed")

    terminal = load(root / "terminal-receipt.json")
    need(digest(root / "terminal-receipt.json") == result["cleanup"]["terminal_receipt_sha256"], "terminal changed")
    need(terminal["terminal"] and terminal["runner_return_code"] == 39 and terminal["state"] == result["status"], "terminal not quarantined rc39")
    need(terminal["protected_profiles_untouched"] and not terminal["historical_replacement_allowed"] and not terminal["automatic_descendant_expansion"], "terminal authority widened")

    arm = load(root / "arm-result.json")
    need(digest(root / "arm-result.json") == result["cleanup"]["arm_result_sha256"], "arm changed")
    passed = (
        "acceptance_conserved",
        "acceptance_passed",
        "cleanup_passed",
        "objective_quality_passed",
        "rank_cache_isolation_passed",
        "same_topology_baseline_comparison_passed",
        "startup_identity_passed",
        "tp2_worker_topology_passed",
    )
    need(arm["runner_return_code"] == 39 and arm["exact_8k_return_code"] == 0 and arm["quality_return_code"] == 0 and all(arm[key] for key in passed), "non-parity gate failed")
    need(not arm["same_topology_target_verification_passed"] and arm["lower_grade_evidence_retained"], "quarantine cause changed")
    need(not arm["publication_authorized"] and not arm["depth_expansion_authorized"] and not arm["descendant_execution_authorized"], "raw authority widened")

    raw_path = root / "exact-depth/depth-8192.json"
    raw = load(raw_path)
    need(raw == load(root / "exact-depth/depth-8192.stdout.json") and raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), "exact depth failed")
    usage = raw["response"]["usage"]
    need(usage["prompt_tokens"] == 8192 and usage["completion_tokens"] == 128 and usage["prompt_tokens_details"]["cached_tokens"] == 0, "usage changed")
    diagnostic = result["diagnostic_point"]
    metrics = raw["metric_window"]
    need(diagnostic["raw_sha256"] == digest(raw_path) and diagnostic["historical_100_event_decode_tok_s"] == metrics["historical_100_event_tok_s"] and diagnostic["conventional_99_interval_decode_tok_s"] == metrics["conventional_99_interval_tok_s"] and diagnostic["ttft_s"] == metrics["time_to_first_token_s"], "diagnostic timing changed")
    need(not diagnostic["site_speed_publication"] and not diagnostic["headline_authority"], "diagnostic speed authority appeared")

    gates = load(root / "verification-gates.json")
    need(digest(root / "verification-gates.json") == result["mechanism"]["raw_sha256"], "verification changed")
    acceptance = gates["acceptance"]
    for key in ("before_drafted_tokens", "after_drafted_tokens", "drafted_tokens", "before_accepted_tokens", "after_accepted_tokens", "accepted_tokens", "acceptance_rate"):
        need(math.isfinite(acceptance[key]) and acceptance[key] == result["mechanism"][key], f"acceptance changed: {key}")
    need(acceptance["passed"] and acceptance["conserved"], "acceptance failed")

    target = gates["target_verification"]
    expected = result["target_failure"]
    need(not target["passed"] and target["candidate_ids_sha256"] == expected["candidate_token_ids_sha256"] and target["target_ids_sha256"] == expected["target_token_ids_sha256"], "target failure changed")
    need(target["first_divergence"] == expected["first_divergence"] and target["first_divergence"]["one_based"] == 99, "divergence changed")
    need(digest(Path(expected["target_path"])) == expected["target_raw_sha256"], "target oracle changed")

    quality = load(root / "quality.json")
    need(digest(root / "quality.json") == result["quality"]["raw_sha256"] and quality["pass_all"] and quality["baseline_match_all"], "quality changed")
    repeat = quality["repeat_case"]
    usages = [item["usage"] for item in quality["exact_cases"]] + [item["usage"] for item in repeat["runs"]] + [quality["long_context_case"]["usage"]]
    need(len(quality["exact_cases"]) == 7 and repeat["pass"] and repeat["repeats"] == 8 and quality["long_context_case"]["pass"] and len(quality["baseline_comparisons"]) == 24, "quality coverage changed")
    need(len(usages) == 16 and all(item["prompt_tokens_details"]["cached_tokens"] == 0 for item in usages), "cache reuse appeared")

    need(digest(root / "rank-cache-isolation.txt") == result["topology_and_cache"]["rank_cache_raw_sha256"], "rank cache changed")
    model = load(root / "model-verification.json")
    need(digest(root / "model-verification.json") == result["model_verification"]["raw_sha256"] and model["status"] == "verified" and len(model["files"]) == 19 and all(item["ok"] and item["paths_coherent"] for item in model["files"]), "model verification failed")

    authority = result["authority"]
    need(not authority["raw_publication_authorized"] and authority["site_structural_quarantine_cells"] == 1 and authority["site_measured_speed_cells"] == 0 and authority["diagnostic_speed_retained_only_in_evidence"], "site authority changed")
    need(not authority["historical_or_protected_replacement"] and not authority["other_depths_tp_mtp_graph_or_kv_inferred"] and authority["protected_decode_values_unchanged"] == [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144], "protected/scope changed")
    return {"status": "pass", "structural_quarantine_cells": 1, "measured_speed_cells": 0, "tp": 2, "mtp": 4, "divergence_token": 99, "runner_rc": 39}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--result", type=Path, default=RESULT)
    args = parser.parse_args()
    try:
        report = validate(args.root, args.result)
    except (KeyError, OSError, TypeError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
