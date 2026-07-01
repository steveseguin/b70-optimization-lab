#!/usr/bin/env python3
"""Convert replay-digest MoE rows into route-count JSONL records.

The grouped-GEMM microbenchmarks use the older route-capture schema:
one JSON object per route window with a 256-entry ``counts`` vector and,
when available, a ``topk_ids`` row list. The replay digest stores the same
route distribution in a compact fixed-width row: header fields followed by
expert/count pairs. This converter bridges those formats without changing
the route data.
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import Any


MAGIC = 0x51573336444947


def expand_inputs(patterns: list[str]) -> list[str]:
    paths: list[str] = []
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        if matches:
            paths.extend(matches)
        else:
            paths.append(pattern)
    return paths


def parse_int_set(value: str) -> set[int]:
    out: set[int] = set()
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            parts = item.split(":")
            if len(parts) not in (2, 3):
                raise argparse.ArgumentTypeError(
                    f"bad range {item!r}; expected start:stop[:step]"
                )
            start = int(parts[0])
            stop = int(parts[1])
            step = int(parts[2]) if len(parts) == 3 else 1
            if step == 0:
                raise argparse.ArgumentTypeError("range step cannot be zero")
            out.update(range(start, stop, step))
        else:
            out.add(int(item))
    if not out:
        raise argparse.ArgumentTypeError("expected at least one integer")
    return out


def row_fields(values: list[int]) -> dict[str, int]:
    return {
        "magic": values[0],
        "sequence": values[1],
        "layer_index": values[2],
        "num_rows": values[3],
        "topk": values[4],
        "num_experts": values[5],
        "hidden_size": values[6],
        "rows_sum": values[7],
        "rows_nonzero": values[8],
        "rows_max": values[9],
        "route_hash": values[10],
        "row_hash": values[11],
        "output_numel": values[12],
        "output_bytes": values[13],
        "output_hash": values[14],
        "valid_marker": values[15],
    }


def count_vector_from_digest(values: list[int], num_experts: int) -> list[int]:
    counts = [0] * num_experts
    for idx in range(16, len(values) - 1, 2):
        expert = int(values[idx])
        count = int(values[idx + 1])
        if expert < 0 or count <= 0:
            continue
        if expert >= num_experts:
            raise ValueError(
                f"expert index {expert} outside [0, {num_experts})"
            )
        counts[expert] += count
    return counts


def topk_rows_from_counts(counts: list[int], num_rows: int, topk: int) -> list[list[int]]:
    if num_rows != 1:
        return []
    experts: list[int] = []
    for expert, count in enumerate(counts):
        experts.extend([expert] * int(count))
    if len(experts) != topk:
        return []
    return [experts]


def convert(args: argparse.Namespace) -> dict[str, Any]:
    paths = expand_inputs(args.inputs)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    loaded_records = 0
    loaded_rows = 0
    emitted = 0
    skipped_invalid = 0
    skipped_filter = 0
    skipped_mismatch = 0
    layers: dict[int, int] = {}
    workers: dict[str, int] = {}

    with out_path.open("w", encoding="utf-8") as out:
        for path in paths:
            with Path(path).open("r", encoding="utf-8") as handle:
                for lineno, line in enumerate(handle, 1):
                    line = line.strip()
                    if not line:
                        continue
                    loaded_records += 1
                    record = json.loads(line)
                    rank = str(record.get("rank", ""))
                    local_rank = str(record.get("local_rank", ""))
                    device = str(record.get("device", ""))
                    worker = (
                        f"rank:{rank}" if rank else
                        (f"local_rank:{local_rank}" if local_rank else f"device:{device}")
                    )
                    if (
                        args.local_ranks is not None
                        and local_rank
                        and int(local_rank) not in args.local_ranks
                    ):
                        skipped_filter += len(record.get("rows", []))
                        continue
                    for row in record.get("rows", []):
                        loaded_rows += 1
                        values = row.get("values")
                        if not isinstance(values, list) or len(values) < 16:
                            skipped_invalid += 1
                            continue
                        try:
                            values_i = [int(value) for value in values]
                            fields = row_fields(values_i)
                        except Exception:
                            skipped_invalid += 1
                            continue
                        if (
                            fields["magic"] != MAGIC
                            or fields["valid_marker"] != 1
                            or fields["layer_index"] < 0
                        ):
                            skipped_invalid += 1
                            continue
                        if (
                            args.num_rows is not None
                            and fields["num_rows"] not in args.num_rows
                        ):
                            skipped_filter += 1
                            continue
                        if (
                            args.layers is not None
                            and fields["layer_index"] not in args.layers
                        ):
                            skipped_filter += 1
                            continue
                        counts = count_vector_from_digest(
                            values_i,
                            fields["num_experts"],
                        )
                        if sum(counts) != fields["rows_sum"]:
                            skipped_mismatch += 1
                            if not args.allow_mismatch:
                                continue
                        topk_ids = topk_rows_from_counts(
                            counts,
                            fields["num_rows"],
                            fields["topk"],
                        )
                        layer_idx = int(fields["layer_index"])
                        route_record = {
                            "ts": record.get("ts"),
                            "pid": record.get("pid"),
                            "rank": rank,
                            "local_rank": local_rank,
                            "device": device,
                            "worker": worker,
                            "layer": (
                                "language_model.model.layers."
                                f"{layer_idx}.mlp.experts"
                            ),
                            "layer_index": layer_idx,
                            "stage": args.stage,
                            "call": fields["sequence"],
                            "shape": [fields["num_rows"], fields["topk"]],
                            "num_tokens": fields["num_rows"],
                            "top_k": fields["topk"],
                            "num_experts": fields["num_experts"],
                            "assignments": fields["rows_sum"],
                            "nonzero_experts": sum(1 for count in counts if count > 0),
                            "max_rows_per_expert": max(counts) if counts else 0,
                            "counts": counts,
                            "topk_ids": topk_ids,
                            "route_hash": fields["route_hash"],
                            "row_hash": fields["row_hash"],
                            "output_hash": fields["output_hash"],
                            "digest_sequence": fields["sequence"],
                            "digest_slot": row.get("slot"),
                            "source": path,
                            "source_lineno": lineno,
                        }
                        out.write(json.dumps(route_record, sort_keys=True) + "\n")
                        emitted += 1
                        layers[layer_idx] = layers.get(layer_idx, 0) + 1
                        workers[worker] = workers.get(worker, 0) + 1
                        if args.limit and emitted >= args.limit:
                            break
                    if args.limit and emitted >= args.limit:
                        break
            if args.limit and emitted >= args.limit:
                break

    return {
        "inputs": paths,
        "out": str(out_path),
        "loaded_records": loaded_records,
        "loaded_rows": loaded_rows,
        "emitted_rows": emitted,
        "skipped_invalid": skipped_invalid,
        "skipped_filter": skipped_filter,
        "skipped_mismatch": skipped_mismatch,
        "filters": {
            "layers": sorted(args.layers) if args.layers is not None else None,
            "num_rows": sorted(args.num_rows) if args.num_rows is not None else None,
            "local_ranks": (
                sorted(args.local_ranks) if args.local_ranks is not None else None
            ),
            "stage": args.stage,
            "limit": args.limit,
        },
        "layers": {str(key): value for key, value in sorted(layers.items())},
        "workers": dict(sorted(workers.items())),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="Replay-digest JSONL path/glob")
    parser.add_argument("--out", required=True, help="Output route-count JSONL")
    parser.add_argument("--metadata-out", help="Optional conversion summary JSON")
    parser.add_argument("--layers", type=parse_int_set)
    parser.add_argument("--num-rows", type=parse_int_set)
    parser.add_argument("--local-ranks", type=parse_int_set)
    parser.add_argument("--stage", default="quark_int8_apply")
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--allow-mismatch",
        action="store_true",
        help="Emit rows even if compact counts do not sum to digest rows_sum.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = convert(args)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.metadata_out:
        path = Path(args.metadata_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
