#!/usr/bin/env python3
"""Summarize rank-qualified gzipped Kineto traces for pure target decode.

The XPU event timeline can be offset from the host timeline on this stack.
Associate device events with an ``execute_context`` interval using the event's
host submission timestamp, while retaining the device event's own duration.

This is deliberately an offline postprocessor.  It does not import vLLM,
modify a launcher, contact an endpoint, or initialize an accelerator.
"""

from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter
import gzip
import json
import math
from pathlib import Path
import re
import statistics
from typing import Any, Iterable

try:
    import ijson
except ImportError as error:  # pragma: no cover - exercised by CLI environments
    ijson = None
    IJSON_IMPORT_ERROR = error
else:
    IJSON_IMPORT_ERROR = None


DEFAULT_CONTEXT = "execute_context_0(0)_generation_1(1)"
DEFAULT_EXPECTED_RANKS = (0, 1, 2, 3)
MAXIMUM_RANK_CONTEXT_START_SKEW_US = 50_000.0
DEVICE_CATEGORIES = frozenset(("kernel", "gpu_memcpy", "gpu_memset"))
COLLECTIVE_PREFIX = "collective_"
RANK_RE = re.compile(r"(?:^|[_.-])rank(?P<rank>[0-9]+)(?=[_.-]|$)")


class TraceContractError(RuntimeError):
    """The trace set does not satisfy the preregistered decode contract."""


def _require_ijson() -> None:
    if ijson is None:
        raise RuntimeError(
            "ijson is required to stream Kineto traces; run this tool with "
            "/home/steve/.venvs/vllm-xpu/bin/python"
        ) from IJSON_IMPORT_ERROR


def iter_events(path: Path) -> Iterable[dict[str, Any]]:
    """Stream trace events without expanding the gzip or JSON in memory."""

    _require_ijson()
    with gzip.open(path, "rb") as handle:
        yield from ijson.items(handle, "traceEvents.item")


def extract_rank(path: Path) -> int:
    match = RANK_RE.search(path.name)
    if match is None:
        raise TraceContractError(f"trace filename is not rank-qualified: {path}")
    return int(match.group("rank"))


def _float(value: Any, *, field: str, path: Path) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise TraceContractError(
            f"invalid {field}={value!r} in {path}"
        ) from error
    if not math.isfinite(parsed):
        raise TraceContractError(f"non-finite {field}={value!r} in {path}")
    return parsed


def _event_anchor(args: dict[str, Any]) -> tuple[float | None, str | None]:
    for field in ("submitted", "appended", "sycl_enqk_begin"):
        value = args.get(field)
        if value is None:
            continue
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(parsed):
            return parsed, field
    return None, None


def _interval_index(
    starts: list[float], intervals: list[tuple[float, float]], timestamp: float
) -> int | None:
    index = bisect_right(starts, timestamp) - 1
    if index >= 0 and timestamp < intervals[index][1]:
        return index
    return None


def _summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"mean": 0.0, "median": 0.0, "min": 0.0, "max": 0.0, "samples": []}
    return {
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "samples": values,
    }


def _json_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def classify_device_event(
    name: str, category: str, operator_name: str | None
) -> str:
    """Apply conservative, inspectable Qwen target-decode classifications."""

    if category in ("gpu_memcpy", "gpu_memset"):
        return "device_memory_operation"

    text = f"{name} {operator_name or ''}".lower()

    if "reduce_scatter" in text or "reduce-scatter" in text:
        return "collective_reduce_scatter"
    if "allgather" in text or "all_gather" in text or "all-gather" in text:
        return "collective_allgather"
    if "allreduce" in text or "all_reduce" in text or "all-reduce" in text:
        return "collective_allreduce"
    if "oneccl" in text or re.search(r"(?:^|[^a-z])ccl(?:[^a-z]|$)", text):
        return "collective_other"

    if "ple" in text or "ngram_embedding" in text:
        return "ple"
    if any(term in text for term in ("gated_delta", "gdn", "causal_conv1d")):
        return "gdn"
    if any(
        term in text
        for term in (
            "qsa",
            "sparse_qk",
            "sparse_pv",
            "qk_lse",
            "compressed_kv",
            "compressed_index",
        )
    ):
        return "qsa"
    if any(term in text for term in ("flash_attn", "flash_attention", "paged_attention")):
        return "full_attention"
    if any(
        term in text
        for term in (
            "radixselect",
            "radix_select",
            "radixsort",
            "radix_sort",
            "biased_topk",
            "moe_topk",
            "topk",
        )
    ):
        return "moe_router"
    if any(
        term in text
        for term in (
            "moe::",
            "fused_moe",
            "gemmcutename",
            "moegather",
            "moe_gather",
            "moe_scatter",
            "silu_and_mul",
        )
    ):
        return "routed_shared_moe"
    if any(term in text for term in ("mhc", "hyperconnection", "hyper_connection")):
        return "hyperconnection"
    if any(term in text for term in ("rms_norm", "rmsnorm", "layer_norm", "layernorm")):
        return "normalization"
    if any(term in text for term in ("gemm", "brgemm", "xetla_gemm")):
        return "dense_projection"
    if any(term in text for term in ("quant", "dequant", "fp8", "cast")):
        return "quantization_cast"
    if any(term in text for term in ("sampler", "multinomial", "argmax")):
        return "sampler"
    if any(term in text for term in ("elementwise", "binaryfunctor", "unaryfunctor")):
        return "elementwise"
    return "other_noncollective"


