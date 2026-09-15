#!/usr/bin/env python3
"""Repeat-count stress census of the two XPU GDN prefill stages (conv, gated delta rule).

Operator diagnostic only. The fused gdn_attention op intermittently returns a
different core_attn_out for identical one-card prefill calls. This runs the conv
stage (causal_conv1d_non_spec) and the delta-rule stage (gated_delta_rule_non_spec)
separately, each R times on identical inputs with freshly zeroed outputs and
states, and counts bitwise mismatches against the first call, per stage and output.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

K_HEADS, V_HEADS, HEAD_K, HEAD_V, KERNEL = 16, 48, 128, 128, 4


def census(tp, n, repeats, dev, gen):
    from vllm.model_executor.layers.mamba.mamba_utils import MambaStateShapeCalculator

    conv_shape, ssm_shape = MambaStateShapeCalculator.gated_delta_net_state_shape(
        tp, K_HEADS, V_HEADS, HEAD_K, HEAD_V, KERNEL, 0)
    key_dim, value_dim, v_local = HEAD_K * K_HEADS // tp, HEAD_V * V_HEADS // tp, V_HEADS // tp

    def rnd(shape, dtype, scale):
        return (torch.randn(shape, generator=gen) * scale).to(dtype).to(dev)

    conv_weights = rnd((2 * key_dim + value_dim, KERNEL), torch.float16, 0.2)
    a_log = rnd((v_local,), torch.float32, 0.5)
    dt_bias = rnd((v_local,), torch.float16, 0.5)
    qkvz = rnd((n, 2 * key_dim + 2 * value_dim), torch.float16, 0.5)
    ba = rnd((n, 2 * v_local), torch.float16, 0.5)
    his = torch.zeros(1, dtype=torch.bool, device=dev)
    qsl = torch.tensor([0, n], dtype=torch.int32, device=dev)
    idx = torch.tensor([0], dtype=torch.int32, device=dev)

    def conv():
        z = torch.zeros((n, v_local, HEAD_V), dtype=torch.float16, device=dev)
        conv_state = torch.zeros((1, *conv_shape), dtype=torch.float16, device=dev)
        outs = torch.ops._xpu_C.causal_conv1d_non_spec(
            z, qkvz, ba, K_HEADS, V_HEADS, HEAD_K, HEAD_V, conv_state, conv_weights, None, 'silu',
            1, 0, 0, his, qsl, None, idx, n, tp, True)
        torch.xpu.synchronize()
        return [t.clone() for t in outs] + [z.clone(), conv_state.clone()]

    def delta(q, k, v, b, a):
        # The stage normalises q/k in place; every call gets fresh copies of identical inputs.
        q, k, v, b, a = (t.clone() for t in (q, k, v, b, a))
        out = torch.zeros((n, v_local, HEAD_V), dtype=torch.float16, device=dev)
        ssm_state = torch.zeros((1, *ssm_shape), dtype=torch.float32, device=dev)
        torch.ops._xpu_C.gated_delta_rule_non_spec(
            out, q, k, v, b, a, V_HEADS, HEAD_V, a_log, dt_bias, ssm_state,
            1, 0, 0, his, qsl, None, idx, n, tp)
        torch.xpu.synchronize()
        return [out.clone(), ssm_state.clone()]

    def delta_split(q, k, v, b, a, groups):
        # Heads are independent in the delta rule: run them as `groups` contiguous head groups,
        # each call shaped like one TP rank (tp_size=groups), writing into views of one output/state.
        q, k, v, b, a = (t.clone() for t in (q, k, v, b, a))
        out = torch.zeros((n, v_local, HEAD_V), dtype=torch.float16, device=dev)
        ssm_state = torch.zeros((1, *ssm_shape), dtype=torch.float32, device=dev)
        kh, vh = q.shape[1] // groups, v.shape[1] // groups
        for g in range(groups):
            ks, vs = slice(g * kh, (g + 1) * kh), slice(g * vh, (g + 1) * vh)
            out_g = torch.zeros((n, vh, HEAD_V), dtype=torch.float16, device=dev)
            state_g = ssm_state[:, vs].contiguous()
            torch.ops._xpu_C.gated_delta_rule_non_spec(
                out_g, q[:, ks].contiguous(), k[:, ks].contiguous(), v[:, vs].contiguous(),
                b[vs].contiguous(), a[vs].contiguous(), V_HEADS, HEAD_V,  # conv returns b/a as [heads, tokens]
                a_log[vs].contiguous(), dt_bias[vs].contiguous(), state_g,
                1, 0, 0, his, qsl, None, idx, n, tp * groups)
            out[:, vs] = out_g
            ssm_state[:, vs] = state_g
        torch.xpu.synchronize()
        return [out.clone(), ssm_state.clone()]

    conv_ref = conv()
    conv_names = ['q', 'k', 'v', 'b', 'a', 'z', 'conv_state']
    conv_mismatch = dict.fromkeys(conv_names, 0)
    for _ in range(repeats):
        for name, x, y in zip(conv_names, conv_ref, conv()):
            conv_mismatch[name] += int(not torch.equal(x, y))
    q, k, v, b, a = conv_ref[:5]
    delta_ref = delta(q, k, v, b, a)
    delta_mismatch = {'core_attn_out': 0, 'ssm_state': 0}
    worst = 0.0
    rows_bad = set()
    for _ in range(repeats):
        got = delta(q, k, v, b, a)
        for name, x, y in zip(delta_mismatch, delta_ref, got):
            if not torch.equal(x, y):
                delta_mismatch[name] += 1
                if name == 'core_attn_out':
                    diff = (x.float() - y.float()).abs()
                    worst = max(worst, float(diff.max()))
                    rows_bad.update(torch.nonzero(diff.amax(dim=(1, 2)) > 0).flatten().tolist()[:64])
    split = {}
    if tp == 1:
        split_ref = delta_split(q, k, v, b, a, 2)
        split_mismatch = {'core_attn_out': 0, 'ssm_state': 0}
        for _ in range(repeats):
            for name, x, y in zip(split_mismatch, split_ref, delta_split(q, k, v, b, a, 2)):
                split_mismatch[name] += int(not torch.equal(x, y))
        split = dict(split2_mismatch=split_mismatch,
                     split2_equals_whole_core=bool(torch.equal(split_ref[0], delta_ref[0])),
                     split2_equals_whole_state=bool(torch.equal(split_ref[1], delta_ref[1])),
                     split2_vs_whole_core_max_abs=float((split_ref[0].float() - delta_ref[0].float()).abs().max()))
    return dict(tp=tp, n=n, repeats=repeats, conv_mismatch=conv_mismatch, delta_mismatch=delta_mismatch,
                delta_core_max_abs=worst, delta_core_bad_rows_sample=sorted(rows_bad)[:64], **split)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--repeats', type=int, default=30)
    ap.add_argument('--seed', type=int, default=20260915)
    args = ap.parse_args()
    import vllm  # noqa: F401
    import vllm._xpu_ops  # noqa: F401
    import vllm_xpu_kernels._xpu_C  # noqa: F401

    dev = torch.device('xpu:0')
    report = dict(schema='neural.download.qwen38-gdn-stage-stress-census.v1',
                  classification='operator-diagnostic-only', torch=torch.__version__, cases=[])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    for tp, n in [(1, 1024), (1, 2048), (1, 4096), (1, 8192), (2, 8192)]:
        gen = torch.Generator().manual_seed(args.seed + tp * 100000 + n)
        case = census(tp, n, args.repeats, dev, gen)
        report['cases'].append(case)
        args.out.write_text(json.dumps(report, indent=1))
        print(f"tp{tp} n={n} delta={case['delta_mismatch']} max_abs={case['delta_core_max_abs']:.3g} "
              f"split2={case.get('split2_mismatch')} split_eq_whole core/state="
              f"{case.get('split2_equals_whole_core')}/{case.get('split2_equals_whole_state')} "
              f"diff={case.get('split2_vs_whole_core_max_abs')}", flush=True)
        torch.xpu.empty_cache()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
