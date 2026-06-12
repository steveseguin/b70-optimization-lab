#!/usr/bin/env python3
"""Export small gather fixtures for resident oneDNN MoE island windows.

The existing oneDNN MoE island packet already contains large GEMM inputs,
weights, scales, and grouped-GEMM references. This script writes only the small
final-gather contract needed by the resident C++ runner:

- moe_topk_weights.f32.bin
- moe_topk_ids.i64.bin
- moe_unpermuted.i32.bin
- moe_ref_output.bf16.bin or moe_ref_output.fp16.bin

It intentionally does not rewrite the large GEMM weight/input files.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import torch


DEFAULT_BENCH_SCRIPT = "scripts/bench-qwen36-int8-moe-kernels.py"
DEFAULT_ROUTE_JSONL = (
    "data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench-script", default=DEFAULT_BENCH_SCRIPT)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--route-jsonl", default=DEFAULT_ROUTE_JSONL)
    parser.add_argument("--route-layer-regex",
                        default=r"layers[.]9[.]mlp[.]experts")
    parser.add_argument("--route-stage-regex", default=r"^quark_int8_apply$")
    parser.add_argument("--rows", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260612)
    parser.add_argument("--tp-size", type=int, default=4)
    parser.add_argument("--dtype", choices=("bf16", "fp16"), default="bf16")
    parser.add_argument("--device", default="xpu")
    parser.add_argument("--out-json", required=True)
    return parser.parse_args()


def load_module(path: str):
    spec = importlib.util.spec_from_file_location("qwen36_moe_bench", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dtype_from_name(name: str) -> torch.dtype:
    if name == "bf16":
        return torch.bfloat16
    if name == "fp16":
        return torch.float16
    raise ValueError(name)


def write_tensor(path: Path, tensor: torch.Tensor) -> None:
    cpu = tensor.detach().contiguous().cpu()
    if cpu.dtype is torch.bfloat16:
        cpu.view(torch.uint16).numpy().tofile(path)
    else:
        cpu.numpy().tofile(path)


def tensor_checksum(tensor: torch.Tensor) -> float:
    return float(tensor.detach().float().sum().item())


def parse_manifest(manifest_path: Path) -> list[tuple[int, Path]]:
    windows: list[tuple[int, Path]] = []
    start_re = re.compile(r"_start_([0-9]+)$")
    base = manifest_path.parent
    with manifest_path.open() as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            fields = [item.strip() for item in line.split(",")]
            if len(fields) < 2:
                raise ValueError(f"manifest line {line_no} needs two columns")
            gemm2_meta = Path(fields[1])
            if not gemm2_meta.is_absolute():
                gemm2_meta = base / gemm2_meta
            window_dir = gemm2_meta.parent
            match = start_re.search(window_dir.name)
            if not match:
                raise ValueError(
                    f"cannot infer route start from {window_dir.name!r}")
            windows.append((int(match.group(1)), window_dir))
    if not windows:
        raise ValueError(f"manifest has no windows: {manifest_path}")
    return windows


def ensure_ops_available() -> None:
    missing = []
    for namespace, op_name in (
        ("_xpu_C", "cutlass_grouped_gemm_w8a8_int8_interface"),
        ("_moe_C", "remap_hidden_states"),
        ("_moe_C", "moe_gather"),
    ):
        if not hasattr(getattr(torch.ops, namespace), op_name):
            missing.append(f"{namespace}.{op_name}")
    if missing:
        raise RuntimeError("Missing required XPU ops: " + ", ".join(missing))


def main() -> int:
    args = parse_args()
    bench = load_module(args.bench_script)
    ensure_ops_available()

    manifest_path = Path(args.manifest)
    windows = parse_manifest(manifest_path)
    text_config = bench.load_text_config(bench.DEFAULT_MODEL_CONFIG)
    route_rows, route_meta = bench.load_route_topk_rows(
        args.route_jsonl,
        layer_regex=args.route_layer_regex,
        stage_regex=args.route_stage_regex,
        min_num_tokens=1,
        max_num_tokens=1,
    )

    dtype = dtype_from_name(args.dtype)
    hidden_size = int(text_config["hidden_size"])
    inter_size = int(text_config["moe_intermediate_size"]) // args.tp_size
    num_experts = int(text_config["num_experts"])
    topk = int(text_config["num_experts_per_tok"])
    summary: dict[str, Any] = {
        "kind": "qwen36_onednn_gather_fixture_export",
        "manifest": str(manifest_path),
        "route_metadata": route_meta,
        "rows": args.rows,
        "topk": topk,
        "hidden_size": hidden_size,
        "dtype": args.dtype,
        "windows": [],
    }

    for route_start, window_dir in windows:
        inputs = bench.make_inputs(
            rows=args.rows,
            hidden_size=hidden_size,
            inter_size=inter_size,
            num_experts=num_experts,
            topk=topk,
            dtype=dtype,
            device=args.device,
            seed=args.seed + args.rows,
            route_topk_rows=route_rows,
            route_start_index=route_start,
        )
        scratch = bench.make_scratch(
            rows=args.rows,
            hidden_size=hidden_size,
            inter_size=inter_size,
            num_experts=num_experts,
            topk=topk,
            dtype=dtype,
            device=args.device,
        )
        ref_output = bench.xpu_fused_moe(
            hidden_states=inputs["hidden_states"],
            w13=inputs["w13"],
            w13_scales=inputs["w13_scales"],
            w13_bias=None,
            w2=inputs["w2"],
            w2_scales=inputs["w2_scales"],
            w2_bias=None,
            topk_weights=inputs["topk_weights"],
            topk_ids=inputs["topk_ids"],
            n_experts_per_token=topk,
            activation="silu",
            num_experts=num_experts,
            is_int8=True,
        )
        scratch["rows_per_expert"].zero_()
        torch.ops._moe_C.remap_hidden_states(
            hidden_states=inputs["hidden_states"],
            hidden_states_scales=None,
            remapped_hidden_states=scratch["remapped_hidden_states"],
            remapped_hidden_states_scales=None,
            expert_map=None,
            rows_per_expert=scratch["rows_per_expert"],
            unpermuted_row_to_permuted_row=scratch["unpermuted"],
            topk_ids=inputs["topk_ids"],
            total_experts_num=num_experts,
            local_experts_num=num_experts,
        )
        torch.xpu.synchronize()

        write_tensor(window_dir / "moe_topk_weights.f32.bin",
                     inputs["topk_weights"])
        write_tensor(window_dir / "moe_topk_ids.i64.bin", inputs["topk_ids"])
        write_tensor(window_dir / "moe_unpermuted.i32.bin",
                     scratch["unpermuted"].to(torch.int32))
        write_tensor(window_dir / f"moe_ref_output.{args.dtype}.bin",
                     ref_output)
        # The C++ runner currently expects the stable bf16 filename for this
        # packet. Keep it explicit even when dtype is passed as the default.
        if args.dtype == "bf16":
            write_tensor(window_dir / "moe_ref_output.bf16.bin", ref_output)

        prior_checksum = None
        prior_path = window_dir / "onednn_moe_island_result.json"
        if prior_path.exists():
            prior = json.loads(prior_path.read_text())
            prior_checksum = prior.get("ref_output_checksum_f32")

        checksum = tensor_checksum(ref_output)
        row = {
            "route_start_index": route_start,
            "window_dir": str(window_dir),
            "topk_ids": inputs["topk_ids"].detach().cpu().tolist(),
            "topk_weights_checksum_f32":
            tensor_checksum(inputs["topk_weights"]),
            "unpermuted": scratch["unpermuted"].detach().cpu().tolist(),
            "ref_output_checksum_f32": checksum,
            "prior_ref_output_checksum_f32": prior_checksum,
            "prior_ref_output_checksum_delta": (
                None if prior_checksum is None else checksum -
                float(prior_checksum)),
        }
        summary["windows"].append(row)

    Path(args.out_json).write_text(json.dumps(summary, indent=2,
                                              sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
