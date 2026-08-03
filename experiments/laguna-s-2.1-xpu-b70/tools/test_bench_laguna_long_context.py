#!/usr/bin/env python3
"""CPU-only metric-contract tests for the Laguna long-context gate."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench_laguna_long_context as bench


def test_labeled_metric_values_accepts_label_order_and_sparse_positions() -> None:
    name = bench.SPEC_ACCEPTED_PER_POS
    metrics = "\n".join(
        (
            f'{name}{{engine="0",model_name="laguna",position="0"}} 7.0',
            f'{name}{{position="7",engine="0",model_name="laguna"}} 2.0',
            'unrelated_metric{position="7"} 99.0',
        )
    )

    assert bench.labeled_metric_values(metrics, name, "position") == {
        0: 7.0,
        7: 2.0,
    }


def test_labeled_metric_values_rejects_duplicate_position() -> None:
    name = bench.SPEC_ACCEPTED_PER_POS
    metrics = "\n".join(
        (
            f'{name}{{engine="0",position="0"}} 7.0',
            f'{name}{{engine="1",position="0"}} 8.0',
        )
    )

    with pytest.raises(ValueError, match="duplicate"):
        bench.labeled_metric_values(metrics, name, "position")


def test_accepted_per_position_ignores_non_position_metrics() -> None:
    deltas = {
        bench.SPEC_ACCEPTED: 9.0,
        f"{bench.SPEC_ACCEPTED_PER_POS}[0]": 7.0,
        f"{bench.SPEC_ACCEPTED_PER_POS}[1]": 2.0,
    }

    assert bench.accepted_per_position(deltas) == {0: 7.0, 1: 2.0}


def test_metric_delta_rejects_position_schema_drift() -> None:
    with pytest.raises(ValueError, match="key set changed"):
        bench.metric_delta({"position[0]": 1.0}, {"position[1]": 1.0})


def test_timing_metrics_reports_client_visible_e2e_latency() -> None:
    row = {
        "token_id_offsets_s": [2.0, 2.5, 3.0, 3.5],
        "elapsed_s": 4.0,
        "client_ttft_s": 2.0,
        "prompt_tokens": 200,
        "per_request_metrics": {"mean_itl_ms": 500.0},
    }

    timing = bench.timing_metrics(row)

    assert timing["client_ttft_s"] == 2.0
    assert timing["client_e2e_s"] == 4.0
    assert timing["client_e2e_output_tok_s"] == 1.0
    assert timing["prompt_tok_s_lower_bound_from_ttft"] == 100.0
    assert timing["full_interval_tok_s"] == 2.0
    assert timing["server_decode_tok_s_from_mean_itl"] == 2.0


def test_latency_summary_groups_real_use_metrics_by_prompt_length() -> None:
    rows = [
        {
            "prompt_tokens": 256,
            "timing": {
                "client_ttft_s": 1.0,
                "client_e2e_s": 2.0,
                "client_e2e_output_tok_s": 64.0,
                "prompt_tok_s_lower_bound_from_ttft": 256.0,
            },
        },
        {
            "prompt_tokens": 256,
            "timing": {
                "client_ttft_s": 3.0,
                "client_e2e_s": 4.0,
                "client_e2e_output_tok_s": 32.0,
                "prompt_tok_s_lower_bound_from_ttft": 128.0,
            },
        },
        {
            "prompt_tokens": 4096,
            "timing": {
                "client_ttft_s": 8.0,
                "client_e2e_s": 10.0,
                "client_e2e_output_tok_s": 12.8,
                "prompt_tok_s_lower_bound_from_ttft": 512.0,
            },
        },
    ]

    summary = bench.latency_summary(rows)

    assert summary["client_ttft_s"]["median"] == 3.0
    assert summary["by_prompt_tokens"]["256"]["client_ttft_s"]["median"] == 2.0
    assert summary["by_prompt_tokens"]["4096"]["client_e2e_s"]["median"] == 10.0
