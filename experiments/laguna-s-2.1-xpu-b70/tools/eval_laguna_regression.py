#!/usr/bin/env python3
"""Quality-regression gate: compare a candidate accuracy run against an oracle.

The gate is exact first and statistical never.

Gate E -- exactness (primary)
-----------------------------

Under this campaign's greedy, ``max_num_seqs=1``, fixed-partition serving
configuration, the whole response is a pure function of weights, kernels, batch
shapes and the prefill partition. So the first question is not "did the score
move" but "did any output change at all". If every item's output token IDs match
the oracle's, quality is *provably* unchanged and the accuracy numbers do not
even need to be recomputed to know that. That verdict is ``PASS_OUTPUT_IDENTICAL``.

This is far stronger than a confidence-interval comparison, and it is what makes
the gate cheap enough to run: an output-neutral kernel change inherits the
oracle's scores by proof rather than by re-measurement.

Gate S -- score (secondary, consulted only when Gate E fails)
-------------------------------------------------------------

Once outputs differ, the candidate is a genuinely different machine and the
score has to be looked at. But the suites here are small -- the locally
available GSM8K sample is 80 rows, HumanEval is 164 -- and at those sizes a
one-item move is several accuracy points and is indistinguishable from noise.
A small suite cannot license a promotion, so the gate does not pretend it can:

* **any** per-dataset accuracy below the oracle's blocks promotion. Not "outside
  the interval" -- below. The campaign standard is that quality is never
  traded for speed, and at n=80 the only honest reading of a one-item drop is
  that it might be real.
* equal or higher scores with changed outputs is ``REVIEW_OUTPUT_CHANGED``, not
  a pass. It requires a human decision recorded in a note. A score improvement
  at this sample size is far more likely to be a bug than an improvement.

Relationship to the existing bit-exactness gates
------------------------------------------------

They are complementary and neither substitutes for the other:

* the repeat-oracle exactness gates prove *unchanged* on the benchmark prompts,
  and say nothing about whether the unchanged behaviour is any good;
* this gate proves *good enough*, and its Gate E reuses exactly the same
  evidence type -- output token-ID equality -- so an output-neutral kernel
  passes both for the same reason.

A promotion needs both: bit-exactness against the benchmark oracle, and either
Gate E against the accuracy oracle or an explicit recorded human decision after
Gate S.

Nothing here contacts an endpoint, loads a model, or touches a device.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

SCHEMA = "laguna-accuracy-regression-v1"

VERDICT_IDENTICAL = "PASS_OUTPUT_IDENTICAL"
VERDICT_REVIEW = "REVIEW_OUTPUT_CHANGED"
VERDICT_BLOCK = "BLOCK_SCORE_REGRESSION"
VERDICT_REFUSED = "REFUSED_NOT_COMPARABLE"

ORACLE_STATUS = "PASS_SCORED"

# Fields that must be identical for two runs to be comparable at all. The
# selector set and the grouped-GEMM DSO hash are deliberately absent: those are
# exactly what a kernel candidate is supposed to change.
COMPARABLE_SAMPLING_KEYS = ("temperature", "top_p", "seed", "ignore_eos")


def wilson_interval(
    correct: int, total: int, z: float = 1.96
) -> dict[str, float] | None:
    """Wilson score interval, reported so nobody over-reads a small-n number."""

    if total <= 0:
        return None
    proportion = correct / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    spread = (
        z
        * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
        / denominator
    )
    return {
        "point": proportion,
        "low": max(0.0, centre - spread),
        "high": min(1.0, centre + spread),
        "z": z,
        "n": total,
    }


def _pass_zero_rows(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        row["item_id"]: row for row in run.get("rows", []) if row.get("pass_index") == 0
    }


def _dataset_fingerprint(run: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "dataset": entry.get("dataset"),
            "file_sha256": entry.get("file_sha256"),
            "item_ids_sha256": entry.get("item_ids_sha256"),
            "prompts_sha256": entry.get("prompts_sha256"),
            "prompt_template_sha256": entry.get("prompt_template_sha256"),
        }
        for entry in run.get("datasets", [])
    ]


def _resolved_budgets(run: dict[str, Any]) -> dict[str, Any] | None:
    attribution = run.get("attribution") or {}
    resolved = attribution.get("resolved_cache_partition") or {}
    return resolved.get("resolved")


def comparability_refusals(
    oracle: dict[str, Any], candidate: dict[str, Any]
) -> list[dict[str, Any]]:
    """Everything that makes the two runs incomparable, collected not raised."""

    refusals: list[dict[str, Any]] = []

    def refuse(kind: str, detail: str, **extra: Any) -> None:
        refusals.append({"kind": kind, "detail": detail, **extra})

    for label, run in (("oracle", oracle), ("candidate", candidate)):
        if run.get("schema") != "laguna-accuracy-eval-v1":
            refuse(
                "wrong_schema",
                f"{label} is not a laguna-accuracy-eval-v1 record",
                actual=run.get("schema"),
            )

    if oracle.get("status") != ORACLE_STATUS:
        refuse(
            "oracle_not_qualified",
            "the oracle run is not PASS_SCORED, so its outputs were never "
            "proved reproducible and it cannot serve as a comparison baseline",
            status=oracle.get("status"),
        )
    if candidate.get("status") not in (
        ORACLE_STATUS,
        "PASS_SCORED_DETERMINISM_UNVERIFIED",
    ):
        refuse(
            "candidate_not_scored",
            "the candidate run did not produce scores",
            status=candidate.get("status"),
        )

    oracle_revisions = oracle.get("revisions") or {}
    candidate_revisions = candidate.get("revisions") or {}
    for key in ("scorer_revision_sha256", "prompt_template_sha256"):
        if oracle_revisions.get(key) != candidate_revisions.get(key):
            refuse(
                "revision_mismatch",
                f"{key} differs; the two runs were scored by different logic",
                oracle=oracle_revisions.get(key),
                candidate=candidate_revisions.get(key),
            )

    if _dataset_fingerprint(oracle) != _dataset_fingerprint(candidate):
        refuse(
            "dataset_mismatch",
            "the two runs did not evaluate the same data with the same prompts",
            oracle=_dataset_fingerprint(oracle),
            candidate=_dataset_fingerprint(candidate),
        )

    oracle_sampling = oracle.get("sampling") or {}
    candidate_sampling = candidate.get("sampling") or {}
    for key in COMPARABLE_SAMPLING_KEYS:
        if oracle_sampling.get(key) != candidate_sampling.get(key):
            refuse(
                "sampling_mismatch",
                f"sampling.{key} differs between the runs",
                oracle=oracle_sampling.get(key),
                candidate=candidate_sampling.get(key),
            )

    oracle_budgets = _resolved_budgets(oracle)
    candidate_budgets = _resolved_budgets(candidate)
    if oracle_budgets != candidate_budgets:
        refuse(
            "partition_mismatch",
            "the resolved prefill partition differs; this campaign has measured "
            "that a partition change alone rewrites output token IDs, so an "
            "exact comparison across partitions is meaningless",
            oracle=oracle_budgets,
            candidate=candidate_budgets,
        )

    oracle_rows = _pass_zero_rows(oracle)
    candidate_rows = _pass_zero_rows(candidate)
    only_oracle = sorted(set(oracle_rows) - set(candidate_rows))
    only_candidate = sorted(set(candidate_rows) - set(oracle_rows))
    if only_oracle or only_candidate:
        refuse(
            "item_set_mismatch",
            "the two runs did not score the same item set",
            missing_from_candidate=only_oracle[:20],
            extra_in_candidate=only_candidate[:20],
        )
    for item_id in sorted(set(oracle_rows) & set(candidate_rows)):
        if (
            oracle_rows[item_id]["prompt_token_ids_sha256"]
            != candidate_rows[item_id]["prompt_token_ids_sha256"]
        ):
            refuse(
                "prompt_mismatch",
                f"{item_id} was sent a different prompt token array",
                item_id=item_id,
            )
    return refusals


def compare_outputs(
    oracle: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    """Gate E. Item-by-item output token-ID equality."""

    oracle_rows = _pass_zero_rows(oracle)
    candidate_rows = _pass_zero_rows(candidate)
    shared = sorted(set(oracle_rows) & set(candidate_rows))
    changed = [
        item_id
        for item_id in shared
        if oracle_rows[item_id]["output_token_ids_sha256"]
        != candidate_rows[item_id]["output_token_ids_sha256"]
    ]
    return {
        "items_compared": len(shared),
        "items_identical": len(shared) - len(changed),
        "items_changed": len(changed),
        "changed_item_ids": changed,
        "output_identical": not changed,
    }


def compare_scores(oracle: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Gate S. Per-dataset accuracy, with intervals attached for honesty."""

    oracle_by = ((oracle.get("summary") or {}).get("by_dataset")) or {}
    candidate_by = ((candidate.get("summary") or {}).get("by_dataset")) or {}
    comparisons: list[dict[str, Any]] = []
    regressions: list[str] = []
    for name in sorted(set(oracle_by) | set(candidate_by)):
        left = oracle_by.get(name) or {}
        right = candidate_by.get(name) or {}
        oracle_correct = left.get("correct")
        candidate_correct = right.get("correct")
        oracle_n = left.get("accuracy_denominator")
        candidate_n = right.get("accuracy_denominator")
        regressed = (
            isinstance(oracle_correct, int)
            and isinstance(candidate_correct, int)
            and oracle_n == candidate_n
            and candidate_correct < oracle_correct
        )
        if regressed or oracle_n != candidate_n:
            regressions.append(name)
        comparisons.append(
            {
                "dataset": name,
                "oracle_correct": oracle_correct,
                "candidate_correct": candidate_correct,
                "denominator": oracle_n,
                "candidate_denominator": candidate_n,
                "delta_items": (
                    candidate_correct - oracle_correct
                    if isinstance(oracle_correct, int)
                    and isinstance(candidate_correct, int)
                    else None
                ),
                "oracle_interval": wilson_interval(oracle_correct or 0, oracle_n or 0),
                "candidate_interval": wilson_interval(
                    candidate_correct or 0, candidate_n or 0
                ),
                "regressed": name in regressions,
            }
        )
    return {
        "per_dataset": comparisons,
        "regressed_datasets": sorted(set(regressions)),
        "any_regression": bool(regressions),
        "interval_note": (
            "Intervals are reported so an absolute score is not over-read. They "
            "are NOT the gate: the gate is a strict item-count comparison, "
            "because at these sample sizes an interval test would accept real "
            "quality loss."
        ),
    }


