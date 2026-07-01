#!/usr/bin/env python3
"""Convert Qwen3.6 first-decode route fixtures into kernel-ready route rows.

This is a CPU-only bridge between the compact first-decode route fixture and
the existing route simulator / MoE microbench scripts. It does not claim speed.
It emits:

- JSONL rows compatible with scripts that expect captured route records.
- A JSON summary with Qwen shape, active experts, overlaps, and memory sizes.
- Optional Markdown with the next exact microbench commands.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_FIXTURE = (
    "data/qwen36-quark-int8-tp4-routefixture-firstdecode-routes-20260612cr.json"
)
DEFAULT_MODEL_CONFIG = (
    "/mnt/fast-ai/llm-cache/hf/models--nameistoken--"
    "Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/"
    "cced56592e8c8935f8220836b4baa04dfd389118/config.json"
)


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_text_config(path: str | Path) -> dict[str, Any]:
    cfg = load_json(path)
    text = cfg.get("text_config")
    if not isinstance(text, dict):
        raise ValueError(f"missing text_config in {path}")
    return text


def sha16(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


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


def summary_stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {
            "count": 0,
            "mean": 0.0,
            "p50": 0.0,
            "p90": 0.0,
            "p95": 0.0,
            "min": 0.0,
            "max": 0.0,
        }
    return {
        "count": float(len(values)),
        "mean": mean(values),
        "p50": percentile(values, 50),
        "p90": percentile(values, 90),
        "p95": percentile(values, 95),
        "min": min(values),
        "max": max(values),
    }


def make_counts(topk_ids: list[int], num_experts: int) -> list[int]:
    counts = [0] * num_experts
    for expert in topk_ids:
        if expert < 0 or expert >= num_experts:
            raise ValueError(
                f"expert id {expert} outside [0, {num_experts})")
        counts[expert] += 1
    return counts


def tensor_mib(numel: int, element_bytes: int) -> float:
    return (numel * element_bytes) / (1024.0 * 1024.0)


def build_records(
    fixture: dict[str, Any],
    text_config: dict[str, Any],
    *,
    stage: str,
) -> list[dict[str, Any]]:
    fixtures = fixture.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        raise ValueError("fixture JSON has no fixtures list")

    num_experts = int(text_config["num_experts"])
    model_topk = int(text_config["num_experts_per_tok"])
    records: list[dict[str, Any]] = []
    call = 0
    for fixture_index, event in enumerate(fixtures):
        layers = event.get("layers")
        if not isinstance(layers, list):
            raise ValueError(f"fixture {fixture_index} has no layers list")
        for layer in layers:
            topk_ids = [int(item) for item in layer.get("topk_expert_ids", [])]
            topk = int(layer.get("topk") or len(topk_ids))
            if topk != model_topk or len(topk_ids) != model_topk:
                raise ValueError(
                    f"fixture {fixture_index} layer {layer.get('layer')} "
                    f"has topk={topk} ids={len(topk_ids)}, expected {model_topk}"
                )
            counts = make_counts(topk_ids, num_experts)
            record = {
                "source_kind": "firstdecode_route_fixture",
                "source_fixture_note": fixture.get("note"),
                "fixture_index": fixture_index,
                "event_id": event.get("event_id"),
                "rank": str(event.get("rank")),
                "is_pure_decode": bool(event.get("is_pure_decode")),
                "num_tokens": int(event.get("num_tokens") or 1),
                "layer": str(layer.get("layer")),
                "layer_index": int(layer.get("layer_index")),
                "stage": stage,
                "call": call,
                "num_experts": num_experts,
                "topk": model_topk,
                "topk_ids": [topk_ids],
                "counts": counts,
                "active_experts": sum(1 for count in counts if count > 0),
                "total_assignments": sum(counts),
                "route_hash": sha16(topk_ids),
            }
            records.append(record)
            call += 1
    return records


def summarize_records(
    records: list[dict[str, Any]],
    text_config: dict[str, Any],
    *,
    tp_size: int,
) -> dict[str, Any]:
    num_experts = int(text_config["num_experts"])
    hidden_size = int(text_config["hidden_size"])
    moe_intermediate_size = int(text_config["moe_intermediate_size"])
    topk = int(text_config["num_experts_per_tok"])
    inter_per_tp = moe_intermediate_size // tp_size

    per_layer: dict[int, list[dict[str, Any]]] = defaultdict(list)
    expert_counter: Counter[int] = Counter()
    tuple_counter: Counter[tuple[int, ...]] = Counter()
    rows_by_group_contiguous: list[list[int]] = []
    rows_by_group_round_robin: list[list[int]] = []
    for record in records:
        per_layer[int(record["layer_index"])].append(record)
        row = tuple(int(item) for item in record["topk_ids"][0])
        tuple_counter[row] += 1
        expert_counter.update(row)

        contiguous = [0] * tp_size
        round_robin = [0] * tp_size
        for expert in row:
            contiguous[min(tp_size - 1, expert * tp_size // num_experts)] += 1
            round_robin[expert % tp_size] += 1
        rows_by_group_contiguous.append(contiguous)
        rows_by_group_round_robin.append(round_robin)

    layer_summaries = []
    overlap_values: list[float] = []
    union_sizes: list[float] = []
    for layer_index, layer_records in sorted(per_layer.items()):
        sets = [
            set(int(item) for item in record["topk_ids"][0])
            for record in layer_records
        ]
        union = set().union(*sets)
        intersection = set.intersection(*sets) if sets else set()
        pairwise_jaccard = []
        for idx, left in enumerate(sets):
            for right in sets[idx + 1:]:
                pairwise_jaccard.append(
                    len(left & right) / float(len(left | right))
                    if (left or right) else 1.0
                )
        avg_jaccard = mean(pairwise_jaccard)
        overlap_values.extend(pairwise_jaccard)
        union_sizes.append(float(len(union)))
        layer_summaries.append({
            "layer_index": layer_index,
            "layer": layer_records[0]["layer"],
            "fixture_rows": len(layer_records),
            "union_active_experts": len(union),
            "intersection_active_experts": len(intersection),
            "pairwise_jaccard_mean": avg_jaccard,
            "route_hashes": [record["route_hash"] for record in layer_records],
        })

    def group_pressure(rows_by_group: list[list[int]]) -> dict[str, Any]:
        max_rows = [float(max(row)) for row in rows_by_group]
        imbalance = [
            (max(row) / (sum(row) / float(tp_size))) if sum(row) else 0.0
            for row in rows_by_group
        ]
        return {
            "max_rows_per_group": summary_stats(max_rows),
            "imbalance_vs_ideal": summary_stats(imbalance),
            "examples": rows_by_group[:8],
        }

    # These shapes match the TP-local INT8 MoE shard used by the current path.
    w13_mib = tensor_mib(num_experts * hidden_size * (2 * inter_per_tp), 1)
    w2_mib = tensor_mib(num_experts * inter_per_tp * hidden_size, 1)
    w13_scale_mib = tensor_mib(num_experts * (2 * inter_per_tp), 4)
    w2_scale_mib = tensor_mib(num_experts * hidden_size, 4)
    rows = 1
    moe_inputs = rows * topk
    scratch_mib = {
        "remapped_hidden_states_bf16": tensor_mib(moe_inputs * hidden_size, 2),
        "gemm1_a_int8": tensor_mib(moe_inputs * hidden_size, 1),
        "gemm1_output_bf16": tensor_mib(moe_inputs * (2 * inter_per_tp), 2),
        "act_output_bf16": tensor_mib(moe_inputs * inter_per_tp, 2),
        "gemm2_a_int8": tensor_mib(moe_inputs * inter_per_tp, 1),
        "gemm2_output_bf16": tensor_mib(moe_inputs * hidden_size, 2),
        "rows_per_expert_int32": tensor_mib(num_experts, 4),
        "unpermuted_row_to_permuted_row_int32": tensor_mib(rows * topk, 4),
    }

    return {
        "model_shape": {
            "hidden_size": hidden_size,
            "moe_intermediate_size": moe_intermediate_size,
            "tp_size": tp_size,
            "intermediate_per_tp": inter_per_tp,
            "num_hidden_layers": int(text_config["num_hidden_layers"]),
            "num_experts": num_experts,
            "num_experts_per_tok": topk,
            "mtp_num_hidden_layers": int(text_config.get("mtp_num_hidden_layers", 0)),
        },
        "record_count": len(records),
        "fixture_count": len({record["fixture_index"] for record in records}),
        "layer_count": len(per_layer),
        "active_experts_global": len(expert_counter),
        "total_assignments": sum(int(record["total_assignments"]) for record in records),
        "unique_topk_tuples": len(tuple_counter),
        "top_experts": [
            {"expert": expert, "count": count}
            for expert, count in expert_counter.most_common(24)
        ],
        "top_route_tuples": [
            {"topk_ids": list(route), "count": count, "hash": sha16(list(route))}
            for route, count in tuple_counter.most_common(16)
        ],
        "layer_overlap": {
            "union_active_experts": summary_stats(union_sizes),
            "pairwise_jaccard": summary_stats(overlap_values),
            "layers": layer_summaries,
        },
        "placement_proxy": {
            "contiguous_ep4": group_pressure(rows_by_group_contiguous),
            "round_robin_ep4": group_pressure(rows_by_group_round_robin),
            "interpretation": (
                "For one-token topk-8 decode, expert-parallel placement can be "
                "imbalanced unless hot experts are replicated or work remains "
                "tensor-parallel. Treat this as a routing pressure proxy only."
            ),
        },
        "tp_local_memory_mib": {
            "w13_int8": w13_mib,
            "w2_int8": w2_mib,
            "w13_scales_fp32": w13_scale_mib,
            "w2_scales_fp32": w2_scale_mib,
            "expert_weight_and_scale_total": (
                w13_mib + w2_mib + w13_scale_mib + w2_scale_mib
            ),
            "single_token_scratch": scratch_mib,
            "single_token_scratch_total": sum(scratch_mib.values()),
        },
    }


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def write_markdown(path: Path, result: dict[str, Any]) -> None:
    shape = result["summary"]["model_shape"]
    placement = result["summary"]["placement_proxy"]
    memory = result["summary"]["tp_local_memory_mib"]
    lines = [
        "# Qwen3.6 First-Decode Route Fixture Plan",
        "",
        "This is a CPU-only planning artifact. It converts the compact route "
        "fixture into JSONL rows for existing route simulators and kernel "
        "microbench scripts.",
        "",
        "## Shape",
        "",
        f"- Hidden size: `{shape['hidden_size']}`",
        f"- MoE intermediate size: `{shape['moe_intermediate_size']}`",
        f"- TP-local intermediate size: `{shape['intermediate_per_tp']}`",
        f"- Layers: `{shape['num_hidden_layers']}`",
        f"- Experts: `{shape['num_experts']}`",
        f"- Experts per token: `{shape['num_experts_per_tok']}`",
        f"- MTP layers in config: `{shape['mtp_num_hidden_layers']}`",
        "",
        "## Fixture Summary",
        "",
        f"- Records emitted: `{result['summary']['record_count']}`",
        f"- Fixtures: `{result['summary']['fixture_count']}`",
        f"- Layers: `{result['summary']['layer_count']}`",
        f"- Global active experts: `{result['summary']['active_experts_global']}`",
        f"- Unique topk tuples: `{result['summary']['unique_topk_tuples']}`",
        "",
        "## Placement Proxy",
        "",
        "| policy | mean max rows/group | p95 max rows/group | mean imbalance | p95 imbalance |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in ("contiguous_ep4", "round_robin_ep4"):
        item = placement[name]
        lines.append(
            f"| `{name}` | "
            f"{item['max_rows_per_group']['mean']:.3f} | "
            f"{item['max_rows_per_group']['p95']:.3f} | "
            f"{item['imbalance_vs_ideal']['mean']:.3f} | "
            f"{item['imbalance_vs_ideal']['p95']:.3f} |"
        )
    lines.extend([
        "",
        "Interpretation: one-token/topk-8 decode has only eight routed expert "
        "rows per MoE layer. If we switch sparse MoE work to EP, route placement "
        "can become imbalanced unless the path replicates hot experts or uses a "
        "route-class scheduler. That keeps persistent topk-8 TP-local MoE as "
        "the first kernel target.",
        "",
        "## TP-Local Memory Estimate",
        "",
        f"- Expert weights/scales per TP shard: "
        f"`{memory['expert_weight_and_scale_total']:.3f} MiB`",
        f"- Single-token scratch estimate: "
        f"`{memory['single_token_scratch_total']:.6f} MiB`",
        "",
        "## Generated Artifacts",
        "",
        f"- JSON summary: `{result['output_json']}`",
        f"- JSONL route rows: `{result['output_jsonl']}`",
        "",
        "## Next Commands",
        "",
        "Route placement proxy:",
        "",
        "```bash",
        "python3 scripts/qwen36-route-parallelism-sim.py \\",
        f"  {result['output_jsonl']} \\",
        "  --output-json data/qwen36-quark-int8-tp4-firstdecode-route-parallelism-sim-20260612ct.json \\",
        "  --markdown-out data/qwen36-quark-int8-tp4-firstdecode-route-parallelism-sim-20260612ct.md \\",
        "  --window-size 1 --stride 1 --max-num-tokens 1",
        "```",
        "",
        "Synthetic XPU MoE microbench, only when the serving endpoint is stopped "
        "or an isolated XPU is available:",
        "",
        "```bash",
        "/home/steve/.venvs/vllm-xpu/bin/python scripts/bench-qwen36-int8-moe-kernels.py \\",
        f"  --route-jsonl {result['output_jsonl']} \\",
        "  --route-layer-regex 'layers[.]9[.]mlp[.]experts' \\",
        "  --rows 1 --iterations 100 --warmup 20 \\",
        "  --output-json data/qwen36-quark-int8-firstdecode-l9-r1-microbench-20260612ct.json \\",
        "  --markdown-out data/qwen36-quark-int8-firstdecode-l9-r1-microbench-20260612ct.md",
        "```",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", default=DEFAULT_FIXTURE)
    parser.add_argument("--model-config", default=DEFAULT_MODEL_CONFIG)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--markdown-out")
    parser.add_argument("--tp-size", type=int, default=4)
    parser.add_argument("--stage", default="quark_int8_apply")
    args = parser.parse_args()

    fixture = load_json(args.fixture)
    text = load_text_config(args.model_config)
    records = build_records(fixture, text, stage=args.stage)
    summary = summarize_records(records, text, tp_size=args.tp_size)

    output_json = Path(args.output_json)
    output_jsonl = Path(args.output_jsonl)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_jsonl, records)

    result = {
        "kind": "qwen36_firstdecode_route_fixture_plan",
        "fixture": args.fixture,
        "model_config": args.model_config,
        "output_json": str(output_json),
        "output_jsonl": str(output_jsonl),
        "summary": summary,
    }
    output_json.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.markdown_out:
        write_markdown(Path(args.markdown_out), result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
