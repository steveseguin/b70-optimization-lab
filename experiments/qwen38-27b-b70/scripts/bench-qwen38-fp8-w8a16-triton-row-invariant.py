#!/usr/bin/env python3
"""Feasibility gate for a fixed-tile row-invariant block-FP8 W8A16 GEMM.

Operator diagnostic only. Each Triton program always computes a fixed 16-row
tile; M changes only the number of programs and the row mask. Weight scales are
one FP32 value per 128x128 [K, N] block, matching the Qwen3.8 checkpoint path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path

import torch
from vllm.triton_utils import tl, triton


SHAPES = {
    "attn_o_proj": (3072, 5120),
    "attn_qkv_proj": (5120, 7168),
}
M_VALUES = [1, 2, 4, 8, 16, 31, 32, 59, 64, 128, 256]
CONFIGS = [
    {"block_n": 64, "block_k": 32, "num_warps": 4},
    {"block_n": 128, "block_k": 32, "num_warps": 4},
    {"block_n": 128, "block_k": 64, "num_warps": 8},
]


@triton.jit
def _w8a16_block_fp8_kernel(
    a_ptr,
    weight_ptr,
    scale_ptr,
    out_ptr,
    m,
    n: tl.constexpr,
    k: tl.constexpr,
    stride_am: tl.constexpr,
    stride_ak: tl.constexpr,
    stride_wk: tl.constexpr,
    stride_wn: tl.constexpr,
    stride_sk: tl.constexpr,
    stride_sn: tl.constexpr,
    stride_om: tl.constexpr,
    stride_on: tl.constexpr,
    block_m: tl.constexpr,
    block_n: tl.constexpr,
    block_k: tl.constexpr,
):
    pid_m = tl.program_id(0)
    pid_n = tl.program_id(1)
    offs_m = pid_m * block_m + tl.arange(0, block_m)
    offs_n = pid_n * block_n + tl.arange(0, block_n)
    accumulator = tl.zeros((block_m, block_n), dtype=tl.float32)

    for scale_k in range(0, k, 128):
        block_accumulator = tl.zeros((block_m, block_n), dtype=tl.float32)
        for inner_k in range(0, 128, block_k):
            offs_k = scale_k + inner_k + tl.arange(0, block_k)
            a = tl.load(
                a_ptr + offs_m[:, None] * stride_am + offs_k[None, :] * stride_ak,
                mask=(offs_m[:, None] < m) & (offs_k[None, :] < k),
                other=0.0,
            ).to(tl.float16)
            weight = tl.load(
                weight_ptr
                + offs_k[:, None] * stride_wk
                + offs_n[None, :] * stride_wn,
                mask=(offs_k[:, None] < k) & (offs_n[None, :] < n),
                other=0.0,
            ).to(tl.float16)
            block_accumulator += tl.dot(a, weight, out_dtype=tl.float32)
        scale = tl.load(
            scale_ptr
            + (scale_k // 128) * stride_sk
            + ((pid_n * block_n) // 128) * stride_sn
        )
        accumulator += block_accumulator * scale

    tl.store(
        out_ptr + offs_m[:, None] * stride_om + offs_n[None, :] * stride_on,
        accumulator,
        mask=(offs_m[:, None] < m) & (offs_n[None, :] < n),
    )


def digest(tensor: torch.Tensor) -> str:
    return hashlib.sha256(
        tensor.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
    ).hexdigest()


def launch(a, weight, scale, config, out=None):
    m, k = a.shape
    n = weight.shape[1]
    if out is None:
        out = torch.empty((m, n), dtype=a.dtype, device=a.device)
    block_m = 16
    block_n = config["block_n"]
    _w8a16_block_fp8_kernel[(triton.cdiv(m, block_m), triton.cdiv(n, block_n))](
        a,
        weight,
        scale,
        out,
        m,
        n=n,
        k=k,
        stride_am=a.stride(0),
        stride_ak=a.stride(1),
        stride_wk=weight.stride(0),
        stride_wn=weight.stride(1),
        stride_sk=scale.stride(0),
        stride_sn=scale.stride(1),
        stride_om=out.stride(0),
        stride_on=out.stride(1),
        block_m=block_m,
        block_n=block_n,
        block_k=config["block_k"],
        num_warps=config["num_warps"],
    )
    return out


def one_dnn(a, weight, scale):
    return torch.ops._xpu_C.fp8_gemm_w8a16(a, weight, scale, None)


def time_us(fn, warmups, iterations, repeats):
    for _ in range(warmups):
        fn()
    torch.xpu.synchronize()
    values = []
    stream = torch.xpu.current_stream()
    for _ in range(repeats):
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record(stream)
        for _ in range(iterations):
            fn()
        end.record(stream)
        end.synchronize()
        values.append(start.elapsed_time(end) * 1000.0 / iterations)
    return {
        "median_us": statistics.median(values),
        "min_us": min(values),
        "max_us": max(values),
        "samples_us": values,
    }


def max_abs(a, b):
    return float((a.float() - b.float()).abs().max().item())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260902)
    parser.add_argument("--warmups", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()

    import vllm_xpu_kernels._xpu_C  # noqa: F401

    if not torch.xpu.is_available():
        raise SystemExit("XPU is required")
    device = torch.device("xpu:0")
    gen = torch.Generator(device="cpu").manual_seed(args.seed)
    report = {
        "schema": "neural.download.qwen38-fp8-w8a16-triton-row-invariant.v1",
        "classification": "operator-diagnostic-only",
        "environment": {
            "device": torch.xpu.get_device_name(0),
            "torch": torch.__version__,
            "triton": triton.__version__,
            "seed": args.seed,
        },
        "fixed_block_m": 16,
        "shapes": {},
    }

    for name, (k, n) in SHAPES.items():
        weight_nk = (
            torch.randn((n, k), generator=gen, device="cpu") * 0.05
        ).to(torch.float8_e4m3fn).to(device)
        weight = weight_nk.t()
        scale = (
            torch.rand((k // 128, n // 128), generator=gen, device="cpu")
            * 0.02
            + 0.005
        ).to(torch.float32).to(device).contiguous()
        a_full = torch.randn((max(M_VALUES), k), generator=gen, device="cpu").to(
            torch.float16
        ).to(device)
        shape_result = {"K": k, "N": n, "configs": []}

        for config in CONFIGS:
            item = dict(config)
            try:
                out_by_m = {
                    m: launch(a_full[:m].contiguous(), weight, scale, config)
                    for m in M_VALUES
                }
                torch.xpu.synchronize()
                row_classes = {}
                for m, out in out_by_m.items():
                    row_classes.setdefault(digest(out[:1]), []).append(m)
                m_perm = 31
                perm = torch.randperm(m_perm, generator=gen).to(device)
                natural = launch(
                    a_full[:m_perm].contiguous(), weight, scale, config
                )
                permuted = launch(
                    a_full[:m_perm][perm].contiguous(), weight, scale, config
                )
                repeated = launch(a_full[:59].contiguous(), weight, scale, config)
                repeated2 = launch(a_full[:59].contiguous(), weight, scale, config)
                reference = one_dnn(a_full[:16].contiguous(), weight, scale)
                candidate16 = out_by_m[16]
                timing = {}
                for m in (2, 16, 32):
                    a = a_full[:m].contiguous()
                    out = torch.empty((m, n), dtype=a.dtype, device=device)
                    timing[str(m)] = time_us(
                        lambda a=a, out=out: launch(
                            a, weight, scale, config, out=out
                        ),
                        args.warmups,
                        args.iterations,
                        args.repeats,
                    )
                a2 = a_full[:2].contiguous()
                one_dnn_timing = time_us(
                    lambda: one_dnn(a2, weight, scale),
                    args.warmups,
                    args.iterations,
                    args.repeats,
                )
                item.update(
                    {
                        "compiled": True,
                        "row0_invariance_classes_by_M": sorted(
                            row_classes.values(), key=lambda values: values[0]
                        ),
                        "row_invariant_across_all_M": len(row_classes) == 1,
                        "permutation_invariant_M31": bool(
                            torch.equal(permuted, natural[perm])
                        ),
                        "permutation_max_abs_M31": max_abs(
                            permuted, natural[perm]
                        ),
                        "repeat_deterministic_M59": bool(
                            torch.equal(repeated, repeated2)
                        ),
                        "max_abs_vs_static_oneDNN_M16": max_abs(
                            candidate16, reference
                        ),
                        "mean_abs_vs_static_oneDNN_M16": float(
                            (candidate16.float() - reference.float())
                            .abs()
                            .mean()
                            .item()
                        ),
                        "triton_latency_us": timing,
                        "static_oneDNN_M2_latency_us": one_dnn_timing,
                        "M2_latency_ratio": timing["2"]["median_us"]
                        / one_dnn_timing["median_us"],
                    }
                )
            except Exception as exc:  # noqa: BLE001
                item.update(
                    {
                        "compiled": False,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
            shape_result["configs"].append(item)
            print(f"[triton-row] {name} {config}: {item}", flush=True)
        report["shapes"][name] = shape_result
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=1, sort_keys=True))
        del weight_nk, weight, scale, a_full
        torch.xpu.synchronize()
        torch.xpu.empty_cache()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
