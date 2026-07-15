#!/usr/bin/env python3
"""Gate the maximum value of fusing DeepSeek V4's Q/KV RMSNorm producer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics

import torch

from vllm.models.deepseek_v4.common.ops import fused_q_kv_rmsnorm
from vllm.platforms import current_platform


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--warmup", type=int, default=100)
    parser.add_argument("--repetitions", type=int, default=400)
    parser.add_argument("--layers", type=int, default=43)
    parser.add_argument("--gate-ms-per-token", type=float, default=0.50)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    torch.xpu.set_device(args.device)
    torch.manual_seed(20260715)
    device = torch.device(args.device)
    current_platform.import_kernels()
    q_size = 1024
    kv_size = 512
    eps = 1e-6
    projection = torch.randn((1, q_size + kv_size), dtype=torch.bfloat16, device=device)
    q_weight = torch.randn((q_size,), dtype=torch.bfloat16, device=device)
    kv_weight = torch.randn((kv_size,), dtype=torch.bfloat16, device=device)

    def run() -> tuple[torch.Tensor, torch.Tensor]:
        qr, kv = projection.split([q_size, kv_size], dim=-1)
        return fused_q_kv_rmsnorm(qr, kv, q_weight, kv_weight, eps)

    for epoch in range(args.warmup):
        projection.add_((epoch % 7) * 0.0009765625)
        run()
    torch.xpu.synchronize()

    starts: list[torch.xpu.Event] = []
    ends: list[torch.xpu.Event] = []
    outputs: list[tuple[torch.Tensor, torch.Tensor]] = []
    for epoch in range(args.repetitions):
        # Change the real producer value without changing addresses or shapes.
        # This update is ordered before the start event and is not timed.
        projection.add_((epoch % 7) * 0.0009765625)
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        outputs.append(run())
        end.record()
        starts.append(start)
        ends.append(end)
    ends[-1].synchronize()
    samples_us = [start.elapsed_time(end) * 1000.0 for start, end in zip(starts, ends)]

    def run_native() -> tuple[torch.Tensor, torch.Tensor]:
        qr, kv = projection.split([q_size, kv_size], dim=-1)
        qr_out = torch.empty_like(qr)
        kv_out = torch.empty_like(kv)
        torch.ops._C.rms_norm(qr_out, qr, q_weight, eps)
        torch.ops._C.rms_norm(kv_out, kv, kv_weight, eps)
        return qr_out, kv_out

    native_starts: list[torch.xpu.Event] = []
    native_ends: list[torch.xpu.Event] = []
    native_outputs: list[tuple[torch.Tensor, torch.Tensor]] = []
    for epoch in range(args.repetitions):
        projection.add_((epoch % 7) * 0.0009765625)
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        native_outputs.append(run_native())
        end.record()
        native_starts.append(start)
        native_ends.append(end)
    native_ends[-1].synchronize()
    native_samples_us = [
        start.elapsed_time(end) * 1000.0
        for start, end in zip(native_starts, native_ends)
    ]

    experimental_samples_us: list[float] = []
    experimental_output: tuple[torch.Tensor, torch.Tensor] | None = None
    experimental_changed_inputs = None
    experimental_graph = None
    if hasattr(torch.ops._xpu_C, "deepseek_dual_rmsnorm_out"):

        def run_experimental() -> tuple[torch.Tensor, torch.Tensor]:
            qr, kv = projection.split([q_size, kv_size], dim=-1)
            qr_out = torch.empty_like(qr)
            kv_out = torch.empty_like(kv)
            torch.ops._xpu_C.deepseek_dual_rmsnorm_out(
                qr_out, kv_out, qr, kv, q_weight, kv_weight, eps
            )
            return qr_out, kv_out

        experimental_starts: list[torch.xpu.Event] = []
        experimental_ends: list[torch.xpu.Event] = []
        experimental_outputs: list[tuple[torch.Tensor, torch.Tensor]] = []
        for epoch in range(args.repetitions):
            projection.add_((epoch % 7) * 0.0009765625)
            start = torch.xpu.Event(enable_timing=True)
            end = torch.xpu.Event(enable_timing=True)
            start.record()
            experimental_outputs.append(run_experimental())
            end.record()
            experimental_starts.append(start)
            experimental_ends.append(end)
        experimental_ends[-1].synchronize()
        experimental_samples_us = [
            start.elapsed_time(end) * 1000.0
            for start, end in zip(experimental_starts, experimental_ends)
        ]

        changed_rows = []
        for epoch in range(40):
            torch.manual_seed(20260715 + epoch)
            scale = 0.125 * (1 + (epoch % 8))
            projection.copy_(torch.randn_like(projection).mul_(scale))
            reference = run()
            candidate = run_experimental()
            torch.xpu.synchronize()
            mismatches = sum(
                int(torch.count_nonzero(a != b).item())
                for a, b in zip(reference, candidate)
            )
            changed_rows.append(
                {
                    "epoch": epoch,
                    "mismatch_elements": mismatches,
                    "max_abs_difference": max(
                        float((a.float() - b.float()).abs().max().item())
                        for a, b in zip(reference, candidate)
                    ),
                }
            )
        experimental_changed_inputs = {
            "epochs": len(changed_rows),
            "exact_epochs": sum(r["mismatch_elements"] == 0 for r in changed_rows),
            "total_mismatch_elements": sum(
                r["mismatch_elements"] for r in changed_rows
            ),
            "maximum_abs_difference": max(
                r["max_abs_difference"] for r in changed_rows
            ),
            "rows": changed_rows,
        }

        # Capture with stable input/output addresses, then mutate the producer
        # value between replays. This catches stale replay and capture-unsafety.
        graph_q, graph_kv = projection.split([q_size, kv_size], dim=-1)
        graph_q_out = torch.empty_like(graph_q)
        graph_kv_out = torch.empty_like(graph_kv)
        graph = torch.xpu.XPUGraph()
        graph_rows = []
        try:
            torch.ops._xpu_C.deepseek_dual_rmsnorm_out(
                graph_q_out,
                graph_kv_out,
                graph_q,
                graph_kv,
                q_weight,
                kv_weight,
                eps,
            )
            torch.xpu.synchronize()
            with torch.xpu.graph(graph):
                torch.ops._xpu_C.deepseek_dual_rmsnorm_out(
                    graph_q_out,
                    graph_kv_out,
                    graph_q,
                    graph_kv,
                    q_weight,
                    kv_weight,
                    eps,
                )
            previous = None
            for replay in range(8):
                torch.manual_seed(20260815 + replay)
                scale = 0.125 * (1 + replay)
                projection.copy_(torch.randn_like(projection).mul_(scale))
                graph.replay()
                torch.xpu.synchronize()
                candidate = (graph_q_out.clone(), graph_kv_out.clone())
                reference = run()
                reference_repeat = run()
                eager_candidate = run_experimental()
                torch.xpu.synchronize()
                mismatches = sum(
                    int(torch.count_nonzero(a != b).item())
                    for a, b in zip(reference, candidate)
                )
                changed = previous is None or any(
                    not torch.equal(a, b) for a, b in zip(previous, candidate)
                )
                graph_rows.append(
                    {
                        "replay": replay,
                        "changed_from_previous": changed,
                        "mismatch_elements": mismatches,
                        "reference_repeat_mismatch_elements": sum(
                            int(torch.count_nonzero(a != b).item())
                            for a, b in zip(reference, reference_repeat)
                        ),
                        "graph_vs_eager_candidate_mismatch_elements": sum(
                            int(torch.count_nonzero(a != b).item())
                            for a, b in zip(candidate, eager_candidate)
                        ),
                        "eager_candidate_vs_reference_mismatch_elements": sum(
                            int(torch.count_nonzero(a != b).item())
                            for a, b in zip(reference, eager_candidate)
                        ),
                        "max_abs_difference": max(
                            float((a.float() - b.float()).abs().max().item())
                            for a, b in zip(reference, candidate)
                        ),
                    }
                )
                previous = candidate
        finally:
            graph.reset()
            torch.xpu.synchronize()
        experimental_graph = {
            "replays": len(graph_rows),
            "exact_replays": sum(r["mismatch_elements"] == 0 for r in graph_rows),
            "changed_replays": sum(r["changed_from_previous"] for r in graph_rows),
            "total_mismatch_elements": sum(
                r["mismatch_elements"] for r in graph_rows
            ),
            "maximum_abs_difference": max(
                r["max_abs_difference"] for r in graph_rows
            ),
            "rows": graph_rows,
        }

    # Re-run the final changed input at stable addresses and require bitwise
    # deterministic output before using the timing as an engineering gate.
    projection.zero_()
    projection.add_(3 * 0.0009765625)
    replay_a = run()
    torch.xpu.synchronize()
    projection.zero_()
    projection.add_(3 * 0.0009765625)
    replay_b = run()
    torch.xpu.synchronize()
    exact_replay = torch.equal(replay_a[0], replay_b[0]) and torch.equal(
        replay_a[1], replay_b[1]
    )
    native = run_native()
    torch.xpu.synchronize()
    native_exact = torch.equal(replay_b[0], native[0]) and torch.equal(
        replay_b[1], native[1]
    )
    mismatch_elements = sum(
        int(torch.count_nonzero(reference != candidate).item())
        for reference, candidate in zip(replay_b, native)
    )
    max_abs_difference = max(
        float((reference.float() - candidate.float()).abs().max().item())
        for reference, candidate in zip(replay_b, native)
    )
    experimental_result = None
    if experimental_samples_us:
        experimental_output = run_experimental()
        torch.xpu.synchronize()
        experimental_exact = torch.equal(
            replay_b[0], experimental_output[0]
        ) and torch.equal(replay_b[1], experimental_output[1])
        experimental_median_us = statistics.median(experimental_samples_us)
        experimental_result = {
            "bitwise_exact": experimental_exact,
            "mismatch_elements": sum(
                int(torch.count_nonzero(reference != candidate).item())
                for reference, candidate in zip(replay_b, experimental_output)
            ),
            "max_abs_difference": max(
                float((reference.float() - candidate.float()).abs().max().item())
                for reference, candidate in zip(replay_b, experimental_output)
            ),
            "median_us": experimental_median_us,
            "minimum_us": min(experimental_samples_us),
            "speedup": statistics.median(samples_us) / experimental_median_us,
            "projected_ms_saved_per_token": (
                (statistics.median(samples_us) - experimental_median_us)
                * args.layers
                / 1000.0
            ),
            "changed_input_gate": experimental_changed_inputs,
            "graph_replay_gate": experimental_graph,
        }

    median_us = statistics.median(samples_us)
    native_median_us = statistics.median(native_samples_us)
    projected_ms = median_us * args.layers / 1000.0
    result = {
        "schema_version": 1,
        "device": args.device,
        "shape": {
            "tokens": 1,
            "q_size": q_size,
            "kv_size": kv_size,
            "dtype": "bfloat16",
        },
        "warmup": args.warmup,
        "repetitions": args.repetitions,
        "layers_per_token": args.layers,
        "exact_changed_input_replay": exact_replay,
        "kernel_us": {
            "median": median_us,
            "p10": percentile(samples_us, 0.10),
            "p90": percentile(samples_us, 0.90),
            "minimum": min(samples_us),
        },
        "two_native_rmsnorm_us": {
            "median": native_median_us,
            "p10": percentile(native_samples_us, 0.10),
            "p90": percentile(native_samples_us, 0.90),
            "minimum": min(native_samples_us),
        },
        "native_vs_current": {
            "bitwise_exact": native_exact,
            "mismatch_elements": mismatch_elements,
            "max_abs_difference": max_abs_difference,
            "speedup": median_us / native_median_us,
            "projected_ms_saved_per_token": (
                (median_us - native_median_us) * args.layers / 1000.0
            ),
        },
        "experimental_dual_rmsnorm": experimental_result,
        "maximum_removable_ms_per_token": projected_ms,
        "gate_ms_per_token": args.gate_ms_per_token,
        "passes_upper_bound_gate": exact_replay
        and projected_ms >= args.gate_ms_per_token,
        "interpretation": (
            "This is an optimistic upper bound: a fused projection epilogue "
            "must still compute both FP32 RMSNorms and round at the existing "
            "BF16 producer boundary."
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
    return 0 if exact_replay else 1


if __name__ == "__main__":
    raise SystemExit(main())
