#!/usr/bin/env python3
"""CPU-only contract tests for the segmented DFlash live smoke."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_laguna_dflash_segmented_smoke as smoke


def test_smoke_length_guarantees_crossing_prior_failure_cycle() -> None:
    assert (
        smoke._SMOKE_TOKENS
        > smoke._PRIOR_FAILURE_CYCLE * smoke._MAX_EMITTED_PER_CYCLE
    )


def test_graph_topologies_follow_replicated_embedding() -> None:
    assert smoke.expected_graph_topologies(False) == ((146, 145), (20, 19))
    assert smoke.expected_graph_topologies(True) == ((145, 144), (19, 18))
    assert smoke.expected_graph_topologies(False, 14, 13) == (
        (146, 145),
        (14, 13),
    )


def metrics(
    *,
    drafts: int,
    draft_tokens: int,
    accepted: int,
    per_position: list[int],
) -> str:
    rows = [
        f'vllm:spec_decode_num_drafts_total{{engine="0"}} {drafts}',
        f'vllm:spec_decode_num_draft_tokens_total{{engine="0"}} {draft_tokens}',
        f'vllm:spec_decode_num_accepted_tokens_total{{engine="0"}} {accepted}',
    ]
    rows.extend(
        "vllm:spec_decode_num_accepted_tokens_per_pos_total"
        f'{{engine="0",position="{index}"}} {value}'
        for index, value in enumerate(per_position)
    )
    return "\n".join(rows) + "\n"


def test_speculation_delta_accepts_realistic_request() -> None:
    before = metrics(
        drafts=10,
        draft_tokens=110,
        accepted=25,
        per_position=[8, 6, 4, 3, 2, 1, 1, 0, 0, 0, 0],
    )
    after = metrics(
        drafts=50,
        draft_tokens=550,
        accepted=145,
        per_position=[43, 36, 29, 24, 20, 16, 13, 10, 8, 6, 4],
    )
    delta = smoke.speculation_delta(before, after)
    smoke.validate_speculation(delta, 0)
    assert delta["drafts"] == 40
    assert delta["accepted_per_position"] == [35, 30, 25, 21, 18, 15, 12, 10, 8, 6, 4]


@pytest.mark.parametrize(
    "per_position,accepted",
    [
        ([40] * 11, 440),
        ([35, 30, 25, 21, 18, 15, 12, 10, 8, 6, 7], 187),
    ],
)
def test_speculation_gate_rejects_flat_or_nondecaying_curve(
    per_position: list[int],
    accepted: int,
) -> None:
    delta = {
        "drafts": 40,
        "draft_tokens": 440,
        "accepted_tokens": accepted,
        "accepted_per_position": per_position,
    }
    with pytest.raises(RuntimeError, match="acceptance"):
        smoke.validate_speculation(delta, 1)


def test_graph_rows_require_rank_complete_topology() -> None:
    lines = [
        f"Worker_TP{rank}_EP{rank} Captured audited breakable cudagraph "
        "BreakableCUDAGraphCapture(graphs=20, eager_breaks=19)"
        for rank in range(4)
    ]
    count, ranks = smoke.graph_rows(
        lines,
        "Captured",
        "(graphs=20, eager_breaks=19)",
    )
    assert count == 4
    assert ranks == {(0, 0), (1, 1), (2, 2), (3, 3)}
