#!/usr/bin/env python3
"""How long does one two-card all-gather take at the 27B decode shapes? (no server; notes/2026-10-17-fp8-step-floor.md)

Run under torch.distributed.run with two processes (one per card) and the server's oneCCL environment. For each fp16
shape [rows, cols] the gathered result is [2 * rows, cols], as b70-allgather-allreduce issues it:
  alone      device time per all_gather_into_tensor in batches of back-to-back calls (rank 0; no synchronisation
             inside a batch, so the ranks stay in lockstep as in a server step)
  added      a [rows, 5120] x [5120, 5120] fp16 matmul (about 50 MB of weight, like a decode linear) is issued before
             each gather; median time of matmul + gather minus median time of the matmul alone, i.e. what one
             exchange adds to a step in which the cards otherwise compute
Bytes are compared after the run (rank 0's half equals rank 1's input on both ranks): a transport check, not a timing.
"""
import argparse
import json
import os
import statistics

import torch
import torch.distributed as dist

ap = argparse.ArgumentParser()
ap.add_argument('--shapes', default='1x5120,6x5120,1x124160,6x124160')
ap.add_argument('--iters', type=int, default=400)
ap.add_argument('--out', required=True)
a = ap.parse_args()
rank, world = int(os.environ['RANK']), int(os.environ['WORLD_SIZE'])
torch.xpu.set_device(rank)
dev = torch.device('xpu', rank)
dist.init_process_group('xccl', rank=rank, world_size=world, device_id=dev)
torch.manual_seed(1234 + rank)
w = torch.randn(5120, 5120, device=dev, dtype=torch.float16) * 0.02


def timed(fn, n, batches=7):
    """Per-call device time from batches of n back-to-back calls (no synchronisation inside a batch, so the two
    ranks stay in lockstep through the collectives, as in a server step); median over the batches."""
    out = []
    for _ in range(20):
        fn()
    torch.xpu.synchronize()
    for _ in range(batches):
        dist.barrier()
        s, e = torch.xpu.Event(enable_timing=True), torch.xpu.Event(enable_timing=True)
        s.record()
        for _ in range(n):
            fn()
        e.record()
        e.synchronize()
        out.append(s.elapsed_time(e) * 1e3 / n)
    return statistics.median(out)


report = {'schema': 'b70-xccl-allgather-latency.v1', 'world': world, 'torch': torch.__version__, 'shapes': []}
for item in a.shapes.split(','):
    rows, cols = (int(x) for x in item.split('x'))
    x = torch.randn(rows, cols, device=dev, dtype=torch.float16)
    g = torch.empty((world * rows, cols), device=dev, dtype=torch.float16)
    h = torch.randn(rows, 5120, device=dev, dtype=torch.float16)

    def gather():
        dist.all_gather_into_tensor(g, x)

    def mm():
        return h @ w

    def mm_gather():
        mm()
        dist.all_gather_into_tensor(g, x)

    alone = timed(gather, a.iters)
    only_mm = timed(mm, a.iters)
    both = timed(mm_gather, a.iters)
    dist.barrier()
    dist.all_gather_into_tensor(g, x)
    torch.xpu.synchronize()
    mine = torch.equal(g[rank * rows:(rank + 1) * rows], x)
    flag = torch.tensor([1 if mine else 0], device=dev, dtype=torch.int32)
    dist.all_reduce(flag)
    row = {'rows': rows, 'cols': cols, 'bytes_per_rank': rows * cols * 2, 'alone_us': round(alone, 1),
           'matmul_us': round(only_mm, 1), 'matmul_plus_gather_us': round(both, 1),
           'added_us': round(both - only_mm, 1), 'bytes_ok_all_ranks': int(flag.item()) == world}
    report['shapes'].append(row)
    if rank == 0:
        print(json.dumps(row), flush=True)
if rank == 0:
    open(a.out, 'w').write(json.dumps(report, indent=1) + '\n')
dist.destroy_process_group()
