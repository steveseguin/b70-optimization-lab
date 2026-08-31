#!/usr/bin/env python3
"""CPU-only contract tests for the BF16 allreduce threshold benchmark."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


TOOL = Path(__file__).with_name("benchmark-bf16-allreduce-threshold.py")
SPEC = importlib.util.spec_from_file_location("q38_bf16_allreduce_threshold", TOOL)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def payload(rank: int, threshold: int, latencies: list[float]) -> dict:
    token = MODULE.THRESHOLDS[threshold]
    return {
        "rank": rank,
        "world_size": 4,
        "rows": 1,
        "hidden": 2560,
        "bytes": 5120,
        "threshold_bytes": threshold,
        "expected_kernel_token": token,
        "output_sha256": "a" * 64,
        "oracle_sha256": "a" * 64,
        "oracle_match": True,
        "latency_us": latencies,
        "kernel_names": [f"oneccl_allreduce<{token}<bf16>>"],
        "loaded_libccl_path": "/frozen/libccl.so.1.0",
        "loaded_libccl_sha256": MODULE.EXPECTED_LIBCCL_SHA256,
    }


class Bf16AllreduceThresholdTest(unittest.TestCase):
    def test_rank_summary_uses_slowest_rank_each_iteration(self) -> None:
        rows = [
            payload(0, 4096, [1.0, 8.0, 3.0]),
            payload(1, 4096, [2.0, 7.0, 4.0]),
            payload(2, 4096, [3.0, 6.0, 5.0]),
            payload(3, 4096, [4.0, 5.0, 6.0]),
        ]
        result = MODULE.summarize_rank_payloads(rows)
        self.assertEqual(result["slowest_rank_latency_us"], [4.0, 8.0, 6.0])
        self.assertEqual(result["slowest_rank_latency"]["median_us"], 6.0)
        self.assertEqual(result["slowest_rank_latency"]["p99_us"], 8.0)

    def test_rank_hash_mismatch_fails_closed(self) -> None:
        rows = [payload(rank, 4096, [1.0]) for rank in range(4)]
        rows[2]["output_sha256"] = "b" * 64
        with self.assertRaisesRegex(
            MODULE.BenchmarkContractError, "identities diverge"
        ):
            MODULE.summarize_rank_payloads(rows)

    def test_candidate_requires_ll_kernel_receipt(self) -> None:
        rows = [payload(rank, 8192, [1.0]) for rank in range(4)]
        rows[3]["kernel_names"] = ["oneccl_allreduce<Rt64_128_PCIE<bf16>>"]
        with self.assertRaisesRegex(MODULE.BenchmarkContractError, "lacks Rt64_PCIE"):
            MODULE.summarize_rank_payloads(rows)

    def test_cross_process_summary_requires_both_arms_and_exact_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            for threshold in (4096, 8192):
                trial = MODULE.summarize_rank_payloads(
                    [
                        payload(rank, threshold, [10.0 + rank, 11.0 + rank])
                        for rank in range(4)
                    ]
                )
                path = root / f"{threshold}.json"
                path.write_text(json.dumps(trial), encoding="utf-8")
                paths.append(path)
            result = MODULE.summarize_trials(paths, root / "comparison.json")
            self.assertEqual(set(result["arms"]), {"4096", "8192"})
            self.assertEqual(result["arms"]["4096"]["fresh_process_trials"], 1)
            self.assertTrue((root / "comparison.json").is_file())

    def test_kernel_trace_parser_is_narrow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "trace.json"
            trace.write_text(
                json.dumps(
                    {
                        "traceEvents": [
                            {"ph": "X", "name": "noise"},
                            {"ph": "X", "name": "oneccl_allreduce<Rt64_PCIE<bf16>>"},
                            {"ph": "i", "name": "Rt64_128_PCIE metadata"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                MODULE.extract_kernel_names(trace),
                ["oneccl_allreduce<Rt64_PCIE<bf16>>"],
            )


if __name__ == "__main__":
    unittest.main()
