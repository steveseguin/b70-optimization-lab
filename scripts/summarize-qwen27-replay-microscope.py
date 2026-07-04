#!/usr/bin/env python3
"""Summarize Qwen27 worker replay-microscope draft-vs-target traces.

Scheduler spec traces can show placeholder speculative ids on the XPU MTP
path.  The worker replay microscope is the right diagnostic source for
calibration work because it records the real verifier target rows after the
worker has scattered the proposed draft tokens into the input buffer.

This tool is diagnostic-only.  It does not produce a promoted throughput
claim; use the strict realistic final gate for headline results.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_STAGES = ("spec_top_ids", "logits_after_compute", "pre_sample")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
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


def stats(values: list[float]) -> dict[str, float | int | None]:
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


def as_flat_int_list(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, list):
        out: list[int] = []
        for item in value:
            if isinstance(item, list):
                out.extend(as_flat_int_list(item))
            else:
                try:
                    out.append(int(item))
                except (TypeError, ValueError):
                    pass
        return out
    try:
        return [int(value)]
    except (TypeError, ValueError):
        return []


def row_top1(record: dict[str, Any], row: dict[str, Any]) -> int | None:
    topk = row.get("logits_topk")
    if isinstance(topk, dict):
        token_ids = topk.get("token_ids") or []
        if token_ids:
            return int(token_ids[0])

    extra = record.get("extra") or {}
    top_ids = as_flat_int_list(extra.get("top_token_ids"))
    if not top_ids:
        top_ids = as_flat_int_list(extra.get("sampled_token_ids"))
    row_index = row.get("row")
    try:
        row_index_i = int(row_index)
    except (TypeError, ValueError):
        return None
    if 0 <= row_index_i < len(top_ids):
        return int(top_ids[row_index_i])
    return None


def extract_step_events(
    rows: list[dict[str, Any]], stages: set[str]
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for record in rows:
        stage = str(record.get("stage") or "")
        if stage not in stages:
            continue
        target_rows: list[dict[str, Any]] = []
        for row in record.get("logit_rows") or []:
            if row.get("role") != "target":
                continue
            if row.get("draft_token_id") is None:
                continue
            top1 = row_top1(record, row)
            if top1 is None:
                continue
            item = dict(row)
            item["target_top1_token_id"] = int(top1)
            item["draft_matches_target_top1"] = (
                int(item["draft_token_id"]) == int(top1)
            )
            target_rows.append(item)
        if not target_rows:
            continue

        by_req: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in target_rows:
            by_req[str(item.get("req_id") or "")].append(item)
        for req_id, req_rows in by_req.items():
            req_rows.sort(
                key=lambda item: (
                    int(item.get("query_pos") or item.get("row") or 0),
                    int(item.get("row") or 0),
                )
            )
            prefix_accepted = 0
            for item in req_rows:
                if not item["draft_matches_target_top1"]:
                    break
                prefix_accepted += 1
            first_reject: dict[str, Any] | None = None
            if prefix_accepted < len(req_rows):
                reject_row = req_rows[prefix_accepted]
                first_reject = {
                    "position": prefix_accepted,
                    "draft_token_id": int(reject_row["draft_token_id"]),
                    "target_top1_token_id": int(
                        reject_row["target_top1_token_id"]
                    ),
                    "row": int(reject_row.get("row") or 0),
                    "query_pos": reject_row.get("query_pos"),
                }
            events.append({
                "line_no": record.get("_line_no"),
                "ts": record.get("ts"),
                "stage": stage,
                "req_id": req_id,
                "num_draft_tokens": len(req_rows),
                "prefix_accepted": prefix_accepted,
                "full_accept": prefix_accepted == len(req_rows),
                "independent_matches": sum(
                    1 for item in req_rows
                    if item["draft_matches_target_top1"]
                ),
                "first_reject": first_reject,
                "target_rows": [
                    {
                        "position": pos,
                        "row": int(item.get("row") or 0),
                        "query_pos": item.get("query_pos"),
                        "input_id": item.get("input_id"),
                        "draft_token_id": int(item["draft_token_id"]),
                        "target_top1_token_id": int(
                            item["target_top1_token_id"]
                        ),
                        "match": bool(item["draft_matches_target_top1"]),
                        "target_top1_top2_margin": (
                            (item.get("logits_topk") or {}).get(
                                "top1_top2_margin"
                            )
                        ),
                    }
                    for pos, item in enumerate(req_rows)
                ],
            })
    events.sort(key=lambda item: (item.get("ts") is None, item.get("ts") or 0.0))
    return events


def summarize_requests(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_req: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_req[event["req_id"]].append(event)

    summaries: list[dict[str, Any]] = []
    for req_id, req_events in by_req.items():
        draft_tokens = sum(int(event["num_draft_tokens"]) for event in req_events)
        prefix_accepted = sum(int(event["prefix_accepted"]) for event in req_events)
        full_accept_steps = sum(1 for event in req_events if event["full_accept"])
        independent_matches = sum(
            int(event["independent_matches"]) for event in req_events
        )
        hist = Counter(int(event["prefix_accepted"]) for event in req_events)
        per_pos = Counter()
        attempts_by_pos = Counter()
        for event in req_events:
            for pos, row in enumerate(event["target_rows"]):
                attempts_by_pos[pos] += 1
                if row["match"]:
                    per_pos[pos] += 1
        summaries.append({
            "req_id": req_id,
            "first_ts": min(
                (event.get("ts") for event in req_events if event.get("ts") is not None),
                default=None,
            ),
            "last_ts": max(
                (event.get("ts") for event in req_events if event.get("ts") is not None),
                default=None,
            ),
            "steps": len(req_events),
            "draft_tokens": draft_tokens,
            "prefix_accepted_tokens": prefix_accepted,
            "independent_matching_tokens": independent_matches,
            "prefix_acceptance_fraction": (
                None if draft_tokens <= 0 else prefix_accepted / draft_tokens
            ),
            "independent_match_fraction": (
                None if draft_tokens <= 0 else independent_matches / draft_tokens
            ),
            "mean_prefix_acceptance_length": (
                None if not req_events else prefix_accepted / len(req_events)
            ),
            "mean_generated_tokens_per_verifier_step": (
                None if not req_events else 1.0 + prefix_accepted / len(req_events)
            ),
            "full_accept_steps": full_accept_steps,
            "full_accept_rate": (
                None if not req_events else full_accept_steps / len(req_events)
            ),
            "prefix_accepted_hist": dict(sorted(hist.items())),
            "per_position_match_rate": {
                str(pos): per_pos[pos] / attempts_by_pos[pos]
                for pos in sorted(attempts_by_pos)
            },
            "first_reject_examples": [
                event["first_reject"]
                for event in req_events
                if event.get("first_reject") is not None
            ][:8],
        })
    summaries.sort(key=lambda item: (item["first_ts"] is None, item["first_ts"] or 0.0))
    return summaries


def join_result_rows(
    request_summaries: list[dict[str, Any]],
    result_path: Path | None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    if result_path is None:
        return request_summaries, None
    result = load_json(result_path)
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
                "ttft_ms": (
                    None
                    if row.get("ttft_s") is None
                    else float(row["ttft_s"]) * 1000.0
                ),
                "cached_tokens": row.get("cached_tokens"),
                "completion_tokens": row.get("completion_tokens"),
                "prompt_sha256": row.get("prompt_sha256"),
                "output_sha256": row.get("sha256"),
            })
        joined.append(merged)
    return joined, result


def aggregate(requests: list[dict[str, Any]]) -> dict[str, Any]:
    steps = sum(int(item["steps"]) for item in requests)
    draft_tokens = sum(int(item["draft_tokens"]) for item in requests)
    prefix_accepted = sum(int(item["prefix_accepted_tokens"]) for item in requests)
    independent_matches = sum(
        int(item["independent_matching_tokens"]) for item in requests
    )
    full_accept_steps = sum(int(item["full_accept_steps"]) for item in requests)
    hist = Counter()
    per_pos_counts = Counter()
    per_pos_attempts = Counter()
    for item in requests:
        hist.update({int(k): int(v) for k, v in item["prefix_accepted_hist"].items()})
        for key, rate in item["per_position_match_rate"].items():
            pos = int(key)
            attempts = int(item["steps"])
            per_pos_attempts[pos] += attempts
            per_pos_counts[pos] += int(round(float(rate) * attempts))
    return {
        "steps": steps,
        "draft_tokens": draft_tokens,
        "prefix_accepted_tokens": prefix_accepted,
        "independent_matching_tokens": independent_matches,
        "prefix_acceptance_fraction": (
            None if draft_tokens <= 0 else prefix_accepted / draft_tokens
        ),
        "independent_match_fraction": (
            None if draft_tokens <= 0 else independent_matches / draft_tokens
        ),
        "mean_prefix_acceptance_length": (
            None if steps <= 0 else prefix_accepted / steps
        ),
        "mean_generated_tokens_per_verifier_step": (
            None if steps <= 0 else 1.0 + prefix_accepted / steps
        ),
        "full_accept_steps": full_accept_steps,
        "full_accept_rate": None if steps <= 0 else full_accept_steps / steps,
        "prefix_accepted_hist": dict(sorted(hist.items())),
        "per_position_match_rate": {
            str(pos): per_pos_counts[pos] / per_pos_attempts[pos]
            for pos in sorted(per_pos_attempts)
            if per_pos_attempts[pos]
        },
    }


def render_md(summary: dict[str, Any]) -> str:
    totals = summary["totals"]
    lines = [
        "# Qwen27 Replay Microscope Draft-vs-Target Summary",
        "",
        f"- microscope trace: `{summary['microscope_path']}`",
        f"- result JSON: `{summary.get('result_path') or ''}`",
        f"- stages: `{summary['stages']}`",
        "- classification: `diagnostic_only`; do not use as headline throughput",
        f"- requests: `{summary['request_count']}`",
        f"- verifier steps: `{totals['steps']}`",
        f"- draft tokens: `{totals['draft_tokens']}`",
        f"- prefix-accepted tokens: `{totals['prefix_accepted_tokens']}`",
        f"- prefix acceptance fraction: `{totals['prefix_acceptance_fraction']}`",
        f"- mean generated tokens per verifier step: `{totals['mean_generated_tokens_per_verifier_step']}`",
        f"- full-accept rate: `{totals['full_accept_rate']}`",
        f"- per-position target-top1 match: `{totals['per_position_match_rate']}`",
        "",
        "## Prompt Rows",
        "",
        "| idx | prompt | tok/s 1-100 | TTFT ms | steps | prefix acc | mean step tokens | full accept | hist |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in summary["requests"]:
        lines.append(
            f"| {item.get('prompt_index', '')} | `{item.get('prompt_id') or ''}` | "
            f"{item.get('tok_s_1_100_after_ttft') if item.get('tok_s_1_100_after_ttft') is not None else ''} | "
            f"{item.get('ttft_ms') if item.get('ttft_ms') is not None else ''} | "
            f"{item['steps']} | "
            f"{item['prefix_acceptance_fraction'] if item['prefix_acceptance_fraction'] is not None else ''} | "
            f"{item['mean_generated_tokens_per_verifier_step'] if item['mean_generated_tokens_per_verifier_step'] is not None else ''} | "
            f"{item['full_accept_rate'] if item['full_accept_rate'] is not None else ''} | "
            f"`{item['prefix_accepted_hist']}` |"
        )
    lines.extend([
        "",
        "## Notes",
        "",
        "- `scheduled_spec_token_ids` in scheduler traces may be `-1` placeholders on the XPU MTP path.",
        "- This summary uses worker-side real draft tokens from `SpecDecodeMetadata.draft_token_ids`.",
        "- `prefix_acceptance_fraction` is the MTP-visible prefix acceptance rate; `independent_match_fraction` is diagnostic only.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--microscope-jsonl", type=Path, required=True)
    parser.add_argument("--result-json", type=Path)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path)
    parser.add_argument(
        "--stage",
        action="append",
        help=(
            "Microscope stage to include. Defaults to spec_top_ids, "
            "logits_after_compute, and pre_sample."
        ),
    )
    args = parser.parse_args()

    stages = set(args.stage or DEFAULT_STAGES)
    rows = load_jsonl(args.microscope_jsonl)
    events = extract_step_events(rows, stages)
    request_summaries = summarize_requests(events)
    joined, result = join_result_rows(request_summaries, args.result_json)
    prompt_speeds = [
        float(item["tok_s_1_100_after_ttft"])
        for item in joined
        if isinstance(item.get("tok_s_1_100_after_ttft"), (int, float))
    ]
    summary = {
        "microscope_path": str(args.microscope_jsonl),
        "result_path": str(args.result_json) if args.result_json else None,
        "classification": "diagnostic_only",
        "stages": sorted(stages),
        "trace_line_count": len(rows),
        "event_count": len(events),
        "request_count": len(joined),
        "totals": aggregate(joined),
        "speed_stats": stats(prompt_speeds),
        "realistic_final_gate": (result or {}).get("realistic_final_gate"),
        "result_summary": (result or {}).get("summary"),
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
        "events": summary["event_count"],
        "requests": summary["request_count"],
        "steps": summary["totals"]["steps"],
        "prefix_acceptance_fraction": summary["totals"][
            "prefix_acceptance_fraction"
        ],
        "mean_generated_tokens_per_verifier_step": summary["totals"][
            "mean_generated_tokens_per_verifier_step"
        ],
        "speed_median": summary["speed_stats"]["median"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
