#!/usr/bin/env python3
"""Pure validation and accounting helpers for exact-depth Qwen measurements.

This module deliberately performs no I/O and launches no work.  Runtime-specific
harnesses can use it to build receipts without duplicating the evidence rules.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import math
import statistics
from typing import Any


DECLARED_DEPTHS = (0, 2048, 4096, 8192, 16384, 24576, 32768)
COMPLETION_TOKEN_BUDGET = 128
METRIC_EVENT_COUNT = 100
METRIC_INTERVAL_COUNT = 99
ALLOWED_COVERAGE_STATES = frozenset(
    {"missing", "measured", "estimated", "closed", "quarantined", "unsupported"}
)


def _require_plain_int(value: object, field: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{field} must be a plain integer")
    return value


def _require_finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be a finite number")
    return result


def validate_depth(depth: object) -> int:
    """Return a declared exact depth, rejecting aliases and undeclared values."""

    result = _require_plain_int(depth, "depth")
    if result not in DECLARED_DEPTHS:
        declared = ", ".join(str(item) for item in DECLARED_DEPTHS)
        raise ValueError(f"depth must be one of: {declared}")
    return result


def validate_flat_token_ids(
    token_ids: object,
    *,
    field: str = "token_ids",
    expected_count: int | None = None,
) -> tuple[int, ...]:
    """Validate a flat JSON-style array of non-negative, plain integer IDs."""

    if not isinstance(token_ids, (list, tuple)):
        raise ValueError(f"{field} must be a flat list or tuple of token IDs")
    validated: list[int] = []
    for index, token_id in enumerate(token_ids):
        value = _require_plain_int(token_id, f"{field}[{index}]")
        if value < 0:
            raise ValueError(f"{field}[{index}] must be non-negative")
        validated.append(value)
    if expected_count is not None:
        count = _require_plain_int(expected_count, "expected_count")
        if count < 0:
            raise ValueError("expected_count must be non-negative")
        if len(validated) != count:
            raise ValueError(
                f"{field} must contain exactly {count} token IDs; got {len(validated)}"
            )
    return tuple(validated)


def _canonical_json_value(value: object, field: str = "payload") -> Any:
    if value is None or isinstance(value, (bool, str)):
        return value
    if type(value) is int:
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field} contains a non-finite number")
        return value
    if isinstance(value, (list, tuple)):
        return [
            _canonical_json_value(item, f"{field}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError(f"{field} contains a non-string object key")
            normalized[key] = _canonical_json_value(item, f"{field}.{key}")
        return normalized
    raise ValueError(
        f"{field} contains a non-JSON value of type {type(value).__name__}"
    )


def canonical_json_bytes(payload: object) -> bytes:
    """Encode the supported JSON domain in one stable, whitespace-free form."""

    normalized = _canonical_json_value(payload)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_json_sha256(payload: object) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def canonical_fixture_sha256(fixture: object) -> str:
    """Explicit fixture-facing alias for the canonical JSON digest."""

    return canonical_json_sha256(fixture)


def canonical_payload_sha256(payload: object) -> str:
    """Explicit request/response-facing alias for the canonical JSON digest."""

    return canonical_json_sha256(payload)


def validate_capacity(
    depth: object,
    capacity: object,
    *,
    completion_tokens: object = COMPLETION_TOKEN_BUDGET,
) -> int:
    """Require configured capacity to cover exact depth plus the output budget."""

    exact_depth = validate_depth(depth)
    configured = _require_plain_int(capacity, "capacity")
    output_budget = _require_plain_int(completion_tokens, "completion_tokens")
    if output_budget < 0:
        raise ValueError("completion_tokens must be non-negative")
    required = exact_depth + output_budget
    if configured < required:
        raise ValueError(
            f"capacity must be at least depth + completion_tokens ({required}); "
            f"got {configured}"
        )
    return configured


def interval_window(timestamped_events_s: object) -> dict[str, float | int]:
    """Account for exactly 100 event timestamps spanning 99 intervals."""

    if not isinstance(timestamped_events_s, (list, tuple)):
        raise ValueError("timestamped_events_s must be a list or tuple")
    if len(timestamped_events_s) != METRIC_EVENT_COUNT:
        raise ValueError(
            f"timestamped_events_s must contain exactly {METRIC_EVENT_COUNT} events; "
            f"got {len(timestamped_events_s)}"
        )
    events = [
        _require_finite_number(value, f"timestamped_events_s[{index}]")
        for index, value in enumerate(timestamped_events_s)
    ]
    for index, (left, right) in enumerate(zip(events, events[1:])):
        if right <= left:
            raise ValueError(
                "timestamped_events_s must be strictly increasing; "
                f"events {index} and {index + 1} are invalid"
            )
    duration_s = events[-1] - events[0]
    return {
        "timestamped_events": METRIC_EVENT_COUNT,
        "inter_token_intervals": METRIC_INTERVAL_COUNT,
        "interval_numerator_tokens": METRIC_INTERVAL_COUNT,
        "first_event_s": events[0],
        "hundredth_event_s": events[-1],
        "duration_s": duration_s,
        "interval_tok_s": METRIC_INTERVAL_COUNT / duration_s,
        "legacy_inclusive_event_tok_s": METRIC_EVENT_COUNT / duration_s,
    }


def _percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summary_stats(values: object) -> dict[str, float | int | None]:
    """Return the standard packet statistics with a linear-interpolated p10."""

    if not isinstance(values, (list, tuple)):
        raise ValueError("values must be a list or tuple")
    numbers = [
        _require_finite_number(value, f"values[{index}]")
        for index, value in enumerate(values)
    ]
    if not numbers:
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
        "count": len(numbers),
        "p10": _percentile(numbers, 0.10),
        "median": statistics.median(numbers),
        "mean": statistics.fmean(numbers),
        "min": min(numbers),
        "max": max(numbers),
        "stdev": statistics.stdev(numbers) if len(numbers) > 1 else 0.0,
    }


def compare_exact_oracle(
    expected_token_ids: object, actual_token_ids: object
) -> dict[str, bool | int | None | str]:
    """Compare complete token streams and locate their first divergence."""

    expected = validate_flat_token_ids(expected_token_ids, field="expected_token_ids")
    actual = validate_flat_token_ids(actual_token_ids, field="actual_token_ids")
    common_count = min(len(expected), len(actual))
    first_divergence: int | None = None
    for index in range(common_count):
        if expected[index] != actual[index]:
            first_divergence = index
            break
    if first_divergence is None and len(expected) != len(actual):
        first_divergence = common_count
    passed = first_divergence is None
    prefix_count = len(expected) if passed else first_divergence
    return {
        "passed": passed,
        "expected_count": len(expected),
        "actual_count": len(actual),
        "matching_prefix_count": prefix_count,
        "first_divergence_index": first_divergence,
        "expected_token_ids_sha256": canonical_json_sha256(list(expected)),
        "actual_token_ids_sha256": canonical_json_sha256(list(actual)),
    }


def metric_delta(
    before: object,
    after: object,
    metric_name: str | None = None,
) -> float:
    """Return a strict finite counter/value delta.

    Pass two numbers for a scalar delta, or two mappings plus ``metric_name``
    for a named metric.  Missing mapping keys fail closed instead of silently
    becoming zero.
    """

    if metric_name is None:
        before_value = _require_finite_number(before, "before")
        after_value = _require_finite_number(after, "after")
    else:
        if not isinstance(metric_name, str) or not metric_name:
            raise ValueError("metric_name must be a non-empty string")
        if not isinstance(before, Mapping) or not isinstance(after, Mapping):
            raise ValueError("named metric deltas require before and after mappings")
        if metric_name not in before or metric_name not in after:
            raise ValueError(f"metric {metric_name!r} must exist in both snapshots")
        before_value = _require_finite_number(
            before[metric_name], f"before.{metric_name}"
        )
        after_value = _require_finite_number(after[metric_name], f"after.{metric_name}")
    return after_value - before_value


def validate_coverage_state(state: object) -> str:
    """Require one explicit evidence state; no state aliases are accepted."""

    if not isinstance(state, str) or state not in ALLOWED_COVERAGE_STATES:
        allowed = ", ".join(sorted(ALLOWED_COVERAGE_STATES))
        raise ValueError(f"coverage state must be one of: {allowed}")
    return state
