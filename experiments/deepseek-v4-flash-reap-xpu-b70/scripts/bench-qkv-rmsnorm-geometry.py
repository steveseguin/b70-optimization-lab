#!/usr/bin/env python3
"""Search exact Triton geometry for DeepSeek V4's M=1 dual RMSNorm."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics

import torch

from vllm.models.deepseek_v4.common.ops.fused_qk_rmsnorm import (
    _fused_q_kv_rmsnorm_kernel,
    fused_q_kv_rmsnorm,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--repetitions", type=int, default=300)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    torch.xpu.set_device(args.device)
    torch.manual_seed(20260715)
    device = torch.device(args.device)
    q_size, kv_size, block_size = 1024, 512, 1024
    eps = 1e-6
    projection = torch.randn((1, q_size + kv_size), dtype=torch.bfloat16, device=device)
    q_weight = torch.randn((q_size,), dtype=torch.bfloat16, device=device)
    kv_weight = torch.randn((kv_size,), dtype=torch.bfloat16, device=device)

    def candidate(num_warps: int) -> tuple[torch.Tensor, torch.Tensor]:
        qr, kv = projection.split([q_size, kv_size], dim=-1)
        qr_out = torch.empty_like(qr)
        kv_out = torch.empty_like(kv)
        _fused_q_kv_rmsnorm_kernel[(1, 2)](
            qr,
            qr_out,
            q_weight,
            qr.stride(0),
            qr_out.stride(0),
            kv,
            kv_out,
            kv_weight,
            kv.stride(0),
            kv_out.stride(0),
            eps,
            Q_SIZE=q_size,
            KV_SIZE=kv_size,
            BLOCK_SIZE=block_size,
            num_warps=num_warps,
        )
        return qr_out, kv_out

    rows = []
    for num_warps in (1, 2, 4, 8, 16):
        exact_epochs = 0
        mismatch_elements = 0
        max_abs_difference = 0.0
        for epoch in range(40):
            projection.copy_(
                torch.sin(
                    torch.arange(q_size + kv_size, device=device) * 0.0037
                    + epoch * 0.019
                ).to(torch.bfloat16)
            )
            qr, kv = projection.split([q_size, kv_size], dim=-1)
            reference = fused_q_kv_rmsnorm(qr, kv, q_weight, kv_weight, eps)
            output = candidate(num_warps)
            torch.xpu.synchronize()
            if torch.equal(reference[0], output[0]) and torch.equal(
                reference[1], output[1]
            ):
                exact_epochs += 1
            else:
                mismatch_elements += sum(
                    int(torch.count_nonzero(want != got).item())
                    for want, got in zip(reference, output)
                )
                max_abs_difference = max(
                    max_abs_difference,
                    *(
                        float((want.float() - got.float()).abs().max().item())
                        for want, got in zip(reference, output)
                    ),
                )

        for _ in range(40):
            candidate(num_warps)
        torch.xpu.synchronize()
        starts: list[torch.xpu.Event] = []
        ends: list[torch.xpu.Event] = []
        outputs: list[tuple[torch.Tensor, torch.Tensor]] = []
        for _ in range(args.repetitions):
            start = torch.xpu.Event(enable_timing=True)
            end = torch.xpu.Event(enable_timing=True)
            start.record()
            outputs.append(candidate(num_warps))
            end.record()
            starts.append(start)
            ends.append(end)
        ends[-1].synchronize()
        samples = [start.elapsed_time(end) * 1000.0 for start, end in zip(starts, ends)]
        rows.append(
            {
                "num_warps": num_warps,
                "exact_epochs": exact_epochs,
                "mismatch_elements": mismatch_elements,
                "max_abs_difference": max_abs_difference,
                "median_us": statistics.median(samples),
                "minimum_us": min(samples),
                "p90_us": sorted(samples)[int(len(samples) * 0.9)],
            }
        )

    exact_rows = [row for row in rows if row["exact_epochs"] == 40]
    best = min(exact_rows, key=lambda row: row["median_us"])
    default = next(row for row in rows if row["num_warps"] == 4)
    result = {
        "schema_version": 1,
        "device": args.device,
        "shape": [1, q_size + kv_size],
        "dtype": "bfloat16",
        "changed_input_epochs": 40,
        "repetitions": args.repetitions,
        "rows": rows,
        "best_exact": best,
        "projected_ms_saved_per_token_vs_warps4": (
            (default["median_us"] - best["median_us"]) * 43 / 1000.0
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
