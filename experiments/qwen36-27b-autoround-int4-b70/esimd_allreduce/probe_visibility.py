#!/usr/bin/env python3
import os

import torch
import torch.distributed as dist

import qwen27_esimd_allreduce as ext


def signed_ptr(ptr: int) -> int:
    return ptr - (1 << 64) if ptr >= (1 << 63) else ptr


def main() -> None:
    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world = int(os.environ["WORLD_SIZE"])
    if world != 2:
        raise RuntimeError("visibility probe requires exactly two ranks")
    torch.xpu.set_device(local_rank)
    dist.init_process_group("xccl")

    local = torch.zeros((1,), device="xpu", dtype=torch.int32)
    observed = torch.zeros_like(local)
    handles = [None] * world
    dist.all_gather_object(handles, ext.get_ipc_handle(local))
    peer_ptr = ext.open_ipc_handle(handles[rank ^ 1], local_rank)
    peer_arg = signed_ptr(peer_ptr)

    def read(label: str, expected: int) -> None:
        ext.read_peer_i32(peer_arg, observed)
        torch.xpu.synchronize()
        value = int(observed.cpu().item())
        print(
            f"rank={rank} phase={label} observed={value} expected={expected}",
            flush=True,
        )
        if value != expected:
            raise AssertionError(f"{label}: observed {value}, expected {expected}")

    local.fill_(100 + rank)
    torch.xpu.synchronize()
    dist.barrier()
    read("torch-store", 100 + (rank ^ 1))
    dist.barrier()

    for mode, name in ((0, "clean"), (1, "evict"), (2, "none")):
        ext.write_local_i32(local, 200 + mode * 10 + rank, mode)
        torch.xpu.synchronize()
        dist.barrier()
        read(f"esimd-{name}", 200 + mode * 10 + (rank ^ 1))
        dist.barrier()

    if rank == 0:
        print("PASS peer visibility", flush=True)
    ext.close_ipc_handle(peer_ptr, local_rank)
    dist.destroy_process_group()


if __name__ == "__main__":
    main()
