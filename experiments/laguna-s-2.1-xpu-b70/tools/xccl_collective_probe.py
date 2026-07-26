"""Minimal 4-rank XCCL all_reduce probe.

Reproduces exactly the collective vLLM hangs on in xpu_worker.init_device,
with nothing else in the process.  Prints a line per stage so a hang is
attributable to a specific step rather than to "startup".
"""

import datetime
import os
import sys
import time

import torch
import torch.distributed as dist


def stage(rank: str, name: str) -> None:
    print(f"[rank {rank}] {name} t={time.monotonic():.2f}", flush=True)


def main() -> int:
    rank = os.environ["RANK"]
    world = int(os.environ["WORLD_SIZE"])
    stage(rank, "import-done")



    device = torch.device(f"xpu:{rank}")
    torch.xpu.set_device(device)
    stage(rank, f"device-set {torch.xpu.get_device_name(int(rank))}")

    dist.init_process_group(
        backend="xccl",
        rank=int(rank),
        world_size=world,
        timeout=datetime.timedelta(seconds=90),
    )
    stage(rank, "pg-initialised")

    t = torch.ones(8, device=device, dtype=torch.float32) * (int(rank) + 1)
    stage(rank, "tensor-allocated")

    dist.all_reduce(t)
    torch.xpu.synchronize()
    stage(rank, f"all_reduce-done sum={t[0].item()}")

    expected = world * (world + 1) / 2
    ok = abs(t[0].item() - expected) < 1e-6
    stage(rank, f"verify {'OK' if ok else 'MISMATCH'} expected={expected}")

    dist.barrier()
    dist.destroy_process_group()
    stage(rank, "teardown-done")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
