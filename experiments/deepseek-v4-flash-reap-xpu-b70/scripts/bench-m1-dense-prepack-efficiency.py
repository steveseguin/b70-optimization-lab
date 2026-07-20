#!/usr/bin/env python3
"""Four-card-ready exact/timing gate for fixed-shape FP8 dense prepacking."""

from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass
from pathlib import Path

import torch

import vllm  # noqa: F401
import vllm._custom_ops  # noqa: F401
import vllm_xpu_kernels  # noqa: F401


GROUP = 128
LAYERS = 43
SHAPES = {
    "shared_down": (4096, 512, "w8a8"),
    "wq_b": (8192, 1024, "w8a16"),
    "shared_gate_up": (1024, 4096, "w8a16"),
}


def bit_mismatches(left: torch.Tensor, right: torch.Tensor) -> int:
    assert left.dtype == right.dtype == torch.bfloat16
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


def make_prepack(weight_nk: torch.Tensor, mode: str) -> torch.Tensor:
    weight_kn = weight_nk.t()
    if mode == "contiguous":
        return weight_kn.contiguous()
    if mode == "padded64":
        k, n = weight_kn.shape
        storage = torch.empty(
            (k, n + 64), dtype=weight_kn.dtype, device=weight_kn.device
        )
        packed = storage[:, :n]
        packed.copy_(weight_kn)
        return packed
    raise ValueError(mode)


@dataclass
class DenseCase:
    name: str
    n: int
    k: int
    kind: str
    x: torch.Tensor
    q: torch.Tensor | None
    a_scale: torch.Tensor | None
    b_scale: torch.Tensor
    weight_nk: torch.Tensor
    control_weight: torch.Tensor
    candidate_weight: torch.Tensor

    @classmethod
    def create(cls, name: str, mode: str, device: torch.device) -> "DenseCase":
        n, k, kind = SHAPES[name]
        x = torch.empty((1, k), dtype=torch.bfloat16, device=device)
        weight_nk = (
            torch.randn((n, k), dtype=torch.bfloat16, device=device) / 10
        ).to(torch.float8_e4m3fn)
        control_weight = weight_nk.t()
        candidate_weight = make_prepack(weight_nk, mode)
        b_scale = torch.empty(
            (k // GROUP, n // GROUP), dtype=torch.float32, device=device
        )
        if kind == "w8a8":
            q = torch.empty((1, k), dtype=torch.float8_e4m3fn, device=device)
            a_scale = torch.empty((1, k // GROUP), dtype=torch.float32, device=device)
        else:
            q = None
            a_scale = None
        return cls(
            name,
            n,
            k,
            kind,
            x,
            q,
            a_scale,
            b_scale,
            weight_nk,
            control_weight,
            candidate_weight,
        )

    def change_input(self, seed: int) -> None:
        generator = torch.Generator(device=self.x.device).manual_seed(seed)
        self.x.copy_(
            torch.randn(
                self.x.shape,
                dtype=self.x.dtype,
                device=self.x.device,
                generator=generator,
            )
            / 10
        )
        self.b_scale.copy_(
            torch.rand(
                self.b_scale.shape,
                dtype=self.b_scale.dtype,
                device=self.b_scale.device,
                generator=generator,
            )
            * 0.02
            + 0.005
        )
        if self.kind == "w8a8":
            assert self.q is not None and self.a_scale is not None
            self.q.copy_(self.x.to(torch.float8_e4m3fn))
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

    def run(self, candidate: bool) -> torch.Tensor:
        weight = self.candidate_weight if candidate else self.control_weight
        if self.kind == "w8a8":
            assert self.q is not None and self.a_scale is not None
            return torch.ops._xpu_C.fp8_gemm(
                self.q,
                weight,
                torch.bfloat16,
                self.a_scale,
                self.b_scale,
                torch.Tensor(),
            )
        return torch.ops._xpu_C.fp8_gemm_w8a16(
            self.x, weight, self.b_scale, torch.Tensor()
        )


def graph_for(case: DenseCase, candidate: bool) -> tuple[torch.xpu.XPUGraph, torch.Tensor]:
    graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(graph):
        output = case.run(candidate)
    return graph, output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--card", type=int, choices=range(4), required=True)
    parser.add_argument("--mode", choices=("contiguous", "padded64"), required=True)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--warmups", type=int, default=40)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--seed", type=int, default=20260720)
    args = parser.parse_args()

    torch.manual_seed(args.seed + args.card)
    torch.xpu.manual_seed_all(args.seed + args.card)
    device = torch.device("xpu:0")
    cases = {
        name: DenseCase.create(name, args.mode, device) for name in SHAPES
    }

    results: dict[str, dict] = {}
    all_exact = True
    for case_index, (name, case) in enumerate(cases.items()):
        eager_rows = []
        for epoch in range(args.epochs):
            case.change_input(args.seed + args.card * 1009 + case_index * 100003 + epoch)
            expected = case.run(False)
            actual = case.run(True)
            repeat = case.run(False)
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

        case.change_input(args.seed + args.card * 1009 + case_index * 100003 + 50000)
        control_graph, control_output = graph_for(case, False)
        candidate_graph, candidate_output = graph_for(case, True)
        graph_rows = []
        for epoch in range(args.epochs):
            case.change_input(
                args.seed + args.card * 1009 + case_index * 100003 + 100000 + epoch
            )
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
        logical_bytes = case.n * case.k
        eager_exact = sum(bool(row["exact"]) for row in eager_rows)
        graph_exact = sum(bool(row["exact"]) for row in graph_rows)
        passed = eager_exact == args.epochs and graph_exact == args.epochs
        all_exact = all_exact and passed
        results[name] = {
            "shape": {"m": 1, "n": case.n, "k": case.k, "kind": case.kind},
            "layout": {
                "control_stride": list(case.control_weight.stride()),
                "candidate_stride": list(case.candidate_weight.stride()),
                "mode": args.mode,
            },
            "logical_weight_bytes": logical_bytes,
            "correctness": {
                "eager_exact": f"{eager_exact}/{args.epochs}",
                "graph_exact": f"{graph_exact}/{args.epochs}",
                "passed": passed,
                "eager_rows": eager_rows,
                "graph_rows": graph_rows,
            },
            "timing": {
                "control_samples_us": control_samples,
                "candidate_samples_us": candidate_samples,
                "control_median_us": control_us,
                "candidate_median_us": candidate_us,
                "saved_us_per_call": control_us - candidate_us,
                "saved_ms_per_token": (control_us - candidate_us) * LAYERS / 1000.0,
                "control_logical_weight_gb_s": logical_bytes / control_us / 1000.0,
                "candidate_logical_weight_gb_s": logical_bytes / candidate_us / 1000.0,
            },
        }
        control_graph.reset()
        candidate_graph.reset()

    retained = [
        row
        for row in results.values()
        if row["correctness"]["passed"]
        and row["timing"]["saved_us_per_call"] >= 0
    ]
    result = {
        "classification": "deepseek_v4_m1_dense_prepack_efficiency_gate",
        "device": torch.xpu.get_device_name(),
        "torch": torch.__version__,
        "card": args.card,
        "mode": args.mode,
        "epochs": args.epochs,
        "rows": results,
        "retained_exact_nonregressing_sum_ms_per_token": sum(
            row["timing"]["saved_ms_per_token"] for row in retained
        ),
        "all_exact": all_exact,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    torch.xpu.synchronize()
    return 0 if all_exact else 1


if __name__ == "__main__":
    raise SystemExit(main())
