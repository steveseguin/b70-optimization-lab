#!/usr/bin/env python3
"""A/B microbench of the GDN spec-decode persistent-scratch fix.

Measures torch.ops._xpu_C.gdn_attention_spec_decode end-to-end per call at
the exact MTP5 TP2 shapes of the 101.922 tok/s record lane:

  record lane:   VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=0 (fresh empty scratch
                 per call - the submitted configuration)
  fixed lane:    =1 with the zero-init rebuild (cached, one memset off the
                 hot path; the record configuration cannot use this because
                 the pinned build's persistent scratch is uninitialized)

Also checks the property the fix exists for: with =1, repeated calls with
the same inputs must be history-independent (bit-exact across an interleaved
poison call). Run once against the pinned .so (expect history dependence in
the =1 lane) and once against the zero-init rebuild (expect none).

Shapes (Qwen3.8-27B TP2, MTP5 verifier step):
  num_k_heads=16 -> 8 local, num_v_heads=48 -> 24 local, head dims 128,
  one request, 6 verifier rows (5 spec + 1), conv kernel width 4.

No model load; safe on the 15 GiB host under a systemd user scope.

Usage: gdn-spec-decode-scratch-bench.py [out.json]
"""
import json
import os
import sys
import time
from pathlib import Path

import torch

import vllm_xpu_kernels._xpu_C  # noqa: F401 - registers torch.ops._xpu_C

WARMUP = 50
ITERS = 300
BURST = 100
BURSTS = 10

