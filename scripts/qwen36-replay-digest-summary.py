#!/usr/bin/env python3
"""Summarize Qwen3.6 XPU MoE replay digest JSONL files."""

from __future__ import annotations

import argparse
import glob
import json
from collections import Counter, defaultdict
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


def row_fields(values: list[int]) -> dict[str, Any]:
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


def hot_expert_pairs(values: list[int]) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for idx in range(16, len(values) - 1, 2):
        expert = int(values[idx])
        count = int(values[idx + 1])
        if expert >= 0 and count > 0:
            pairs.append((expert, count))
    return pairs


def counter_to_dict(counter: Counter[Any]) -> dict[str, int]:
    return {str(key): int(value) for key, value in sorted(counter.items(), key=lambda item: str(item[0]))}


def top_counter(counter: Counter[Any], limit: int) -> list[list[Any]]:
    return [[key, int(value)] for key, value in counter.most_common(limit)]


def worker_key(rank: str, local_rank: str, device: str) -> str:
    if rank:
        return f"rank:{rank}"
    if local_rank:
        return f"local_rank:{local_rank}"
    return f"device:{device}"


def summarize(paths: list[str], top_n: int) -> dict[str, Any]:
    record_count = 0
    row_count = 0
    valid_magic_rows = 0
    invalid_rows = 0
    first_counter: int | None = None
    last_counter: int | None = None
    rank_records: Counter[str] = Counter()
    local_rank_records: Counter[str] = Counter()
    device_records: Counter[str] = Counter()
    rank_rows: Counter[str] = Counter()
    local_rank_rows: Counter[str] = Counter()
    device_rows: Counter[str] = Counter()
    worker_rows: Counter[str] = Counter()
    layer_counts: Counter[int] = Counter()
    shape_summaries: Counter[str] = Counter()
    route_hashes: set[tuple[Any, ...]] = set()
    route_by_rank_layer: dict[str, set[int]] = defaultdict(set)
    layers_by_rank: dict[str, set[int]] = defaultdict(set)
    layers_by_worker: dict[str, set[int]] = defaultdict(set)
    rows_by_rank_layer: Counter[tuple[str, int]] = Counter()
    rows_by_worker_layer: Counter[tuple[str, int]] = Counter()
    non_negative_layer_rows = 0
    negative_layer_rows = 0
    max_rows_nonzero = 0
    max_rows_max = 0
    max_columns = 0
    hot_pair_observations = 0
    rows_with_hot_pairs = 0
    rows_sum_by_layer: Counter[int] = Counter()
    hot_count_sum_by_layer: Counter[int] = Counter()
    hot_expert_overall: Counter[str] = Counter()
    hot_expert_by_layer: Counter[tuple[int, int]] = Counter()
    hot_expert_by_worker_layer: Counter[tuple[str, int, int]] = Counter()

    for path in paths:
        with open(path, "r", encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise SystemExit(f"{path}:{lineno}: JSON decode failed: {exc}") from exc
                record_count += 1
                rank = str(record.get("rank", ""))
                local_rank = str(record.get("local_rank", ""))
                device = str(record.get("device", ""))
                worker = worker_key(rank, local_rank, device)
                rank_records[rank] += 1
                local_rank_records[local_rank] += 1
                device_records[device] += 1
                counter = record.get("counter")
                if isinstance(counter, int):
                    first_counter = counter if first_counter is None else min(first_counter, counter)
                    last_counter = counter if last_counter is None else max(last_counter, counter)
                for row in record.get("rows", []):
                    values = row.get("values")
                    if not isinstance(values, list) or len(values) < 16:
                        invalid_rows += 1
                        continue
                    try:
                        values_i = [int(value) for value in values]
                    except Exception:
                        invalid_rows += 1
                        continue
                    max_columns = max(max_columns, len(values_i))
                    fields = row_fields(values_i)
                    row_count += 1
                    rank_rows[rank] += 1
                    local_rank_rows[local_rank] += 1
                    device_rows[device] += 1
                    worker_rows[worker] += 1
                    if fields["magic"] == MAGIC and fields["valid_marker"] == 1:
                        valid_magic_rows += 1
                    else:
                        invalid_rows += 1
                    layer = int(fields["layer_index"])
                    layer_counts[layer] += 1
                    rows_sum_by_layer[layer] += int(fields["rows_sum"])
                    layers_by_rank[rank].add(layer)
                    layers_by_worker[worker].add(layer)
                    rows_by_rank_layer[(rank, layer)] += 1
                    rows_by_worker_layer[(worker, layer)] += 1
                    if layer >= 0:
                        non_negative_layer_rows += 1
                    else:
                        negative_layer_rows += 1
                    shape = (
                        fields["num_rows"],
                        fields["topk"],
                        fields["num_experts"],
                        fields["hidden_size"],
                    )
                    shape_summaries[str(shape)] += 1
                    route_key = (
                        worker,
                        layer,
                        fields["num_rows"],
                        fields["route_hash"],
                        fields["row_hash"],
                        fields["output_hash"],
                    )
                    route_hashes.add(route_key)
                    route_by_rank_layer[f"{worker}:{layer}"].add(fields["route_hash"])
                    max_rows_nonzero = max(max_rows_nonzero, int(fields["rows_nonzero"]))
                    max_rows_max = max(max_rows_max, int(fields["rows_max"]))
                    pairs = hot_expert_pairs(values_i)
                    if pairs:
                        rows_with_hot_pairs += 1
                    for expert, count in pairs:
                        hot_pair_observations += 1
                        hot_count_sum_by_layer[layer] += count
                        hot_expert_overall[f"layer:{layer}:expert:{expert}"] += count
                        hot_expert_by_layer[(layer, expert)] += count
                        hot_expert_by_worker_layer[(worker, layer, expert)] += count

    rank_layer_counts: dict[str, dict[str, int]] = defaultdict(dict)
    for (rank, layer), count in rows_by_rank_layer.items():
        rank_layer_counts[str(rank)][str(layer)] = int(count)
    worker_layer_counts: dict[str, dict[str, int]] = defaultdict(dict)
    for (worker, layer), count in rows_by_worker_layer.items():
        worker_layer_counts[str(worker)][str(layer)] = int(count)

    layers_by_rank_out = {
        str(rank): sorted(int(layer) for layer in layers)
        for rank, layers in sorted(layers_by_rank.items(), key=lambda item: str(item[0]))
    }
    layers_by_worker_out = {
        str(worker): sorted(int(layer) for layer in layers)
        for worker, layers in sorted(layers_by_worker.items(), key=lambda item: str(item[0]))
    }
    unique_route_hashes_by_rank_layer = {
        key: len(value)
        for key, value in sorted(route_by_rank_layer.items(), key=lambda item: item[0])
    }
    hot_by_layer_out: dict[str, list[list[int]]] = {}
    hot_unique_by_layer: dict[str, int] = {}
    for layer in sorted(layer_counts):
        layer_counter = Counter({
            expert: count
            for (hot_layer, expert), count in hot_expert_by_layer.items()
            if hot_layer == layer
        })
        if layer_counter:
            hot_by_layer_out[str(layer)] = [
                [int(expert), int(count)]
                for expert, count in layer_counter.most_common(top_n)
            ]
            hot_unique_by_layer[str(layer)] = int(len(layer_counter))

    hot_by_worker_layer_out: dict[str, list[list[int]]] = {}
    worker_layer_keys = sorted({
        (worker, layer)
        for (worker, layer, _expert) in hot_expert_by_worker_layer
    }, key=lambda item: (str(item[0]), int(item[1])))
    for worker, layer in worker_layer_keys:
        layer_counter = Counter({
            expert: count
            for (hot_worker, hot_layer, expert), count in hot_expert_by_worker_layer.items()
            if hot_worker == worker and hot_layer == layer
        })
        if layer_counter:
            hot_by_worker_layer_out[f"{worker}:{layer}"] = [
                [int(expert), int(count)]
                for expert, count in layer_counter.most_common(top_n)
            ]

    hot_coverage_by_layer = {}
    for layer, rows_sum in sorted(rows_sum_by_layer.items()):
        hot_sum = int(hot_count_sum_by_layer[layer])
        denom = int(rows_sum)
        hot_coverage_by_layer[str(layer)] = {
            "hot_count_sum": hot_sum,
            "rows_sum": denom,
            "coverage": (hot_sum / denom) if denom else None,
        }

    return {
        "sources": paths,
        "records": record_count,
        "rows": row_count,
        "valid_magic_rows": valid_magic_rows,
        "invalid_rows": invalid_rows,
        "first_counter": first_counter,
        "last_counter": last_counter,
        "rank_records": counter_to_dict(rank_records),
        "local_rank_records": counter_to_dict(local_rank_records),
        "device_records": counter_to_dict(device_records),
        "rank_rows": counter_to_dict(rank_rows),
        "local_rank_rows": counter_to_dict(local_rank_rows),
        "device_rows": counter_to_dict(device_rows),
        "worker_rows": counter_to_dict(worker_rows),
        "layer_counts": counter_to_dict(layer_counts),
        "layers_by_rank": layers_by_rank_out,
        "layers_by_worker": layers_by_worker_out,
        "rank_layer_counts": dict(sorted(rank_layer_counts.items())),
        "worker_layer_counts": dict(sorted(worker_layer_counts.items())),
        "non_negative_layer_rows": non_negative_layer_rows,
        "negative_layer_rows": negative_layer_rows,
        "unique_layers": sorted(int(layer) for layer in layer_counts),
        "unique_shape_summaries": len(shape_summaries),
        "top_shape_summaries": top_counter(shape_summaries, top_n),
        "unique_digest_combos": len(route_hashes),
        "unique_route_hashes_by_rank_layer": unique_route_hashes_by_rank_layer,
        "max_rows_nonzero": max_rows_nonzero,
        "max_rows_max": max_rows_max,
        "max_columns": max_columns,
        "hot_columns_detected": max(0, (max_columns - 16) // 2),
        "hot_pair_observations": hot_pair_observations,
        "rows_with_hot_pairs": rows_with_hot_pairs,
        "top_hot_experts_overall": top_counter(hot_expert_overall, top_n),
        "top_hot_experts_by_layer": hot_by_layer_out,
        "top_hot_experts_by_worker_layer": hot_by_worker_layer_out,
        "unique_hot_experts_by_layer": hot_unique_by_layer,
        "hot_coverage_by_layer": hot_coverage_by_layer,
    }


def write_markdown(summary: dict[str, Any], path: str) -> None:
    lines = [
        "# Qwen3.6 Replay Digest Summary",
        "",
        f"- Sources: `{len(summary['sources'])}`",
        f"- Records: `{summary['records']}`",
        f"- Rows: `{summary['rows']}`",
        f"- Valid magic rows: `{summary['valid_magic_rows']}`",
        f"- Invalid rows: `{summary['invalid_rows']}`",
        f"- Counter range: `{summary['first_counter']}` to `{summary['last_counter']}`",
        f"- Rank records: `{summary['rank_records']}`",
        f"- Rank rows: `{summary['rank_rows']}`",
        f"- Device rows: `{summary['device_rows']}`",
        f"- Worker rows: `{summary['worker_rows']}`",
        f"- Non-negative layer rows: `{summary['non_negative_layer_rows']}`",
        f"- Negative layer rows: `{summary['negative_layer_rows']}`",
        f"- Unique layers: `{summary['unique_layers']}`",
        f"- Unique shape summaries: `{summary['unique_shape_summaries']}`",
        f"- Unique digest combos: `{summary['unique_digest_combos']}`",
        f"- Max rows_nonzero: `{summary['max_rows_nonzero']}`",
        f"- Max rows_max: `{summary['max_rows_max']}`",
        f"- Max columns: `{summary['max_columns']}`",
        f"- Hot columns detected: `{summary['hot_columns_detected']}`",
        f"- Hot pair observations: `{summary['hot_pair_observations']}`",
        f"- Rows with hot pairs: `{summary['rows_with_hot_pairs']}`",
        "",
        "## Top Shapes",
        "",
        "| Shape `(num_rows, topk, experts, hidden)` | Rows |",
        "| --- | ---: |",
    ]
    for shape, count in summary["top_shape_summaries"]:
        lines.append(f"| `{shape}` | {count} |")
    lines.extend(["", "## Rank Layer Coverage", ""])
    for worker, layers in summary["layers_by_worker"].items():
        lines.append(f"- Worker `{worker}`: `{len(layers)}` layers, `{layers}`")
    if summary.get("hot_pair_observations"):
        lines.extend(["", "## Top Hot Experts Overall", ""])
        lines.extend(["| Layer/expert | Routed rows |", "| --- | ---: |"])
        for key, count in summary["top_hot_experts_overall"]:
            lines.append(f"| `{key}` | {count} |")
        lines.extend(["", "## Hot Coverage By Layer", ""])
        lines.extend(["| Layer | Hot routed rows | Total routed rows | Coverage |", "| ---: | ---: | ---: | ---: |"])
        for layer, data in summary["hot_coverage_by_layer"].items():
            coverage = data["coverage"]
            coverage_s = "" if coverage is None else f"{coverage:.6f}"
            lines.append(
                f"| {layer} | {data['hot_count_sum']} | {data['rows_sum']} | {coverage_s} |"
            )
        lines.extend(["", "## Top Hot Experts By Layer", ""])
        for layer, items in summary["top_hot_experts_by_layer"].items():
            rendered = ", ".join(f"{expert}:{count}" for expert, count in items)
            lines.append(f"- Layer `{layer}`: {rendered}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", help="JSONL file paths or glob patterns")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--markdown-out")
    parser.add_argument("--top-n", type=int, default=16)
    args = parser.parse_args()

    paths = expand_inputs(args.inputs)
    missing = [path for path in paths if not Path(path).exists()]
    if missing:
        raise SystemExit(f"missing input files: {missing}")
    summary = summarize(paths, args.top_n)
    Path(args.output_json).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_out:
        write_markdown(summary, args.markdown_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
