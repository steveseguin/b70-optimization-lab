#!/usr/bin/env python3
"""Read-only validator for the TP1 E4M3 full-graph exact-4K quarantine."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-mtp0-e4m3kv-full-and-piecewise-4k-sentinel-20260826-r1")
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp0-e4m3kv-full-and-piecewise-4k-sentinel-r1-result.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


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

    need(arg("--tensor-parallel-size") == "1" and arg("--gpu-memory-utilization") == "0.90", "TP1 changed")
    need(arg("--kv-cache-dtype") == "fp8_e4m3" and "--enforce-eager" not in args, "E4M3 graph identity changed")
    compilation = json.loads(arg("--compilation-config"))
    need(compilation == {"cudagraph_mode": "FULL_AND_PIECEWISE", "cudagraph_capture_sizes": [1, 2], "max_cudagraph_capture_size": 2}, "graph config changed")
    need("ZE_AFFINITY_MASK=0" in env and "ONEAPI_DEVICE_SELECTOR=level_zero:0" in env and "PYTHONHASHSEED=0" in env, "environment changed")

    terminal = load(root / "terminal-receipt.json")
    need(digest(root / "terminal-receipt.json") == result["cleanup"]["terminal_receipt_sha256"], "terminal changed")
    need(terminal["terminal"] and terminal["runner_return_code"] == 38 and terminal["state"] == result["status"], "terminal not quarantined rc38")
    need(terminal["protected_profiles_untouched"] and not terminal["historical_replacement_allowed"] and not terminal["automatic_publication"], "terminal authority widened")

    arm = load(root / "arm-result.json")
    need(digest(root / "arm-result.json") == result["cleanup"]["arm_result_sha256"], "arm changed")
    passed = ("cleanup_passed", "full_and_piecewise_graph_identity_passed", "quality_contract_passed", "rank_cache_isolation_passed", "startup_identity_passed", "tp1_topology_passed")
    need(arm["runner_return_code"] == 38 and arm["exact_4k_return_code"] == 0 and arm["quality_return_code"] == 0 and all(arm[key] for key in passed), "non-parity gate failed")
    need(not arm["dual_e4m3_target_verification_passed"] and not arm["publication_authorized"] and not arm["descendant_execution_authorized"], "quarantine cause or authority changed")

    raw_path = root / "exact-depth/depth-4096.json"
    raw = load(raw_path)
    need(raw == load(root / "exact-depth/depth-4096.stdout.json") and raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), "exact depth failed")
    usage = raw["response"]["usage"]
    need(usage["prompt_tokens"] == 4096 and usage["completion_tokens"] == 128 and usage["prompt_tokens_details"]["cached_tokens"] == 0, "usage changed")
    diagnostic = result["diagnostic_point"]
    metrics = raw["metric_window"]
    need(diagnostic["raw_sha256"] == digest(raw_path) and diagnostic["candidate_output_token_ids_sha256"] == raw["response"]["output_token_ids_sha256"], "diagnostic payload changed")
    need(diagnostic["historical_100_event_decode_tok_s"] == metrics["historical_100_event_tok_s"] and diagnostic["conventional_99_interval_decode_tok_s"] == metrics["conventional_99_interval_tok_s"] and diagnostic["ttft_s"] == metrics["time_to_first_token_s"], "diagnostic timing changed")
    need(not diagnostic["site_speed_publication"] and not diagnostic["headline_authority"], "diagnostic speed authority appeared")

    target = load(root / "target-verification.json")
    expected = result["target_failure"]
    need(digest(root / "target-verification.json") == expected["raw_sha256"] and not target["passed"] and target["candidate_exact_passed"], "target failure changed")
    need(target["candidate_ids_sha256"] == expected["candidate_token_ids_sha256"] and target["eager_parent_ids_sha256"] == expected["eager_target_token_ids_sha256"] and target["piecewise_parent_ids_sha256"] == expected["piecewise_target_token_ids_sha256"], "target hashes changed")
    need(target["parents_equal"] and target["candidate_vs_eager_first_divergence"] == expected["first_divergence"] and expected["first_divergence"]["one_based"] == 95, "divergence changed")

    quality = load(root / "quality.json")
    need(digest(root / "quality.json") == result["quality"]["raw_sha256"] and quality["pass_all"] and quality["baseline_match_all"], "quality changed")
    usages = [item["usage"] for item in quality["exact_cases"]] + [item["usage"] for item in quality["repeat_case"]["runs"]] + [quality["long_context_case"]["usage"]]
    need(len(quality["exact_cases"]) == 7 and quality["repeat_case"]["pass"] and quality["repeat_case"]["repeats"] == 8 and len(quality["repeat_case"]["unique_hashes"]) == 1, "quality coverage changed")
    need(quality["long_context_case"]["pass"] and len(quality["baseline_comparisons"]) == 24 and len(usages) == 16 and all(item["prompt_tokens_details"]["cached_tokens"] == 0 for item in usages), "quality or cache-zero coverage changed")

    rank_cache = load(root / "rank-cache-isolation.json")
    need(digest(root / "rank-cache-isolation.json") == result["graph_topology_and_cache"]["rank_cache_raw_sha256"] and rank_cache["passed"] and rank_cache["observed_rank_namespaces"] == ["rank_0_0"], "rank cache changed")
    startup = (root / "server-startup.log").read_text(errors="replace")
    need(digest(root / "server-startup.log") == result["graph_topology_and_cache"]["startup_raw_sha256"], "startup log changed")
    for marker in ("world_size=1 rank=0 local_rank=0", "Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)", "Capturing CUDA graphs (decode, FULL)", "Graph capturing finished"):
        need(marker in startup, f"startup marker absent: {marker}")

    model = load(root / "model-verification.json")
    need(digest(root / "model-verification.json") == result["model_verification"]["raw_sha256"] and model["status"] == "verified" and len(model["files"]) == 19 and all(item["ok"] and item["paths_coherent"] for item in model["files"]), "model verification failed")

    authority = result["authority"]
    need(authority["site_structural_quarantine_cells"] == 1 and authority["site_measured_speed_cells"] == 0 and authority["diagnostic_speed_retained_only_in_evidence"], "site authority changed")
    need(not authority["raw_publication_authorized"] and not authority["historical_or_protected_replacement"] and not authority["other_depths_tp_mtp_graph_or_kv_inferred"], "authority widened")
    need(authority["protected_decode_values_unchanged"] == [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144], "protected values changed")
    return {"status": "pass", "structural_quarantine_cells": 1, "measured_speed_cells": 0, "tp": 1, "mtp": 0, "kv": "fp8_e4m3", "graph": "FULL_AND_PIECEWISE", "x": 4096, "divergence_token": 95, "runner_rc": 38}


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