def _collect_contexts(
    path: Path,
    context_name: str,
    drop_first: int,
    expected_retained: int,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]], Counter[str]]:
    expected: list[tuple[float, float]] = []
    observed_names: Counter[str] = Counter()

    for event in iter_events(path):
        if event.get("ph") != "X":
            continue
        name = str(event.get("name", ""))
        if not name.startswith("execute_context_"):
            continue
        observed_names[name] += 1
        if name != context_name:
            continue
        start = _float(event.get("ts"), field="annotation ts", path=path)
        duration = _float(event.get("dur"), field="annotation dur", path=path)
        if duration <= 0.0:
            raise TraceContractError(f"non-positive decode annotation duration in {path}")
        expected.append((start, start + duration))

    foreign = {name: count for name, count in observed_names.items() if name != context_name}
    if foreign:
        raise TraceContractError(
            f"non-target execute_context annotations in {path}: {foreign}"
        )

    expected.sort()
    required = drop_first + expected_retained
    if len(expected) != required:
        raise TraceContractError(
            f"expected exactly {required} {context_name!r} annotations in {path} "
            f"({drop_first} dropped + {expected_retained} retained), found {len(expected)}"
        )
    for previous, current in zip(expected, expected[1:]):
        if previous[1] > current[0]:
            raise TraceContractError(f"overlapping decode annotations in {path}")

    retained = expected[drop_first:]
    return expected, retained, observed_names


