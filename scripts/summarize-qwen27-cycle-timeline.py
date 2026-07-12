#!/usr/bin/env python3
"""Reconcile Qwen27 request, server, graph, speculation, and SYCL trace timing."""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


EVAL_RE = re.compile(r"\|\s+eval time =\s*([0-9.]+) ms /\s*(\d+) tokens")
PROMPT_RE = re.compile(r"\|\s+prompt eval time =\s*([0-9.]+) ms /\s*(\d+) tokens")
ACCEPT_RE = re.compile(
    r"draft acceptance =\s*([0-9.]+)\s*\(\s*(\d+) accepted /\s*(\d+) generated\), mean len =\s*([0-9.]+)"
)
GRAPH_SUMMARY_RE = re.compile(r"\[SYCL-GRAPH\].*summary[^\n]*")
CYCLE_LINE_RE = re.compile(r"\[SYCL-CYCLE\]\s+([^\n]+)")
CYCLE_KV_RE = re.compile(r"([a-z_]+)=([^\s]+)")
KV_RE = re.compile(r"([a-z_]+)=(\d+)")
TRACE_CALL_RE = re.compile(r"\b((?:ur|ze|zes|zel)[A-Z][A-Za-z0-9_]*)\b")
TRACE_DURATION_RE = re.compile(r"(?:duration|time)\s*[=:]\s*([0-9.]+)\s*(ns|us|ms|s)\b", re.I)


def stats(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"n": 0, "min": None, "median": None, "mean": None, "p90": None, "max": None}
    ordered = sorted(values)
    p90_i = min(len(ordered) - 1, math.ceil(0.9 * len(ordered)) - 1)
    return {
        "n": len(values),
        "min": ordered[0],
        "median": statistics.median(ordered),
        "mean": statistics.fmean(ordered),
        "p90": ordered[p90_i],
        "max": ordered[-1],
    }


