#!/usr/bin/env python3
"""Analyze Qwen3.6 MoE route signatures for resident primitive caches.

This is a CPU-only planning tool. It separates the cheap resident oneDNN-style
primitive key from exact route-specialized keys so we can decide whether to
cache generic grouped-matmul primitives, route-specific bundles, or generated
layerlets.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import re
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from typing import Any


KEY_TYPES = (
    "primitive",
    "count_vector",
    "active_set",
    "topk_tuple",
    "count_histogram",
)


def parse_csv_ints(value: str) -> list[int]:
    out = []
    for item in value.split(","):
        item = item.strip()
        if item:
            out.append(int(item))
    if not out:
        raise argparse.ArgumentTypeError("expected at least one integer")
    return out


def expand_inputs(patterns: list[str]) -> list[str]:
    paths: list[str] = []
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        paths.extend(matches or [pattern])
    seen = set()
    deduped = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            deduped.append(path)
    return deduped


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = (len(ordered) - 1) * pct
    lo = math.floor(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return float(ordered[lo] * (1.0 - frac) + ordered[hi] * frac)


def stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "p50": None, "p90": None, "p99": None, "max": None}
    return {
        "mean": float(sum(values) / len(values)),
        "p50": percentile(values, 0.50),
        "p90": percentile(values, 0.90),
        "p99": percentile(values, 0.99),
        "max": float(max(values)),
    }


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]


def layer_index(layer: str) -> int | None:
    match = re.search(r"\.layers\.(\d+)\.", layer)
    if not match:
        return None
    return int(match.group(1))


def active_experts_from_counts(counts: list[Any]) -> tuple[int, ...]:
    return tuple(idx for idx, count in enumerate(counts) if int(count) > 0)


def count_histogram(counts: list[Any]) -> tuple[tuple[int, int], ...]:
    hist = Counter(int(count) for count in counts if int(count) > 0)
    return tuple(sorted(hist.items()))


def flatten_topk_ids(topk_ids: Any) -> tuple[tuple[int, ...], ...]:
    if not isinstance(topk_ids, list):
        return tuple()
    rows = []
    for row in topk_ids:
        if isinstance(row, list):
            rows.append(tuple(int(item) for item in row))
    return tuple(rows)


def load_records(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[str]]:
    stage_re = re.compile(args.stage_regex) if args.stage_regex else None
    layer_re = re.compile(args.layer_regex) if args.layer_regex else None
    records: list[dict[str, Any]] = []
    input_files = expand_inputs(args.inputs)
    for path in input_files:
        with open(path, "r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                record["_source"] = path
                record["_line"] = line_number
                stage = str(record.get("stage") or "")
                layer = str(record.get("layer") or "")
                if stage_re and not stage_re.search(stage):
                    continue
                if layer_re and not layer_re.search(layer):
                    continue
                num_tokens = int(record.get("num_tokens") or 0)
                if args.min_num_tokens is not None and num_tokens < args.min_num_tokens:
                    continue
                if args.max_num_tokens is not None and num_tokens > args.max_num_tokens:
                    continue
                counts = record.get("counts")
                if not isinstance(counts, list):
                    continue
                records.append(record)
    if not records:
        raise SystemExit("no route records matched filters")
    return records, input_files


def signature_parts(record: dict[str, Any]) -> dict[str, Any]:
    counts = [int(item) for item in record.get("counts") or []]
    active_set = active_experts_from_counts(counts)
    topk_tuple = flatten_topk_ids(record.get("topk_ids"))
    primitive = {
        "layer": str(record.get("layer") or ""),
        "stage": str(record.get("stage") or ""),
        "shape": record.get("shape") or [],
        "num_tokens": int(record.get("num_tokens") or 0),
        "top_k": int(record.get("top_k") or 0),
        "assignments": int(record.get("assignments") or sum(counts)),
        "num_experts": int(record.get("num_experts") or len(counts)),
    }
    return {
        "primitive": primitive,
        "count_vector": counts,
        "active_set": active_set,
        "topk_tuple": topk_tuple,
        "count_histogram": count_histogram(counts),
    }


def signature_keys(record: dict[str, Any]) -> dict[str, str | None]:
    parts = signature_parts(record)
    keys: dict[str, str | None] = {}
    for key_type in KEY_TYPES:
        value = parts[key_type]
        if key_type == "topk_tuple" and not value:
            keys[key_type] = None
        else:
            keys[key_type] = stable_hash(value)
    return keys


def lru_hit_rate(keys: list[str], capacity: int) -> dict[str, float | int]:
    if capacity <= 0:
        raise ValueError("capacity must be positive")
    cache: OrderedDict[str, None] = OrderedDict()
    hits = 0
    misses = 0
    for key in keys:
        if key in cache:
            hits += 1
            cache.move_to_end(key)
        else:
            misses += 1
            cache[key] = None
            if len(cache) > capacity:
                cache.popitem(last=False)
    total = hits + misses
    return {
        "capacity": capacity,
        "hits": hits,
        "misses": misses,
        "hit_rate": (hits / total) if total else 0.0,
    }


def summarize_key_type(
    records: list[dict[str, Any]],
    keys_by_record: list[dict[str, str | None]],
    key_type: str,
    capacities: list[int],
) -> dict[str, Any]:
    raw_keys = [row[key_type] for row in keys_by_record]
    keys = [key for key in raw_keys if key is not None]
    counter = Counter(keys)
    missing = len(raw_keys) - len(keys)
    return {
        "records": len(raw_keys),
        "available": len(keys),
        "missing": missing,
        "unique": len(counter),
        "repeat_rate": 1.0 - (len(counter) / len(keys)) if keys else 0.0,
        "top_key_share": (counter.most_common(1)[0][1] / len(keys)) if keys else 0.0,
        "lru": {str(cap): lru_hit_rate(keys, cap) for cap in capacities},
    }


def summarize_layer(
    layer: str,
    records: list[dict[str, Any]],
    capacities: list[int],
) -> dict[str, Any]:
    keys_by_record = [signature_keys(record) for record in records]
    counts_active = [float(record.get("nonzero_experts") or 0) for record in records]
    max_rows = [float(record.get("max_rows_per_expert") or 0) for record in records]
    assignments = [float(record.get("assignments") or 0) for record in records]
    stages = Counter(str(record.get("stage") or "unknown") for record in records)
    sources = Counter(str(record.get("_source") or "") for record in records)
    key_stats = {
        key_type: summarize_key_type(records, keys_by_record, key_type, capacities)
        for key_type in KEY_TYPES
    }
    active_counter = Counter(row["active_set"] for row in keys_by_record if row["active_set"])
    route_counter = Counter(row["topk_tuple"] for row in keys_by_record if row["topk_tuple"])
    return {
        "layer": layer,
        "layer_index": layer_index(layer),
        "records": len(records),
        "stages": dict(sorted(stages.items())),
        "sources": dict(sorted(sources.items())),
        "nonzero_experts": stats(counts_active),
        "max_rows_per_expert": stats(max_rows),
        "assignments": stats(assignments),
        "key_stats": key_stats,
        "top_active_sets": [
            {"key": key, "count": int(count)}
            for key, count in active_counter.most_common(8)
        ],
        "top_ordered_routes": [
            {"key": key, "count": int(count)}
            for key, count in route_counter.most_common(8)
        ],
    }


def summarize(records: list[dict[str, Any]], input_files: list[str],
              capacities: list[int]) -> dict[str, Any]:
    keys_by_record = [signature_keys(record) for record in records]
    by_layer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_layer[str(record.get("layer") or "")].append(record)
    layers = {
        layer: summarize_layer(layer, rows, capacities)
        for layer, rows in sorted(
            by_layer.items(),
            key=lambda item: (layer_index(item[0]) if layer_index(item[0]) is not None else 9999, item[0]),
        )
    }
    return {
        "input_files": input_files,
        "records": len(records),
        "layers": layers,
        "layer_count": len(layers),
        "capacities": capacities,
        "overall_key_stats": {
            key_type: summarize_key_type(records, keys_by_record, key_type, capacities)
            for key_type in KEY_TYPES
        },
    }


def fmt_pct(value: float | None) -> str:
    if value is None:
        return ""
    return f"{100.0 * value:.1f}%"


def make_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Qwen3.6 Route Signature Cache Analysis",
        "",
        f"Inputs: `{', '.join(summary['input_files'])}`",
        f"Records: `{summary['records']}`",
        f"Layers: `{summary['layer_count']}`",
        "",
        "## Overall Cache Keys",
        "",
        "| key type | available | missing | unique | repeat rate | LRU@4 | LRU@16 | LRU@40 | LRU@64 | LRU@128 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key_type in KEY_TYPES:
        row = summary["overall_key_stats"][key_type]
        lru = row["lru"]
        def hit(cap: int) -> str:
            item = lru.get(str(cap))
            return fmt_pct(item["hit_rate"]) if item else ""
        lines.append(
            f"| `{key_type}` | {row['available']} | {row['missing']} | "
            f"{row['unique']} | {fmt_pct(row['repeat_rate'])} | "
            f"{hit(4)} | {hit(16)} | {hit(40)} | {hit(64)} | {hit(128)} |"
        )

    lines.extend([
        "",
        "## Layer Summary",
        "",
        "| layer | records | primitive unique | active-set unique | route unique | "
        "active repeat | route repeat | route missing | primitive LRU@40 | active LRU@40 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for layer, row in summary["layers"].items():
        ks = row["key_stats"]
        primitive = ks["primitive"]
        active = ks["active_set"]
        route = ks["topk_tuple"]
        primitive_lru40 = primitive["lru"].get("40", {}).get("hit_rate")
        active_lru40 = active["lru"].get("40", {}).get("hit_rate")
        lines.append(
            f"| `{layer}` | {row['records']} | {primitive['unique']} | "
            f"{active['unique']} | {route['unique']} | "
            f"{fmt_pct(active['repeat_rate'])} | {fmt_pct(route['repeat_rate'])} | "
            f"{route['missing']} | {fmt_pct(primitive_lru40)} | {fmt_pct(active_lru40)} |"
        )

    lines.extend([
        "",
        "## Interpretation",
        "",
        "- `primitive` approximates a resident oneDNN grouped-matmul key with mutable",
        "  offsets/counts. High LRU hit rates here mean primitive construction can",
        "  move to startup or a small per-layer cache.",
        "- `active_set` and `topk_tuple` approximate route-specialized layerlets.",
        "  Low reuse here means generated kernels should target route classes or",
        "  hot-expert sets, not exact ordered routes.",
        "- Endpoint promotion still requires exact route replay and accepted-service",
        "  provenance; this analysis only decides which cache design is plausible.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--stage-regex", default=r"^quark_int8_apply$")
    parser.add_argument("--layer-regex", default=r"mlp[.]experts")
    parser.add_argument("--min-num-tokens", type=int, default=None)
    parser.add_argument("--max-num-tokens", type=int, default=None)
    parser.add_argument("--capacities", type=parse_csv_ints, default=parse_csv_ints("1,2,4,8,16,32,40,64,128,256,512"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--markdown-out")
    args = parser.parse_args()

    records, input_files = load_records(args)
    report = summarize(records, input_files, args.capacities)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.markdown_out:
        md = Path(args.markdown_out)
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(make_markdown(report))
    print(json.dumps({
        "out": str(out),
        "records": report["records"],
        "layers": report["layer_count"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