def summarize_trace(
    path: Path,
    *,
    context_name: str,
    drop_first: int,
    expected_retained: int,
    minimum_anchor_coverage: float,
    top: int,
) -> dict[str, Any]:
    if context_name != DEFAULT_CONTEXT:
        raise TraceContractError(
            "this report is frozen to the pure target-only decode context "
            f"{DEFAULT_CONTEXT!r}; got {context_name!r}"
        )
    rank = extract_rank(path)
    all_intervals, intervals, observed_names = _collect_contexts(
        path, context_name, drop_first, expected_retained
    )
    all_starts = [start for start, _ in all_intervals]
    starts = [start for start, _ in intervals]

    cpu_op_by_external_id: dict[int, dict[str, Any]] = {}
    for event in iter_events(path):
        if event.get("cat") != "cpu_op" or event.get("ph") != "X":
            continue
        timestamp = _float(event.get("ts", -1), field="cpu_op ts", path=path)
        if _interval_index(starts, intervals, timestamp) is None:
            continue
        args = event.get("args") or {}
        external_id = args.get("External id")
        try:
            external_id_int = int(external_id)
        except (TypeError, ValueError):
            continue
        cpu_op_by_external_id[external_id_int] = {
            "name": str(event.get("name", "<unnamed>")),
            "input_dims": args.get("Input Dims") or [],
            "input_strides": args.get("Input Strides") or [],
            "input_types": args.get("Input type") or [],
            "concrete_inputs": args.get("Concrete Inputs") or [],
        }

    per_cycle_buckets = [Counter() for _ in intervals]
    per_cycle_bucket_calls = [Counter() for _ in intervals]
    per_cycle_names = [Counter() for _ in intervals]
    per_cycle_name_calls = [Counter() for _ in intervals]
    operation_shape_duration_us: Counter[str] = Counter()
    operation_shape_calls: Counter[str] = Counter()
    device_counts: Counter[str] = Counter()
    anchor_fields: Counter[str] = Counter()

    for event in iter_events(path):
        category = str(event.get("cat", ""))
        if event.get("ph") != "X" or category not in DEVICE_CATEGORIES:
            continue
        device_counts["total"] += 1
        args = event.get("args") or {}
        anchor, anchor_field = _event_anchor(args)
        if anchor is None:
            device_counts["without_host_anchor"] += 1
            continue
        device_counts["with_host_anchor"] += 1
        anchor_fields[anchor_field or "unknown"] += 1

        all_index = _interval_index(all_starts, all_intervals, anchor)
        if all_index is None:
            device_counts["outside_target_annotations"] += 1
            continue
        if all_index < drop_first:
            device_counts["inside_dropped_annotation"] += 1
            continue

        index = all_index - drop_first
        device_counts["inside_retained_annotations"] += 1
        name = str(event.get("name", "<unnamed>"))
        duration_us = _float(event.get("dur", 0), field="device dur", path=path)
        if duration_us < 0.0:
            raise TraceContractError(f"negative device-event duration in {path}: {name}")

        external_id = args.get("External id")
        try:
            external_id_int = int(external_id)
        except (TypeError, ValueError):
            external_id_int = -1
        operator = cpu_op_by_external_id.get(external_id_int)
        operator_name = None if operator is None else str(operator["name"])
        if operator is None:
            device_counts["retained_without_cpu_operator"] += 1
        else:
            device_counts["retained_with_cpu_operator"] += 1
        bucket = classify_device_event(name, category, operator_name)

        per_cycle_buckets[index][bucket] += duration_us
        per_cycle_bucket_calls[index][bucket] += 1
        per_cycle_names[index][name] += duration_us
        per_cycle_name_calls[index][name] += 1

        shape_key = _json_key(
            {
                "bucket": bucket,
                "device_event": name,
                "operator": operator
                or {"name": None, "mapping": "unmapped_external_id"},
            }
        )
        operation_shape_duration_us[shape_key] += duration_us
        operation_shape_calls[shape_key] += 1

    total_device = device_counts["total"]
    anchor_coverage = (
        device_counts["with_host_anchor"] / total_device if total_device else 0.0
    )
    if total_device == 0:
        raise TraceContractError(f"no XPU device events found in {path}")
    if anchor_coverage < minimum_anchor_coverage:
        raise TraceContractError(
            f"device host-anchor coverage {anchor_coverage:.6f} is below "
            f"{minimum_anchor_coverage:.6f} in {path}"
        )
    empty_cycles = [index for index, row in enumerate(per_cycle_bucket_calls) if not row]
    if empty_cycles:
        raise TraceContractError(
            f"retained decode annotations without anchored device events in {path}: "
            f"{empty_cycles}"
        )

    bucket_names = sorted(set().union(*(row.keys() for row in per_cycle_buckets)))
    bucket_duration = {
        bucket: [row[bucket] / 1000.0 for row in per_cycle_buckets]
        for bucket in bucket_names
    }
    bucket_calls = {
        bucket: [row[bucket] for row in per_cycle_bucket_calls]
        for bucket in bucket_names
    }
    noncollective_ms = [
        sum(duration for bucket, duration in row.items() if not bucket.startswith(COLLECTIVE_PREFIX))
        / 1000.0
        for row in per_cycle_buckets
    ]
    collective_ms = [
        sum(duration for bucket, duration in row.items() if bucket.startswith(COLLECTIVE_PREFIX))
        / 1000.0
        for row in per_cycle_buckets
    ]
    aggregate_names = sum(per_cycle_names, Counter())
    aggregate_name_calls = sum(per_cycle_name_calls, Counter())

    cycles = []
    for index, ((start, end), buckets, calls) in enumerate(
        zip(intervals, per_cycle_buckets, per_cycle_bucket_calls)
    ):
        cycles.append(
            {
                "retained_ordinal": index,
                "original_annotation_ordinal": index + drop_first,
                "host_start_us": start,
                "host_duration_ms": (end - start) / 1000.0,
                "summed_noncollective_device_ms": noncollective_ms[index],
                "summed_collective_device_ms_distorted": collective_ms[index],
                "bucket_device_ms": {
                    bucket: buckets[bucket] / 1000.0 for bucket in sorted(buckets)
                },
                "bucket_calls": {bucket: calls[bucket] for bucket in sorted(calls)},
            }
        )

    return {
        "rank": rank,
        "trace": str(path),
        "compressed_bytes": path.stat().st_size,
        "observed_execute_context_annotations": dict(observed_names),
        "dropped_initial_contexts": drop_first,
        "retained_contexts": len(intervals),
        "context_host_duration_ms": _summary(
            [(end - start) / 1000.0 for start, end in intervals]
        ),
        "summed_noncollective_device_ms_per_cycle": _summary(noncollective_ms),
        "summed_collective_device_ms_per_cycle_distorted": _summary(collective_ms),
        "bucket_device_ms_per_cycle": {
            bucket: {
                **_summary(bucket_duration[bucket]),
                "calls": _summary([float(value) for value in bucket_calls[bucket]]),
            }
            for bucket in bucket_names
        },
        "cycles": cycles,
        "device_event_accounting": {
            **dict(device_counts),
            "host_anchor_coverage": anchor_coverage,
            "host_anchor_fields": dict(anchor_fields),
        },
        "mapped_cpu_operator_count": len(cpu_op_by_external_id),
        "top_device_events_by_duration": [
            {
                "name": name,
                "mean_ms_per_retained_cycle": duration / len(intervals) / 1000.0,
                "calls_per_retained_cycle": aggregate_name_calls[name] / len(intervals),
            }
            for name, duration in aggregate_names.most_common(top)
        ],
        "top_device_event_operator_shapes": [
            {
                **json.loads(key),
                "mean_ms_per_retained_cycle": duration / len(intervals) / 1000.0,
                "calls_per_retained_cycle": operation_shape_calls[key] / len(intervals),
            }
            for key, duration in operation_shape_duration_us.most_common(top)
        ],
    }


