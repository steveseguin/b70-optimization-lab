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
        record["trace_line"] = line_number
        record["stage"] = payload.get("stage")
        records.append(record)
    return records


def find_alignment(
    records: list[dict[str, Any]], candidate_tokens: list[int]
) -> tuple[int, list[dict[str, Any]]]:
    for start in range(len(records)):
        emitted: list[int] = []
        selected: list[dict[str, Any]] = []
        for record in records[start:]:
            output = [int(token) for token in record.get("output_token_ids", [])]
            if not output:
                continue
            selected.append(record)
            emitted.extend(output)
            prefix_len = min(len(emitted), len(candidate_tokens))
            if emitted[:prefix_len] != candidate_tokens[:prefix_len]:
                break
            if len(emitted) >= len(candidate_tokens):
                if emitted[: len(candidate_tokens)] == candidate_tokens:
                    return start, selected
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
    start, aligned = find_alignment(records, candidate)

    offset = 0
    rounds: list[dict[str, Any]] = []
    first_target_disagreement: dict[str, Any] | None = None
    for record in aligned:
        emitted = [int(token) for token in record.get("output_token_ids", [])]
        targets = [int(token) for token in record.get("target_argmax_token_ids", [])]
        target0 = targets[0] if targets else None
        reference_next = reference[offset] if offset < len(reference) else None
        prefix_exact_before = candidate[:offset] == reference[:offset]
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
        }
        rounds.append(row)
        if (
            first_target_disagreement is None
            and prefix_exact_before
            and target0 is not None
            and target0 != reference_next
        ):
            first_target_disagreement = row
        offset += len(emitted)
        if offset >= len(candidate):
            break

    candidate_difference = first_difference(candidate, reference)
    classification = "no_divergence_in_window"
    if candidate_difference is not None:
        if (
            first_target_disagreement is not None
            and first_target_disagreement["output_offset"]
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
        "aligned_round_count": len(rounds),
        "candidate_token_count": len(candidate),
        "reference_token_count": len(reference),
        "candidate_vs_reference_first_difference": candidate_difference,
        "first_target_verifier_disagreement": first_target_disagreement,
        "rounds": rounds,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

