#!/usr/bin/env python3
"""Compare Gemma long-context service gate A/B summaries.

This is for service/prefill experiments, not LocalMaxxing headline claims. It
keeps the validity fields next to the speed deltas so small kernel experiments
do not get promoted from stale or cached runs.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


def parse_named_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("expected NAME=PATH")
    name, path = value.split("=", 1)
    name = name.strip()
    if not name:
        raise argparse.ArgumentTypeError("empty NAME in NAME=PATH")
    return name, Path(path)


def parse_key_value(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("expected KEY=VALUE")
    key, val = value.split("=", 1)
    key = key.strip()
    if not key:
        raise argparse.ArgumentTypeError("empty KEY in KEY=VALUE")
    return key, val


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def pct_delta(candidate: float | None, control: float | None) -> float | None:
    if candidate is None or control in (None, 0):
        return None
    return (candidate / control - 1.0) * 100.0


def stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "min": None, "max": None, "mean": None, "median": None}
    return {
        "n": len(values),
        "min": min(values),
        "max": max(values),
        "mean": mean(values),
        "median": median(values),
    }


def load_summary(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def collect_records(kind: str, tag: str, path: Path) -> list[dict[str, Any]]:
    data = load_summary(path)
    records: list[dict[str, Any]] = []
    for row in data.get("rows", []):
        for case_row in row.get("case_rows", []):
            records.append({
                "kind": kind,
                "wave": tag,
                "summary_path": str(path),
                "label": row.get("label"),
                "gpu_index": row.get("gpu_index"),
                "batch_size": row.get("batch_size"),
                "ubatch_size": row.get("ubatch_size"),
                "prefill_ubatch_size": row.get("prefill_ubatch_size"),
                "case_id": case_row.get("case_id"),
                "cached_tokens": case_row.get("cached_tokens"),
                "validation_pass": case_row.get("validation_pass"),
                "prompt_sha256": case_row.get("prompt_sha256"),
                "output_sha256": case_row.get("output_sha256"),
                "prefill_tok_s_approx": case_row.get("prefill_tok_s_approx"),
                "tok_s_after_ttft": case_row.get("tok_s_after_ttft"),
                "tok_s_wall": case_row.get("tok_s_wall"),
                "ttft_s": case_row.get("ttft_s"),
            })
    return records


def numeric(records: list[dict[str, Any]], key: str) -> list[float]:
    return [
        float(record[key])
        for record in records
        if record.get(key) is not None
    ]


def group_by(records: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        groups.setdefault(str(record.get(key)), []).append(record)
    return groups


def metric_block(control: list[dict[str, Any]],
                 candidate: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("prefill_tok_s_approx", "tok_s_after_ttft", "ttft_s"):
        c_stats = stats(numeric(control, key))
        x_stats = stats(numeric(candidate, key))
        out[key] = {
            "control": c_stats,
            "candidate": x_stats,
            "candidate_vs_control_mean_delta_pct": pct_delta(
                x_stats["mean"], c_stats["mean"]),
            "candidate_vs_control_median_delta_pct": pct_delta(
                x_stats["median"], c_stats["median"]),
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control", action="append", type=parse_named_path,
                        required=True, help="NAME=summary.json")
    parser.add_argument("--candidate", action="append", type=parse_named_path,
                        required=True, help="NAME=summary.json")
    parser.add_argument("--candidate-env", action="append", type=parse_key_value,
                        default=[], help="KEY=VALUE")
    parser.add_argument("--kind", required=True)
    parser.add_argument("--decision", default="needs-review")
    parser.add_argument("--notes", default="")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    control: list[dict[str, Any]] = []
    candidate: list[dict[str, Any]] = []
    input_summaries: dict[str, str] = {}

    for tag, path in args.control:
        control.extend(collect_records("control", tag, path))
        input_summaries[f"{tag}_control"] = str(path)
    for tag, path in args.candidate:
        candidate.extend(collect_records("candidate", tag, path))
        input_summaries[f"{tag}_candidate"] = str(path)

    records = control + candidate
    valid_records = [
        bool(r.get("validation_pass")) and r.get("cached_tokens") == 0
        for r in records
    ]

    by_wave: dict[str, Any] = {}
    for wave in sorted(set(r["wave"] for r in records)):
        by_wave[wave] = metric_block(
            [r for r in control if r["wave"] == wave],
            [r for r in candidate if r["wave"] == wave],
        )

    by_case: dict[str, Any] = {}
    for case_id in sorted(set(r["case_id"] for r in records)):
        by_case[case_id] = metric_block(
            [r for r in control if r["case_id"] == case_id],
            [r for r in candidate if r["case_id"] == case_id],
        )

    by_gpu: dict[str, Any] = {}
    for gpu_index in sorted(set(r["gpu_index"] for r in records)):
        by_gpu[gpu_index] = metric_block(
            [r for r in control if r["gpu_index"] == gpu_index],
            [r for r in candidate if r["gpu_index"] == gpu_index],
        )

    by_gpu_case: dict[str, Any] = {}
    for gpu_index in sorted(set(r["gpu_index"] for r in records)):
        for case_id in sorted(set(r["case_id"] for r in records)):
            key = f"gpu{gpu_index}:{case_id}"
            by_gpu_case[key] = metric_block(
                [
                    r for r in control
                    if r["gpu_index"] == gpu_index and r["case_id"] == case_id
                ],
                [
                    r for r in candidate
                    if r["gpu_index"] == gpu_index and r["case_id"] == case_id
                ],
            )

    output = {
        "kind": args.kind,
        "created_by": "codex",
        "decision": args.decision,
        "notes": args.notes,
        "candidate_env": dict(args.candidate_env),
        "input_summaries": input_summaries,
        "validity": {
            "records": len(records),
            "all_records_cached_tokens_zero": all(
                r.get("cached_tokens") == 0 for r in records),
            "all_records_validation_pass": all(
                bool(r.get("validation_pass")) for r in records),
            "all_records_valid": bool(records) and all(valid_records),
        },
        "overall": metric_block(control, candidate),
        "by_wave": by_wave,
        "by_case": by_case,
        "by_gpu": by_gpu,
        "by_gpu_case": by_gpu_case,
        "records": records,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
