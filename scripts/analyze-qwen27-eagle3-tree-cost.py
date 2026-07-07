#!/usr/bin/env python3
"""Cost model for Qwen27 EAGLE3 top-k/tree-verifier diagnostics.

This is not a throughput benchmark. It converts offline accepted-depth
diagnostics into a rough endpoint-worthiness screen:

* "magic reranker" assumes the top-k oracle accepted depth could be obtained
  at the same verifier row shape/cost as the current MTP3 recipe.
* "full tree" assumes a legal breadth-k verifier tree to depth D, so verifier
  candidate rows grow as k + k^2 + ... + k^D plus one bonus row.

If even the magic reranker stays below the target throughput, or the legal full
tree is catastrophically below it, this branch needs a stronger drafter rather
than endpoint plumbing.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--summary",
        default=(
            "experiments/qwen36-27b-autoround-int4-b70/diagnostics/"
            "qwen27-eagle3-v6b-topk-oracle-reranker-summary-20260707.json"
        ),
        help="Top-k oracle summary JSON.",
    )
    parser.add_argument(
        "--current-throughput",
        type=float,
        default=68.23626314761921,
        help="Current valid Qwen27 median tok/s.",
    )
    parser.add_argument(
        "--current-visible-tokens-per-step",
        type=float,
        default=2.6727,
        help=(
            "Current MTP3 visible tokens per verifier step. Default comes from "
            "the 2026-07-06 branch-regenerate trace: accepted draft prefix "
            "1.6727 + target bonus 1."
        ),
    )
    parser.add_argument(
        "--current-verifier-rows",
        type=int,
        default=4,
        help="Current MTP3 verifier row shape: 3 draft rows + 1 bonus row.",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=5,
        help="Tree depth / max accepted draft tokens for full-tree rows.",
    )
    parser.add_argument(
        "--target-throughput",
        type=float,
        default=100.0,
        help="Throughput target for endpoint-worthiness screening.",
    )
    parser.add_argument("--out", default="", help="Optional output JSON path.")
    return parser.parse_args()


def full_tree_rows(branch_factor: int, depth: int) -> int:
    return sum(branch_factor**level for level in range(1, depth + 1)) + 1


def throughput_estimate(
    *,
    current_throughput: float,
    current_visible_tokens_per_step: float,
    current_verifier_rows: int,
    visible_tokens_per_step: float,
    verifier_rows: int,
) -> float:
    return current_throughput * (
        visible_tokens_per_step / current_visible_tokens_per_step
    ) * (current_verifier_rows / verifier_rows)


def main() -> int:
    args = parse_args()
    with open(args.summary, "r", encoding="utf-8") as f:
        summary: dict[str, Any] = json.load(f)

    rows: list[dict[str, Any]] = []
    for item in summary["topk_oracle"]["results"]:
        topk = int(item["topk"])
        mean_accepted = float(item["mean_accepted"])
        visible = mean_accepted + 1.0
        magic_rows = args.current_verifier_rows
        tree_rows = full_tree_rows(topk, args.depth)
        magic_tps = throughput_estimate(
            current_throughput=args.current_throughput,
            current_visible_tokens_per_step=args.current_visible_tokens_per_step,
            current_verifier_rows=args.current_verifier_rows,
            visible_tokens_per_step=visible,
            verifier_rows=magic_rows,
        )
        tree_tps = throughput_estimate(
            current_throughput=args.current_throughput,
            current_visible_tokens_per_step=args.current_visible_tokens_per_step,
            current_verifier_rows=args.current_verifier_rows,
            visible_tokens_per_step=visible,
            verifier_rows=tree_rows,
        )
        rows.append({
            "topk": topk,
            "mean_accepted_draft_tokens": mean_accepted,
            "visible_tokens_per_step": visible,
            "magic_reranker_rows": magic_rows,
            "magic_reranker_tok_s_estimate": magic_tps,
            "full_tree_depth": args.depth,
            "full_tree_verifier_rows": tree_rows,
            "full_tree_tok_s_estimate": tree_tps,
            "magic_reaches_target": magic_tps >= args.target_throughput,
            "full_tree_reaches_target": tree_tps >= args.target_throughput,
        })

    best_magic = max(rows, key=lambda r: r["magic_reranker_tok_s_estimate"])
    best_tree = max(rows, key=lambda r: r["full_tree_tok_s_estimate"])
    result = {
        "schema": "qwen27_eagle3_tree_cost_model",
        "classification": "diagnostic_only_no_endpoint",
        "valid_headline_throughput": False,
        "summary": str(Path(args.summary)),
        "current_valid_tok_s": args.current_throughput,
        "current_visible_tokens_per_step": args.current_visible_tokens_per_step,
        "current_verifier_rows": args.current_verifier_rows,
        "target_tok_s": args.target_throughput,
        "rows": rows,
        "best_magic_reranker": best_magic,
        "best_full_tree": best_tree,
        "decision": (
            "Top-k candidate headroom is not enough by itself. Even a free "
            "top-k oracle/reranker stays below the target throughput under "
            "current MTP3 step cost, and a legal full verifier tree is far too "
            "expensive. Continue only with a stronger drafter or a much cheaper "
            "tree/branch verifier design."
        ),
    }

    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
