#!/usr/bin/env python3
"""Compare Qwen3.6 completion logprob fingerprints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def first_token_diff(left: list[int], right: list[int]) -> dict[str, Any]:
    limit = min(len(left), len(right))
    for index in range(limit):
        if left[index] != right[index]:
            return {
                "index": index,
                "left": left[index],
                "right": right[index],
                "left_context": left[max(0, index - 8): index + 8],
                "right_context": right[max(0, index - 8): index + 8],
            }
    if len(left) != len(right):
        return {"index": limit, "left_len": len(left), "right_len": len(right)}
    return {"index": None}


def top_signature(row: dict[str, Any], top_n: int) -> list[tuple[Any, str]]:
    entries = row.get("top") or []
    sig: list[tuple[Any, str]] = []
    for item in entries[:top_n]:
        token_id = item.get("token_id")
        text = item.get("text")
        sig.append((token_id if token_id is not None else item.get("token_ids"), text))
    return sig


def compact_top(row: dict[str, Any] | None, top_n: int) -> list[dict[str, Any]]:
    if not row:
        return []
    out = []
    for item in (row.get("top") or [])[:top_n]:
        out.append({
            "text": item.get("text"),
            "token_id": item.get("token_id"),
            "token_ids": item.get("token_ids"),
            "logprob": item.get("logprob"),
        })
    return out


def compare_logprobs(
    left: list[dict[str, Any]] | None,
    right: list[dict[str, Any]] | None,
    *,
    top_n: int,
    logprob_epsilon: float,
) -> dict[str, Any]:
    if left is None or right is None:
        return {"available": False}
    limit = min(len(left), len(right))
    first_selected_diff = None
    first_top_diff = None
    first_logprob_delta = None

    for index in range(limit):
        lrow = left[index]
        rrow = right[index]
        if first_selected_diff is None:
            if (
                lrow.get("token_id") != rrow.get("token_id")
                or lrow.get("token_text") != rrow.get("token_text")
            ):
                first_selected_diff = {
                    "index": index,
                    "left_token_id": lrow.get("token_id"),
                    "right_token_id": rrow.get("token_id"),
                    "left_token_text": lrow.get("token_text"),
                    "right_token_text": rrow.get("token_text"),
                    "left_token_logprob": lrow.get("token_logprob"),
                    "right_token_logprob": rrow.get("token_logprob"),
                    "left_top": compact_top(lrow, top_n),
                    "right_top": compact_top(rrow, top_n),
                }
        if first_top_diff is None:
            if top_signature(lrow, top_n) != top_signature(rrow, top_n):
                first_top_diff = {
                    "index": index,
                    "left_selected_token_id": lrow.get("token_id"),
                    "right_selected_token_id": rrow.get("token_id"),
                    "left_selected_token_text": lrow.get("token_text"),
                    "right_selected_token_text": rrow.get("token_text"),
                    "left_top": compact_top(lrow, top_n),
                    "right_top": compact_top(rrow, top_n),
                }
        if first_logprob_delta is None:
            ltop = lrow.get("top") or []
            rtop = rrow.get("top") or []
            shared = min(len(ltop), len(rtop), top_n)
            for pos in range(shared):
                litem = ltop[pos]
                ritem = rtop[pos]
                if (
                    (litem.get("token_id"), litem.get("text"))
                    != (ritem.get("token_id"), ritem.get("text"))
                ):
                    continue
                lprob = litem.get("logprob")
                rprob = ritem.get("logprob")
                if lprob is None or rprob is None:
                    continue
                delta = abs(float(lprob) - float(rprob))
                if delta > logprob_epsilon:
                    first_logprob_delta = {
                        "index": index,
                        "top_position": pos,
                        "token_id": litem.get("token_id"),
                        "text": litem.get("text"),
                        "left_logprob": float(lprob),
                        "right_logprob": float(rprob),
                        "abs_delta": delta,
                    }
                    break
        if first_selected_diff and first_top_diff and first_logprob_delta:
            break

    length_diff = None
    if len(left) != len(right):
        length_diff = {"left_len": len(left), "right_len": len(right)}

    return {
        "available": True,
        "first_selected_diff": first_selected_diff,
        "first_top_diff": first_top_diff,
        "first_logprob_delta": first_logprob_delta,
        "length_diff": length_diff,
    }


def case_map(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text())
    return {case["name"]: case for case in data.get("cases", [])}


def render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Qwen3.6 Logprob Fingerprint Compare",
        "",
        f"- Left: `{report['left']}`",
        f"- Right: `{report['right']}`",
        f"- Cases: `{len(report['cases'])}`",
        f"- All selected tokens match: `{report['selected_tokens_match_all']}`",
        f"- All top-k signatures match: `{report['topk_match_all']}`",
        "",
    ]
    for name, case in report["cases"].items():
        token_diff = case["token_diff"]
        logprob = case["logprob_compare"]
        lines.extend([
            f"## {name}",
            "",
            f"- Selected tokens match: `{token_diff.get('index') is None}`",
            f"- First token diff index: `{token_diff.get('index')}`",
        ])
        if token_diff.get("index") is not None:
            lines.extend([
                f"- Left token: `{token_diff.get('left')}`",
                f"- Right token: `{token_diff.get('right')}`",
            ])
        lines.append(f"- Logprobs available: `{logprob.get('available')}`")
        if logprob.get("available"):
            selected = logprob.get("first_selected_diff")
            top = logprob.get("first_top_diff")
            delta = logprob.get("first_logprob_delta")
            lines.extend([
                f"- First selected-token logprob row diff: `{None if not selected else selected.get('index')}`",
                f"- First top-k signature diff: `{None if not top else top.get('index')}`",
                f"- First same-rank logprob delta > epsilon: `{None if not delta else delta.get('index')}`",
            ])
            if selected:
                lines.extend([
                    "",
                    "Selected-token diff top-k:",
                    "",
                    f"- Left selected: `{selected.get('left_token_id')}` `{selected.get('left_token_text')}`",
                    f"- Right selected: `{selected.get('right_token_id')}` `{selected.get('right_token_text')}`",
                    f"- Left top: `{selected.get('left_top')}`",
                    f"- Right top: `{selected.get('right_top')}`",
                ])
            elif top:
                lines.extend([
                    "",
                    "First top-k diff:",
                    "",
                    f"- Left top: `{top.get('left_top')}`",
                    f"- Right top: `{top.get('right_top')}`",
                ])
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--logprob-epsilon", type=float, default=1e-5)
    args = parser.parse_args()

    left = case_map(args.left)
    right = case_map(args.right)
    names = sorted(set(left) & set(right))
    cases: dict[str, Any] = {}
    selected_match_all = True
    topk_match_all = True
    for name in names:
        lcase = left[name]
        rcase = right[name]
        token_diff = first_token_diff(
            lcase.get("output_token_ids") or [],
            rcase.get("output_token_ids") or [],
        )
        logprob_compare = compare_logprobs(
            lcase.get("normalized_logprobs"),
            rcase.get("normalized_logprobs"),
            top_n=args.top_n,
            logprob_epsilon=args.logprob_epsilon,
        )
        if token_diff.get("index") is not None:
            selected_match_all = False
        if logprob_compare.get("available") and (
            logprob_compare.get("first_top_diff") is not None
            or logprob_compare.get("length_diff") is not None
        ):
            topk_match_all = False
        cases[name] = {
            "token_diff": token_diff,
            "logprob_compare": logprob_compare,
            "left_response_id": lcase.get("response_id"),
            "right_response_id": rcase.get("response_id"),
        }

    report = {
        "left": str(args.left),
        "right": str(args.right),
        "top_n": args.top_n,
        "logprob_epsilon": args.logprob_epsilon,
        "case_names": names,
        "selected_tokens_match_all": selected_match_all,
        "topk_match_all": topk_match_all,
        "cases": cases,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    args.output_md.write_text(render_md(report) + "\n")
    print(json.dumps({
        "output_json": str(args.output_json),
        "output_md": str(args.output_md),
        "selected_tokens_match_all": selected_match_all,
        "topk_match_all": topk_match_all,
        "cases": names,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
