#!/usr/bin/env python3
"""Validate the compact TP2 exact-depth result against retained raw evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-b2dd9ce73d-tp2-exact-depth-quality-r1-result.json"
PREREG = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-b2dd9ce73d-tp2-exact-depth-quality-r1-prereg.json"
ROOT = Path("/home/steve/qwen38-current-main-runs/tp2-exact-depth-b2dd9ce73d-20260826-r1/01-exact-depths")
DEPTHS = (2048, 4096, 8192, 16384, 24576, 32768)
PROTECTED = [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144]


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compact_cell(row: dict[str, Any]) -> dict[str, Any]:
    response = row["response"]
    window = row["metric_window"]
    usage = response["usage"]
    return {
        "active_context_tokens": row["depth"],
        "serving_decode_tok_s_99_interval": window["conventional_99_interval_tok_s"],
        "time_to_first_token_s": window["time_to_first_token_s"],
        "timestamped_events": window["timestamped_events"],
        "inter_token_intervals": window["inter_token_intervals"],
        "prompt_token_ids_sha256": row["prompt_token_ids_sha256"],
        "returned_prompt_token_ids_sha256": response["returned_prompt_token_ids_sha256"],
        "output_token_ids_sha256": response["output_token_ids_sha256"],
        "text_sha256": response["text_sha256"],
        "cached_tokens": usage["prompt_tokens_details"]["cached_tokens"],
        "completion_tokens": usage["completion_tokens"],
        "receipt_sha256": row["receipt_sha256"],
    }


def main() -> int:
    result = load(RESULT)
    prereg = load(PREREG)
    stage = load(ROOT / "stage-receipt.json")
    bench = load(ROOT / "bench.json")
    quality = load(ROOT / "quality.json")
    source = load(ROOT / "source-identity.json")

    assert result["status"] == "passed"
    assert result["campaign_id"] == stage["campaign_id"] == bench["campaign_id"] == prereg["campaign_id"]
    assert sha256(PREREG) == stage["frozen_dependency_sha256"][str(PREREG)] == "33d3db1798e859183f4f07f5887e0968dc0dd89d1ce455933a479ee76239341a"
    assert sha256(ROOT / "stage-receipt.json") == result["raw_artifacts"]["sha256"]["stage-receipt.json"] == "584560e72acebe3213dea14ac44dc26099fcce36db31ce26417c5d19398e8db9"
    for relative, expected in result["raw_artifacts"]["sha256"].items():
        assert sha256(ROOT / relative) == expected, relative
    assert stage["evidence_sha256"]["bench.json"] == result["raw_artifacts"]["sha256"]["bench.json"]
    assert stage["evidence_sha256"]["quality.json"] == result["raw_artifacts"]["sha256"]["quality.json"]
    assert stage["evidence_sha256"]["cache-manifest.post.sha256"] == result["raw_artifacts"]["sha256"]["cache-manifest.post.sha256"]
    assert sum(1 for path in ROOT.rglob("*") if path.is_file()) == result["raw_artifacts"]["run_file_count"] == 44
    with (ROOT / "cache-manifest.post.sha256").open(encoding="utf-8") as stream:
        assert sum(1 for _ in stream) == result["raw_artifacts"]["cache_manifest_entries"] == 2277

    run = prereg["run_identity"]
    exact = stage["gates"]["exact_run_identity"]
    identity = result["identity"]
    assert source["overlay"] == "none" and run["source_overlay"] == run["decision_overlay"] == "none"
    assert sha256(ROOT / "source-identity.json") == run["source_identity_sha256"]
    assert source["vllm"]["head"] == exact["vllm_head"] == run["vllm_head"] == identity["runtime"]["vllm_head"]
    assert source["kernel"]["head"] == exact["xpu_kernel_head"] == run["xpu_kernel_head"] == identity["runtime"]["xpu_kernel_head"]
    assert exact == {
        "gpus": [0, 1],
        "graph_mode": "FULL_AND_PIECEWISE",
        "image_id": run["image_id"],
        "kv_cache_dtype": "float16",
        "max_model_len": 32896,
        "model_revision": run["model_revision"],
        "mtp_depth": 0,
        "passed": True,
        "tp": 2,
        "vllm_head": run["vllm_head"],
        "worker_ranks": [0, 1],
        "xpu_kernel_head": run["xpu_kernel_head"],
    }
    assert identity["configuration"]["tp"] == 2 and identity["configuration"]["mtp"] == 0
    assert identity["configuration"]["target_kv"] == "float16"
    assert identity["configuration"]["graph_mode"] == "FULL_AND_PIECEWISE"
    assert identity["configuration"]["max_model_len"] == 32896
    assert identity["configuration"]["gpu_memory_utilization"] == 0.9
    assert stage["lab_git_head"] == identity["lab_git_head"] == identity["origin_main_at_launch"]
    assert stage["git_state"] == {
        "cached_origin_main_after": identity["lab_git_head"],
        "launch_head": identity["lab_git_head"],
        "live_origin_advanced_during_stage": False,
        "live_origin_main_after": identity["lab_git_head"],
        "live_origin_query_error": None,
        "live_origin_query_passed": True,
        "local_lab_unchanged": True,
        "post_run_branch": "main",
        "post_run_head": identity["lab_git_head"],
        "post_run_worktree_clean": True,
        "remote_movement_is_non_gating_after_launch": True,
    }

    assert stage["state"] == "passed" and stage["terminal"] is True and stage["receipt_complete"] is True
    assert result["completed_at_utc"] == stage["created_at_utc"]
    gates = stage["gates"]
    assert gates["runner_final_pass"] is True and gates["runner_return_code"] == 0
    assert gates["speed_gate_applied"] is False and gates["historical_speed_replacement_allowed"] is False
    assert gates["post_cleanup_passed"] is True and gates["local_lab_unchanged"] is True
    assert all(gates["graph_capture"]["checks"].values()) and gates["graph_capture"]["passed"] is True
    assert result["validation"]["graph_capture_checks"] == gates["graph_capture"]["checks"]
    assert result["validation"]["post_cleanup_passed"] is True
    validator = result["validation"]["exact_validator_outcome"]
    assert validator["script"].endswith("validate-20260826-qwen38-b2dd9ce73d-tp2-exact-depth-quality-r1.py")
    assert validator["status"] == "completed-valid-six-nonzero-exact-context-cells"
    assert len(validator["checks"]) == 16 and all(validator["checks"].values())

    depth_gate = gates["exact_depth_battery"]
    assert bench["status"] == "passed" and bench["one_server"] is True
    assert bench["expected_depths"] == bench["passed_depths"] == list(DEPTHS)
    assert bench["depth_zero_state"] == depth_gate["depth_zero_state"] == "missing"
    assert bench["configured_context_capacity"] == 32896
    assert bench["metric_events"] == 100 and bench["metric_intervals"] == 99
    assert bench["output_tokens_per_depth"] == 128
    assert depth_gate["passed"] is True and depth_gate["passed_depths"] == list(DEPTHS)
    rows = depth_gate["rows"]
    assert len(rows) == 6
    assert result["serving_curve"]["cells"] == [compact_cell(row) for row in rows]
    for depth, row in zip(DEPTHS, rows, strict=True):
        assert row["depth"] == depth and row["gate_passed"] is True
        assert row["prompt_token_ids_sha256"] == row["response"]["returned_prompt_token_ids_sha256"]
        receipt = load(ROOT / f"exact-depth/depth-{depth}.json")
        assert sha256(ROOT / f"exact-depth/depth-{depth}.json") == row["receipt_sha256"]
        assert receipt["status"] == "passed" and receipt["gate"]["passed"] is True
        assert all(receipt["gate"]["checks"].values())
        assert receipt["run_identity"]["active_context_tokens"] == depth
        assert receipt["run_identity"]["configured_context_capacity"] == 32896
        assert receipt["context_semantics"]["configured_context_capacity_is_not_active_context"] is True
        assert receipt["request"]["prompt_token_ids_sha256"] == row["prompt_token_ids_sha256"]
        assert receipt["response"]["output_token_ids_sha256"] == row["response"]["output_token_ids_sha256"]
        assert receipt["response"]["usage"]["completion_tokens"] == 128
        assert receipt["response"]["usage"]["prompt_tokens_details"]["cached_tokens"] == 0

    qgate = gates["quality"]
    assert quality["pass_all"] is True and qgate == {
        "baseline_comparison_count": 24,
        "baseline_match_all": True,
        "baseline_status": "passed",
        "cached_count": 16,
        "cached_zero_count": 16,
        "exact_count": 7,
        "pass_all": True,
        "passed": True,
        "repeat_count": 8,
    }
    assert len(quality["exact_cases"]) == 7 and all(case["pass"] for case in quality["exact_cases"])
    assert quality["repeat_case"]["pass"] is True and quality["repeat_case"]["repeats"] == 8
    assert quality["repeat_case"]["unique_hashes"] == [result["quality"]["repeat_stability"]["output_sha256"]]
    assert quality["long_context_case"]["pass"] is True
    assert quality["long_context_case"]["sha256"] == result["quality"]["long_context_needle"]["output_sha256"]
    assert len(quality["baseline_comparisons"]) == 24 and quality["baseline_match_all"] is True

    authority = result["authority"]
    assert authority["authorized_cells"] == 6
    assert authority["selectors"]["active_context_tokens"] == list(DEPTHS)
    assert authority["depth_zero_cells"] == authority["configured_capacity_cells"] == 0
    assert authority["identity_parent_cells"] == authority["quality_workload_cells"] == 0
    assert authority["other_tp_mtp_kv_graph_or_quantization_cells"] == authority["prefill_cells"] == 0
    assert authority["protected_or_headline_replacement"] is False
    assert authority["localmaxxing_submission"] is False
    assert stage["authority"] == {
        "depth_zero_cells": 0,
        "localmaxxing_submission": False,
        "nonzero_exact_context_cells": 6,
        "other_cells": 0,
        "protected_or_headline_replacement": False,
    }
    assert prereg["identity_parent"]["state"] == "preregistered-not-launched"
    assert prereg["frozen_interpretation"]["identity_parent_cells_authorized"] == 0
    assert result["protected_decode_values"] == prereg["frozen_interpretation"]["protected_decode_values"] == PROTECTED
    assert len(result["explicit_prohibitions"]) == 6
    for required in ("x0", "32896", "parent", "headline", "LocalMaxxing"):
        assert any(required in item for item in result["explicit_prohibitions"]), required

    print("PASS: compact TP2 evidence matches raw hashes, identity, gates, cleanup, and six-cell-only authority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
