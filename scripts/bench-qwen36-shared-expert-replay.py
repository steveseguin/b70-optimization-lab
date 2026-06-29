#!/usr/bin/env python3
"""Replay and time the Qwen3.6 shared-expert INT8 path on XPU.

This is an offline harness for the live endpoint bottleneck labelled
``moe_forward_shared`` / ``qwen2_moe.shared.*``.  It uses the TP-local shapes
from the Quark W8A8 INT8 model and compares exact-preserving variants before
they are wired into the endpoint.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Callable

import torch

# Registers torch.ops._xpu_C INT8 GEMM and quantization operators.
import vllm_xpu_kernels.fused_moe_interface  # noqa: F401


DEFAULT_CONFIG = (
    "/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/"
    "snapshots/cced56592e8c8935f8220836b4baa04dfd389118/config.json"
)


def parse_rows(value: str) -> list[int]:
    rows: list[int] = []
    for item in value.split(","):
        item = item.strip()
        if item:
            rows.append(int(item))
    if not rows:
        raise argparse.ArgumentTypeError("at least one row count is required")
    return rows


def load_text_config(path: str) -> dict:
    data = json.loads(Path(path).read_text())
    text_config = data.get("text_config")
    if not isinstance(text_config, dict):
        raise ValueError(f"Missing text_config in {path}")
    return text_config


def elapsed_us(start: torch.xpu.Event, end: torch.xpu.Event) -> float:
    return float(start.elapsed_time(end) * 1000.0)


def bench(fn: Callable[[], torch.Tensor | tuple[torch.Tensor, ...]],
          *,
          warmup: int,
          iters: int) -> dict[str, float]:
    for _ in range(warmup):
        fn()
    torch.xpu.synchronize()

    times: list[float] = []
    for _ in range(iters):
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        fn()
        end.record()
        torch.xpu.synchronize()
        times.append(elapsed_us(start, end))
    return {
        "mean_us": statistics.fmean(times),
        "median_us": statistics.median(times),
        "min_us": min(times),
        "max_us": max(times),
    }


def compare(a: torch.Tensor, b: torch.Tensor) -> dict[str, float | bool]:
    diff = (a.float() - b.float()).abs()
    max_abs = float(diff.max().cpu().item())
    return {
        "exact": bool(torch.equal(a, b)),
        "max_abs_diff": max_abs,
        "mean_abs_diff": float(diff.mean().cpu().item()),
    }


class SharedExpertCase:
    def __init__(
        self,
        *,
        rows: int,
        hidden: int,
        inter_local: int,
        dtype: torch.dtype,
        device: torch.device,
    ) -> None:
        self.rows = rows
        self.hidden = hidden
        self.inter_local = inter_local
        self.dtype = dtype
        self.device = device

        self.x = torch.randn((rows, hidden), device=device, dtype=dtype)
        self.gate_up_w = torch.randint(
            -127,
            127,
            (hidden, 2 * inter_local),
            device=device,
            dtype=torch.int8,
        )
        self.gate_up_w_scale = torch.rand(
            (2 * inter_local, ), device=device, dtype=torch.float32)
        self.down_w = torch.randint(
            -127,
            127,
            (inter_local, hidden),
            device=device,
            dtype=torch.int8,
        )
        self.down_w_scale = torch.rand(
            (hidden, ), device=device, dtype=torch.float32)
        self.expert_gate_w = torch.randn(
            (hidden, 1), device=device, dtype=dtype)

        self.act = torch.empty(
            (rows, inter_local), device=device, dtype=dtype)
        self.act_q = torch.empty(
            (rows, inter_local), device=device, dtype=torch.int8)
        self.act_scale = torch.empty(
            (rows, 1), device=device, dtype=torch.float32)
        self.hidden_q = torch.empty(
            (rows, hidden), device=device, dtype=torch.int8)
        self.hidden_scale = torch.empty(
            (rows, 1), device=device, dtype=torch.float32)
        self.gate_up_out = torch.empty(
            (rows, 2 * inter_local), device=device, dtype=dtype)
        self.down_out = torch.empty(
            (rows, hidden), device=device, dtype=dtype)
        self.cpp_out = torch.empty(
            (rows, hidden), device=device, dtype=dtype)

    def quant_x(self) -> tuple[torch.Tensor, torch.Tensor]:
        return torch.ops._xpu_C.per_token_quant_int8_xpu(self.x)

    def gate_up(self) -> torch.Tensor:
        x_q, x_scale = self.quant_x()
        return torch.ops._xpu_C.int8_gemm_w8a8(
            x_q,
            x_scale,
            self.gate_up_w,
            self.gate_up_w_scale,
            self.dtype,
            None,
        )

    def separate_act_quant_down(self,
                                gate_up: torch.Tensor) -> torch.Tensor:
        torch.ops._C.silu_and_mul(self.act, gate_up)
        act_q, act_scale = torch.ops._xpu_C.per_token_quant_int8_xpu(
            self.act)
        return torch.ops._xpu_C.int8_gemm_w8a8(
            act_q,
            act_scale,
            self.down_w,
            self.down_w_scale,
            self.dtype,
            None,
        )

    def fused_alloc_act_quant_down(self,
                                   gate_up: torch.Tensor) -> torch.Tensor:
        act_q, act_scale = torch.ops._xpu_C.silu_and_mul_quant_int8_xpu(
            gate_up)
        return torch.ops._xpu_C.int8_gemm_w8a8(
            act_q,
            act_scale,
            self.down_w,
            self.down_w_scale,
            self.dtype,
            None,
        )

    def fused_out_act_quant_down(self,
                                 gate_up: torch.Tensor) -> torch.Tensor:
        act_q, act_scale = torch.ops._xpu_C.silu_and_mul_quant_int8_xpu_out(
            gate_up, self.act_q, self.act_scale)
        return torch.ops._xpu_C.int8_gemm_w8a8(
            act_q,
            act_scale,
            self.down_w,
            self.down_w_scale,
            self.dtype,
            None,
        )

    def gate_mul(self, down: torch.Tensor) -> torch.Tensor:
        gate = self.x.matmul(self.expert_gate_w)
        return torch.sigmoid(gate) * down

    def baseline(self) -> torch.Tensor:
        gate_up = self.gate_up()
        down = self.separate_act_quant_down(gate_up)
        return self.gate_mul(down)

    def fused_alloc(self) -> torch.Tensor:
        gate_up = self.gate_up()
        down = self.fused_alloc_act_quant_down(gate_up)
        return self.gate_mul(down)

    def fused_out(self) -> torch.Tensor:
        gate_up = self.gate_up()
        down = self.fused_out_act_quant_down(gate_up)
        return self.gate_mul(down)

    def cpp_boundary_out(self) -> torch.Tensor:
        return torch.ops._xpu_C.qwen36_shared_expert_w8a8_out(
            self.x,
            self.hidden_q,
            self.hidden_scale,
            self.gate_up_w,
            self.gate_up_w_scale,
            self.gate_up_out,
            self.act_q,
            self.act_scale,
            self.down_w,
            self.down_w_scale,
            self.down_out,
            self.expert_gate_w,
            self.cpp_out,
        )

    def stage_functions(self) -> dict[str, Callable[[], torch.Tensor]]:
        gate_up_cache = self.gate_up()
        down_cache = self.fused_out_act_quant_down(gate_up_cache)
        torch.xpu.synchronize()
        return {
            "quant_x_plus_gate_up_int8_gemm": self.gate_up,
            "separate_silu_mul_quant_down_int8_gemm":
            lambda: self.separate_act_quant_down(gate_up_cache),
            "fused_alloc_silu_quant_down_int8_gemm":
            lambda: self.fused_alloc_act_quant_down(gate_up_cache),
            "fused_out_silu_quant_down_int8_gemm":
            lambda: self.fused_out_act_quant_down(gate_up_cache),
            "expert_gate_sigmoid_mul":
            lambda: self.gate_mul(down_cache),
        }


def run_case(args: argparse.Namespace, rows: int) -> dict:
    cfg = load_text_config(args.config)
    hidden = int(args.hidden_size or cfg["hidden_size"])
    inter_global = int(args.shared_intermediate_size
                       or cfg["shared_expert_intermediate_size"])
    if inter_global % args.tp_size != 0:
        raise ValueError(
            f"shared intermediate {inter_global} is not divisible by TP {args.tp_size}"
        )
    inter_local = inter_global // args.tp_size
    dtype = getattr(torch, args.dtype)
    device = torch.device("xpu")

    case = SharedExpertCase(
        rows=rows,
        hidden=hidden,
        inter_local=inter_local,
        dtype=dtype,
        device=device,
    )

    baseline_out = case.baseline()
    fused_alloc_out = case.fused_alloc()
    fused_out_out = case.fused_out()
    cpp_boundary_out = case.cpp_boundary_out()
    torch.xpu.synchronize()

    result = {
        "rows": rows,
        "hidden": hidden,
        "shared_intermediate_global": inter_global,
        "shared_intermediate_local": inter_local,
        "tp_size": args.tp_size,
        "dtype": args.dtype,
        "parity": {
            "fused_alloc_vs_baseline": compare(fused_alloc_out, baseline_out),
            "fused_out_vs_baseline": compare(fused_out_out, baseline_out),
            "cpp_boundary_out_vs_baseline": compare(
                cpp_boundary_out, baseline_out),
        },
        "whole_path": {
            "baseline": bench(
                case.baseline, warmup=args.warmup, iters=args.iters),
            "fused_alloc": bench(
                case.fused_alloc, warmup=args.warmup, iters=args.iters),
            "fused_out": bench(
                case.fused_out, warmup=args.warmup, iters=args.iters),
            "cpp_boundary_out": bench(
                case.cpp_boundary_out, warmup=args.warmup, iters=args.iters),
        },
        "stages": {},
    }
    for name, fn in case.stage_functions().items():
        result["stages"][name] = bench(
            fn, warmup=args.warmup, iters=args.iters)
    return result


def write_markdown(path: Path, payload: dict) -> None:
    lines = [
        "# Qwen3.6 Shared-Expert Replay",
        "",
        f"- Device selector: `{payload['device_selector']}`",
        f"- Config: `{payload['config']}`",
        f"- TP size: `{payload['tp_size']}`",
        f"- Iterations: `{payload['iters']}` warmup `{payload['warmup']}`",
        "",
        "| rows | baseline us | fused alloc us | fused out us | C++ boundary us | C++ diff |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for case in payload["cases"]:
        whole = case["whole_path"]
        diff = case["parity"]["cpp_boundary_out_vs_baseline"]["max_abs_diff"]
        lines.append(
            f"| {case['rows']} | "
            f"{whole['baseline']['mean_us']:.3f} | "
            f"{whole['fused_alloc']['mean_us']:.3f} | "
            f"{whole['fused_out']['mean_us']:.3f} | "
            f"{whole['cpp_boundary_out']['mean_us']:.3f} | "
            f"{diff:.6g} |")
    lines.extend(["", "## Stage Means", ""])
    for case in payload["cases"]:
        lines.append(f"### rows={case['rows']}")
        lines.append("")
        lines.append("| stage | mean us | min us | max us |")
        lines.append("|---|---:|---:|---:|")
        for name, stats in case["stages"].items():
            lines.append(
                f"| `{name}` | {stats['mean_us']:.3f} | "
                f"{stats['min_us']:.3f} | {stats['max_us']:.3f} |")
        lines.append("")
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--rows", type=parse_rows, default=parse_rows("1,2,4,8,16,32"))
    parser.add_argument("--tp-size", type=int, default=2)
    parser.add_argument("--hidden-size", type=int, default=None)
    parser.add_argument("--shared-intermediate-size", type=int, default=None)
    parser.add_argument("--dtype", choices=["bfloat16", "float16"], default="bfloat16")
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--iters", type=int, default=100)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, default=None)
    args = parser.parse_args()

    torch.xpu.set_device(0)
    payload = {
        "kind": "qwen36_shared_expert_replay",
        "config": args.config,
        "device_selector": torch.xpu.get_device_name(0),
        "tp_size": args.tp_size,
        "dtype": args.dtype,
        "warmup": args.warmup,
        "iters": args.iters,
        "cases": [run_case(args, rows) for rows in args.rows],
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, sort_keys=True))
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        write_markdown(args.markdown_out, payload)
    print(f"wrote={args.output_json}")
    if args.markdown_out:
        print(f"wrote={args.markdown_out}")


if __name__ == "__main__":
    main()
