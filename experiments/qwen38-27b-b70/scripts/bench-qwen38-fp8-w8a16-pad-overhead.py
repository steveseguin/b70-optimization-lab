#!/usr/bin/env python3
"""Micro-benchmark: where does the R118 padded-GEMM cost come from?

Operator diagnostic only, one GPU, random data. For each production W8A16 shape
at M in {2, 4} it times: the plain kernel at M; the plain kernel at M=32; the
R118 op as written (new_zeros + copy + kernel + slice); and a preallocated-buffer
variant (copy into a persistent zeroed 32-row buffer + kernel + slice). Times are
per call in microseconds after warmup, median of repeats.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import torch

GEMMS = {
    "gdn_in_proj_qkvz": (5120, 8192),
    "gdn_out_proj": (3072, 5120),
    "attn_qkv_proj": (5120, 7168),
    "attn_o_proj": (3072, 5120),
    "mlp_gate_up_proj": (5120, 17408),
    "mlp_down_proj": (8704, 5120),
}
BLOCK = 128


def gemm(a, w_fp8, scales_t):
    return torch.ops._xpu_C.fp8_gemm_w8a16(a, w_fp8.t(), scales_t, None)


def timed(fn, iters=50, reps=5):
    for _ in range(5):
        fn()
    torch.xpu.synchronize()
    samples = []
    for _ in range(reps):
        t0 = time.perf_counter()
        for _ in range(iters):
            fn()
        torch.xpu.synchronize()
        samples.append((time.perf_counter() - t0) / iters * 1e6)
    return statistics.median(samples)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pad", type=int, default=32)
    args = parser.parse_args()
    import vllm  # noqa: F401
    import vllm._xpu_ops  # noqa: F401

    device = torch.device("xpu:0")
    gen = torch.Generator(device="cpu").manual_seed(1)
    report = {"schema": "neural.download.qwen38-fp8-w8a16-pad-overhead.v1", "pad": args.pad, "shapes": {}}
    for name, (k, n) in GEMMS.items():
        w = (torch.randn((n, k), generator=gen, device="cpu") * 0.05).to(torch.float8_e4m3fn).to(device)
        s = (torch.rand((k // BLOCK, n // BLOCK), generator=gen, device="cpu") * 0.02 + 0.005).to(torch.float32).to(device).contiguous()
        buf = torch.zeros((args.pad, k), dtype=torch.float16, device=device)
        entry = {}
        for m in (2, 4):
            a = torch.randn((m, k), generator=gen, device="cpu").to(torch.float16).to(device)
            a32 = torch.randn((args.pad, k), generator=gen, device="cpu").to(torch.float16).to(device)

            def plain():
                return gemm(a, w, s)

            def plain32():
                return gemm(a32, w, s)

            def r118_as_written():
                padded = a.new_zeros((args.pad, k))
                padded[:m] = a
                return gemm(padded, w, s)[:m]

            def prealloc():
                buf[:m].copy_(a)
                return gemm(buf, w, s)[:m]

            entry[f"M{m}"] = {
                "plain_us": round(timed(plain), 1),
                "plain_M32_us": round(timed(plain32), 1),
                "r118_as_written_us": round(timed(r118_as_written), 1),
                "prealloc_copy_us": round(timed(prealloc), 1),
            }
        report["shapes"][name] = entry
        print(name, json.dumps(entry), flush=True)
        del w, s, buf
        torch.xpu.synchronize()
        torch.xpu.empty_cache()
    args.out.write_text(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
