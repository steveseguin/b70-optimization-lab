#!/usr/bin/env python3
"""Join Qwen replay-microscope traces to repeat-quality failures.

The quality suite gives stable repeat indices while vLLM appends a random
suffix to each request ID. This tool extracts the repeat index, finds the modal
quality output, and reports the first large hidden-state divergence plus the
verifier/sampler timeline for each mismatch.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import re
from pathlib import Path
from typing import Any


REPEAT_INDEX_RE = re.compile(r"repeat-(\d+)")


def load_trace(path: Path) -> dict[int, list[dict[str, Any]]]:
    records: dict[int, list[dict[str, Any]]] = defaultdict(list)
    with path.open(encoding="utf-8") as trace_file:
        for line_number, line in enumerate(trace_file, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at {path}:{line_number}") from exc
            request_ids = record.get("matched_req_ids") or record.get("req_ids") or []
            if not request_ids:
                continue
            match = REPEAT_INDEX_RE.search(str(request_ids[0]))
            if match:
                records[int(match.group(1))].append(record)
    return records


def hidden_timeline(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    timeline = []
    for record in records:
        if record.get("stage") != "hidden_after_forward":
            continue
        requests = record.get("requests") or [{}]
        hidden = (record.get("tensors") or {}).get("hidden_states") or {}
        timeline.append(
            {
                "num_computed_tokens": requests[0].get("num_computed_tokens_cpu"),
                "shape": hidden.get("shape"),
                "sum": hidden.get("sum"),
                "l2": hidden.get("l2"),
                "head": hidden.get("head"),
            }
        )
    return timeline


def sampler_timeline(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    timeline = []
    for record in records:
        if record.get("stage") != "sampler_output":
            continue
        requests = record.get("requests") or [{}]
        rows = record.get("logit_rows") or []
        sampled = (record.get("tensors") or {}).get("sampled_token_ids") or {}
        first_row = rows[0] if rows else {}
        timeline.append(
            {
                "num_computed_tokens": requests[0].get("num_computed_tokens_cpu"),
                "num_tokens_no_spec": requests[0].get("num_tokens_no_spec"),
                "accepted_tokens_cpu": first_row.get("num_accepted_tokens_cpu"),
                "accepted_tokens_gpu": first_row.get("num_accepted_tokens_gpu"),
                "sampled_token_ids": sampled.get("head"),
                "row_top1_token_ids": [
                    ((row.get("logits_topk") or {}).get("token_ids") or [None])[0]
                    for row in rows
                ],
                "row_top1_top2_margins": [
                    (row.get("logits_topk") or {}).get("top1_top2_margin")
                    for row in rows
                ],
                "output_token_ids_tail": requests[0].get("state_output_token_ids_tail"),
            }
        )
    return timeline


def first_large_hidden_divergence(
    reference: list[dict[str, Any]],
    candidate: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for step, (expected, actual) in enumerate(zip(reference, candidate)):
        if expected.get("num_computed_tokens") != actual.get("num_computed_tokens"):
            return {
                "step": step,
                "reason": "computed_token_position",
                "reference": expected,
                "candidate": actual,
            }
        expected_sum = expected.get("sum")
        actual_sum = actual.get("sum")
        expected_l2 = expected.get("l2")
        actual_l2 = actual.get("l2")
        if not all(
            isinstance(value, (int, float))
            for value in (expected_sum, actual_sum, expected_l2, actual_l2)
        ):
            continue
        sum_delta = abs(float(actual_sum) - float(expected_sum))
        l2_delta = abs(float(actual_l2) - float(expected_l2))
        # Good repeats show small BF16/collective drift later in a request.
        # Corrupt replay rows observed here jump by hundreds in sum or tens in L2.
        if sum_delta > 50.0 or l2_delta > 5.0:
            return {
                "step": step,
                "reason": "hidden_digest",
                "sum_delta": sum_delta,
                "l2_delta": l2_delta,
                "reference": expected,
                "candidate": actual,
            }
    if len(reference) != len(candidate):
        return {
            "step": min(len(reference), len(candidate)),
            "reason": "timeline_length",
            "reference_steps": len(reference),
            "candidate_steps": len(candidate),
        }
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--quality", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    quality = json.loads(args.quality.read_text(encoding="utf-8"))
    texts = (quality.get("repeat_case") or {}).get("texts") or []
    if not texts:
        raise SystemExit("quality JSON has no repeat_case.texts")
    expected_text, expected_count = Counter(texts).most_common(1)[0]
    mismatch_indices = [index for index, text in enumerate(texts) if text != expected_text]
    trace = load_trace(args.trace)
    reference_index = next(
        (index for index, text in enumerate(texts) if text == expected_text and index in trace),
        None,
    )
    if reference_index is None:
        raise SystemExit("trace has no clean reference repeat")

    reference_hidden = hidden_timeline(trace[reference_index])
    mismatches = []
    for index in mismatch_indices:
        records = trace.get(index, [])
        candidate_hidden = hidden_timeline(records)
        mismatches.append(
            {
                "repeat_index": index,
                "output": texts[index],
                "trace_record_count": len(records),
                "first_large_hidden_divergence": first_large_hidden_divergence(
                    reference_hidden, candidate_hidden
                ),
                "sampler_timeline": sampler_timeline(records),
            }
        )

    output = {
        "classification": "qwen_replay_microscope_quality_join",
        "trace": str(args.trace),
        "quality": str(args.quality),
        "repeat_count": len(texts),
        "expected_output": expected_text,
        "expected_count": expected_count,
        "mismatch_count": len(mismatch_indices),
        "mismatch_indices": mismatch_indices,
        "reference_repeat_index": reference_index,
        "reference_hidden_timeline": reference_hidden,
        "mismatches": mismatches,
    }
    rendered = json.dumps(output, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
