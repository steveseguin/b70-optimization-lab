#!/usr/bin/env python3
"""Estimate Qwen3.6 hot-expert replication memory/headroom.

This is a planning tool. It combines model dimensions, vLLM-reported KV-cache
capacity, and optional xpu-smi memory telemetry to decide whether hot-expert
replication is viable in the current production lane or needs a smaller static
latency lane.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = (
    "/mnt/fast-ai/llm-cache/hf/models--nameistoken--"
    "Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/"
    "cced56592e8c8935f8220836b4baa04dfd389118/config.json"
)


def mib(value: float) -> float:
    return value / (1024.0 * 1024.0)


def gib(value: float) -> float:
    return value / (1024.0 * 1024.0 * 1024.0)


def parse_float_list(value: str) -> list[float]:
    out = []
    for item in value.split(","):
        item = item.strip()
        if item:
            out.append(float(item))
    if not out:
        raise argparse.ArgumentTypeError("expected at least one number")
    return out


def parse_int_list(value: str) -> list[int]:
    out = []
    for item in value.split(","):
        item = item.strip()
        if item:
            out.append(int(item))
    if not out:
        raise argparse.ArgumentTypeError("expected at least one integer")
    return out


def load_text_config(path: str) -> dict[str, Any]:
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    text_config = cfg.get("text_config")
    if not isinstance(text_config, dict):
        raise ValueError(f"Missing text_config in {path}")
    return text_config


def parse_vllm_log(path: str | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not path:
        return out
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    kv_mem_matches = re.findall(r"Available KV cache memory:\s*([0-9.]+)\s*GiB", text)
    kv_tokens_matches = re.findall(r"GPU KV cache size:\s*([0-9,]+)\s*tokens", text)
    conc_matches = re.findall(
        r"Maximum concurrency for\s*([0-9,]+)\s*tokens per request:\s*([0-9.]+)x",
        text,
    )
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


def estimate(
    *,
    text_config: dict[str, Any],
    tp_size: int,
    hotset_sizes: list[int],
    target_layers: list[int],
    kv_report: dict[str, Any],
    device_memory_mib: float,
    xpu_memory: dict[str, Any],
    reserve_mib_values: list[float],
) -> dict[str, Any]:
    hidden = int(text_config["hidden_size"])
    inter = int(text_config["moe_intermediate_size"])
    num_layers = int(text_config["num_hidden_layers"])
    num_experts = int(text_config["num_experts"])
    if any(layer < 0 or layer >= num_layers for layer in target_layers):
        raise ValueError("target layer outside model layer range")

    # Quark W8A8 local shard estimate used by the route hotset planning notes:
    # gate/up has 2*inter/tp outputs and down has hidden/tp outputs. INT8
    # weights are one byte plus one fp32 output scale per output channel. The
    # model stores both expert projections per logical expert.
    inter_tp = inter // tp_size
    hidden_tp = hidden // tp_size
    gate_up_weight = hidden * (2 * inter_tp)
    gate_up_scales = 2 * inter_tp * 4
    down_weight = inter * hidden_tp
    down_scales = hidden * 4
    local_shard_expert_bytes = gate_up_weight + gate_up_scales + down_weight + down_scales

    all_layer_count = num_layers
    selected_layer_count = len(target_layers)
    hotset_rows = []
    for hotset in hotset_sizes:
        selected_bytes = hotset * local_shard_expert_bytes * selected_layer_count
        all_layer_bytes = hotset * local_shard_expert_bytes * all_layer_count
        hotset_rows.append({
            "hotset_size": hotset,
            "target_layers": target_layers,
            "selected_layers_mib_per_rank": mib(selected_bytes),
            "all_layers_mib_per_rank": mib(all_layer_bytes),
        })

    baseline_expert_bytes = num_experts * local_shard_expert_bytes * num_layers
    kv_tokens = int(kv_report.get("gpu_kv_cache_tokens") or 0)
    kv_gib = float(kv_report.get("available_kv_cache_gib") or 0.0)
    kv_mib = kv_gib * 1024.0
    mib_per_kv_token = kv_mib / kv_tokens if kv_tokens else 0.0
    reported_context = int(kv_report.get("reported_context_length") or 32768)
    current_max_concurrency = (
        float(kv_report.get("reported_max_concurrency") or 0.0)
        or (kv_tokens / reported_context if reported_context and kv_tokens else 0.0)
    )

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

    scenarios = []
    for hot in hotset_rows:
        for reserve_mib in reserve_mib_values:
            add_mib = float(hot["all_layers_mib_per_rank"])
            freed_tokens = math.ceil((add_mib + reserve_mib) / mib_per_kv_token) if mib_per_kv_token else 0
            remaining_tokens = max(0, kv_tokens - freed_tokens)
            remaining_concurrency_32k = (
                remaining_tokens / reported_context if reported_context else 0.0
            )
            scenarios.append({
                "hotset_size": hot["hotset_size"],
                "all_layers_additional_mib_per_rank": add_mib,
                "reserve_mib": reserve_mib,
                "kv_tokens_to_free": freed_tokens,
                "remaining_kv_tokens": remaining_tokens,
                "current_max_concurrency_at_reported_context": current_max_concurrency,
                "remaining_concurrency_at_reported_context": remaining_concurrency_32k,
                "drop_in_concurrency_at_reported_context": (
                    current_max_concurrency - remaining_concurrency_32k
                ),
                "fits_without_kv_tradeoff_by_xpu_snapshot": (
                    current_free_min is not None and current_free_min >= add_mib + reserve_mib
                ),
            })

    return {
        "model": {
            "hidden_size": hidden,
            "moe_intermediate_size": inter,
            "num_hidden_layers": num_layers,
            "num_experts": num_experts,
            "tp_size": tp_size,
            "intermediate_per_tp_rank": inter_tp,
            "hidden_per_tp_rank": hidden_tp,
        },
        "expert_memory": {
            "local_shard_expert_bytes": local_shard_expert_bytes,
            "local_shard_expert_mib": mib(local_shard_expert_bytes),
            "baseline_all_experts_all_layers_mib_per_rank": mib(baseline_expert_bytes),
        },
        "hotset_memory": hotset_rows,
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
        "capacity_scenarios": scenarios,
    }


def write_markdown(path: str, result: dict[str, Any]) -> None:
    lines = []
    lines.append("# Qwen3.6 Hot-Replication Memory Plan")
    lines.append("")
    expert = result["expert_memory"]
    kv = result["runtime_kv_report"]
    xpu = result["xpu_memory"]
    lines.append(f"Per local-shard expert bytes: `{expert['local_shard_expert_bytes']}`")
    lines.append(
        "Baseline all-expert MoE weight footprint per rank: "
        f"`{expert['baseline_all_experts_all_layers_mib_per_rank']:.1f} MiB`"
    )
    lines.append(
        f"Runtime KV report: `{kv.get('available_kv_cache_gib', 0):.2f} GiB`, "
        f"`{kv.get('gpu_kv_cache_tokens', 0)}` tokens, "
        f"`{kv.get('reported_max_concurrency', 0):.2f}x` at "
        f"`{kv.get('reported_context_length', 0)}` context."
    )
    lines.append(
        f"XPU memory snapshot max used: `{(xpu.get('current_used_mib_max') or 0):.1f} MiB`; "
        f"min free: `{(xpu.get('current_free_mib_min') or 0):.1f} MiB`."
    )
    lines.append("")
    lines.append("## Hotset Storage")
    lines.append("")
    lines.append("| hotset | selected layers MiB/rank | all layers MiB/rank |")
    lines.append("|---:|---:|---:|")
    for row in result["hotset_memory"]:
        lines.append(
            f"| {row['hotset_size']} | "
            f"{row['selected_layers_mib_per_rank']:.1f} | "
            f"{row['all_layers_mib_per_rank']:.1f} |"
        )
    lines.append("")
    lines.append("## Capacity Tradeoff")
    lines.append("")
    lines.append(
        "| hotset | reserve MiB | add MiB/rank | KV tokens to free | remaining 32K concurrency | fits current free? |"
    )
    lines.append("|---:|---:|---:|---:|---:|---|")
    for row in result["capacity_scenarios"]:
        lines.append(
            f"| {row['hotset_size']} | {row['reserve_mib']:.0f} | "
            f"{row['all_layers_additional_mib_per_rank']:.1f} | "
            f"{row['kv_tokens_to_free']} | "
            f"{row['remaining_concurrency_at_reported_context']:.2f} | "
            f"{row['fits_without_kv_tradeoff_by_xpu_snapshot']} |"
        )
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    lines.append(
        "- Current accepted TP4/32K/c48 lane is effectively full by telemetry, "
        "so an all-layer hot cache cannot be bolted on without reducing KV/graph "
        "memory or using a separate latency lane."
    )
    lines.append(
        "- All-layer hot64 storage is small relative to the reported KV budget, "
        "but too large for current free VRAM. It is feasible only by carving "
        "roughly a few hundred thousand KV tokens from the capacity lane or by "
        "running a lower-context static c1 lane."
    )
    lines.append(
        "- The next safe implementation step is a route-replay-only one-layer "
        "hot64 prototype, then an explicit low-context sidecar memory screen if "
        "the replay kernel shows real latency upside."
    )
    lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-config", default=DEFAULT_CONFIG)
    parser.add_argument("--vllm-log")
    parser.add_argument("--tp-size", type=int, default=4)
    parser.add_argument("--hotset-sizes", type=parse_int_list, default=parse_int_list("16,32,64"))
    parser.add_argument("--target-layers", type=parse_int_list, default=parse_int_list("9,14,20,21,8"))
    parser.add_argument("--device-memory-mib", type=float, default=32656.0)
    parser.add_argument("--reserve-mib", type=parse_float_list, default=parse_float_list("0,512,1024"))
    parser.add_argument("--skip-xpu-smi", action="store_true")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--markdown-out")
    args = parser.parse_args()

    text_config = load_text_config(args.model_config)
    kv_report = parse_vllm_log(args.vllm_log)
    xpu_memory = {"rows": []} if args.skip_xpu_smi else xpu_memory_snapshot()
    result = estimate(
        text_config=text_config,
        tp_size=args.tp_size,
        hotset_sizes=args.hotset_sizes,
        target_layers=args.target_layers,
        kv_report=kv_report,
        device_memory_mib=args.device_memory_mib,
        xpu_memory=xpu_memory,
        reserve_mib_values=args.reserve_mib,
    )
    Path(args.output_json).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.markdown_out:
        write_markdown(args.markdown_out, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
