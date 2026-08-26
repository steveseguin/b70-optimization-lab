#!/usr/bin/env python3
"""Validate the qualified TP1/MTP2 PIECEWISE/F16 exact-4K candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

REPO = Path(__file__).resolve().parents[3]
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-mtp2-f16-piecewise-4k-sentinel-20260826-r1")
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp2-f16-piecewise-4k-sentinel-r1-result.json"
PROTECTED = [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def git_blob_digest(commit: str, path: str):
    blob = subprocess.run(
        ["git", "-C", str(REPO), "show", f"{commit}:{path}"],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    return hashlib.sha256(blob).hexdigest()


def need(value, message):
    if not value:
        raise RuntimeError(message)


def arg_value(args, name):
    return args[args.index(name) + 1]


def validate(root: Path, result_path: Path):
    result = load(result_path)
    need(result["status"] == "passed-quality-postrun-cache-audited-publication-candidate", "qualified status changed")
    need(result["original_terminal_class"] == "passed-quality-clean-sentinel", "terminal class disclosure changed")
    need(result["raw_root"] == str(root), "raw root changed")
    for binding in result["tracked_inputs"].values():
        if "git_commit" in binding:
            need(git_blob_digest(binding["git_commit"], binding["path"]) == binding["sha256"], f"launch blob changed: {binding['path']}")
        else:
            path = REPO / binding["path"]
            need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")

    identity = result["identity"]
    for name, expected in identity["raw_sha256"].items():
        need(digest(root / name) == expected, f"raw identity changed: {name}")
    need((root / "image-id.txt").read_text().strip() == identity["image"].split("@", 1)[1], "image changed")
    need((root / "vllm-source-commit.txt").read_text().strip() == identity["vllm_source"], "vLLM source changed")
    need((root / "stack-versions.txt").read_text().splitlines() == [identity["vllm_version"], identity["xpu_kernels_version"]], "stack changed")

    container = load(root / "container-inspect.json")[0]
    args, env = container["Config"]["Cmd"], container["Config"]["Env"]
    need(arg_value(args, "--tensor-parallel-size") == "1", "TP1 changed")
    need(arg_value(args, "--pipeline-parallel-size") == arg_value(args, "--data-parallel-size") == "1", "parallel topology changed")
    need(arg_value(args, "--max-model-len") == "32896", "context capacity changed")
    need(arg_value(args, "--max-num-batched-tokens") == "1024", "batch cap changed")
    need(arg_value(args, "--gpu-memory-utilization") == "0.90", "memory utilization changed")
    need("--enforce-eager" not in args and "--kv-cache-dtype" not in args, "PIECEWISE/F16 identity changed")
    need(json.loads(arg_value(args, "--compilation-config")) == {"cudagraph_mode": "PIECEWISE", "cudagraph_capture_sizes": [1], "max_cudagraph_capture_size": 1}, "PIECEWISE config changed")
    need(json.loads(arg_value(args, "--speculative-config")) == {"method": "qwen3_next_mtp", "num_speculative_tokens": 2}, "MTP2 changed")
    need("ZE_AFFINITY_MASK=0" in env and "ONEAPI_DEVICE_SELECTOR=level_zero:0" in env, "TP1 selector changed")
    need("VLLM_XPU_ENABLE_XPU_GRAPH=1" in env and "PYTHONHASHSEED=0" in env, "graph/hash environment changed")
    cache_root = result["cache_isolation"]["cache_root"]
    need(any(m["Source"] == cache_root and m["Destination"] == "/run-cache" and m["RW"] is True for m in container["Mounts"]), "cache mount changed")

    startup = (root / "server-startup.log").read_text(errors="replace")
    for marker in ("SpeculativeConfig(method='mtp'", "num_spec_tokens=2", "tensor_parallel_size=1", "enforce_eager=False", "kv_cache_dtype=auto", "world_size=1 rank=0 local_rank=0", "TP rank 0", "Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)", "Graph capturing finished"):
        need(marker in startup, f"missing startup marker: {marker}")
    need("cudagraph_mode': <CUDAGraphMode.PIECEWISE: 1>" in startup, "PIECEWISE startup changed")
    need("Capturing CUDA graphs (decode, FULL)" not in startup, "FULL capture appeared")

    terminal, arm = load(root / "terminal-receipt.json"), load(root / "arm-result.json")
    cleanup = result["cleanup"]
    need(digest(root / "terminal-receipt.json") == cleanup["terminal_receipt_sha256"], "terminal changed")
    need(digest(root / "arm-result.json") == cleanup["arm_result_sha256"], "arm changed")
    need(terminal["terminal"] and terminal["runner_return_code"] == 0 and terminal["state"] == "passed-quality-clean-sentinel", "original terminal failed")
    need(terminal["launch_git_head"] == cleanup["launch_git_head"] and terminal["protected_profiles_untouched"], "terminal identity changed")
    need(not terminal["automatic_publication"] and not terminal["automatic_descendant_expansion"], "terminal authority widened")
    need(arm["exact_4k_return_code"] == arm["quality_return_code"] == arm["runner_return_code"] == 0, "raw rc changed")
    need(all(arm[k] for k in ("acceptance_passed", "cleanup_passed", "dual_parent_verification_passed", "quality_contract_passed", "startup_identity_passed")), "raw gate failed")
    need(not arm["publication_authorized"] and not arm["descendant_expansion_authorized"] and not arm["descendant_execution_authorized"] and not arm["historical_replacement_allowed"], "raw authority widened")

    raw_path = root / "exact-depth/depth-4096.json"
    raw = load(raw_path)
    need(raw == load(root / "exact-depth/depth-4096.stdout.json"), "stdout mirror changed")
    need((root / "exact-depth/depth-4096.rc").read_text().strip() == "0", "exact rc changed")
    need(raw["status"] == "passed" and raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), "exact gate failed")
    metric, response, usage, point = raw["metric_window"], raw["response"], raw["response"]["usage"], result["point"]
    need(digest(raw_path) == point["raw_sha256"], "raw point changed")
    need(metric["conventional_99_interval_tok_s"] == point["decode_tok_s"], "decode changed")
    need(metric["historical_100_event_tok_s"] == point["historical_100_event_decode_tok_s"], "historical decode changed")
    need(metric["time_to_first_token_s"] == point["ttft_s"] and metric["time_to_first_token_s"] * 1000 == point["ttft_ms"], "TTFT changed")
    need(usage["prompt_tokens"] == 4096 and usage["completion_tokens"] == 128 and usage["prompt_tokens_details"]["cached_tokens"] == 0, "usage changed")
    need(len(response["token_ids"]) == 128 and response["output_token_ids_sha256"] == point["output_token_ids_sha256"], "token output changed")

    gates, mechanism, oracle = load(root / "verification-gates.json"), result["mechanism"], result["dual_parent_oracle"]
    need(digest(root / "verification-gates.json") == mechanism["raw_sha256"], "verification gates changed")
    acceptance = gates["acceptance"]
    need(acceptance["passed"] and acceptance["drafted_tokens"] == mechanism["drafted_tokens"] and acceptance["accepted_tokens"] == mechanism["accepted_tokens"] and acceptance["acceptance_rate"] == mechanism["acceptance_rate"], "acceptance changed")
    dual = gates["dual_parent_verification"]
    need(dual["passed"] and dual["parent_ids_equal"] and dual["candidate_vs_eager_first_divergence"] is None and dual["candidate_vs_graph_first_divergence"] is None, "dual-parent parity failed")
    need(dual["candidate_ids_sha256"] == dual["eager_parent_ids_sha256"] == dual["graph_parent_ids_sha256"] == oracle["candidate_token_ids_sha256"], "parent hash changed")
    eager_path, graph_path = Path(oracle["eager_target_path"]), Path(oracle["piecewise_parent_path"])
    need(digest(eager_path) == oracle["eager_target_raw_sha256"] and digest(graph_path) == oracle["piecewise_parent_raw_sha256"], "parent receipt changed")
    need(response["token_ids"] == load(eager_path)["response"]["token_ids"] == load(graph_path)["response"]["token_ids"], "parent tokens changed")

    quality, expected_quality = load(root / "quality.json"), result["quality"]
    need(digest(root / "quality.json") == expected_quality["raw_sha256"], "quality changed")
    need(quality["pass_all"] and quality["baseline_match_all"], "quality failed")
    need(len(quality["exact_cases"]) == 7 and all(case["pass"] for case in quality["exact_cases"]), "exact quality failed")
    repeat = quality["repeat_case"]
    need(repeat["pass"] and repeat["repeats"] == 8 and len(repeat["unique_hashes"]) == 1, "repeat quality failed")
    need(quality["long_context_case"]["pass"] and len(quality["baseline_comparisons"]) == 24 and all(quality["baseline_comparisons"].values()), "needle/baseline failed")
    usages = [case["usage"] for case in quality["exact_cases"]] + [run["usage"] for run in repeat["runs"]] + [quality["long_context_case"]["usage"]]
    need(len(usages) == 16 and all(item["prompt_tokens_details"]["cached_tokens"] == 0 for item in usages), "quality cache reuse appeared")

    verification = load(root / "model-verification.json")
    need(digest(root / "model-verification.json") == result["model_verification"]["raw_sha256"], "model verification changed")
    need(verification["status"] == "verified" and len(verification["files"]) == 19 and all(item["ok"] and item["paths_coherent"] for item in verification["files"]), "model verification failed")

    cache = result["cache_isolation"]
    need(cache["classification"] == "passed-by-transparent-post-run-report-only-audit" and cache["runner_defect_disclosed"], "qualified cache classification changed")
    need(not cache["original_terminal_enforced_cache_gate"] and not cache["original_terminal_rewritten"] and not cache["measured_response_rewritten"] and cache["posthoc"], "result hides the original cache-gate defect")
    need(cache["postrun_audit_passed"], "result does not retain the post-run audit pass")
    need(cleanup["classification"] == "original-runtime-cleanup-passed-cache-gate-omitted" and cleanup["cache_isolation_was_not_an_original_terminal_gate"], "cleanup disclosure changed")
    audit_path, manifest_path = Path(cache["audit_path"]), Path(cache["content_manifest_path"])
    need(digest(audit_path) == cache["audit_sha256"], "post-run audit changed")
    need(digest(manifest_path) == cache["content_manifest_sha256"], "cache content manifest changed")
    audit = load(audit_path)
    need(audit["passed"] and audit["posthoc"] and audit["audit_mode"] == "post-run-report-only", "post-run audit classification changed")
    need(not audit["original_terminal_enforced_cache_gate"] and not audit["original_terminal_rewritten"] and not audit["measured_response_rewritten"], "cache defect disclosure lost")
    need(audit["terminal_identity_passed"] and audit["terminal_receipt_sha256"] == cleanup["terminal_receipt_sha256"], "audit terminal binding changed")
    need(audit["cache_root"] == cache_root and audit["content_manifest_sha256"] == cache["content_manifest_sha256"], "audit binding changed")
    need(audit["expected_rank_namespaces"] == audit["observed_rank_namespaces"] == ["rank_0_0"], "rank namespace changed")
    need(audit["rank_file_counts"] == {"rank_0_0": 6} and audit["shared_file_count"] == 1364 and audit["total_file_count"] == 1370 and audit["total_bytes"] == 173190178, "cache census changed")
    manifest_lines = manifest_path.read_text(encoding="utf-8").splitlines()
    need(len(manifest_lines) == 1370, "manifest count changed")
    parsed = [line.split("  ", 2) for line in manifest_lines]
    need(all(len(parts) == 3 and re.fullmatch(r"[0-9a-f]{64}", parts[0]) for parts in parsed), "manifest format changed")
    need(sum(int(parts[1]) for parts in parsed) == 173190178, "manifest byte total changed")
    ranks = [part for _, _, path in parsed for part in PurePosixPath(path).parts if re.fullmatch(r"rank_[0-9]+_[0-9]+", part)]
    need(ranks == ["rank_0_0"] * 6, "manifest rank census changed")

    caveats = result["historical_corruption_caveats"]
    need(caveats["retained"] and caveats["same_image_graph_family_8k"]["first_divergence"]["one_based"] == 99, "graph 8K caveat lost")
    expected_divergences = {"2048": (90, 59178, 16539), "8192": (99, 411, 579), "16384": (32, 13, 11)}
    for depth, expected in expected_divergences.items():
        divergence = caveats["same_image_mtp2_eager"][depth]["first_divergence"]
        need((divergence["one_based"], divergence["candidate"], divergence["target"]) == expected, f"{depth} caveat changed")

    adjudication, authority = result["human_adjudication"], result["authority"]
    need(adjudication["kind"] == "separate-human-one-cell-publication-candidate-with-postrun-cache-defect-disclosure", "adjudication changed")
    need(adjudication["decision"] == "pending-separate-family-and-site-publication" and adjudication["selected_depths"] == [4096], "one-cell adjudication changed")
    need(adjudication["excluded_depths"] == [0, 2048, 8192, 16384, 24576, 32768] and adjudication["original_terminal_cache_gate_omission_accepted_only_with_disclosure"], "exclusions/defect disclosure changed")
    need(authority["measured_cells_pending_publication"] == 1 and authority["site_cells_published_by_this_packet"] == 0, "one-cell pending authority changed")
    need(not authority["site_or_family_publication_authorized_by_original_runner"] and authority["quality_grade_candidate"] == "C", "publication/grade authority changed")
    need(not authority["historical_or_protected_replacement"] and not authority["headline_or_frontier_replacement"], "replacement appeared")
    need(authority["protected_decode_values_unchanged"] == PROTECTED and authority["corruption_caveats_preserved"], "protected state changed")
    need(not authority["other_depths_modes_tp_mtp_or_kv_inferred"] and not authority["automatic_descendant_expansion"] and not authority["descendant_execution_authorized"], "scope widened")
    return {"status": "pass-qualified", "terminal_class": terminal["state"], "runner_cache_gate_enforced": False, "postrun_cache_audit": "pass", "cells_pending": 1, "cells_published": 0, "tp": 1, "mtp": 2, "context": 4096, "decode_tok_s": point["decode_tok_s"], "ttft_ms": point["ttft_ms"], "accepted": 80, "drafted": 94, "token_hash": point["output_token_ids_sha256"], "grade_candidate": "C"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--result", type=Path, default=RESULT)
    args = parser.parse_args()
    try:
        report = validate(args.root, args.result)
    except (KeyError, OSError, TypeError, ValueError, RuntimeError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
