#!/usr/bin/env python3
"""Summarize text output from `xpu-smi dump`.

This host's xpu-smi build does not support JSON dump output without the daemon,
so benchmark telemetry is captured as CSV-like text and summarized here.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def maybe_float(value: str) -> float | None:
    value = value.strip()
    if not value or value.upper() == "N/A":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_dump(path: str) -> tuple[list[str], list[dict[str, str]]]:
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    header_index = None
    for index, line in enumerate(lines):
        if line.startswith("Timestamp,"):
            header_index = index
            break
    if header_index is None:
        raise SystemExit(f"{path}: no xpu-smi dump header found")

    csv_text = "\n".join(lines[header_index:])
    reader = csv.DictReader(csv_text.splitlines(), skipinitialspace=True)
    rows: list[dict[str, str]] = []
    for row in reader:
        if not row or not row.get("Timestamp"):
            continue
        rows.append({str(key).strip(): str(value).strip() for key, value in row.items() if key is not None})
    return [str(name).strip() for name in (reader.fieldnames or [])], rows


def summarize(path: str) -> dict[str, Any]:
    fields, rows = parse_dump(path)
    by_device: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_device[str(row.get("DeviceId", "")).strip()].append(row)

    numeric_fields = [
        field
        for field in fields
        if field not in {"Timestamp", "DeviceId", "Throttle reason"}
    ]
    devices: dict[str, Any] = {}
    for device, device_rows in sorted(by_device.items(), key=lambda item: item[0]):
        metrics: dict[str, Any] = {}
        for field in numeric_fields:
            values = [maybe_float(row.get(field, "")) for row in device_rows]
            clean = [value for value in values if value is not None]
            metrics[field] = {
                "count": len(clean),
                "missing": len(values) - len(clean),
                "min": min(clean) if clean else None,
                "mean": statistics.fmean(clean) if clean else None,
                "max": max(clean) if clean else None,
            }
        throttles = Counter(row.get("Throttle reason", "") for row in device_rows)
        devices[device] = {
            "samples": len(device_rows),
            "metrics": metrics,
            "throttle_reasons": dict(sorted(throttles.items())),
        }

    return {
        "source": path,
        "fields": fields,
        "rows": len(rows),
        "devices": devices,
    }


def write_markdown(summary: dict[str, Any], path: str) -> None:
    lines = [
        "# XPU-SMI Dump Summary",
        "",
        f"- Source: `{summary['source']}`",
        f"- Rows: `{summary['rows']}`",
        "",
    ]
    for device, data in summary["devices"].items():
        lines.extend([
            f"## Device {device}",
            "",
            f"- Samples: `{data['samples']}`",
            f"- Throttle reasons: `{data['throttle_reasons']}`",
            "",
            "| Metric | Count | Missing | Min | Mean | Max |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ])
        for metric, stats in data["metrics"].items():
            def fmt(value: Any) -> str:
                if value is None:
                    return ""
                if isinstance(value, float):
                    return f"{value:.3f}"
                return str(value)

            lines.append(
                f"| {metric} | {stats['count']} | {stats['missing']} | "
                f"{fmt(stats['min'])} | {fmt(stats['mean'])} | {fmt(stats['max'])} |"
            )
        lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--markdown-out")
    args = parser.parse_args()

    summary = summarize(args.input)
    Path(args.output_json).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_out:
        write_markdown(summary, args.markdown_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
