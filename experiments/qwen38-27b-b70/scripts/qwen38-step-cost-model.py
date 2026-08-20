#!/usr/bin/env python3
"""Per-component decode-step cost model for the Qwen3.8-27B INT4 TP2 MTP5
record lane, measured with the production ops on this host's B70.

Answers "what's next for decode rate": how the ~35 ms engine step (101.922
tok/s, ~3.6 accepted tokens/step) splits across weight-bound GEMMs, the GDN
spec op, and the LM heads, and what effective bandwidth the int4 oneDNN GEMM
achieves at verifier width M=6 - i.e. how much kernel headroom exists beyond
the queued scratch-fix (+~1.5 tok/s) and rerank (+1.5-4.5) levers.

Method: burst-timed (100 iters between syncs) production op calls at exact
TP2-local shapes. Weights: real layer-0 checkpoint gate/up from the fusion
fixture (packed, repacked to oneDNN NT layout exactly as INCXPU does);
down/head/attn weights synthesized (timing is data-independent). GPU-only,
bounded via systemd user scope; no model load.

Usage: qwen38-step-cost-model.py [out.json]
"""
import json
import os
import sys
import time
from pathlib import Path

import torch

import vllm_xpu_kernels._xpu_C  # noqa: F401

FIXTURE = "/home/steve/qwen38-fusion-fixture-v1/fixture.safetensors"
WARMUP = 20
BURST = 100
BURSTS = 10

K = 5120
VOCAB_LOCAL = 151936 // 2          # 75968
M_VERIFY, M_DRAFT = 6, 1


