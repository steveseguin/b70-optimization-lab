#!/usr/bin/env python3
"""CPU-only tests for the Laguna accuracy regression gate.

These encode the promotion policy, so they are the tests to read first if the
question is "what exactly blocks a kernel promotion on quality".
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_laguna_regression as gate


def make_run(
    *,
    status: str = "PASS_SCORED",
    outputs: dict[str, str] | None = None,
    correct: int = 8,
    denominator: int = 10,
    vllm_commit: str = "aaa",
    kernels_commit: str = "bbb",
) -> dict[str, Any]:
    outputs = outputs or {"d:1": "h1", "d:2": "h2"}
    return {
        "schema": "laguna-accuracy-eval-v1",
        "status": status,
        "contract": {"contract_id": "c1"},
        "revisions": {
            "scorer_revision_sha256": "s" * 64,
            "prompt_template_sha256": {"gsm8k_v1": "t" * 64},
        },
        "datasets": [
            {
                "dataset": "angelslim_gsm8k",
                "file_sha256": "f" * 64,
                "item_ids_sha256": "i" * 64,
                "prompts_sha256": "p" * 64,
                "prompt_template_sha256": "t" * 64,
            }
        ],
        "sampling": {"temperature": 0, "top_p": 1, "seed": 1, "ignore_eos": False},
        "attribution": {
            "vllm_commit": vllm_commit,
            "kernels_commit": kernels_commit,
            "resolved_cache_partition": {
                "resolved": {
                    "enable_prefix_caching": False,
                    "max_num_partial_prefills": 1,
                    "max_num_batched_tokens": 8192,
                    "max_num_scheduled_tokens": 8182,
                }
            },
        },
        "summary": {
            "by_dataset": {
                "angelslim_gsm8k": {
                    "dataset": "angelslim_gsm8k",
                    "correct": correct,
                    "accuracy_denominator": denominator,
                    "accuracy": correct / denominator if denominator else None,
                }
            }
        },
        "rows": [
            {
                "item_id": item_id,
                "dataset": "angelslim_gsm8k",
                "pass_index": 0,
                "prompt_token_ids_sha256": f"prompt-{item_id}",
                "output_token_ids_sha256": output_hash,
            }
            for item_id, output_hash in sorted(outputs.items())
        ]
        + [
            {
                "item_id": item_id,
                "pass_index": 1,
                "prompt_token_ids_sha256": f"prompt-{item_id}",
                "output_token_ids_sha256": output_hash,
            }
            for item_id, output_hash in sorted(outputs.items())
        ],
    }


# ---------------------------------------------------------------------------
# Gate E: exactness
# ---------------------------------------------------------------------------


def test_identical_outputs_pass_without_needing_the_scores() -> None:
    oracle = make_run()
    candidate = make_run(vllm_commit="ccc", kernels_commit="ddd")
    result = gate.evaluate(oracle, candidate)
    assert result["verdict"] == gate.VERDICT_IDENTICAL
    assert result["outputs"]["items_changed"] == 0
    assert result["outputs"]["output_identical"] is True
    assert any("does not block" in line for line in result["authorizes"])


def test_a_new_kernel_and_a_new_dso_do_not_make_runs_incomparable() -> None:
    """The whole point: the candidate is supposed to be a different kernel.

    Only the data, prompts, scoring logic, sampling and partition have to match.
    """

    oracle = make_run(vllm_commit="old", kernels_commit="old")
    candidate = make_run(vllm_commit="new", kernels_commit="new")
    assert gate.comparability_refusals(oracle, candidate) == []


def test_one_changed_answer_is_detected_exactly() -> None:
    oracle = make_run(outputs={"d:1": "h1", "d:2": "h2"})
    candidate = make_run(outputs={"d:1": "h1", "d:2": "CHANGED"})
    comparison = gate.compare_outputs(oracle, candidate)
    assert comparison["items_changed"] == 1
    assert comparison["changed_item_ids"] == ["d:2"]
    assert comparison["items_identical"] == 1


# ---------------------------------------------------------------------------
# Gate S: score
# ---------------------------------------------------------------------------


def test_a_single_lost_item_blocks_promotion() -> None:
    """Not "outside the confidence interval" -- below. One item is enough.

    At n=80 an interval test would accept a real quality loss, so the gate is a
    strict item-count comparison.
    """

    oracle = make_run(correct=8)
    candidate = make_run(outputs={"d:1": "h1", "d:2": "CHANGED"}, correct=7)
    result = gate.evaluate(oracle, candidate)
    assert result["verdict"] == gate.VERDICT_BLOCK
    assert result["scores"]["regressed_datasets"] == ["angelslim_gsm8k"]
    assert result["authorizes"] == []


def test_changed_outputs_with_equal_scores_require_human_review() -> None:
    oracle = make_run(correct=8)
    candidate = make_run(outputs={"d:1": "h1", "d:2": "CHANGED"}, correct=8)
    result = gate.evaluate(oracle, candidate)
    assert result["verdict"] == gate.VERDICT_REVIEW
    assert result["authorizes"] == [
        "Nothing automatically. The candidate changed the model's output "
        "without scoring lower on any suite; a human must record the "
        "changed items in a note and decide explicitly."
    ]


def test_a_score_improvement_still_does_not_auto_promote() -> None:
    oracle = make_run(correct=8)
    candidate = make_run(outputs={"d:1": "h1", "d:2": "CHANGED"}, correct=10)
    result = gate.evaluate(oracle, candidate)
    assert result["verdict"] == gate.VERDICT_REVIEW


def test_a_changed_denominator_is_treated_as_a_regression() -> None:
    oracle = make_run(correct=8, denominator=10)
    candidate = make_run(
        outputs={"d:1": "h1", "d:2": "CHANGED"}, correct=8, denominator=9
    )
    result = gate.evaluate(oracle, candidate)
    assert result["verdict"] == gate.VERDICT_BLOCK


def test_score_comparison_reports_intervals_without_gating_on_them() -> None:
    oracle = make_run(correct=8, denominator=10)
    candidate = make_run(outputs={"d:1": "h1", "d:2": "X"}, correct=7, denominator=10)
    scores = gate.compare_scores(oracle, candidate)
    entry = scores["per_dataset"][0]
    assert entry["delta_items"] == -1
    assert entry["oracle_interval"]["n"] == 10
    assert (
        0.0
        <= entry["candidate_interval"]["low"]
        <= entry["candidate_interval"]["high"]
        <= 1.0
    )
    assert "NOT the gate" in scores["interval_note"]


# ---------------------------------------------------------------------------
# comparability refusals
# ---------------------------------------------------------------------------


def test_an_oracle_whose_determinism_was_never_proved_is_refused() -> None:
    oracle = make_run(status="PASS_SCORED_DETERMINISM_UNVERIFIED")
    candidate = make_run()
    result = gate.evaluate(oracle, candidate)
    assert result["verdict"] == gate.VERDICT_REFUSED
    kinds = [entry["kind"] for entry in result["refusals"]]
    assert "oracle_not_qualified" in kinds


def test_a_refused_candidate_run_cannot_be_compared() -> None:
    result = gate.evaluate(make_run(), make_run(status="REFUSED"))
    assert result["verdict"] == gate.VERDICT_REFUSED
    assert "candidate_not_scored" in [e["kind"] for e in result["refusals"]]


def test_different_scoring_logic_is_refused() -> None:
    oracle = make_run()
    candidate = copy.deepcopy(oracle)
    candidate["revisions"]["scorer_revision_sha256"] = "z" * 64
    result = gate.evaluate(oracle, candidate)
    assert "revision_mismatch" in [e["kind"] for e in result["refusals"]]


def test_different_prompt_templates_are_refused() -> None:
    oracle = make_run()
    candidate = copy.deepcopy(oracle)
    candidate["revisions"]["prompt_template_sha256"] = {"gsm8k_v1": "q" * 64}
    result = gate.evaluate(oracle, candidate)
    assert "revision_mismatch" in [e["kind"] for e in result["refusals"]]


def test_different_data_is_refused() -> None:
    oracle = make_run()
    candidate = copy.deepcopy(oracle)
    candidate["datasets"][0]["file_sha256"] = "9" * 64
    result = gate.evaluate(oracle, candidate)
    assert "dataset_mismatch" in [e["kind"] for e in result["refusals"]]


@pytest.mark.parametrize("key", ["temperature", "top_p", "seed", "ignore_eos"])
def test_different_sampling_is_refused(key: str) -> None:
    oracle = make_run()
    candidate = copy.deepcopy(oracle)
    candidate["sampling"][key] = "changed"
    result = gate.evaluate(oracle, candidate)
    assert "sampling_mismatch" in [e["kind"] for e in result["refusals"]]


def test_a_different_prefill_partition_is_refused() -> None:
    """A partition change alone rewrites token IDs, as this campaign measured."""

    oracle = make_run()
    candidate = copy.deepcopy(oracle)
    candidate["attribution"]["resolved_cache_partition"]["resolved"][
        "max_num_scheduled_tokens"
    ] = 8192
    result = gate.evaluate(oracle, candidate)
    entries = [e for e in result["refusals"] if e["kind"] == "partition_mismatch"]
    assert entries
    assert "rewrites output token IDs" in entries[0]["detail"]


def test_a_different_item_set_is_refused() -> None:
    oracle = make_run(outputs={"d:1": "h1", "d:2": "h2"})
    candidate = make_run(outputs={"d:1": "h1"})
    result = gate.evaluate(oracle, candidate)
    entries = [e for e in result["refusals"] if e["kind"] == "item_set_mismatch"]
    assert entries and entries[0]["missing_from_candidate"] == ["d:2"]


def test_a_different_prompt_array_for_the_same_item_is_refused() -> None:
    oracle = make_run()
    candidate = copy.deepcopy(oracle)
    candidate["rows"][0]["prompt_token_ids_sha256"] = "different"
    result = gate.evaluate(oracle, candidate)
    assert "prompt_mismatch" in [e["kind"] for e in result["refusals"]]


def test_a_foreign_schema_is_refused() -> None:
    oracle = make_run()
    candidate = copy.deepcopy(oracle)
    candidate["schema"] = "some-other-tool-v1"
    result = gate.evaluate(oracle, candidate)
    assert "wrong_schema" in [e["kind"] for e in result["refusals"]]


def test_a_refusal_suppresses_every_score_and_output_claim() -> None:
    oracle = make_run()
    candidate = make_run(status="REFUSED")
    result = gate.evaluate(oracle, candidate)
    assert result["outputs"] is None
    assert result["scores"] is None
    assert result["authorizes"] == []


# ---------------------------------------------------------------------------
# statistics helper
# ---------------------------------------------------------------------------


def test_wilson_interval_brackets_the_point_estimate() -> None:
    interval = gate.wilson_interval(40, 80)
    assert interval["low"] < 0.5 < interval["high"]
    # At n=80 and p=0.5 the interval is roughly +/- 11 points, which is why an
    # interval test cannot police a one-item regression.
    assert 0.20 < interval["high"] - interval["low"] < 0.24


def test_wilson_interval_is_none_for_an_empty_denominator() -> None:
    assert gate.wilson_interval(0, 0) is None


def test_wilson_interval_stays_inside_zero_and_one() -> None:
    for correct, total in ((0, 10), (10, 10), (1, 3)):
        interval = gate.wilson_interval(correct, total)
        assert 0.0 <= interval["low"] <= interval["high"] <= 1.0


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------


def test_cli_writes_a_verdict_and_exits_nonzero_unless_identical(
    tmp_path: Path,
) -> None:
    oracle_path = tmp_path / "oracle.json"
    candidate_path = tmp_path / "candidate.json"
    out = tmp_path / "verdict.json"
    oracle_path.write_text(json.dumps(make_run()))
    candidate_path.write_text(json.dumps(make_run()))
    code = gate.main(
        [
            "--oracle",
            str(oracle_path),
            "--candidate",
            str(candidate_path),
            "--out",
            str(out),
        ]
    )
    assert code == 0
    assert json.loads(out.read_text())["verdict"] == gate.VERDICT_IDENTICAL

    candidate_path.write_text(
        json.dumps(make_run(outputs={"d:1": "h1", "d:2": "X"}, correct=1))
    )
    code = gate.main(
        [
            "--oracle",
            str(oracle_path),
            "--candidate",
            str(candidate_path),
            "--out",
            str(out),
        ]
    )
    assert code == 1
    payload = json.loads(out.read_text())
    assert payload["verdict"] == gate.VERDICT_BLOCK
    assert payload["oracle_path"] == str(oracle_path)
