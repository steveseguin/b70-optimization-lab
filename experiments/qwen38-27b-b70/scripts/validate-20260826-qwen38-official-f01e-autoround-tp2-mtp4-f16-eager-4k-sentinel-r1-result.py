#!/usr/bin/env python3
"""Read-only validator for the published current-f01e TP2/MTP4 4K sentinel."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-4k-sentinel-20260826-r1")
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-4k-sentinel-r1-result.json"
PROTECTED = [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144]


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def need(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def validate(root: Path = ROOT, result_path: Path = RESULT) -> dict:
    result = load(result_path)
    need(result["status"] == "passed-quality-clean-sentinel-human-adjudicated-grade-c", "result not Grade C")

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

    need(arg("--tensor-parallel-size") == "2" and arg("--gpu-memory-utilization") == "0.60", "TP2 identity changed")
    need("--enforce-eager" in args and "--kv-cache-dtype" not in args and "--compilation-config" not in args, "eager/F16 changed")
    need(json.loads(arg("--speculative-config")) == {"method": "qwen3_next_mtp", "num_speculative_tokens": 4}, "MTP4 changed")
    need("ZE_AFFINITY_MASK=0,1" in env and not any(item.startswith("ONEAPI_DEVICE_SELECTOR=") for item in env), "GPU selection changed")
    need("VLLM_XPU_ENABLE_XPU_GRAPH=0" in env and "VLLM_XPU_GRAPH=0" in env, "graph-off identity changed")

    cleanup = result["cleanup"]
    terminal = load(root / "terminal-receipt.json")
    need(digest(root / "terminal-receipt.json") == cleanup["terminal_receipt_sha256"], "terminal changed")
    need(digest(root / "input-sha256sums.txt") == cleanup["input_sha256sums_sha256"], "input provenance changed")
    need(terminal["terminal"] and terminal["runner_return_code"] == 0 and terminal["state"] == "passed-quality-clean-sentinel", "terminal not clean rc0")
    need(terminal["launch_git_head"] == cleanup["launch_git_head"] and terminal["protected_profiles_untouched"], "launch/protected identity changed")
    need(not terminal["publication_authorized"] and not terminal["depth_expansion_authorized"] and not terminal["descendant_execution_authorized"] and not terminal["automatic_descendant_expansion"], "raw authority widened")

    arm = load(root / "arm-result.json")
    need(digest(root / "arm-result.json") == cleanup["arm_result_sha256"], "arm changed")
    passed = (
        "acceptance_conserved",
        "acceptance_passed",
        "cleanup_passed",
        "exact_depth_and_cache_zero_passed",
        "objective_quality_passed",
        "rank_cache_isolation_passed",
        "same_topology_baseline_comparison_passed",
        "same_topology_target_verification_passed",
        "startup_identity_passed",
        "tp2_worker_topology_passed",
    )
    need(arm["runner_return_code"] == 0 and arm["exact_4k_return_code"] == 0 and arm["quality_return_code"] == 0 and all(arm[key] for key in passed), "arm gate failed")
    need(not arm["publication_authorized"] and not arm["depth_expansion_authorized"] and not arm["descendant_execution_authorized"] and not arm["descendant_expansion_authorized"], "arm authority widened")

    raw_path = root / "exact-depth/depth-4096.json"
    raw = load(raw_path)
    need(raw == load(root / "exact-depth/depth-4096.stdout.json"), "stdout receipt differs")
    need(raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), "exact-depth gate failed")
    usage = raw["response"]["usage"]
    need(usage["prompt_tokens"] == 4096 and usage["completion_tokens"] == 128 and usage["prompt_tokens_details"]["cached_tokens"] == 0, "exact usage changed")
    metric = raw["metric_window"]
    point = result["point"]
    need(point["x"] == 4096 and point["decode_tok_s"] == metric["conventional_99_interval_tok_s"], "decode point changed")
    need(point["ttft_ms"] == metric["time_to_first_token_s"] * 1000 and point["raw_sha256"] == digest(raw_path), "TTFT/raw point changed")
    need(point["cached_tokens"] == 0 and point["completion_tokens"] == 128 and point["output_token_ids_sha256"] == raw["response"]["output_token_ids_sha256"], "point receipt changed")

    gates = load(root / "verification-gates.json")
    mechanism = result["mechanism"]
    need(digest(root / "verification-gates.json") == mechanism["raw_sha256"], "verification gates changed")
    acceptance = gates["acceptance"]
    for key in ("before_drafted_tokens", "after_drafted_tokens", "drafted_tokens", "before_accepted_tokens", "after_accepted_tokens", "accepted_tokens", "acceptance_rate"):
        need(math.isfinite(acceptance[key]) and acceptance[key] == mechanism[key], f"acceptance changed: {key}")
    need(acceptance["passed"] and acceptance["conserved"], "acceptance failed")
    need((point["accepted_tokens"], point["drafted_tokens"], point["draft_acceptance_rate"]) == (90, 148, acceptance["acceptance_rate"]), "published acceptance changed")

    target = gates["target_verification"]
    oracle = result["same_topology_oracle"]
    need(target["passed"] and target["first_divergence"] is None and target["candidate_token_count"] == target["target_token_count"] == 128, "target parity failed")
    need(target["candidate_ids_sha256"] == target["target_ids_sha256"] == oracle["target_token_ids_sha256"] == point["output_token_ids_sha256"], "target hash changed")
    target_path = Path(oracle["target_path"])
    need(digest(target_path) == oracle["target_raw_sha256"] and raw["response"]["token_ids"] == load(target_path)["response"]["token_ids"], "frozen oracle changed")

    quality = load(root / "quality.json")
    quality_result = result["quality"]
    need(digest(root / "quality.json") == quality_result["raw_sha256"], "quality receipt changed")
    need(quality["pass_all"] and quality["baseline_match_all"] and len(quality["exact_cases"]) == 7 and all(item["pass"] for item in quality["exact_cases"]), "quality failed")
    repeat = quality["repeat_case"]
    need(repeat["pass"] and repeat["repeats"] == 8 and len(repeat["unique_hashes"]) == 1 and quality["long_context_case"]["pass"], "repeat/needle failed")
    need(len(quality["baseline_comparisons"]) == 24 and all(quality["baseline_comparisons"].values()), "baseline comparison failed")
    usages = [item["usage"] for item in quality["exact_cases"]] + [item["usage"] for item in repeat["runs"]] + [quality["long_context_case"]["usage"]]
    need(len(usages) == 16 and all(item["prompt_tokens_details"]["cached_tokens"] == 0 for item in usages), "cache reuse appeared")

    topology = result["topology_and_cache"]
    need(digest(root / "rank-cache-isolation.txt") == topology["rank_cache_raw_sha256"] and (root / "rank-cache-isolation.txt").read_text().strip() == topology["rank_cache_status"], "rank cache changed")
    server_log = root / "server.log"
    server_text = server_log.read_text(errors="replace")
    need(digest(server_log) == topology["server_log_sha256"], "server log changed")
    need("world_size=2 rank=0 local_rank=0" in server_text and "world_size=2 rank=1 local_rank=1" in server_text, "TP2 worker topology missing")
    model = load(root / "model-verification.json")
    model_result = result["model_verification"]
    need(digest(root / "model-verification.json") == model_result["raw_sha256"] and model["status"] == "verified", "model verification changed")
    need(len(model["files"]) == 19 and all(item["ok"] and item["paths_coherent"] for item in model["files"]), "model file verification failed")

    adjudication = result["adjudication"]
    authority = result["authority"]
    need(not adjudication["raw_automatic_publication_authority"] and adjudication["explicit_human_per_cell_publication_authority"] and adjudication["published_depths"] == [4096], "adjudication changed")
    need(not adjudication["descendant_expansion_authorized"] and adjudication["quarantined_8k_retained"], "expansion/quarantine authority changed")
    need(authority["site_cells"] == 1 and authority["quality_grade"] == "C" and not authority["historical_or_protected_replacement"], "site authority changed")
    need(authority["protected_decode_values_unchanged"] == PROTECTED and not authority["other_depths_tp_mtp_graph_or_kv_inferred"], "protected/scope changed")
    need(not authority["automatic_depth_or_descendant_expansion"] and authority["existing_8k_quarantine_unchanged"] and authority["x0_2k_16k_24k_32k_remain_missing"], "cell scope widened")

    return {"status": "pass", "cells_published": 1, "tp": 2, "mtp": 4, "depth": 4096, "accepted": 90, "drafted": 148, "grade": "C"}


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
