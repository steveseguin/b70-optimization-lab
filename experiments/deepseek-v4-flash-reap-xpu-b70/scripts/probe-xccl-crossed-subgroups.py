#!/usr/bin/env python3
"""Probe XCCL crossed DP pairs with and without vLLM subgroup creation order."""

from __future__ import annotations

import argparse
import os

import torch
import torch.distributed as dist


def create_family(groups: list[list[int]], name: str):
    rank = dist.get_rank()
    selected = None
    for index, ranks in enumerate(groups):
        device_group = dist.new_group(ranks, backend="xccl", group_desc=f"{name}-{index}")
        dist.new_group(ranks, backend="gloo", group_desc=f"{name}-cpu-{index}")
        if rank in ranks:
            selected = device_group
    assert selected is not None
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("direct", "vllm-order"), required=True)
    args = parser.parse_args()

    local_rank = int(os.environ["LOCAL_RANK"])
    rank = int(os.environ["RANK"])
    torch.xpu.set_device(local_rank)
    dist.init_process_group("xccl")

    if args.mode == "vllm-order":
        create_family([[0, 1], [2, 3]], "tp")
        create_family([[0], [1], [2], [3]], "dcp")
        create_family([[0], [1], [2], [3]], "pcp")
        create_family([[0], [1], [2], [3]], "pp")
    dp_group = create_family([[0, 2], [1, 3]], "dp")
    if args.mode == "vllm-order":
        create_family([[0, 1, 2, 3]], "ep")

    dist.barrier()
    value = torch.tensor([rank + 1.0], device=f"xpu:{local_rank}")
    dist.all_reduce(value, group=dp_group)
    torch.xpu.synchronize()
    expected = 4.0 if rank in (0, 2) else 6.0
    actual = float(value.cpu()[0])
    if actual != expected:
        raise AssertionError(f"rank={rank} actual={actual} expected={expected}")
    print(f"rank={rank} mode={args.mode} crossed_dp_allreduce={actual}", flush=True)
    dist.destroy_process_group()


if __name__ == "__main__":
    main()
