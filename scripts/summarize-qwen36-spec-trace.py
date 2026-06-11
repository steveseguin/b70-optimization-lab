#!/usr/bin/env python3
"""Summarize Qwen3.6 speculative scheduler traces and benchmark artifacts.

The scheduler trace is low-level JSONL keyed by vLLM request id. Older
benchmark artifacts may not store request ids or request timestamps, so this
tool reports whether an exact request-level join is possible instead of
pretending prompt-class results can be mapped to trace rows.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import statistics
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return statistics.mean(values)


def median_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return statistics.median(values)


def pct(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator * 100.0 / denominator


def parse_label_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        path = Path(value)
        return path.stem, path
    label, path = value.split("=", 1)
    label = label.strip()
    if not label:
        raise ValueError(f"empty label in {value!r}")
    return label, Path(path)


def summarize_trace(path: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    malformed = 0
    for line_no, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            malformed += 1

    by_req: dict[str, dict[str, Any]] = {}
    accept_hist = collections.Counter()
    scheduled_pairs = collections.Counter()
    generated_heads = collections.Counter()
    repeated_scheduled_rows = 0
    full_accept_rows = 0
    full_reject_rows = 0
    suppressed_bonus_rows = 0
    max_full_accept_streak = 0

    for row in rows:
        req_id = str(row.get("req_id") or "")
        req = by_req.setdefault(
            req_id,
            {
                "req_id": req_id,
                "rows": 0,
                "draft_tokens": 0,
                "accepted": 0,
                "rejected": 0,
                "first_ts": None,
                "last_ts": None,
                "min_output_tokens": None,
                "max_output_tokens": None,
                "full_accept_rows": 0,
                "full_reject_rows": 0,
                "current_full_accept_streak": 0,
                "max_full_accept_streak": 0,
                "repeated_scheduled_rows": 0,
                "suppressed_bonus_rows": 0,
                "top_scheduled_pairs": collections.Counter(),
            },
        )

        draft = int(row.get("num_draft_tokens") or 0)
        accepted = int(row.get("num_accepted") or 0)
        rejected = int(row.get("num_rejected") or 0)
        ts = row.get("ts")
        output_tokens = row.get("num_output_tokens")
        if output_tokens is None:
            state = row.get("request_state_before_reject_adjust")
            if isinstance(state, dict):
                output_tokens = state.get("num_output_tokens")
        scheduled = list(row.get("scheduled_spec_token_ids") or [])
        generated = list(row.get("generated_token_ids") or [])
        suppressed_bonus = row.get("suppressed_bonus_token_id")
        state_after_reject = row.get("request_state_after_reject_adjust")
        state_after_output = row.get("request_state_after_output_update")

        req["rows"] += 1
        req["draft_tokens"] += draft
        req["accepted"] += accepted
        req["rejected"] += rejected
        if ts is not None:
            req["first_ts"] = ts if req["first_ts"] is None else min(req["first_ts"], ts)
            req["last_ts"] = ts if req["last_ts"] is None else max(req["last_ts"], ts)
        if output_tokens is not None:
            req["min_output_tokens"] = (
                output_tokens
                if req["min_output_tokens"] is None
                else min(req["min_output_tokens"], output_tokens)
            )
            req["max_output_tokens"] = (
                output_tokens
                if req["max_output_tokens"] is None
                else max(req["max_output_tokens"], output_tokens)
            )

        accept_hist[str(accepted)] += 1
        if scheduled:
            pair_key = ",".join(str(tok) for tok in scheduled)
            scheduled_pairs[pair_key] += 1
            req["top_scheduled_pairs"][pair_key] += 1
            if len(set(scheduled)) == 1 and len(scheduled) > 1:
                repeated_scheduled_rows += 1
                req["repeated_scheduled_rows"] += 1
        if generated:
            generated_heads[str(generated[0])] += 1
        if suppressed_bonus is not None:
            suppressed_bonus_rows += 1
            req["suppressed_bonus_rows"] += 1
        if isinstance(state_after_reject, dict):
            req.setdefault("min_computed_after_reject", None)
            req.setdefault("max_computed_after_reject", None)
            computed_after_reject = state_after_reject.get("num_computed_tokens")
            if computed_after_reject is not None:
                req["min_computed_after_reject"] = (
                    computed_after_reject
                    if req["min_computed_after_reject"] is None
                    else min(req["min_computed_after_reject"], computed_after_reject)
                )
                req["max_computed_after_reject"] = (
                    computed_after_reject
                    if req["max_computed_after_reject"] is None
                    else max(req["max_computed_after_reject"], computed_after_reject)
                )
        if isinstance(state_after_output, dict):
            req.setdefault("min_tokens_after_output", None)
            req.setdefault("max_tokens_after_output", None)
            tokens_after_output = state_after_output.get("num_tokens")
            if tokens_after_output is not None:
                req["min_tokens_after_output"] = (
                    tokens_after_output
                    if req["min_tokens_after_output"] is None
                    else min(req["min_tokens_after_output"], tokens_after_output)
                )
                req["max_tokens_after_output"] = (
                    tokens_after_output
                    if req["max_tokens_after_output"] is None
                    else max(req["max_tokens_after_output"], tokens_after_output)
                )

        if draft and accepted == draft:
            full_accept_rows += 1
            req["full_accept_rows"] += 1
            req["current_full_accept_streak"] += 1
        else:
            req["current_full_accept_streak"] = 0
        if draft and accepted == 0:
            full_reject_rows += 1
            req["full_reject_rows"] += 1
        req["max_full_accept_streak"] = max(
            req["max_full_accept_streak"], req["current_full_accept_streak"]
        )
        max_full_accept_streak = max(max_full_accept_streak, req["max_full_accept_streak"])

    request_summaries = []
    for req in by_req.values():
        req = dict(req)
        req.pop("current_full_accept_streak", None)
        req["accept_rate"] = pct(req["accepted"], req["draft_tokens"])
        req["top_scheduled_pairs"] = [
            {"tokens": key, "count": count}
            for key, count in req["top_scheduled_pairs"].most_common(5)
        ]
        request_summaries.append(req)

    request_summaries.sort(
        key=lambda req: (req["draft_tokens"], req["accepted"], req["rows"]), reverse=True
    )
    total_draft = sum(int(row.get("num_draft_tokens") or 0) for row in rows)
    total_accepted = sum(int(row.get("num_accepted") or 0) for row in rows)
    total_rejected = sum(int(row.get("num_rejected") or 0) for row in rows)
    return {
        "path": str(path),
        "rows": len(rows),
        "malformed_rows": malformed,
        "requests": len(by_req),
        "draft_tokens": total_draft,
        "accepted": total_accepted,
        "rejected": total_rejected,
        "accept_rate_pct": pct(total_accepted, total_draft),
        "reject_rate_pct": pct(total_rejected, total_draft),
        "full_accept_rows": full_accept_rows,
        "full_reject_rows": full_reject_rows,
        "suppressed_bonus_rows": suppressed_bonus_rows,
        "full_accept_row_pct": pct(full_accept_rows, len(rows)),
        "full_reject_row_pct": pct(full_reject_rows, len(rows)),
        "suppressed_bonus_row_pct": pct(suppressed_bonus_rows, len(rows)),
        "repeated_scheduled_rows": repeated_scheduled_rows,
        "max_full_accept_streak": max_full_accept_streak,
        "accept_count_histogram": dict(sorted(accept_hist.items(), key=lambda kv: int(kv[0]))),
        "top_scheduled_pairs": [
            {"tokens": key, "count": count} for key, count in scheduled_pairs.most_common(10)
        ],
        "top_generated_first_tokens": [
            {"token": key, "count": count} for key, count in generated_heads.most_common(10)
        ],
        "request_ids": sorted(by_req),
        "top_requests_by_draft": request_summaries[:10],
        "top_requests_by_rejects": sorted(
            request_summaries,
            key=lambda req: (req["rejected"], req["draft_tokens"], req["rows"]),
            reverse=True,
        )[:10],
        "top_requests_by_full_accept_streak": sorted(
            request_summaries,
            key=lambda req: (req["max_full_accept_streak"], req["draft_tokens"]),
            reverse=True,
        )[:10],
    }


def summary_stat_from_artifact(data: dict[str, Any], key: str) -> dict[str, Any] | None:
    summary = data.get("summary")
    if isinstance(summary, dict) and isinstance(summary.get(key), dict):
        return summary[key]
    return None


def summarize_metric_artifact(label: str, path: Path) -> dict[str, Any]:
    data = load_json(path)
    records = list(data.get("records") or [])
    corrected = [
        float(record["tok_s_out_client_after_first_chunk_corrected"])
        for record in records
        if record.get("tok_s_out_client_after_first_chunk_corrected") is not None
    ]
    e2e = [
        float(record["tok_s_out_client_e2e"])
        for record in records
        if record.get("tok_s_out_client_e2e") is not None
    ]
    output_tokens = [
        int(record["output_tokens_client"])
        for record in records
        if record.get("output_tokens_client") is not None
    ]
    request_ids = [record.get("request_id") for record in records if record.get("request_id")]
    starts = [
        float(record["request_started_at_unix"])
        for record in records
        if record.get("request_started_at_unix") is not None
    ]
    finishes = [
        float(record["request_finished_at_unix"])
        for record in records
        if record.get("request_finished_at_unix") is not None
    ]
    texts = [record.get("text") for record in records if isinstance(record.get("text"), str)]
    text_hashes = []
    if texts:
        import hashlib

        text_hashes = [hashlib.sha256(text.encode("utf-8")).hexdigest() for text in texts]

    corrected_summary = summary_stat_from_artifact(
        data, "tok_s_out_client_after_first_chunk_corrected"
    )
    e2e_summary = summary_stat_from_artifact(data, "tok_s_out_client_e2e")

    return {
        "label": label,
        "path": str(path),
        "prompt_preset": data.get("prompt_preset"),
        "endpoint": data.get("endpoint"),
        "repeats": data.get("repeats"),
        "records": len(records),
        "has_request_ids": len(request_ids) == len(records) and bool(records),
        "request_ids": request_ids,
        "has_request_timestamps": (
            len(starts) == len(records) and len(finishes) == len(records) and bool(records)
        ),
        "request_window": (
            {"start": min(starts), "finish": max(finishes)}
            if starts and finishes
            else None
        ),
        "corrected_tok_s_mean": (
            corrected_summary.get("mean")
            if corrected_summary
            else mean_or_none(corrected)
        ),
        "corrected_tok_s_min": (
            corrected_summary.get("min")
            if corrected_summary
            else (min(corrected) if corrected else None)
        ),
        "corrected_tok_s_max": (
            corrected_summary.get("max")
            if corrected_summary
            else (max(corrected) if corrected else None)
        ),
        "e2e_tok_s_mean": e2e_summary.get("mean") if e2e_summary else mean_or_none(e2e),
        "output_tokens": output_tokens,
        "output_tokens_mean": mean_or_none([float(v) for v in output_tokens]),
        "output_tokens_min": min(output_tokens) if output_tokens else None,
        "output_tokens_max": max(output_tokens) if output_tokens else None,
        "has_full_text": len(texts) == len(records) and bool(records),
        "repeat_text_stable": (len(set(text_hashes)) == 1) if text_hashes else None,
        "text_hashes": text_hashes,
    }


def summarize_quality_artifact(label: str, path: Path) -> dict[str, Any]:
    data = load_json(path)
    repeat_case = data.get("repeat_case") or {}
    repeat_runs = repeat_case.get("runs") or []
    token_trace_cases = list(data.get("cases") or [])
    request_ids = [
        case.get("request_id") or case.get("response_id")
        for case in token_trace_cases
        if case.get("request_id") or case.get("response_id")
    ]
    starts = [
        float(case["request_started_at_unix"])
        for case in token_trace_cases
        if case.get("request_started_at_unix") is not None
    ]
    finishes = [
        float(case["request_finished_at_unix"])
        for case in token_trace_cases
        if case.get("request_finished_at_unix") is not None
    ]
    return {
        "label": label,
        "path": str(path),
        "pass_all": data.get("pass_all"),
        "baseline_match_all": data.get("baseline_match_all"),
        "exact_pass_count": sum(1 for case in data.get("exact_cases") or [] if case.get("pass")),
        "exact_case_count": len(data.get("exact_cases") or []),
        "repeat_pass": repeat_case.get("pass"),
        "repeat_unique_hashes": repeat_case.get("unique_hashes"),
        "repeat_repeats": repeat_case.get("repeats") or len(repeat_runs),
        "long_context_pass": (data.get("long_context_case") or {}).get("pass"),
        "token_trace_cases": len(token_trace_cases),
        "has_request_ids": len(request_ids) == len(token_trace_cases) and bool(token_trace_cases),
        "request_ids": request_ids,
        "has_request_timestamps": (
            len(starts) == len(token_trace_cases)
            and len(finishes) == len(token_trace_cases)
            and bool(token_trace_cases)
        ),
        "request_window": (
            {"start": min(starts), "finish": max(finishes)}
            if starts and finishes
            else None
        ),
    }


def join_stats(
    trace_ids: list[str], artifact_ids: list[str]
) -> dict[str, Any]:
    exact = sorted(set(trace_ids).intersection(artifact_ids))
    prefix_matches: list[dict[str, str]] = []
    for trace_id in trace_ids:
        matches = [
            artifact_id
            for artifact_id in artifact_ids
            if trace_id.startswith(artifact_id + "-")
            or artifact_id.startswith(trace_id + "-")
        ]
        if len(matches) == 1:
            prefix_matches.append({
                "trace_id": trace_id,
                "artifact_id": matches[0],
            })
    return {
        "exact_matches": exact,
        "prefix_matches": prefix_matches,
        "exact_match_count": len(exact),
        "prefix_match_count": len(prefix_matches),
    }


def compute_joinability(
    traces: list[dict[str, Any]],
    metric_artifacts: list[dict[str, Any]],
    quality_artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    trace_ids = sorted({
        req_id
        for trace in traces
        for req_id in trace.get("request_ids", [])
        if req_id
    })
    artifact_ids = sorted({
        req_id
        for artifact in [*metric_artifacts, *quality_artifacts]
        for req_id in artifact.get("request_ids", [])
        if req_id
    })
    stats = join_stats(trace_ids, artifact_ids)
    timestamp_window_join_possible = any(
        item.get("has_request_timestamps") for item in [*metric_artifacts, *quality_artifacts]
    )
    request_id_join_possible = bool(stats["exact_match_count"] or stats["prefix_match_count"])
    if stats["exact_match_count"]:
        note = "Trace rows can be joined to artifacts by exact request id."
    elif stats["prefix_match_count"]:
        note = (
            "Trace rows can be joined to artifacts by request-id prefix; "
            "scheduler ids append an internal suffix."
        )
    elif artifact_ids:
        note = (
            "Artifacts store request ids, but no trace request ids matched. "
            "Check whether the trace and artifact came from the same run."
        )
    else:
        note = (
            "Artifacts do not store request ids. Re-run metrics with current "
            "scripts before attributing trace rows to exact prompts."
        )
    return {
        "request_id_join_possible": request_id_join_possible,
        "exact_request_id_join_possible": bool(stats["exact_match_count"]),
        "prefix_request_id_join_possible": bool(stats["prefix_match_count"]),
        "timestamp_window_join_possible": timestamp_window_join_possible,
        "trace_request_count": len(trace_ids),
        "artifact_request_count": len(artifact_ids),
        "exact_match_count": stats["exact_match_count"],
        "prefix_match_count": stats["prefix_match_count"],
        "prefix_matches": stats["prefix_matches"],
        "note": note,
    }


def compare_metric_pairs(metric_summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_label = {item["label"]: item for item in metric_summaries}
    comparisons = []
    for label, candidate in by_label.items():
        for prefix in ("ngram2-", "candidate-"):
            if not label.startswith(prefix):
                continue
            suffix = label.removeprefix(prefix)
            baseline = by_label.get(f"accepted-{suffix}") or by_label.get(f"baseline-{suffix}")
            if not baseline:
                continue
            base_speed = baseline.get("corrected_tok_s_mean")
            cand_speed = candidate.get("corrected_tok_s_mean")
            delta = None
            if isinstance(base_speed, (int, float)) and isinstance(cand_speed, (int, float)):
                delta = pct(cand_speed - base_speed, base_speed)
            same_tokens = (
                baseline.get("output_tokens") == candidate.get("output_tokens")
                if baseline.get("output_tokens") and candidate.get("output_tokens")
                else None
            )
            comparisons.append(
                {
                    "baseline": baseline["label"],
                    "candidate": candidate["label"],
                    "baseline_corrected_tok_s": base_speed,
                    "candidate_corrected_tok_s": cand_speed,
                    "delta_pct": delta,
                    "same_output_token_counts": same_tokens,
                    "baseline_output_tokens": baseline.get("output_tokens"),
                    "candidate_output_tokens": candidate.get("output_tokens"),
                    "candidate_has_request_ids": candidate.get("has_request_ids"),
                    "candidate_has_request_timestamps": candidate.get("has_request_timestamps"),
                }
            )
    return comparisons


def render_markdown(summary: dict[str, Any]) -> str:
    lines = ["# Qwen3.6 Spec Trace Summary", ""]
    for trace in summary["traces"]:
        lines.extend(
            [
                f"## Trace: `{trace['path']}`",
                "",
                (
                    f"- rows `{trace['rows']}`, requests `{trace['requests']}`, "
                    f"drafts `{trace['draft_tokens']}`, accepted `{trace['accepted']}`, "
                    f"rejected `{trace['rejected']}`, accept rate "
                    f"`{trace['accept_rate_pct']:.2f}%`"
                    if trace["accept_rate_pct"] is not None
                    else "- no draft tokens"
                ),
                (
                    f"- full accept rows `{trace['full_accept_rows']}` "
                    f"(`{trace['full_accept_row_pct']:.2f}%`), full reject rows "
                    f"`{trace['full_reject_rows']}` (`{trace['full_reject_row_pct']:.2f}%`)"
                    if trace["full_accept_row_pct"] is not None
                    else "- no rows"
                ),
                (
                    f"- suppressed bonus rows `{trace['suppressed_bonus_rows']}` "
                    f"(`{trace['suppressed_bonus_row_pct']:.2f}%`)"
                    if trace["suppressed_bonus_row_pct"] is not None
                    else "- no suppressed bonus rows"
                ),
                f"- max full-accept streak `{trace['max_full_accept_streak']}`",
                f"- repeated scheduled rows `{trace['repeated_scheduled_rows']}`",
                "",
                "| top request | drafts | accepted | rejected | accept rate | max full-accept streak |",
                "| --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for req in trace["top_requests_by_draft"][:5]:
            rate = req["accept_rate"]
            rate_text = "" if rate is None or math.isnan(rate) else f"{rate:.2f}%"
            lines.append(
                f"| `{req['req_id']}` | {req['draft_tokens']} | {req['accepted']} | "
                f"{req['rejected']} | {rate_text} | {req['max_full_accept_streak']} |"
            )
        lines.append("")

    if summary["metric_artifacts"]:
        lines.extend(
            [
                "## Metric Artifacts",
                "",
                "| label | preset | corrected tok/s | output tokens | request IDs | timestamps |",
                "| --- | --- | ---: | --- | --- | --- |",
            ]
        )
        for item in summary["metric_artifacts"]:
            speed = item.get("corrected_tok_s_mean")
            speed_text = "" if speed is None else f"{speed:.2f}"
            lines.append(
                f"| `{item['label']}` | `{item.get('prompt_preset')}` | {speed_text} | "
                f"{item.get('output_tokens')} | {item.get('has_request_ids')} | "
                f"{item.get('has_request_timestamps')} |"
            )
        lines.append("")

    if summary["metric_comparisons"]:
        lines.extend(
            [
                "## Metric Comparisons",
                "",
                "| candidate | baseline | delta | same output-token counts |",
                "| --- | --- | ---: | --- |",
            ]
        )
        for item in summary["metric_comparisons"]:
            delta = item.get("delta_pct")
            delta_text = "" if delta is None else f"{delta:+.2f}%"
            lines.append(
                f"| `{item['candidate']}` | `{item['baseline']}` | {delta_text} | "
                f"{item.get('same_output_token_counts')} |"
            )
        lines.append("")

    if summary["quality_artifacts"]:
        lines.extend(
            [
                "## Quality Artifacts",
                "",
                "| label | pass all | baseline match | repeat pass | repeat unique hashes | long context |",
                "| --- | --- | --- | --- | ---: | --- |",
            ]
        )
        for item in summary["quality_artifacts"]:
            lines.append(
                f"| `{item['label']}` | {item.get('pass_all')} | "
                f"{item.get('baseline_match_all')} | {item.get('repeat_pass')} | "
                f"{item.get('repeat_unique_hashes')} | {item.get('long_context_pass')} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Joinability",
            "",
            f"- exact request-id join possible: `{summary['joinability']['request_id_join_possible']}`",
            f"- exact request-id matches: `{summary['joinability']['exact_match_count']}`",
            f"- prefix request-id matches: `{summary['joinability']['prefix_match_count']}`",
            f"- timestamp-window join possible: `{summary['joinability']['timestamp_window_join_possible']}`",
            f"- note: {summary['joinability']['note']}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-jsonl", action="append", default=[])
    parser.add_argument("--metric-json", action="append", default=[], help="label=path")
    parser.add_argument("--quality-json", action="append", default=[], help="label=path")
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md")
    args = parser.parse_args()

    traces = [summarize_trace(Path(path)) for path in args.trace_jsonl]
    metric_artifacts = [
        summarize_metric_artifact(label, path)
        for label, path in (parse_label_path(value) for value in args.metric_json)
    ]
    quality_artifacts = [
        summarize_quality_artifact(label, path)
        for label, path in (parse_label_path(value) for value in args.quality_json)
    ]
    joinability = compute_joinability(traces, metric_artifacts, quality_artifacts)

    summary = {
        "traces": traces,
        "metric_artifacts": metric_artifacts,
        "metric_comparisons": compare_metric_pairs(metric_artifacts),
        "quality_artifacts": quality_artifacts,
        "joinability": joinability,
    }

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2) + "\n")
    if args.out_md:
        out_md = Path(args.out_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(summary) + "\n")
    print(json.dumps(summary["joinability"], indent=2))
    for trace in traces:
        print(
            f"{trace['path']}: accept={trace['accept_rate_pct']:.2f}% "
            f"rows={trace['rows']} requests={trace['requests']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
