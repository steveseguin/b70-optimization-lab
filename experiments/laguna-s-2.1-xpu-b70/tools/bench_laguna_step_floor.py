"""Minimal TP4 decode-step floor: is the fixed ~27-34 ms inherent or vLLM-side?

A Laguna decode step at M=12 costs 27-34 ms while device kernel time is ~2.2 ms.
Eight causes are excluded by measurement (bandwidth, compute, PCIe, collective
transport, collective volume, draft depth, clocks, explicit synchronisation).

This reproduces only the *shape* of a step -- 48 layers, each a few small
M=12 GEMMs plus the two collectives a layer performs -- on four ranks with no
model, no vLLM and no scheduler. It answers one question:

  ~2 ms   -> the floor is cheap; the fixed cost lives in the serving path
  ~27 ms  -> the floor is inherent to this topology at this layer count

Run: torchrun --nproc-per-node 4 bench_laguna_step_floor.py
"""

import os
import time

import torch
import torch.distributed as dist

try:  # oneCCL binding lives behind this import on some builds
    import oneccl_bindings_for_pytorch  # noqa: F401
except Exception:
    pass

LAYERS = 48
M = 12          # verifier width
HIDDEN = 3072
INTER = 1024    # EP4 shard of the expert intermediate size
TOPK = 10


def main() -> None:
    rank = int(os.environ.get("RANK", "0"))
    world = int(os.environ.get("WORLD_SIZE", "1"))
    local = int(os.environ.get("LOCAL_RANK", str(rank)))
    torch.xpu.set_device(local)
    dist.init_process_group(backend="xccl", rank=rank, world_size=world)
    dev = f"xpu:{local}"
    bf16 = torch.bfloat16

    x = torch.randn(M, HIDDEN, dtype=bf16, device=dev)
    qkv = torch.randn(HIDDEN, HIDDEN, dtype=bf16, device=dev)
    w13 = torch.randn(HIDDEN, 2 * INTER, dtype=bf16, device=dev)
    w2 = torch.randn(INTER, HIDDEN, dtype=bf16, device=dev)
    disp = torch.randn(M * TOPK, HIDDEN, dtype=bf16, device=dev)
    gathered = torch.empty(M * TOPK * world, HIDDEN, dtype=bf16, device=dev)
    reduced = torch.empty_like(x)

    def step() -> None:
        h = x
        for _ in range(LAYERS):
            h = (h @ qkv)                       # attention projection
            a = h @ w13                         # expert gate/up
            a = torch.nn.functional.silu(a[:, :INTER]) * a[:, INTER:]
            h = a @ w2                          # expert down
            dist.all_gather_into_tensor(gathered, disp)   # MoE dispatch
            dist.all_reduce(reduced)                      # TP reduce

    for _ in range(5):
        step()
    torch.xpu.synchronize()
    dist.barrier()

    iters = 20
    t0 = time.perf_counter()
    for _ in range(iters):
        step()
    torch.xpu.synchronize()
    dt = (time.perf_counter() - t0) / iters

    if rank == 0:
        print(f"  layers={LAYERS} M={M} hidden={HIDDEN} world={world}")
        print(f"  step floor        = {dt * 1e3:8.2f} ms")
        print(f"  per layer         = {dt * 1e6 / LAYERS:8.1f} us")
        print("  measured Laguna step = 27-34 ms, device kernel time ~2.2 ms")

    # Same shape with the collectives removed, to price them inside this floor.
    def step_nocoll() -> None:
        h = x
        for _ in range(LAYERS):
            h = h @ qkv
            a = h @ w13
            a = torch.nn.functional.silu(a[:, :INTER]) * a[:, INTER:]
            h = a @ w2

    for _ in range(5):
        step_nocoll()
    torch.xpu.synchronize()
    dist.barrier()
    t0 = time.perf_counter()
    for _ in range(iters):
        step_nocoll()
    torch.xpu.synchronize()
    dt2 = (time.perf_counter() - t0) / iters
    if rank == 0:
        print(f"  step floor, no collectives = {dt2 * 1e3:8.2f} ms")
        print(f"  collectives cost           = {(dt - dt2) * 1e3:8.2f} ms")


    # Variant: add the per-step host-to-device copies the serving path performs.
    # The warm trace shows ~75 aten::copy_ per decode step (input ids, positions,
    # slot mapping, block tables), and sampling puts 27.6% of decode wall clock
    # inside copy_to_gpu. Each enqueues in 2-3 us standalone; the question is
    # what they cost when the queue already holds a step's work.
    COPIES = 75
    hostbufs = [
        torch.zeros(4096, dtype=torch.int32, pin_memory=True) for _ in range(8)
    ]
    devbufs = [torch.zeros(4096, dtype=torch.int32, device=dev) for _ in range(8)]

    def step_copies() -> None:
        h = x
        for i in range(LAYERS):
            h = h @ qkv
            a = h @ w13
            a = torch.nn.functional.silu(a[:, :INTER]) * a[:, INTER:]
            h = a @ w2
            dist.all_gather_into_tensor(gathered, disp)
            dist.all_reduce(reduced)
        for j in range(COPIES):
            devbufs[j % 8].copy_(hostbufs[j % 8], non_blocking=True)

    for _ in range(5):
        step_copies()
    torch.xpu.synchronize()
    dist.barrier()
    t0 = time.perf_counter()
    for _ in range(iters):
        step_copies()
    torch.xpu.synchronize()
    dt3 = (time.perf_counter() - t0) / iters
    if rank == 0:
        print(f"  step floor + {COPIES} H2D copies = {dt3 * 1e3:8.2f} ms")
        print(f"  copies cost                  = {(dt3 - dt) * 1e3:8.2f} ms")

    dist.destroy_process_group()


if __name__ == "__main__":
    main()
