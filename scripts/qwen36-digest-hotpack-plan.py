#!/usr/bin/env python3
"""Plan Qwen3.6 hot-expert packs from replay-digest summaries.

The replay digest captures the hottest expert columns per MoE layer while the
endpoint is serving real prompts. This tool converts that atlas into an
implementation plan: exact top-K coverage for K values present in the digest,
local-rank memory cost for replicated hot packs, and layer subsets that are
worth trying before an all-layer fast lane.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_MODEL_CONFIG = (
    "/mnt/fast-ai/llm-cache/hf/models--nameistoken--"
    "Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/"
    "cced56592e8c8935f8220836b4baa04dfd389118/config.json"
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


def parse_csv_floats(value: str) -> list[float]:
    out = []
    for item in value.split(","):
        item = item.strip()
        if item:
            out.append(float(item))
    if not out:
        raise argparse.ArgumentTypeError("expected at least one number")
    return out


def mib(value: float) -> float:
    return value / (1024.0 * 1024.0)


def gib(value: float) -> float:
    return value / (1024.0 * 1024.0 * 1024.0)


def load_text_config(path: str) -> dict[str, Any]:
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    text_config = cfg.get("text_config")
    if not isinstance(text_config, dict):
        raise ValueError(f"Missing text_config in {path}")
    return text_config


def bytes_per_local_expert(
    *,
    hidden_size: int,
    moe_intermediate_size: int,
    tp_size: int,
    include_scales: bool,
) -> dict[str, int]:
    inter_per_tp = moe_intermediate_size // tp_size
    w13_bytes = hidden_size * (2 * inter_per_tp)
    w2_bytes = inter_per_tp * hidden_size
    scale_bytes = ((2 * inter_per_tp) + hidden_size) * 4 if include_scales else 0
    return {
        "intermediate_size_per_tp": inter_per_tp,
        "w13_int8_bytes": w13_bytes,
        "w2_int8_bytes": w2_bytes,
        "scale_bytes": scale_bytes,
        "total_bytes": w13_bytes + w2_bytes + scale_bytes,
    }


def parse_vllm_log(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    kv_mem_matches = re.findall(r"Available KV cache memory:\s*([0-9.]+)\s*GiB", text)
    kv_tokens_matches = re.findall(r"GPU KV cache size:\s*([0-9,]+)\s*tokens", text)
    conc_matches = re.findall(
        r"Maximum concurrency for\s*([0-9,]+)\s*tokens per request:\s*([0-9.]+)x",
        text,
    )
    out: dict[str, Any] = {}
    if kv_mem_matches:
        out["available_kv_cache_gib"] = float(kv_mem_matches[-1])
    if kv_tokens_matches:
        out["gpu_kv_cache_tokens"] = int(kv_tokens_matches[-1].replace(",", ""))
    if conc_matches:
        context, concurrency = conc_matches[-1]
        out["reported_context_length"] = int(context.replace(",", ""))
        out["reported_max_concurrency"] = float(concurrency)
    return out


def xpu_memory_snapshot() -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["xpu-smi", "dump", "-d", "-1", "-m", "18", "-n", "1"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except Exception as exc:  # pragma: no cover - telemetry best effort
        return {"error": str(exc)}

    rows = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("Timestamp"):
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 3:
            continue
        try:
            rows.append({
                "timestamp": parts[0],
                "device": int(parts[1]),
                "memory_used_mib": float(parts[2]),
            })
        except ValueError:
            continue
    return {"rows": rows, "raw": proc.stdout}


def topk_coverage(
    top_counts: list[list[int]],
    *,
    rows_sum: int,
    hot_size: int,
) -> dict[str, Any]:
    selected = top_counts[:hot_size]
    count_sum = sum(int(row[1]) for row in selected)
    return {
        "hot_size": hot_size,
        "coverage": count_sum / rows_sum if rows_sum else 0.0,
        "count_sum": count_sum,
        "experts": [int(row[0]) for row in selected],
    }


def make_plan(
    *,
    summary: dict[str, Any],
    text_config: dict[str, Any],
    tp_size: int,
    hot_sizes: list[int],
    thresholds: list[float],
    include_scales: bool,
    kv_report: dict[str, Any],
    xpu_memory: dict[str, Any],
    device_memory_mib: float,
    reserve_mib: float,
) -> dict[str, Any]:
    hidden_size = int(text_config["hidden_size"])
    moe_intermediate_size = int(text_config["moe_intermediate_size"])
    num_hidden_layers = int(text_config["num_hidden_layers"])
    num_experts = int(text_config["num_experts"])
    per_expert = bytes_per_local_expert(
        hidden_size=hidden_size,
        moe_intermediate_size=moe_intermediate_size,
        tp_size=tp_size,
        include_scales=include_scales,
    )
    per_expert_bytes = int(per_expert["total_bytes"])

    top_by_layer = summary.get("top_hot_experts_by_layer") or {}
    hot_coverage_by_layer = summary.get("hot_coverage_by_layer") or {}
    layer_rows = []
    all_layers_by_size = {str(size): 0 for size in hot_sizes}
    coverage_weighted_by_size = {str(size): 0.0 for size in hot_sizes}
    total_rows_by_size = {str(size): 0 for size in hot_sizes}
    recorded_dynamic_hot_sum = 0
    recorded_dynamic_rows_sum = 0

    for layer_key in sorted(top_by_layer, key=lambda item: int(item)):
        top_counts = [[int(pair[0]), int(pair[1])] for pair in top_by_layer[layer_key]]
        recorded_layer = hot_coverage_by_layer.get(layer_key) or {}
        rows_sum = int(recorded_layer.get("rows_sum") or 0)
        recorded_hot_sum = int(recorded_layer.get("hot_count_sum") or 0)
        recorded_dynamic_hot_sum += recorded_hot_sum
        recorded_dynamic_rows_sum += rows_sum
        layer_plans = {}
        for size in hot_sizes:
            if size > len(top_counts):
                continue
            cov = topk_coverage(top_counts, rows_sum=rows_sum, hot_size=size)
            add_bytes = per_expert_bytes * size
            key = str(size)
            layer_plans[key] = {
                **cov,
                "local_rank_mib": mib(add_bytes),
                "all_tp_ranks_mib": mib(add_bytes * tp_size),
            }
            all_layers_by_size[key] += add_bytes
            coverage_weighted_by_size[key] += cov["count_sum"]
            total_rows_by_size[key] += rows_sum
        layer_rows.append({
            "layer": int(layer_key),
            "rows_sum": rows_sum,
            "recorded_dynamic_top16_count_sum": recorded_hot_sum,
            "recorded_dynamic_top16_coverage": recorded_layer.get("coverage"),
            "plans": layer_plans,
        })

    threshold_plans = []
    for size in hot_sizes:
        key = str(size)
        for threshold in thresholds:
            selected_layers = [
                row["layer"]
                for row in layer_rows
                if key in row["plans"] and row["plans"][key]["coverage"] >= threshold
            ]
            add_bytes = len(selected_layers) * per_expert_bytes * size
            threshold_plans.append({
                "hot_size": size,
                "min_coverage": threshold,
                "selected_layers": selected_layers,
                "selected_layer_count": len(selected_layers),
                "local_rank_mib": mib(add_bytes),
                "all_tp_ranks_mib": mib(add_bytes * tp_size),
            })

    kv_tokens = int(kv_report.get("gpu_kv_cache_tokens") or 0)
    kv_gib = float(kv_report.get("available_kv_cache_gib") or 0.0)
    reported_context = int(kv_report.get("reported_context_length") or 32768)
    reported_concurrency = (
        float(kv_report.get("reported_max_concurrency") or 0.0)
        or (kv_tokens / reported_context if kv_tokens and reported_context else 0.0)
    )
    mib_per_kv_token = (kv_gib * 1024.0 / kv_tokens) if kv_tokens else 0.0

    current_used = [
        float(row["memory_used_mib"])
        for row in xpu_memory.get("rows", [])
        if "memory_used_mib" in row
    ]
    current_used_max = max(current_used) if current_used else None
    current_free_min = (
        device_memory_mib - current_used_max
        if current_used_max is not None else None
    )

    capacity_by_size = []
    for size in hot_sizes:
        key = str(size)
        add_mib = mib(all_layers_by_size[key])
        kv_tokens_to_free = (
            math.ceil((add_mib + reserve_mib) / mib_per_kv_token)
            if mib_per_kv_token else 0
        )
        remaining_tokens = max(0, kv_tokens - kv_tokens_to_free)
        capacity_by_size.append({
            "hot_size": size,
            "all_layers_local_rank_mib": add_mib,
            "reserve_mib": reserve_mib,
            "kv_tokens_to_free": kv_tokens_to_free,
            "remaining_kv_tokens": remaining_tokens,
            "remaining_concurrency_at_reported_context": (
                remaining_tokens / reported_context if reported_context else 0.0
            ),
            "current_max_concurrency_at_reported_context": reported_concurrency,
            "fits_without_kv_tradeoff_by_xpu_snapshot": (
                current_free_min is not None and current_free_min >= add_mib + reserve_mib
            ),
        })

    return {
        "source_summary": summary.get("sources"),
        "digest": {
            "records": summary.get("records"),
            "rows": summary.get("rows"),
            "valid_magic_rows": summary.get("valid_magic_rows"),
            "invalid_rows": summary.get("invalid_rows"),
            "hot_columns_detected": summary.get("hot_columns_detected"),
            "hot_pair_observations": summary.get("hot_pair_observations"),
            "rows_with_hot_pairs": summary.get("rows_with_hot_pairs"),
        },
        "model": {
            "hidden_size": hidden_size,
            "moe_intermediate_size": moe_intermediate_size,
            "num_hidden_layers": num_hidden_layers,
            "num_experts": num_experts,
            "tp_size": tp_size,
            "include_scales": include_scales,
        },
        "expert_memory": {
            **per_expert,
            "local_rank_mib_per_expert": mib(per_expert_bytes),
            "all_tp_ranks_mib_per_expert": mib(per_expert_bytes * tp_size),
            "baseline_all_experts_all_layers_mib_per_rank": mib(
                per_expert_bytes * num_experts * num_hidden_layers
            ),
        },
        "hot_sizes": hot_sizes,
        "all_layers_local_rank_mib_by_size": {
            key: mib(value) for key, value in all_layers_by_size.items()
        },
        "weighted_coverage_by_size": {
            key: (
                coverage_weighted_by_size[key] / total_rows_by_size[key]
                if total_rows_by_size[key] else 0.0
            )
            for key in coverage_weighted_by_size
        },
        "recorded_dynamic_top16_weighted_coverage": (
            recorded_dynamic_hot_sum / recorded_dynamic_rows_sum
            if recorded_dynamic_rows_sum else 0.0
        ),
        "threshold_plans": threshold_plans,
        "capacity_by_size": capacity_by_size,
        "runtime_kv_report": {
            **kv_report,
            "mib_per_kv_token_from_report": mib_per_kv_token,
        },
        "xpu_memory": {
            "device_memory_mib": device_memory_mib,
            "current_used_mib_by_device": current_used,
            "current_used_mib_max": current_used_max,
            "current_free_mib_min": current_free_min,
            "snapshot": xpu_memory,
        },
        "layers": layer_rows,
    }


def write_markdown(path: Path, plan: dict[str, Any]) -> None:
    lines = [
        "# Qwen3.6 Replay-Digest Hot-Pack Plan",
        "",
        "## Scope",
        "",
        (
            "This plan uses only the replay-digest hot columns captured in the "
            "20260612dq diagnostic run. The digest records top-16 hot experts, "
            "so top-32/top-64 coverage is intentionally not extrapolated here."
        ),
        "",
        "## Memory Model",
        "",
        f"TP size: `{plan['model']['tp_size']}`",
        f"Per local-rank expert pack: `{plan['expert_memory']['total_bytes']}` bytes "
        f"(`{plan['expert_memory']['local_rank_mib_per_expert']:.3f} MiB`).",
        (
            "Baseline all-expert MoE footprint per rank: "
            f"`{plan['expert_memory']['baseline_all_experts_all_layers_mib_per_rank']:.1f} MiB`."
        ),
        "",
        "## All-Layer Hot Pack",
        "",
        (
            "Static coverage uses one per-layer hot pack across the whole replay. "
            "Recorded dynamic top-16 coverage is an upper bound from the per-call "
            f"digest columns: `{plan['recorded_dynamic_top16_weighted_coverage']:.3f}`."
        ),
        "",
        "| static hot K | weighted coverage | add MiB/rank | KV tokens to free | remaining 32K conc | fits current free? |",
        "|---:|---:|---:|---:|---:|---|",
    ]
    weighted = plan["weighted_coverage_by_size"]
    capacity = {str(row["hot_size"]): row for row in plan["capacity_by_size"]}
    for size in plan["hot_sizes"]:
        key = str(size)
        row = capacity[key]
        lines.append(
            f"| {size} | {weighted[key]:.3f} | "
            f"{row['all_layers_local_rank_mib']:.1f} | "
            f"{row['kv_tokens_to_free']} | "
            f"{row['remaining_concurrency_at_reported_context']:.2f} | "
            f"{row['fits_without_kv_tradeoff_by_xpu_snapshot']} |"
        )

    lines.extend([
        "",
        "## Layer Threshold Packs",
        "",
        "| hot K | min layer coverage | layers | add MiB/rank |",
        "|---:|---:|---:|---:|",
    ])
    for row in plan["threshold_plans"]:
        if row["selected_layer_count"] == 0:
            continue
        lines.append(
            f"| {row['hot_size']} | {row['min_coverage']:.2f} | "
            f"{row['selected_layer_count']} | {row['local_rank_mib']:.1f} |"
        )

    lines.extend([
        "",
        "## Per-Layer Coverage",
        "",
        "| layer | static top1 | static top2 | static top4 | static top8 | static top16 | dynamic top16 upper | static top16 experts |",
        "|---:|---:|---:|---:|---:|---:|---:|---|",
    ])
    for layer in plan["layers"]:
        plans = layer["plans"]
        top16 = plans.get("16", {})
        top16_experts = ",".join(str(item) for item in top16.get("experts", [])[:16])
        lines.append(
            f"| {layer['layer']} | "
            f"{plans.get('1', {}).get('coverage', 0.0):.3f} | "
            f"{plans.get('2', {}).get('coverage', 0.0):.3f} | "
            f"{plans.get('4', {}).get('coverage', 0.0):.3f} | "
            f"{plans.get('8', {}).get('coverage', 0.0):.3f} | "
            f"{plans.get('16', {}).get('coverage', 0.0):.3f} | "
            f"{(layer.get('recorded_dynamic_top16_coverage') or 0.0):.3f} | "
            f"`{top16_experts}` |"
        )

    lines.extend([
        "",
        "## Decision",
        "",
        (
            "- A static top-16 pack covers a majority of replayed decode rows "
            "while adding only a few hundred MiB per rank. The dynamic top-16 "
            "upper bound is materially higher, so route-aware exact hotset "
            "selection is a real opportunity."
        ),
        (
            "- The first implementation target should still be a one-layer or "
            "threshold-selected fast lane, because the speed risk is kernel "
            "routing and copy overhead, not raw VRAM."
        ),
        (
            "- Keep full cold fallback and sentinel parity. The hot pack is an "
            "execution shortcut for already-selected experts, not a routing "
            "approximation."
        ),
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True)
    parser.add_argument("--model-config", default=DEFAULT_MODEL_CONFIG)
    parser.add_argument("--vllm-log")
    parser.add_argument("--tp-size", type=int, default=4)
    parser.add_argument("--hot-sizes", type=parse_csv_ints, default=parse_csv_ints("1,2,4,8,16"))
    parser.add_argument(
        "--coverage-thresholds",
        type=parse_csv_floats,
        default=parse_csv_floats("0.80,0.75,0.70,0.65"),
    )
    parser.add_argument("--no-scales", action="store_true")
    parser.add_argument("--skip-xpu-smi", action="store_true")
    parser.add_argument("--device-memory-mib", type=float, default=32656.0)
    parser.add_argument("--reserve-mib", type=float, default=512.0)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md")
    args = parser.parse_args()

    summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    text_config = load_text_config(args.model_config)
    kv_report = parse_vllm_log(args.vllm_log)
    xpu_memory = {"rows": []} if args.skip_xpu_smi else xpu_memory_snapshot()
    plan = make_plan(
        summary=summary,
        text_config=text_config,
        tp_size=args.tp_size,
        hot_sizes=args.hot_sizes,
        thresholds=args.coverage_thresholds,
        include_scales=not args.no_scales,
        kv_report=kv_report,
        xpu_memory=xpu_memory,
        device_memory_mib=args.device_memory_mib,
        reserve_mib=args.reserve_mib,
    )

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.out_md:
        out_md = Path(args.out_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        write_markdown(out_md, plan)
    print(json.dumps({
        "out_json": str(out_json),
        "out_md": args.out_md,
        "weighted_coverage_by_size": plan["weighted_coverage_by_size"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
