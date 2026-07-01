#!/usr/bin/env python3
"""Summarize live Qwen3.6 MoE ABI logs into a oneDNN sidecar plan.

The live ABI logs are diagnostic metadata only. Pointer values are useful for
designing a zero-copy sidecar interface, but they are valid only during the
captured call and must not be replayed out of process.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REQUIRED_TENSORS = [
    "hidden_states",
    "topk_weights",
    "topk_ids",
    "w13",
    "w13_scales",
    "w2",
    "w2_scales",
    "output",
    "remapped_hidden_states",
    "rows_per_expert",
    "unpermuted_row_to_permuted_row",
    "gemm1_a",
    "gemm1_a_scales",
    "gemm1_output",
    "act_output",
    "gemm2_a",
    "gemm2_a_scales",
    "gemm2_output",
]

EXPECTED_DTYPES = {
    "hidden_states": "bfloat16",
    "topk_weights": "float32",
    "topk_ids": "int32",
    "w13": "int8",
    "w13_scales": "float32",
    "w2": "int8",
    "w2_scales": "float32",
    "output": "bfloat16",
    "remapped_hidden_states": "int8",
    "rows_per_expert": "int32",
    "unpermuted_row_to_permuted_row": "int32",
    "gemm1_a": "int8",
    "gemm1_a_scales": "float32",
    "gemm1_output": "bfloat16",
    "act_output": "bfloat16",
    "gemm2_a": "int8",
    "gemm2_a_scales": "float32",
    "gemm2_output": "bfloat16",
}


def load_records(paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}") from exc
                record["_source_file"] = str(path)
                record["_source_line"] = line_no
                records.append(record)
    return records


def layer_index(layer: str) -> int | None:
    match = re.search(r"layers\.(\d+)\.", layer or "")
    if not match:
        return None
    return int(match.group(1))


def local_rank(record: dict[str, Any]) -> str:
    return str(record.get("local_rank") or record.get("rank") or record.get("pid") or "?")


def shape_of(record: dict[str, Any], name: str) -> list[int] | None:
    tensor = record.get("tensors", {}).get(name)
    if not tensor:
        return None
    shape = tensor.get("shape")
    if not isinstance(shape, list):
        return None
    return [int(x) for x in shape]


def expected_shapes(record: dict[str, Any]) -> dict[str, list[int]]:
    shape = record.get("shape", {})
    rows = int(shape.get("num_rows", 0))
    topk = int(shape.get("topk", 0))
    hidden = int(shape.get("hidden_size", 0))
    inter = int(shape.get("inter_size", 0))
    experts = int(shape.get("num_experts", 0))
    moe_inputs = int(shape.get("num_moe_inputs", rows * topk))
    return {
        "hidden_states": [rows, hidden],
        "topk_weights": [rows, topk],
        "topk_ids": [rows, topk],
        "w13": [experts, hidden, 2 * inter],
        "w13_scales": [experts, 2 * inter],
        "w2": [experts, inter, hidden],
        "w2_scales": [experts, hidden],
        "output": [rows, hidden],
        "remapped_hidden_states": [moe_inputs, hidden],
        "rows_per_expert": [experts],
        "unpermuted_row_to_permuted_row": [rows, topk],
        "gemm1_a": [moe_inputs, hidden],
        "gemm1_a_scales": [moe_inputs, 1],
        "gemm1_output": [moe_inputs, 2 * inter],
        "act_output": [moe_inputs, inter],
        "gemm2_a": [moe_inputs, inter],
        "gemm2_a_scales": [moe_inputs, 1],
        "gemm2_output": [moe_inputs, hidden],
    }


def tensor_descriptor(record: dict[str, Any], name: str) -> dict[str, Any] | None:
    tensor = record.get("tensors", {}).get(name)
    if not tensor:
        return None
    return {
        "ptr": tensor.get("data_ptr"),
        "device": tensor.get("device"),
        "dtype": tensor.get("dtype"),
        "shape": tensor.get("shape"),
        "stride": tensor.get("stride"),
        "contiguous": bool(tensor.get("is_contiguous")),
        "numel": tensor.get("numel"),
    }


def validate_record(record: dict[str, Any]) -> tuple[list[str], list[str]]:
    tensors = record.get("tensors", {})
    expected = expected_shapes(record)
    missing: list[str] = []
    problems: list[str] = []
    for name in REQUIRED_TENSORS:
        tensor = tensors.get(name)
        if not tensor:
            missing.append(name)
            continue
        dtype = tensor.get("dtype")
        if dtype != EXPECTED_DTYPES[name]:
            problems.append(f"{name}: dtype {dtype} != {EXPECTED_DTYPES[name]}")
        if tensor.get("shape") != expected.get(name):
            problems.append(f"{name}: shape {tensor.get('shape')} != {expected.get(name)}")
        if not tensor.get("is_contiguous"):
            problems.append(f"{name}: non-contiguous")

    shape = record.get("shape", {})
    rows = int(shape.get("num_rows", 0))
    topk = int(shape.get("topk", 0))
    moe_inputs = int(shape.get("num_moe_inputs", 0))
    if rows and topk and moe_inputs != rows * topk:
        problems.append(f"num_moe_inputs {moe_inputs} != num_rows*topk {rows * topk}")

    route = record.get("route", {})
    rows_sum = route.get("rows_sum")
    if rows_sum is not None and moe_inputs and int(rows_sum) != moe_inputs:
        problems.append(f"route.rows_sum {rows_sum} != num_moe_inputs {moe_inputs}")
    return missing, problems


def derive_descriptor(record: dict[str, Any]) -> dict[str, Any]:
    shape = record.get("shape", {})
    rows = int(shape.get("num_rows", 0))
    topk = int(shape.get("topk", 0))
    hidden = int(shape.get("hidden_size", 0))
    inter = int(shape.get("inter_size", 0))
    experts = int(shape.get("num_experts", 0))
    moe_inputs = int(shape.get("num_moe_inputs", rows * topk))
    route = record.get("route", {})
    rows_per_expert = route.get("rows_sample") or []
    active_experts = [idx for idx, count in enumerate(rows_per_expert) if int(count) > 0]
    grouped_offsets = []
    cursor = 0
    for count in rows_per_expert:
        grouped_offsets.append(cursor)
        cursor += int(count)

    return {
        "rank": local_rank(record),
        "pid": record.get("pid"),
        "layer": record.get("layer"),
        "layer_index": layer_index(str(record.get("layer", ""))),
        "source": {
            "file": record.get("_source_file"),
            "line": record.get("_source_line"),
            "call": record.get("call"),
        },
        "shape": {
            "num_rows": rows,
            "topk": topk,
            "num_moe_inputs": moe_inputs,
            "hidden_size": hidden,
            "inter_size": inter,
            "num_experts": experts,
            "gemm1": {"m": moe_inputs, "k": hidden, "n": 2 * inter},
            "gemm2": {"m": moe_inputs, "k": inter, "n": hidden},
        },
        "route": {
            "active_expert_count": len(active_experts),
            "active_experts_head": active_experts[:32],
            "rows_sum": route.get("rows_sum"),
            "max_rows_per_expert": route.get("max_rows_per_expert"),
            "grouped_offsets_head": grouped_offsets[:32],
            "offsets_cover_rows": cursor == moe_inputs,
        },
        "tensors": {
            name: tensor_descriptor(record, name)
            for name in REQUIRED_TENSORS
            if tensor_descriptor(record, name) is not None
        },
        "oneDNN_sidecar_call": {
            "candidate_name": "qwen36_w8a8_moe_onednn_sidecar",
            "scope": "rank-local MoE layer call",
            "required_zero_copy_inputs": [
                "gemm1_a",
                "gemm1_a_scales",
                "w13",
                "w13_scales",
                "rows_per_expert",
                "gemm2_a",
                "gemm2_a_scales",
                "w2",
                "w2_scales",
                "topk_weights",
                "unpermuted_row_to_permuted_row",
            ],
            "required_outputs": ["gemm1_output", "act_output", "gemm2_output", "output"],
            "lifetime_rule": "Pointers are live-call only; the sidecar must run inside xpu_fused_moe before buffers are freed or reused.",
            "queue_rule": "Use the same rank-local XPU device/context/queue or explicit SYCL interop events; no CPU copies.",
        },
    }


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    missing_counter: Counter[str] = Counter()
    problem_counter: Counter[str] = Counter()
    by_rank: Counter[str] = Counter()
    by_layer: Counter[str] = Counter()
    descriptor_samples: list[dict[str, Any]] = []
    groups: dict[tuple[str, str, int], int] = defaultdict(int)

    for record in records:
        missing, problems = validate_record(record)
        missing_counter.update(missing)
        problem_counter.update(problems)
        rank = local_rank(record)
        layer = str(record.get("layer", "unknown"))
        by_rank[rank] += 1
        by_layer[layer] += 1
        shape = record.get("shape", {})
        groups[(rank, layer, int(shape.get("num_rows", 0)))] += 1
        if len(descriptor_samples) < 8:
            descriptor_samples.append(derive_descriptor(record))

    return {
        "record_count": len(records),
        "ranks": dict(sorted(by_rank.items())),
        "layers": dict(sorted(by_layer.items())),
        "rank_layer_shape_groups": [
            {
                "rank": rank,
                "layer": layer,
                "num_rows": rows,
                "records": count,
            }
            for (rank, layer, rows), count in sorted(groups.items())
        ],
        "required_tensors": REQUIRED_TENSORS,
        "missing_tensors": dict(sorted(missing_counter.items())),
        "validation_problem_counts": dict(sorted(problem_counter.items())),
        "all_required_tensors_present": not missing_counter,
        "all_shape_dtype_contiguity_checks_passed": not problem_counter,
        "descriptor_samples": descriptor_samples,
        "implementation_gates": [
            "Build a C++ sidecar entry point that accepts Tensor-derived device pointers and derived grouped offsets without serializing to files.",
            "Wrap live XPU/USM pointers in oneDNN memory objects on the same rank-local SYCL device and prove no implicit host copy.",
            "Cache packed w13/w2 weights and oneDNN grouped-matmul primitives by layer/shape; update rows_per_expert and offsets per call.",
            "Run GEMM1 plus activation/quant plus GEMM2 and final gather with max_abs_diff=0.0 versus xpu_fused_moe before timing claims.",
            "Add a kill switch and per-rank fallback to current xpu_fused_moe on any sidecar validation failure or unsupported shape.",
        ],
        "bigger_bets": [
            "A route-class layerlet generator backed by oneDNN parity fixtures, targeting only hot route classes where launch and epilogue fusion can beat oneDNN.",
            "A fixed-shape c1 decode lane that bypasses general vLLM scheduling for latency-critical single-user traffic after the prompt is admitted.",
            "Expert-parallel or hot-expert replication simulations that spend the large remaining VRAM budget to reduce c1 cross-card latency.",
            "A verifier-owned speculative transaction API with temporary KV/request state, so DFlash/MTP/n-gram proposers can be tested without changing accepted model outputs.",
            "A Level Zero command-list supernode for one token that captures MoE, dense, attention, and TP collective boundaries without lowering precision.",
        ],
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Qwen3.6 Live ABI Sidecar Plan")
    lines.append("")
    lines.append("This is a design artifact derived from disabled-by-default live ABI smoke logs.")
    lines.append("It is not a speed claim and it does not replay stale pointer values.")
    lines.append("")
    lines.append("## Coverage")
    lines.append("")
    lines.append(f"- Records: `{summary['record_count']}`")
    lines.append(f"- Ranks: `{summary['ranks']}`")
    lines.append(f"- Layers: `{len(summary['layers'])}` unique layer names")
    lines.append(f"- Required tensors present: `{summary['all_required_tensors_present']}`")
    lines.append(
        "- Shape/dtype/contiguity checks passed: "
        f"`{summary['all_shape_dtype_contiguity_checks_passed']}`"
    )
    if summary["missing_tensors"]:
        lines.append(f"- Missing tensors: `{summary['missing_tensors']}`")
    if summary["validation_problem_counts"]:
        lines.append("- Validation problems:")
        for problem, count in summary["validation_problem_counts"].items():
            lines.append(f"  - `{problem}`: `{count}`")
    lines.append("")
    lines.append("## Derived Sidecar ABI")
    lines.append("")
    lines.append("The live logs already expose the tensors needed for a zero-copy sidecar:")
    for name in summary["required_tensors"]:
        lines.append(f"- `{name}`")
    lines.append("")
    sample = summary["descriptor_samples"][0] if summary["descriptor_samples"] else {}
    if sample:
        shape = sample["shape"]
        route = sample["route"]
        lines.append("Representative descriptor:")
        lines.append("")
        lines.append(f"- GEMM1: `M={shape['gemm1']['m']}, K={shape['gemm1']['k']}, N={shape['gemm1']['n']}`")
        lines.append(f"- GEMM2: `M={shape['gemm2']['m']}, K={shape['gemm2']['k']}, N={shape['gemm2']['n']}`")
        lines.append(f"- Experts: `{shape['num_experts']}`, top-k: `{shape['topk']}`")
        lines.append(f"- Active experts in sample: `{route['active_expert_count']}`")
        lines.append(f"- Route offsets cover all rows: `{route['offsets_cover_rows']}`")
    lines.append("")
    lines.append("## Missing C++ Work")
    lines.append("")
    for gate in summary["implementation_gates"]:
        lines.append(f"- {gate}")
    lines.append("")
    lines.append("## Bigger Bets Added")
    lines.append("")
    for item in summary["bigger_bets"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Next Guarded Call")
    lines.append("")
    lines.append(
        "Start with a disabled-by-default sidecar path for one layer/rank that "
        "wraps live XPU tensors in oneDNN memory, executes GEMM1 and GEMM2 with "
        "cached primitives, falls back on any unsupported condition, and records "
        "final-layer `max_abs_diff=0.0` before endpoint timing is considered."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-abi-jsonl", nargs="+", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    args = parser.parse_args()

    records = load_records(args.live_abi_jsonl)
    if not records:
        raise SystemExit("no records loaded")

    summary = summarize(records)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_out.write_text(render_markdown(summary), encoding="utf-8")
    print(f"loaded {len(records)} records")
    print(f"wrote {args.out_json}")
    print(f"wrote {args.markdown_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
