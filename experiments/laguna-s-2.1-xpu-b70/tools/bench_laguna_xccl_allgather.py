"""Measure XCCL allgather latency at the size a Laguna decode step uses.

The kernel trace shows ~122 us per allgatherv for ~73 KiB at M=12, i.e. about
0.6 GB/s -- a latency signature. This isolates that number from vLLM so the
floor can be found in minutes instead of 20-minute model-load runs.

Run: torchrun --nproc-per-node 4 ccl_allgather_bench.py
"""

import os
import time

import torch
import torch.distributed as dist

# oneCCL binding lives behind this import on some builds.
try:
    import oneccl_bindings_for_pytorch  # noqa: F401
except Exception:
    pass


def main() -> None:
    rank = int(os.environ.get("RANK", "0"))
    world = int(os.environ.get("WORLD_SIZE", "1"))
    local = int(os.environ.get("LOCAL_RANK", str(rank)))

    torch.xpu.set_device(local)
    dist.init_process_group(backend="xccl", rank=rank, world_size=world)

    if rank == 0:
        print(f"world={world} backend=xccl device=xpu:{local}", flush=True)

    # 12 rows x 3072 hidden x 2 bytes = 73,728 B, the decode-step payload,
    # plus neighbours to show whether cost tracks size (bandwidth) or not
    # (latency).
    for rows in (1, 12, 48, 192, 768):
        numel = rows * 3072
        src = torch.ones(numel, dtype=torch.bfloat16, device=f"xpu:{local}")
        dst = torch.empty(numel * world, dtype=torch.bfloat16, device=f"xpu:{local}")

        for _ in range(20):  # warmup
            dist.all_gather_into_tensor(dst, src)
        torch.xpu.synchronize()
        dist.barrier()

        iters = 200
        t0 = time.perf_counter()
        for _ in range(iters):
            dist.all_gather_into_tensor(dst, src)
        torch.xpu.synchronize()
        elapsed = time.perf_counter() - t0

        if rank == 0:
            per_call_us = elapsed / iters * 1e6
            payload = numel * 2
            gbps = payload / (elapsed / iters) / 1e9
            print(
                f"rows={rows:4d}  payload={payload / 1024:8.1f} KiB  "
                f"{per_call_us:8.1f} us/call  {gbps:6.2f} GB/s",
                flush=True,
            )

    dist.destroy_process_group()


if __name__ == "__main__":
    main()
