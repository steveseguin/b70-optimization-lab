#!/usr/bin/env python3
"""Bitwise self-determinism bisection of Qwen3.8 decode-step ops.

Context: margin-free arms diverge ~1 argmax flip per ~3100 tokens at
runtime with oneDNN completion-barrier + input-dependency aids ON
(data/qwen38-27b-autoround-int4-baseline-20260818.json,
MARGIN_WAS_MASKING_RUNTIME_NONDETERMINISM_20260820). Named candidates:
GDN core, oneDNN INT4/INT8 GEMM, TP allreduce. This sweeps each op N
times on bitwise-identical inputs at production MTP5 TP2 shapes and
counts bitwise-distinct outputs.

GDN op mutates recurrent state in place; each iteration restores the
state snapshots first, so every call sees identical inputs.
"""
import json
import os
import sys
import time

import torch

import vllm_xpu_kernels._xpu_C  # noqa: F401 - registers torch.ops._xpu_C

ITERS = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
DEV = "xpu:0"

os.environ.setdefault("VLLM_XPU_GDN_SPEC_KERNEL_MODE", "native")
os.environ.setdefault("VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT", "0")
os.environ.setdefault("VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH", "1")

# --- GDN shapes (TP2-local, MTP5 verifier width) ---
TOTAL = 6
NSPEC_DECODE = 1
K_DIM = V_DIM = 128
L_KH, L_VH = 8, 24
QKVZ = L_KH * (2 * K_DIM + 2 * V_DIM * (48 // 16))
BA = 2 * L_VH
CONV_DIM = L_KH * (2 * K_DIM + V_DIM * (48 // 16))
CONV_W = 4


def pure_sweep(name, fn, iters=ITERS):
    ref = fn()
    torch.xpu.synchronize()
    ref = ref.clone()
    mismatches = 0
    t0 = time.perf_counter_ns()
    for i in range(iters):
        out = fn()
        if not torch.equal(out, ref):
            mismatches += 1
            if mismatches == 1:
                torch.xpu.synchronize()
                d = (out.float() - ref.float()).abs().max().item()
                print(f"  [{name}] first mismatch iter={i} "
                      f"max_abs_diff={d}", flush=True)
    torch.xpu.synchronize()
    us = (time.perf_counter_ns() - t0) / iters / 1e3
    res = {"op": name, "iters": iters, "bitwise_mismatches": mismatches,
           "us_per_call": round(us, 2)}
    print(json.dumps(res), flush=True)
    return res


def nt_pack(qweight_k8n):
    return qweight_k8n.t().contiguous().t()


def main():
    torch.xpu.set_device(0)
    torch.manual_seed(20260820)
    results = []

    # --- oneDNN INT4 GEMM: verifier M=6, prefill-ish M=341 ---
    zp8 = torch.tensor([8], dtype=torch.int8, device=DEV)
    qkv_nt = nt_pack(torch.randint(-2**31, 2**31 - 1, (5120 // 8, 1408),
                                   dtype=torch.int32)).to(DEV)
    qkv_s = torch.randn(5120 // 128, 1408, dtype=torch.float16,
                        device=DEV).abs()
    for m in (6, 341):
        x = torch.randn(m, 5120, dtype=torch.float16, device=DEV)
        results.append(pure_sweep(
            f"int4_gemm_w4a16_m{m}_5120x1408",
            lambda x=x: torch.ops._xpu_C.int4_gemm_w4a16(
                x, qkv_nt, None, qkv_s, zp8, 128, None, False)))

    # --- MLP-sized INT4: gate_up [M,5120]x[5120,17408] M=6 and M=1 ---
    gu_nt = nt_pack(torch.randint(-2**31, 2**31 - 1, (5120 // 8, 17408 // 2),
                                  dtype=torch.int32)).to(DEV)
    gu_s = torch.randn(5120 // 128, 17408 // 2, dtype=torch.float16,
                       device=DEV).abs()
    for m in (6, 1):
        x = torch.randn(m, 5120, dtype=torch.float16, device=DEV)
        results.append(pure_sweep(
            f"int4_gemm_w4a16_m{m}_5120x8704",
            lambda x=x: torch.ops._xpu_C.int4_gemm_w4a16(
                x, gu_nt, None, gu_s, zp8, 128, None, False)))

    # --- INT8 LM head (TP-local vocab half) ---
    VOCAB_LOCAL = 151936 // 2
    hw = torch.randint(-127, 127, (5120, VOCAB_LOCAL), dtype=torch.int8,
                       device=DEV)
    hs = torch.rand(VOCAB_LOCAL, dtype=torch.float32, device=DEV) * 0.01
    for m in (6, 1):
        x = torch.randn(m, 5120, dtype=torch.float16, device=DEV)

        def head(x=x):
            q, s = torch.ops._xpu_C.per_token_quant_int8_xpu(x)
            return torch.ops._xpu_C.int8_gemm_w8a8(q, s, hw, hs,
                                                   torch.float16, None)
        results.append(pure_sweep(f"int8_head_m{m}", head))

    # --- GDN spec decode (state-mutating; restore snapshots per call) ---
    f16 = dict(dtype=torch.float16, device=DEV)
    state_slots = 8
    inp = dict(
        core=torch.zeros((TOTAL, L_VH, V_DIM), **f16),
        z=torch.zeros((TOTAL, L_VH, V_DIM), **f16),
        qkvz=torch.randn((TOTAL, QKVZ), **f16),
        ba=torch.randn((TOTAL, BA), **f16),
        conv_state=torch.randn((state_slots, CONV_W - 1, CONV_DIM), **f16),
        ssm_state=torch.randn((state_slots, L_VH, V_DIM, K_DIM),
                              dtype=torch.float32, device=DEV),
        conv_weights=torch.randn((CONV_DIM, CONV_W), **f16),
        A_log=torch.randn((L_VH,), dtype=torch.float32, device=DEV),
        dt_bias=torch.randn((L_VH,), **f16),
        qsl=torch.tensor([0, TOTAL], dtype=torch.int32, device=DEV),
        ssi=torch.arange(TOTAL, dtype=torch.int32, device=DEV).reshape(1, -1),
        sti=torch.arange(TOTAL, dtype=torch.int32, device=DEV),
        nat=torch.tensor([3], dtype=torch.int32, device=DEV),
    )
    conv0 = inp["conv_state"].clone()
    ssm0 = inp["ssm_state"].clone()

    def gdn():
        inp["conv_state"].copy_(conv0)
        inp["ssm_state"].copy_(ssm0)
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
            tp_size=2, reorder_input=True)
        return torch.cat([inp["core"].flatten(), inp["z"].flatten(),
                          inp["conv_state"].flatten().half(),
                          inp["ssm_state"].flatten().half()])

    results.append(pure_sweep("gdn_spec_decode_m6_persistent_serial", gdn))

    summary = {"iters": ITERS, "results": results,
               "any_nondeterministic": any(r["bitwise_mismatches"] > 0
                                           for r in results)}
    with open(sys.argv[1], "w") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps({"any_nondeterministic":
                      summary["any_nondeterministic"]}))


if __name__ == "__main__":
    main()