def burst_time(fn):
    for _ in range(WARMUP):
        fn()
    torch.xpu.synchronize()
    ts = []
    for _ in range(BURSTS):
        t0 = time.perf_counter_ns()
        for _ in range(BURST):
            fn()
        torch.xpu.synchronize()
        ts.append((time.perf_counter_ns() - t0) / BURST / 1e3)
    ts.sort()
    return ts[len(ts) // 2]


def gbps(us, nbytes):
    return nbytes / (us * 1e-6) / 1e9


def nt_pack(qweight_k8n):
    """GPTQ [K/8, N] -> oneDNN NT view [K/8, N] strides (1, K/8... ) exactly
    as INCXPULinearMethod.process_weights_after_loading."""
    return qweight_k8n.t().contiguous().t()


def main():
    if not torch.xpu.is_available():
        sys.exit("XPU unavailable")
    dev = "xpu:0"
    from safetensors.torch import load_file
    fx = load_file(FIXTURE)
    zp8 = torch.tensor([8], dtype=torch.int8, device=dev)

    results = {}

    # --- MLP gate_up (real checkpoint weights, TP2 rank-0 local shard)
    half = 17408 // 2
    gate_nt = nt_pack(fx["layer0.gate_qweight"][:, :half]).to(dev)
    up_nt = nt_pack(fx["layer0.up_qweight"][:, :half]).to(dev)
    gs = fx["layer0.gate_scales"][:, :half].to(dev)
    us_ = fx["layer0.up_scales"][:, :half].to(dev)
    gateup_bytes = 2 * (640 * 8704 * 4 + 40 * 8704 * 2)  # packed int32 + fp16 scales
    x6 = torch.randn(M_VERIFY, K, dtype=torch.float16, device=dev)
    x1 = torch.randn(M_DRAFT, K, dtype=torch.float16, device=dev)

    def gateup(x):
        a = torch.ops._xpu_C.int4_gemm_w4a16(x, gate_nt, None, gs, zp8, 128, None, False)
        b = torch.ops._xpu_C.int4_gemm_w4a16(x, up_nt, None, us_, zp8, 128, None, False)
        return a, b

    for m, x in ((M_VERIFY, x6), (M_DRAFT, x1)):
        us = burst_time(lambda: gateup(x))
        results[f"mlp_gateup_int4_m{m}"] = {"us": us, "gbps": gbps(us, gateup_bytes)}
        print(f"{'mlp_gateup_int4_m'+str(m):>28}: {us:8.2f} us  {gbps(us, gateup_bytes):7.1f} GB/s")

    # --- MLP down_proj (synth, [6,8704] x [8704,5120] int4)
    down_nt = nt_pack(torch.randint(-2**31, 2**31 - 1, (8704 // 8, 5120),
                                    dtype=torch.int32)).to(dev)
    ds = torch.randn(8704 // 128, 5120, dtype=torch.float16, device=dev).abs()
    down_bytes = 1088 * 5120 * 4 + 68 * 5120 * 2
    xa6 = torch.randn(M_VERIFY, 8704, dtype=torch.float16, device=dev)
    xa1 = torch.randn(M_DRAFT, 8704, dtype=torch.float16, device=dev)
    for m, x in ((M_VERIFY, xa6), (M_DRAFT, xa1)):
        fn = lambda: torch.ops._xpu_C.int4_gemm_w4a16(x, down_nt, None, ds, zp8, 128, None, False)  # noqa: E731
        us = burst_time(fn)
        results[f"mlp_down_int4_m{m}"] = {"us": us, "gbps": gbps(us, down_bytes)}
        print(f"{'mlp_down_int4_m'+str(m):>28}: {us:8.2f} us  {gbps(us, down_bytes):7.1f} GB/s")

    # --- target LM head int8 ([M,5120] x [5120,75968])
    hw = torch.randint(-127, 127, (K, VOCAB_LOCAL), dtype=torch.int8, device=dev)
    hs = torch.rand(VOCAB_LOCAL, dtype=torch.float32, device=dev) * 0.01
    head_bytes = K * VOCAB_LOCAL + VOCAB_LOCAL * 4
    for m in (M_VERIFY, M_DRAFT):
        x = torch.randn(m, K, dtype=torch.float16, device=dev)
        xq, xs = torch.ops._xpu_C.per_token_quant_int8_xpu(x)

        def head():
            q, s = torch.ops._xpu_C.per_token_quant_int8_xpu(x)
            return torch.ops._xpu_C.int8_gemm_w8a8(q, s, hw, hs, torch.float16, None)
        us = burst_time(head)
        results[f"target_lm_head_int8_m{m}"] = {"us": us, "gbps": gbps(us, head_bytes)}
        print(f"{'target_lm_head_int8_m'+str(m):>28}: {us:8.2f} us  {gbps(us, head_bytes):7.1f} GB/s")

    # --- draft LM head int4 ([1,5120] x [5120,75968] int4, NT)
    dh_nt = nt_pack(torch.randint(-2**31, 2**31 - 1, (K // 8, VOCAB_LOCAL),
                                  dtype=torch.int32)).to(dev)
    dhs = torch.rand(K // 128, VOCAB_LOCAL, dtype=torch.float16, device=dev).abs()
    dhead_bytes = 640 * VOCAB_LOCAL * 4 + 40 * VOCAB_LOCAL * 2
    fn = lambda: torch.ops._xpu_C.int4_gemm_w4a16(x1, dh_nt, None, dhs, zp8, 128, None, False)  # noqa: E731
    us = burst_time(fn)
    results["draft_lm_head_int4_m1"] = {"us": us, "gbps": gbps(us, dhead_bytes)}
    print(f"{'draft_lm_head_int4_m1':>28}: {us:8.2f} us  {gbps(us, dhead_bytes):7.1f} GB/s")

    # --- GDN in_proj qkvz+ba int8 ([M,5120] x [5120,8240])
    qw = torch.randint(-127, 127, (K, 8240), dtype=torch.int8, device=dev)
    qs = torch.rand(8240, dtype=torch.float32, device=dev) * 0.01
    qkvz_bytes = K * 8240 + 8240 * 4
    for m in (M_VERIFY, M_DRAFT):
        x = torch.randn(m, K, dtype=torch.float16, device=dev)

        def qkvz():
            q, s = torch.ops._xpu_C.per_token_quant_int8_xpu(x)
            return torch.ops._xpu_C.int8_gemm_w8a8(q, s, qw, qs, torch.float16, None)
        us = burst_time(qkvz)
        results[f"gdn_inproj_int8_m{m}"] = {"us": us, "gbps": gbps(us, qkvz_bytes)}
        print(f"{'gdn_inproj_int8_m'+str(m):>28}: {us:8.2f} us  {gbps(us, qkvz_bytes):7.1f} GB/s")

    # --- GDN out_proj int4 ([M,3072] x [3072,5120])
    go_nt = nt_pack(torch.randint(-2**31, 2**31 - 1, (3072 // 8, 5120),
                                  dtype=torch.int32)).to(dev)
    gos = torch.rand(3072 // 128, 5120, dtype=torch.float16, device=dev).abs()
    go_bytes = 384 * 5120 * 4 + 24 * 5120 * 2
    for m in (M_VERIFY, M_DRAFT):
        x = torch.randn(m, 3072, dtype=torch.float16, device=dev)
        fn = lambda: torch.ops._xpu_C.int4_gemm_w4a16(x, go_nt, None, gos, zp8, 128, None, False)  # noqa: E731
        us = burst_time(fn)
        results[f"gdn_outproj_int4_m{m}"] = {"us": us, "gbps": gbps(us, go_bytes)}
        print(f"{'gdn_outproj_int4_m'+str(m):>28}: {us:8.2f} us  {gbps(us, go_bytes):7.1f} GB/s")

    # --- attention qkv int4 ([M,5120] x [5120,4096]) + o int4 ([M,3072]x[3072,5120])
    aq_nt = nt_pack(torch.randint(-2**31, 2**31 - 1, (K // 8, 4096),
                                  dtype=torch.int32)).to(dev)
    aqs = torch.rand(K // 128, 4096, dtype=torch.float16, device=dev).abs()
    aq_bytes = 640 * 4096 * 4 + 40 * 4096 * 2
    us = burst_time(lambda: torch.ops._xpu_C.int4_gemm_w4a16(x6, aq_nt, None, aqs, zp8, 128, None, False))
    results["attn_qkv_int4_m6"] = {"us": us, "gbps": gbps(us, aq_bytes)}
    print(f"{'attn_qkv_int4_m6':>28}: {us:8.2f} us  {gbps(us, aq_bytes):7.1f} GB/s")

    # ---- step model (MTP5: 1 verifier fwd M=6 over 64 layers + 5 draft fwds M=1 over 1 GDN layer + heads)
    gdn_spec_us = 43.4  # measured in 2026-08-19-gdn-scratch-ab-fixed.json
    step = {}
    step["mlp_us"] = 64 * (results["mlp_gateup_int4_m6"]["us"] + results["mlp_down_int4_m6"]["us"])
    step["gdn_us"] = 48 * (results["gdn_inproj_int8_m6"]["us"] + gdn_spec_us + results["gdn_outproj_int4_m6"]["us"])
    step["attn_us"] = 16 * (results["attn_qkv_int4_m6"]["us"] + results["gdn_outproj_int4_m6"]["us"])
    step["target_head_us"] = results["target_lm_head_int8_m6"]["us"]
    step["draft_us"] = 5 * (results["gdn_inproj_int8_m1"]["us"] + gdn_spec_us
                            + results["gdn_outproj_int4_m1"]["us"]
                            + results["draft_lm_head_int4_m1"]["us"])
    step["measured_components_total_ms"] = sum(step.values()) / 1e3
    for k, v in step.items():
        print(f"step/{k}: {v/1e3:.2f} ms" if k != "measured_components_total_ms" else f"step/{k}: {v:.2f} ms")

    out = {"date": time.strftime("%Y-%m-%d"),
           "device": torch.xpu.get_device_name(0),
           "method": "100-call bursts, production _xpu_C ops, TP2-local shapes",
           "weights": "gate/up real (fixture v1 NT repack); rest synthetic "
                      "(data-independent timing)",
           "components": results, "step_model_us": step,
           "reference_step_ms_at_101.922tok_s": 35.3,
           "note": "residual = attention kernels, TP2 allreduces (128/step), "
                   "sampler, host overhead, draft overheads not captured here"}
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(out, indent=1) + "\n")
        print(f"wrote {sys.argv[1]}")


if __name__ == "__main__":
    main()
