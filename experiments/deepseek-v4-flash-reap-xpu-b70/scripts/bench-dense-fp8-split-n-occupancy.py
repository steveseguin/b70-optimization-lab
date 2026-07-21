#!/usr/bin/env python3
"""Exact/timing gate for the default-off dense FP8 split-N JIT schedule."""

from __future__ import annotations

import argparse
import json
import os
import statistics
from pathlib import Path

# The wrapper has its own cache keyed by the experimental schedule. Disable
# oneDNN's descriptor-only cache so the incumbent and candidate JITs can both
# be created in one process; execution still reuses the wrapper-held primitives.
os.environ.setdefault("ONEDNN_PRIMITIVE_CACHE_CAPACITY", "0")

import torch

import vllm  # noqa: F401
import vllm._custom_ops  # noqa: F401
import vllm_xpu_kernels  # noqa: F401


FLAG = "VLLM_XPU_V4_SHARED_DOWN_FP8_SPLIT_N"
N = 4096
K = 512
GROUP = 128
LAYERS = 43


def select(mode: int | None) -> None:
    if mode is None:
        os.environ.pop(FLAG, None)
    else:
        os.environ[FLAG] = str(mode)


def bit_mismatches(left: torch.Tensor, right: torch.Tensor) -> int:
    return int((left.view(torch.uint16) != right.view(torch.uint16)).sum().item())


def timed_us(call, iterations: int) -> float:
    start = torch.xpu.Event(enable_timing=True)
    end = torch.xpu.Event(enable_timing=True)
    start.record()
    for _ in range(iterations):
        call()
    end.record()
    end.synchronize()
    return start.elapsed_time(end) * 1000.0 / iterations


