#!/usr/bin/env python3
"""Read-only validator for the pending TP1/MTP1 eager/E4M3 exact-4K cell."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOT = Path(
    "/mnt/fast-ai/bench-results/"
    "qwen38-official-f01e-autoround-tp1-mtp1-e4m3kv-eager-4k-sentinel-20260826-r1"
)
RESULT = REPO / (
    "experiments/qwen38-27b-b70/data/"
    "2026-08-26-qwen38-official-f01e-autoround-tp1-mtp1-e4m3kv-eager-4k-sentinel-r1-result.json"
)
PROTECTED = [
    71.45427094575045,
    30.329809361830037,
    49.05894025767351,
    71.9001988117144,
]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def need(value, message):
    if not value:
        raise RuntimeError(message)


def arg_value(args, name):
    return args[args.index(name) + 1]


def validate(root: Path, result_path: Path):
    result = load(result_path)
    need(result["status"] == "passed-quality-clean-sentinel", "result is not passed")
    need(result["raw_root"] == str(root), "raw root binding changed")
    for binding in result["tracked_inputs"].values():
        path = REPO / binding["path"]
        need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")

    identity = result["identity"]
    for name, expected in identity["raw_sha256"].items():
        need(digest(root / name) == expected, f"raw identity changed: {name}")
    need((root / "image-id.txt").read_text().strip() == identity["image"].split("@", 1)[1], "image changed")
    need((root / "vllm-source-commit.txt").read_text().strip() == identity["vllm_source"], "vLLM source changed")
    need(
        (root / "stack-versions.txt").read_text().splitlines()
        == [identity["vllm_version"], identity["xpu_kernels_version"]],
        "stack changed",
    )

    container = load(root / "container-inspect.json")[0]
    args, env = container["Config"]["Cmd"], container["Config"]["Env"]
    need(arg_value(args, "--tensor-parallel-size") == "1", "TP1 changed")
    need(arg_value(args, "--pipeline-parallel-size") == "1", "PP1 changed")
    need(arg_value(args, "--data-parallel-size") == "1", "DP1 changed")
    need(arg_value(args, "--max-model-len") == "32896", "context capacity changed")
    need(arg_value(args, "--max-num-seqs") == "1", "parallel slots changed")
    need(arg_value(args, "--max-num-batched-tokens") == "1024", "batch cap changed")
    need(arg_value(args, "--gpu-memory-utilization") == "0.90", "memory utilization changed")
    need(arg_value(args, "--kv-cache-dtype") == "fp8_e4m3", "E4M3 KV identity changed")
    need("--enforce-eager" in args and "--compilation-config" not in args, "eager identity changed")
    need(
        json.loads(arg_value(args, "--speculative-config"))
        == {"method": "qwen3_next_mtp", "num_speculative_tokens": 1},
        "MTP1 changed",
    )
    need("--no-enable-prefix-caching" in args, "prefix cache policy changed")
    need("ZE_AFFINITY_MASK=0" in env and "ONEAPI_DEVICE_SELECTOR=level_zero:0" in env, "TP1 device binding changed")
    need("PYTHONHASHSEED=0" in env, "hash seed changed")
    need("VLLM_XPU_ENABLE_XPU_GRAPH=1" not in env, "graph environment appeared")
    cache_root = result["runtime_isolation"]["dedicated_cache_root"]
    mounts = container["Mounts"]
    need(
        any(
            mount["Source"] == cache_root
            and mount["Destination"] == "/run-cache"
            and mount["RW"] is True
            for mount in mounts
        ),
        "dedicated cache mount changed",
    )
    startup = (root / "server-startup.log").read_text(errors="replace")
    for marker in (
        "'enforce_eager': True",
        "'kv_cache_dtype': 'fp8_e4m3'",
        "SpeculativeConfig(method='mtp'",
        "num_spec_tokens=1",
        "tensor_parallel_size=1",
        "enforce_eager=True",
        "kv_cache_dtype=fp8_e4m3",
        "world_size=1 rank=0 local_rank=0",
        "TP rank 0",
    ):
        need(marker in startup, f"missing startup marker: {marker}")
    need("cudagraph_mode': <CUDAGraphMode.NONE: 0>" in startup, "graph-off startup identity changed")
    need("Capturing CUDA graphs" not in startup and "Graph capturing finished" not in startup, "graph capture appeared")

    terminal, arm = load(root / "terminal-receipt.json"), load(root / "arm-result.json")
    cleanup = result["cleanup"]
    need(digest(root / "terminal-receipt.json") == cleanup["terminal_receipt_sha256"], "terminal changed")
    need(digest(root / "arm-result.json") == cleanup["arm_result_sha256"], "arm changed")
    need(terminal["terminal"] and terminal["runner_return_code"] == 0, "terminal failed")
    need(terminal["state"] == "passed-quality-clean-sentinel", "terminal state changed")
    need(terminal["launch_git_head"] == cleanup["launch_git_head"], "launch head changed")
    need(terminal["protected_profiles_untouched"], "protected profiles changed")
    need(not terminal["automatic_publication"] and not terminal["automatic_descendant_expansion"], "terminal authority widened")
    need(arm["exact_4k_return_code"] == 0 and arm["quality_return_code"] == 0, "raw gate rc changed")
    need(
        all(
            arm[key]
            for key in (
                "acceptance_passed",
                "cleanup_passed",
                "startup_identity_passed",
                "target_verification_passed",
            )
        ),
        "raw gate failed",
    )
    need(
        not arm["publication_authorized"]
        and not arm["descendant_expansion_authorized"]
        and not arm["descendant_execution_authorized"]
        and not arm["historical_replacement_allowed"],
        "raw authority changed",
    )

    raw_path = root / "exact-depth/depth-4096.json"
    raw = load(raw_path)
    need(raw == load(root / "exact-depth/depth-4096.stdout.json"), "stdout mirror changed")
    need((root / "exact-depth/depth-4096.rc").read_text().strip() == "0", "exact 4K rc changed")
    need(raw["status"] == "passed" and raw["gate"]["passed"], "exact 4K gate failed")
    need(all(raw["gate"]["checks"].values()), "an exact 4K check failed")
    metric, response, usage = raw["metric_window"], raw["response"], raw["response"]["usage"]
    point = result["point"]
    need(digest(raw_path) == point["raw_sha256"], "raw point changed")
    need(metric["conventional_99_interval_tok_s"] == point["decode_tok_s"], "decode changed")
    need(metric["historical_100_event_tok_s"] == point["historical_100_event_decode_tok_s"], "historical metric changed")
    need(metric["time_to_first_token_s"] == point["ttft_s"], "TTFT seconds changed")
    need(metric["time_to_first_token_s"] * 1000 == point["ttft_ms"], "TTFT milliseconds changed")
    need(metric["timestamped_events"] == 100 and metric["inter_token_intervals"] == 99, "metric window changed")
    need(
        usage["prompt_tokens"] == 4096
        and usage["completion_tokens"] == 128
        and usage["prompt_tokens_details"]["cached_tokens"] == 0,
        "usage changed",
    )
    need(len(response["token_ids"]) == 128, "token count changed")
    need(response["output_token_ids_sha256"] == point["output_token_ids_sha256"], "output hash changed")

    gates = load(root / "verification-gates.json")
    mechanism, oracle = result["mechanism"], result["target_oracle"]
    need(digest(root / "verification-gates.json") == mechanism["raw_sha256"], "verification gates changed")
    acceptance = gates["acceptance"]
    need(acceptance["passed"] and acceptance["drafted_tokens"] == mechanism["drafted_tokens"], "draft count changed")
    need(acceptance["accepted_tokens"] == mechanism["accepted_tokens"], "accepted count changed")
    need(acceptance["acceptance_rate"] == mechanism["acceptance_rate"], "acceptance rate changed")
    target_gate = gates["target_verification"]
    need(target_gate["passed"] and target_gate["first_divergence"] is None, "target parity failed")
    need(target_gate["candidate_token_count"] == target_gate["target_token_count"] == oracle["token_count"], "oracle token count changed")
    need(target_gate["candidate_ids_sha256"] == target_gate["target_ids_sha256"] == oracle["target_token_ids_sha256"], "oracle hash changed")
    target_path = Path(oracle["target_path"])
    target = load(target_path)
    need(digest(target_path) == oracle["target_raw_sha256"], "frozen target changed")
    need(response["token_ids"] == target["response"]["token_ids"], "candidate no longer equals target")

    quality = load(root / "quality.json")
    expected_quality = result["quality"]
    need(digest(root / "quality.json") == expected_quality["raw_sha256"], "quality changed")
    need(quality["pass_all"] and quality["baseline_match_all"], "quality failed")
    need(len(quality["exact_cases"]) == 7 and all(case["pass"] for case in quality["exact_cases"]), "exact quality failed")
    repeat = quality["repeat_case"]
    need(repeat["pass"] and repeat["repeats"] == 8 and len(repeat["unique_hashes"]) == 1, "repeat quality failed")
    need(
        quality["long_context_case"]["pass"]
        and len(quality["baseline_comparisons"]) == 24
        and all(quality["baseline_comparisons"].values()),
        "needle/baseline quality failed",
    )
    usages = (
        [case["usage"] for case in quality["exact_cases"]]
        + [run["usage"] for run in repeat["runs"]]
        + [quality["long_context_case"]["usage"]]
    )
    need(len(usages) == 16, "quality request count changed")
    need(all(item["prompt_tokens_details"]["cached_tokens"] == 0 for item in usages), "quality cache reuse appeared")

    verification = load(root / "model-verification.json")
    model = result["model_verification"]
    need(digest(root / "model-verification.json") == model["raw_sha256"], "model verification changed")
    need(
        verification["status"] == "verified"
        and len(verification["files"]) == 19
        and all(item["ok"] and item["paths_coherent"] for item in verification["files"]),
        "model verification failed",
    )

    candidate, authority = result["publication_candidate"], result["authority"]
    need(candidate["decision"] == "pending-separate-family-and-site-publication", "publication state changed")
    need(candidate["selected_depths"] == [4096], "selected depth scope widened")
    need(candidate["missing_depths"] == [0, 2048, 8192, 16384, 24576, 32768], "missing depths changed")
    need(candidate["candidate_grade"] == "C" and not candidate["publication_is_automatic"], "candidate grade/authority changed")
    need(authority["measured_cells_pending_publication"] == 1, "one-cell pending authority missing")
    need(authority["site_cells_published_by_this_packet"] == 0, "packet claims a published site cell")
    need(not authority["site_or_family_publication_authorized_by_raw_runner"], "raw runner publication appeared")
    need(authority["quality_grade_candidate"] == "C", "candidate grade changed")
    need(not authority["headline_or_frontier_replacement"] and not authority["historical_or_protected_replacement"], "replacement authority appeared")
    need(authority["protected_decode_values_unchanged"] == PROTECTED, "protected values changed")
    need(not authority["other_depths_modes_tp_mtp_or_kv_inferred"], "inference authority appeared")
    need(not authority["automatic_descendant_expansion"] and not authority["descendant_execution_authorized"], "descendant authority appeared")
    need(not authority["localmaxxing_submission"] and authority["x0_remains_missing"], "external/zero-context authority changed")
    return {
        "status": "pass",
        "measured_cells_pending_publication": 1,
        "site_cells_published": 0,
        "exact_context": 4096,
        "tp": 1,
        "mtp": 1,
        "graph_mode": "off",
        "kv": "fp8_e4m3",
        "grade_candidate": "C",
        "accepted": 62,
        "drafted": 66,
        "target_parity": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--result", type=Path, default=RESULT)
    args = parser.parse_args()
    try:
        report = validate(args.root, args.result)
    except (KeyError, OSError, TypeError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
