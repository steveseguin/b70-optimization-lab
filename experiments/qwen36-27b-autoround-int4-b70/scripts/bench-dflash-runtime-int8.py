#!/usr/bin/env python3
"""Benchmark real Qwen27 DFlash BF16 linears against XPU runtime W8A8.

This is a diagnostic microbenchmark, not a headline throughput result. It loads
the actual DFlash checkpoint weights, quantizes them per output channel, and
measures activation quantization plus GEMM at the row counts used by DDTree.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


DEFAULT_MODEL = Path(
    "/mnt/fast-ai/llm-cache/hf/manual/z-lab--Qwen3.6-27B-DFlash"
)


def parse_ints(value: str) -> list[int]:
    values = [int(item) for item in value.split(",") if item.strip()]
    if not values or any(item <= 0 for item in values):
        raise argparse.ArgumentTypeError("expected comma-separated positive integers")
    return values


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize(values: list[float]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "median_ms": statistics.median(values),
        "mean_ms": statistics.mean(values),
        "p10_ms": percentile(values, 0.10),
        "p90_ms": percentile(values, 0.90),
        "min_ms": min(values),
        "max_ms": max(values),
        "stdev_ms": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def bench(
    fn: Callable[[], Any], *, torch: Any, warmup: int, iterations: int
) -> dict[str, float | int]:
    for _ in range(warmup):
        fn()
    torch.xpu.synchronize()
    elapsed: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        torch.xpu.synchronize()
        elapsed.append((time.perf_counter() - start) * 1000.0)
    return summarize(elapsed)


def load_case_weight(model_file: Path, case: str, *, torch: Any) -> Any:
    from safetensors import safe_open

    with safe_open(model_file, framework="pt", device="cpu") as handle:
        if case == "fc":
            return handle.get_tensor("fc.weight")
        if case == "qkv":
            return torch.cat(
                [
                    handle.get_tensor("layers.0.self_attn.q_proj.weight"),
                    handle.get_tensor("layers.0.self_attn.k_proj.weight"),
                    handle.get_tensor("layers.0.self_attn.v_proj.weight"),
                ],
                dim=0,
            )
        if case == "o_proj":
            return handle.get_tensor("layers.0.self_attn.o_proj.weight")
        if case == "gate_up":
            return torch.cat(
                [
                    handle.get_tensor("layers.0.mlp.gate_proj.weight"),
                    handle.get_tensor("layers.0.mlp.up_proj.weight"),
                ],
                dim=0,
            )
        if case == "down":
            return handle.get_tensor("layers.0.mlp.down_proj.weight")
    raise ValueError(f"unknown case: {case}")


def quantize_weight(weight: Any, *, torch: Any) -> tuple[Any, Any]:
    weight_f = weight.float()
    scale = weight_f.abs().amax(dim=1).clamp_min(1.0e-10) / 127.0
    weight_q_t = (
        torch.round(weight_f / scale[:, None])
        .clamp(-127, 127)
        .to(torch.int8)
        .t()
        .contiguous()
    )
    return weight_q_t, scale.contiguous()


def accuracy(reference: Any, candidate: Any, *, torch: Any) -> dict[str, float]:
    ref = reference.float()
    got = candidate.float()
    error = got - ref
    denom = ref.square().mean().sqrt().clamp_min(1.0e-12)
    cosine = torch.nn.functional.cosine_similarity(ref, got, dim=-1).mean()
    top1 = (ref.argmax(dim=-1) == got.argmax(dim=-1)).float().mean()
    return {
        "max_abs": float(error.abs().max().item()),
        "mean_abs": float(error.abs().mean().item()),
        "relative_rmse": float((error.square().mean().sqrt() / denom).item()),
        "mean_row_cosine": float(cosine.item()),
        "row_argmax_agreement": float(top1.item()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case", required=True, choices=("fc", "qkv", "o_proj", "gate_up", "down")
    )
    parser.add_argument("--rows", type=parse_ints, default=parse_ints("4,8,16"))
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=80)
    parser.add_argument("--seed", type=int, default=20260711)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    import torch
    import vllm_xpu_kernels._xpu_C  # noqa: F401

    torch.xpu.set_device(0)
    model_file = args.model_dir / "model.safetensors"
    weight_cpu = load_case_weight(model_file, args.case, torch=torch)
    weight_q_t_cpu, scale_f32_cpu = quantize_weight(weight_cpu, torch=torch)
    weight = weight_cpu.to(device="xpu", dtype=torch.bfloat16).contiguous()
    weight_q_t = weight_q_t_cpu.to(device="xpu").contiguous()
    scale_f32 = scale_f32_cpu.to(device="xpu").contiguous()
    scale_bf16 = scale_f32.to(torch.bfloat16).contiguous()
    del weight_cpu, weight_q_t_cpu, scale_f32_cpu

    report: dict[str, Any] = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": (
            "Diagnostic real-weight DFlash BF16-vs-runtime-W8A8 microbenchmark; "
            "not endpoint or headline throughput."
        ),
        "case": args.case,
        "weight_shape_out_in": list(weight.shape),
        "rows": args.rows,
        "warmup": args.warmup,
        "iterations": args.iterations,
        "model_file": str(model_file),
        "torch": torch.__version__,
        "env": {
            "ZE_AFFINITY_MASK": os.environ.get("ZE_AFFINITY_MASK"),
            "ONEAPI_DEVICE_SELECTOR": os.environ.get("ONEAPI_DEVICE_SELECTOR"),
        },
        "results": [],
    }

    for rows in args.rows:
        generator = torch.Generator(device="xpu")
        generator.manual_seed(args.seed + rows)
        x = torch.randn(
            (rows, weight.shape[1]),
            device="xpu",
            dtype=torch.bfloat16,
            generator=generator,
        ).contiguous()

        def bf16_linear():
            return torch.nn.functional.linear(x, weight)

        def w8a8_f32scale():
            x_q, x_scale = torch.ops._xpu_C.per_token_quant_int8_xpu(x)
            return torch.ops._xpu_C.int8_gemm_w8a8(
                x_q, x_scale, weight_q_t, scale_f32, torch.bfloat16, None
            )

        def w8a8_bf16scale():
            x_q, x_scale = torch.ops._xpu_C.per_token_quant_int8_xpu(x)
            return torch.ops._xpu_C.int8_gemm_w8a8(
                x_q, x_scale, weight_q_t, scale_bf16, torch.bfloat16, None
            )

        reference = bf16_linear()
        candidate_f32 = w8a8_f32scale()
        candidate_bf16 = w8a8_bf16scale()
        torch.xpu.synchronize()
        row_result = {
            "rows": rows,
            "bf16_linear": bench(
                bf16_linear,
                torch=torch,
                warmup=args.warmup,
                iterations=args.iterations,
            ),
            "w8a8_f32scale_quant_plus_gemm": bench(
                w8a8_f32scale,
                torch=torch,
                warmup=args.warmup,
                iterations=args.iterations,
            ),
            "w8a8_bf16scale_quant_plus_gemm": bench(
                w8a8_bf16scale,
                torch=torch,
                warmup=args.warmup,
                iterations=args.iterations,
            ),
            "accuracy_f32scale": accuracy(reference, candidate_f32, torch=torch),
            "accuracy_bf16scale": accuracy(reference, candidate_bf16, torch=torch),
        }
        for name in (
            "w8a8_f32scale_quant_plus_gemm",
            "w8a8_bf16scale_quant_plus_gemm",
        ):
            row_result[name]["speedup_vs_bf16"] = (
                row_result["bf16_linear"]["median_ms"]
                / row_result[name]["median_ms"]
            )
        report["results"].append(row_result)
        print(json.dumps(row_result, indent=2))

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