# MTP5 TP2 shapes; override rows with GDN_BENCH_ROWS (e.g. 5 = the MTP4
# shape where the pinned build's uninitialized scratch was history-dependent)
TOTAL = int(os.environ.get("GDN_BENCH_ROWS", "6"))  # verifier rows (spec + 1)
NSPEC_DECODE = 1
K_DIM = V_DIM = 128
L_KH, L_VH = 8, 24   # TP2-local heads
QKVZ = L_KH * (2 * K_DIM + 2 * V_DIM * (48 // 16))  # 8192
BA = 2 * L_VH                                       # 48
CONV_DIM = L_KH * (2 * K_DIM + V_DIM * (48 // 16))  # 5120
CONV_W = 4
GDN_LAYERS_PER_STEP = 48  # 64 layers, 3:1 linear:full


def build_inputs(device):
    torch.manual_seed(20260819)
    f16 = dict(dtype=torch.float16, device=device)
    # spec_state_indices values 0..5 index the state cache, so it needs at
    # least 6 slots; production allocates max_num_seqs * (num_spec + 1).
    state_slots = 8
    out = dict(
        core=torch.zeros((TOTAL, L_VH, V_DIM), **f16),
        z=torch.zeros((TOTAL, L_VH, V_DIM), **f16),
        qkvz=torch.randn((TOTAL, QKVZ), **f16),
        ba=torch.randn((TOTAL, BA), **f16),
        conv_state=torch.randn((state_slots, CONV_W - 1, CONV_DIM), **f16),
        ssm_state=torch.randn((state_slots, L_VH, V_DIM, K_DIM),
                              dtype=torch.float32, device=device),
        conv_weights=torch.randn((CONV_DIM, CONV_W), **f16),
        A_log=torch.randn((L_VH,), dtype=torch.float32, device=device),
        dt_bias=torch.randn((L_VH,), **f16),
        qsl=torch.tensor([0, TOTAL], dtype=torch.int32, device=device),
        ssi=torch.arange(TOTAL, dtype=torch.int32, device=device).reshape(1, -1),
        sti=torch.arange(TOTAL, dtype=torch.int32, device=device),
        nat=torch.tensor([3], dtype=torch.int32, device=device),
    )
    return out


def call(inp):
    torch.ops._xpu_C.gdn_attention_spec_decode(
        inp["core"], inp["z"], inp["qkvz"], inp["ba"],
        16, 48, K_DIM, V_DIM,
        conv_state=inp["conv_state"], ssm_state=inp["ssm_state"],
        conv_weights=inp["conv_weights"], conv_bias=None,
        activation="silu", A_log=inp["A_log"], dt_bias=inp["dt_bias"],
        spec_query_start_loc=inp["qsl"],
        spec_state_indices_tensor=inp["ssi"],
        spec_token_indices=inp["sti"],
        num_accepted_tokens=inp["nat"],
        num_spec_decodes=NSPEC_DECODE, num_actual_tokens=TOTAL,
        tp_size=2, reorder_input=True,
    )


def set_lane(persistent: bool):
    os.environ["VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH"] = "1" if persistent else "0"


def timed_lane(persistent, inp):
    set_lane(persistent)
    for _ in range(WARMUP):
        call(inp)
    torch.xpu.synchronize()
    ts = []
    for _ in range(ITERS):
        t0 = time.perf_counter_ns()
        call(inp)
        torch.xpu.synchronize()
        ts.append(time.perf_counter_ns() - t0)
    ts.sort()
    n = len(ts)
    per_call = {"median_us": ts[n // 2] / 1e3, "p10_us": ts[n // 10] / 1e3,
                "p90_us": ts[9 * n // 10] / 1e3}
    bursts = []
    for _ in range(BURSTS):
        t0 = time.perf_counter_ns()
        for _ in range(BURST):
            call(inp)
        torch.xpu.synchronize()
        bursts.append((time.perf_counter_ns() - t0) / BURST / 1e3)
    bursts.sort()
    per_call["burst_median_us"] = bursts[len(bursts) // 2]
    return per_call


def history_check(persistent, inp):
    """out(A) -> poison(B) -> out(A'): fixed build must give A == A'."""
    set_lane(persistent)
    inp["core"].zero_()
    inp["z"].zero_()
    call(inp)
    torch.xpu.synchronize()
    a1 = inp["core"].clone()
    poison = {k: (torch.randn_like(v) if v.is_floating_point() else v)
              for k, v in inp.items()}
    poison["core"] = inp["core"]
    poison["z"] = inp["z"]
    call(poison)
    torch.xpu.synchronize()
    inp["core"].zero_()
    call(inp)
    torch.xpu.synchronize()
    a2 = inp["core"].clone()
    diff = (a1.to(torch.float32) - a2.to(torch.float32)).abs().max().item()
    return {"max_abs_diff": diff, "history_independent": bool(diff == 0.0)}


def main():
    if not torch.xpu.is_available():
        sys.exit("XPU unavailable")
    import vllm_xpu_kernels
    so = Path(vllm_xpu_kernels.__file__).parent / "_xpu_C.abi3.so"
    inp = build_inputs("xpu:0")
    out = {"date": time.strftime("%Y-%m-%d"),
           "device": torch.xpu.get_device_name(0),
           "shapes": {"total_tokens": TOTAL, "qkvz": QKVZ, "ba": BA,
                      "conv_dim": CONV_DIM, "conv_width": CONV_W,
                      "local_k_heads": L_KH, "local_v_heads": L_VH},
           "gdn_layers_per_engine_step": GDN_LAYERS_PER_STEP,
           "iters": ITERS, "burst": BURST}
    out["ephemeral_record_lane"] = timed_lane(False, inp)
    out["persistent_lane"] = timed_lane(True, inp)
    out["history_check_ephemeral"] = history_check(False, inp)
    out["history_check_persistent"] = history_check(True, inp)
    # Step-time impact of switching the record lane to the fixed persistent
    # scratch, using burst (launch-amortized) numbers.
    d_us = (out["ephemeral_record_lane"]["burst_median_us"]
            - out["persistent_lane"]["burst_median_us"])
    out["delta_us_per_call"] = d_us
    out["delta_ms_per_step_48_layers"] = d_us * GDN_LAYERS_PER_STEP / 1e3
    for k, v in out.items():
        print(f"{k}: {v}" if not isinstance(v, dict) else f"{k}: "
              + json.dumps(v))
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(out, indent=1) + "\n")
        print(f"wrote {sys.argv[1]}")


if __name__ == "__main__":
    main()
