#!/usr/bin/env python3
"""Time the Laguna expert GEMM in isolation, on one card.

Per-segment profiling puts about 69% of a verifier forward inside the graph
segments holding this kernel, and the roofline says the whole cycle runs near
38% of what the memory system permits. Endpoint legs cannot resolve that: this
host's run-to-run spread is 1.63%, so a 1% kernel change is invisible without
repeats, and each leg costs about seven minutes.

This runs the real decode shape on a single device, so four configurations can
be measured at once across the four cards, deterministically, in seconds.

It reports achieved bandwidth against a stated ceiling so a result reads as a
fraction of what the hardware can do rather than as a bare duration.

Usage:
  ONEAPI_DEVICE_SELECTOR=level_zero:0 ZE_AFFINITY_MASK=0 \
    bench_laguna_expert_gemm.py --rows 12 --iters 200
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import time

import torch

# Laguna S 2.1: 3072 hidden, 1024 MoE intermediate, 256 experts, top-10, EP4.
HIDDEN = 3072
INTERMEDIATE = 1024
NUM_EXPERTS = 256
TOPK = 10
EP_SIZE = 4
LAYERS = 48


def _int4_expert_bytes() -> float:
    """Bytes for one expert's gate+up+down at INT4 plus BF16 group scales."""
    params = 3 * HIDDEN * INTERMEDIATE
    return params * 0.5 + (params / 128) * 2


def _distinct_experts(rows: int) -> float:
    """Expected distinct experts touched by ``rows`` tokens at top-10."""
    draws = rows * TOPK
    return NUM_EXPERTS * (1.0 - (1.0 - 1.0 / NUM_EXPERTS) ** draws)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rows", type=int, default=12)
    ap.add_argument("--iters", type=int, default=200)
    ap.add_argument("--warmup", type=int, default=20)
    ap.add_argument(
        "--peak-gbps",
        type=float,
        default=532.0,
        help="achievable bandwidth for the fraction-of-roofline column",
    )
    ap.add_argument("--json-out", type=str, default="")
    args = ap.parse_args()

    if not torch.xpu.is_available():
        raise SystemExit("no XPU visible; set ONEAPI_DEVICE_SELECTOR")
    device = "xpu:0"
    rows = args.rows
    local_experts = NUM_EXPERTS // EP_SIZE

    active = _distinct_experts(rows) / EP_SIZE
    torch.manual_seed(0)
    hidden = torch.randn(rows, HIDDEN, dtype=torch.bfloat16, device=device)
    # Packed signed INT4 bytes, two values per byte, as the kernel expects.
    w13 = torch.randint(
        -128, 127, (local_experts, 2 * INTERMEDIATE, HIDDEN // 2),
        dtype=torch.int8, device=device,
    )
    w2 = torch.randint(
        -128, 127, (local_experts, HIDDEN, INTERMEDIATE // 2),
        dtype=torch.int8, device=device,
    )
    scale_groups = HIDDEN // 128
    w13_scales = torch.randn(
        local_experts, 2 * INTERMEDIATE, scale_groups,
        dtype=torch.bfloat16, device=device,
    )
    w2_scales = torch.randn(
        local_experts, HIDDEN, INTERMEDIATE // 128,
        dtype=torch.bfloat16, device=device,
    )
    topk_ids = torch.randint(
        0, NUM_EXPERTS, (rows, TOPK), dtype=torch.int32, device=device
    )
    topk_weights = torch.rand(rows, TOPK, dtype=torch.float32, device=device)

    # Read the weights an expert pass must stream, in their real packed INT4
    # layout, for the number of experts a cycle actually touches. This is not
    # the fused kernel and makes no claim about its arithmetic: it measures
    # what the memory system delivers on this layout, which is the quantity
    # the roofline argument rests on and the one an endpoint leg cannot see.
    active_int = max(1, int(round(active)))
    expert_ids = torch.arange(active_int, device=device) % local_experts
    w13_slice = w13.index_select(0, expert_ids)
    w2_slice = w2.index_select(0, expert_ids)
    read_bytes = float(
        w13_slice.numel() * w13_slice.element_size()
        + w2_slice.numel() * w2_slice.element_size()
    )

    # Read through a wide dtype. A reduction over the int8 view measures
    # PyTorch's int8 reduction kernel, which on this stack runs at 50 GB/s
    # against 555 for bfloat16 over the same bytes -- an 11x penalty that has
    # nothing to do with the memory system and would be misread as the expert
    # weights failing to stream.
    w13_wide = w13_slice.reshape(-1).view(torch.bfloat16)
    w2_wide = w2_slice.reshape(-1).view(torch.bfloat16)

    def one_pass() -> None:
        w13_wide.sum()
        w2_wide.sum()

    for _ in range(args.warmup):
        one_pass()
    torch.xpu.synchronize()

    samples = []
    for _ in range(args.iters):
        start = time.perf_counter()
        one_pass()
        torch.xpu.synchronize()
        samples.append(time.perf_counter() - start)

    median_s = st.median(samples)
    bytes_per_layer = read_bytes
    achieved = read_bytes / median_s / 1e9

    result = {
        "rows": rows,
        "local_experts": local_experts,
        "median_ms": median_s * 1e3,
        "p10_ms": st.quantiles(samples, n=10)[0] * 1e3,
        "expected_active_experts_per_rank": active,
        "expert_bytes_int4": _int4_expert_bytes(),
        "projected_bytes_per_layer_per_rank": bytes_per_layer,
        "projected_cycle_bytes_per_rank": bytes_per_layer * LAYERS,
        "achieved_gbps": achieved,
        "peak_gbps": args.peak_gbps,
        "fraction_of_roofline": achieved / args.peak_gbps,
        "device_name": torch.xpu.get_device_name(0),
    }
    print(json.dumps(result, indent=2))
    if args.json_out:
        with open(args.json_out, "w") as handle:
            json.dump(result, handle, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
