#!/usr/bin/env python3
"""Split MoE route-capture JSONL records by benchmark request windows.

`scripts/measure-openai-endpoint-metrics.py` records per-repeat
`request_started_at_unix` and `request_finished_at_unix` timestamps. This
helper maps route-capture records into labeled prompt-class JSONL files by
matching each route record's `ts` against those measured request windows.
"""

from __future__ import annotations

import argparse
import glob
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def parse_labeled_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(
            "expected LABEL=PATH, for example natural=data/run.json"
        )
    label, path = value.split("=", 1)
    label = label.strip()
    path = path.strip()
    if not label:
        raise argparse.ArgumentTypeError("label cannot be empty")
    if not path:
        raise argparse.ArgumentTypeError("path cannot be empty")
    return label, Path(path)


def expand_inputs(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        if matches:
            paths.extend(Path(item) for item in matches)
        else:
            paths.append(Path(pattern))
    seen = set()
    out = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def load_windows(items: list[tuple[str, Path]], slop_s: float) -> dict[str, list[dict[str, Any]]]:
    windows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for label, path in items:
        artifact = json.loads(path.read_text(encoding="utf-8"))
        for record in artifact.get("records", []):
            start = record.get("request_started_at_unix")
            finish = record.get("request_finished_at_unix")
            if start is None or finish is None:
                raise ValueError(
                    f"{path} repeat {record.get('repeat')} does not have request timestamps"
                )
            windows[label].append({
                "start": float(start) - slop_s,
                "finish": float(finish) + slop_s,
                "path": str(path),
                "repeat": record.get("repeat"),
                "request_id": record.get("request_id"),
                "prompt_preset": artifact.get("prompt_preset"),
                "prompt_kind": artifact.get("prompt_kind"),
                "prompt_tokens_actual": artifact.get("prompt_tokens_actual"),
                "output_tokens_requested": artifact.get("output_tokens_requested"),
            })
    for label in windows:
        windows[label].sort(key=lambda item: (item["start"], item["finish"]))
    return dict(windows)


def matching_labels(ts: float, windows: dict[str, list[dict[str, Any]]]) -> list[str]:
    labels = []
    for label, label_windows in windows.items():
        for window in label_windows:
            if window["start"] <= ts <= window["finish"]:
                labels.append(label)
                break
    return labels


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--routes",
        action="append",
        required=True,
        help="Route JSONL path or glob. Repeat for multiple patterns.",
    )
    parser.add_argument(
        "--metrics",
        action="append",
        type=parse_labeled_path,
        required=True,
        help="Labeled metrics artifact, LABEL=PATH. Repeat for each prompt class.",
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--slop-s", type=float, default=0.25)
    parser.add_argument("--unmatched-out", type=Path)
    parser.add_argument("--summary-json", type=Path, required=True)
    args = parser.parse_args()

    route_paths = expand_inputs(args.routes)
    windows = load_windows(args.metrics, args.slop_s)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    writers = {
        label: (args.out_dir / f"{args.prefix}-{label}.jsonl").open("w", encoding="utf-8")
        for label in sorted(windows)
    }
    unmatched_writer = (
        args.unmatched_out.open("w", encoding="utf-8") if args.unmatched_out else None
    )

    counts = {label: 0 for label in windows}
    layer_counts: dict[str, dict[str, int]] = {
        label: defaultdict(int) for label in windows
    }
    source_counts: dict[str, int] = defaultdict(int)
    unmatched = 0
    ambiguous = 0
    total = 0
    try:
        for path in route_paths:
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    total += 1
                    record = json.loads(line)
                    ts = float(record.get("ts") or 0.0)
                    labels = matching_labels(ts, windows)
                    if len(labels) > 1:
                        ambiguous += 1
                    if not labels:
                        unmatched += 1
                        if unmatched_writer:
                            unmatched_writer.write(line + "\n")
                        continue
                    for label in labels:
                        writers[label].write(line + "\n")
                        counts[label] += 1
                        layer_counts[label][str(record.get("layer") or "unknown")] += 1
                    source_counts[f"{path}:{line_number}"] += 1
    finally:
        for writer in writers.values():
            writer.close()
        if unmatched_writer:
            unmatched_writer.close()

    summary = {
        "route_inputs": [str(path) for path in route_paths],
        "metrics_inputs": [
            {"label": label, "path": str(path)} for label, path in args.metrics
        ],
        "slop_s": args.slop_s,
        "windows": windows,
        "output_files": {
            label: str(args.out_dir / f"{args.prefix}-{label}.jsonl")
            for label in sorted(windows)
        },
        "total_route_records": total,
        "matched_records_by_label": counts,
        "unmatched_records": unmatched,
        "ambiguous_records": ambiguous,
        "layer_counts_by_label": {
            label: dict(sorted(layer_counts[label].items()))
            for label in sorted(layer_counts)
        },
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