class SharedDownCase:
    def __init__(self, width: int, device: torch.device) -> None:
        self.width = width
        self.q = torch.empty(
            (width, K), dtype=torch.float8_e4m3fn, device=device
        )
        # Preserve the incumbent checkpoint view: logical [K,N], NT storage.
        weight_nk = (
            torch.randn((N, K), dtype=torch.bfloat16, device=device) / 10
        ).to(torch.float8_e4m3fn)
        self.weight = weight_nk.t()
        self.a_scale = torch.empty(
            (width, K // GROUP), dtype=torch.float32, device=device
        )
        self.b_scale = torch.ones(
            (K // GROUP, N // GROUP),
            dtype=torch.float8_e8m0fnu,
            device=device,
        )
        self.empty_bias = torch.Tensor()

    def change_input(self, seed: int) -> None:
        generator = torch.Generator(device=self.q.device).manual_seed(seed)
        values = torch.randn(
            self.q.shape,
            dtype=torch.bfloat16,
            device=self.q.device,
            generator=generator,
        ) / 10
        self.q.copy_(values.to(torch.float8_e4m3fn))
        self.a_scale.copy_(
            torch.rand(
                self.a_scale.shape,
                dtype=self.a_scale.dtype,
                device=self.a_scale.device,
                generator=generator,
            )
            * 0.02
            + 0.005
        )

    def run(self, mode: int | None) -> torch.Tensor:
        select(mode)
        return torch.ops._xpu_C.fp8_gemm(
            self.q,
            self.weight,
            torch.bfloat16,
            self.a_scale,
            self.b_scale,
            self.empty_bias,
        )

    def graph(self, mode: int | None) -> tuple[torch.xpu.XPUGraph, torch.Tensor]:
        select(mode)
        graph = torch.xpu.XPUGraph()
        with torch.xpu.graph(graph):
            output = self.run(mode)
        return graph, output

    @property
    def logical_bytes(self) -> int:
        tensors = (self.q, self.weight, self.a_scale, self.b_scale)
        return sum(t.numel() * t.element_size() for t in tensors) + (
            self.width * N * torch.tensor([], dtype=torch.bfloat16).element_size()
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--card", type=int, choices=range(4), required=True)
    parser.add_argument("--width", type=int, choices=(1, 8), required=True)
    parser.add_argument("--split-n", type=int, choices=(1, 2, 4), required=True)
    parser.add_argument("--eager-epochs", type=int, default=40)
    parser.add_argument("--graph-replays", type=int, default=70)
    parser.add_argument("--warmups", type=int, default=40)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--seed", type=int, default=20260721)
    args = parser.parse_args()

    torch.manual_seed(args.seed + args.card)
    torch.xpu.manual_seed_all(args.seed + args.card)
    case = SharedDownCase(args.width, torch.device("xpu:0"))

    eager_rows = []
    for epoch in range(args.eager_epochs):
        case.change_input(args.seed + args.card * 1009 + epoch)
        expected = case.run(None)
        actual = case.run(args.split_n)
        repeat = case.run(None)
        torch.xpu.synchronize()
        mismatches = bit_mismatches(expected, actual)
        repeat_mismatches = bit_mismatches(expected, repeat)
        eager_rows.append(
            {
                "epoch": epoch,
                "mismatches": mismatches,
                "baseline_a_b_a_mismatches": repeat_mismatches,
                "exact": mismatches == 0 and repeat_mismatches == 0,
            }
        )

    case.change_input(args.seed + args.card * 1009 + 50000)
    control_graph, control_output = case.graph(None)
    candidate_graph, candidate_output = case.graph(args.split_n)
    select(None)
    graph_rows = []
    for epoch in range(args.graph_replays):
        case.change_input(args.seed + args.card * 1009 + 100000 + epoch)
        control_graph.replay()
        torch.xpu.synchronize()
        expected = control_output.clone()
        candidate_graph.replay()
        torch.xpu.synchronize()
        mismatches = bit_mismatches(expected, candidate_output)
        control_graph.replay()
        torch.xpu.synchronize()
        repeat_mismatches = bit_mismatches(expected, control_output)
        graph_rows.append(
            {
                "epoch": epoch,
                "mismatches": mismatches,
                "baseline_a_b_a_mismatches": repeat_mismatches,
                "exact": mismatches == 0 and repeat_mismatches == 0,
            }
        )

    for _ in range(args.warmups):
        control_graph.replay()
        candidate_graph.replay()
    torch.xpu.synchronize()
    control_samples = []
    candidate_samples = []
    for sample in range(args.samples):
        if sample % 2:
            candidate_samples.append(timed_us(candidate_graph.replay, args.iterations))
            control_samples.append(timed_us(control_graph.replay, args.iterations))
        else:
            control_samples.append(timed_us(control_graph.replay, args.iterations))
            candidate_samples.append(timed_us(candidate_graph.replay, args.iterations))

    control_us = statistics.median(control_samples)
    candidate_us = statistics.median(candidate_samples)
    eager_exact = sum(bool(row["exact"]) for row in eager_rows)
    graph_exact = sum(bool(row["exact"]) for row in graph_rows)
    exact = eager_exact == args.eager_epochs and graph_exact == args.graph_replays
    saved_us = control_us - candidate_us
    result = {
        "classification": "deepseek_v4_dense_fp8_split_n_occupancy_gate",
        "device": torch.xpu.get_device_name(),
        "torch": torch.__version__,
        "physical_card": args.card,
        "shape": {"m": args.width, "n": N, "k": K},
        "selector": {"name": FLAG, "value": args.split_n, "default_off": True},
        "schedule": {
            "incumbent_wg": "8x4",
            "candidate_wg": f"{args.split_n}x1",
            "subgroup_output_n_tile": 32,
            "candidate_output_n_workgroups": N // (32 * args.split_n),
            "layout_changed": False,
            "arithmetic_changed": False,
        },
        "logical_bytes_per_call": case.logical_bytes,
        "correctness": {
            "eager_exact": f"{eager_exact}/{args.eager_epochs}",
            "graph_exact": f"{graph_exact}/{args.graph_replays}",
            "passed": exact,
            "eager_rows": eager_rows,
            "graph_rows": graph_rows,
        },
        "timing": {
            "control_samples_us": control_samples,
            "candidate_samples_us": candidate_samples,
            "control_median_us": control_us,
            "candidate_median_us": candidate_us,
            "saved_us_per_call": saved_us,
            "saved_ms_per_43_layers": saved_us * LAYERS / 1000.0,
            "control_logical_gb_s": case.logical_bytes / control_us / 1000.0,
            "candidate_logical_gb_s": case.logical_bytes / candidate_us / 1000.0,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    control_graph.reset()
    candidate_graph.reset()
    select(None)
    torch.xpu.synchronize()
    return 0 if exact else 1


if __name__ == "__main__":
    raise SystemExit(main())
