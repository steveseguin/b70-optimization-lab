#!/usr/bin/env python3
"""Add explicit event/interval accounting to realistic-suite benchmark JSON."""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import tempfile
from pathlib import Path
from typing import Any


LEGACY_METRIC = "median_tok_s_1_100_after_ttft"
INTERVAL_METRIC = "median_tok_s_1_100_intervals_after_ttft"
INTERVAL_SUMMARY_KEY = "tok_s_1_100_intervals_after_ttft"
CLASS_BALANCED_METRIC = (
    "median_of_prompt_class_medians_tok_s_1_100_intervals_after_ttft"
)
CLASS_BALANCED_SUMMARY_KEY = (
    "class_balanced_tok_s_1_100_intervals_after_ttft"
)
PROMOTION_OUTPUT_TOKENS = 512
MIN_FIXED_SUITE_PROMPTS = 12
MIN_PROMOTION_PROMPT_CLASSES = 5
PROMOTION_PROMPT_CLASSES = {
    "incident-retrospective": "operations",
    "code-review": "code",
    "customer-email": "prose",
    "sql-debugging": "code",
    "release-plan": "operations",
    "benchmark-analysis": "analysis",
    "architecture-tradeoff": "analysis",
    "bug-report-synthesis": "operations",
    "technical-guide": "documentation",
    "risk-register": "structured-writing",
    "performance-hypotheses": "analysis",
    "decision-memo": "prose",
}


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * pct
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
        "p10": percentile(values, 0.10),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "min": min(values),
        "max": max(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def event_window_rates(
    offsets: list[float], event_count: int
) -> tuple[float | None, float | None]:
    """Return historical event-count and conventional interval-count rates."""
    if event_count <= 1 or len(offsets) < event_count:
        return None, None
    duration = float(offsets[event_count - 1]) - float(offsets[0])
    if duration <= 0:
        return None, None
    return event_count / duration, (event_count - 1) / duration


def prompt_class_for_row(row: dict[str, Any]) -> str | None:
    value = row.get("prompt_class") or PROMOTION_PROMPT_CLASSES.get(
        str(row.get("prompt_id") or "")
    )
    return value if isinstance(value, str) and value != "unclassified" else None


def class_balanced_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        prompt_class = prompt_class_for_row(row)
        value = row.get("tok_s_1_100_intervals_after_ttft")
        if prompt_class and isinstance(value, (int, float)):
            grouped.setdefault(prompt_class, []).append(float(value))
    class_medians = {
        prompt_class: statistics.median(values)
        for prompt_class, values in sorted(grouped.items())
    }
    result: dict[str, Any] = stats(list(class_medians.values()))
    result["aggregation"] = "median-of-prompt-class-medians"
    result["class_medians"] = class_medians
    result["class_prompt_counts"] = {
        prompt_class: len(grouped[prompt_class]) for prompt_class in class_medians
    }
    return result


def qualify(data: dict[str, Any]) -> dict[str, Any]:
    gate = data.get("realistic_final_gate") or {}
    fresh = data.get("fresh_response_validity") or {}
    rows = data.get("rows")
    summary = data.get("summary")
    if not isinstance(rows, list) or not rows:
        raise ValueError("benchmark has no rows")
    if not isinstance(summary, dict):
        raise ValueError("benchmark has no summary")
    event_count = gate.get("metric_tokens")
    if not isinstance(event_count, int) or event_count <= 1:
        raise ValueError("realistic_final_gate.metric_tokens must be greater than one")
    if event_count != 100:
        raise ValueError(
            "this schema names the first-100-token window and requires 100 events"
        )

    use_token_ids = bool(fresh.get("return_token_ids_requested"))
    offsets_key = "token_id_offsets_s" if use_token_ids else "chunk_offsets_s"
    legacy_values: list[float] = []
    interval_values: list[float] = []
    for index, row in enumerate(rows):
        offsets = row.get(offsets_key)
        if not isinstance(offsets, list):
            raise ValueError(f"row {index} is missing {offsets_key}")
        legacy, interval = event_window_rates(offsets, event_count)
        if legacy is None or interval is None:
            raise ValueError(f"row {index} does not contain a valid metric window")
        recorded = row.get("tok_s_1_100_after_ttft")
        if not isinstance(recorded, (int, float)) or not math.isclose(
            float(recorded), legacy, rel_tol=0, abs_tol=1e-12
        ):
            raise ValueError(
                f"row {index} historical metric does not match its timestamps"
            )
        row["tok_s_1_100_after_ttft_legacy_inclusive_events"] = legacy
        row["tok_s_1_100_intervals_after_ttft"] = interval
        legacy_values.append(legacy)
        interval_values.append(interval)

    existing = summary.get("tok_s_1_100_after_ttft") or {}
    existing_median = existing.get("median")
    legacy_median = statistics.median(legacy_values)
    if not isinstance(existing_median, (int, float)) or not math.isclose(
        float(existing_median), legacy_median, rel_tol=0, abs_tol=1e-12
    ):
        raise ValueError("historical summary median does not match row timestamps")

    summary["tok_s_1_100_after_ttft_legacy_inclusive_events"] = stats(legacy_values)
    summary["tok_s_1_100_intervals_after_ttft"] = stats(interval_values)
    summary[CLASS_BALANCED_SUMMARY_KEY] = class_balanced_stats(rows)
    gate["metric_name_note"] = (
        "Historical compatibility field: 100 timestamped token events divided "
        "by the first-to-100th event span (99 intervals)."
    )
    gate["preferred_metric_name"] = CLASS_BALANCED_METRIC
    gate["preferred_metric_aggregation"] = "median-of-prompt-class-medians"
    gate["metric_intervals"] = event_count - 1
    fresh["primary_metric_accounting"] = "legacy-inclusive-events"
    fresh["preferred_metric_name"] = CLASS_BALANCED_METRIC
    fresh["preferred_metric_aggregation"] = "median-of-prompt-class-medians"
    fresh["primary_metric_intervals"] = event_count - 1
    data["metric_accounting"] = {
        "schema": "realistic-window-accounting-v1",
        "historical_metric_name": LEGACY_METRIC,
        "historical_formula": "100 / (timestamp[99] - timestamp[0])",
        "preferred_metric_name": CLASS_BALANCED_METRIC,
        "preferred_formula": (
            "median by prompt class, then median across class medians, of "
            "99 / (timestamp[99] - timestamp[0])"
        ),
        "timestamped_events": event_count,
        "inter_token_intervals": event_count - 1,
        "timing_source": fresh.get("token_timing_source"),
    }
    return data


def promotion_evidence_failures(data: dict[str, Any]) -> list[str]:
    """Re-check promotion evidence without trusting a stored ``passed`` flag.

    Older benchmark JSON can contain ``realistic_final_gate.passed=true`` for
    a 128-token or filtered diagnostic.  Submission tools must derive the
    answer from raw identity and row fields so that stale or forged booleans
    cannot authorize publication.
    """
    failures: list[str] = []
    gate = data.get("realistic_final_gate") or {}
    fresh = data.get("fresh_response_validity") or {}
    identity = data.get("run_identity") or {}
    rows = data.get("rows") or []
    if gate.get("passed") is not True:
        failures.append("realistic_final_gate_not_passed")
    if fresh.get("valid") is not True:
        failures.append("fresh_response_validity_not_valid")
    if identity.get("max_tokens") != PROMOTION_OUTPUT_TOKENS:
        failures.append("requested_output_tokens_not_512")
    if identity.get("selected_prompt_ids"):
        failures.append("prompt_subset_selected")
    if not isinstance(rows, list) or len(rows) < MIN_FIXED_SUITE_PROMPTS:
        failures.append("fixed_suite_has_fewer_than_12_prompts")
        rows = []
    expected_count = (
        identity.get("suite_prompt_count")
        or gate.get("suite_prompt_count")
        or identity.get("prompt_count")
    )
    if not isinstance(expected_count, int) or len(rows) != expected_count:
        failures.append("fixed_suite_incomplete")
    prompt_hashes = [row.get("prompt_sha256") for row in rows]
    if (
        not prompt_hashes
        or any(not isinstance(value, str) or not value for value in prompt_hashes)
        or len(set(prompt_hashes)) != len(prompt_hashes)
    ):
        failures.append("prompt_hashes_missing_or_not_unique")
    prompt_classes = [
        prompt_class_for_row(row)
        for row in rows
    ]
    classified = {
        value for value in prompt_classes
        if isinstance(value, str) and value and value != "unclassified"
    }
    if len(prompt_classes) != len(rows) or len(classified) < MIN_PROMOTION_PROMPT_CLASSES:
        failures.append("fixed_suite_lacks_varied_prompt_classes")
    completion_counts = [row.get("completion_tokens") for row in rows]
    if not completion_counts or any(
        not isinstance(value, int) or value < 100 for value in completion_counts
    ):
        failures.append("every_completion_must_cover_100_event_metric")
    cached = [row.get("cached_tokens") for row in rows]
    if not cached or any(not isinstance(value, int) or value != 0 for value in cached):
        failures.append("cached_tokens_not_all_zero")
    request_extra = identity.get("request_extra") or {}
    if isinstance(request_extra, dict) and request_extra.get("ignore_eos") is True:
        failures.append("ignore_eos_enabled")
    if gate.get("metric_tokens") != 100:
        failures.append("metric_window_not_100_events")
    summary = data.get("summary") or {}
    conventional = summary.get(INTERVAL_SUMMARY_KEY) or {}
    if conventional.get("count") != len(rows):
        failures.append("conventional_metric_missing_rows")
    class_balanced = summary.get(CLASS_BALANCED_SUMMARY_KEY) or {}
    if (
        class_balanced.get("aggregation")
        != "median-of-prompt-class-medians"
        or class_balanced.get("count") != len(classified)
    ):
        failures.append("class_balanced_metric_missing_prompt_classes")
    return failures


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bench_json", type=Path)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--out", type=Path)
    destination.add_argument("--in-place", action="store_true")
    args = parser.parse_args()

    data = json.loads(args.bench_json.read_text(encoding="utf-8"))
    qualified = qualify(data)
    output = json.dumps(qualified, indent=2, sort_keys=True) + "\n"
    destination_path = args.bench_json if args.in_place else args.out
    assert destination_path is not None
    write_atomic(destination_path, output)

    legacy = qualified["summary"]["tok_s_1_100_after_ttft"]["median"]
    interval = qualified["summary"]["tok_s_1_100_intervals_after_ttft"]["median"]
    class_balanced = qualified["summary"][CLASS_BALANCED_SUMMARY_KEY]["median"]
    print(f"published_legacy_tok_s={legacy}")
    print(f"conventional_interval_tok_s={interval}")
    print(f"class_balanced_interval_tok_s={class_balanced}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
