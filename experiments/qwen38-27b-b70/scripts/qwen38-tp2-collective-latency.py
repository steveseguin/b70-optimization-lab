#!/usr/bin/env python3
"""TP2 collective latency at the Qwen3.8 MTP5 record shapes.

Prices the per-step collective share of the 35.3 ms engine step:
- 128 layer allreduces  [6,5120] fp16 (o_proj + down_proj per layer, x64)
- 10 draft allreduces   [1,5120] fp16 (draft layer, x5 draft forwards)
- 1  target logits allgather [6, 75968] fp16
- 5  draft logits allgather  [1, 75968] fp16

Run: torchrun --nproc_per_node=2 qwen38-tp2-collective-latency.py [out.json]
Requires the rebuilt oneCCL on LD_LIBRARY_PATH. GPU-only; safe under a
systemd user scope on the 15 GiB host.
"""
import json
import os
import sys
import time
from pathlib import Path

import torch
import torch.distributed as dist

WARMUP = 50
ITERS = 500
BURST = 100
BURSTS = 10


def bench_eager(t):
    for _ in range(WARMUP):
        dist.all_reduce(t)
    torch.xpu.synchronize()
    ts = []
    for _ in range(ITERS):
        t0 = time.perf_counter_ns()
        dist.all_reduce(t)
        torch.xpu.synchronize()
        ts.append(time.perf_counter_ns() - t0)
    ts.sort()
    n = len(ts)
    bursts = []
    for _ in range(BURSTS):
        t0 = time.perf_counter_ns()
        for _ in range(BURST):
            dist.all_reduce(t)
        torch.xpu.synchronize()
        bursts.append((time.perf_counter_ns() - t0) / BURST / 1e3)
    bursts.sort()
    return {"median_us": ts[n // 2] / 1e3, "p10_us": ts[n // 10] / 1e3,
            "p90_us": ts[9 * n // 10] / 1e3,
            "burst_median_us": bursts[len(bursts) // 2]}


def bench_graph(t, n_ops=10):
    s = torch.xpu.Stream()
    with torch.xpu.stream(s):
        for _ in range(3):
            dist.all_reduce(t)
    torch.xpu.current_stream().wait_stream(s)
    g = torch.xpu.XPUGraph()
    with torch.xpu.graph(g):
        for _ in range(n_ops):
            dist.all_reduce(t)
    for _ in range(WARMUP):
        g.replay()
    torch.xpu.synchronize()
    bursts = []
    for _ in range(BURSTS):
        t0 = time.perf_counter_ns()
        for _ in range(BURST):
            g.replay()
        torch.xpu.synchronize()
        bursts.append((time.perf_counter_ns() - t0) / BURST / n_ops / 1e3)
    bursts.sort()
    return {"graph_burst_us_per_op": bursts[len(bursts) // 2]}


def bench_allgather(t, out):
    for _ in range(WARMUP):
        dist.all_gather_into_tensor(out, t)
    torch.xpu.synchronize()
    ts = []
    for _ in range(ITERS):
        t0 = time.perf_counter_ns()
        dist.all_gather_into_tensor(out, t)
        torch.xpu.synchronize()
        ts.append(time.perf_counter_ns() - t0)
    ts.sort()
    n = len(ts)
    return {"median_us": ts[n // 2] / 1e3, "p10_us": ts[n // 10] / 1e3,
            "p90_us": ts[9 * n // 10] / 1e3}


def main():
    rank = int(os.environ["LOCAL_RANK"])
    torch.xpu.set_device(rank)
    dist.init_process_group("xccl")
    dev = f"xpu:{rank}"
    results = {}
    if rank == 0:
        results["device"] = torch.xpu.get_device_name(0)

    for name, rows in (("allreduce_layer_m6", 6), ("allreduce_draft_m1", 1)):
        t = torch.randn(rows, 5120, dtype=torch.float16, device=dev)
        r = bench_eager(t)
        r.update(bench_graph(t))
        results[name] = r
        if rank == 0:
            print(f"{name}: {r}")

    for name, rows in (("logits_allgather_m6", 6), ("logits_allgather_m1", 1)):
        t = torch.randn(rows, 75968, dtype=torch.float16, device=dev)
        out = torch.empty(rows, 75968 * 2, dtype=torch.float16, device=dev)
        r = bench_allgather(t, out)
        results[name] = r
        if rank == 0:
            print(f"{name}: {r}")

    ar = results["allreduce_layer_m6"]["burst_median_us"]
    step_us = 128 * ar + 10 * results["allreduce_draft_m1"]["burst_median_us"] \
        + results["logits_allgather_m6"]["median_us"] \
        + 5 * results["logits_allgather_m1"]["median_us"]
    results["step_collectives_ms"] = step_us / 1e3
    results["note"] = ("128 layer AR + 10 draft AR + 1 target logits AG + "
                       "5 draft logits AG per MTP5 step")
    if rank == 0:
        print(f"step_collectives_ms: {step_us/1e3:.3f}")
        if len(sys.argv) > 1:
            Path(sys.argv[1]).write_text(json.dumps(results, indent=1) + "\n")
            print(f"wrote {sys.argv[1]}")
    dist.barrier()
    dist.destroy_process_group()


if __name__ == "__main__":
    main()
