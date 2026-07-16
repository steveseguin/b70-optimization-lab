#!/usr/bin/env python3
"""Measure the local DeepSeek V4 MTP draft LM-head and argmax ceiling."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from vllm.triton_utils import triton


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hidden-size", type=int, default=4096)
    parser.add_argument("--local-vocab-size", type=int, default=32320)
    parser.add_argument("--warmup-ms", type=int, default=200)
    parser.add_argument("--rep-ms", type=int, default=1000)
    parser.add_argument("--assumed-bandwidth-gbps", type=float, default=608.0)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    device = torch.device("xpu")
    generator = torch.Generator(device=device).manual_seed(17)
    hidden = torch.randn(
        (1, args.hidden_size),
        dtype=torch.bfloat16,
        device=device,
        generator=generator,
    )
    weight = torch.randn(
        (args.local_vocab_size, args.hidden_size),
        dtype=torch.bfloat16,
        device=device,
        generator=generator,
    )
    logits = torch.empty(
        (1, args.local_vocab_size), dtype=torch.bfloat16, device=device
    )

    def project() -> None:
        torch.mm(hidden, weight.t(), out=logits)

    def local_argmax() -> None:
        torch.argmax(logits, dim=-1)

    def project_argmax() -> None:
        project()
        local_argmax()

    project_argmax()
    torch.xpu.synchronize()
    project_ms = triton.testing.do_bench(
        project,
        warmup=args.warmup_ms,
        rep=args.rep_ms,
        quantiles=[0.5, 0.2, 0.8],
    )
    argmax_ms = triton.testing.do_bench(
        local_argmax,
        warmup=args.warmup_ms,
        rep=args.rep_ms,
        quantiles=[0.5, 0.2, 0.8],
    )
    combined_ms = triton.testing.do_bench(
        project_argmax,
        warmup=args.warmup_ms,
        rep=args.rep_ms,
        quantiles=[0.5, 0.2, 0.8],
    )

    weight_bytes = weight.numel() * weight.element_size()
    roofline_ms = weight_bytes / (args.assumed_bandwidth_gbps * 1e9) * 1000
    payload = {
        "shape": {
            "hidden_size": args.hidden_size,
            "local_vocab_size": args.local_vocab_size,
            "dtype": "bfloat16",
            "weight_bytes": weight_bytes,
            "weight_mib": weight_bytes / 2**20,
        },
        "projection_ms": {
            "median": float(project_ms[0]),
            "p20": float(project_ms[1]),
            "p80": float(project_ms[2]),
        },
        "argmax_ms": {
            "median": float(argmax_ms[0]),
            "p20": float(argmax_ms[1]),
            "p80": float(argmax_ms[2]),
        },
        "projection_plus_argmax_ms": {
            "median": float(combined_ms[0]),
            "p20": float(combined_ms[1]),
            "p80": float(combined_ms[2]),
        },
        "projection_effective_gbps": weight_bytes / float(project_ms[0]) / 1e6,
        "assumed_bandwidth_gbps": args.assumed_bandwidth_gbps,
        "weight_read_roofline_ms": roofline_ms,
        "perfect_fused_ceiling_ms": float(combined_ms[0]) - roofline_ms,
    }
    text = json.dumps(payload, indent=2)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
