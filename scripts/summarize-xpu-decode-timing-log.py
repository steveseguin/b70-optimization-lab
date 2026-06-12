#!/usr/bin/env python3
"""Summarize vLLM XPU decode timing log lines."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path


SAMPLE_RE = re.compile(
    r"\[vllm-xpu-timing\]\s+rank=(?P<rank>\d+)\s+"
    r"label=(?P<label>.+?)\s+count=(?P<count>\d+)\s+last_ms=(?P<last_ms>[0-9.]+)"
)
SUMMARY_RE = re.compile(
    r"\[vllm-xpu-timing-summary\]\s+rank=(?P<rank>\d+)\s+"
    r"label=(?P<label>.+?)\s+count=(?P<count>\d+)\s+"
    r"total_ms=(?P<total_ms>[0-9.]+)\s+avg_ms=(?P<avg_ms>[0-9.]+)\s+"
    r"max_ms=(?P<max_ms>[0-9.]+)"
)
STEP_RE = re.compile(r"\[vllm-xpu-timing-step\]\s+(?P<payload>\{.*\})")
ENGINE_STEP_RE = re.compile(r"\[vllm-xpu-engine-step\]\s+(?P<payload>\{.*\})")
EXECUTOR_RPC_RE = re.compile(
    r"\[vllm-xpu-executor-rpc\]\s+(?P<payload>\{.*\})"
)
WORKER_RPC_RE = re.compile(r"\[vllm-xpu-worker-rpc\]\s+(?P<payload>\{.*\})")
WORKER_OUTPUT_RE = re.compile(
    r"\[vllm-xpu-worker-output\]\s+(?P<payload>\{.*\})"
)
POST_RE = re.compile(r'POST\s+/v1/(?:completions|chat/completions)\s+HTTP/\d(?:\.\d)?"\s+200')


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * pct
    lower = int(pos)
    upper = min(lower + 1, len(ordered) - 1)
    frac = pos - lower
    return ordered[lower] * (1.0 - frac) + ordered[upper] * frac


def summarize_metric_values(values: list[float]) -> dict[str, float | None]:
    return {
        "mean": statistics.fmean(values) if values else None,
        "median": statistics.median(values) if values else None,
        "p90": percentile(values, 0.90),
        "p99": percentile(values, 0.99),
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }


def summarize_samples(samples: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for sample in samples:
        grouped.setdefault(sample["label"], []).append(sample)

    rows = []
    for label, items in grouped.items():
        values = [float(item["last_ms"]) for item in items]
        counts = [int(item["count"]) for item in items]
        rows.append(
            {
                "label": label,
                "sample_count": len(items),
                "first_count": min(counts),
                "last_count": max(counts),
                "mean_last_ms": statistics.fmean(values),
                "median_last_ms": statistics.median(values),
                "p90_last_ms": percentile(values, 0.90),
                "p99_last_ms": percentile(values, 0.99),
                "min_last_ms": min(values),
                "max_last_ms": max(values),
            }
        )
    rows.sort(key=lambda row: row["mean_last_ms"], reverse=True)
    return rows


def summarize_steps(steps: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for step in steps:
        for row in step.get("summary_by_total_ms", []):
            grouped.setdefault(row["label"], []).append(row)

    rows = []
    for label, items in grouped.items():
        totals = [float(item["total_ms"]) for item in items]
        counts = [int(item["count"]) for item in items]
        avg_per_call = [float(item["avg_ms"]) for item in items]
        maxes = [float(item["max_ms"]) for item in items]
        rows.append(
            {
                "label": label,
                "step_count": len(items),
                "call_count": sum(counts),
                "mean_total_ms_per_step": statistics.fmean(totals),
                "median_total_ms_per_step": statistics.median(totals),
                "p90_total_ms_per_step": percentile(totals, 0.90),
                "max_total_ms_per_step": max(totals),
                "mean_avg_ms_per_call": statistics.fmean(avg_per_call),
                "max_ms": max(maxes),
            }
        )
    rows.sort(key=lambda row: row["mean_total_ms_per_step"], reverse=True)
    return rows


def summarize_steps_by_rank_label(steps: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict]] = {}
    for step in steps:
        for row in step.get("summary_by_total_ms", []):
            key = (str(row.get("rank", "")), str(row.get("label", "")))
            grouped.setdefault(key, []).append(row)

    rows = []
    for (rank, label), items in grouped.items():
        totals = [float(item["total_ms"]) for item in items]
        counts = [int(item["count"]) for item in items]
        avg_per_call = [float(item["avg_ms"]) for item in items]
        maxes = [float(item["max_ms"]) for item in items]
        rows.append(
            {
                "rank": rank,
                "label": label,
                "step_count": len(items),
                "call_count": sum(counts),
                "mean_total_ms_per_step": statistics.fmean(totals),
                "median_total_ms_per_step": statistics.median(totals),
                "p90_total_ms_per_step": percentile(totals, 0.90),
                "max_total_ms_per_step": max(totals),
                "mean_avg_ms_per_call": statistics.fmean(avg_per_call),
                "max_ms": max(maxes),
            }
        )
    rows.sort(
        key=lambda row: (row["mean_total_ms_per_step"], row["rank"]),
        reverse=True,
    )
    return rows


def _as_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _histogram_from_values(values: object) -> dict[str, int]:
    histogram: dict[str, int] = {}
    if not isinstance(values, list):
        return histogram
    for value in values:
        key = str(_as_int(value))
        histogram[key] = histogram.get(key, 0) + 1
    return histogram


def _normalize_histogram(value: object) -> dict[str, int]:
    if isinstance(value, dict):
        histogram: dict[str, int] = {}
        for key, count in value.items():
            histogram[str(key)] = _as_int(count)
        return histogram
    return {}


def _merge_histogram(target: dict[str, int], value: dict[str, int]) -> None:
    for key, count in value.items():
        target[key] = target.get(key, 0) + count


def summarize_steps_by_bucket(steps: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for step in steps:
        metadata = step.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}

        scheduled_token_histogram = _normalize_histogram(
            metadata.get("scheduled_token_histogram")
        )
        if not scheduled_token_histogram:
            scheduled_token_histogram = _histogram_from_values(
                metadata.get("scheduled_token_counts")
            )

        scheduled_spec_histogram = _normalize_histogram(
            metadata.get("scheduled_spec_histogram")
        )
        if not scheduled_spec_histogram:
            scheduled_spec_histogram = _histogram_from_values(
                metadata.get("scheduled_spec_lengths")
            )

        spec_lengths = metadata.get("scheduled_spec_lengths")
        max_spec_from_lengths = 0
        if isinstance(spec_lengths, list) and spec_lengths:
            max_spec_from_lengths = max(_as_int(value) for value in spec_lengths)

        group = {
            "status": str(step.get("status", "")),
            "cudagraph_mode": str(metadata.get("cudagraph_mode", "")),
            "skip_compiled": _as_bool(metadata.get("skip_compiled")),
            "should_ubatch": _as_bool(metadata.get("should_ubatch")),
            "use_spec_decode": _as_bool(metadata.get("use_spec_decode")),
            "is_pure_decode": _as_bool(metadata.get("is_pure_decode")),
            "decode_bucket": metadata.get("decode_bucket"),
            "max_num_scheduled_tokens": _as_int(
                metadata.get("max_num_scheduled_tokens")
            ),
            "max_scheduled_spec_tokens": _as_int(
                metadata.get("max_scheduled_spec_tokens"),
                default=max_spec_from_lengths,
            ),
            "num_reqs": _as_int(metadata.get("num_reqs")),
            "decode_req_count": _as_int(metadata.get("decode_req_count")),
            "prefill_req_count": _as_int(metadata.get("prefill_req_count")),
            "num_tokens_unpadded": _as_int(metadata.get("num_tokens_unpadded")),
            "num_tokens_padded": _as_int(metadata.get("num_tokens_padded")),
            "batch_desc_num_tokens": _as_int(metadata.get("batch_desc_num_tokens")),
            "batch_desc_num_reqs": metadata.get("batch_desc_num_reqs"),
        }
        key = json.dumps(group, sort_keys=True, separators=(",", ":"))
        entry = grouped.setdefault(
            key,
            {
                "group": group,
                "step_count": 0,
                "first_step": step.get("step"),
                "last_step": step.get("step"),
                "first_line": step.get("line"),
                "last_line": step.get("line"),
                "scheduled_token_histogram_total": {},
                "scheduled_spec_histogram_total": {},
                "model_forward_ms": [],
                "visible_timed_ms": [],
                "top_labels": {},
            },
        )
        entry["step_count"] += 1
        entry["last_step"] = step.get("step")
        entry["last_line"] = step.get("line")
        _merge_histogram(
            entry["scheduled_token_histogram_total"], scheduled_token_histogram
        )
        _merge_histogram(
            entry["scheduled_spec_histogram_total"], scheduled_spec_histogram
        )

        visible_total = 0.0
        model_forward = None
        for row in step.get("summary_by_total_ms", []):
            label = row.get("label")
            total_ms = float(row.get("total_ms", 0.0))
            visible_total += total_ms
            if label == "gpu_model_runner.model_forward":
                model_forward = total_ms
            if label:
                label_entry = entry["top_labels"].setdefault(label, [])
                label_entry.append(total_ms)

        entry["visible_timed_ms"].append(visible_total)
        if model_forward is not None:
            entry["model_forward_ms"].append(model_forward)

    rows = []
    for entry in grouped.values():
        model_forward_values = entry.pop("model_forward_ms")
        visible_values = entry.pop("visible_timed_ms")
        top_labels = entry.pop("top_labels")
        label_rows = []
        for label, values in top_labels.items():
            label_rows.append(
                {
                    "label": label,
                    "mean_total_ms": statistics.fmean(values),
                    "median_total_ms": statistics.median(values),
                    "p90_total_ms": percentile(values, 0.90),
                    "max_total_ms": max(values),
                }
            )
        label_rows.sort(key=lambda row: row["mean_total_ms"], reverse=True)

        row = {
            **entry,
            "mean_visible_timed_ms": statistics.fmean(visible_values)
            if visible_values
            else None,
            "median_visible_timed_ms": statistics.median(visible_values)
            if visible_values
            else None,
            "p90_visible_timed_ms": percentile(visible_values, 0.90),
            "mean_model_forward_ms": statistics.fmean(model_forward_values)
            if model_forward_values
            else None,
            "median_model_forward_ms": statistics.median(model_forward_values)
            if model_forward_values
            else None,
            "p90_model_forward_ms": percentile(model_forward_values, 0.90),
            "max_model_forward_ms": max(model_forward_values)
            if model_forward_values
            else None,
            "top_labels_by_mean_total_ms": label_rows[:8],
        }
        rows.append(row)

    rows.sort(
        key=lambda row: (
            row["mean_model_forward_ms"]
            if row["mean_model_forward_ms"] is not None
            else -1.0
        ),
        reverse=True,
    )
    return rows


def summarize_engine_steps(engine_steps: list[dict]) -> dict[str, object]:
    if not engine_steps:
        return {
            "step_count": 0,
            "status_counts": {},
            "total_ms": {},
            "accounted_region_ms": {},
            "unaccounted_ms": {},
            "regions_by_mean_elapsed_ms": [],
        }

    status_counts: dict[str, int] = {}
    totals = []
    accounted = []
    unaccounted = []
    regions: dict[str, list[dict]] = {}
    for step in engine_steps:
        status = str(step.get("status", ""))
        status_counts[status] = status_counts.get(status, 0) + 1
        totals.append(float(step.get("total_ms", 0.0)))
        accounted.append(float(step.get("accounted_region_ms", 0.0)))
        unaccounted.append(float(step.get("unaccounted_ms", 0.0)))
        for region in step.get("regions", []):
            label = region.get("label")
            if label:
                regions.setdefault(str(label), []).append(region)

    region_rows = []
    for label, items in regions.items():
        elapsed_values = [float(item.get("elapsed_ms", 0.0)) for item in items]
        start_offsets = [float(item.get("start_offset_ms", 0.0)) for item in items]
        row = {
            "label": label,
            "count": len(items),
            "elapsed_ms": summarize_metric_values(elapsed_values),
            "start_offset_ms": summarize_metric_values(start_offsets),
        }
        region_rows.append(row)
    region_rows.sort(
        key=lambda row: row["elapsed_ms"]["mean"]
        if row["elapsed_ms"]["mean"] is not None
        else -1.0,
        reverse=True,
    )

    return {
        "step_count": len(engine_steps),
        "status_counts": status_counts,
        "total_ms": summarize_metric_values(totals),
        "accounted_region_ms": summarize_metric_values(accounted),
        "unaccounted_ms": summarize_metric_values(unaccounted),
        "regions_by_mean_elapsed_ms": region_rows,
    }


def summarize_engine_steps_by_bucket(engine_steps: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for step in engine_steps:
        metadata = step.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        group = {
            "label": step.get("label"),
            "status": step.get("status"),
            "return_kind": metadata.get("return_kind"),
            "num_reqs": metadata.get("num_reqs", metadata.get("popped_num_reqs")),
            "total_num_scheduled_tokens": metadata.get(
                "total_num_scheduled_tokens",
                metadata.get("popped_total_num_scheduled_tokens"),
            ),
            "decode_bucket": metadata.get(
                "decode_bucket", metadata.get("popped_decode_bucket")
            ),
            "is_pure_decode": metadata.get(
                "is_pure_decode", metadata.get("popped_is_pure_decode")
            ),
            "scheduled_num_reqs": metadata.get("scheduled_num_reqs"),
            "popped_num_reqs": metadata.get("popped_num_reqs"),
            "batch_queue_len_start": metadata.get("batch_queue_len_start"),
            "batch_queue_len_end": metadata.get("batch_queue_len_end"),
        }
        key = json.dumps(group, sort_keys=True, separators=(",", ":"))
        entry = grouped.setdefault(
            key,
            {
                "group": group,
                "step_count": 0,
                "first_step": step.get("step"),
                "last_step": step.get("step"),
                "first_line": step.get("line"),
                "last_line": step.get("line"),
                "total_ms": [],
                "unaccounted_ms": [],
                "regions": {},
            },
        )
        entry["step_count"] += 1
        entry["last_step"] = step.get("step")
        entry["last_line"] = step.get("line")
        entry["total_ms"].append(float(step.get("total_ms", 0.0)))
        entry["unaccounted_ms"].append(float(step.get("unaccounted_ms", 0.0)))
        for region in step.get("regions", []):
            label = region.get("label")
            if label:
                entry["regions"].setdefault(str(label), []).append(
                    float(region.get("elapsed_ms", 0.0))
                )

    rows = []
    for entry in grouped.values():
        totals = entry.pop("total_ms")
        unaccounted = entry.pop("unaccounted_ms")
        regions = entry.pop("regions")
        region_rows = []
        for label, values in regions.items():
            region_rows.append(
                {
                    "label": label,
                    "mean_elapsed_ms": statistics.fmean(values),
                    "median_elapsed_ms": statistics.median(values),
                    "p90_elapsed_ms": percentile(values, 0.90),
                    "max_elapsed_ms": max(values),
                }
            )
        region_rows.sort(key=lambda row: row["mean_elapsed_ms"], reverse=True)
        rows.append(
            {
                **entry,
                "mean_total_ms": statistics.fmean(totals),
                "median_total_ms": statistics.median(totals),
                "p90_total_ms": percentile(totals, 0.90),
                "max_total_ms": max(totals),
                "mean_unaccounted_ms": statistics.fmean(unaccounted),
                "top_regions_by_mean_elapsed_ms": region_rows[:8],
            }
        )

    rows.sort(key=lambda row: row["mean_total_ms"], reverse=True)
    return rows


def summarize_rpc_events(events: list[dict], group_fields: list[str]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for event in events:
        group = {field: event.get(field) for field in group_fields}
        key = json.dumps(group, sort_keys=True, separators=(",", ":"))
        entry = grouped.setdefault(
            key,
            {
                "group": group,
                "event_count": 0,
                "first_line": event.get("line"),
                "last_line": event.get("line"),
                "first_call_id": event.get("call_id"),
                "last_call_id": event.get("call_id"),
                "metrics": {},
            },
        )
        entry["event_count"] += 1
        entry["last_line"] = event.get("line")
        entry["last_call_id"] = event.get("call_id")
        for key2, value in event.items():
            if key2 in group_fields or key2 in {
                "line",
                "call_id",
                "scheduler",
                "response_dequeue_rows",
            }:
                continue
            if isinstance(value, bool):
                continue
            if isinstance(value, int | float):
                entry["metrics"].setdefault(key2, []).append(float(value))

    rows = []
    for entry in grouped.values():
        metrics = entry.pop("metrics")
        rows.append(
            {
                **entry,
                "metric_summaries": {
                    key: summarize_metric_values(values)
                    for key, values in sorted(metrics.items())
                },
            }
        )
    rows.sort(
        key=lambda row: (
            row["group"].get("method") or "",
            str(row["group"].get("event") or row["group"].get("rank") or ""),
        )
    )
    return rows


def summarize_rpc_calls(
    executor_rpc_events: list[dict],
    worker_rpc_events: list[dict],
    worker_output_events: list[dict],
) -> dict[str, object]:
    calls: dict[int, dict] = {}

    def call_for(event: dict) -> dict | None:
        call_id = event.get("call_id")
        if not isinstance(call_id, int):
            return None
        return calls.setdefault(
            call_id,
            {
                "call_id": call_id,
                "method": event.get("method"),
                "scheduler": event.get("scheduler") or {},
                "executor": {},
                "workers": [],
                "outputs": [],
            },
        )

    for event in executor_rpc_events:
        call = call_for(event)
        if call is None:
            continue
        if event.get("method"):
            call["method"] = event.get("method")
        if event.get("scheduler"):
            call["scheduler"] = event.get("scheduler")
        event_name = event.get("event")
        if event_name:
            call["executor"][event_name] = event

    for event in worker_rpc_events:
        call = call_for(event)
        if call is None:
            continue
        call["workers"].append(event)

    for event in worker_output_events:
        call = call_for(event)
        if call is None:
            continue
        call["outputs"].append(event)

    joined = []
    for call in sorted(calls.values(), key=lambda row: row["call_id"]):
        workers = call["workers"]
        outputs = call["outputs"]
        executor = call["executor"]
        response = executor.get("response_dequeue") or {}
        enqueue = executor.get("enqueue") or {}
        worker_func = [
            float(row["func_ms"])
            for row in workers
            if isinstance(row.get("func_ms"), int | float)
        ]
        worker_after = [
            float(row["worker_after_dequeue_ms"])
            for row in workers
            if isinstance(row.get("worker_after_dequeue_ms"), int | float)
        ]
        driver_to_worker = [
            float(row["driver_enqueue_to_dequeue_ms"])
            for row in workers
            if isinstance(row.get("driver_enqueue_to_dequeue_ms"), int | float)
        ]
        output_enqueue = [
            float(row["enqueue_ms"])
            for row in outputs
            if isinstance(row.get("enqueue_ms"), int | float)
        ]
        response_wait = response.get("response_wait_ms")
        max_worker_func = max(worker_func) if worker_func else None
        min_worker_func = min(worker_func) if worker_func else None
        max_worker_after = max(worker_after) if worker_after else None
        row = {
            "call_id": call["call_id"],
            "method": call["method"],
            "scheduler": call["scheduler"],
            "executor_enqueue_ms": enqueue.get("enqueue_ms"),
            "executor_response_wait_ms": response_wait,
            "worker_count": len(workers),
            "output_event_count": len(outputs),
            "max_worker_func_ms": max_worker_func,
            "min_worker_func_ms": min_worker_func,
            "worker_func_skew_ms": (
                max_worker_func - min_worker_func
                if max_worker_func is not None and min_worker_func is not None
                else None
            ),
            "max_worker_after_dequeue_ms": max_worker_after,
            "max_driver_enqueue_to_worker_dequeue_ms": max(driver_to_worker)
            if driver_to_worker
            else None,
            "max_output_enqueue_ms": max(output_enqueue)
            if output_enqueue
            else None,
        }
        if isinstance(response_wait, int | float) and max_worker_func is not None:
            row["response_wait_minus_max_worker_func_ms"] = (
                float(response_wait) - max_worker_func
            )
        if isinstance(response_wait, int | float) and max_worker_after is not None:
            row["response_wait_minus_max_worker_after_dequeue_ms"] = (
                float(response_wait) - max_worker_after
            )
        joined.append(row)

    by_method: dict[str, dict[str, list[float]]] = {}
    for row in joined:
        method = str(row.get("method") or "")
        entry = by_method.setdefault(method, {})
        for key, value in row.items():
            if key in {"call_id", "method", "scheduler"} or isinstance(value, bool):
                continue
            if isinstance(value, int | float):
                entry.setdefault(key, []).append(float(value))

    summary_rows = []
    for method, metrics in by_method.items():
        summary_rows.append(
            {
                "method": method,
                "call_count": max((len(values) for values in metrics.values()), default=0),
                "metric_summaries": {
                    key: summarize_metric_values(values)
                    for key, values in sorted(metrics.items())
                },
            }
        )
    summary_rows.sort(key=lambda row: row["method"])

    return {
        "call_count": len(joined),
        "by_method": summary_rows,
        "calls": joined,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True, help="vLLM worker log file")
    parser.add_argument("--out", required=True, help="JSON summary output path")
    parser.add_argument(
        "--all-lines",
        action="store_true",
        help="include every timing sample and aggregate summary in the log",
    )
    parser.add_argument(
        "--include-raw",
        action="store_true",
        help="include raw matched sample and summary rows",
    )
    args = parser.parse_args()

    log_path = Path(args.log)
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()

    post_lines = [idx + 1 for idx, line in enumerate(lines) if POST_RE.search(line)]
    sample_start_line = 1
    sample_end_line = len(lines)
    summary_start_line = 1
    if post_lines and not args.all_lines:
        sample_start_line = post_lines[-2] + 1 if len(post_lines) >= 2 else 1
        sample_end_line = post_lines[-1]
        summary_start_line = post_lines[-1] + 1

    samples = []
    summaries = []
    steps = []
    engine_steps = []
    executor_rpc_events = []
    worker_rpc_events = []
    worker_output_events = []
    for idx, line in enumerate(lines, start=1):
        if sample_start_line <= idx <= sample_end_line:
            match = SAMPLE_RE.search(line)
            if match:
                samples.append(
                    {
                        "line": idx,
                        "rank": int(match.group("rank")),
                        "label": match.group("label"),
                        "count": int(match.group("count")),
                        "last_ms": float(match.group("last_ms")),
                    }
                )
                continue
        if idx >= summary_start_line:
            match = SUMMARY_RE.search(line)
        else:
            match = None
        if match:
            summaries.append(
                {
                    "line": idx,
                    "rank": int(match.group("rank")),
                    "label": match.group("label"),
                    "count": int(match.group("count")),
                    "total_ms": float(match.group("total_ms")),
                    "avg_ms": float(match.group("avg_ms")),
                    "max_ms": float(match.group("max_ms")),
                }
            )
        match = STEP_RE.search(line)
        if match and (args.all_lines or idx >= sample_start_line):
            try:
                payload = json.loads(match.group("payload"))
            except json.JSONDecodeError:
                continue
            payload["line"] = idx
            steps.append(payload)
        match = ENGINE_STEP_RE.search(line)
        if match and (args.all_lines or idx >= sample_start_line):
            try:
                payload = json.loads(match.group("payload"))
            except json.JSONDecodeError:
                continue
            payload["line"] = idx
            engine_steps.append(payload)
        match = EXECUTOR_RPC_RE.search(line)
        if match and (args.all_lines or idx >= sample_start_line):
            try:
                payload = json.loads(match.group("payload"))
            except json.JSONDecodeError:
                continue
            payload["line"] = idx
            executor_rpc_events.append(payload)
        match = WORKER_RPC_RE.search(line)
        if match and (args.all_lines or idx >= sample_start_line):
            try:
                payload = json.loads(match.group("payload"))
            except json.JSONDecodeError:
                continue
            payload["line"] = idx
            worker_rpc_events.append(payload)
        match = WORKER_OUTPUT_RE.search(line)
        if match and (args.all_lines or idx >= sample_start_line):
            try:
                payload = json.loads(match.group("payload"))
            except json.JSONDecodeError:
                continue
            payload["line"] = idx
            worker_output_events.append(payload)

    summary_rows = summarize_samples(samples)
    timing_summary = sorted(summaries, key=lambda row: row["total_ms"], reverse=True)
    step_summary = summarize_steps(steps)
    step_rank_label_summary = summarize_steps_by_rank_label(steps)
    step_bucket_summary = summarize_steps_by_bucket(steps)
    engine_step_summary = summarize_engine_steps(engine_steps)
    engine_step_bucket_summary = summarize_engine_steps_by_bucket(engine_steps)
    executor_rpc_summary = summarize_rpc_events(
        executor_rpc_events,
        ["event", "method", "output_rank"],
    )
    worker_rpc_summary = summarize_rpc_events(
        worker_rpc_events,
        ["method", "rank", "output_rank", "status"],
    )
    worker_output_summary = summarize_rpc_events(
        worker_output_events,
        ["event", "method", "rank", "status"],
    )
    rpc_call_summary = summarize_rpc_calls(
        executor_rpc_events,
        worker_rpc_events,
        worker_output_events,
    )
    payload = {
        "source_log": str(log_path),
        "line_count": len(lines),
        "post_lines": post_lines,
        "sample_start_line": sample_start_line,
        "sample_end_line": sample_end_line,
        "summary_start_line": summary_start_line,
        "sample_line_count": len(samples),
        "summary_line_count": len(timing_summary),
        "step_line_count": len(steps),
        "engine_step_line_count": len(engine_steps),
        "executor_rpc_line_count": len(executor_rpc_events),
        "worker_rpc_line_count": len(worker_rpc_events),
        "worker_output_line_count": len(worker_output_events),
        "samples_by_last_ms": summary_rows,
        "summary_by_total_ms": timing_summary,
        "step_summary_by_mean_total_ms": step_summary,
        "step_summary_by_rank_label": step_rank_label_summary,
        "step_summary_by_bucket": step_bucket_summary,
        "engine_step_summary": engine_step_summary,
        "engine_step_summary_by_bucket": engine_step_bucket_summary,
        "executor_rpc_summary": executor_rpc_summary,
        "worker_rpc_summary": worker_rpc_summary,
        "worker_output_summary": worker_output_summary,
        "rpc_call_summary": rpc_call_summary,
    }
    if args.include_raw:
        payload["raw_samples"] = samples
        payload["raw_summaries"] = summaries
        payload["raw_steps"] = steps
        payload["raw_engine_steps"] = engine_steps
        payload["raw_executor_rpc_events"] = executor_rpc_events
        payload["raw_worker_rpc_events"] = worker_rpc_events
        payload["raw_worker_output_events"] = worker_output_events

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
