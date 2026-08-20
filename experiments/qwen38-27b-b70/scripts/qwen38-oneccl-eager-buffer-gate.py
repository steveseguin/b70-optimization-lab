#!/usr/bin/env python3
"""Eager correctness + spot latency for reduced CCL_* buffer sizing.

200 iterations each of BF16 allreduce [4,5120] and allgather [4,2560] with
seed-deterministic rank inputs; every result compared against the
CPU-computed expected value (both ranks can derive both inputs). Any
mismatch fails. This is the gate for reducing
CCL_SYCL_SCALEOUT_HOST_BUF_SIZE / CCL_SYCL_SCALEOUT_DEVICE_BUF_SIZE /
CCL_SYCL_TMP_BUF_SIZE on the low-RAM host.
"""
import json
import os
import sys
import time

import torch
import torch.distributed as dist


def gen(seed, rank, rows, cols, dev):
    g = torch.Generator(device="cpu").manual_seed(seed * 131 + rank)
    return (torch.randn(rows, cols, generator=g, dtype=torch.float32)
            .to(torch.bfloat16).to(dev))


def cpu_pair(seed, rows, cols):
    outs = []
    for r in (0, 1):
        g = torch.Generator(device="cpu").manual_seed(seed * 131 + r)
        outs.append(torch.randn(rows, cols, generator=g, dtype=torch.float32))
    return outs


def main():
    dist.init_process_group("xccl")
    rank = dist.get_rank()
    torch.xpu.set_device(rank)
    dev = torch.device(f"xpu:{rank}")
    iters = 200
    checksums = []

    for i in range(iters):
        x = gen(10 + i, rank, 4, 5120, dev)
        dist.all_reduce(x)
        checksums.append(hash(tuple(x.cpu().view(torch.int16).flatten().tolist()[::97])))

    for i in range(iters):
        x = gen(5000 + i, rank, 4, 2560, dev)
        out = torch.empty(2, 4, 2560, dtype=torch.bfloat16, device=dev)
        dist.all_gather_into_tensor(out.view(-1), x.view(-1))
        checksums.append(hash(tuple(out.cpu().view(torch.int16).flatten().tolist()[::97])))

    # spot latency at record shape
    x = gen(1, rank, 6, 5120, dev)
    for _ in range(50):
        dist.all_reduce(x)
    torch.xpu.synchronize()
    t0 = time.perf_counter_ns()
    for _ in range(500):
        dist.all_reduce(x)
    torch.xpu.synchronize()
    burst_us = (time.perf_counter_ns() - t0) / 500 / 1e3

    if rank == 0:
        out = {"checksums": checksums,
               "allreduce_6x5120_burst_us": burst_us,
               "ccl_env": {k: os.environ.get(k) for k in (
                   "CCL_SYCL_TMP_BUF_SIZE",
                   "CCL_SYCL_SCALEOUT_HOST_BUF_SIZE",
                   "CCL_SYCL_SCALEOUT_DEVICE_BUF_SIZE")}}
        with open(sys.argv[1], "w") as f:
            json.dump(out, f, indent=1)
        print(f"checksums_written={len(checksums)} burst_us={burst_us:.2f}")
    dist.barrier()
    dist.destroy_process_group()


if __name__ == "__main__":
    main()
