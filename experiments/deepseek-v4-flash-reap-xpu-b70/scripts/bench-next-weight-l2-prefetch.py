#!/usr/bin/env python3
"""Gate finite next-weight L2 prefetch on real DeepSeek V4 dense shapes."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import torch

import vllm  # noqa: F401
import vllm_xpu_kernels._xpu_C  # noqa: F401


SHAPES = {
    "fused_wqa_wkv_6mib": (1536, 4096),
    "shared_gate_up_4mib": (1024, 4096),
    "wq_b_8mib": (8192, 1024),
}
LAYERS = 43


def summarize(values: list[float]) -> dict[str, object]:
    return {
        "median_us": statistics.median(values),
        "min_us": min(values),
        "max_us": max(values),
        "samples_us": values,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=31)
    parser.add_argument("--warmup", type=int, default=12)
    parser.add_argument("--ep-rank", type=int, choices=range(4), required=True)
    args = parser.parse_args()

    device = torch.device("xpu:0")
    main_stream = torch.xpu.current_stream(device)
    prefetch_stream = torch.xpu.Stream(device=device)
    # Larger than expected B70 L2. Mutation happens outside measured windows.
    eviction = torch.zeros(64 * 1024 * 1024, dtype=torch.uint8, device=device)
    rows: dict[str, object] = {}

    for name, (n, k) in SHAPES.items():
        x = torch.randn((1, k), dtype=torch.bfloat16, device=device) / 10
        weight_nk = (
            torch.randn((n, k), dtype=torch.bfloat16, device=device) / 10
        ).to(torch.float8_e4m3fn)
        weight_kn = weight_nk.t()
        scales = torch.ones(
            (k // 128, n // 128), dtype=torch.float32, device=device
        )
        empty_bias = torch.Tensor()

        def consumer() -> torch.Tensor:
            return torch.ops._xpu_C.fp8_gemm_w8a16(
                x, weight_kn, scales, empty_bias
            )

        baseline = consumer().clone()
        for _ in range(args.warmup):
            eviction.add_(1)
            consumer()
            torch.ops._xpu_C.deepseek_l2_prefetch(
                weight_nk, weight_nk.numel()
            )
        torch.xpu.synchronize()

        cold_samples: list[float] = []
        prefetched_samples: list[float] = []
        prefetch_samples: list[float] = []
        exact = True

        def evict() -> None:
            eviction.add_(1)
            torch.xpu.synchronize()

        def time_main(fn) -> tuple[float, torch.Tensor | None]:
            start = torch.xpu.Event(enable_timing=True)
            end = torch.xpu.Event(enable_timing=True)
            start.record(main_stream)
            value = fn()
            end.record(main_stream)
            end.synchronize()
            return start.elapsed_time(end) * 1000.0, value

        for sample in range(args.samples):
            order = ("cold", "prefetched") if sample % 2 == 0 else (
                "prefetched",
                "cold",
            )
            for mode in order:
                evict()
                if mode == "cold":
                    elapsed, output = time_main(consumer)
                    cold_samples.append(elapsed)
                else:
                    with torch.xpu.stream(prefetch_stream):
                        pf_start = torch.xpu.Event(enable_timing=True)
                        pf_end = torch.xpu.Event(enable_timing=True)
                        pf_start.record(prefetch_stream)
                        torch.ops._xpu_C.deepseek_l2_prefetch(
                            weight_nk, weight_nk.numel()
                        )
                        pf_end.record(prefetch_stream)
                    pf_end.synchronize()
                    prefetch_samples.append(
                        pf_start.elapsed_time(pf_end) * 1000.0
                    )
                    elapsed, output = time_main(consumer)
                    prefetched_samples.append(elapsed)
                exact = exact and torch.equal(baseline, output)

        cold_median = statistics.median(cold_samples)
        prefetched_median = statistics.median(prefetched_samples)
        prefetch_median = statistics.median(prefetch_samples)
        consumer_saved = cold_median - prefetched_median
        serial_net = consumer_saved - prefetch_median
        rows[name] = {
            "n": n,
            "k": k,
            "weight_bytes": weight_nk.numel(),
            "output_exact": exact,
            "cold_consumer": summarize(cold_samples),
            "prefetched_consumer": summarize(prefetched_samples),
            "prefetch": summarize(prefetch_samples),
            "consumer_saved_us": consumer_saved,
            "serial_net_saved_us": serial_net,
            "projected_consumer_saved_ms_per_token": (
                consumer_saved * LAYERS / 1000.0
            ),
            "projected_serial_net_ms_per_token": serial_net * LAYERS / 1000.0,
        }

    slowest_projection = min(
        float(row["projected_consumer_saved_ms_per_token"])
        for row in rows.values()
    )
    payload = {
        "classification": "deepseek_v4_next_weight_l2_prefetch_isolated_gate",
        "device": torch.xpu.get_device_name(),
        "ep_rank": args.ep_rank,
        "torch": torch.__version__,
        "rows": rows,
        "integration_gate": {
            "requires_all_outputs_exact": True,
            "requires_slowest_projected_consumer_saved_ms_at_least": 0.50,
            "slowest_projected_consumer_saved_ms_per_token": slowest_projection,
            "passed": all(bool(row["output_exact"]) for row in rows.values())
            and slowest_projection >= 0.50,
            "note": (
                "This isolated gate tests whether L2 staging can reduce the "
                "unchanged consumer at all. A pass still requires a second-"
                "stream overlap gate whose total critical-path saving is at "
                "least 0.50 ms/token on the slowest card."
            ),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["integration_gate"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
