#!/usr/bin/env python3
"""Estimate hot-expert cache/repack tradeoffs from MoE flight records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_MODEL_CONFIG = (
    "/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/"
    "snapshots/cced56592e8c8935f8220836b4baa04dfd389118/config.json"
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


def load_text_config(path: str) -> dict[str, Any]:
    cfg = json.loads(Path(path).read_text())
    text_config = cfg.get("text_config")
    if not isinstance(text_config, dict):
        raise ValueError(f"Missing text_config in {path}")
    return text_config


def bytes_per_expert(
    *,
    hidden_size: int,
    moe_intermediate_size: int,
    tp_size: int,
    include_scales: bool,
) -> dict[str, int]:
    inter_per_tp = moe_intermediate_size // tp_size
    w13_bytes = hidden_size * (2 * inter_per_tp)
    w2_bytes = inter_per_tp * hidden_size
    # Current Quark W8A8 scales are fp32 per output channel in the local shard.
    scale_bytes = ((2 * inter_per_tp) + hidden_size) * 4 if include_scales else 0
    total = w13_bytes + w2_bytes + scale_bytes
    return {
        "intermediate_size_per_tp": inter_per_tp,
        "w13_int8_bytes": w13_bytes,
        "w2_int8_bytes": w2_bytes,
        "scale_bytes": scale_bytes,
        "total_bytes": total,
    }


def mib(value: float) -> float:
    return value / (1024.0 * 1024.0)


def make_plan(
    flight: dict[str, Any],
    text_config: dict[str, Any],
    *,
    tp_size: int,
    hot_sizes: list[int],
    include_scales: bool,
    min_coverage: float,
) -> dict[str, Any]:
    hidden_size = int(text_config["hidden_size"])
    moe_intermediate_size = int(text_config["moe_intermediate_size"])
    num_layers = int(text_config["num_hidden_layers"])
    num_experts = int(text_config["num_experts"])
    per_expert = bytes_per_expert(
        hidden_size=hidden_size,
        moe_intermediate_size=moe_intermediate_size,
        tp_size=tp_size,
        include_scales=include_scales,
    )

    layers = []
    total_by_size: dict[str, float] = {str(size): 0.0 for size in hot_sizes}
    selected_by_size: dict[str, float] = {str(size): 0.0 for size in hot_sizes}
    for name, layer in flight.get("layers", {}).items():
        aggregate = layer.get("aggregate", {})
        hot_coverage = aggregate.get("hot_coverage", {})
        row = {
            "layer": name,
            "layer_index": layer.get("layer_index"),
            "records": aggregate.get("records"),
            "active_experts": aggregate.get("active_experts"),
            "window_active_experts_p50": (
                layer.get("window_active_experts", {}).get("p50")
            ),
            "plans": {},
        }
        for size in hot_sizes:
            size_key = str(size)
            coverage = float(hot_coverage.get(size_key, 0.0) or 0.0)
            bytes_local = per_expert["total_bytes"] * size
            selected = coverage >= min_coverage
            total_by_size[size_key] += bytes_local
            if selected:
                selected_by_size[size_key] += bytes_local
            row["plans"][size_key] = {
                "hot_experts": size,
                "coverage": coverage,
                "local_rank_mib": mib(bytes_local),
                "all_tp_ranks_mib": mib(bytes_local * tp_size),
                "selected_at_min_coverage": selected,
            }
        layers.append(row)

    layers.sort(
        key=lambda row: (
            max(plan["coverage"] for plan in row["plans"].values()),
            -(row.get("window_active_experts_p50") or 9999),
        ),
        reverse=True,
    )

    return {
        "flight_record": flight.get("input_files"),
        "model": {
            "hidden_size": hidden_size,
            "moe_intermediate_size": moe_intermediate_size,
            "intermediate_size_per_tp": per_expert["intermediate_size_per_tp"],
            "num_hidden_layers": num_layers,
            "num_experts": num_experts,
            "tp_size": tp_size,
            "include_scales": include_scales,
        },
        "bytes_per_local_tp_expert": per_expert,
        "hot_sizes": hot_sizes,
        "min_coverage": min_coverage,
        "captured_layers": len(layers),
        "estimated_all_layers_local_rank_mib": {
            str(size): mib(per_expert["total_bytes"] * size * num_layers)
            for size in hot_sizes
        },
        "captured_layers_local_rank_mib": {
            size: mib(total) for size, total in total_by_size.items()
        },
        "captured_selected_layers_local_rank_mib": {
            size: mib(total) for size, total in selected_by_size.items()
        },
        "layers": layers,
    }


def make_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Qwen3.6 MoE Hot-Set Plan",
        "",
        f"Captured layers: `{plan['captured_layers']}`",
        f"TP size: `{plan['model']['tp_size']}`",
        f"Per local-shard expert bytes: `{plan['bytes_per_local_tp_expert']['total_bytes']}`",
        "",
        "## Memory Estimate",
        "",
        "| hot set | captured local-rank MiB | all 40 layers local-rank MiB |",
        "|---:|---:|---:|",
    ]
    for size in plan["hot_sizes"]:
        key = str(size)
        lines.append(
            f"| {size} | {plan['captured_layers_local_rank_mib'][key]:.1f} | "
            f"{plan['estimated_all_layers_local_rank_mib'][key]:.1f} |"
        )
    lines.extend(
        [
            "",
            "## Layer Coverage",
            "",
            "| layer | active experts | p50 window active | top16 | top32 | top64 | top32 MiB/rank |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for layer in plan["layers"]:
        plans = layer["plans"]
        lines.append(
            "| "
            f"`{layer['layer']}` | {layer['active_experts']} | "
            f"{layer['window_active_experts_p50']} | "
            f"{plans.get('16', {}).get('coverage', 0.0):.3f} | "
            f"{plans.get('32', {}).get('coverage', 0.0):.3f} | "
            f"{plans.get('64', {}).get('coverage', 0.0):.3f} | "
            f"{plans.get('32', {}).get('local_rank_mib', 0.0):.1f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Top-32 hot-set repack is small enough to test per layer before considering a full all-layer cache.",
            "- Top-64 captures much more traffic but roughly doubles the local-rank cache footprint.",
            "- Use this as a planning estimate only; endpoint promotion still requires exact sentinel parity and speed proof.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--flight-record", required=True)
    parser.add_argument("--model-config", default=DEFAULT_MODEL_CONFIG)
    parser.add_argument("--tp-size", type=int, default=4)
    parser.add_argument("--hot-sizes", type=parse_csv_ints, default=parse_csv_ints("16,32,64"))
    parser.add_argument("--min-coverage", type=float, default=0.50)
    parser.add_argument("--no-scales", action="store_true")
    parser.add_argument("--out", required=True)
    parser.add_argument("--markdown-out")
    args = parser.parse_args()

    flight = json.loads(Path(args.flight_record).read_text())
    text_config = load_text_config(args.model_config)
    plan = make_plan(
        flight,
        text_config,
        tp_size=args.tp_size,
        hot_sizes=args.hot_sizes,
        include_scales=not args.no_scales,
        min_coverage=args.min_coverage,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    if args.markdown_out:
        md = Path(args.markdown_out)
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(make_markdown(plan))
    print(json.dumps({"out": str(out), "captured_layers": plan["captured_layers"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
