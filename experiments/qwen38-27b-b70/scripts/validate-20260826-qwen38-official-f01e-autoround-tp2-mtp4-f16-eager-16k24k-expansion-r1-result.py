#!/usr/bin/env python3
"""Read-only raw validator for TP2/MTP4 exact 16K+24K evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-16k24k-expansion-20260826-r1")
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-16k24k-expansion-r1-result.json"
PROTECTED = [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144]
DEPTHS = [16384, 24576]


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
    need(result["status"] == "passed-quality-clean-two-depth-expansion-evidence-only", "result status changed")

    for binding in result["tracked_inputs"].values():
        path = REPO / binding["path"]
        need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")
    for name, expected in result["identity"]["raw_sha256"].items():
        need(digest(root / name) == expected, f"identity changed: {name}")

    container = load(root / "container-inspect.json")[0]
    args, env = container["Config"]["Cmd"], container["Config"]["Env"]

    def arg(name: str) -> str:
        return args[args.index(name) + 1]

    need(arg("--tensor-parallel-size") == "2" and arg("--gpu-memory-utilization") == "0.60", "TP2 identity changed")
    need("--enforce-eager" in args and "--kv-cache-dtype" not in args and "--compilation-config" not in args, "eager/F16 identity changed")
    need(json.loads(arg("--speculative-config")) == {"method": "qwen3_next_mtp", "num_speculative_tokens": 4}, "MTP4 identity changed")
    need("ZE_AFFINITY_MASK=0,1" in env and not any(item.startswith("ONEAPI_DEVICE_SELECTOR=") for item in env), "device selection changed")
    need("VLLM_XPU_ENABLE_XPU_GRAPH=0" in env and "VLLM_XPU_GRAPH=0" in env, "graph-off identity changed")

    cleanup = result["cleanup"]
    terminal = load(root / "terminal-receipt.json")
    arm = load(root / "arm-result.json")
    need(digest(root / "terminal-receipt.json") == cleanup["terminal_receipt_sha256"], "terminal changed")
    need(digest(root / "arm-result.json") == cleanup["arm_result_sha256"], "arm changed")
    need(digest(root / "input-sha256sums.txt") == cleanup["input_sha256sums_sha256"], "input provenance changed")
    need(terminal["campaign_id"] == result["campaign_id"], "campaign identity changed")
    need(terminal["terminal"] and terminal["state"] == "passed-quality-clean-two-depth-expansion" and terminal["runner_return_code"] == 0, "terminal not clean pass")
    need(terminal["launch_git_head"] == cleanup["launch_git_head"] and terminal["protected_profiles_untouched"], "launch/protected identity changed")
    need(not terminal["automatic_descendant_expansion"] and not terminal["historical_replacement_allowed"], "terminal authority widened")
    passed_arm = ("startup_identity_passed", "objective_quality_passed", "same_topology_baseline_passed", "tp2_worker_topology_passed", "rank_cache_isolation_passed", "cleanup_passed")
    need(arm["state"] == "passed-quality-clean-two-depth-expansion" and arm["runner_return_code"] == arm["quality_return_code"] == 0, "arm state changed")
    need(all(arm[key] for key in passed_arm), "global arm gate failed")
    need(arm["passed_depth_count"] == arm["passed_acceptance_count"] == arm["passed_same_topology_target_count"] == 2, "arm count changed")
    need(arm["frozen_same_topology_oracle_depths"] == DEPTHS and arm["failed_or_quarantined_depths"] == [], "arm depth scope changed")
    need(not arm["complete_descendant_expansion_authorized"] and not arm["descendant_execution_authorized"] and not arm["historical_or_protected_replacement_allowed"], "arm authority widened")

    points = result["points"]
    need([point["x"] for point in points] == DEPTHS and len(result["same_topology_oracles"]) == 2, "result depth scope changed")
    arm_receipts = {item["depth"]: item for item in arm["depth_receipts"]}
    mechanisms = result["mechanism"]["depths"]
    oracles = {item["depth"]: item for item in result["same_topology_oracles"]}
    for point in points:
        depth = point["x"]
        raw_path = root / f"exact-depth/depth-{depth}.json"
        verify_path = root / f"verification/depth-{depth}.json"
        raw, verification = load(raw_path), load(verify_path)
        need(raw == load(root / f"exact-depth/depth-{depth}.stdout.json"), f"depth {depth} stdout differs")
        need(raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), f"depth {depth} exact gate failed")
        usage = raw["response"]["usage"]
        need(usage["prompt_tokens"] == depth and usage["completion_tokens"] == 128 and usage["prompt_tokens_details"]["cached_tokens"] == 0, f"depth {depth} usage changed")
        metric = raw["metric_window"]
        need(point["decode_tok_s"] == metric["conventional_99_interval_tok_s"], f"depth {depth} decode changed")
        need(point["historical_100_event_decode_tok_s"] == metric["historical_100_event_tok_s"], f"depth {depth} historical metric changed")
        need(point["ttft_ms"] == metric["time_to_first_token_s"] * 1000, f"depth {depth} TTFT changed")
        need(point["raw_sha256"] == digest(raw_path) and point["verification_raw_sha256"] == digest(verify_path), f"depth {depth} raw hash changed")
        need(point["output_token_ids_sha256"] == raw["response"]["output_token_ids_sha256"], f"depth {depth} output hash changed")

        receipt = arm_receipts[depth]
        need(receipt["return_code"] == 0 and receipt["exact_passed"] and receipt["acceptance_passed"] and receipt["target_parity_passed"] and receipt["per_depth_valid"], f"depth {depth} arm receipt failed")
        acceptance = verification["acceptance"]
        mechanism = mechanisms[str(depth)]
        for key in ("before_drafted_tokens", "after_drafted_tokens", "drafted_tokens", "before_accepted_tokens", "after_accepted_tokens", "accepted_tokens", "acceptance_rate"):
            need(math.isfinite(acceptance[key]) and acceptance[key] == mechanism[key], f"depth {depth} acceptance changed: {key}")
        need(acceptance["passed"] and acceptance["drafted_tokens"] > 0 and 0 < acceptance["accepted_tokens"] <= acceptance["drafted_tokens"], f"depth {depth} acceptance failed")
        need((point["accepted_tokens"], point["drafted_tokens"], point["draft_acceptance_rate"]) == (acceptance["accepted_tokens"], acceptance["drafted_tokens"], acceptance["acceptance_rate"]), f"depth {depth} point acceptance changed")

        parity = verification["same_topology_target_verification"]
        oracle = oracles[depth]
        target_path = Path(oracle["target_path"])
        need(parity["passed"] and parity["first_divergence"] is None and oracle["passed"], f"depth {depth} target parity failed")
        need(verification["candidate_ids_sha256"] == parity["target_ids_sha256"] == oracle["target_token_ids_sha256"] == point["output_token_ids_sha256"], f"depth {depth} parity hash changed")
        need(digest(target_path) == oracle["target_raw_sha256"] and raw["response"]["token_ids"] == load(target_path)["response"]["token_ids"], f"depth {depth} frozen target changed")

    need(result["mechanism"]["passed_depths"] == DEPTHS and result["mechanism"]["isolated_per_depth"] and result["mechanism"]["finite_positive_conserved_acceptance"], "mechanism summary changed")
    need((points[0]["accepted_tokens"], points[0]["drafted_tokens"], points[1]["accepted_tokens"], points[1]["drafted_tokens"]) == (89, 160, 93, 144), "required acceptance values changed")

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
    need("world_size=2 rank=0 local_rank=0" in server_text and "world_size=2 rank=1 local_rank=1" in server_text, "TP2 topology missing")
    model = load(root / "model-verification.json")
    model_result = result["model_verification"]
    need(digest(root / "model-verification.json") == model_result["raw_sha256"] and model["status"] == "verified", "model verification changed")
    need(len(model["files"]) == 19 and all(item["ok"] and item["paths_coherent"] for item in model["files"]), "model file verification failed")

    authority = result["authority"]
    need(authority["evidence_depths"] == DEPTHS and authority["site_cells"] == 0 and not authority["publication_authorized"], "publication authority changed")
    need(authority["protected_decode_values_unchanged"] == PROTECTED and not authority["historical_or_protected_replacement"], "protected authority changed")
    need(not authority["other_depths_tp_mtp_graph_or_kv_inferred"] and not authority["automatic_depth_or_descendant_expansion"], "scope widened")
    need(authority["existing_8k_quarantine_unchanged"] and authority["x0_2k_4k_8k_32k_not_selected_by_this_result"] and not authority["localmaxxing_submission"], "excluded-cell authority changed")

    return {"status": "pass", "evidence_depths": DEPTHS, "site_cells": 0, "tp": 2, "mtp": 4, "accepted": [89, 93], "drafted": [160, 144]}


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
