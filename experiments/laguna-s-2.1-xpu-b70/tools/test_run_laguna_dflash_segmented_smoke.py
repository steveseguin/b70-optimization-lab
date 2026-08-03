#!/usr/bin/env python3
"""CPU-only contract tests for the segmented DFlash live smoke."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_laguna_dflash_segmented_smoke as smoke


def test_smoke_length_guarantees_crossing_prior_failure_cycle() -> None:
    assert (
        smoke._SMOKE_TOKENS > smoke._PRIOR_FAILURE_CYCLE * smoke._MAX_EMITTED_PER_CYCLE
    )


def test_graph_topologies_follow_replicated_embedding() -> None:
    assert smoke.expected_graph_topologies(False) == ((146, 145), (20, 19))
    assert smoke.expected_graph_topologies(True) == ((145, 144), (19, 18))
    assert smoke.expected_graph_topologies(False, 14, 13) == (
        (146, 145),
        (14, 13),
    )
    assert smoke.expected_graph_topologies(
        False,
        14,
        13,
        target_graphs=50,
        target_eager_breaks=49,
    ) == ((50, 49), (14, 13))


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
        accepted=209,
        per_position=[43, 36, 29, 24, 20, 16, 13, 10, 8, 6, 4],
    )
    delta = smoke.speculation_delta(before, after)
    smoke.validate_speculation(delta, 0)
    assert delta["drafts"] == 40
    assert delta["accepted_per_position"] == [35, 30, 25, 21, 18, 15, 12, 10, 8, 6, 4]


def test_speculation_gate_rejects_counter_disagreement() -> None:
    delta = {
        "drafts": 40,
        "draft_tokens": 440,
        "accepted_tokens": 12,
        "accepted_per_position": [10, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    }
    with pytest.raises(RuntimeError, match="counters disagree"):
        smoke.validate_speculation(delta, 0)


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


def test_graph_gate_rejects_unexpected_audited_topology(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "server.log"
    lines = []
    for action in ("Captured", "Replayed"):
        for rank in range(4):
            for graphs, breaks in ((146, 145), (14, 13)):
                lines.append(
                    f"Worker_TP{rank}_EP{rank} {action} audited breakable "
                    f"cudagraph (graphs={graphs}, eager_breaks={breaks})"
                )
    lines.append(
        "Worker_TP0_EP0 Captured audited breakable cudagraph "
        "(graphs=99, eager_breaks=98)"
    )
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(smoke.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="unexpected audited"):
        smoke.validate_graph_log(
            log,
            replicated_embedding=False,
            target_graphs=146,
            target_eager_breaks=145,
            draft_graphs=14,
            draft_eager_breaks=13,
        )


def test_raw_request_evidence_is_persisted_before_validation(tmp_path: Path) -> None:
    result = {"token_ids": [1, 2, 3], "text": "example"}
    speculation = {"drafts": 2, "draft_tokens": 22, "accepted_tokens": 4}

    path = smoke.persist_request_evidence(
        tmp_path / "segmented-smoke.json",
        0,
        result,
        speculation,
    )

    assert path.name == "segmented-smoke-request-0-raw.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["result"] == result
    assert payload["speculation"] == speculation


def test_response_gate_accepts_configured_full_exactness_length() -> None:
    prompt = {"id": "full", "prompt": "fixed prompt"}
    token_ids = list(range(512))
    expected = {
        "prompt_index": 0,
        "prompt_id": "full",
        "prompt_sha256": hashlib.sha256(b"fixed prompt").hexdigest(),
        "token_ids": token_ids,
    }
    result = {
        "token_ids": token_ids,
        "completion_tokens": 512,
        "usage": {"prompt_tokens_details": {"cached_tokens": 0}},
    }

    smoke.validate_response(result, expected, prompt, 0, 512)
