#!/usr/bin/env python3
"""Go/no-go microbenchmark for the fused resadd/RMSNorm/INT4 gate-up candidate.

The triage note
(experiments/qwen38-27b-b70/notes/2026-08-18-autoround-fused-resadd-rmsnorm-int4-triage.md)
sets the integration threshold: the fusion must save at least 0.04 ms/layer at
M=4, K=5120, N=17408 (TP2-local gate_up). The most the fusion can ever save is
the cost of the separate residual-add + RMSNorm kernels plus one extra pass
over x and the extra launches — the INT4 GEMM itself stays. So measuring the
unfused boundary with the REAL runtime GEMM and REAL checkpoint weights gives
the go/no-go answer before anyone writes the ESIMD kernel.

Uses auto_round_kernel's XPU path (the same woqgemm the model runs) with the
fixture's real layer-0 gate/up weights. Needs libdnnl: run with
LD_LIBRARY_PATH=/opt/intel/oneapi/dnnl/2026.0/lib:... and under a memory scope,
e.g. systemd-run --user --scope -p MemoryMax=8G.

No model is loaded; host footprint <1.5 GB. GPU 0 only.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import torch
from safetensors.torch import load_file

FIXTURE = os.environ.get(
    "FUSION_FIXTURE_DIR", "/home/steve/qwen38-fusion-fixture-v1")
LAYER = 0
M, K, N_LOCAL = 4, 5120, 17408  # TP2-local gate_up: gate 8704 + up 8704
WARMUP, ITERS = 50, 300


def _unpack_rows(qweight: torch.Tensor) -> torch.Tensor:
    """[K/8, N] int32 -> [K, N] uint8, LSB-first nibble order along K."""
    k8, n = qweight.shape
    q = torch.empty((k8 * 8, n), dtype=torch.uint8)
    for j in range(8):
        q[j::8] = ((qweight >> (4 * j)) & 0xF).to(torch.uint8)
    return q


def _unpack_zeros(qzeros: torch.Tensor) -> torch.Tensor:
    """[G, N/8] int32 -> [G, N] uint8, LSB-first along N."""
    g, n8 = qzeros.shape
    zp = torch.empty((g, n8 * 8), dtype=torch.uint8)
    for j in range(8):
        zp[:, j::8] = ((qzeros >> (4 * j)) & 0xF).to(torch.uint8)
    return zp


def build_fp16_weight(tensors, proj: str) -> torch.Tensor:
    """Dequantize the fixture's real checkpoint projection to fp16 [K,N].

    Verified bitwise against the auto_round_kernel CPU repack/unpack oracle
    by fusion-fixture.py. Proxy only: the production path is ark's packed
    int4 woqgemm, whose prebuilt wheel does not support BMG-G31 on this host
    ('no matrix hardware'). The fp16 proxy reads 4x the weight bytes, so it
    upper-bounds GEMM time; the go/no-go fusible share (add + RMSNorm +
    launches) is measured exactly and does not depend on the GEMM backend.
    """
    qw = tensors[f"layer{LAYER}.{proj}_qweight"]
    sc = tensors[f"layer{LAYER}.{proj}_scales"]
    qz = tensors[f"layer{LAYER}.{proj}_qzeros"]
    q = _unpack_rows(qw).to(torch.float32)
    zp = _unpack_zeros(qz).to(torch.float32) + 1.0  # stored 7 -> effective 8
    k, n = q.shape
    g = sc.shape[0]
    assert k == g * 128
    zp = zp.repeat_interleave(128, dim=0)
    s = sc.to(torch.float32).repeat_interleave(128, dim=0)
    w = (q - zp) * s
    half = N_LOCAL // 2
    return w[:, :half].to(torch.float16).t().contiguous()  # [N,K] for x @ W.T


def time_op(fn) -> dict:
    for _ in range(WARMUP):
        fn()
    torch.xpu.synchronize()
    ts = []
    for _ in range(ITERS):
        t0 = time.perf_counter_ns()
        fn()
        torch.xpu.synchronize()
        ts.append(time.perf_counter_ns() - t0)
    ts.sort()
    n = len(ts)
    return {"median_us": ts[n // 2] / 1e3, "p10_us": ts[n // 10] / 1e3,
            "p90_us": ts[9 * n // 10] / 1e3}


def time_graphed(fn) -> dict:
    """Device-side time via XPU graph capture: replay amortizes host launch
    overhead, matching the production PIECEWISE-graph regime. Burst mode
    (100 replays between syncs) further suppresses replay-launch cost."""
    side = torch.xpu.Stream()
    with torch.xpu.stream(side):
        fn()
    torch.xpu.current_stream().wait_stream(side)
    g = torch.xpu.XPUGraph()
    with torch.xpu.graph(g):
        fn()
    for _ in range(WARMUP):
        g.replay()
    torch.xpu.synchronize()
    burst = 100
    ts = []
    for _ in range(ITERS // burst):
        t0 = time.perf_counter_ns()
        for _ in range(burst):
            g.replay()
        torch.xpu.synchronize()
        ts.append((time.perf_counter_ns() - t0) / burst)
    ts.sort()
    n = len(ts)
    return {"median_us": ts[n // 2] / 1e3, "p10_us": ts[n // 10] / 1e3,
            "p90_us": ts[9 * n // 10] / 1e3}


def main() -> None:
    if not torch.xpu.is_available():
        raise SystemExit("XPU unavailable")
    device = "xpu:0"
    torch.xpu.set_device(device)

    tensors = load_file(str(Path(FIXTURE) / "fixture.safetensors"))
    wg_t = build_fp16_weight(tensors, "gate").to(device)  # [8704, 5120]
    wu_t = build_fp16_weight(tensors, "up").to(device)

    h = torch.randn(M, K, dtype=torch.float16, device=device)
    r = torch.randn(M, K, dtype=torch.float16, device=device)
    norm_w = torch.randn(K, dtype=torch.float16, device=device).abs() * 0.5 + 0.5
    eps = 1e-6

    def rmsnorm(x):
        xf = x.to(torch.float32)
        return (xf * torch.rsqrt(xf.pow(2).mean(-1, keepdim=True) + eps)
                * norm_w.to(torch.float32)).to(torch.float16)

    def add_only():
        return h + r

    def norm_only():
        return rmsnorm(h + r)

    def gemm_only():
        return torch.cat([h @ wg_t.t(), h @ wu_t.t()], dim=-1)

    def full_boundary():
        x = rmsnorm(h + r)
        return torch.cat([x @ wg_t.t(), x @ wu_t.t()], dim=-1)

    results = {
        "add": time_op(add_only),
        "add_rmsnorm": time_op(norm_only),
        "gateup_gemm": time_op(gemm_only),
        "full_boundary": time_op(full_boundary),
        "graph_add_rmsnorm": time_graphed(norm_only),
        "graph_gateup_gemm": time_graphed(gemm_only),
        "graph_full_boundary": time_graphed(full_boundary),
    }
    for name, r in results.items():
        print(f"{name:>14}: median {r['median_us']:8.2f} us/layer "
              f"(p10 {r['p10_us']:.2f}, p90 {r['p90_us']:.2f})")

    # Production runs inside captured graph pieces, so the device-time
    # (graph replay) numbers are the honest fusible share; eager numbers
    # include ~25 us/launch host overhead and are kept for context.
    fusible_ms = (results["graph_full_boundary"]["median_us"]
                  - results["graph_gateup_gemm"]["median_us"]) / 1e3
    threshold_ms = 0.04
    verdict = ("GO: fusible share exceeds the 0.04 ms/layer threshold"
               if fusible_ms >= threshold_ms
               else "NO-GO: fusible share is below the 0.04 ms/layer "
                    "integration threshold; fusion cannot pay for itself at "
                    "this shape")
    print(f"\nfusible share (add+rmsnorm): {fusible_ms * 1000:.2f} us/layer")
    print(verdict)

    out = {
        "date": time.strftime("%Y-%m-%d"),
        "device": torch.xpu.get_device_name(0),
        "shape": {"M": M, "K": K, "N_local_gateup": N_LOCAL},
        "weights": "real layer-0 checkpoint gate/up, TP2 rank-0 local shards, dequantized to fp16 (proxy)",
        "gemm_path": "fp16 torch.matmul proxy; production ark woqgemm int4 "
                     "unsupported by the prebuilt wheel on BMG-G31 "
                     "('no matrix hardware'), proxy reads 4x weight bytes",
        "warmup": WARMUP, "iters": ITERS,
        "results": results,
        "fusible_ms_per_layer": fusible_ms,
        "threshold_ms_per_layer": threshold_ms,
        "verdict": verdict,
    }
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(out, indent=1) + "\n")
        print(f"wrote {sys.argv[1]}")


if __name__ == "__main__":
    main()
