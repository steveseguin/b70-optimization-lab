#!/usr/bin/env python3
"""CPU-only tests for the long-context mixed-depth feasibility analyzer."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_laguna_long_mixed_depth as analyzer


def positions(*, beyond: int) -> dict[str, int]:
    result = {str(position): 0 for position in range(11)}
    result["0"] = 3
    result["7"] = beyond
    return result


def row(case_id: str, *, kind: str, prompt_tokens: int, beyond: int) -> dict:
    per_position = positions(beyond=beyond)
    accepted = sum(per_position.values())
    return {
        "case_id": case_id,
        "row_kind": kind,
        "prompt_tokens": prompt_tokens,
        "cached_tokens": 0,
        "passed": True,
        "checks": {"intrinsic": True, "spec_position_counter_consistent": True},
        "oracle": {
            "tested": True,
            "prompt_hash_equal": True,
            "token_ids_equal": True,
            "text_hash_equal": True,
        },
        "spec_decode": {
            "accepted_tokens": accepted,
            "accepted_tokens_per_position": per_position,
            "accepted_tokens_beyond_position_6": beyond,
            "max_accepted_draft_position": 7 if beyond else 0,
        },
    }


def valid_payload() -> dict:
    rows = [row(analyzer.WARMUP_ID, kind="long", prompt_tokens=1024, beyond=2)]
    for long_id, sentinel_id in zip(
        analyzer.LONG_IDS, analyzer.SENTINEL_IDS, strict=True
    ):
        rows.append(row(long_id, kind="long", prompt_tokens=32640, beyond=0))
        rows.append(row(sentinel_id, kind="sentinel", prompt_tokens=256, beyond=2))
    return {
        "schema": "laguna-long-context-gate-v1",
        "status": "PASS_ORACLE_EXACT",
        "run_identity": {"run_role": "candidate", "oracle": "/oracle.json"},
        "summary": {
            "intrinsic_pass_all": True,
            "oracle_exact_all": True,
            "cached_tokens_all_zero": True,
            "prompts_unique": True,
        },
        "prompt_build_manifest": [{"case_id": item["case_id"]} for item in rows],
        "rows": rows,
    }


def test_valid_evidence_authorizes_only_source_prototype() -> None:
    result = analyzer.analyze(valid_payload())

    assert result["status"] == "PASS_IMPLEMENTATION_AUTHORIZED"
    assert result["source_implementation_exists"] is False
    assert result["long_context_depth"] == 7
    assert result["target_verifier_width"] == 12
    assert all(
        item["accepted_tokens_beyond_position_6"] == 0 for item in result["long_rows"]
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("long_beyond", "accepted a token beyond position 6"),
        ("sentinel_shallow", "did not prove deeper short acceptance"),
        ("position_schema", "accepted-position schema drifted"),
        ("oracle", "oracle evidence failed"),
        ("row_order", "row order/identity drifted"),
    ],
)
def test_evidence_drift_fails_closed(mutation: str, message: str) -> None:
    payload = valid_payload()
    if mutation == "long_beyond":
        target = payload["rows"][1]
        target["spec_decode"]["accepted_tokens_per_position"] = positions(beyond=1)
        target["spec_decode"]["accepted_tokens"] = 4
        target["spec_decode"]["accepted_tokens_beyond_position_6"] = 1
        target["spec_decode"]["max_accepted_draft_position"] = 7
    elif mutation == "sentinel_shallow":
        target = payload["rows"][2]
        target["spec_decode"]["accepted_tokens_per_position"] = positions(beyond=0)
        target["spec_decode"]["accepted_tokens"] = 3
        target["spec_decode"]["accepted_tokens_beyond_position_6"] = 0
        target["spec_decode"]["max_accepted_draft_position"] = 0
    elif mutation == "position_schema":
        payload["rows"][1]["spec_decode"]["accepted_tokens_per_position"].pop("10")
    elif mutation == "oracle":
        payload["rows"][1]["oracle"]["token_ids_equal"] = False
    elif mutation == "row_order":
        payload["rows"][1], payload["rows"][2] = (
            payload["rows"][2],
            payload["rows"][1],
        )
    else:
        raise AssertionError(mutation)

    with pytest.raises(ValueError, match=message):
        analyzer.analyze(copy.deepcopy(payload))
