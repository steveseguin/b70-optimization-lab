#!/usr/bin/env python3
"""Read-only validator for the pending TP2/MTP2 PIECEWISE/F16 exact-4K cell."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOT = Path(
    "/mnt/fast-ai/bench-results/"
    "qwen38-official-f01e-autoround-tp2-mtp2-f16-piecewise-4k-sentinel-20260826-r1"
)
RESULT = REPO / (
    "experiments/qwen38-27b-b70/data/"
    "2026-08-26-qwen38-official-f01e-autoround-tp2-mtp2-f16-piecewise-4k-sentinel-r1-result.json"
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

    # Bind every raw file, and reject an omitted or later-added artifact.
    actual_files = {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}
    expected_files = set(result["raw_sha256"])
    need(actual_files == expected_files, "raw file inventory changed")
    for name, expected in result["raw_sha256"].items():
        need(digest(root / name) == expected, f"raw artifact changed: {name}")
    for binding in result["tracked_inputs"].values():
        path = REPO / binding["path"]
        need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")

    identity = result["identity"]
    need((root / "image-id.txt").read_text().strip() == identity["image"].split("@", 1)[1], "image changed")
    need((root / "vllm-source-commit.txt").read_text().strip() == identity["vllm_source"], "vLLM source changed")
    need(
        (root / "stack-versions.txt").read_text().splitlines()
        == [identity["vllm_version"], identity["xpu_kernels_version"]],
        "stack changed",
    )

    config = result["config"]
    need(config["tp"] == config["cards"] == 2, "result TP/card scope changed")
    need(config["mtp"] == config["num_speculative_tokens"] == 2, "result MTP2 scope changed")
    need(config["graph_mode"] == "PIECEWISE" and config["graph_capture_sizes"] == [1], "result graph scope changed")
    need(config["kv"] == "f16" and not config["enforce_eager"], "result F16/graph scope changed")
    need(config["device_affinity"] == "0,1" and config["oneapi_device_selector"] is None, "result device scope changed")
    need(config["configured_max_context_tokens"] == 32896 and config["parallel_slots"] == 1, "result capacity changed")
    need(not config["prefix_caching"] and config["pythonhashseed"] == 0, "result cache/hash policy changed")

    container = load(root / "container-inspect.json")[0]
    args, env = container["Config"]["Cmd"], container["Config"]["Env"]
    need(arg_value(args, "--tensor-parallel-size") == "2", "TP2 changed")
    need(arg_value(args, "--pipeline-parallel-size") == "1", "PP1 changed")
    need(arg_value(args, "--data-parallel-size") == "1", "DP1 changed")
    need(arg_value(args, "--max-model-len") == "32896", "context capacity changed")
    need(arg_value(args, "--max-num-seqs") == "1", "parallel slots changed")
    need(arg_value(args, "--max-num-batched-tokens") == "1024", "batch cap changed")
    need(arg_value(args, "--gpu-memory-utilization") == "0.60", "memory utilization changed")
    need(arg_value(args, "--dtype") == "float16", "dtype changed")
    need("--enforce-eager" not in args and "--kv-cache-dtype" not in args, "PIECEWISE/F16 identity changed")
    need(
        json.loads(arg_value(args, "--compilation-config"))
        == {
            "cudagraph_mode": "PIECEWISE",
            "cudagraph_capture_sizes": [1],
            "max_cudagraph_capture_size": 1,
        },
        "PIECEWISE config changed",
    )
    need(
        json.loads(arg_value(args, "--speculative-config"))
        == {"method": "qwen3_next_mtp", "num_speculative_tokens": 2},
        "MTP2 changed",
    )
    need("--no-enable-prefix-caching" in args, "prefix cache policy changed")
    need("ZE_AFFINITY_MASK=0,1" in env, "TP2 device mask changed")
    need(not any(item.startswith("ONEAPI_DEVICE_SELECTOR=") for item in env), "selector unexpectedly appeared")
    need("VLLM_XPU_ENABLE_XPU_GRAPH=1" in env and "PYTHONHASHSEED=0" in env, "graph/hash environment changed")
    cache_root = result["graph_topology_and_cache"]["dedicated_cache_root"]
    need(
        any(
            mount["Source"] == cache_root
            and mount["Destination"] == "/run-cache"
            and mount["RW"] is True
            for mount in container["Mounts"]
        ),
        "dedicated cache mount changed",
    )

    startup = (root / "server-startup.log").read_text(errors="replace")
    for marker in (
        "SpeculativeConfig(method='mtp'",
        "num_spec_tokens=2",
        "tensor_parallel_size=2",
        "enforce_eager=False",
        "kv_cache_dtype=auto",
        "world_size=2, local_world_size=2",
        "world_size=2 rank=0 local_rank=0",
        "world_size=2 rank=1 local_rank=1",
        "TP rank 0",
        "Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)",
        "Graph capturing finished",
    ):
        need(marker in startup, f"missing startup marker: {marker}")
    need("cudagraph_mode': <CUDAGraphMode.PIECEWISE: 1>" in startup, "PIECEWISE startup identity changed")
    need("cudagraph_capture_sizes': [1]" in startup, "capture size changed")
    need("Capturing CUDA graphs (decode, FULL)" not in startup, "FULL capture appeared")

    terminal, arm = load(root / "terminal-receipt.json"), load(root / "arm-result.json")
    cleanup = result["cleanup"]
    need(terminal["terminal"] and terminal["runner_return_code"] == 0, "terminal failed")
    need(terminal["state"] == "passed-quality-clean-sentinel", "terminal state changed")
    need(terminal["launch_git_head"] == cleanup["launch_git_head"], "launch head changed")
    need(terminal["protected_profiles_untouched"], "protected profiles changed")
    need(not terminal["automatic_publication"] and not terminal["automatic_descendant_expansion"], "terminal authority widened")
    need(terminal["arm"] == arm, "terminal arm mirror changed")
    need(arm["exact_4k_return_code"] == 0 and arm["quality_return_code"] == 0, "raw gate rc changed")
    need(
        all(
            arm[key]
            for key in (
                "acceptance_passed",
                "cleanup_passed",
                "dual_parent_verification_passed",
                "quality_contract_passed",
                "rank_cache_isolation_passed",
                "startup_identity_passed",
                "tp2_worker_topology_passed",
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

    raw = load(root / "exact-depth/depth-4096.json")
    need(raw == load(root / "exact-depth/depth-4096.stdout.json"), "stdout mirror changed")
    need((root / "exact-depth/depth-4096.rc").read_text().strip() == "0", "exact 4K rc changed")
    need(raw["status"] == "passed" and raw["gate"]["passed"], "exact 4K gate failed")
    need(all(raw["gate"]["checks"].values()), "an exact 4K check failed")
    metric, response, usage = raw["metric_window"], raw["response"], raw["response"]["usage"]
    point = result["point"]
    need(metric["conventional_99_interval_tok_s"] == point["decode_tok_s"], "decode changed")
    need(metric["historical_100_event_tok_s"] == point["historical_100_event_diagnostic_tok_s"], "historical diagnostic changed")
    need(point["publication_metric"] == "conventional_99_interval_tok_s", "publication metric changed")
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
    mechanism, oracle = result["mechanism"], result["dual_parent_oracle"]
    acceptance = gates["acceptance"]
    need(acceptance["passed"] and mechanism["passed"], "acceptance gate failed")
    need(acceptance["drafted_tokens"] == mechanism["drafted_tokens"] == 94, "draft count changed")
    need(acceptance["accepted_tokens"] == mechanism["accepted_tokens"] == 80, "accepted count changed")
    need(acceptance["acceptance_rate"] == mechanism["acceptance_rate"], "acceptance rate changed")
    need(0 < mechanism["accepted_tokens"] <= mechanism["drafted_tokens"], "acceptance counters are not conserved")
    dual = gates["dual_parent_verification"]
    need(dual["passed"] and dual["parent_ids_equal"] and oracle["passed"], "dual-parent parity failed")
    need(dual["candidate_vs_graph_first_divergence"] is None and dual["candidate_vs_eager_first_divergence"] is None, "parent divergence appeared")
    need(
        dual["candidate_ids_sha256"]
        == dual["eager_parent_ids_sha256"]
        == dual["graph_parent_ids_sha256"]
        == oracle["candidate_token_ids_sha256"],
        "parent hash changed",
    )
    graph_path, eager_path = Path(oracle["graph_target_path"]), Path(oracle["eager_parent_path"])
    graph, eager = load(graph_path), load(eager_path)
    need(digest(graph_path) == oracle["graph_target_raw_sha256"], "graph target changed")
    need(digest(eager_path) == oracle["eager_parent_raw_sha256"], "eager parent changed")
    need(response["token_ids"] == graph["response"]["token_ids"] == eager["response"]["token_ids"], "parent tokens changed")

    quality = load(root / "quality.json")
    expected_quality = result["quality"]
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
    need(len(usages) == expected_quality["cache_zero_requests"] == 16, "quality request count changed")
    need(all(item["prompt_tokens_details"]["cached_tokens"] == 0 for item in usages), "quality cache reuse appeared")

    cache = load(root / "rank-cache-isolation.json")
    cache_result = result["graph_topology_and_cache"]
    need(cache["passed"] and cache["cache_root"] == cache_root, "rank-cache isolation failed")
    need(cache["expected_rank_namespaces"] == cache["observed_rank_namespaces"] == ["rank_0_0", "rank_1_0"], "rank namespaces changed")
    need(cache["rank_file_counts"] == {"rank_0_0": 6, "rank_1_0": 6}, "rank file counts changed")
    need(cache["shared_file_count"] == cache_result["shared_file_count"] == 2850, "shared cache count changed")
    need(cache["total_files"] == cache_result["total_files"] == 2862, "total cache count changed")

    verification = load(root / "model-verification.json")
    need(
        verification["status"] == "verified"
        and len(verification["files"]) == result["model_verification"]["files_verified"] == 19
        and all(item["ok"] and item["paths_coherent"] for item in verification["files"]),
        "model verification failed",
    )

    candidate, authority = result["publication_candidate"], result["authority"]
    need(candidate["decision"] == "pending-separate-human-family-and-site-publication", "publication state changed")
    need(candidate["coverage_contract_id"] == "qwen38-tp2-vllm-xpu-autoround-f01e-mtp2-piecewise-depth", "contract identity changed")
    need(candidate["selected_depths"] == [4096], "selected depth scope widened")
    need(candidate["missing_depths"] == [0, 2048, 8192, 16384, 24576, 32768], "missing depths changed")
    need(candidate["candidate_grade"] == "C" and not candidate["publication_is_automatic"], "candidate grade/authority changed")
    need(authority["measured_cells_pending_publication"] == 1, "one-cell pending authority missing")
    need(authority["site_cells_published_by_this_packet"] == 0, "packet claims a published site cell")
    need(authority["separate_human_publication_required"], "human publication gate disappeared")
    need(not authority["site_or_family_publication_authorized_by_raw_runner"], "raw runner publication appeared")
    need(not authority["headline_or_frontier_replacement"] and not authority["historical_or_protected_replacement"], "replacement authority appeared")
    need(authority["protected_decode_values_unchanged"] == PROTECTED, "protected values changed")
    need(not authority["other_depths_modes_tp_mtp_or_kv_inferred"], "inference authority appeared")
    need(not authority["automatic_descendant_expansion"] and not authority["descendant_execution_authorized"], "descendant authority appeared")
    need(not authority["localmaxxing_submission"] and authority["x0_remains_missing"], "external/zero-context authority changed")
    return {
        "status": "pass",
        "terminal_class": terminal["state"],
        "raw_files_bound": len(expected_files),
        "measured_cells_pending_publication": 1,
        "site_cells_published": 0,
        "exact_context": 4096,
        "tp": 2,
        "mtp": 2,
        "graph_mode": "PIECEWISE",
        "kv": "f16",
        "grade_candidate": "C",
        "decode_tok_s": point["decode_tok_s"],
        "ttft_ms": point["ttft_ms"],
        "accepted": 80,
        "drafted": 94,
        "token_hash": point["output_token_ids_sha256"],
        "dual_parent_parity": True,
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
