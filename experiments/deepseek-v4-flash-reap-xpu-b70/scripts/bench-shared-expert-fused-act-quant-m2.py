#!/usr/bin/env python3
"""Gate M=2 shared-expert clamped-SwiGLU + FP8 quantization fusion.

The target verifier presents two rows to every shared expert.  The promoted
M=1 path already uses ``silu_and_mul_per_block_quant``, but the model wrapper
currently rejects M=2.  This microgate checks the exact production arithmetic
contract under changing inputs and measures graph-replay device time before
the M=2 route can be enabled in the model.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import torch

import vllm  # noqa: F401 - register core custom operators
import vllm._custom_ops  # noqa: F401
from vllm.platforms import current_platform


def summarize(values: list[float]) -> dict[str, float | list[float]]:
    return {
        "median_us": statistics.median(values),
        "min_us": min(values),
        "max_us": max(values),
        "samples_us": values,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--layers", type=int, default=43)
    parser.add_argument("--required-ms", type=float, default=0.50)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    torch.xpu.set_device(args.device)
    device = torch.device(args.device)
    current_platform.import_kernels()
    dtype = torch.bfloat16
    quant_dtype = current_platform.fp8_dtype()
    rows = 2
    gate_up_width = 1024
    hidden = gate_up_width // 2
    group_size = 128
    groups = hidden // group_size
    clamp_limit = 10.0
    alpha = 1.0
    beta = 0.0

    gate_up = torch.empty((rows, gate_up_width), dtype=dtype, device=device)
    reference_q = torch.empty((rows, hidden), dtype=quant_dtype, device=device)
    reference_scales = torch.empty((rows, groups), dtype=torch.float32, device=device)
    candidate_q = torch.empty_like(reference_q)
    candidate_scales = torch.empty_like(reference_scales)
    fp8 = torch.finfo(quant_dtype)

    def reference() -> None:
        # Keep the tensor operations separate.  Their BF16 store boundaries
        # are the production SiluAndMulWithClamp.forward_native contract.
        gate = torch.clamp(gate_up[:, :hidden], max=clamp_limit)
        up = torch.clamp(gate_up[:, hidden:], min=-clamp_limit, max=clamp_limit)
        activated = gate * torch.sigmoid(alpha * gate) * (up + beta)
        torch.ops._C.per_token_group_fp8_quant(
            activated,
            reference_q,
            reference_scales,
            group_size,
            1e-10,
            fp8.min,
            fp8.max,
            False,
            False,
            False,
        )

    def candidate() -> None:
        torch.ops._C.silu_and_mul_per_block_quant(
            candidate_q,
            gate_up,
            candidate_scales,
            group_size,
            None,
            False,
            False,
            clamp_limit,
            alpha,
            beta,
        )

    generator = torch.Generator(device=device).manual_seed(20260715)
    gate_up.copy_(torch.randn(gate_up.shape, dtype=dtype, device=device, generator=generator))
    for _ in range(3):
        reference()
        candidate()
    torch.xpu.synchronize()

    reference_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(reference_graph):
        reference()
    candidate_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(candidate_graph):
        candidate()
    reference_graph.replay()
    candidate_graph.replay()
    torch.xpu.synchronize()

    correctness = []
    input_scales = (0.125, 1.0, 4.0, 12.0, 32.0)
    for epoch in range(args.epochs):
        generator.manual_seed(20260715 + 97 * epoch)
        gate_up.copy_(
            torch.randn(
                gate_up.shape,
                dtype=dtype,
                device=device,
                generator=generator,
            )
            * input_scales[epoch % len(input_scales)]
        )
        # A/B/A catches stale-address and replay-state mistakes.
        reference_graph.replay()
        torch.xpu.synchronize()
        expected_q = reference_q.clone()
        expected_scales = reference_scales.clone()
        candidate_graph.replay()
        torch.xpu.synchronize()
        first_q = candidate_q.clone()
        first_scales = candidate_scales.clone()
        reference_graph.replay()
        candidate_graph.replay()
        torch.xpu.synchronize()
        q_mismatches = int(torch.count_nonzero(expected_q != candidate_q).item())
        scale_mismatches = int(
            torch.count_nonzero(expected_scales != candidate_scales).item()
        )
        correctness.append(
            {
                "epoch": epoch,
                "input_scale": input_scales[epoch % len(input_scales)],
                "q_mismatches": q_mismatches,
                "scale_mismatches": scale_mismatches,
                "candidate_repeat_exact": torch.equal(first_q, candidate_q)
                and torch.equal(first_scales, candidate_scales),
                "reference_repeat_exact": torch.equal(expected_q, reference_q)
                and torch.equal(expected_scales, reference_scales),
            }
        )

    def timed_graph_us(graph: torch.xpu.XPUGraph) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.iterations):
            graph.replay()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.iterations

    for _ in range(args.warmup):
        reference_graph.replay()
        candidate_graph.replay()
    torch.xpu.synchronize()
    reference_samples = []
    candidate_samples = []
    for sample in range(args.samples):
        if sample % 2 == 0:
            reference_samples.append(timed_graph_us(reference_graph))
            candidate_samples.append(timed_graph_us(candidate_graph))
        else:
            candidate_samples.append(timed_graph_us(candidate_graph))
            reference_samples.append(timed_graph_us(reference_graph))

    reference_timing = summarize(reference_samples)
    candidate_timing = summarize(candidate_samples)
    saved_us = reference_timing["median_us"] - candidate_timing["median_us"]
    projected_saved_ms = saved_us * args.layers / 1000.0
    exact = all(
        row["q_mismatches"] == 0
        and row["scale_mismatches"] == 0
        and row["candidate_repeat_exact"]
        and row["reference_repeat_exact"]
        for row in correctness
    )
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_shared_expert_fused_act_quant_m2_microgate",
        "device": args.device,
        "device_name": torch.xpu.get_device_name(device),
        "torch_version": torch.__version__,
        "shape": {
            "rows": rows,
            "gate_up_width": gate_up_width,
            "activated_width": hidden,
            "group_size": group_size,
            "dtype": str(dtype),
            "quant_dtype": str(quant_dtype),
        },
        "contract": {
            "clamp_limit": clamp_limit,
            "alpha": alpha,
            "beta": beta,
            "changing_input_epochs": args.epochs,
            "input_scales": input_scales,
            "graph_replay_aba_checked": True,
        },
        "correctness": {
            "exact": exact,
            "rows": correctness,
        },
        "timing": {
            "reference": reference_timing,
            "candidate": candidate_timing,
            "saved_us_per_layer": saved_us,
            "projected_saved_ms_per_cycle": projected_saved_ms,
            "layers_per_target_verification": args.layers,
        },
        "gate": {
            "required_projected_ms": args.required_ms,
            "passed": exact and projected_saved_ms >= args.required_ms,
        },
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(rendered)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered)
    return 0 if result["gate"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
