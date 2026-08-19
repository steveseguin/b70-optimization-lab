#!/usr/bin/env python3
"""Microbenchmark: per-call scratch allocation cost of the MTP5 record lane.

The approved 101.922 tok/s MTP5 lane runs VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=0,
so every GDN layer allocates the 12 spec-decode scratch buffers fresh per engine
step (the fixed lane allocates once per shape and caches). These buffers are
tiny (~250 KB total), so the cost is pure allocator overhead, ~576 torch.empty
calls per step on the 48 GDN layers.

This script times the three patterns on XPU at the exact TP2/MTP5 shapes:
  empty-per-call  - the submitted record lane
  zeros-per-call  - naive alternative (must not be adopted; measured for scale)
  cached          - the zero-init fix lane (allocate+zero once, reuse)

No model is loaded; host memory stays <1 GB. Run under a memory-scoped unit,
e.g. systemd-run --user --scope -p MemoryMax=8G.

Shapes (TP2-local, from the pinned checkpoint config):
  k_heads=8 x head_k=128, v_heads=24 x head_v=128, conv dim=5120, history=3,
  qkvz_dim=8192, ba_dim=48, num_spec_decodes=1, total_spec_tokens=6 (k=5).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import torch

DTYPE = torch.float16
NUM_GDN_LAYERS = 48  # 3:1 linear:full hybrid pattern across 64 layers
NUM_SPEC_DECODES = 1
TOTAL_SPEC_TOKENS = 6  # MTP5 verifier rows
CONV_DIM = 5120
CONV_HISTORY = 3
QKVZ_DIM = 8192
BA_DIM = 48
K_HEADS, HEAD_K = 8, 128
V_HEADS, HEAD_V = 24, 128

WARMUP_STEPS = 200
MEASURE_STEPS = 1000


def alloc_scratch(device: str, ctor) -> list[torch.Tensor]:
    i32 = dict(dtype=torch.int32, device=device)
    f16 = dict(dtype=DTYPE, device=device)
    return [
        ctor((NUM_SPEC_DECODES,), **i32),                     # accepted_state_indices
        ctor((NUM_SPEC_DECODES,), **i32),                     # running_state_indices
        ctor((NUM_SPEC_DECODES, CONV_HISTORY, CONV_DIM), **f16),  # base_conv_state
        ctor((TOTAL_SPEC_TOKENS, QKVZ_DIM), **f16),           # compact_qkvz
        ctor((TOTAL_SPEC_TOKENS, BA_DIM), **f16),             # compact_ba
        ctor((TOTAL_SPEC_TOKENS, V_HEADS, HEAD_V), **f16),    # compact_z
        ctor((NUM_SPEC_DECODES,), dtype=torch.bool, device=device),  # has_initial_state
        ctor((TOTAL_SPEC_TOKENS, K_HEADS, HEAD_K), **f16),    # q
        ctor((TOTAL_SPEC_TOKENS, K_HEADS, HEAD_K), **f16),    # k
        ctor((TOTAL_SPEC_TOKENS, V_HEADS, HEAD_V), **f16),    # v
        ctor((TOTAL_SPEC_TOKENS, V_HEADS), **f16),            # b
        ctor((TOTAL_SPEC_TOKENS, V_HEADS), **f16),            # a
    ]


def bench(pattern: str, device: str) -> dict:
    ctor = {"empty-per-call": torch.empty, "zeros-per-call": torch.zeros}.get(
        pattern)
    cached: list[torch.Tensor] = []
    if pattern == "cached":
        cached = alloc_scratch(device, torch.zeros)
        torch.xpu.synchronize()

    times_ns: list[int] = []
    for step in range(WARMUP_STEPS + MEASURE_STEPS):
        t0 = time.perf_counter_ns()
        if pattern == "cached":
            # fixed lane: one cached lookup per layer, no allocation
            out = [cached[i] for _ in range(NUM_GDN_LAYERS) for i in range(12)]
        else:
            out = [t for _ in range(NUM_GDN_LAYERS)
                   for t in alloc_scratch(device, ctor)]
        if pattern == "zeros-per-call":
            torch.xpu.synchronize()  # memset kernels are device work
        dt = time.perf_counter_ns() - t0
        del out
        if step >= WARMUP_STEPS:
            times_ns.append(dt)
    torch.xpu.synchronize()

    times_ns.sort()
    n = len(times_ns)
    return {
        "pattern": pattern,
        "steps": n,
        "median_ms": times_ns[n // 2] / 1e6,
        "p10_ms": times_ns[n // 10] / 1e6,
        "p90_ms": times_ns[9 * n // 10] / 1e6,
        "mean_ms": sum(times_ns) / n / 1e6,
    }


def main() -> None:
    if not torch.xpu.is_available():
        raise SystemExit("XPU unavailable")
    device = "xpu:0"
    torch.xpu.set_device(device)

    results = [bench(p, device)
               for p in ("empty-per-call", "zeros-per-call", "cached")]
    for r in results:
        print(f"{r['pattern']:>15}: median {r['median_ms']:.4f} ms/step "
              f"(p10 {r['p10_ms']:.4f}, p90 {r['p90_ms']:.4f})")

    empty = next(r for r in results if r["pattern"] == "empty-per-call")
    cached = next(r for r in results if r["pattern"] == "cached")
    overhead_ms = empty["median_ms"] - cached["median_ms"]

    # MTP5 record: 101.922 tok/s. Tokens per step ~= 1 + 5*acceptance;
    # bracket acceptance 0.45-0.60 from the lane's MTP3/MTP4 history.
    impact = {}
    for acc in (0.45, 0.50, 0.55, 0.60):
        tokens_per_step = 1 + 5 * acc
        steps_per_s = 101.922 / tokens_per_step
        overhead_frac = overhead_ms * steps_per_s / 1000.0
        gained = 101.922 * overhead_frac / (1 - overhead_frac)
        impact[f"acceptance_{acc:.2f}"] = {
            "tokens_per_step": tokens_per_step,
            "step_ms": 1000.0 / steps_per_s,
            "overhead_ms_per_step": overhead_ms,
            "overhead_fraction": overhead_frac,
            "projected_tok_s_gain": gained,
            "projected_tok_s": 101.922 + gained,
        }
        print(f"acc={acc:.2f}: overhead {overhead_frac * 100:.2f}% of step "
              f"-> +{gained:.2f} tok/s -> {101.922 + gained:.2f}")

    out = {
        "date": time.strftime("%Y-%m-%d"),
        "device": torch.xpu.get_device_name(0),
        "shapes": {
            "num_gdn_layers": NUM_GDN_LAYERS,
            "num_spec_decodes": NUM_SPEC_DECODES,
            "total_spec_tokens": TOTAL_SPEC_TOKENS,
            "conv": [NUM_SPEC_DECODES, CONV_HISTORY, CONV_DIM],
            "qkvz": [TOTAL_SPEC_TOKENS, QKVZ_DIM],
        },
        "warmup_steps": WARMUP_STEPS,
        "measured_steps": MEASURE_STEPS,
        "results": results,
        "record_baseline_tok_s": 101.922,
        "impact": impact,
        "note": "allocator-only measurement; the true lane cost additionally "
                "includes any cache-lookup and device-side effects",
    }
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if dest:
        dest.write_text(json.dumps(out, indent=1) + "\n")
        print(f"wrote {dest}")


if __name__ == "__main__":
    main()
