#!/usr/bin/env python3
"""Kernel-level equivalence probe for VLLM_XPU_GDN_SPEC_ROUND_STATE.

Path A mirrors vLLM's exact serial verifier-row path (VLLM_XPU_GDN_SERIAL_SPEC_DECODE with the
views fast path): the accepted state is copied into spec column 0, row 0 is decoded there with the
plain decode op, column 0 is copied into column 1, row 1 is decoded there.  Path B runs the
multi-row spec-decode op once over both rows.  With VLLM_XPU_GDN_SPEC_ROUND_STATE=1 the spec kernel
rounds its carried fp32 state through the cache dtype between the rows, which is the only
arithmetic difference between the two paths that this probe's author found in the kernel source.

Usage: PYTHONPATH=<stage> LD_LIBRARY_PATH=<stage>/vllm_xpu_kernels:... python3 this.py [seeds]
Set VLLM_XPU_GDN_SPEC_ROUND_STATE in the environment before running (read by the extension).
Prints one line per seed/case and a final PASS/FAIL for bit equality of outputs and both states.
"""
import importlib
import os
import sys

import torch

importlib.import_module("vllm_xpu_kernels._xpu_C")
ops = torch.ops._xpu_C
dev = torch.device("xpu:0")

# Qwen3.8-Flash-Next linear-attention dims, TP4 rank view (op takes global heads + tp_size).
NUM_K_HEADS, NUM_V_HEADS, HK, HV, WIDTH, TP = 16, 48, 128, 128, 4, 4
LK, LV = NUM_K_HEADS // TP, NUM_V_HEADS // TP
CONV_DIM = 2 * LK * HK + LV * HV  # 2560
QKVZ = CONV_DIM + LV * HV  # 4096
BA = 2 * LV
SLOTS = 8
ACT = "silu"
REORDER = True  # not gqa_interleaved_layout (False on this model)


def make_case(seed, accepted):
    g = torch.Generator(device="cpu").manual_seed(seed)
    r = lambda *s: (torch.randn(*s, generator=g) * 0.5).to(torch.bfloat16).to(dev)
    case = dict(
        qkvz=r(2, QKVZ),
        ba=r(2, BA),
        conv_w=r(CONV_DIM, WIDTH),
        A_log=(torch.randn(LV, generator=g) * 0.5).to(dev),  # float32
        dt_bias=r(LV),
        conv_state=r(SLOTS, WIDTH - 1, CONV_DIM),  # SD layout
        ssm_state=(torch.randn(SLOTS, LV, HV, HK, generator=g) * 0.2).to(torch.bfloat16).to(dev),
        columns=torch.tensor([[2, 3]], dtype=torch.int32, device=dev),
        accepted=torch.tensor([accepted], dtype=torch.int32, device=dev),
    )
    mode = os.environ.get("PROBE_CONV", "random")
    if mode == "identity":  # last tap 1, others 0: conv output = act(x_t) in both kernels
        w = torch.zeros(CONV_DIM, WIDTH, dtype=torch.bfloat16); w[:, -1] = 1.0
        case["conv_w"] = w.to(dev)
    elif mode == "zero":  # conv output = act(0): recurrence sees identical constant q/k/v
        case["conv_w"] = torch.zeros(CONV_DIM, WIDTH, dtype=torch.bfloat16).to(dev)
    if os.environ.get("PROBE_ZERO_STATE") == "1":
        case["ssm_state"].zero_()
    return case


def outputs():
    out = torch.zeros(2, LV, HV, dtype=torch.bfloat16, device=dev)
    z = torch.zeros(2, LV, HV, dtype=torch.bfloat16, device=dev)
    return out, z


