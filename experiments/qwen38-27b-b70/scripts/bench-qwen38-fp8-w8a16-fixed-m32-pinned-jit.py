#!/usr/bin/env python3
"""Screen fixed-M32 oneDNN batches under the exact R123 JIT strategy."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
from pathlib import Path

import torch


SHAPES = {
    "attn_o_proj": (3072, 5120),
    "attn_qkv_proj": (5120, 7168),
}
MS = [1, 2, 4, 8, 16, 32, 64, 128, 168, 200, 224, 250, 256, 300, 512]
TIMED_MS = [1, 4, 32, 168, 256]
TILE_M = 32


def gemm(a, weight, scale):
    return torch.ops._xpu_C.fp8_gemm_w8a16(a, weight, scale, None)


def digest(tensor: torch.Tensor) -> str:
    return hashlib.sha256(
        tensor.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
    ).hexdigest()


def max_abs(a, b) -> float:
    return float((a.float() - b.float()).abs().max().item())


def padded_input(a_full, m, k, *, random_pad=False, gen=None):
    batch = (m + TILE_M - 1) // TILE_M
    rows = batch * TILE_M
    if random_pad:
        value = torch.randn((rows, k), generator=gen).to(torch.float16).to(a_full.device)
    else:
        value = torch.zeros((rows, k), dtype=torch.float16, device=a_full.device)
    value[:m].copy_(a_full[:m])
    return value.reshape(batch, TILE_M, k)


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
        "schema": "neural.download.qwen38-fp8-w8a16-fixed-m32-pinned-jit.v1",
        "classification": "operator-diagnostic-only",
        "tile_m": TILE_M,
        "ms": MS,
        "environment": {
            "device": torch.xpu.get_device_name(0),
            "torch": torch.__version__,
            "seed": args.seed,
            "gemm_kernel_override": os.environ.get("GEMM_KERNEL"),
        },
        "shapes": {},
    }

    for name, (k, n) in SHAPES.items():
        weight_nk = (torch.randn((n, k), generator=gen) * 0.05).to(
            torch.float8_e4m3fn
        ).to(device)
        weight = weight_nk.t()
        scale = (
            torch.rand((k // 128, n // 128), generator=gen) * 0.02 + 0.005
        ).to(torch.float32).to(device).contiguous()
        a_full = torch.randn((max(MS), k), generator=gen).to(torch.float16).to(device)

        inputs = {m: padded_input(a_full, m, k) for m in MS}
        outputs = {m: gemm(inputs[m], weight, scale).reshape(-1, n)[:m] for m in MS}
        torch.xpu.synchronize()
        row0_classes = {}
        for m, output in outputs.items():
            row0_classes.setdefault(digest(output[:1]), []).append(m)
        largest_m = max(MS)
        prefix_exact = {
            str(m): bool(torch.equal(output, outputs[largest_m][:m]))
            for m, output in outputs.items()
        }
        prefix_max_abs = {
            str(m): max_abs(output, outputs[largest_m][:m])
            for m, output in outputs.items()
        }

        sequential512 = torch.cat(
            [gemm(a_full[i : i + TILE_M], weight, scale) for i in range(0, 512, TILE_M)],
            dim=0,
        )
        perm_cpu = torch.randperm(200, generator=gen)
        perm = perm_cpu.to(device)
        perm_source = torch.zeros((224, k), dtype=torch.float16, device=device)
        perm_source[:200].copy_(a_full[:200][perm])
        permuted = gemm(perm_source.reshape(7, TILE_M, k), weight, scale).reshape(-1, n)[:200]
        unpermuted = permuted[torch.argsort(perm)]
        repeated = gemm(inputs[200], weight, scale).reshape(-1, n)[:200]
        random_padded = padded_input(a_full, 168, k, random_pad=True, gen=gen)
        random_pad_output = gemm(random_padded, weight, scale).reshape(-1, n)[:168]
        torch.xpu.synchronize()

        timings = {}
        for m in TIMED_MS:
            timings[str(m)] = {
                "fixed_m32_batch": time_us(
                    lambda m=m: gemm(inputs[m], weight, scale),
                    args.warmups,
                    args.iterations,
                    args.repeats,
                ),
                "flattened": time_us(
                    lambda m=m: gemm(a_full[:m], weight, scale),
                    args.warmups,
                    args.iterations,
                    args.repeats,
                ),
            }

        report["shapes"][name] = {
            "K": k,
            "N": n,
            "row0_classes_by_m": sorted(row0_classes.values(), key=lambda x: x[0]),
            "row0_invariant": len(row0_classes) == 1,
            "exact_vs_m512_prefix_by_m": prefix_exact,
            "max_abs_vs_m512_prefix_by_m": prefix_max_abs,
            "exact_vs_sequential_m32_m512": bool(torch.equal(outputs[512], sequential512)),
            "max_abs_vs_sequential_m32_m512": max_abs(outputs[512], sequential512),
            "permutation_m200_exact": bool(torch.equal(unpermuted, outputs[200])),
            "permutation_m200_max_abs": max_abs(unpermuted, outputs[200]),
            "repeat_m200_exact": bool(torch.equal(repeated, outputs[200])),
            "random_pad_content_m168_exact": bool(torch.equal(random_pad_output, outputs[168])),
            "random_pad_content_m168_max_abs": max_abs(random_pad_output, outputs[168]),
            "latency_us": timings,
        }
        print(f"[fixed-m32] {name}: {report['shapes'][name]}", flush=True)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=1, sort_keys=True))
        del weight_nk, weight, scale, a_full, inputs, outputs
        torch.xpu.synchronize()
        torch.xpu.empty_cache()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
