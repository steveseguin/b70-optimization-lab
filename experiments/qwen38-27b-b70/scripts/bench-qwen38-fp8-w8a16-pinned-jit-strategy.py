#!/usr/bin/env python3
"""Screen oneDNN JIT GEMM strategy pinning for row-invariant W8A16."""

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
DEFAULT_MS = [1, 2, 4, 8, 16, 32, 64, 128, 168, 200, 224, 250, 256, 300, 512]
TIMED_MS = [1, 4, 32, 168, 256]


def gemm(a, weight, scale):
    return torch.ops._xpu_C.fp8_gemm_w8a16(a, weight, scale, None)


def digest(tensor: torch.Tensor) -> str:
    return hashlib.sha256(
        tensor.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
    ).hexdigest()


def max_abs(a, b) -> float:
    return float((a.float() - b.float()).abs().max().item())


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
    parser.add_argument("--shape", choices=sorted(SHAPES), required=True)
    parser.add_argument("--ms", default=",".join(map(str, DEFAULT_MS)))
    parser.add_argument("--seed", type=int, default=20260902)
    parser.add_argument("--warmups", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--skip-timing", action="store_true")
    args = parser.parse_args()

    import vllm_xpu_kernels._xpu_C  # noqa: F401

    if not torch.xpu.is_available():
        raise SystemExit("XPU is required")
    ms = [int(value) for value in args.ms.split(",")]
    if not ms or min(ms) < 1 or len(ms) != len(set(ms)):
        raise SystemExit("--ms must contain distinct positive integers")
    k, n = SHAPES[args.shape]
    device = torch.device("xpu:0")
    gen = torch.Generator(device="cpu").manual_seed(args.seed)

    weight_nk = (torch.randn((n, k), generator=gen) * 0.05).to(
        torch.float8_e4m3fn
    ).to(device)
    weight = weight_nk.t()
    scale = (
        torch.rand((k // 128, n // 128), generator=gen) * 0.02 + 0.005
    ).to(torch.float32).to(device).contiguous()
    a_full = torch.randn((max(max(ms), 512), k), generator=gen).to(
        torch.float16
    ).to(device)

    report = {
        "schema": "neural.download.qwen38-fp8-w8a16-pinned-jit-strategy.v1",
        "classification": "operator-diagnostic-only",
        "environment": {
            "device": torch.xpu.get_device_name(0),
            "torch": torch.__version__,
            "seed": args.seed,
            "gemm_kernel_override": os.environ.get("GEMM_KERNEL"),
        },
        "shape": args.shape,
        "K": k,
        "N": n,
        "ms": ms,
    }

    outputs = {}
    for m in ms:
        print(f"R123_MARKER before shape={args.shape} M={m}", flush=True)
        outputs[m] = gemm(a_full[:m], weight, scale)
        torch.xpu.synchronize()
        print(f"R123_MARKER after shape={args.shape} M={m}", flush=True)

    row0_classes = {}
    for m, output in outputs.items():
        row0_classes.setdefault(digest(output[:1]), []).append(m)
    largest_m = max(ms)
    exact_vs_largest_prefix = {
        str(m): bool(torch.equal(output, outputs[largest_m][:m]))
        for m, output in outputs.items()
    }
    max_abs_vs_largest_prefix = {
        str(m): max_abs(output, outputs[largest_m][:m])
        for m, output in outputs.items()
    }

    check_m = 200 if 200 in ms else largest_m
    perm_cpu = torch.randperm(check_m, generator=gen)
    perm = perm_cpu.to(device)
    permuted = gemm(a_full[:check_m][perm], weight, scale)
    unpermuted = permuted[torch.argsort(perm)]
    repeated = gemm(a_full[:check_m], weight, scale)
    padded_source = torch.zeros((200, k), dtype=torch.float16, device=device)
    padded_source[:168].copy_(a_full[:168])
    padded = gemm(padded_source, weight, scale)
    direct168 = gemm(a_full[:168], weight, scale)
    torch.xpu.synchronize()

    timings = {}
    if not args.skip_timing:
        for m in TIMED_MS:
            if m <= a_full.shape[0]:
                timings[str(m)] = time_us(
                    lambda m=m: gemm(a_full[:m], weight, scale),
                    args.warmups,
                    args.iterations,
                    args.repeats,
                )

    report.update(
        {
            "row0_classes_by_m": sorted(
                row0_classes.values(), key=lambda values: values[0]
            ),
            "row0_invariant": len(row0_classes) == 1,
            "exact_vs_largest_prefix_by_m": exact_vs_largest_prefix,
            "max_abs_vs_largest_prefix_by_m": max_abs_vs_largest_prefix,
            "permutation_m": check_m,
            "permutation_invariant": bool(
                torch.equal(unpermuted, outputs[check_m])
            ),
            "permutation_max_abs": max_abs(unpermuted, outputs[check_m]),
            "repeat_m": check_m,
            "repeat_deterministic": bool(
                torch.equal(repeated, outputs[check_m])
            ),
            "padding_168_to_200_exact": bool(
                torch.equal(padded[:168], direct168)
            ),
            "padding_168_to_200_max_abs": max_abs(padded[:168], direct168),
            "latency_us": timings,
        }
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1, sort_keys=True))
    print(json.dumps(report, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