def path_serial(c):
    conv_state, ssm_state = c["conv_state"].clone(), c["ssm_state"].clone()
    out, z = outputs()
    columns = c["columns"].long()
    source_offset = (c["accepted"].long() - 1).clamp_(min=0)
    source_slots = columns.gather(1, source_offset.view(-1, 1)).view(-1)
    first_slots = columns[:, 0]
    conv_state.index_copy_(0, first_slots, conv_state.index_select(0, source_slots))
    ssm_state.index_copy_(0, first_slots, ssm_state.index_select(0, source_slots))
    qsl = torch.arange(0, 2, dtype=torch.int32, device=dev)
    his = torch.ones(1, dtype=torch.bool, device=dev)
    for j in range(2):
        if j > 0:
            prev_slots, slots = columns[:, j - 1], columns[:, j]
            conv_state.index_copy_(0, slots, conv_state.index_select(0, prev_slots))
            ssm_state.index_copy_(0, slots, ssm_state.index_select(0, prev_slots))
        ops.gdn_attention(
            out.narrow(0, j, 1), z.narrow(0, j, 1),
            c["qkvz"].narrow(0, j, 1), c["ba"].narrow(0, j, 1),
            NUM_K_HEADS, NUM_V_HEADS, HK, HV,
            conv_state=conv_state, ssm_state=ssm_state, conv_weights=c["conv_w"], conv_bias=None,
            activation=ACT, A_log=c["A_log"], dt_bias=c["dt_bias"],
            num_prefills=0, num_decodes=1, has_initial_state=his,
            non_spec_query_start_loc=qsl,
            non_spec_state_indices_tensor=columns[:, j].to(torch.int32).contiguous(),
            num_actual_tokens=1, tp_size=TP, reorder_input=REORDER,
        )
    torch.xpu.synchronize()
    return out, z, conv_state, ssm_state


def path_spec(c):
    conv_state, ssm_state = c["conv_state"].clone(), c["ssm_state"].clone()
    out, z = outputs()
    ops.gdn_attention_spec_decode(
        out, z, c["qkvz"], c["ba"], NUM_K_HEADS, NUM_V_HEADS, HK, HV,
        conv_state=conv_state, ssm_state=ssm_state, conv_weights=c["conv_w"], conv_bias=None,
        activation=ACT, A_log=c["A_log"], dt_bias=c["dt_bias"],
        spec_query_start_loc=torch.tensor([0, 2], dtype=torch.int32, device=dev),
        spec_state_indices_tensor=c["columns"].contiguous(),
        spec_token_indices=torch.tensor([0, 1], dtype=torch.int32, device=dev),
        num_accepted_tokens=c["accepted"].contiguous(),
        num_spec_decodes=1, num_actual_tokens=2, tp_size=TP, reorder_input=REORDER,
    )
    torch.xpu.synchronize()
    return out, z, conv_state, ssm_state


def main():
    seeds = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    flag = os.environ.get("VLLM_XPU_GDN_SPEC_ROUND_STATE", "0")
    print(f"round_state flag={flag} conv={os.environ.get('PROBE_CONV','random')} zero_state={os.environ.get('PROBE_ZERO_STATE','0')}")
    ok_all = True
    for seed in range(seeds):
        for accepted in (1, 2):
            c = make_case(1000 + seed, accepted)
            a = path_serial(c)
            a2 = path_serial(c)
            b = path_spec(c)
            det = all(torch.equal(x, y) for x, y in zip(a, a2))
            cols = [2, 3]
            eq_out = torch.equal(a[0], b[0])
            eq_z = torch.equal(a[1], b[1])
            eq_conv = all(torch.equal(a[2][s], b[2][s]) for s in cols)
            eq_ssm = all(torch.equal(a[3][s], b[3][s]) for s in cols)
            row0 = torch.equal(a[0][0], b[0][0])
            maxdiff = (a[0].float() - b[0].float()).abs().max().item()
            ok = eq_out and eq_z and eq_ssm and eq_conv
            ok_all &= ok
            print(
                f"seed={seed} accepted={accepted} serial_deterministic={det} out={eq_out} "
                f"(row0={row0}) z={eq_z} ssm_cols={eq_ssm} conv_cols={eq_conv} max|dout|={maxdiff:.3e}"
            )
    print("PASS" if ok_all else "FAIL")


if __name__ == "__main__":
    main()
