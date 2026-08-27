#!/usr/bin/env python3
"""Validate and aggregate the frozen Qwen3.8 Q4+MTP2 mixed-content campaign."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
CAMPAIGN = "qwen38-q4km-q4mtp-tp1-mixed-content-depth-20260827-r1"
DEPTHS = (2048, 4096, 8192, 16384, 24576, 32768)
CLASSES = ("technical-prose", "python-code", "structured-docs")
INPUTS = {
    "mtp0": (
        REPO / "experiments/qwen38-27b-b70/data/qwen38-q4km-q4mtp-tp1-mixed-content-depth-20260827-r1-mtp0/summary.json",
        "7605eec0ca0dc04c0af43bd42f540a1041cadfc77a1e852803bb03cf10733d2f",
    ),
    "mtp2-r1-a": (
        REPO / "experiments/qwen38-27b-b70/data/qwen38-q4km-q4mtp-tp1-mixed-content-depth-20260827-r1-mtp2-attempt1/summary.json",
        "52526367bfe2b69b7f88d9dc69b2884ce79b959cbc87f1139d7f61e30acaa85f",
    ),
    "mtp2-r1-b": (
        REPO / "experiments/qwen38-27b-b70/data/qwen38-q4km-q4mtp-tp1-mixed-content-depth-20260827-r1-mtp2-attempt2/summary.json",
        "15decd31beb2e30a8450e7ee8ba75cb5931ea972a69a20732848a94f4335ac06",
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs() -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    for name, (path, expected_hash) in INPUTS.items():
        if sha256(path) != expected_hash:
            raise ValueError(f"{name} summary SHA mismatch")
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("campaign_id") != CAMPAIGN or value.get("status") != "passed":
            raise ValueError(f"{name} is not a passed campaign summary")
        loaded[name] = value
    return loaded


def case_map(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cases = summary.get("cases")
    if not isinstance(cases, list) or len(cases) != len(DEPTHS) * len(CLASSES):
        raise ValueError("summary must contain exactly 18 cases")
    mapped = {row["case_id"]: row for row in cases}
    expected = {
        f"{content_class}-depth-{depth}"
        for depth in DEPTHS
        for content_class in CLASSES
    }
    if set(mapped) != expected:
        raise ValueError("summary case set mismatch")
    if not all(
        row.get("receipt_status") == "passed"
        and row.get("cache_zero") is True
        and isinstance(row.get("decode_tok_s"), (int, float))
        and math.isfinite(row["decode_tok_s"])
        and isinstance(row.get("ttft_ms"), (int, float))
        and math.isfinite(row["ttft_ms"])
        and len(row.get("output_token_ids", [])) == 128
        for row in mapped.values()
    ):
        raise ValueError("one or more case gates failed")
    return mapped


def median(values: list[float]) -> float:
    return statistics.median(values)


def relative_range_percent(values: list[float]) -> float:
    center = median(values)
    return (max(values) - min(values)) / center * 100


def build_result(created_at_utc: str) -> dict[str, Any]:
    inputs = load_inputs()
    target = case_map(inputs["mtp0"])
    attempts = [
        (name, inputs[name], case_map(inputs[name]))
        for name in ("mtp2-r1-a", "mtp2-r1-b")
    ]
    for name, summary, cases in attempts:
        if not all(row.get("target_oracle_exact") is True for row in cases.values()):
            raise ValueError(f"{name} did not pass recorded target parity")
        if not all(
            cases[case_id]["output_token_ids"] == target[case_id]["output_token_ids"]
            for case_id in target
        ):
            raise ValueError(f"{name} output arrays differ from the target oracle")
        counters = summary.get("draft_counters", {})
        if not (counters.get("drafted", 0) > 0 and counters.get("accepted", 0) > 0):
            raise ValueError(f"{name} speculative counters did not engage")

    all_summaries = [inputs["mtp0"], *(summary for _n, summary, _c in attempts)]
    if not all(
        summary.get("canaries") == {"before": True, "after": True}
        for summary in all_summaries
    ):
        raise ValueError("one or more canary batteries failed")

    points = []
    for depth in DEPTHS:
        target_class_samples = [
            target[f"{content_class}-depth-{depth}"] for content_class in CLASSES
        ]
        target_decode = median([row["decode_tok_s"] for row in target_class_samples])
        target_ttft = median([row["ttft_ms"] for row in target_class_samples])
        attempt_rows = []
        for name, _summary, cases in attempts:
            selected = [cases[f"{content_class}-depth-{depth}"] for content_class in CLASSES]
            attempt_rows.append(
                {
                    "attempt": name,
                    "class_decode_tok_s": {
                        content_class: cases[f"{content_class}-depth-{depth}"]["decode_tok_s"]
                        for content_class in CLASSES
                    },
                    "class_ttft_ms": {
                        content_class: cases[f"{content_class}-depth-{depth}"]["ttft_ms"]
                        for content_class in CLASSES
                    },
                    "class_median_decode_tok_s": median(
                        [row["decode_tok_s"] for row in selected]
                    ),
                    "class_median_ttft_ms": median([row["ttft_ms"] for row in selected]),
                    "target_exact_cases": 3,
                }
            )
        decode_values = [row["class_median_decode_tok_s"] for row in attempt_rows]
        ttft_values = [row["class_median_ttft_ms"] for row in attempt_rows]
        aggregate_decode = median(decode_values)
        aggregate_ttft = median(ttft_values)
        points.append(
            {
                "active_context_tokens": depth,
                "decode_tok_s": aggregate_decode,
                "ttft_ms": aggregate_ttft,
                "fresh_server_decode_samples": decode_values,
                "fresh_server_ttft_samples_ms": ttft_values,
                "decode_relative_range_percent": relative_range_percent(decode_values),
                "ttft_relative_range_percent": relative_range_percent(ttft_values),
                "target_control_decode_tok_s": target_decode,
                "target_control_ttft_ms": target_ttft,
                "decode_speedup_vs_control_percent": (aggregate_decode / target_decode - 1) * 100,
                "fresh_servers": 2,
                "content_classes": 3,
                "measured_requests": 6,
                "target_exact_cases": 6,
                "attempts": attempt_rows,
            }
        )

    return {
        "schema": "neural.download.qwen38-q4km-q4mtp-tp1-mixed-content-depth-result.v1",
        "campaign_id": CAMPAIGN,
        "created_at_utc": created_at_utc,
        "status": "passed",
        "classification": "Grade B three-class unrepeated real-content exact-depth HTTP decode and TTFT profile",
        "identity": {
            "model": "Qwen3.8-27B",
            "target": "Q4_K_M",
            "draft": "Q4_0 external MTP",
            "mtp_depth": 2,
            "cards": 1,
            "tensor_parallel": 1,
            "context_capacity": 33024,
            "parallel_slots": 1,
            "target_and_draft_kv": "f16",
            "graph": False,
            "prompt_cache": False,
        },
        "fixture": {
            "path": "data/qwen27-exact-depth/qwen38-bce40ca-mixed-content-depth-v1.json",
            "sha256": "a8a48b3549062759cc94b28f2360bea119f8adde582ace04928111b624d952ed",
            "content_classes": list(CLASSES),
            "source_repetition": False,
            "natural_task_or_retrieval_prompt": False,
        },
        "inputs": {
            name: {"path": str(path.relative_to(REPO)), "sha256": expected_hash}
            for name, (path, expected_hash) in INPUTS.items()
        },
        "quality": {
            "mtp2_target_exact_cases": 36,
            "mtp2_target_exact_total": 36,
            "complete_output_token_ids_per_case": 128,
            "objective_canary_batteries_passed": 6,
            "objective_canary_batteries_total": 6,
            "cached_tokens_zero_requests": 54,
            "request_gate_passes": 54,
            "request_gate_total": 54,
        },
        "draft_acceptance": {
            name: summary["draft_counters"]
            for name, summary, _cases in attempts
        },
        "aggregation": {
            "within_server": "median of the three content-class values at each exact depth",
            "across_servers": "median of two fresh-server within-server medians",
            "decode_metric": "99 inter-token intervals between timestamped output events 1 and 100 after TTFT",
            "ttft_metric": "direct request start to first returned output token",
        },
        "points": points,
        "publication_authority": {
            "context_decode_and_ttft_cells": list(DEPTHS),
            "single_user_headline_replacement": False,
            "localmaxxing_submission": False,
            "natural_task_or_retrieval_claim": False,
            "interpolation_or_extrapolation": False,
        },
        "publication_boundary": "Directly measured raw-document continuations from unrepeated technical prose, Python code, and structured documentation. Representative real-content context shape, not a natural retrieval/task suite. No value transfers to another quant, topology, MTP depth, KV type, graph mode, runtime, or model revision.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = build_result(dt.datetime.now(dt.UTC).isoformat())
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as stream:
            stream.write(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
