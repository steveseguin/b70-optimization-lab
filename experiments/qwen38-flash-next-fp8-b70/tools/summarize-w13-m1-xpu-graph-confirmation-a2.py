#!/usr/bin/env python3
"""Summarize the bounded one-seed W13 N32 A2 confirmation matrix."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
from typing import Any


BASE_PATH = Path(__file__).with_name("summarize-w13-m1-xpu-graph-confirmation.py")
EXPECTED_BASE_SHA256 = (
    "fd403e8f5435612b9f1216598947ee156cdf2f2f4de5a72de5bfea5dbd8355e0"
)
SEEDS = (20260827,)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_base():
    actual = sha256_file(BASE_PATH)
    if actual != EXPECTED_BASE_SHA256:
        raise RuntimeError(f"A1 summarizer drifted: {actual}")
    spec = importlib.util.spec_from_file_location("q38_w13_confirmation_a1", BASE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = load_base()


def summarize(root: Path) -> dict[str, Any]:
    original_seeds = BASE.SEEDS
    try:
        BASE.SEEDS = SEEDS
        result = BASE.summarize(root)
    finally:
        BASE.SEEDS = original_seeds

    rows = result["rows"]
    reductions = [row["matched_latency_reduction_percent"] for row in rows]
    exact = len(rows) == 8 and all(row["exact"] for row in rows)
    drift_ok = len(rows) == 8 and all(
        row["control_drift_within_two_percent"] for row in rows
    )
    median_reduction = statistics.median(reductions)
    positive_cells = sum(row["positive"] for row in rows)
    worst_reduction = min(reductions)
    passed = (
        exact
        and drift_ok
        and median_reduction >= 3.0
        and positive_cells >= 7
        and worst_reduction >= -2.0
    )
    result.update(
        {
            "status": "pass" if passed else "failed_closed",
            "classification": "qwen38_w13_m1_xpu_graph_confirmation_a2",
            "scope": "layers0_47_ep_ranks0_3_seed20260827_matched_fresh_process_cac",
            "source_receipt": {
                "base_summarizer_path": str(BASE_PATH.resolve()),
                "base_summarizer_sha256": EXPECTED_BASE_SHA256,
            },
        }
    )
    result["gates"].update(
        {
            "all_8_cells_exact": exact,
            "all_control_drifts_within_two_percent": drift_ok,
            "median_matched_reduction_percent": median_reduction,
            "median_reduction_at_least_three_percent": median_reduction >= 3.0,
            "positive_cells": positive_cells,
            "at_least_7_positive_cells": positive_cells >= 7,
            "worst_cell_reduction_percent": worst_reduction,
            "no_cell_regressed_more_than_two_percent": worst_reduction >= -2.0,
        }
    )
    result["gates"].pop("all_24_cells_exact", None)
    result["gates"].pop("at_least_20_positive_cells", None)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.result_dir.resolve()
    result = summarize(root)
    (root / "summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
