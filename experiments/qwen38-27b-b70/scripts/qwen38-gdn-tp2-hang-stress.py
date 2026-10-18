#!/usr/bin/env python3
"""Two-card hang stress: GDN prompt layers with the server's exchanges between them (TP2, both cards at once).

Operator diagnostic only (notes/2026-10-17-hang-repro.md, 2026-10-18). Run under `torchrun --nproc-per-node 2` in the
context server's image with the server's oneCCL environment (`run-20261018-gdn-tp2-hang-stress.sh`). Each step runs
--layers GDN-layer stand-ins on the same 300-600 new tokens on both ranks: an fp16 input projection, the fused prompt
kernel `torch.ops._xpu_C.gdn_attention` from a cached state (as `vllm._xpu_ops` calls it for a prompt step), an fp16
output projection, then the server's two-rank all-reduce (`all_gather_into_tensor` + a fixed-order add, the
b70_allgather_allreduce overlay), and synchronises once per step like a server step. A watchdog thread prints `STUCK`
with the rank, step and token count when a step has not finished after --stuck seconds. Nothing is compared: the
question is only whether a step ever fails to finish.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import threading
import time
from pathlib import Path

import torch
import torch.distributed as dist

K_HEADS, V_HEADS, HEAD_K, HEAD_V, KERNEL, HIDDEN = 16, 48, 128, 128, 4, 5120


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--minutes', type=float, default=20.0)
    ap.add_argument('--layers', type=int, default=16)
    ap.add_argument('--min-tokens', type=int, default=300)
    ap.add_argument('--max-tokens', type=int, default=600)
    ap.add_argument('--slots', type=int, default=8)
    ap.add_argument('--stuck', type=float, default=5.0)
    ap.add_argument('--seed', type=int, default=20261018)
    args = ap.parse_args()
    import vllm  # noqa: F401
    import vllm._xpu_ops  # noqa: F401
    import vllm_xpu_kernels._xpu_C  # noqa: F401
    from vllm.model_executor.layers.mamba.mamba_utils import MambaStateShapeCalculator

    rank, world = int(os.environ['RANK']), int(os.environ['WORLD_SIZE'])
    torch.xpu.set_device(rank)
    dev = torch.device(f'xpu:{rank}')
    dist.init_process_group('xccl', rank=rank, world_size=world)
    tp = world
    conv_shape, ssm_shape = MambaStateShapeCalculator.gated_delta_net_state_shape(
        tp, K_HEADS, V_HEADS, HEAD_K, HEAD_V, KERNEL, 0)
    key_dim, value_dim, v_local = HEAD_K * K_HEADS // tp, HEAD_V * V_HEADS // tp, V_HEADS // tp
    gen = torch.Generator().manual_seed(args.seed + rank)
    rng = random.Random(args.seed)  # same token counts on both ranks: the gathers must match

    def rnd(shape, dtype, scale):
        return (torch.randn(shape, generator=gen) * scale).to(dtype).to(dev)

    f16 = torch.float16
    w_in = rnd((HIDDEN, 2 * key_dim + 2 * value_dim), f16, 0.01)
    w_ba = rnd((HIDDEN, 2 * v_local), f16, 0.01)
    w_out = rnd((value_dim, HIDDEN), f16, 0.01)
    conv_weights = rnd((2 * key_dim + value_dim, KERNEL), f16, 0.2)
    a_log = rnd((v_local,), torch.float32, 0.5)
    dt_bias = rnd((v_local,), f16, 0.5)
    conv_state = rnd((args.slots, *conv_shape), f16, 0.5)
    ssm_state = rnd((args.slots, *ssm_shape), torch.float32, 0.05)
    x_all = rnd((args.max_tokens, HIDDEN), f16, 0.5)
    his = torch.ones(1, dtype=torch.bool, device=dev)

    state = {'step': 0, 'n': 0, 'since': time.monotonic(), 'busy': False, 'printed': False}
    stop = threading.Event()

    def watchdog():
        while not stop.wait(0.25):
            if state['busy'] and time.monotonic() - state['since'] > args.stuck and not state['printed']:
                state['printed'] = True
                print(f"STUCK rank {rank} step {state['step']} tokens {state['n']} for {args.stuck:.1f}+ s "
                      f"at {time.strftime('%H:%M:%S')}", flush=True)

    threading.Thread(target=watchdog, daemon=True).start()
    report = dict(schema='neural.download.qwen38-gdn-tp2-hang-stress.v1', classification='operator-diagnostic-only',
                  rank=rank, torch=torch.__version__, tp=tp, layers=args.layers, tokens=[args.min_tokens, args.max_tokens],
                  minutes=args.minutes, steps=0, kernel_calls=0, gathers=0, slow=[], error=None)
    out_path = args.out.parent / f'{args.out.stem}{rank}{args.out.suffix}'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    times = []
    end = time.monotonic() + 60 * args.minutes
    last_write = time.monotonic()
    print(f"start rank {rank}/{world} conv {tuple(conv_shape)} ssm {tuple(ssm_shape)} layers {args.layers}", flush=True)
    try:
        while True:
            # both ranks stop on the same step: rank 0's clock decides, shared through a tiny all-reduce every 64 steps
            if report['steps'] % 64 == 0:
                flag = torch.tensor([1.0 if time.monotonic() >= end else 0.0], device=dev)
                dist.all_reduce(flag)
                if flag.item() > 0:
                    break
            n = rng.randint(args.min_tokens, args.max_tokens)
            slots = [rng.randrange(args.slots) for _ in range(args.layers)]
            state.update(step=report['steps'], n=n, since=time.monotonic(), busy=True)
            t0 = time.perf_counter()
            h = x_all[:n]
            qsl = torch.tensor([0, n], dtype=torch.int32, device=dev)
            for layer in range(args.layers):
                qkvz = h @ w_in
                ba = h @ w_ba
                out = torch.zeros((n, v_local, HEAD_V), dtype=f16, device=dev)
                z = torch.empty_like(out)
                idx = torch.tensor([slots[layer]], dtype=torch.int32, device=dev)
                torch.ops._xpu_C.gdn_attention(
                    out, z, qkvz, ba, K_HEADS, V_HEADS, HEAD_K, HEAD_V,
                    conv_state=conv_state, ssm_state=ssm_state, conv_weights=conv_weights, conv_bias=None,
                    activation='silu', A_log=a_log, dt_bias=dt_bias, num_prefills=1, num_decodes=0,
                    num_spec_decodes=0, has_initial_state=his, non_spec_query_start_loc=qsl, non_spec_token_indx=None,
                    non_spec_state_indices_tensor=idx, spec_query_start_loc=None, spec_token_indx=None,
                    spec_state_indices_tensor=None, num_accepted_tokens=None, num_actual_tokens=n, tp_size=tp,
                    reorder_input=True)
                o = (out.reshape(n, value_dim) @ w_out).contiguous()
                gathered = torch.empty((2, n, HIDDEN), dtype=f16, device=dev)
                dist.all_gather_into_tensor(gathered, o)
                h = x_all[:n] + 0.1 * (gathered[0] + gathered[1])
            torch.xpu.synchronize()
            dt = time.perf_counter() - t0
            state['busy'] = False
            report['steps'] += 1
            report['kernel_calls'] += args.layers
            report['gathers'] += args.layers
            times.append(dt)
            if dt > 1.0:
                report['slow'].append(dict(step=report['steps'] - 1, tokens=n, seconds=round(dt, 3)))
                print(f"SLOW rank {rank} step {report['steps'] - 1} tokens {n} {dt:.3f} s", flush=True)
            if report['steps'] % 500 == 0:
                ssm_state.mul_(0.5)
            if time.monotonic() - last_write > 30:
                last_write = time.monotonic()
                s = sorted(times[-5000:])
                report.update(p50_ms=round(1e3 * s[len(s) // 2], 3), max_ms=round(1e3 * max(times), 3))
                out_path.write_text(json.dumps(report, indent=1))
                print(f"progress rank {rank} {report['steps']} steps {report['kernel_calls']} kernel calls "
                      f"p50 {report['p50_ms']} ms max {report['max_ms']} ms", flush=True)
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        print(f"ERROR rank {rank} at step {state['step']} tokens {state['n']}: {report['error']}", flush=True)
    stop.set()
    if times:
        s = sorted(times)
        report.update(p50_ms=round(1e3 * s[len(s) // 2], 3), p999_ms=round(1e3 * s[int(len(s) * 0.999)], 3),
                      max_ms=round(1e3 * max(times), 3))
    out_path.write_text(json.dumps(report, indent=1))
    print(f"done rank {rank} {report['steps']} steps {report['kernel_calls']} kernel calls, slow {len(report['slow'])}, "
          f"error {report['error']}", flush=True)
    if report['error'] is None:
        dist.destroy_process_group()
    return 1 if report['error'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
