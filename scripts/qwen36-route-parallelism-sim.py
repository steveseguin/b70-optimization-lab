#!/usr/bin/env python3
"""Route-conditioned parallelism simulator for Qwen3.6 MoE captures.

This does not run kernels. It uses captured exact top-k route histograms to
screen whether EP/TP/hot-expert replication ideas have enough shape-level upside
to justify implementation work. Treat the numbers as routing pressure and
communication proxies, not as measured tok/s.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import re
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


def parse_int_list(value: str) -> list[int]:
    out: list[int] = []
    for item in value.split(","):
        item = item.strip()
        if item:
            out.append(int(item))
    if not out:
        raise argparse.ArgumentTypeError("expected at least one integer")
    return out


def expand_inputs(patterns: list[str]) -> list[str]:
    out: list[str] = []
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        if matches:
            out.extend(matches)
        else:
            out.append(pattern)
    seen: set[str] = set()
    deduped: list[str] = []
    for path in out:
        if path not in seen:
            seen.add(path)
            deduped.append(path)
    return deduped


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (pct / 100.0) * (len(ordered) - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return float(ordered[lo])
    frac = rank - lo
    return float(ordered[lo] * (1.0 - frac) + ordered[hi] * frac)


def summarize(values: list[float]) -> dict[str, float]:
    if not values:
        return {
            "mean": 0.0,
            "p50": 0.0,
            "p90": 0.0,
            "p95": 0.0,
            "min": 0.0,
            "max": 0.0,
        }
    return {
        "mean": mean(values),
        "p50": percentile(values, 50),
        "p90": percentile(values, 90),
        "p95": percentile(values, 95),
        "min": min(values),
        "max": max(values),
    }


def source_label(path: str) -> str:
    name = Path(path).name
    name = name.replace(".jsonl", "")
    prefixes = [
        "qwen36-quark-int8-tp4-",
        "promptclass-routecapture-20260611a-routes-",
        "routecapture",
    ]
    for prefix in prefixes:
        name = name.replace(prefix, "")
    return name


def load_records(
    paths: list[str],
    *,
    layer_regex: str | None,
    stage_regex: str | None,
    min_num_tokens: int | None,
    max_num_tokens: int | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    layer_pattern = re.compile(layer_regex) if layer_regex else None
    stage_pattern = re.compile(stage_regex) if stage_regex else None
    records: list[dict[str, Any]] = []
    loaded = 0
    skipped = 0
    by_source: dict[str, int] = defaultdict(int)

    for path in paths:
        with Path(path).open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                loaded += 1
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_number}: invalid JSONL") from exc
                layer = str(record.get("layer") or "")
                stage = str(record.get("stage") or "")
                num_tokens = int(record.get("num_tokens") or 0)
                counts = record.get("counts")
                if not isinstance(counts, list):
                    skipped += 1
                    continue
                if layer_pattern and not layer_pattern.search(layer):
                    skipped += 1
                    continue
                if stage_pattern and not stage_pattern.search(stage):
                    skipped += 1
                    continue
                if min_num_tokens is not None and num_tokens < min_num_tokens:
                    skipped += 1
                    continue
                if max_num_tokens is not None and num_tokens > max_num_tokens:
                    skipped += 1
                    continue
                record["_source"] = path
                record["_label"] = source_label(path)
                records.append(record)
                by_source[path] += 1

    if not records:
        raise ValueError("No route records matched the requested filters")

    return records, {
        "input_files": paths,
        "records_loaded": loaded,
        "records_matched": len(records),
        "records_skipped": skipped,
        "records_by_source": dict(sorted(by_source.items())),
    }


def add_counts(dst: list[int], src: list[int]) -> None:
    if len(dst) != len(src):
        raise ValueError("mismatched expert count length")
    for idx, value in enumerate(src):
        dst[idx] += int(value)


def aggregate_counts(records: list[dict[str, Any]]) -> list[int]:
    first_counts = records[0]["counts"]
    counts = [0] * len(first_counts)
    for record in records:
        add_counts(counts, [int(item) for item in record["counts"]])
    return counts


def make_windows(
    records: list[dict[str, Any]],
    *,
    window_size: int,
    stride: int,
    max_windows_per_layer: int | None,
) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_key[(str(record.get("_label") or ""), str(record.get("layer") or ""))].append(record)

    windows: list[dict[str, Any]] = []
    for (label, layer), layer_records in sorted(by_key.items()):
        num_experts = int(layer_records[0].get("num_experts") or len(layer_records[0]["counts"]))
        layer_counts = aggregate_counts(layer_records)
        made_for_layer = 0
        for start in range(0, max(0, len(layer_records) - window_size + 1), stride):
            selected = layer_records[start:start + window_size]
            if len(selected) < window_size:
                continue
            counts = aggregate_counts(selected)
            windows.append({
                "label": label,
                "layer": layer,
                "start": start,
                "window_size": window_size,
                "records": len(selected),
                "num_experts": num_experts,
                "counts": counts,
                "layer_counts": layer_counts,
                "calls": [
                    record.get("call")
                    for record in selected
                    if record.get("call") is not None
                ],
            })
            made_for_layer += 1
            if max_windows_per_layer is not None and made_for_layer >= max_windows_per_layer:
                break
    if not windows:
        raise ValueError("No windows selected")
    return windows


def owner_map_contiguous(num_experts: int, groups: int) -> list[int]:
    return [min(groups - 1, expert * groups // num_experts) for expert in range(num_experts)]


def owner_map_round_robin(num_experts: int, groups: int) -> list[int]:
    return [expert % groups for expert in range(num_experts)]


def owner_map_greedy(layer_counts: list[int], groups: int) -> list[int]:
    loads = [0] * groups
    owners = [0] * len(layer_counts)
    for expert, count in sorted(
        enumerate(layer_counts), key=lambda item: item[1], reverse=True
    ):
        owner = min(range(groups), key=lambda idx: (loads[idx], idx))
        owners[expert] = owner
        loads[owner] += int(count)
    return owners


def owner_map_greedy_excluding(
    layer_counts: list[int],
    groups: int,
    excluded: set[int],
) -> list[int]:
    loads = [0] * groups
    owners = [0] * len(layer_counts)
    for expert, count in sorted(
        enumerate(layer_counts), key=lambda item: item[1], reverse=True
    ):
        if expert in excluded:
            owners[expert] = 0
            continue
        owner = min(range(groups), key=lambda idx: (loads[idx], idx))
        owners[expert] = owner
        loads[owner] += int(count)
    return owners


def rows_by_owner(counts: list[int], owners: list[int], groups: int) -> list[int]:
    rows = [0] * groups
    for expert, count in enumerate(counts):
        rows[owners[expert]] += int(count)
    return rows


def active_experts(counts: list[int]) -> int:
    return sum(1 for count in counts if count > 0)


def hotset_from_counts(counts: list[int], size: int) -> set[int]:
    return {
        expert
        for expert, count in sorted(
            enumerate(counts), key=lambda item: item[1], reverse=True
        )[:size]
        if count > 0
    }


def greedy_assign_hot_rows(
    *,
    counts: list[int],
    cold_owners: list[int],
    hotset: set[int],
    groups: int,
) -> tuple[list[int], list[int]]:
    loads = [0] * groups
    cold_rows = [0] * groups
    hot_items: list[tuple[int, int]] = []
    for expert, count in enumerate(counts):
        count = int(count)
        if count <= 0:
            continue
        if expert in hotset:
            hot_items.append((expert, count))
        else:
            owner = cold_owners[expert]
            loads[owner] += count
            cold_rows[owner] += count
    for _, count in sorted(hot_items, key=lambda item: item[1], reverse=True):
        owner = min(range(groups), key=lambda idx: (loads[idx], idx))
        loads[owner] += count
    return loads, cold_rows


def pressure_from_rows(
    rows: list[int],
    *,
    total_rows: int,
    baseline_tp: int,
    inner_tp: int,
) -> float:
    if total_rows <= 0:
        return 0.0
    baseline_rank_work = total_rows / float(baseline_tp)
    candidate_rank_work = max(rows) / float(inner_tp)
    return candidate_rank_work / baseline_rank_work


def expert_memory_relative(
    *,
    num_experts: int,
    groups: int,
    hotset: set[int],
    baseline_tp: int,
) -> float:
    # Memory is a capacity lower bound: in an implementation we would balance
    # cold expert ownership by expert count, then tune the route placement within
    # that capacity. Route load and memory pressure are intentionally reported as
    # separate risks.
    cold_experts = max(0, num_experts - len(hotset))
    max_full_experts = len(hotset) + math.ceil(cold_experts / float(groups))
    baseline_full_expert_equiv = num_experts / float(baseline_tp)
    return max_full_experts / baseline_full_expert_equiv


def simulate_window(
    window: dict[str, Any],
    *,
    baseline_tp: int,
    gpu_count: int,
    hotset_sizes: list[int],
) -> list[dict[str, Any]]:
    counts = [int(item) for item in window["counts"]]
    layer_counts = [int(item) for item in window["layer_counts"]]
    total_rows = sum(counts)
    num_experts = int(window["num_experts"])
    if total_rows <= 0:
        return []

    policies = [
        ("ep4_contiguous", gpu_count, 1, owner_map_contiguous(num_experts, gpu_count)),
        ("ep4_round_robin", gpu_count, 1, owner_map_round_robin(num_experts, gpu_count)),
        ("ep4_greedy_static", gpu_count, 1, owner_map_greedy(layer_counts, gpu_count)),
        ("tp2_ep2_contiguous", 2, 2, owner_map_contiguous(num_experts, 2)),
        ("tp2_ep2_round_robin", 2, 2, owner_map_round_robin(num_experts, 2)),
        ("tp2_ep2_greedy_static", 2, 2, owner_map_greedy(layer_counts, 2)),
    ]

    out: list[dict[str, Any]] = []
    for name, groups, inner_tp, owners in policies:
        rows = rows_by_owner(counts, owners, groups)
        pressure = pressure_from_rows(
            rows,
            total_rows=total_rows,
            baseline_tp=baseline_tp,
            inner_tp=inner_tp,
        )
        out.append({
            "policy": name,
            "groups": groups,
            "inner_tp": inner_tp,
            "total_rows": total_rows,
            "active_experts": active_experts(counts),
            "rows_by_group": rows,
            "max_rows_by_group": max(rows),
            "mean_rows_by_group": mean([float(row) for row in rows]),
            "compute_pressure_vs_tp4": pressure,
            "imbalance_vs_ideal": pressure,
            "communication_row_fraction_proxy": 1.0,
            "expert_memory_relative_to_tp4": 1.0,
            "hotset_size": 0,
            "hot_coverage": 0.0,
        })

    for hotset_size in hotset_sizes:
        hotset = hotset_from_counts(layer_counts, hotset_size)
        if not hotset:
            continue
        cold_greedy_ep4 = owner_map_greedy_excluding(
            layer_counts,
            gpu_count,
            hotset,
        )
        loads, cold_rows = greedy_assign_hot_rows(
            counts=counts,
            cold_owners=cold_greedy_ep4,
            hotset=hotset,
            groups=gpu_count,
        )
        hot_rows = sum(
            int(counts[expert])
            for expert in hotset
            if expert < len(counts)
        )
        pressure = pressure_from_rows(
            loads,
            total_rows=total_rows,
            baseline_tp=baseline_tp,
            inner_tp=1,
        )
        out.append({
            "policy": f"ep4_hot{len(hotset)}_replicated_greedy",
            "groups": gpu_count,
            "inner_tp": 1,
            "total_rows": total_rows,
            "active_experts": active_experts(counts),
            "rows_by_group": loads,
            "cold_rows_by_group": cold_rows,
            "max_rows_by_group": max(loads),
            "mean_rows_by_group": mean([float(row) for row in loads]),
            "compute_pressure_vs_tp4": pressure,
            "imbalance_vs_ideal": pressure,
            "communication_row_fraction_proxy": (
                (total_rows - hot_rows) / total_rows if total_rows else 0.0
            ),
            "expert_memory_relative_to_tp4": expert_memory_relative(
                num_experts=num_experts,
                groups=gpu_count,
                hotset=hotset,
                baseline_tp=baseline_tp,
            ),
            "hotset_size": len(hotset),
            "hot_coverage": hot_rows / total_rows if total_rows else 0.0,
        })

    return out


def aggregate_results(windows: list[dict[str, Any]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_policy: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_layer_policy: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_policy[row["policy"]].append(row)
        by_layer_policy[(row["label"], row["layer"], row["policy"])].append(row)

    def summarize_bucket(items: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "windows": len(items),
            "compute_pressure_vs_tp4": summarize([
                float(item["compute_pressure_vs_tp4"]) for item in items
            ]),
            "communication_row_fraction_proxy": summarize([
                float(item["communication_row_fraction_proxy"]) for item in items
            ]),
            "expert_memory_relative_to_tp4": summarize([
                float(item["expert_memory_relative_to_tp4"]) for item in items
            ]),
            "hot_coverage": summarize([
                float(item["hot_coverage"]) for item in items
            ]),
            "active_experts": summarize([
                float(item["active_experts"]) for item in items
            ]),
            "total_rows": summarize([
                float(item["total_rows"]) for item in items
            ]),
        }

    policy_summary = {
        policy: summarize_bucket(items)
        for policy, items in sorted(by_policy.items())
    }

    layer_policy_summary = []
    for (label, layer, policy), items in sorted(by_layer_policy.items()):
        layer_policy_summary.append({
            "label": label,
            "layer": layer,
            "policy": policy,
            **summarize_bucket(items),
        })

    best_by_layer = []
    by_label_layer: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in layer_policy_summary:
        by_label_layer[(item["label"], item["layer"])].append(item)
    for (label, layer), items in sorted(by_label_layer.items()):
        best = min(
            items,
            key=lambda item: (
                item["compute_pressure_vs_tp4"]["p95"],
                item["communication_row_fraction_proxy"]["mean"],
                item["expert_memory_relative_to_tp4"]["max"],
            ),
        )
        best_by_layer.append({
            "label": label,
            "layer": layer,
            "best_policy_by_p95_compute_pressure": best["policy"],
            "p95_compute_pressure_vs_tp4": best["compute_pressure_vs_tp4"]["p95"],
            "mean_compute_pressure_vs_tp4": best["compute_pressure_vs_tp4"]["mean"],
            "mean_comm_row_fraction_proxy": best["communication_row_fraction_proxy"]["mean"],
            "max_expert_memory_relative_to_tp4": best["expert_memory_relative_to_tp4"]["max"],
        })

    return {
        "window_count": len(windows),
        "policy_summary": policy_summary,
        "layer_policy_summary": layer_policy_summary,
        "best_by_layer": best_by_layer,
    }


def write_markdown(path: str, result: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Qwen3.6 Route-Conditioned Parallelism Simulation")
    lines.append("")
    lines.append("This is a routing proxy, not a kernel benchmark.")
    lines.append("")
    meta = result["metadata"]
    lines.append(f"Inputs: `{', '.join(meta['input_files'])}`")
    lines.append(f"Matched records: `{meta['records_matched']}`")
    lines.append(f"Windows: `{result['summary']['window_count']}`")
    lines.append("")
    lines.append("## Policy Summary")
    lines.append("")
    lines.append(
        "| policy | windows | mean pressure | p95 pressure | mean comm rows | max memory rel |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|")
    for policy, item in sorted(result["summary"]["policy_summary"].items()):
        lines.append(
            f"| `{policy}` | {item['windows']} | "
            f"{item['compute_pressure_vs_tp4']['mean']:.3f} | "
            f"{item['compute_pressure_vs_tp4']['p95']:.3f} | "
            f"{item['communication_row_fraction_proxy']['mean']:.3f} | "
            f"{item['expert_memory_relative_to_tp4']['max']:.3f} |"
        )
    lines.append("")
    lines.append("## Best Policy By Label/Layer")
    lines.append("")
    lines.append(
        "| label | layer | best policy | mean pressure | p95 pressure | mean comm rows | max memory rel |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|")
    for item in result["summary"]["best_by_layer"]:
        layer = str(item["layer"]).replace("language_model.model.", "")
        lines.append(
            f"| `{item['label']}` | `{layer}` | "
            f"`{item['best_policy_by_p95_compute_pressure']}` | "
            f"{item['mean_compute_pressure_vs_tp4']:.3f} | "
            f"{item['p95_compute_pressure_vs_tp4']:.3f} | "
            f"{item['mean_comm_row_fraction_proxy']:.3f} | "
            f"{item['max_expert_memory_relative_to_tp4']:.3f} |"
        )
    lines.append("")
    lines.append("## Reading The Numbers")
    lines.append("")
    lines.append(
        "- `compute_pressure_vs_tp4` is normalized so `1.0` means balanced "
        "rank work equal to the current TP4 row-work proxy."
    )
    lines.append(
        "- Values above `1.0` are load-imbalance risk. Values below `1.0` "
        "are only possible when replication lets hot rows balance better than "
        "the TP4 row-work proxy; kernel overhead can still erase that."
    )
    lines.append(
        "- `communication_row_fraction_proxy` is the fraction of routed rows "
        "that would still need expert-parallel movement. Plain EP policies are "
        "`1.0`; hot-replicated policies reduce this by localizing hot rows."
    )
    lines.append(
        "- `expert_memory_relative_to_tp4` estimates per-rank expert-weight "
        "memory relative to current TP4. It ignores dense weights and KV."
    )
    lines.append("")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", help="Route JSONL files or globs")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--markdown-out")
    parser.add_argument("--layer-regex")
    parser.add_argument("--stage-regex", default="quark_int8_apply")
    parser.add_argument("--min-num-tokens", type=int)
    parser.add_argument("--max-num-tokens", type=int)
    parser.add_argument("--window-size", type=int, default=16)
    parser.add_argument("--stride", type=int, default=16)
    parser.add_argument("--max-windows-per-layer", type=int)
    parser.add_argument("--baseline-tp", type=int, default=4)
    parser.add_argument("--gpu-count", type=int, default=4)
    parser.add_argument("--hotset-sizes", type=parse_int_list, default=parse_int_list("16,32,64"))
    parser.add_argument(
        "--include-windows",
        action="store_true",
        help="Include every per-window policy row in the JSON output.",
    )
    args = parser.parse_args()

    if args.window_size <= 0:
        raise ValueError("--window-size must be positive")
    if args.stride <= 0:
        raise ValueError("--stride must be positive")
    if args.baseline_tp <= 0 or args.gpu_count <= 0:
        raise ValueError("--baseline-tp and --gpu-count must be positive")

    paths = expand_inputs(args.inputs)
    records, metadata = load_records(
        paths,
        layer_regex=args.layer_regex,
        stage_regex=args.stage_regex,
        min_num_tokens=args.min_num_tokens,
        max_num_tokens=args.max_num_tokens,
    )
    windows = make_windows(
        records,
        window_size=args.window_size,
        stride=args.stride,
        max_windows_per_layer=args.max_windows_per_layer,
    )

    rows: list[dict[str, Any]] = []
    for window in windows:
        for row in simulate_window(
            window,
            baseline_tp=args.baseline_tp,
            gpu_count=args.gpu_count,
            hotset_sizes=args.hotset_sizes,
        ):
            rows.append({
                "label": window["label"],
                "layer": window["layer"],
                "start": window["start"],
                "window_size": window["window_size"],
                "calls": window["calls"],
                **row,
            })

    result = {
        "metadata": {
            **metadata,
            "layer_regex": args.layer_regex,
            "stage_regex": args.stage_regex,
            "window_size": args.window_size,
            "stride": args.stride,
            "baseline_tp": args.baseline_tp,
            "gpu_count": args.gpu_count,
            "hotset_sizes": args.hotset_sizes,
        },
        "summary": aggregate_results(windows, rows),
    }
    if args.include_windows:
        result["windows"] = rows
    Path(args.output_json).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.markdown_out:
        write_markdown(args.markdown_out, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
