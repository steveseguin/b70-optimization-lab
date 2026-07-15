#!/usr/bin/env python3
"""Compare repeated DeepSeek V4 XPU tensor-capture hashes by TP rank."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture_dir", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    rows = []
    manifests = sorted(args.capture_dir.glob("rank*-*.jsonl"))
    if not manifests:
        raise SystemExit(f"no capture manifests in {args.capture_dir}")
    for path in manifests:
        with path.open(encoding="utf-8") as handle:
            rows.extend(json.loads(line) for line in handle if line.strip())

    grouped = defaultdict(list)
    for row in rows:
        key = (
            row["rank"],
            row["layer"],
            row["stage"],
            row["tensor_name"],
        )
        grouped[key].append((row["forward"], row["raw_sha256"]))

    comparisons = []
    for key, values in sorted(
        grouped.items(),
        key=lambda item: (
            item[0][0],
            -1 if item[0][1] is None else item[0][1],
            item[0][2],
            item[0][3],
        ),
    ):
        rank, layer, stage, tensor_name = key
        values.sort()
        counts = Counter(value for _, value in values)
        modal_hash, modal_count = counts.most_common(1)[0]
        divergent = [forward for forward, value in values if value != modal_hash]
        comparisons.append(
            {
                "rank": rank,
                "layer": layer,
                "stage": stage,
                "tensor_name": tensor_name,
                "forwards": len(values),
                "unique_hashes": len(counts),
                "modal_count": modal_count,
                "divergent_forwards": divergent,
            }
        )

    layer_rows = [row for row in comparisons if row["stage"] == "layer_out"]
    divergent_layers = [row for row in layer_rows if row["unique_hashes"] > 1]
    earliest_by_rank: dict[str, int | None] = {}
    for rank in sorted({row["rank"] for row in rows}):
        layers = [
            row["layer"]
            for row in divergent_layers
            if row["rank"] == rank and row["layer"] is not None
        ]
        earliest_by_rank[str(rank)] = min(layers) if layers else None

    input_rows = [row for row in comparisons if row["stage"] == "forward_input"]
    result = {
        "capture_dir": str(args.capture_dir),
        "manifests": [str(path) for path in manifests],
        "row_count": len(rows),
        "input_hashes_stable": all(row["unique_hashes"] == 1 for row in input_rows),
        "earliest_divergent_layer_by_rank": earliest_by_rank,
        "divergent": [row for row in comparisons if row["unique_hashes"] > 1],
        "comparisons": comparisons,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered)
    print(rendered, end="")
    return 0 if result["input_hashes_stable"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
