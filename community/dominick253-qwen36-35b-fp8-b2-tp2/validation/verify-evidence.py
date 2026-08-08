#!/usr/bin/env python3
"""Recompute all submitted benchmark and long-output claims from raw artifacts."""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRICS = (
    "pp_throughput",
    "tg_throughput",
    "tg_req_throughput",
    "ttfr",
)


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def sha256(name: str) -> str:
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def main() -> int:
    summary = load("benchmark-triple-summary.json")
    raw_runs = []
    for sweep in (1, 2, 3):
        name = f"benchmark-clean-r{sweep}.json"
        expected_hash = summary["raw_sha256"][name]
        assert sha256(name) == expected_hash, f"hash mismatch: {name}"
        raw = load(name)
        raw_runs.append(raw)
        assert raw["version"] == "0.4.1.dev1+ge9be34457"
        for benchmark in raw["benchmarks"]:
            for metric in METRICS:
                values = benchmark[metric]["values"]
                calculated = statistics.fmean(values)
                recorded = benchmark[metric]["mean"]
                assert math.isclose(calculated, recorded, rel_tol=1e-12, abs_tol=1e-12), (
                    name,
                    benchmark["concurrency"],
                    metric,
                )

        monitor = load(f"benchmark-clean-r{sweep}-monitor.json")
        assert monitor["benchmark_exit_code"] == 0
        assert monitor["expected_requests"] == 165
        assert monitor["actual_requests"] == 165
        assert monitor["request_count_clean"] is True
        assert monitor["new_faults"] == 0
        assert monitor["faults_before"] == monitor["faults_after"]

    for aggregate in summary["results"]:
        concurrency = aggregate["concurrency"]
        raw_rows = [
            next(row for row in raw["benchmarks"] if row["concurrency"] == concurrency)
            for raw in raw_runs
        ]
        mappings = {
            "prompt_tokens_per_second": "pp_throughput",
            "aggregate_generation_tokens_per_second": "tg_throughput",
            "per_request_generation_tokens_per_second": "tg_req_throughput",
            "time_to_first_response_ms": "ttfr",
        }
        for summary_key, raw_key in mappings.items():
            means = [row[raw_key]["mean"] for row in raw_rows]
            submitted = aggregate[summary_key]
            assert len(submitted["sweep_means"]) == 3
            for actual, recorded in zip(means, submitted["sweep_means"], strict=True):
                assert math.isclose(actual, recorded, rel_tol=0, abs_tol=5e-7)
            calculated = statistics.fmean(means)
            assert math.isclose(
                calculated, submitted["three_sweep_mean"], rel_tol=0, abs_tol=5e-7
            )
            if "range" in submitted:
                assert math.isclose(min(means), submitted["range"][0], rel_tol=0, abs_tol=5e-7)
                assert math.isclose(max(means), submitted["range"][1], rel_tol=0, abs_tol=5e-7)

    quality = load("quality-manifest.json")
    total_tokens = 0
    for artifact in quality["artifacts"]:
        name = artifact["artifact"]
        assert sha256(name) == artifact["artifact_sha256"]
        raw = load(name)
        assert raw["passed"] is True
        assert raw["failures"] == 0
        assert len(raw["results"]) == len(artifact["responses"])
        for result, submitted in zip(raw["results"], artifact["responses"], strict=True):
            text = (result.get("reasoning_content") or "") + "\n" + (result.get("text") or "")
            total_tokens += result["completion_tokens"]
            assert result["errors"] == []
            assert result["completion_tokens"] == submitted["completion_tokens"]
            assert result["finish_reason"] == submitted["finish_reason"]
            assert text.count("!!!!") == submitted["bang4_occurrences"] == 0
            assert hashlib.sha256(text.encode()).hexdigest() == submitted["text_sha256"]
            assert len(text) == submitted["characters"]
            assert re.search(r"([!?.;,])\1{9,}", text) is None

    assert total_tokens == quality["total_completion_tokens"] == 11024

    launcher = (ROOT.parent / "vllm-qwen36-35b-fp8-b2-tp2.sh").read_text()
    required = (
        "sha256:3f0a8c60fbaf376ec09538f093cba91f171238b99c117445c0bcc6096272ec3e",
        "95a723d08a9490559dae23d0cff1d9466213d989",
        "CCL_TOPO_P2P_ACCESS=0",
        "CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296",
        "CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296",
        "CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296",
        "CCL_SYCL_ALLTOALL_TMP_BUF=1",
        "--tensor-parallel-size 2",
        "--kv-cache-dtype fp8_e4m3",
        "--max-model-len ${MAX_LEN}",
        "--max-num-seqs ${MAX_SEQS}",
        '\\"method\\":\\"mtp\\",\\"num_speculative_tokens\\":2',
    )
    for value in required:
        assert value in launcher, f"launcher setting missing: {value}"

    print("PASS: 3 benchmark sweeps, 495 isolated requests, raw means, hashes, faults, and 11,024 long-output tokens verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
