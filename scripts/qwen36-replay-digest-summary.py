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


def parse_csv_ints(value: str) -> list[int]:
    out = []
    for item in value.split(","):
        item = item.strip()
        if item:
            out.append(int(item))
    if not out:
        raise argparse.ArgumentTypeError("expected at least one integer")
    return out


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


def summarize(
    paths: list[str],
    top_n: int,
    *,
    num_rows_filter: set[int] | None,
) -> dict[str, Any]:
    record_count = 0
    row_count = 0
    filtered_out_rows = 0
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
    route_hash_rows_by_layer: Counter[tuple[int, int]] = Counter()
    route_hash_routed_rows_by_layer: Counter[tuple[int, int]] = Counter()
    route_hash_rows_by_worker_layer: Counter[tuple[str, int, int]] = Counter()
    route_hash_routed_rows_by_worker_layer: Counter[tuple[str, int, int]] = Counter()
    route_shape_hash_rows_by_layer: Counter[tuple[int, str, int]] = Counter()
    route_row_hash_rows_by_layer: Counter[tuple[int, int, int]] = Counter()
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
                    if (
                        num_rows_filter is not None
                        and int(fields["num_rows"]) not in num_rows_filter
                    ):
                        filtered_out_rows += 1
                        continue
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
                    route_hash = int(fields["route_hash"])
                    row_hash = int(fields["row_hash"])
                    rows_sum = int(fields["rows_sum"])
                    route_hash_rows_by_layer[(layer, route_hash)] += 1
                    route_hash_routed_rows_by_layer[(layer, route_hash)] += rows_sum
                    route_hash_rows_by_worker_layer[(worker, layer, route_hash)] += 1
                    route_hash_routed_rows_by_worker_layer[(worker, layer, route_hash)] += rows_sum
                    route_shape_hash_rows_by_layer[(layer, str(shape), route_hash)] += 1
                    route_row_hash_rows_by_layer[(layer, route_hash, row_hash)] += 1
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
    unique_route_hashes_by_layer = {}
    route_hash_coverage_by_layer = {}
    top_route_hashes_by_layer: dict[str, list[dict[str, Any]]] = {}
    for layer in sorted(layer_counts):
        layer_route_items = [
            (route_hash, count)
            for (route_layer, route_hash), count in route_hash_rows_by_layer.items()
            if route_layer == layer
        ]
        if not layer_route_items:
            continue
        unique_route_hashes_by_layer[str(layer)] = len(layer_route_items)
        by_records = Counter({route_hash: count for route_hash, count in layer_route_items})
        top_records = by_records.most_common(top_n)
        layer_record_denom = int(layer_counts[layer])
        layer_routed_denom = int(rows_sum_by_layer[layer])
        route_hash_coverage_by_layer[str(layer)] = {
            "unique_route_hashes": len(layer_route_items),
            "digest_rows": layer_record_denom,
            "routed_rows": layer_routed_denom,
        }
        for k in (1, 4, 8, 16):
            selected = top_records[:k]
            selected_records = sum(count for _route_hash, count in selected)
            selected_routed = sum(
                int(route_hash_routed_rows_by_layer[(layer, route_hash)])
                for route_hash, _count in selected
            )
            route_hash_coverage_by_layer[str(layer)][f"top{k}_digest_row_coverage"] = (
                selected_records / layer_record_denom if layer_record_denom else 0.0
            )
            route_hash_coverage_by_layer[str(layer)][f"top{k}_routed_row_coverage"] = (
                selected_routed / layer_routed_denom if layer_routed_denom else 0.0
            )
        top_route_hashes_by_layer[str(layer)] = [
            {
                "route_hash": str(route_hash),
                "digest_rows": int(record_count_for_hash),
                "digest_row_coverage": (
                    record_count_for_hash / layer_record_denom
                    if layer_record_denom else 0.0
                ),
                "routed_rows": int(route_hash_routed_rows_by_layer[(layer, route_hash)]),
                "routed_row_coverage": (
                    route_hash_routed_rows_by_layer[(layer, route_hash)] / layer_routed_denom
                    if layer_routed_denom else 0.0
                ),
            }
            for route_hash, record_count_for_hash in top_records
        ]

    top_route_hashes_by_worker_layer: dict[str, list[dict[str, Any]]] = {}
    worker_route_keys = sorted({
        (worker, layer)
        for (worker, layer, _route_hash) in route_hash_rows_by_worker_layer
    }, key=lambda item: (str(item[0]), int(item[1])))
    for worker, layer in worker_route_keys:
        by_records = Counter({
            route_hash: count
            for (route_worker, route_layer, route_hash), count in route_hash_rows_by_worker_layer.items()
            if route_worker == worker and route_layer == layer
        })
        if not by_records:
            continue
        digest_denom = int(rows_by_worker_layer[(worker, layer)])
        routed_denom = sum(
            int(count)
            for (route_worker, route_layer, _route_hash), count in route_hash_routed_rows_by_worker_layer.items()
            if route_worker == worker and route_layer == layer
        )
        top_route_hashes_by_worker_layer[f"{worker}:{layer}"] = [
            {
                "route_hash": str(route_hash),
                "digest_rows": int(count),
                "digest_row_coverage": count / digest_denom if digest_denom else 0.0,
                "routed_rows": int(route_hash_routed_rows_by_worker_layer[(worker, layer, route_hash)]),
                "routed_row_coverage": (
                    route_hash_routed_rows_by_worker_layer[(worker, layer, route_hash)] / routed_denom
                    if routed_denom else 0.0
                ),
            }
            for route_hash, count in by_records.most_common(top_n)
        ]

    top_route_shape_hashes_by_layer: dict[str, list[dict[str, Any]]] = {}
    for layer in sorted(layer_counts):
        layer_items = [
            ((shape, route_hash), count)
            for (route_layer, shape, route_hash), count in route_shape_hash_rows_by_layer.items()
            if route_layer == layer
        ]
        if layer_items:
            top_route_shape_hashes_by_layer[str(layer)] = [
                {
                    "shape": shape,
                    "route_hash": str(route_hash),
                    "digest_rows": int(count),
                }
                for (shape, route_hash), count in Counter(dict(layer_items)).most_common(top_n)
            ]

    top_route_row_hashes_by_layer: dict[str, list[dict[str, Any]]] = {}
    for layer in sorted(layer_counts):
        layer_items = [
            ((route_hash, row_hash), count)
            for (route_layer, route_hash, row_hash), count in route_row_hash_rows_by_layer.items()
            if route_layer == layer
        ]
        if layer_items:
            top_route_row_hashes_by_layer[str(layer)] = [
                {
                    "route_hash": str(route_hash),
                    "row_hash": str(row_hash),
                    "digest_rows": int(count),
                }
                for (route_hash, row_hash), count in Counter(dict(layer_items)).most_common(top_n)
            ]
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
        "filters": {
            "num_rows": sorted(num_rows_filter) if num_rows_filter is not None else None,
        },
        "records": record_count,
        "rows": row_count,
        "filtered_out_rows": filtered_out_rows,
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
        "unique_route_hashes_by_layer": unique_route_hashes_by_layer,
        "route_hash_coverage_by_layer": route_hash_coverage_by_layer,
        "top_route_hashes_by_layer": top_route_hashes_by_layer,
        "top_route_hashes_by_worker_layer": top_route_hashes_by_worker_layer,
        "top_route_shape_hashes_by_layer": top_route_shape_hashes_by_layer,
        "top_route_row_hashes_by_layer": top_route_row_hashes_by_layer,
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
        f"- Filtered out rows: `{summary.get('filtered_out_rows', 0)}`",
        f"- Filters: `{summary.get('filters', {})}`",
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
    if summary.get("route_hash_coverage_by_layer"):
        lines.extend(["", "## Route Hash Coverage By Layer", ""])
        lines.extend([
            "| Layer | Unique route hashes | top1 routed | top4 routed | top8 routed | top16 routed |",
            "| ---: | ---: | ---: | ---: | ---: | ---: |",
        ])
        for layer, data in summary["route_hash_coverage_by_layer"].items():
            lines.append(
                f"| {layer} | {data['unique_route_hashes']} | "
                f"{data['top1_routed_row_coverage']:.6f} | "
                f"{data['top4_routed_row_coverage']:.6f} | "
                f"{data['top8_routed_row_coverage']:.6f} | "
                f"{data['top16_routed_row_coverage']:.6f} |"
            )
        lines.extend(["", "## Top Route Hashes By Layer", ""])
        for layer, items in summary["top_route_hashes_by_layer"].items():
            rendered = ", ".join(
                f"{item['route_hash']}:{item['digest_rows']}r/"
                f"{item['routed_row_coverage']:.3f}"
                for item in items
            )
            lines.append(f"- Layer `{layer}`: {rendered}")
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
    parser.add_argument("--num-rows", type=parse_csv_ints)
    args = parser.parse_args()

    paths = expand_inputs(args.inputs)
    missing = [path for path in paths if not Path(path).exists()]
    if missing:
        raise SystemExit(f"missing input files: {missing}")
    summary = summarize(
        paths,
        args.top_n,
        num_rows_filter=set(args.num_rows) if args.num_rows else None,
    )
    Path(args.output_json).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_out:
        write_markdown(summary, args.markdown_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