def evaluate(oracle: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    refusals = comparability_refusals(oracle, candidate)
    if refusals:
        return {
            "schema": SCHEMA,
            "verdict": VERDICT_REFUSED,
            "refusals": refusals,
            "authorizes": [],
            "outputs": None,
            "scores": None,
        }
    outputs = compare_outputs(oracle, candidate)
    scores = compare_scores(oracle, candidate)
    if outputs["output_identical"]:
        verdict = VERDICT_IDENTICAL
        authorizes = [
            "The candidate is output-identical to the accuracy oracle on every "
            "scored item, so its quality is proved equal by construction and "
            "the oracle's scores transfer without re-measurement.",
            "Quality does not block this promotion. Every other campaign gate "
            "still applies unchanged.",
        ]
    elif scores["any_regression"]:
        verdict = VERDICT_BLOCK
        authorizes = []
    else:
        verdict = VERDICT_REVIEW
        authorizes = [
            "Nothing automatically. The candidate changed the model's output "
            "without scoring lower on any suite; a human must record the "
            "changed items in a note and decide explicitly."
        ]
    return {
        "schema": SCHEMA,
        "verdict": verdict,
        "refusals": [],
        "authorizes": authorizes,
        "outputs": outputs,
        "scores": scores,
        "oracle": {
            "contract_id": (oracle.get("contract") or {}).get("contract_id"),
            "status": oracle.get("status"),
            "vllm_commit": (oracle.get("attribution") or {}).get("vllm_commit"),
            "kernels_commit": (oracle.get("attribution") or {}).get("kernels_commit"),
        },
        "candidate": {
            "contract_id": (candidate.get("contract") or {}).get("contract_id"),
            "status": candidate.get("status"),
            "vllm_commit": (candidate.get("attribution") or {}).get("vllm_commit"),
            "kernels_commit": (candidate.get("attribution") or {}).get(
                "kernels_commit"
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    oracle = json.loads(args.oracle.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    result = evaluate(oracle, candidate)
    result["oracle_path"] = str(args.oracle)
    result["candidate_path"] = str(args.candidate)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verdict"] == VERDICT_IDENTICAL else 1


if __name__ == "__main__":
    raise SystemExit(main())
