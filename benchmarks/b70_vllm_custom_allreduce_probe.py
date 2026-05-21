#!/usr/bin/env python3
"""Probe vLLM's Python custom-op all-reduce path on XPU/XCCL.

This is a small reproduction harness for failures seen when enabling
``VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES=1`` in the full MiniMax M2.7 stack.  It
registers a minimal vLLM-style group object, then compares direct XCCL
all-reduce with ``torch.ops.vllm.all_reduce`` in eager and optional
``torch.compile`` modes.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from dataclasses import dataclass

import torch
import torch.distributed as dist

from vllm.distributed import parallel_state as ps


@dataclass(frozen=True)
class Case:
    name: str
    dtype_name: str
    shape: tuple[int, ...]


class ProbeGroup:
    def __init__(self, name: str, device_group: dist.ProcessGroup) -> None:
        self.unique_name = name
        self.device_group = device_group

    def _all_reduce_out_place(self, input_: torch.Tensor) -> torch.Tensor:
        out = input_.clone()
        dist.all_reduce(out, group=self.device_group)
        return out


def dtype_from_name(name: str) -> torch.dtype:
    if name == "fp16":
        return torch.float16
    if name == "fp32":
        return torch.float32
    raise ValueError(f"unsupported dtype: {name}")


def default_cases() -> list[Case]:
    return [
        Case("qk_decode_fp32", "fp32", (1, 2)),
        Case("qk_two_fp32", "fp32", (2, 2)),
        Case("hidden_decode_fp16", "fp16", (1, 3072)),
        Case("hidden_two_fp16", "fp16", (2, 3072)),
    ]


def make_input(case: Case, rank: int, device: str) -> torch.Tensor:
    dtype = dtype_from_name(case.dtype_name)
    x = torch.arange(1, 1 + int(torch.tensor(case.shape).prod().item()),
                     dtype=dtype, device=device).reshape(case.shape)
    return x + rank


def analytical_ref(case: Case, world_size: int, device: str) -> torch.Tensor:
    dtype = dtype_from_name(case.dtype_name)
    base = torch.arange(1, 1 + int(torch.tensor(case.shape).prod().item()),
                        dtype=dtype, device=device).reshape(case.shape)
    rank_sum = world_size * (world_size - 1) // 2
    return base * world_size + rank_sum


def direct_ref(x: torch.Tensor, sync: bool = True) -> torch.Tensor:
    out = x.clone()
    dist.all_reduce(out)
    if sync:
        torch.xpu.synchronize()
        dist.barrier()
    return out


def custom_op(x: torch.Tensor, group_name: str) -> torch.Tensor:
    return torch.ops.vllm.all_reduce(x, group_name=group_name)


def check_path(
    name: str,
    fn,
    x: torch.Tensor,
    ref_cpu: torch.Tensor,
    iters: int,
) -> dict[str, object]:
    try:
        x_probe = x.clone()
        torch.xpu.synchronize()
        dist.barrier()
        y = fn(x_probe)
        torch.xpu.synchronize()
        dist.barrier()
        input_mutated = not bool(torch.equal(x_probe, x))
        y_cpu = y.detach().cpu()
        max_abs = float((y_cpu - ref_cpu).abs().max().item())
        ok = bool(torch.equal(y_cpu, ref_cpu))
        sample_output = y_cpu.flatten()[:8].tolist()

        samples = []
        for _ in range(3):
            start = time.perf_counter()
            for _ in range(iters):
                x_iter = x.clone()
                torch.xpu.synchronize()
                fn(x_iter)
            torch.xpu.synchronize()
            dist.barrier()
            samples.append((time.perf_counter() - start) * 1000.0 / iters)

        return {
            "name": name,
            "ok": ok,
            "max_abs": max_abs,
            "input_mutated": input_mutated,
            "mean_ms": statistics.fmean(samples),
            "samples_ms": samples,
            "sample_output_rank0": sample_output,
            "error": None,
        }
    except Exception as exc:
        try:
            dist.barrier()
        except Exception:
            pass
        return {
            "name": name,
            "ok": False,
            "max_abs": None,
            "input_mutated": None,
            "mean_ms": None,
            "samples_ms": [],
            "sample_output_rank0": [],
            "error": f"{type(exc).__name__}: {exc}",
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iters", type=int, default=200)
    parser.add_argument("--compile", action="store_true")
    args = parser.parse_args()

    local_rank = int(os.environ["LOCAL_RANK"])
    rank = int(os.environ["RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    torch.xpu.set_device(local_rank)
    dist.init_process_group(backend="xccl")
    device = f"xpu:{local_rank}"

    group_name = "b70_probe_tp"
    group = ProbeGroup(group_name, dist.group.WORLD)
    ps._register_group(group)

    results = []
    for case in default_cases():
        x = make_input(case, rank, device)
        torch.xpu.synchronize()
        dist.barrier()
        ref_cpu = analytical_ref(case, world_size, "cpu")
        paths = [
            ("direct_dist_clone", lambda t: direct_ref(t, sync=False)),
            ("vllm_custom_op_eager", lambda t: custom_op(t, group_name)),
        ]
        if args.compile:
            compiled = torch.compile(
                lambda t: custom_op(t, group_name),
                backend="inductor",
                fullgraph=True,
            )
            paths.append(("vllm_custom_op_compile", compiled))
        case_results = [
            check_path(path_name, path_fn, x, ref_cpu, args.iters)
            for path_name, path_fn in paths
        ]
        if rank == 0:
            results.append(
                {
                    "case": case.__dict__,
                    "reference_rank0": ref_cpu.flatten()[:8].tolist(),
                    "paths": case_results,
                }
            )

    if rank == 0:
        print(
            json.dumps(
                {
                    "benchmark": "b70_vllm_custom_allreduce_probe",
                    "world_size": world_size,
                    "iters": args.iters,
                    "compile": args.compile,
                    "env": {
                        key: os.environ[key]
                        for key in sorted(os.environ)
                        if key.startswith("VLLM_XPU_CUSTOM_ALLREDUCE")
                        or key.startswith("CCL_")
                    },
                    "results": results,
                },
                indent=2,
                sort_keys=True,
            )
        )

    dist.destroy_process_group()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