def discover_traces(trace_dir: Path, expected_ranks: tuple[int, ...]) -> list[Path]:
    traces = sorted(trace_dir.rglob("*rank*.pt.trace.json.gz"))
    if not traces:
        raise TraceContractError(
            f"no rank-qualified *.pt.trace.json.gz traces found under {trace_dir}"
        )

    by_rank: dict[int, Path] = {}
    for trace in traces:
        rank = extract_rank(trace)
        if rank in by_rank:
            raise TraceContractError(
                f"duplicate trace for rank {rank}: {by_rank[rank]} and {trace}"
            )
        by_rank[rank] = trace

    actual = tuple(sorted(by_rank))
    if actual != expected_ranks:
        raise TraceContractError(
            f"expected ranks {expected_ranks}, found {actual} under {trace_dir}"
        )
    return [by_rank[rank] for rank in expected_ranks]


def summarize_directory(
    trace_dir: Path,
    *,
    context_name: str = DEFAULT_CONTEXT,
    drop_first: int = 1,
    expected_retained: int = 3,
    expected_ranks: tuple[int, ...] = DEFAULT_EXPECTED_RANKS,
    minimum_anchor_coverage: float = 0.98,
    top: int = 50,
) -> dict[str, Any]:
    if context_name != DEFAULT_CONTEXT:
        raise TraceContractError(
            "this report is frozen to the pure target-only decode context "
            f"{DEFAULT_CONTEXT!r}; got {context_name!r}"
        )
    if drop_first < 0:
        raise ValueError("drop_first must be non-negative")
    if expected_retained <= 0:
        raise ValueError("expected_retained must be positive")
    if not expected_ranks or len(set(expected_ranks)) != len(expected_ranks):
        raise ValueError("expected_ranks must be non-empty and unique")
    if not 0.0 <= minimum_anchor_coverage <= 1.0:
        raise ValueError("minimum_anchor_coverage must be between zero and one")
    if top <= 0:
        raise ValueError("top must be positive")

    expected_ranks = tuple(sorted(expected_ranks))
    traces = discover_traces(trace_dir, expected_ranks)
    ranks = [
        summarize_trace(
            trace,
            context_name=context_name,
            drop_first=drop_first,
            expected_retained=expected_retained,
            minimum_anchor_coverage=minimum_anchor_coverage,
            top=top,
        )
        for trace in traces
    ]

    bucket_names = sorted(
        set().union(*(rank["bucket_device_ms_per_cycle"].keys() for rank in ranks))
    )
    cross_rank_buckets = {}
    for bucket in bucket_names:
        values = [
            rank["bucket_device_ms_per_cycle"].get(bucket, {}).get("mean", 0.0)
            for rank in ranks
        ]
        cross_rank_buckets[bucket] = {
            "rank_mean_ms_per_cycle": statistics.fmean(values),
            "min_rank_mean_ms_per_cycle": min(values),
            "max_rank_mean_ms_per_cycle": max(values),
            "rank_samples": {
                str(rank["rank"]): value for rank, value in zip(ranks, values)
            },
        }

    slowest_rank_context = []
    for cycle in range(expected_retained):
        starts = [rank["cycles"][cycle]["host_start_us"] for rank in ranks]
        start_skew_us = max(starts) - min(starts)
        if start_skew_us > MAXIMUM_RANK_CONTEXT_START_SKEW_US:
            raise TraceContractError(
                f"rank contexts at retained ordinal {cycle} are not temporally "
                f"aligned: start skew {start_skew_us} us exceeds "
                f"{MAXIMUM_RANK_CONTEXT_START_SKEW_US} us"
            )
        samples = [
            (rank["cycles"][cycle]["host_duration_ms"], rank["rank"])
            for rank in ranks
        ]
        duration = max(sample[0] for sample in samples)
        slowest_ranks = sorted(
            rank for sample_duration, rank in samples if sample_duration == duration
        )
        slowest_rank_context.append(
            {
                "retained_ordinal": cycle,
                "slowest_ranks": slowest_ranks,
                "host_duration_ms": duration,
                "rank_context_start_skew_us": start_skew_us,
                "rank_samples_ms": {
                    str(item["rank"]): item["cycles"][cycle]["host_duration_ms"]
                    for item in ranks
                },
            }
        )

    return {
        "schema_version": 1,
        "classification": "qwen38_flash_next_tp4_pure_target_decode_kineto",
        "trace_directory": str(trace_dir),
        "context_name": context_name,
        "expected_ranks": list(expected_ranks),
        "dropped_initial_contexts_per_rank": drop_first,
        "retained_contexts_per_rank": expected_retained,
        "timestamp_method": (
            "associate XPU kernels/memcpy/memset with host execute_context by "
            "args.submitted, falling back to appended then sycl_enqk_begin; use "
            "the device event's own dur for bucket timing"
        ),
        "interpretation_warnings": [
            "Profiler-run throughput and host duration are diagnostic only because Kineto adds material overhead.",
            "Summed device-event duration is not wall time and can double-count overlap across queues.",
            "oneCCL event timing is timeline-distorted on this stack; collective buckets are separated and excluded from noncollective totals.",
            "Architecture buckets are conservative name/operator heuristics; inspect top event/operator rows before choosing an optimization.",
        ],
        "cross_rank_bucket_device_ms": cross_rank_buckets,
        "slowest_rank_context_by_cycle": slowest_rank_context,
        "ranks": ranks,
    }


