#!/usr/bin/env python3
"""Replay one Qwen3.6 W8A8 MoE layer with oneDNN grouped-GEMM islands.

This is an exactness scaffold, not an endpoint-speed benchmark. Python keeps
the current XPU remap, quantization, activation, and gather semantics; oneDNN
replaces GEMM1 and GEMM2 through exported file-backed cases. If this matches
`xpu_fused_moe` exactly, the next useful step is moving the same layout into a
resident primitive cache instead of the file boundary.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch


DEFAULT_ROUTE_JSONL = (
    "data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl"
)
DEFAULT_BENCH_SCRIPT = "scripts/bench-qwen36-int8-moe-kernels.py"
DEFAULT_RUNNER = "scripts/run-onednn-grouped-int8-case.sh"


def parse_int_list(value: str) -> list[int]:
    values: list[int] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            parts = item.split(":")
            if len(parts) not in (2, 3):
                raise argparse.ArgumentTypeError(
                    f"Invalid integer range {item!r}; use start:stop[:step]")
            start = int(parts[0])
            stop = int(parts[1])
            step = int(parts[2]) if len(parts) == 3 else 1
            if step == 0:
                raise argparse.ArgumentTypeError("range step cannot be zero")
            values.extend(range(start, stop, step))
        else:
            values.append(int(item))
    if not values:
        raise argparse.ArgumentTypeError("at least one integer is required")
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench-script", default=DEFAULT_BENCH_SCRIPT)
    parser.add_argument("--runner", default=DEFAULT_RUNNER)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--route-jsonl", default=DEFAULT_ROUTE_JSONL)
    parser.add_argument(
        "--route-layer-regex",
        default=r"layers[.]9[.]mlp[.]experts",
        help="Regex selecting the captured MoE layer to replay.",
    )
    parser.add_argument("--route-stage-regex", default=r"^quark_int8_apply$")
    parser.add_argument("--route-start-index", type=int, default=0)
    parser.add_argument(
        "--route-start-indices",
        type=parse_int_list,
        help=(
            "Comma-separated route offsets or ranges to replay, for example "
            "'0,8,16' or '0:64:4'. When set, each window is written under "
            "out-dir/window_NNN_start_X and a multi-window summary is emitted."
        ),
    )
    parser.add_argument("--rows", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260612)
    parser.add_argument("--tp-size", type=int, default=4)
    parser.add_argument("--dtype", choices=("bf16", "fp16"), default="bf16")
    parser.add_argument("--device", default="xpu")
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--compile-only", action="store_true")
    parser.add_argument(
        "--case-bin",
        default="/tmp/qwen36-onednn-moe-island-case-runner-20260612",
        help="Reusable oneDNN case runner binary path.",
    )
    return parser.parse_args()


def load_bench_module(path: str):
    spec = importlib.util.spec_from_file_location("qwen36_moe_bench", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ensure_xpu_ops_available() -> None:
    missing = []
    for op_name in (
        "cutlass_grouped_gemm_w8a8_int8_interface",
        "per_token_quant_int8_xpu",
    ):
        if not hasattr(torch.ops._xpu_C, op_name):
            missing.append(f"_xpu_C.{op_name}")
    for op_name in ("remap_hidden_states", "moe_gather"):
        if not hasattr(torch.ops._moe_C, op_name):
            missing.append(f"_moe_C.{op_name}")
    if missing:
        raise RuntimeError(
            "Missing required vllm_xpu_kernels ops: "
            + ", ".join(missing)
            + ". Run with the local vLLM/vllm-xpu-kernels environment, for "
            "example PYTHONPATH=/home/steve/src/vllm:/home/steve/src/"
            "vllm-xpu-kernels and LD_LIBRARY_PATH including /home/steve/src/"
            "vllm-xpu-kernels/vllm_xpu_kernels."
        )


def dtype_from_name(name: str) -> torch.dtype:
    if name == "bf16":
        return torch.bfloat16
    if name == "fp16":
        return torch.float16
    raise ValueError(name)


def tensor_checksum(tensor: torch.Tensor) -> float:
    return float(tensor.detach().float().sum().item())


def write_tensor(path: Path, tensor: torch.Tensor) -> None:
    cpu = tensor.detach().contiguous().cpu()
    if cpu.dtype is torch.bfloat16:
        cpu.view(torch.uint16).numpy().tofile(path)
    else:
        cpu.numpy().tofile(path)


def load_tensor(path: Path, dtype: torch.dtype, shape: tuple[int, ...],
                device: str) -> torch.Tensor:
    if dtype is torch.bfloat16:
        raw = np.fromfile(path, dtype=np.uint16)
        tensor = torch.from_numpy(raw.copy()).view(torch.bfloat16)
    elif dtype is torch.float16:
        raw = np.fromfile(path, dtype=np.float16)
        tensor = torch.from_numpy(raw.copy()).to(torch.float16)
    elif dtype is torch.float32:
        raw = np.fromfile(path, dtype=np.float32)
        tensor = torch.from_numpy(raw.copy())
    else:
        raise ValueError(dtype)
    return tensor.view(*shape).to(device)


def write_meta(path: Path, values: dict[str, Any]) -> None:
    with path.open("w") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def case_paths(name: str, dst_dtype: str) -> dict[str, str]:
    return {
        "a_path": f"{name}_A.s8.bin",
        "a_scales_path": f"{name}_A_scales.f32.bin",
        "b_path": f"{name}_B.s8.bin",
        "b_acb_path": f"{name}_B_acb.s8.bin",
        "b_scales_path": f"{name}_B_scales.f32.bin",
        "rows_path": f"{name}_rows.i32.bin",
        "xpu_out_path": f"{name}_xpu_out.{dst_dtype}.bin",
        "xpu_out_f32_path": f"{name}_xpu_out.f32.bin",
    }


def export_case(
    *,
    out_dir: Path,
    name: str,
    a: torch.Tensor,
    a_scales: torch.Tensor,
    b: torch.Tensor,
    b_scales: torch.Tensor,
    rows_per_expert: torch.Tensor,
    xpu_out: torch.Tensor,
    num_experts: int,
    dst_dtype: str,
    weight_source_dir: Path | None = None,
) -> Path:
    k_dim = int(a.shape[1])
    n_dim = int(xpu_out.shape[1])
    paths = case_paths(name, dst_dtype)
    write_tensor(out_dir / paths["a_path"], a)
    write_tensor(out_dir / paths["a_scales_path"], a_scales.view(-1, 1))
    if weight_source_dir is None:
        write_tensor(out_dir / paths["b_path"], b)
        write_tensor(
            out_dir / paths["b_acb_path"],
            b.permute(0, 2, 1).contiguous(),
        )
        write_tensor(out_dir / paths["b_scales_path"], b_scales)
    else:
        for key in ("b_path", "b_acb_path", "b_scales_path"):
            paths[key] = os.path.relpath(
                weight_source_dir / paths[key],
                out_dir,
            )
    write_tensor(out_dir / paths["rows_path"], rows_per_expert.to(torch.int32))
    write_tensor(out_dir / paths["xpu_out_path"], xpu_out)
    write_tensor(out_dir / paths["xpu_out_f32_path"], xpu_out.float())
    meta = {
        "name": name,
        "num_experts": num_experts,
        "total_tokens": int(a.shape[0]),
        "k": k_dim,
        "n": n_dim,
        "dst_dtype": dst_dtype,
        "weight_format": "abc",
        **paths,
    }
    meta_path = out_dir / f"{name}.meta"
    write_meta(meta_path, meta)
    return meta_path


def run_onednn_case(
    *,
    runner: Path,
    meta_path: Path,
    out_path: Path,
    json_path: Path,
    case_bin: str,
    warmup: int,
    iterations: int,
    compile_first: bool,
) -> dict[str, Any]:
    env = os.environ.copy()
    env.update({
        "CASE_BIN": case_bin,
        "ONEDNN_CASE_META": str(meta_path.resolve()),
        "ONEDNN_CASE_OUTPUT": str(out_path.resolve()),
        "ONEDNN_CASE_JSON": str(json_path.resolve()),
        "ONEDNN_WEIGHT_FORMAT": "acb",
        "ONEDNN_CASE_WARMUP": str(warmup),
        "ONEDNN_CASE_ITERATIONS": str(iterations),
    })
    if not compile_first:
        env["ONEDNN_SKIP_COMPILE"] = "1"
    subprocess.run(["bash", str(runner)], check=True, env=env)
    return json.loads(json_path.read_text())


def max_abs_diff(left: torch.Tensor, right: torch.Tensor) -> float:
    return float((left - right).abs().max().item())


def replay_window(
    *,
    args: argparse.Namespace,
    bench: Any,
    text_config: dict[str, Any],
    route_rows: list[list[int]],
    route_meta: dict[str, Any],
    out_dir: Path,
    route_start_index: int,
    compile_first_case: bool,
    weight_source_dir: Path | None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    dtype = dtype_from_name(args.dtype)
    hidden_size = int(text_config["hidden_size"])
    inter_size = int(text_config["moe_intermediate_size"]) // args.tp_size
    num_experts = int(text_config["num_experts"])
    topk = int(text_config["num_experts_per_tok"])
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
        route_start_index=route_start_index,
    )
    topk_summary = bench.summarize_topk_ids(inputs["topk_ids"])

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
    staged_output = bench.manual_int8_moe_preallocated_once(
        hidden_states=inputs["hidden_states"],
        w13=inputs["w13"],
        w13_scales=inputs["w13_scales"],
        w2=inputs["w2"],
        w2_scales=inputs["w2_scales"],
        topk_weights=inputs["topk_weights"],
        topk_ids=inputs["topk_ids"],
        num_experts=num_experts,
        topk=topk,
        scratch=scratch,
    )
    torch.xpu.synchronize()

    rows_per_expert = scratch["rows_per_expert"]
    rows_per_expert.zero_()
    torch.ops._moe_C.remap_hidden_states(
        hidden_states=inputs["hidden_states"],
        hidden_states_scales=None,
        remapped_hidden_states=scratch["remapped_hidden_states"],
        remapped_hidden_states_scales=None,
        expert_map=None,
        rows_per_expert=rows_per_expert,
        unpermuted_row_to_permuted_row=scratch["unpermuted"],
        topk_ids=inputs["topk_ids"],
        total_experts_num=num_experts,
        local_experts_num=num_experts,
    )
    gemm1_a, gemm1_a_scales = bench._per_token_quant_int8_maybe_out(
        scratch["remapped_hidden_states"],
        scratch["gemm1_a"],
        scratch["gemm1_a_scales"],
    )
    gemm1_scales = bench._normalize_int8_weight_scales(
        inputs["w13_scales"], 2 * inter_size)
    xpu_gemm1 = torch.empty_like(scratch["gemm1_output"])
    torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_interface(
        ptr_A=gemm1_a,
        ptr_A_scales=gemm1_a_scales,
        ptr_B=inputs["w13"],
        ptr_B_scales=gemm1_scales,
        ptr_bias=None,
        ptr_D=xpu_gemm1,
        rows_per_expert=rows_per_expert,
        N=2 * inter_size,
        K=hidden_size,
        num_experts=num_experts,
    )
    torch.xpu.synchronize()

    gemm1_meta = export_case(
        out_dir=out_dir,
        name="gemm1",
        a=gemm1_a,
        a_scales=gemm1_a_scales,
        b=inputs["w13"],
        b_scales=gemm1_scales,
        rows_per_expert=rows_per_expert,
        xpu_out=xpu_gemm1,
        num_experts=num_experts,
        dst_dtype=args.dtype,
        weight_source_dir=weight_source_dir,
    )
    runner = Path(args.runner)
    wall_start = time.perf_counter()
    gemm1_json = run_onednn_case(
        runner=runner,
        meta_path=gemm1_meta,
        out_path=out_dir / f"gemm1_onednn_acb_out.{args.dtype}.bin",
        json_path=out_dir / "gemm1_onednn_acb_result.json",
        case_bin=args.case_bin,
        warmup=args.warmup,
        iterations=args.iterations,
        compile_first=compile_first_case,
    )
    gemm1_onednn = load_tensor(
        out_dir / f"gemm1_onednn_acb_out.{args.dtype}.bin",
        dtype,
        tuple(xpu_gemm1.shape),
        args.device,
    )
    bench.fused_moe_activation(scratch["act_output"], gemm1_onednn, "silu")
    gemm2_a, gemm2_a_scales = bench._per_token_quant_int8_maybe_out(
        scratch["act_output"],
        scratch["gemm2_a"],
        scratch["gemm2_a_scales"],
    )
    gemm2_scales = bench._normalize_int8_weight_scales(
        inputs["w2_scales"], hidden_size)
    xpu_gemm2 = torch.empty_like(scratch["gemm2_output"])
    torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_interface(
        ptr_A=gemm2_a,
        ptr_A_scales=gemm2_a_scales,
        ptr_B=inputs["w2"],
        ptr_B_scales=gemm2_scales,
        ptr_bias=None,
        ptr_D=xpu_gemm2,
        rows_per_expert=rows_per_expert,
        N=hidden_size,
        K=inter_size,
        num_experts=num_experts,
    )
    torch.xpu.synchronize()

    gemm2_meta = export_case(
        out_dir=out_dir,
        name="gemm2",
        a=gemm2_a,
        a_scales=gemm2_a_scales,
        b=inputs["w2"],
        b_scales=gemm2_scales,
        rows_per_expert=rows_per_expert,
        xpu_out=xpu_gemm2,
        num_experts=num_experts,
        dst_dtype=args.dtype,
        weight_source_dir=weight_source_dir,
    )
    gemm2_json = run_onednn_case(
        runner=runner,
        meta_path=gemm2_meta,
        out_path=out_dir / f"gemm2_onednn_acb_out.{args.dtype}.bin",
        json_path=out_dir / "gemm2_onednn_acb_result.json",
        case_bin=args.case_bin,
        warmup=args.warmup,
        iterations=args.iterations,
        compile_first=False,
    )
    gemm2_onednn = load_tensor(
        out_dir / f"gemm2_onednn_acb_out.{args.dtype}.bin",
        dtype,
        tuple(xpu_gemm2.shape),
        args.device,
    )
    onednn_output = torch.empty_like(ref_output)
    torch.ops._moe_C.moe_gather(
        onednn_output,
        gemm2_onednn,
        inputs["topk_weights"],
        scratch["unpermuted"],
        num_experts,
    )
    torch.xpu.synchronize()
    wall_s = time.perf_counter() - wall_start

    result = {
        "kind": "file_backed_onednn_moe_island",
        "note": (
            "Correctness scaffold only. File IO and process boundaries are "
            "excluded from endpoint-speed interpretation."
        ),
        "route_metadata": route_meta,
        "route_start_index": route_start_index,
        "rows": args.rows,
        "moe_inputs": args.rows * topk,
        "topk_summary": topk_summary,
        "rows_per_expert": [
            int(item)
            for item in rows_per_expert.detach().cpu().to(torch.int32).tolist()
        ],
        "hidden_size": hidden_size,
        "inter_size_per_tp": inter_size,
        "num_experts": num_experts,
        "topk": topk,
        "dtype": args.dtype,
        "tp_size": args.tp_size,
        "gemm1_onednn": gemm1_json,
        "gemm2_onednn": gemm2_json,
        "gemm1_vs_xpu_max_abs_diff": max_abs_diff(gemm1_onednn, xpu_gemm1),
        "gemm2_vs_xpu_max_abs_diff": max_abs_diff(gemm2_onednn, xpu_gemm2),
        "staged_vs_xpu_fused_moe_max_abs_diff":
        max_abs_diff(staged_output, ref_output),
        "onednn_island_vs_xpu_fused_moe_max_abs_diff":
        max_abs_diff(onednn_output, ref_output),
        "onednn_island_vs_staged_max_abs_diff":
        max_abs_diff(onednn_output, staged_output),
        "ref_output_checksum_f32": tensor_checksum(ref_output),
        "onednn_output_checksum_f32": tensor_checksum(onednn_output),
        "file_backed_wall_s": wall_s,
    }
    (out_dir / "onednn_moe_island_result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def summarize_multi_window(
    *,
    args: argparse.Namespace,
    route_meta: dict[str, Any],
    window_results: list[dict[str, Any]],
    out_dir: Path,
) -> dict[str, Any]:
    diff_keys = [
        "gemm1_vs_xpu_max_abs_diff",
        "gemm2_vs_xpu_max_abs_diff",
        "staged_vs_xpu_fused_moe_max_abs_diff",
        "onednn_island_vs_xpu_fused_moe_max_abs_diff",
        "onednn_island_vs_staged_max_abs_diff",
    ]
    summary = {
        "kind": "multi_window_file_backed_onednn_moe_island",
        "note": (
            "Correctness scaffold only. Each window regenerates remap, "
            "quantization, oneDNN GEMM outputs, and final gather for its "
            "captured route slice. File IO and process boundaries are excluded "
            "from endpoint-speed interpretation."
        ),
        "route_metadata": route_meta,
        "route_start_indices": [
            int(result["route_start_index"]) for result in window_results
        ],
        "rows": args.rows,
        "dtype": args.dtype,
        "tp_size": args.tp_size,
        "window_count": len(window_results),
        "aggregate_max_abs_diffs": {
            key: max(float(result[key]) for result in window_results)
            for key in diff_keys
        },
        "all_exact": all(
            float(result[key]) == 0.0
            for result in window_results
            for key in diff_keys
        ),
        "windows": [
            {
                "route_start_index": int(result["route_start_index"]),
                "subdir": f"window_{index:03d}_start_"
                f"{int(result['route_start_index'])}",
                "topk_summary": result["topk_summary"],
                "active_experts": result["topk_summary"]["active_experts"],
                "rows_per_expert_nonzero": [
                    {"expert": expert, "rows": rows}
                    for expert, rows in enumerate(result["rows_per_expert"])
                    if rows
                ],
                "gemm1_vs_xpu_max_abs_diff":
                result["gemm1_vs_xpu_max_abs_diff"],
                "gemm2_vs_xpu_max_abs_diff":
                result["gemm2_vs_xpu_max_abs_diff"],
                "staged_vs_xpu_fused_moe_max_abs_diff":
                result["staged_vs_xpu_fused_moe_max_abs_diff"],
                "onednn_island_vs_xpu_fused_moe_max_abs_diff":
                result["onednn_island_vs_xpu_fused_moe_max_abs_diff"],
                "onednn_island_vs_staged_max_abs_diff":
                result["onednn_island_vs_staged_max_abs_diff"],
                "ref_output_checksum_f32": result["ref_output_checksum_f32"],
                "onednn_output_checksum_f32":
                result["onednn_output_checksum_f32"],
                "gemm1_onednn_mean_us":
                result["gemm1_onednn"].get("mean_us"),
                "gemm1_onednn_p50_us":
                result["gemm1_onednn"].get("p50_us"),
                "gemm2_onednn_mean_us":
                result["gemm2_onednn"].get("mean_us"),
                "gemm2_onednn_p50_us":
                result["gemm2_onednn"].get("p50_us"),
            }
            for index, result in enumerate(window_results)
        ],
    }
    (out_dir / "multi_window_onednn_moe_island_result.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> int:
    args = parse_args()
    bench = load_bench_module(args.bench_script)
    ensure_xpu_ops_available()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.compile_only:
        env = os.environ.copy()
        env["CASE_BIN"] = args.case_bin
        subprocess.run(["bash", args.runner, "--compile-only"], check=True, env=env)
        return 0

    text_config = bench.load_text_config(bench.DEFAULT_MODEL_CONFIG)
    route_rows, route_meta = bench.load_route_topk_rows(
        args.route_jsonl,
        layer_regex=args.route_layer_regex,
        stage_regex=args.route_stage_regex,
        min_num_tokens=1,
        max_num_tokens=1,
    )
    route_start_indices = args.route_start_indices or [args.route_start_index]
    if args.route_start_indices is None:
        replay_window(
            args=args,
            bench=bench,
            text_config=text_config,
            route_rows=route_rows,
            route_meta=route_meta,
            out_dir=out_dir,
            route_start_index=route_start_indices[0],
            compile_first_case=True,
            weight_source_dir=None,
        )
        return 0

    window_results = []
    weight_source_dir = None
    for index, route_start_index in enumerate(route_start_indices):
        window_dir = out_dir / f"window_{index:03d}_start_{route_start_index}"
        result = replay_window(
            args=args,
            bench=bench,
            text_config=text_config,
            route_rows=route_rows,
            route_meta=route_meta,
            out_dir=window_dir,
            route_start_index=route_start_index,
            compile_first_case=(index == 0),
            weight_source_dir=weight_source_dir,
        )
        window_results.append(result)
        if weight_source_dir is None:
            weight_source_dir = window_dir

    summarize_multi_window(
        args=args,
        route_meta=route_meta,
        window_results=window_results,
        out_dir=out_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
