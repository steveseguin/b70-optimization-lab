#!/usr/bin/env python3
"""Read-only validator for the current-f01e TP2/MTP0 PIECEWISE partial result."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp2-mtp0-f16-piecewise-depth-20260826-r1")
TARGET_ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp2-mtp0-f16-eager-depth-expansion-20260826-r1")
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp0-f16-piecewise-depth-r1-result.json"
DEPTHS = [2048, 4096, 8192, 16384, 24576, 32768]
VALID_DEPTHS = [2048, 4096, 24576, 32768]
QUARANTINED_DEPTHS = [8192, 16384]
PROTECTED = [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144]


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
    need(result["status"] == "partial-depth-expansion-human-adjudicated-grade-c", "result status changed")
    need(result["published_decode_field"] == "conventional_99_interval_tok_s", "site metric changed")
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
    need("--enforce-eager" not in args and "--kv-cache-dtype" not in args and "--speculative-config" not in args, "target-only PIECEWISE/F16 changed")
    need(json.loads(arg("--compilation-config")) == {"cudagraph_mode": "PIECEWISE", "cudagraph_capture_sizes": [1], "max_cudagraph_capture_size": 1}, "PIECEWISE config changed")
    need("VLLM_XPU_ENABLE_XPU_GRAPH=1" in env and "ZE_AFFINITY_MASK=0,1" in env and not any(item.startswith("ONEAPI_DEVICE_SELECTOR=") for item in env), "graph/GPU environment changed")
    startup = (root / "server-startup.log").read_text()
    for marker in (
        "tensor_parallel_size=2",
        "speculative_config=None",
        "quantization=inc",
        "enforce_eager=False",
        "kv_cache_dtype=auto",
        "cudagraph_mode': <CUDAGraphMode.PIECEWISE: 1>",
        "world_size=2, local_world_size=2",
        "Compiling a graph for compile range (1, 1024)",
        "Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)",
        "Graph capturing finished",
    ):
        need(marker in startup, f"startup identity missing: {marker}")
    need("Capturing CUDA graphs (decode, FULL)" not in startup and "enforce_eager=True" not in startup, "forbidden graph identity appeared")

    terminal = load(root / "terminal-receipt.json")
    arm = load(root / "arm-result.json")
    need(digest(root / "terminal-receipt.json") == result["cleanup"]["terminal_receipt_sha256"], "terminal changed")
    need(digest(root / "arm-result.json") == result["cleanup"]["arm_result_sha256"], "arm changed")
    need(terminal["terminal"] and terminal["state"] == "partial-depth-expansion" and terminal["runner_return_code"] == 37, "terminal partial receipt changed")
    need(not terminal["automatic_publication_allowed"] and not terminal["historical_replacement_allowed"] and not terminal["automatic_descendant_execution"], "terminal authority widened")
    need(arm["state"] == "partial-depth-expansion" and arm["runner_return_code"] == 37, "arm state changed")
    need(arm["exact_passed_count"] == 6 and arm["same_image_target_passed_count"] == 4 and arm["valid_depths"] == VALID_DEPTHS and arm["invalid_or_quarantined_depths"] == QUARANTINED_DEPTHS, "per-depth authority changed")
    need(arm["startup_graph_identity_passed"] and arm["tp2_worker_topology_passed"] and arm["rank_cache_isolation_passed"] and arm["objective_quality_passed"] and arm["same_topology_baseline_passed"] and arm["cleanup_passed"], "global gate failed")
    need(not arm["automatic_publication_allowed"] and not arm["historical_or_protected_replacement_allowed"] and not arm["descendant_execution_authorized"], "arm authority widened")

    rank_cache = load(root / "rank-cache-isolation.json")
    need(digest(root / "rank-cache-isolation.json") == result["graph_and_topology"]["rank_cache_raw_sha256"], "rank cache changed")
    need(rank_cache["passed"] and rank_cache["expected_rank_namespaces"] == ["rank_0_0", "rank_1_0"] and rank_cache["observed_rank_namespaces"] == ["rank_0_0", "rank_1_0"], "rank namespaces changed")

    valid = []
    quarantined = []
    receipts = {item["depth"]: item for item in arm["depth_receipts"]}
    for depth in DEPTHS:
        raw_path = root / "exact-depth" / f"depth-{depth}.json"
        verification_path = root / "verification" / f"depth-{depth}.json"
        raw = load(raw_path)
        verification = load(verification_path)
        target_raw = load(TARGET_ROOT / "exact-depth" / f"depth-{depth}.json")
        need(raw == load(root / "exact-depth" / f"depth-{depth}.stdout.json"), f"stdout differs: {depth}")
        need(raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), f"exact depth failed: {depth}")
        usage = raw["response"]["usage"]
        need(usage["prompt_tokens"] == depth and usage["completion_tokens"] == 128 and usage["prompt_tokens_details"]["cached_tokens"] == 0, f"usage changed: {depth}")
        same_image = verification["same_image_target_comparison"]
        need(same_image == receipts[depth]["verification"]["same_image_target_comparison"], f"arm verification differs: {depth}")
        point = (depth, raw["metric_window"]["conventional_99_interval_tok_s"], raw["response"]["output_token_ids_sha256"], digest(raw_path), digest(verification_path))
        if depth in VALID_DEPTHS:
            need(same_image["passed"] and same_image["first_divergence"] is None, f"target parity failed: {depth}")
            need(raw["response"]["token_ids"] == target_raw["response"]["token_ids"], f"direct target IDs differ: {depth}")
            need(receipts[depth]["same_image_target_passed"], f"arm valid receipt failed: {depth}")
            valid.append(point)
        else:
            expected_divergence = {8192: {"candidate": 411, "one_based": 99, "target": 579, "zero_based": 98}, 16384: {"candidate": 13, "one_based": 32, "target": 11, "zero_based": 31}}[depth]
            need(not same_image["passed"] and same_image["first_divergence"] == expected_divergence, f"quarantine divergence changed: {depth}")
            need(raw["response"]["token_ids"] != target_raw["response"]["token_ids"] and not receipts[depth]["same_image_target_passed"], f"quarantine unexpectedly passed: {depth}")
            quarantined.append((*point, expected_divergence))

    expected_valid = [(point["x"], point["decode_tok_s"], point["output_token_ids_sha256"], point["raw_sha256"], point["verification_sha256"]) for point in result["valid_points"]]
    need(valid == expected_valid, "valid points differ from raw")
    expected_quarantined = []
    for point in result["quarantined_points"]:
        expected_quarantined.append((point["x"], point["decode_tok_s_diagnostic_only"], point["output_token_ids_sha256"], point["raw_sha256"], point["verification_sha256"], {"candidate": point["candidate_token"], "one_based": point["first_divergence_one_based"], "target": point["target_token"], "zero_based": point["first_divergence_zero_based"]}))
        need(point["exact_depth_gate_passed"] and point["cache_zero"] and point["site_action"] == "quarantine-no-speed", f"quarantine disclosure weakened: {point['x']}")
    need(quarantined == expected_quarantined, "quarantined points differ from raw")

    quality = load(root / "quality.json")
    need(digest(root / "quality.json") == result["quality"]["raw_sha256"] and quality["pass_all"] and quality["baseline_match_all"], "quality changed")
    usages = [item["usage"] for item in quality["exact_cases"]] + [item["usage"] for item in quality["repeat_case"]["runs"]] + [quality["long_context_case"]["usage"]]
    need(len(quality["exact_cases"]) == 7 and quality["repeat_case"]["pass"] and quality["repeat_case"]["repeats"] == 8 and len(quality["repeat_case"]["unique_hashes"]) == 1, "quality cardinality changed")
    need(quality["long_context_case"]["pass"] and len(quality["baseline_comparisons"]) == 24 and len(usages) == 16 and all(item["prompt_tokens_details"]["cached_tokens"] == 0 for item in usages), "quality/cache gate weakened")
    model = load(root / "model-verification.json")
    need(digest(root / "model-verification.json") == result["model_verification"]["raw_sha256"] and model["status"] == "verified" and len(model["files"]) == 19 and all(item["direct_mode"] == "odirect" and item["ok"] and item["paths_coherent"] for item in model["files"]), "model verification weakened")

    authority = result["authority"]
    need(authority["qualified_raw_cells"] == authority["new_site_measured_cells"] == 4 and authority["new_site_quarantined_cells"] == 2 and authority["zero_context_cells"] == 0, "site authority widened")
    need(not authority["headline_or_protected_replacement"] and not authority["current_eager_profile_replacement"] and not authority["dated_fully_certified_graph_profile_replacement"] and not authority["frontier_or_localmaxxing_replacement"] and not authority["diagnostic_quarantine_speeds_exposed_on_site"], "replacement or diagnostic speed enabled")
    need(authority["protected_decode_values_unchanged"] == PROTECTED, "protected values changed")
    need(result["adjudication"]["valid_depths"] == VALID_DEPTHS and result["adjudication"]["quarantined_depths"] == QUARANTINED_DEPTHS and not result["adjudication"]["automatic_publication_authority"], "adjudication changed")
    return {"status": "pass", "raw_exact": "6/6", "target_parity": "4/6", "new_site_measured": 4, "quarantined": QUARANTINED_DEPTHS, "quality_cache_zero": "16/16", "graph_mode": "PIECEWISE", "x0": "missing"}


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
