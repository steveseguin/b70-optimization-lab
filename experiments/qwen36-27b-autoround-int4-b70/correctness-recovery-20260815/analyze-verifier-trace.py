#!/usr/bin/env python3
"""Align one XPU verifier trace with candidate and target-only token streams."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROMPT_ID = "holdout--arithmetic-reasoning"


def load_row(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    matches = [row for row in payload["rows"] if row["prompt_id"] == PROMPT_ID]
    if len(matches) != 1:
        raise SystemExit(f"expected one {PROMPT_ID!r} row in {path}, got {len(matches)}")
    return matches[0]


def load_trace(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        payload = json.loads(line)
        rows = payload.get("records") or []
        if len(rows) != 1:
            continue
        record = dict(rows[0])
        # The TP workers both append the same logical verifier decision.  Keep
        # one copy so an emitted token is not counted once per rank.
        if records and all(
            records[-1].get(key) == value for key, value in record.items()
        ) and all(
            record.get(key) == value
            for key, value in records[-1].items()
            if key not in {"trace_line", "stage"}
        ):
            continue
        record["trace_line"] = line_number
        record["stage"] = payload.get("stage")
        records.append(record)
    return records


def find_alignment(
    records: list[dict[str, Any]], candidate_tokens: list[int]
) -> tuple[int, int, list[dict[str, Any]]]:
    # The first generated token seeds speculative decoding and therefore is
    # not represented by a verifier record.  Search candidate offsets as well
    # as trace starts instead of assuming the trace begins at token zero.
    for candidate_offset in range(min(8, len(candidate_tokens))):
        expected = candidate_tokens[candidate_offset:]
        for start in range(len(records)):
            emitted: list[int] = []
            selected: list[dict[str, Any]] = []
            for record in records[start:]:
                output = [int(token) for token in record.get("output_token_ids", [])]
                if not output:
                    continue
                selected.append(record)
                emitted.extend(output)
                prefix_len = min(len(emitted), len(expected))
                if emitted[:prefix_len] != expected[:prefix_len]:
                    break
                if len(emitted) >= len(expected):
                    if emitted[: len(expected)] == expected:
                        return start, candidate_offset, selected
                    break
    raise SystemExit("could not align verifier records with candidate token stream")


def first_difference(left: list[int], right: list[int]) -> dict[str, Any] | None:
    for index, (lhs, rhs) in enumerate(zip(left, right)):
        if lhs != rhs:
            return {"index": index, "left": lhs, "right": rhs}
    if len(left) != len(right):
        return {
            "index": min(len(left), len(right)),
            "left": left[min(len(left), len(right)) :] or None,
            "right": right[min(len(left), len(right)) :] or None,
        }
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    candidate = [int(token) for token in load_row(args.candidate)["token_ids"]]
    reference = [int(token) for token in load_row(args.reference)["token_ids"]]
    records = load_trace(args.trace)
    start, candidate_offset, aligned = find_alignment(records, candidate)

    offset = candidate_offset
    rounds: list[dict[str, Any]] = []
    first_target_disagreement: dict[str, Any] | None = None
    for record in aligned:
        emitted = [int(token) for token in record.get("output_token_ids", [])]
        targets = [int(token) for token in record.get("target_argmax_token_ids", [])]
        target0 = targets[0] if targets else None
        reference_next = reference[offset] if offset < len(reference) else None
        prefix_exact_before = candidate[:offset] == reference[:offset]
        comparable_target_rows: list[dict[str, Any]] = []
        if prefix_exact_before:
            drafts = [int(token) for token in record.get("draft_token_ids", [])]
            for row_index, target_token in enumerate(targets):
                target_position = offset + row_index
                if target_position >= len(reference):
                    break
                # Verifier row j is conditioned on draft rows [0, j).  It is
                # comparable to the target-only stream only while that draft
                # prefix equals the reference continuation.
                if drafts[:row_index] != reference[offset:target_position]:
                    break
                comparison = {
                    "row_index": row_index,
                    "output_position": target_position,
                    "target_token": target_token,
                    "reference_token": reference[target_position],
                    "matches_reference": target_token == reference[target_position],
                }
                comparable_target_rows.append(comparison)
                if first_target_disagreement is None and not comparison["matches_reference"]:
                    first_target_disagreement = {
                        "trace_line": record["trace_line"],
                        "stage": record.get("stage"),
                        **comparison,
                        "draft_token_ids": drafts,
                        "target_argmax_token_ids": targets,
                        "output_token_ids": emitted,
                    }
        row = {
            "trace_line": record["trace_line"],
            "stage": record.get("stage"),
            "output_offset": offset,
            "prefix_exact_before": prefix_exact_before,
            "draft_token_ids": record.get("draft_token_ids", []),
            "target_argmax_token_ids": targets,
            "output_token_ids": emitted,
            "prefix_accepted": record.get("prefix_accepted"),
            "target0": target0,
            "reference_next": reference_next,
            "target0_matches_reference": target0 == reference_next,
            "comparable_target_rows": comparable_target_rows,
        }
        rounds.append(row)
        offset += len(emitted)
        if offset >= len(candidate):
            break

    # The diagnostic intentionally generates only 128 tokens while the frozen
    # target-only reference has 512. A matching shorter candidate is an exact
    # reference prefix, not a divergence at EOF. If a candidate is longer than
    # the reference, first_difference still reports the first excess token.
    candidate_difference = first_difference(candidate, reference[: len(candidate)])
    candidate_is_exact_reference_prefix = candidate_difference is None
    classification = "no_divergence_in_window"
    if candidate_difference is not None:
        if (
            first_target_disagreement is not None
            and first_target_disagreement["output_position"]
            <= candidate_difference["index"]
        ):
            classification = "target_verifier_row_diverged_before_or_at_output"
        else:
            classification = "rejection_or_state_bookkeeping_diverged_output"

    result = {
        "classification": classification,
        "prompt_id": PROMPT_ID,
        "trace_record_count": len(records),
        "aligned_start_record": start,
        "candidate_tokens_before_trace": candidate_offset,
        "aligned_round_count": len(rounds),
        "candidate_token_count": len(candidate),
        "reference_token_count": len(reference),
        "candidate_is_exact_reference_prefix": candidate_is_exact_reference_prefix,
        "candidate_vs_reference_first_difference": candidate_difference,
        "first_target_verifier_disagreement": first_target_disagreement,
        "rounds": rounds,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
