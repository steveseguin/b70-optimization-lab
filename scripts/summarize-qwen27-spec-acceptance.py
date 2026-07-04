#!/usr/bin/env python3
"""Summarize Qwen27 speculative acceptance traces.

The strict Qwen realistic-suite runner sends prompts sequentially with one
active request. vLLM's scheduler trace does not include the prompt id, so this
tool joins trace request groups to benchmark rows by chronological order.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_trace(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        row["_line_no"] = line_no
        rows.append(row)
    return rows


def pct(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * p
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {
            "count": 0,
            "p10": None,
            "median": None,
            "mean": None,
            "min": None,
            "max": None,
            "stdev": None,
        }
    return {
        "count": len(values),
        "p10": pct(values, 0.10),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "min": min(values),
        "max": max(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def summarize_request(req_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    accepted_hist: Counter[int] = Counter()
    draft_hist: Counter[int] = Counter()
    per_pos = Counter()
    emitted_tokens = 0
    generated_tokens = 0
    for row in rows:
        accepted = int(row.get("num_accepted") or 0)
        drafts = int(row.get("num_draft_tokens") or 0)
        accepted_hist[accepted] += 1
        draft_hist[drafts] += 1
        for pos in range(accepted):
            per_pos[pos] += 1
        emitted_tokens += len(row.get("emitted_token_ids") or [])
        generated_tokens += len(row.get("generated_token_ids") or [])
    draft_steps = sum(accepted_hist.values())
    draft_tokens = sum(int(row.get("num_draft_tokens") or 0) for row in rows)
    accepted_tokens = sum(int(row.get("num_accepted") or 0) for row in rows)
    rejected_tokens = sum(int(row.get("num_rejected") or 0) for row in rows)
    full_accept_steps = sum(
        1
        for row in rows
        if int(row.get("num_draft_tokens") or 0) > 0
        and int(row.get("num_accepted") or 0)
        == int(row.get("num_draft_tokens") or 0)
    )
    first_ts = min((row.get("ts") for row in rows if row.get("ts") is not None), default=None)
    last_ts = max((row.get("ts") for row in rows if row.get("ts") is not None), default=None)
    return {
        "req_id": req_id,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "trace_rows": len(rows),
        "draft_steps": draft_steps,
        "draft_tokens": draft_tokens,
        "accepted_tokens": accepted_tokens,
        "rejected_tokens": rejected_tokens,
        "emitted_tokens_from_trace": emitted_tokens,
        "generated_tokens_from_trace": generated_tokens,
        "acceptance_fraction": None
        if draft_tokens <= 0
        else accepted_tokens / draft_tokens,
        "mean_acceptance_length_including_target": None
        if draft_steps <= 0
        else 1.0 + accepted_tokens / draft_steps,
        "emitted_tokens_per_step": None
        if draft_steps <= 0
        else emitted_tokens / draft_steps,
        "accepted_hist": dict(sorted(accepted_hist.items())),
        "draft_hist": dict(sorted(draft_hist.items())),
        "per_position_acceptance_rate": {
            str(pos): per_pos[pos] / draft_steps for pos in sorted(per_pos)
        }
        if draft_steps
        else {},
        "full_accept_steps": full_accept_steps,
        "full_accept_rate": None
        if draft_steps <= 0
        else full_accept_steps / draft_steps,
    }


def render_md(summary: dict[str, Any]) -> str:
    lines = [
        "# Qwen27 Spec Acceptance Summary",
        "",
        f"- trace: `{summary['trace_path']}`",
        f"- result: `{summary.get('result_path') or ''}`",
        f"- requests: `{summary['request_count']}`",
        f"- trace rows: `{summary['trace_row_count']}`",
        f"- draft steps: `{summary['totals']['draft_steps']}`",
        f"- draft tokens: `{summary['totals']['draft_tokens']}`",
        f"- accepted tokens: `{summary['totals']['accepted_tokens']}`",
        f"- acceptance fraction: `{summary['totals']['acceptance_fraction']}`",
        f"- mean acceptance length including target: `{summary['totals']['mean_acceptance_length_including_target']}`",
        f"- emitted tokens per step: `{summary['totals']['emitted_tokens_per_step']}`",
        f"- full-accept rate: `{summary['totals']['full_accept_rate']}`",
        "",
        "## Histograms",
        "",
        f"- accepted histogram: `{summary['totals']['accepted_hist']}`",
        f"- per-position acceptance: `{summary['totals']['per_position_acceptance_rate']}`",
        "",
        "## Prompt Rows",
        "",
        "| idx | prompt | tok/s 1-100 | TTFT ms | steps | acc frac | mean len | full accept | hist |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in summary["requests"]:
        prompt_id = item.get("prompt_id") or ""
        tok_s = item.get("tok_s_1_100_after_ttft")
        ttft = item.get("ttft_ms")
        lines.append(
            f"| {item.get('prompt_index', '')} | `{prompt_id}` | "
            f"{tok_s if tok_s is not None else ''} | "
            f"{ttft if ttft is not None else ''} | "
            f"{item['draft_steps']} | "
            f"{item['acceptance_fraction'] if item['acceptance_fraction'] is not None else ''} | "
            f"{item['mean_acceptance_length_including_target'] if item['mean_acceptance_length_including_target'] is not None else ''} | "
            f"{item['full_accept_rate'] if item['full_accept_rate'] is not None else ''} | "
            f"`{item['accepted_hist']}` |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-jsonl", type=Path, required=True)
    parser.add_argument("--result-json", type=Path)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path)
    args = parser.parse_args()

    trace_rows = load_trace(args.trace_jsonl)
    by_req: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trace_rows:
        by_req[str(row.get("req_id") or "")].append(row)

    request_summaries = [
        summarize_request(req_id, rows) for req_id, rows in by_req.items()
    ]
    request_summaries.sort(
        key=lambda row: (row["first_ts"] is None, row["first_ts"] or 0.0)
    )

    result_rows: list[dict[str, Any]] = []
    result = None
    if args.result_json:
        result = load_json(args.result_json)
        result_rows = result.get("rows") or []

    joined: list[dict[str, Any]] = []
    for index, item in enumerate(request_summaries):
        merged = dict(item)
        if index < len(result_rows):
            row = result_rows[index]
            merged.update({
                "prompt_index": row.get("prompt_index"),
                "prompt_id": row.get("prompt_id"),
                "tok_s_1_100_after_ttft": row.get("tok_s_1_100_after_ttft"),
                "tok_s_after_ttft_full": row.get("tok_s_after_ttft_full"),
                "tok_s_wall_full": row.get("tok_s_wall_full"),
                "ttft_ms": None
                if row.get("ttft_s") is None
                else float(row["ttft_s"]) * 1000.0,
                "cached_tokens": row.get("cached_tokens"),
                "completion_tokens": row.get("completion_tokens"),
                "prompt_sha256": row.get("prompt_sha256"),
                "output_sha256": row.get("sha256"),
            })
        joined.append(merged)

    totals = {
        "draft_steps": sum(item["draft_steps"] for item in request_summaries),
        "draft_tokens": sum(item["draft_tokens"] for item in request_summaries),
        "accepted_tokens": sum(item["accepted_tokens"] for item in request_summaries),
        "rejected_tokens": sum(item["rejected_tokens"] for item in request_summaries),
        "emitted_tokens_from_trace": sum(
            item["emitted_tokens_from_trace"] for item in request_summaries
        ),
        "generated_tokens_from_trace": sum(
            item["generated_tokens_from_trace"] for item in request_summaries
        ),
        "full_accept_steps": sum(
            item["full_accept_steps"] for item in request_summaries
        ),
        "accepted_hist": {},
        "draft_hist": {},
        "per_position_acceptance_rate": {},
    }
    accepted_hist: Counter[int] = Counter()
    draft_hist: Counter[int] = Counter()
    per_pos_counts = Counter()
    for item in request_summaries:
        accepted_hist.update({int(k): int(v) for k, v in item["accepted_hist"].items()})
        draft_hist.update({int(k): int(v) for k, v in item["draft_hist"].items()})
        for key, value in item["per_position_acceptance_rate"].items():
            # Convert request-level rates back to counts.
            per_pos_counts[int(key)] += int(round(value * item["draft_steps"]))
    draft_steps = int(totals["draft_steps"])
    draft_tokens = int(totals["draft_tokens"])
    accepted_tokens = int(totals["accepted_tokens"])
    emitted_tokens = int(totals["emitted_tokens_from_trace"])
    full_accept_steps = int(totals["full_accept_steps"])
    totals["accepted_hist"] = dict(sorted(accepted_hist.items()))
    totals["draft_hist"] = dict(sorted(draft_hist.items()))
    totals["acceptance_fraction"] = (
        None if draft_tokens <= 0 else accepted_tokens / draft_tokens
    )
    totals["mean_acceptance_length_including_target"] = (
        None if draft_steps <= 0 else 1.0 + accepted_tokens / draft_steps
    )
    totals["emitted_tokens_per_step"] = (
        None if draft_steps <= 0 else emitted_tokens / draft_steps
    )
    totals["full_accept_rate"] = (
        None if draft_steps <= 0 else full_accept_steps / draft_steps
    )
    totals["per_position_acceptance_rate"] = (
        {str(pos): per_pos_counts[pos] / draft_steps for pos in sorted(per_pos_counts)}
        if draft_steps
        else {}
    )

    prompt_speeds = [
        float(item["tok_s_1_100_after_ttft"])
        for item in joined
        if isinstance(item.get("tok_s_1_100_after_ttft"), (int, float))
    ]
    summary = {
        "trace_path": str(args.trace_jsonl),
        "result_path": str(args.result_json) if args.result_json else None,
        "trace_row_count": len(trace_rows),
        "request_count": len(request_summaries),
        "totals": totals,
        "speed_stats": stats(prompt_speeds),
        "realistic_final_gate": (result or {}).get("realistic_final_gate"),
        "summary": (result or {}).get("summary"),
        "requests": joined,
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(summary, indent=2) + "\n")
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        args.out_md.write_text(render_md(summary))
    print(json.dumps({
        "out_json": str(args.out_json),
        "out_md": str(args.out_md) if args.out_md else None,
        "requests": summary["request_count"],
        "draft_steps": totals["draft_steps"],
        "acceptance_fraction": totals["acceptance_fraction"],
        "mean_acceptance_length": totals["mean_acceptance_length_including_target"],
        "speed_median": summary["speed_stats"]["median"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
