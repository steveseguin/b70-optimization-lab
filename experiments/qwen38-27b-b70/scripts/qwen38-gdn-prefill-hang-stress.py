#!/usr/bin/env python3
"""Hang stress of the fused XPU GDN prompt kernel (`_xpu_C.gdn_attention`), one card, layer-50 shapes.

Operator diagnostic only (notes/2026-10-17-hang-repro.md, 2026-10-18). The 00:31 hang of the two-card context
server ran a compute kernel past the driver's job timeout in layer 50's GDN prompt path (a 463-token prompt step
from a cached state at 7,488); the same request on a fresh server passed, so it is a race, not the data. This calls
the same fused op the server calls (`vllm._xpu_ops` -> `torch.ops._xpu_C.gdn_attention`, prefill only, an initial
state from a cache slot, TP2 head split, `reorder_input=True` as for Qwen3.5-family checkpoints) with 300-600 new
tokens, synchronising after every call. A watchdog thread prints `STUCK` with the call's shape when one call has not
returned for --stuck seconds, so the log names the call even if the driver ends the process. Nothing is compared:
the question is only whether the kernel ever fails to finish.
"""
from __future__ import annotations

import argparse
import json
import random
import threading
import time
from pathlib import Path

import torch

K_HEADS, V_HEADS, HEAD_K, HEAD_V, KERNEL = 16, 48, 128, 128, 4


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--minutes', type=float, default=20.0)
    ap.add_argument('--tp', type=int, default=2)
    ap.add_argument('--min-tokens', type=int, default=300)
    ap.add_argument('--max-tokens', type=int, default=600)
    ap.add_argument('--slots', type=int, default=8)
    ap.add_argument('--stuck', type=float, default=2.0)
    ap.add_argument('--seed', type=int, default=20261018)
    args = ap.parse_args()
    import vllm  # noqa: F401
    import vllm._xpu_ops  # noqa: F401
    import vllm_xpu_kernels._xpu_C  # noqa: F401
    from vllm.model_executor.layers.mamba.mamba_utils import MambaStateShapeCalculator

    dev = torch.device('xpu:0')
    tp = args.tp
    conv_shape, ssm_shape = MambaStateShapeCalculator.gated_delta_net_state_shape(
        tp, K_HEADS, V_HEADS, HEAD_K, HEAD_V, KERNEL, 0)
    key_dim, value_dim, v_local = HEAD_K * K_HEADS // tp, HEAD_V * V_HEADS // tp, V_HEADS // tp
    k_local = K_HEADS // tp
    gen = torch.Generator().manual_seed(args.seed)
    rng = random.Random(args.seed)

    def rnd(shape, dtype, scale):
        return (torch.randn(shape, generator=gen) * scale).to(dtype).to(dev)

    conv_weights = rnd((2 * key_dim + value_dim, KERNEL), torch.float16, 0.2)
    a_log = rnd((v_local,), torch.float32, 0.5)
    dt_bias = rnd((v_local,), torch.float16, 0.5)
    conv_state = rnd((args.slots, *conv_shape), torch.float16, 0.5)
    ssm_state = rnd((args.slots, *ssm_shape), torch.float32, 0.05)
    big = args.max_tokens
    qkvz_all = rnd((big, 2 * key_dim + 2 * value_dim), torch.float16, 0.5)
    ba_all = rnd((big, 2 * v_local), torch.float16, 0.5)
    his = torch.ones(1, dtype=torch.bool, device=dev)

    state = {'i': 0, 'n': 0, 'slot': 0, 'since': time.monotonic(), 'busy': False, 'stuck_printed': False}
    stop = threading.Event()

    def watchdog():
        while not stop.wait(0.25):
            if state['busy'] and time.monotonic() - state['since'] > args.stuck and not state['stuck_printed']:
                state['stuck_printed'] = True
                print(f"STUCK call {state['i']} tokens {state['n']} slot {state['slot']} for {args.stuck:.1f}+ s "
                      f"at {time.strftime('%H:%M:%S')}", flush=True)

    threading.Thread(target=watchdog, daemon=True).start()
    report = dict(schema='neural.download.qwen38-gdn-prefill-hang-stress.v1', classification='operator-diagnostic-only',
                  torch=torch.__version__, tp=tp, conv_shape=list(conv_shape), ssm_shape=list(ssm_shape),
                  tokens=[args.min_tokens, args.max_tokens], minutes=args.minutes, calls=0, slow=[], error=None)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    times = []
    end = time.monotonic() + 60 * args.minutes
    last_write = time.monotonic()
    print(f"start tp{tp} conv {tuple(conv_shape)} ssm {tuple(ssm_shape)} k_local {k_local} v_local {v_local}", flush=True)
    try:
        while time.monotonic() < end:
            n = rng.randint(args.min_tokens, args.max_tokens)
            slot = rng.randrange(args.slots)
            out = torch.zeros((n, v_local, HEAD_V), dtype=torch.float16, device=dev)
            z = torch.empty_like(out)
            qsl = torch.tensor([0, n], dtype=torch.int32, device=dev)
            idx = torch.tensor([slot], dtype=torch.int32, device=dev)
            state.update(i=report['calls'], n=n, slot=slot, since=time.monotonic(), busy=True)
            t0 = time.perf_counter()
            torch.ops._xpu_C.gdn_attention(
                out, z, qkvz_all[:n], ba_all[:n], K_HEADS, V_HEADS, HEAD_K, HEAD_V,
                conv_state=conv_state, ssm_state=ssm_state, conv_weights=conv_weights, conv_bias=None,
                activation='silu', A_log=a_log, dt_bias=dt_bias, num_prefills=1, num_decodes=0,
                num_spec_decodes=0, has_initial_state=his, non_spec_query_start_loc=qsl, non_spec_token_indx=None,
                non_spec_state_indices_tensor=idx, spec_query_start_loc=None, spec_token_indx=None,
                spec_state_indices_tensor=None, num_accepted_tokens=None, num_actual_tokens=n, tp_size=tp,
                reorder_input=True)
            torch.xpu.synchronize()
            dt = time.perf_counter() - t0
            state['busy'] = False
            report['calls'] += 1
            times.append(dt)
            if dt > 0.5:
                report['slow'].append(dict(call=report['calls'] - 1, tokens=n, slot=slot, seconds=round(dt, 3)))
                print(f"SLOW call {report['calls'] - 1} tokens {n} slot {slot} {dt:.3f} s", flush=True)
            if report['calls'] % 2000 == 0:
                # keep the states bounded: the delta rule may grow them over many calls from one slot
                ssm_state.mul_(0.5)
            if time.monotonic() - last_write > 30:
                last_write = time.monotonic()
                s = sorted(times[-20000:])
                report.update(p50_ms=round(1e3 * s[len(s) // 2], 3), p999_ms=round(1e3 * s[int(len(s) * 0.999)], 3),
                              max_ms=round(1e3 * max(times), 3))
                args.out.write_text(json.dumps(report, indent=1))
                print(f"progress {report['calls']} calls p50 {report['p50_ms']} ms max {report['max_ms']} ms", flush=True)
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        print(f"ERROR at call {state['i']} tokens {state['n']}: {report['error']}", flush=True)
    stop.set()
    if times:
        s = sorted(times)
        report.update(p50_ms=round(1e3 * s[len(s) // 2], 3), p999_ms=round(1e3 * s[int(len(s) * 0.999)], 3),
                      max_ms=round(1e3 * max(times), 3))
    args.out.write_text(json.dumps(report, indent=1))
    print(f"done {report['calls']} calls, slow {len(report['slow'])}, error {report['error']}", flush=True)
    return 1 if report['error'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
