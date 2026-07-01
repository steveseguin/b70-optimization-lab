#!/usr/bin/env python3
"""Build layer-gated hotset manifests from Qwen3.6 MoE route JSONL files."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any


def parse_input(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("expected LABEL=PATH")
    label, path = value.split("=", 1)
    label = label.strip()
    if not label:
        raise argparse.ArgumentTypeError("input label cannot be empty")
    return label, Path(path)


def parse_ints(value: str) -> list[int]:
    out = []
    for item in value.split(","):
        item = item.strip()
        if item:
            out.append(int(item))
    if not out:
        raise argparse.ArgumentTypeError("expected at least one integer")
    return out


def layer_index(layer: str) -> int | None:
    match = re.search(r"layers[.](\d+)[.]", layer)
    return int(match.group(1)) if match else None


def coverage(counts: list[int], experts: set[int]) -> float:
    total = sum(counts)
    if total <= 0:
        return 0.0
    return sum(counts[idx] for idx in experts if 0 <= idx < len(counts)) / total


def top_ids_from_counts(counts: list[int], size: int) -> list[int]:
    return [
        idx for idx, value in sorted(
            enumerate(counts),
            key=lambda item: (item[1], -item[0]),
            reverse=True,
        )
        if value > 0
    ][:size]


def quantile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return ordered[low]
    frac = pos - low
    return ordered[low] * (1.0 - frac) + ordered[high] * frac


def load_source(
    *,
    label: str,
    path: Path,
    stage_pattern: re.Pattern[str] | None,
    min_num_tokens: int | None,
    max_num_tokens: int | None,
    target_indices: set[int] | None,
) -> dict[str, Any]:
    loaded = 0
    matched = 0
    layers: dict[str, dict[str, Any]] = {}

    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            loaded += 1
            record = json.loads(line)
            stage = str(record.get("stage") or "")
            if stage_pattern and not stage_pattern.search(stage):
                continue
            num_tokens = int(record.get("num_tokens") or 0)
            if min_num_tokens is not None and num_tokens < min_num_tokens:
                continue
            if max_num_tokens is not None and num_tokens > max_num_tokens:
                continue
            layer = str(record.get("layer") or "")
            idx = layer_index(layer)
            if idx is None:
                continue
            if target_indices is not None and idx not in target_indices:
                continue
            counts_raw = record.get("counts")
            if not isinstance(counts_raw, list):
                continue
            counts = [int(item) for item in counts_raw]
            entry = layers.setdefault(
                layer,
                {
                    "layer": layer,
                    "layer_index": idx,
                    "records": [],
                    "counts": [0] * len(counts),
                    "has_topk_ids": False,
                },
            )
            if len(entry["counts"]) != len(counts):
                raise ValueError(f"{path} mixes expert counts for {layer}")
            for i, value in enumerate(counts):
                entry["counts"][i] += value
            entry["records"].append(record)
            if isinstance(record.get("topk_ids"), list):
                entry["has_topk_ids"] = True
            matched += 1

    layer_summaries: dict[str, dict[str, Any]] = {}
    for layer, entry in layers.items():
        counts = entry["counts"]
        active = sum(1 for item in counts if item > 0)
        assignments = sum(counts)
        layer_summaries[layer] = {
            "layer": layer,
            "layer_index": entry["layer_index"],
            "records": entry["records"],
            "counts": counts,
            "active_experts": active,
            "assignments": assignments,
            "has_topk_ids": entry["has_topk_ids"],
        }

    return {
        "label": label,
        "path": str(path),
        "records_loaded": loaded,
        "records_matched": matched,
        "layers": layer_summaries,
    }


def summarize_windows(
    records: list[dict[str, Any]],
    *,
    hotsets: dict[str, set[int]],
    window_size: int,
    limit: int,
) -> list[dict[str, Any]]:
    windows = []
    for start in range(0, max(0, len(records) - window_size + 1)):
        window = records[start:start + window_size]
        if len(window) < window_size:
            continue
        counts = [0] * len(window[0]["counts"])
        for record in window:
            for i, value in enumerate(record["counts"]):
                counts[i] += int(value)
        hot_cov = {name: coverage(counts, experts) for name, experts in hotsets.items()}
        active = sum(1 for item in counts if item > 0)
        windows.append({
            "start_index": start,
            "records": len(window),
            "assignments": sum(counts),
            "active_experts": active,
            "coverage": hot_cov,
        })
    if not windows:
        return []

    key = "combined_top32" if "combined_top32" in hotsets else sorted(hotsets)[0]
    ranked = sorted(windows, key=lambda row: row["coverage"][key])
    choices = []
    for label, pos in (
        ("low", 0),
        ("median", len(ranked) // 2),
        ("high", len(ranked) - 1),
    ):
        item = dict(ranked[pos])
        item["choice"] = label
        choices.append(item)
    # Add a few high-coverage windows for throughput-friendly replay.
    for item in sorted(windows, key=lambda row: row["coverage"][key], reverse=True)[:limit]:
        if not any(existing["start_index"] == item["start_index"] for existing in choices):
            extra = dict(item)
            extra["choice"] = "high_extra"
            choices.append(extra)
    choices.sort(key=lambda row: row["start_index"])
    return choices


def source_hotsets(counts: list[int], hot_sizes: list[int]) -> dict[str, Any]:
    out = {}
    for size in hot_sizes:
        ids = top_ids_from_counts(counts, size)
        out[str(size)] = {
            "experts": ids,
            "coverage": coverage(counts, set(ids)),
        }
    return out


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    stage_pattern = re.compile(args.stage_regex) if args.stage_regex else None
    target_indices = set(args.target_layer_indices) if args.target_layer_indices else None
    sources = [
        load_source(
            label=label,
            path=path,
            stage_pattern=stage_pattern,
            min_num_tokens=args.min_num_tokens,
            max_num_tokens=args.max_num_tokens,
            target_indices=target_indices,
        )
        for label, path in args.inputs
    ]

    layers = sorted({
        layer
        for source in sources
        for layer in source["layers"].keys()
    }, key=lambda item: (layer_index(item) or 9999, item))

    layer_entries: list[dict[str, Any]] = []
    for layer in layers:
        layer_sources = [source for source in sources if layer in source["layers"]]
        num_experts = len(layer_sources[0]["layers"][layer]["counts"])

        normalized_scores = [0.0] * num_experts
        raw_counts = [0] * num_experts
        source_entries = []
        for source in layer_sources:
            stats = source["layers"][layer]
            counts = stats["counts"]
            assignments = stats["assignments"]
            for idx, count in enumerate(counts):
                raw_counts[idx] += count
                if assignments:
                    normalized_scores[idx] += count / assignments
            source_entries.append({
                "label": source["label"],
                "path": source["path"],
                "records": len(stats["records"]),
                "assignments": assignments,
                "active_experts": stats["active_experts"],
                "has_topk_ids": stats["has_topk_ids"],
                "hotsets": source_hotsets(counts, args.hot_sizes),
            })

        combined_hotsets: dict[str, Any] = {}
        combined_sets: dict[str, set[int]] = {}
        for size in args.hot_sizes:
            normalized_ids = [
                idx for idx, score in sorted(
                    enumerate(normalized_scores),
                    key=lambda item: (item[1], -item[0]),
                    reverse=True,
                )
                if score > 0
            ][:size]
            raw_ids = top_ids_from_counts(raw_counts, size)
            normalized_set = set(normalized_ids)
            combined_sets[f"combined_top{size}"] = normalized_set
            per_source_cov = {
                item["label"]: coverage(
                    next(source for source in layer_sources if source["label"] == item["label"])["layers"][layer]["counts"],
                    normalized_set,
                )
                for item in source_entries
            }
            raw_set = set(raw_ids)
            combined_hotsets[str(size)] = {
                "source_normalized_experts": normalized_ids,
                "source_normalized_mean_coverage": (
                    sum(per_source_cov.values()) / max(1, len(per_source_cov))
                ),
                "source_normalized_min_coverage": min(per_source_cov.values()) if per_source_cov else 0.0,
                "source_normalized_per_source_coverage": per_source_cov,
                "raw_count_experts": raw_ids,
                "raw_count_coverage": coverage(raw_counts, raw_set),
            }

        top32_sets = [
            set(item["hotsets"].get("32", {}).get("experts", []))
            for item in source_entries
            if item["hotsets"].get("32", {}).get("experts")
        ]
        overlap = {
            "source_top32_union_size": len(set().union(*top32_sets)) if top32_sets else 0,
            "source_top32_intersection_size": len(set.intersection(*top32_sets)) if top32_sets else 0,
        }

        replay_sources = []
        for source in layer_sources:
            stats = source["layers"][layer]
            windows = summarize_windows(
                stats["records"],
                hotsets=combined_sets,
                window_size=args.window_size,
                limit=args.extra_high_windows,
            )
            start_indices = sorted({item["start_index"] for item in windows})
            layer_regex = rf"layers[.]{stats['layer_index']}[.]"
            commands = {
                "grouped_gemm_dry_run": (
                    "python3 scripts/bench-qwen36-route-exact-w8a8-grouped-gemm.py "
                    f"--dry-run --route-jsonl {source['path']} "
                    f"--route-layer-regex '{layer_regex}' "
                    f"--route-start-indices {','.join(str(i) for i in start_indices) or '0'} "
                    f"--route-window-size {args.window_size}"
                ),
            }
            if stats["has_topk_ids"]:
                commands["fused_moe_rows_1_16"] = (
                    "/home/steve/.venvs/vllm-xpu/bin/python "
                    "scripts/bench-qwen36-int8-moe-kernels.py "
                    f"--route-jsonl {source['path']} "
                    f"--route-layer-regex '{layer_regex}' "
                    "--rows 1,16 "
                    f"--route-start-indices {','.join(str(i) for i in start_indices) or '0'}"
                )
            replay_sources.append({
                "label": source["label"],
                "path": source["path"],
                "has_topk_ids": stats["has_topk_ids"],
                "window_choices": windows,
                "commands": commands,
            })

        recommended_size = 32
        if combined_hotsets["32"]["source_normalized_min_coverage"] < args.min_top32_coverage:
            recommended_size = 64
        layer_entries.append({
            "layer": layer,
            "layer_index": layer_index(layer),
            "source_count": len(source_entries),
            "sources": source_entries,
            "combined_hotsets": combined_hotsets,
            "overlap": overlap,
            "recommended_hotset_size": recommended_size,
            "recommended_experts": combined_hotsets[str(recommended_size)]["source_normalized_experts"],
            "replay_sources": replay_sources,
        })

    return {
        "inputs": [{"label": label, "path": str(path)} for label, path in args.inputs],
        "filters": {
            "stage_regex": args.stage_regex,
            "min_num_tokens": args.min_num_tokens,
            "max_num_tokens": args.max_num_tokens,
            "target_layer_indices": args.target_layer_indices,
        },
        "hot_sizes": args.hot_sizes,
        "window_size": args.window_size,
        "min_top32_coverage": args.min_top32_coverage,
        "layers": layer_entries,
    }


def make_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        "# Qwen3.6 MoE Hotset Manifest",
        "",
        f"Window size: `{manifest['window_size']}`",
        "",
        "## Layer Summary",
        "",
        "| layer | sources | rec | top32 mean | top32 min | top64 mean | top64 min | top32 union | top32 intersection |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for layer in manifest["layers"]:
        c32 = layer["combined_hotsets"].get("32", {})
        c64 = layer["combined_hotsets"].get("64", {})
        lines.append(
            f"| `{layer['layer']}` | {layer['source_count']} | "
            f"{layer['recommended_hotset_size']} | "
            f"{c32.get('source_normalized_mean_coverage', 0.0):.3f} | "
            f"{c32.get('source_normalized_min_coverage', 0.0):.3f} | "
            f"{c64.get('source_normalized_mean_coverage', 0.0):.3f} | "
            f"{c64.get('source_normalized_min_coverage', 0.0):.3f} | "
            f"{layer['overlap']['source_top32_union_size']} | "
            f"{layer['overlap']['source_top32_intersection_size']} |"
        )

    lines.extend(["", "## Recommended Replay Windows", ""])
    for layer in manifest["layers"]:
        lines.append(f"### Layer {layer['layer_index']}")
        lines.append("")
        lines.append(
            f"- Recommended hotset: top-{layer['recommended_hotset_size']} "
            f"with `{len(layer['recommended_experts'])}` experts."
        )
        lines.append(
            "- Expert IDs: `" + ",".join(str(item) for item in layer["recommended_experts"]) + "`"
        )
        for source in layer["replay_sources"]:
            choices = source["window_choices"]
            if not choices:
                continue
            starts = ",".join(str(item["start_index"]) for item in choices)
            lines.append(
                f"- `{source['label']}` starts: `{starts}` "
                f"(topk ids: `{source['has_topk_ids']}`)."
            )
            for command_name, command in source["commands"].items():
                lines.append(f"  - `{command_name}`: `{command}`")
        lines.append("")

    lines.extend([
        "## Promotion Rules",
        "",
        "- Hotset fast paths must preserve exact Quark W8A8 math with cold-expert fallback.",
        "- A route replay win is not enough; live promotion must reduce the accepted model-forward sync bucket.",
        "- Keep exact canaries and provenance guard before any endpoint speed claim.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", dest="inputs", action="append", type=parse_input, required=True)
    parser.add_argument("--target-layer-indices", type=parse_ints, default=parse_ints("9,20"))
    parser.add_argument("--stage-regex", default="^quark_int8_apply$")
    parser.add_argument("--min-num-tokens", type=int, default=1)
    parser.add_argument("--max-num-tokens", type=int, default=1)
    parser.add_argument("--hot-sizes", type=parse_ints, default=parse_ints("16,32,64"))
    parser.add_argument("--window-size", type=int, default=16)
    parser.add_argument("--extra-high-windows", type=int, default=3)
    parser.add_argument("--min-top32-coverage", type=float, default=0.60)
    parser.add_argument("--out", required=True)
    parser.add_argument("--markdown-out")
    args = parser.parse_args()

    manifest = build_manifest(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_out:
        md = Path(args.markdown_out)
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(make_markdown(manifest), encoding="utf-8")
    print(json.dumps({"out": str(out), "layers": len(manifest["layers"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
