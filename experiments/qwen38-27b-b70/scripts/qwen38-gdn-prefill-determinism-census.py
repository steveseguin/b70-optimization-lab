#!/usr/bin/env python3
"""GDN prefill kernel repeatability census for Qwen3.8-27B (one-card vs TP2 per-rank widths).

Operator diagnostic only. A one-card MTP0 server produced different layer-0
GDN outputs for identical 2,048-token prompts while the TP2 service was bitwise
stable. This calls torch.ops._xpu_C.gdn_attention directly for one fresh prefill
(has_initial_state=False) with fixed inputs and varies only what should not
matter: the state slot index, the stale contents of the recurrent-state cache,
and allocator state. Every output (core_attn_out, z, written conv/ssm slot) must
be bitwise identical to the first trial.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

K_HEADS, V_HEADS, HEAD_K, HEAD_V, KERNEL = 16, 48, 128, 128, 4
SLOTS = 4
STALE_ELEMENTS = 384 * 1024 * 1024  # 768 MiB of float16, freed back to the caching allocator


def run_case(tp, n, trials, dev, gen):
    from vllm.model_executor.layers.mamba.mamba_utils import MambaStateShapeCalculator

    conv_shape, ssm_shape = MambaStateShapeCalculator.gated_delta_net_state_shape(
        tp, K_HEADS, V_HEADS, HEAD_K, HEAD_V, KERNEL, 0)
    key_dim, value_dim = HEAD_K * K_HEADS // tp, HEAD_V * V_HEADS // tp
    conv_dim = 2 * key_dim + value_dim
    v_local = V_HEADS // tp

    def rnd(shape, dtype, scale=1.0):
        return (torch.randn(shape, generator=gen) * scale).to(dtype).to(dev)

    conv_weights = rnd((conv_dim, KERNEL), torch.float16, 0.2)
    a_log = rnd((v_local,), torch.float32, 0.5)
    dt_bias = rnd((v_local,), torch.float16, 0.5)
    qkvz = rnd((n, 2 * key_dim + 2 * value_dim), torch.float16, 0.5)
    ba = rnd((n, 2 * v_local), torch.float16, 0.5)
    conv_state = torch.zeros((SLOTS, *conv_shape), dtype=torch.float16, device=dev)
    ssm_state = torch.zeros((SLOTS, *ssm_shape), dtype=torch.float32, device=dev)

    def offset_copy(t, offset):
        flat = torch.empty(t.numel() + offset, dtype=t.dtype, device=dev)
        view = flat[offset:].view(t.shape)
        view.copy_(t)
        return view

    def call(slot, out_offset=0, in_offset=0):
        out = offset_copy(torch.zeros((n, v_local, HEAD_V), dtype=torch.float16, device=dev), out_offset)
        z = offset_copy(torch.zeros_like(out), out_offset)
        q_in = offset_copy(qkvz, in_offset) if in_offset else qkvz
        b_in = offset_copy(ba, in_offset) if in_offset else ba
        torch.ops._xpu_C.gdn_attention(
            out, z, q_in, b_in, K_HEADS, V_HEADS, HEAD_K, HEAD_V,
            conv_state=conv_state, ssm_state=ssm_state, conv_weights=conv_weights,
            conv_bias=None, activation='silu', A_log=a_log, dt_bias=dt_bias,
            num_prefills=1, num_decodes=0, num_spec_decodes=0,
            has_initial_state=torch.zeros(1, dtype=torch.bool, device=dev),
            non_spec_query_start_loc=torch.tensor([0, n], dtype=torch.int32, device=dev),
            non_spec_token_indx=None,
            non_spec_state_indices_tensor=torch.tensor([slot], dtype=torch.int32, device=dev),
            spec_query_start_loc=None, spec_token_indx=None, spec_state_indices_tensor=None,
            num_accepted_tokens=None, num_actual_tokens=n, tp_size=tp, reorder_input=True)
        torch.xpu.synchronize()
        return out.clone(), z.clone(), conv_state[slot].clone(), ssm_state[slot].clone()

    names = ('core_attn_out', 'z', 'conv_state_slot', 'ssm_state_slot')
    reference = call(0)
    results = []
    plans = [('repeat', 0, 'zero'), ('repeat', 0, 'zero'), ('other-slot', 1, 'zero'),
             ('garbage-states', 0, 'garbage'), ('garbage-states', 2, 'garbage'),
             ('allocator-churn', 0, 'churn'), ('garbage-states', 3, 'garbage'),
             ('stale-free-zeros', 0, 'stale-zero'), ('stale-free-random', 0, 'stale-random'),
             ('stale-free-random-2', 0, 'stale-random'), ('stale-free-zeros-2', 0, 'stale-zero'),
             ('output-offset-1', 0, 'out-offset'), ('input-offset-1', 0, 'in-offset')]
    for label, slot, prep in plans[:trials]:
        if prep == 'garbage':
            conv_state.copy_(torch.randn(conv_state.shape, generator=gen).to(torch.float16))
            ssm_state.copy_(torch.randn(ssm_state.shape, generator=gen).to(torch.float32))
        else:
            conv_state.zero_()
            ssm_state.zero_()
        junk = [torch.empty(int(x), dtype=torch.float16, device=dev) for x in (4097, n * 777 + 3)] if prep == 'churn' else []
        if prep.startswith('stale'):
            # Same allocation pattern each time; only the contents left in the freed block differ.
            torch.xpu.empty_cache()
            stale = torch.empty(STALE_ELEMENTS, dtype=torch.float16, device=dev)
            if prep == 'stale-zero':
                stale.zero_()
            else:
                stale.copy_(torch.randn(STALE_ELEMENTS, generator=gen).to(torch.float16))
            torch.xpu.synchronize()
            del stale
        got = call(slot, out_offset=1 if prep == 'out-offset' else 0, in_offset=1 if prep == 'in-offset' else 0)
        del junk
        equal = {name: bool(torch.equal(a, b)) for name, a, b in zip(names, reference, got)}
        diff = {name: float((a.float() - b.float()).abs().max()) for name, a, b in zip(names, reference, got)}
        results.append(dict(trial=label, slot=slot, states=prep, equal=equal, max_abs=diff))
    return dict(tp=tp, n=n, conv_state_shape=list(conv_shape), ssm_state_shape=list(ssm_shape),
                all_equal=all(all(r['equal'].values()) for r in results), trials=results)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--seed', type=int, default=20260915)
    args = ap.parse_args()
    import vllm  # noqa: F401
    import vllm._xpu_ops  # noqa: F401
    import vllm_xpu_kernels._xpu_C  # noqa: F401

    dev = torch.device('xpu:0')
    report = dict(schema='neural.download.qwen38-gdn-prefill-determinism-census.v1',
                  classification='operator-diagnostic-only', torch=torch.__version__, cases=[])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    for tp in (1, 2):
        for n in (512, 1024, 2048, 4096):
            gen = torch.Generator().manual_seed(args.seed + tp * 10 + n)
            case = run_case(tp, n, 13, dev, gen)
            report['cases'].append(case)
            args.out.write_text(json.dumps(report, indent=1))
            print(f"tp{tp} n={n} all_equal={case['all_equal']}",
                  [(t['trial'], t['slot'], [k for k, v in t['equal'].items() if not v]) for t in case['trials']
                   if not all(t['equal'].values())], flush=True)
            torch.xpu.empty_cache()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
