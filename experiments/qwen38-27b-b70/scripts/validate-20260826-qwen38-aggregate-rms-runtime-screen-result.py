#!/usr/bin/env python3
"""Validate the 2026-08-26 Qwen3.8 aggregate/runtime screen packet."""

from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
LANE = ROOT / "experiments" / "qwen38-27b-b70"
RAW = LANE / "data" / "qwen38-aggregate-rms-runtime-screen-20260826-r1"
SUMMARY_PATH = LANE / "data" / "2026-08-26-qwen38-aggregate-rms-runtime-screen-summary.json"


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def close(actual: float, expected: float) -> None:
    assert math.isclose(actual, expected, rel_tol=0, abs_tol=1e-9), (
        actual,
        expected,
    )


def concurrent_failures(name: str) -> tuple[int, int]:
    payload = load(RAW / name)
    total = sum(row["concurrency"] for row in payload["results"])
    failed = sum(row["failed"] for row in payload["results"])
    assert total == payload["total_requests"]
    assert payload["pass_all"] is (failed == 0)
    return total, failed


def main() -> None:
    summary = load(SUMMARY_PATH)
    assert summary["objective"]["no_extrapolation"] is True
    assert summary["objective"]["achieved_with_quality_gates"] is False
    assert summary["hardware"] == {
        "gpu": "Intel Arc Pro B70",
        "visible_gpu_count": 2,
        "tp4_available": False,
    }

    fp8_first = load(RAW / "fp8-tp2-c128-first-shape.json")["batches"][0]
    close(
        fp8_first["aggregate_tok_s_wall"],
        summary["official_fp8_tp2_c128"]["first_shape_aggregate_tok_s"],
    )
    assert (fp8_first["oracle_exact_count"], fp8_first["oracle_exact_total"]) == (5, 128)

    conditioned = load(RAW / "fp8-tp2-c128-conditioned-x2.json")["batches"]
    conditioned_rates = [row["aggregate_tok_s_wall"] for row in conditioned]
    assert conditioned_rates == summary["official_fp8_tp2_c128"]["conditioned_aggregate_tok_s"]
    close(
        sum(conditioned_rates) / 2,
        summary["official_fp8_tp2_c128"]["conditioned_median_aggregate_tok_s"],
    )
    assert [(row["oracle_exact_count"], row["oracle_exact_total"]) for row in conditioned] == [
        (5, 128),
        (2, 128),
    ]
    assert concurrent_failures("fp8-tp2-c128-concurrent-quality.json") == (256, 0)

    native_tp2 = load(RAW / "autoround-native-tp2-c64.json")["batches"][0]
    close(
        native_tp2["aggregate_tok_s_wall"],
        summary["autoround_native_xmx"]["tp2_c64"]["aggregate_tok_s"],
    )
    assert (native_tp2["oracle_exact_count"], native_tp2["oracle_exact_total"]) == (0, 64)
    assert concurrent_failures("autoround-native-tp2-c64-quality.json") == (128, 17)

    native_tp1 = load(RAW / "autoround-native-tp1-c64-screen.json")
    close(
        native_tp1["scenarios"]["c64"]["summary"]["aggregate_output_tok_s_wall"],
        summary["autoround_native_xmx"]["tp1_c64"]["aggregate_tok_s"],
    )
    assert load(RAW / "autoround-native-tp1-sequential-quality.json")["pass_all"] is False
    assert load(RAW / "autoround-native-tp2-sequential-quality.json")["pass_all"] is True
    assert load(RAW / "fp8-tp2-c128-sequential-quality.json")["pass_all"] is True

    rms_files = {
        48: "w8a8-rms48-c64-quality.json",
        52: "w8a8-rms52-c64-quality.json",
        54: "w8a8-rms54-c64-quality.json",
        56: "w8a8-rms56-c64-quality.json",
        64: "w8a8-rms64-c64-quality.json",
    }
    expected = {
        row["alpha"]: (row["concurrent_requests"], row["concurrent_failures"])
        for row in summary["w8a8_rms_clip"]["screens"]
        if row["concurrent_requests"]
    }
    assert {alpha: concurrent_failures(name) for alpha, name in rms_files.items()} == expected
    assert concurrent_failures("w8a8-static-c64-quality.json") == (256, 35)

    for relative in (
        "notes/2026-08-26-qwen38-aggregate-rms-runtime-screen-result.md",
        "patches/vllm-qwen38-w8a8-rms-diagnostic-20260826.patch",
        "patches/vllm-xpu-kernels-qwen38-w8a8-rms-diagnostic-20260826.patch",
        "patches/autoround-kernel-oneapi-guard-diagnostic-20260826.Dockerfile",
    ):
        path = LANE / relative
        assert path.is_file() and path.stat().st_size > 0, path

    print("PASS: Qwen3.8 aggregate/runtime screen summary matches raw evidence")


if __name__ == "__main__":
    main()
