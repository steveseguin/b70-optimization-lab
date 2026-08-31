#!/usr/bin/env python3
"""Cross-process Gemma RMSNorm screen at Qwen3.8 production row counts."""

import argparse
import hashlib
import json
from pathlib import Path

import torch
from vllm import ir


M_VALUES = (1, 48, 49, 52, 53, 55, 56, 57, 59, 65, 71, 75, 78)
HIDDEN = 5120
EPS = 1e-6
SEED = 20260831


def digest(parts: tuple[torch.Tensor, ...]) -> str:
    value = torch.cat([part.reshape(-1) for part in parts])
    return hashlib.sha256(value.cpu().contiguous().numpy().tobytes()).hexdigest()


def run_plain(x: torch.Tensor, weight: torch.Tensor) -> tuple[torch.Tensor, ...]:
    return (ir.ops.rms_norm(x, weight, EPS),)


def run_fused(
    x: torch.Tensor, residual: torch.Tensor, weight: torch.Tensor
) -> tuple[torch.Tensor, ...]:
    out = ir.ops.fused_add_rms_norm(x, residual, weight, EPS)
    return tuple(out) if isinstance(out, tuple) else (out,)


def invoke_twice(fn):
    first = fn()
    torch.xpu.synchronize()
    first = tuple(part.clone() for part in first)
    second = fn()
    torch.xpu.synchronize()
    return first, second, all(torch.equal(a, b) for a, b in zip(first, second))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    torch.set_num_threads(1)
    device = torch.device("xpu:0")
    generator = torch.Generator(device="cpu")
    generator.manual_seed(SEED)
    weight = (torch.randn(HIDDEN, dtype=torch.float32, generator=generator) + 1.0).to(device)
    rows = []
    for m in M_VALUES:
        xgen = torch.Generator(device="cpu"); xgen.manual_seed(SEED + m)
        rgen = torch.Generator(device="cpu"); rgen.manual_seed(SEED + 1000 + m)
        x = torch.randn(m, HIDDEN, dtype=torch.float16, generator=xgen).to(device)
        residual = torch.randn(m, HIDDEN, dtype=torch.float16, generator=rgen).to(device)
        for fused in (False, True):
            def direct():
                return run_fused(x, residual, weight) if fused else run_plain(x, weight)

            def serial():
                pieces = [run_fused(x[i:i+1], residual[i:i+1], weight) if fused else run_plain(x[i:i+1], weight) for i in range(m)]
                return tuple(torch.cat([piece[j] for piece in pieces], dim=0) for j in range(len(pieces[0])))

            def padded():
                px = torch.zeros(128, HIDDEN, dtype=x.dtype, device=device)
                pr = torch.zeros(128, HIDDEN, dtype=residual.dtype, device=device)
                px[:m].copy_(x); pr[:m].copy_(residual)
                value = run_fused(px, pr, weight) if fused else run_plain(px, weight)
                return tuple(part[:m] for part in value)

            d1,d2,dexact=invoke_twice(direct)
            s1,s2,sexact=invoke_twice(serial)
            p1,p2,pexact=invoke_twice(padded)
            rows.append({"m":m,"fused_residual":fused,
                "direct_within_exact":dexact,"serial_within_exact":sexact,"padded_within_exact":pexact,
                "direct_sha256":digest(d1),"serial_sha256":digest(s1),"padded_sha256":digest(p1),
                "direct_vs_serial_exact":all(torch.equal(a,b) for a,b in zip(d1,s1)),
                "direct_vs_padded_exact":all(torch.equal(a,b) for a,b in zip(d1,p1))})
        del x,residual
    payload = json.dumps({"seed":SEED,"hidden":HIDDEN,"rows":rows},sort_keys=True)
    if args.out is not None:
        args.out.write_text(payload + "\n")
    else:
        print(payload)


if __name__ == "__main__":
    main()
