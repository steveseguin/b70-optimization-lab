#!/usr/bin/env python3
"""Align endpoint DDTree commit depths with an offline acceptance report.

This is diagnostic only. It compares the same prompt and canonical root token
position; it does not measure throughput or establish a quality result.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint-trace", required=True)
    parser.add_argument("--offline-report", required=True)
    parser.add_argument("--budget", required=True)
    parser.add_argument("--out", default="")
    return parser.parse_args()


def mean(values: list[int]) -> float | None:
    return sum(values) / len(values) if values else None


def main() -> int:
    args = parse_args()
    offline = json.loads(Path(args.offline_report).read_text(encoding="utf-8"))
    records = offline["budgets"][str(args.budget)]["records"]
    offline_by_key = {
        (str(record["prompt_id"]), int(record["start"])): int(
            record["accepted_depth"]
        )
        for record in records
    }
    prompt_ids = sorted({key[0] for key in offline_by_key}, key=len, reverse=True)

    pairs: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    endpoint_by_prompt: dict[str, list[int]] = defaultdict(list)
    offline_by_prompt: dict[str, list[int]] = defaultdict(list)
    with open(args.endpoint_trace, "r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            endpoint = json.loads(line)
            req_id = str(endpoint.get("req_id", ""))
            prompt_id = next((item for item in prompt_ids if item in req_id), None)
            start = int(endpoint["num_computed_tokens"]) - 1
            if prompt_id is None or (prompt_id, start) not in offline_by_key:
                unmatched.append(
                    {
                        "line": line_number,
                        "req_id": req_id,
                        "start": start,
                    }
                )
                continue
            endpoint_depth = int(endpoint["accepted_depth"])
            offline_depth = offline_by_key[(prompt_id, start)]
            endpoint_by_prompt[prompt_id].append(endpoint_depth)
            offline_by_prompt[prompt_id].append(offline_depth)
            pairs.append(
                {
                    "line": line_number,
                    "prompt_id": prompt_id,
                    "start": start,
                    "endpoint_accepted_depth": endpoint_depth,
                    "offline_accepted_depth": offline_depth,
                    "delta": endpoint_depth - offline_depth,
                    "exact_match": endpoint_depth == offline_depth,
                }
            )

    endpoint_depths = [row["endpoint_accepted_depth"] for row in pairs]
    offline_depths = [row["offline_accepted_depth"] for row in pairs]
    deltas = [row["delta"] for row in pairs]
    result = {
        "classification": "diagnostic_ddtree_endpoint_offline_alignment",
        "endpoint_trace": str(Path(args.endpoint_trace).resolve()),
        "offline_report": str(Path(args.offline_report).resolve()),
        "budget": int(args.budget),
        "aligned_steps": len(pairs),
        "unmatched_steps": len(unmatched),
        "exact_match_steps": sum(row["exact_match"] for row in pairs),
        "exact_match_fraction": (
            sum(row["exact_match"] for row in pairs) / len(pairs)
            if pairs
            else None
        ),
        "endpoint_mean_accepted_depth": mean(endpoint_depths),
        "offline_aligned_mean_accepted_depth": mean(offline_depths),
        "mean_delta": mean(deltas),
        "delta_histogram": dict(sorted(Counter(deltas).items())),
        "per_prompt": {
            prompt_id: {
                "steps": len(endpoint_by_prompt[prompt_id]),
                "endpoint_mean_accepted_depth": mean(
                    endpoint_by_prompt[prompt_id]
                ),
                "offline_aligned_mean_accepted_depth": mean(
                    offline_by_prompt[prompt_id]
                ),
            }
            for prompt_id in sorted(endpoint_by_prompt)
        },
        "pairs": pairs,
        "unmatched": unmatched,
        "validity": (
            "Diagnostic alignment only; target-verified endpoint traces and "
            "offline target-owned labels, not a throughput claim."
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
