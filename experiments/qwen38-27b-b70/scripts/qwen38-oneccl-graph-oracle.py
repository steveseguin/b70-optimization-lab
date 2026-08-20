#!/usr/bin/env python3
"""Two-rank graph-replay correctness oracle for the rebuilt oneCCL,
mirroring repro/qwen38-27b-autoround-int4-b70/evidence/oneccl-*-graph-20260818.json:
- BF16 allreduce [4,5120], 512 graph replays per rank
- BF16 blocking allgather [4,2560], 512 graph replays per rank
Inputs mutated and outputs poisoned on every replay; each replay compared
against a fresh eager collective on identical inputs. Any mismatch or
nonzero diff fails. Used here to validate reduced CCL_* buffer sizing.
"""
import json
import os
import sys

import torch
import torch.distributed as dist


def oracle(name, shape, fn_eager, fn_capture, gen_fn, rank, replays=512):
    """Phase 1: eager reference pass (all collectives done before capture).
    Phase 2: capture, then replays-only — mixing eager collectives with
    graph replays on one communicator deadlocks (replays are pre-baked,
    eager ops re-negotiate)."""
    if rank == 0:
        print(f"[oracle] {name}: eager reference pass", flush=True)
    refs = [fn_eager(gen_fn(10 + i).clone()).clone() for i in range(replays)]
    torch.xpu.synchronize()
    dist.barrier()
    if rank == 0:
        print(f"[oracle] {name}: capture", flush=True)
    g = torch.xpu.XPUGraph()
    buf_in = gen_fn(1)
    with torch.xpu.graph(g):
        out = fn_capture(buf_in)
    torch.xpu.synchronize()
    if rank == 0:
        print(f"[oracle] {name}: replays", flush=True)
    max_abs = 0.0
    mismatches = 0
    for i in range(replays):
        buf_in.copy_(gen_fn(10 + i))
        out.fill_(float("nan"))
        torch.xpu.synchronize()
        g.replay()
        torch.xpu.synchronize()
        ref = refs[i]
        if torch.isnan(out.float()).any():
            mismatches += 1
            continue
        d = float((out.float() - ref.float()).abs().max())
        max_abs = max(max_abs, d)
        if d > 0:
            mismatches += 1
    return {"op": name, "replays": replays, "mismatches": mismatches,
            "max_abs_diff": max_abs}


def main():
    dist.init_process_group("xccl")
    rank = dist.get_rank()
    torch.xpu.set_device(rank)
    dev = torch.device(f"xpu:{rank}")

    def gen_allreduce(seed):
        g = torch.Generator(device="cpu").manual_seed(seed * 131 + rank)
        return (torch.randn(4, 5120, generator=g, dtype=torch.float32)
                .to(torch.bfloat16).to(dev))

    def gen_allgather(seed):
        g = torch.Generator(device="cpu").manual_seed(seed * 131 + rank)
        return (torch.randn(4, 2560, generator=g, dtype=torch.float32)
                .to(torch.bfloat16).to(dev))

    def eager_allreduce(x):
        dist.all_reduce(x)
        return x

    def eager_allgather(x):
        out = torch.empty(2, 4, 2560, dtype=torch.bfloat16, device=dev)
        dist.all_gather_into_tensor(out.view(-1), x.view(-1))
        return out

    def cap_allreduce(x):
        o = x.clone()
        dist.all_reduce(o)
        return o

    gather_hold = {}

    def cap_allgather(x):
        o = torch.empty(2, 4, 2560, dtype=torch.bfloat16, device=dev)
        gather_hold["buf"] = o
        dist.all_gather_into_tensor(o.view(-1), x.view(-1))
        return o

    ops = os.environ.get("ORACLE_OPS", "allreduce,allgather")
    results = []
    if "allreduce" in ops:
        results.append(oracle("allreduce_bf16_4x5120", (4, 5120),
                              eager_allreduce, cap_allreduce,
                              gen_allreduce, rank))
    if "allgather" in ops:
        results.append(oracle("allgather_bf16_4x2560", (4, 2560),
                              eager_allgather, cap_allgather,
                              gen_allgather, rank))
    if rank == 0:
        out = {"passed": all(r["mismatches"] == 0 for r in results),
               "results": results,
               "ccl_env": {k: os.environ.get(k) for k in (
                   "CCL_SYCL_TMP_BUF_SIZE",
                   "CCL_SYCL_SCALEOUT_HOST_BUF_SIZE",
                   "CCL_SYCL_SCALEOUT_DEVICE_BUF_SIZE")}}
        print(json.dumps(out))
        out_path = sys.argv[1]
        with open(out_path, "w") as f:
            json.dump(out, f, indent=1)
    dist.barrier()
    dist.destroy_process_group()


if __name__ == "__main__":
    main()