def load_result(path: Path | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if path is None:
        return {}, []
    doc = json.loads(path.read_text())
    rows = doc.get("rows", [])
    per_request = []
    for row in rows:
        offsets = [float(x) for x in row.get("chunk_offsets_s", [])]
        gaps_ms = [(b - a) * 1000 for a, b in zip(offsets, offsets[1:])]
        # Multiple accepted tokens arrive nearly together. A 1 ms boundary
        # distinguishes network/JSON emission within a burst from model cycles.
        cycle_gaps = [x for x in gaps_ms if x >= 1.0]
        burst_sizes: list[int] = []
        if offsets:
            size = 1
            for gap in gaps_ms:
                if gap < 1.0:
                    size += 1
                else:
                    burst_sizes.append(size)
                    size = 1
            burst_sizes.append(size)
        elapsed_ms = float(row.get("elapsed_s", 0)) * 1000
        ttft_ms = float(row.get("ttft_s", 0)) * 1000
        post_ttft_ms = float(row.get("post_ttft_s", 0)) * 1000
        per_request.append({
            "prompt_index": row.get("prompt_index"),
            "prompt_id": row.get("prompt_id"),
            "prompt_tokens": row.get("prompt_tokens"),
            "completion_tokens": row.get("completion_tokens"),
            "cached_tokens": row.get("cached_tokens"),
            "elapsed_ms": elapsed_ms,
            "ttft_ms": ttft_ms,
            "post_ttft_ms": post_ttft_ms,
            "stream_cycle_gap_ms": stats(cycle_gaps),
            "stream_burst_size_tokens": stats([float(x) for x in burst_sizes]),
            "estimated_stream_cycles": len(burst_sizes),
            "tok_s_1_100_after_ttft": row.get("tok_s_1_100_after_ttft"),
        })
    summary = {
        "path": str(path),
        "requests": len(rows),
        "cached_tokens_all_zero": all(row.get("cached_tokens") == 0 for row in rows) if rows else None,
        "elapsed_ms": stats([x["elapsed_ms"] for x in per_request]),
        "ttft_ms": stats([x["ttft_ms"] for x in per_request]),
        "post_ttft_ms": stats([x["post_ttft_ms"] for x in per_request]),
        "stream_cycle_gap_ms": stats([
            gap
            for row in rows
            for gap in [
                (b - a) * 1000
                for a, b in zip(row.get("chunk_offsets_s", []), row.get("chunk_offsets_s", [])[1:])
                if (b - a) * 1000 >= 1.0
            ]
        ]),
        "stream_burst_size_tokens": stats([
            float(size)
            for request in per_request
            for size in _burst_sizes(rows[request["prompt_index"]].get("chunk_offsets_s", []))
        ]) if rows and all(isinstance(x.get("prompt_index"), int) and x["prompt_index"] < len(rows) for x in per_request) else {},
    }
    return summary, per_request


def _burst_sizes(offsets: list[float]) -> list[int]:
    if not offsets:
        return []
    out, size = [], 1
    for a, b in zip(offsets, offsets[1:]):
        if (b - a) * 1000 < 1.0:
            size += 1
        else:
            out.append(size)
            size = 1
    out.append(size)
    return out


def load_server_log(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    text = path.read_text(errors="replace")
    evals = [(float(ms), int(n)) for ms, n in EVAL_RE.findall(text)]
    prompts = [(float(ms), int(n)) for ms, n in PROMPT_RE.findall(text)]
    accepts = [(float(r), int(a), int(g), float(m)) for r, a, g, m in ACCEPT_RE.findall(text)]
    graph_lines = GRAPH_SUMMARY_RE.findall(text)
    graph = dict(KV_RE.findall(graph_lines[-1])) if graph_lines else {}
    cycle_rows: list[dict[str, Any]] = []
    for body in CYCLE_LINE_RE.findall(text):
        row: dict[str, Any] = {}
        for key, raw in CYCLE_KV_RE.findall(body):
            try:
                row[key] = float(raw) if "." in raw else int(raw)
            except ValueError:
                row[key] = raw
        cycle_rows.append(row)

    cycle_metrics = (
        "host_work_submit_us",
        "host_marker_submit_us",
        "host_sync_us",
        "host_total_us",
        "device_queue_us",
        "graph_queue_us",
        "graph_exec_us",
    )
    cycle_paths = Counter(str(row.get("path", "unknown")) for row in cycle_rows)
    cycle_timing = {
        "count": len(cycle_rows),
        "paths": dict(cycle_paths),
        "metrics": {
            metric: stats([
                float(row[metric])
                for row in cycle_rows
                if isinstance(row.get(metric), (int, float)) and float(row[metric]) >= 0
            ])
            for metric in cycle_metrics
        },
        "interpretation": (
            "Native timing is opt-in and serializes each measured graph_compute with marker barriers. "
            "host_work_submit_us is the ordinary host call's submission portion; host_sync_us is the "
            "diagnostic forced wait; device_queue_us is the in-order interval between marker events."
        ),
    }
    return {
        "path": str(path),
        "request_count_from_eval_lines": len(evals),
        "decode_ms": stats([x[0] for x in evals]),
        "decode_ms_per_emitted_token": stats([ms / n for ms, n in evals if n]),
        "prompt_ms": stats([x[0] for x in prompts]),
        "speculation": {
            "request_count": len(accepts),
            "accepted": sum(x[1] for x in accepts),
            "generated": sum(x[2] for x in accepts),
            "aggregate_acceptance": (
                sum(x[1] for x in accepts) / sum(x[2] for x in accepts)
                if sum(x[2] for x in accepts) else None
            ),
            "mean_accepted_length": stats([x[3] for x in accepts]),
        },
        "graph_counters": {key: int(value) for key, value in graph.items()},
        "native_cycle_timing": cycle_timing,
    }


def load_trace(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    calls: Counter[str] = Counter()
    durations_ms: dict[str, list[float]] = {}
    malformed_duration_lines = 0
    for line in path.read_text(errors="replace").splitlines():
        match = TRACE_CALL_RE.search(line)
        if not match:
            continue
        name = match.group(1)
        calls[name] += 1
        duration = TRACE_DURATION_RE.search(line)
        if duration:
            value, unit = float(duration.group(1)), duration.group(2).lower()
            scale = {"ns": 1e-6, "us": 1e-3, "ms": 1.0, "s": 1000.0}[unit]
            durations_ms.setdefault(name, []).append(value * scale)
        elif "duration" in line.lower():
            malformed_duration_lines += 1
    timed = {
        name: {"total_ms": sum(values), **stats(values)}
        for name, values in durations_ms.items()
    }
    return {
        "path": str(path),
        "format_note": "Call counts are reliable if trace is complete; duration attribution is emitted only when sycl-trace includes a recognized duration field.",
        "total_calls": sum(calls.values()),
        "calls_by_api": dict(calls.most_common()),
        "timed_calls": dict(sorted(timed.items(), key=lambda x: x[1]["total_ms"], reverse=True)),
        "malformed_duration_lines": malformed_duration_lines,
    }


def reconcile(result: dict[str, Any], server: dict[str, Any]) -> dict[str, Any]:
    request_elapsed = result.get("elapsed_ms", {}).get("median")
    decode = server.get("decode_ms", {}).get("median")
    ttft = result.get("ttft_ms", {}).get("median")
    prompt = server.get("prompt_ms", {}).get("median")
    out: dict[str, Any] = {}
    if request_elapsed is not None and decode is not None:
        out["median_request_minus_server_decode_ms"] = request_elapsed - decode
        out["warning"] = "This residual includes TTFT/prompt work, HTTP streaming, scheduling, and clock-boundary differences; it is not pure host overhead."
    if ttft is not None and request_elapsed is not None:
        out["median_request_minus_ttft_ms"] = request_elapsed - ttft
    if request_elapsed is not None and decode is not None and prompt is not None:
        out["median_request_minus_prompt_and_decode_ms"] = request_elapsed - prompt - decode
        out["prompt_plus_decode_note"] = "A near-zero value validates the request/server clocks in aggregate; it does not split device kernels from host work inside eval time."
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path)
    parser.add_argument("--server-log", type=Path)
    parser.add_argument("--sycl-trace", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--requests-out", type=Path)
    args = parser.parse_args()
    if not any((args.result, args.server_log, args.sycl_trace)):
        parser.error("provide at least one input")

    result, requests = load_result(args.result)
    server = load_server_log(args.server_log)
    doc = {
        "schema_version": 1,
        "result_timeline": result,
        "server_timeline": server,
        "sycl_trace": load_trace(args.sycl_trace),
        "reconciliation": reconcile(result, server),
        "limitations": [
            "Stream burst boundaries use a 1 ms heuristic and are cycle estimates, not device timestamps.",
            "llama.cpp eval time includes target, draft, sampling, synchronization, and host coordination.",
            "sycl-trace perturbs execution and must never supply headline throughput.",
            "No Level Zero hardware-counter profiler is installed; kernel occupancy and bandwidth remain unmeasured.",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n")
    if args.requests_out:
        args.requests_out.parent.mkdir(parents=True, exist_ok=True)
        args.requests_out.write_text("".join(json.dumps(row) + "\n" for row in requests))


if __name__ == "__main__":
    main()
