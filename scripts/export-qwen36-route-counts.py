#!/usr/bin/env python3
"""Export real route-capture topk rows as per-expert count windows."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def parse_range(value: str) -> list[int]:
    if ":" not in value:
        return [int(part.strip()) for part in value.split(",") if part.strip()]
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        start, stop = parts
        step = 1
    elif len(parts) == 3:
        start, stop, step = parts
    else:
        raise argparse.ArgumentTypeError(
            "range must be start:stop[:step] or comma-separated integers")
    return list(range(start, stop, step))


def load_rows(path: Path, layer_regex: str) -> list[list[int]]:
    pattern = re.compile(layer_regex)
    rows: list[list[int]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            name = str(record.get("name") or record.get("layer") or "")
            if not pattern.search(name):
                continue
            topk_ids = record.get("topk_ids")
            if not isinstance(topk_ids, list):
                continue
            for row in topk_ids:
                if not isinstance(row, list):
                    continue
                rows.append([int(item) for item in row])
    if not rows:
        raise SystemExit(f"no rows matched {layer_regex!r} in {path}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("route_jsonl", type=Path)
    parser.add_argument("--layer-regex", required=True)
    parser.add_argument("--rows", type=int, default=1)
    parser.add_argument("--starts", type=parse_range, default=[0])
    parser.add_argument("--num-experts", type=int, default=256)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--metadata-out", type=Path)
    args = parser.parse_args()

    source_rows = load_rows(args.route_jsonl, args.layer_regex)
    emitted: list[dict[str, object]] = []
    with args.out.open("w", encoding="utf-8") as handle:
        for start in args.starts:
            window = source_rows[start:start + args.rows]
            if len(window) != args.rows:
                continue
            counts = [0] * args.num_experts
            for row in window:
                for expert in row:
                    counts[expert] += 1
            handle.write(",".join(str(item) for item in counts))
            handle.write("\n")
            emitted.append({
                "start": start,
                "rows": args.rows,
                "total_assignments": sum(counts),
                "active_experts": sum(1 for item in counts if item),
                "topk_rows": window,
            })

    metadata = {
        "route_jsonl": str(args.route_jsonl),
        "layer_regex": args.layer_regex,
        "rows": args.rows,
        "starts": args.starts,
        "num_experts": args.num_experts,
        "emitted_windows": emitted,
    }
    if args.metadata_out:
        args.metadata_out.write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
    else:
        print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
