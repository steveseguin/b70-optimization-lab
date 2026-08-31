#!/usr/bin/env python3
"""Synthetic contract tests for the offline target-decode trace summarizer."""

from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


TOOL = Path(__file__).with_name("summarize-tp4-target-decode-kineto.py")
SPEC = importlib.util.spec_from_file_location("q38_target_decode_summary", TOOL)
assert SPEC is not None and SPEC.loader is not None
SUMMARY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUMMARY)


def _write_trace(
    path: Path,
    rank: int,
    *,
    foreign_context: bool = False,
    base_time_ns: int | str | None = 1_782_967_788_000_000_000,
) -> None:
    anchor_base_ns = (
        base_time_ns if isinstance(base_time_ns, int) else 1_782_967_788_000_000_000
    )
    events = []
    for cycle in range(4):
        start = 1_000_000.0 + cycle * 10_000.0
        context_name = SUMMARY.DEFAULT_CONTEXT
        if foreign_context and cycle == 2:
            context_name = "execute_context_1(64)_generation_0(0)"
        events.append(
            {
                "ph": "X",
                "cat": "user_annotation",
                "name": context_name,
                "ts": start,
                "dur": 5_000.0,
                "args": {},
            }
        )

        dense_id = cycle * 10 + 1
        gdn_id = cycle * 10 + 2
        events.extend(
            [
                {
                    "ph": "X",
                    "cat": "cpu_op",
                    "name": "aten::linear",
                    "ts": start + 100.0,
                    "dur": 20.0,
                    "args": {
                        "External id": dense_id,
                        "Input Dims": [[1, 6144], [6144, 6144]],
                        "Input type": ["BFloat16", "Float8_e4m3fn"],
                    },
                },
                {
                    "ph": "X",
                    "cat": "cpu_op",
                    "name": "qwen::gated_delta_net_decode",
                    "ts": start + 120.0,
                    "dur": 20.0,
                    "args": {
                        "External id": gdn_id,
                        "Input Dims": [[1, 6144]],
                    },
                },
                {
                    "ph": "X",
                    "cat": "kernel",
                    "name": "gemm_kernel",
                    "ts": start + 500.0,
                    "dur": 100.0 + rank,
                    "args": {
                        "External id": dense_id,
                        "submitted": str(
                            anchor_base_ns + int((start + 200.0) * 1000.0)
                        ),
                    },
                },
                {
                    "ph": "X",
                    "cat": "kernel",
                    "name": "opaque_recurrent_kernel",
                    "ts": start + 700.0,
                    "dur": 200.0,
                    "args": {
                        "External id": gdn_id,
                        "appended": str(anchor_base_ns + int((start + 300.0) * 1000.0)),
                    },
                },
                {
                    "ph": "X",
                    "cat": "kernel",
                    "name": "oneccl_reduce_scatter",
                    "ts": start + 900.0,
                    "dur": 50.0,
                    "args": {
                        "External id": cycle * 10 + 3,
                        "sycl_enqk_begin": str(
                            anchor_base_ns + int((start + 400.0) * 1000.0)
                        ),
                    },
                },
                {
                    "ph": "X",
                    "cat": "kernel",
                    "name": "profiler_housekeeping_outside_decode",
                    "ts": start + 7_000.0,
                    "dur": 10.0,
                    "args": {
                        "External id": cycle * 10 + 4,
                        "submitted": str(
                            anchor_base_ns + int((start + 7_000.0) * 1000.0)
                        ),
                    },
                },
            ]
        )

    with gzip.open(path, "wt", encoding="utf-8") as handle:
        document = {"traceEvents": events}
        if base_time_ns is not None:
            document["baseTimeNanoseconds"] = base_time_ns
        json.dump(document, handle)


class TargetDecodeSummaryTest(unittest.TestCase):
    def test_four_rank_gzip_summary_separates_collectives(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            trace_dir = Path(directory)
            for rank in range(4):
                _write_trace(
                    trace_dir
                    / f"dp0_pp0_tp{rank}_dcp0_ep{rank}_rank{rank}.1.pt.trace.json.gz",
                    rank,
                )

            result = SUMMARY.summarize_directory(trace_dir)
            json.dumps(result)

        self.assertEqual(result["expected_ranks"], [0, 1, 2, 3])
        self.assertEqual(len(result["ranks"]), 4)
        rank0 = result["ranks"][0]
        self.assertEqual(rank0["retained_contexts"], 3)
        self.assertAlmostEqual(
            rank0["bucket_device_ms_per_cycle"]["dense_projection"]["mean"],
            0.1,
        )
        self.assertAlmostEqual(rank0["bucket_device_ms_per_cycle"]["gdn"]["mean"], 0.2)
        self.assertAlmostEqual(
            rank0["summed_noncollective_device_ms_per_cycle"]["mean"], 0.3
        )
        self.assertAlmostEqual(
            rank0["summed_collective_device_ms_per_cycle_distorted"]["mean"],
            0.05,
        )
        self.assertEqual(
            rank0["device_event_accounting"]["inside_dropped_annotation"], 3
        )
        self.assertEqual(
            rank0["device_event_accounting"]["outside_target_annotations"], 4
        )
        self.assertTrue(
            any(
                row["operator"]["name"] == "qwen::gated_delta_net_decode"
                for row in rank0["top_device_event_operator_shapes"]
            )
        )
        self.assertEqual(
            result["slowest_rank_context_by_cycle"][0]["slowest_ranks"],
            [0, 1, 2, 3],
        )

    def test_custom_context_cannot_claim_target_only_decode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                SUMMARY.TraceContractError,
                "frozen to the pure target-only decode context",
            ):
                SUMMARY.summarize_directory(
                    Path(directory),
                    context_name="execute_context_1(64)_generation_0(0)",
                )

    def test_foreign_execute_context_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            trace_dir = Path(directory)
            for rank in range(4):
                _write_trace(
                    trace_dir / f"worker_rank{rank}.1.pt.trace.json.gz",
                    rank,
                    foreign_context=(rank == 0),
                )

            with self.assertRaisesRegex(
                SUMMARY.TraceContractError,
                "non-target execute_context annotations",
            ):
                SUMMARY.summarize_directory(trace_dir)

    def test_missing_base_time_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "worker_rank0.1.pt.trace.json.gz"
            _write_trace(trace, 0, base_time_ns=None)
            with self.assertRaisesRegex(
                SUMMARY.TraceContractError, "no baseTimeNanoseconds origin"
            ):
                SUMMARY.summarize_trace(
                    trace,
                    context_name=SUMMARY.DEFAULT_CONTEXT,
                    drop_first=1,
                    expected_retained=3,
                    minimum_anchor_coverage=0.98,
                    top=50,
                )

    def test_malformed_base_time_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "worker_rank0.1.pt.trace.json.gz"
            _write_trace(trace, 0, base_time_ns="not-a-time")
            with self.assertRaisesRegex(
                SUMMARY.TraceContractError, "invalid baseTimeNanoseconds"
            ):
                SUMMARY.summarize_trace(
                    trace,
                    context_name=SUMMARY.DEFAULT_CONTEXT,
                    drop_first=1,
                    expected_retained=3,
                    minimum_anchor_coverage=0.98,
                    top=50,
                )


if __name__ == "__main__":
    unittest.main()
