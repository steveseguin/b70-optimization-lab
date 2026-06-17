#!/usr/bin/env python3
"""Summarize Qwen3.6 ablation run summaries into promotion gates.

The raw runner summaries are useful but easy to misread because skipped checks
can have rc=0 and different runners put metrics in different JSON paths. This
report is deliberately strict: a candidate is quality-validated only when
metrics, JSON canary, color canary, and quality suite are all present and
passing. It is promotion-ready only when it is quality-validated and meets an
optional speed floor.
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import Any


METRIC_TOK_S_KEYS = (
    "tok_s_out_client_after_first_chunk_corrected",
    "tok_s_out_client_after_first_chunk",
    "tok_s_out_client_e2e",
)

METRIC_DECODE_KEYS = (
    "decode_ms_per_generation_token_vllm_histogram",
    "time_per_output_token_ms_vllm_histogram",
    "inter_token_ms_vllm_histogram",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def expand_paths(values: list[str]) -> list[Path]:
    paths: list[Path] = []
    for value in values:
        matches = sorted(glob.glob(value))
        if matches:
            paths.extend(Path(match) for match in matches)
        else:
            paths.append(Path(value))
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            unique.append(path)
            seen.add(resolved)
    return unique


def nested(data: Any, keys: tuple[str, ...]) -> Any:
    cur = data
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def metric_mean(metrics: dict[str, Any] | None, keys: tuple[str, ...]) -> float | None:
    if not isinstance(metrics, dict):
        return None
    for key in keys:
        value = metrics.get(key)
        if isinstance(value, dict):
            value = value.get("mean")
        try:
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            continue
    return None


def status_from_bool(value: Any, present: bool = True) -> str:
    if not present:
        return "missing"
    if value is True:
        return "pass"
    if value is False:
        return "fail"
    return "unknown"


def check_rc(summary: dict[str, Any], name: str) -> int | None:
    rc = nested(summary, ("return_codes", name))
    try:
        return int(rc) if rc is not None else None
    except (TypeError, ValueError):
        return None


def first_mismatch_text(canary: dict[str, Any] | None) -> str | None:
    if not isinstance(canary, dict):
        return None
    mismatch = canary.get("first_mismatch")
    if not mismatch:
        return None
    if isinstance(mismatch, dict):
        for key in ("normalized", "text", "message", "error"):
            value = mismatch.get(key)
            if value:
                return str(value)
        return json.dumps(mismatch, sort_keys=True)[:160]
    return str(mismatch)


def quality_pass(quality: dict[str, Any] | None) -> bool | None:
    if not isinstance(quality, dict):
        return None
    if "pass_all" in quality:
        return bool(quality.get("pass_all"))
    exact = quality.get("exact")
    if isinstance(exact, dict) and any(value is False for value in exact.values()):
        return False
    checks = (
        quality.get("baseline_match_all"),
        quality.get("repeat_pass"),
        quality.get("long_context_pass"),
    )
    known = [value for value in checks if value is not None]
    if known:
        return all(bool(value) for value in known)
    return None


def summarize(path: Path, min_tok_s: float | None) -> dict[str, Any]:
    data = load_json(path)
    metrics = data.get("metrics_summary")
    if metrics is None:
        metrics = nested(data, ("metrics", "summary"))

    tok_s = metric_mean(metrics, METRIC_TOK_S_KEYS)
    decode_ms = metric_mean(metrics, METRIC_DECODE_KEYS)
    ttft_ms = metric_mean(metrics, ("ttft_ms_client", "ttft_ms_vllm_metrics"))

    json_canary = data.get("json_canary")
    color_canary = data.get("color_canary")
    quality = data.get("quality_suite")

    metrics_rc = check_rc(data, "metrics")
    json_rc = check_rc(data, "json_canary")
    color_rc = check_rc(data, "color_canary")
    quality_rc = check_rc(data, "quality_suite")

    metrics_ok = metrics is not None and tok_s is not None and metrics_rc in (0, None)
    json_ok = isinstance(json_canary, dict) and json_canary.get("pass_all") is True and json_rc in (0, None)
    color_ok = isinstance(color_canary, dict) and color_canary.get("pass_all") is True and color_rc in (0, None)
    quality_ok_value = quality_pass(quality)
    quality_ok = quality_ok_value is True and quality_rc in (0, None)

    failures: list[str] = []
    if not metrics_ok:
        failures.append("metrics missing/fail")
    if not json_ok:
        reason = first_mismatch_text(json_canary)
        failures.append("json canary" + (f": {reason}" if reason else " missing/fail"))
    if not color_ok:
        reason = first_mismatch_text(color_canary)
        failures.append("color canary" + (f": {reason}" if reason else " missing/fail"))
    if not quality_ok:
        failures.append("quality suite missing/fail")

    quality_validated = metrics_ok and json_ok and color_ok and quality_ok
    performance_ok = (
        min_tok_s is None
        or (tok_s is not None and tok_s >= min_tok_s)
    )
    promotion_ready = quality_validated and performance_ok
    validation_clean = metrics_ok
    for check in (json_canary, color_canary, quality):
        if isinstance(check, dict):
            if check is quality:
                validation_clean = validation_clean and quality_ok_value is not False
            else:
                validation_clean = validation_clean and check.get("pass_all") is not False

    return {
        "path": str(path),
        "label": data.get("label") or path.stem,
        "stamp": data.get("stamp"),
        "tok_s_out_corrected": tok_s,
        "decode_ms_per_token": decode_ms,
        "ttft_ms": ttft_ms,
        "metrics_status": status_from_bool(metrics_ok, metrics is not None),
        "json_status": status_from_bool(
            json_canary.get("pass_all") if isinstance(json_canary, dict) else None,
            isinstance(json_canary, dict),
        ),
        "color_status": status_from_bool(
            color_canary.get("pass_all") if isinstance(color_canary, dict) else None,
            isinstance(color_canary, dict),
        ),
        "quality_status": status_from_bool(
            quality_ok_value,
            isinstance(quality, dict),
        ),
        "quality_validated": quality_validated,
        "min_tok_s_required": min_tok_s,
        "performance_status": (
            status_from_bool(performance_ok, True)
            if min_tok_s is not None else "not_gated"
        ),
        "validation_clean_for_executed_checks": validation_clean,
        "promotion_ready": promotion_ready,
        "first_failure": "; ".join(failures) if failures else "",
        "artifacts": data.get("artifacts", {}),
    }


def fmt_num(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def write_markdown(rows: list[dict[str, Any]], path: Path) -> None:
    lines = [
        "| label | tok/s | decode ms/tok | JSON | color | quality | speed | promotion | first failure |",
        "| --- | ---: | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        failure = str(row["first_failure"]).replace("\n", " ")
        if len(failure) > 140:
            failure = failure[:137] + "..."
        lines.append(
            "| {label} | {tok} | {decode} | {json} | {color} | {quality} | {speed} | {promo} | {failure} |".format(
                label=row["label"],
                tok=fmt_num(row["tok_s_out_corrected"]),
                decode=fmt_num(row["decode_ms_per_token"]),
                json=row["json_status"],
                color=row["color_status"],
                quality=row["quality_status"],
                speed=row["performance_status"],
                promo="yes" if row["promotion_ready"] else "no",
                failure=failure.replace("|", "\\|"),
            ))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("summaries", nargs="+", help="Summary JSON paths or globs")
    parser.add_argument("--out-json", help="Write machine-readable report")
    parser.add_argument("--out-md", help="Write Markdown table")
    parser.add_argument(
        "--min-tok-s",
        type=float,
        help="Optional speed floor required for promotion_ready=true.",
    )
    args = parser.parse_args()

    rows = [summarize(path, args.min_tok_s) for path in expand_paths(args.summaries)]
    rows.sort(key=lambda row: (
        row["promotion_ready"] is not True,
        -(row["tok_s_out_corrected"] or 0.0),
        row["label"],
    ))

    if args.out_json:
        Path(args.out_json).write_text(json.dumps(rows, indent=2) + "\n",
                                       encoding="utf-8")
    if args.out_md:
        write_markdown(rows, Path(args.out_md))

    print(json.dumps(rows, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