def _parse_expected_ranks(value: str) -> tuple[int, ...]:
    try:
        ranks = tuple(sorted(int(item.strip()) for item in value.split(",") if item.strip()))
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected comma-separated integer ranks") from error
    if not ranks or len(set(ranks)) != len(ranks):
        raise argparse.ArgumentTypeError("expected non-empty unique ranks")
    return ranks


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stream and summarize rank-qualified gzipped XPU Kineto traces."
    )
    parser.add_argument("trace_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--context-name", default=DEFAULT_CONTEXT)
    parser.add_argument("--drop-first", type=int, default=1)
    parser.add_argument("--expected-retained", type=int, default=3)
    parser.add_argument(
        "--expected-ranks",
        type=_parse_expected_ranks,
        default=DEFAULT_EXPECTED_RANKS,
        metavar="RANKS",
        help="comma-separated ranks (default: 0,1,2,3)",
    )
    parser.add_argument("--minimum-anchor-coverage", type=float, default=0.98)
    parser.add_argument("--top", type=int, default=50)
    args = parser.parse_args()

    try:
        result = summarize_directory(
            args.trace_dir,
            context_name=args.context_name,
            drop_first=args.drop_first,
            expected_retained=args.expected_retained,
            expected_ranks=args.expected_ranks,
            minimum_anchor_coverage=args.minimum_anchor_coverage,
            top=args.top,
        )
    except (TraceContractError, RuntimeError, ValueError) as error:
        parser.error(str(error))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
