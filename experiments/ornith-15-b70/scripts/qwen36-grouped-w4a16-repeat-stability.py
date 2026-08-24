#!/usr/bin/env python3
"""Check fixed-input repeat stability of the Qwen35MoE XPU W4A16 kernel.

This is an operator diagnostic, not a model-quality or throughput benchmark.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import torch

import vllm_xpu_kernels._moe_C  # noqa: F401
import vllm_xpu_kernels._xpu_C  # noqa: F401
from vllm_xpu_kernels.fused_moe_interface import xpu_fused_moe


def tensor_sha256(value: torch.Tensor) -> str:
    payload = value.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=25)
    parser.add_argument("--seed", type=int, default=20260824)
    parser.add_argument("--mode", choices=("eager", "graph"), default="eager")
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    device = torch.device("xpu:0")
    dtype = torch.float16
    experts = 256
    hidden = 2048
    intermediate = 512
    top_k = 8
    group_size = 128

    # Symmetric INT4 data in the ABI's packed uint8 layout. The first call
    # performs the package's one-time zero-point conversion in place.
    w13 = torch.randint(
        0,
        256,
        (experts, 2 * intermediate, hidden // 2),
        dtype=torch.uint8,
        device=device,
    )
    w2 = torch.randint(
        0,
        256,
        (experts, hidden, intermediate // 2),
        dtype=torch.uint8,
        device=device,
    )
    w13_scales = (
        torch.rand(
            experts,
            2 * intermediate,
            hidden // group_size,
            dtype=dtype,
            device=device,
        )
        * 0.01
    )
    w2_scales = (
        torch.rand(
            experts,
            hidden,
            intermediate // group_size,
            dtype=dtype,
            device=device,
        )
        * 0.01
    )

    rows = []
    for batch_size in (1, 2, 4, 8, 16, 32, 64):
        x = torch.randn(batch_size, hidden, dtype=dtype, device=device)
        ids_cpu = torch.stack(
            [torch.randperm(experts)[:top_k] for _ in range(batch_size)]
        )
        topk_ids = ids_cpu.to(device=device, dtype=torch.int32)
        topk_weights = torch.softmax(
            torch.randn(batch_size, top_k, dtype=torch.float32, device=device),
            dim=-1,
        )

        def invoke() -> torch.Tensor:
            return xpu_fused_moe(
                hidden_states=x,
                w13=w13,
                w13_scales=w13_scales,
                w13_bias=None,
                w2=w2,
                w2_scales=w2_scales,
                w2_bias=None,
                topk_weights=topk_weights,
                topk_ids=topk_ids,
                n_experts_per_token=top_k,
                activation="silu",
                num_experts=experts,
                is_int4=True,
            )

        if args.mode == "graph":
            invoke()
            torch.xpu.synchronize()
            graph = torch.xpu.XPUGraph()
            with torch.xpu.graph(graph):
                captured_output = invoke()

            def measured_invoke() -> torch.Tensor:
                graph.replay()
                return captured_output

        else:
            measured_invoke = invoke

        measured_invoke()
        torch.xpu.synchronize()
        outputs = []
        hashes = []
        for _ in range(args.repeats):
            output = measured_invoke()
            torch.xpu.synchronize()
            outputs.append(output.detach().cpu())
            hashes.append(tensor_sha256(output))
        reference = outputs[0].float()
        max_abs = max(
            float((output.float() - reference).abs().max()) for output in outputs[1:]
        )
        rows.append(
            {
                "batch_size": batch_size,
                "repeats": args.repeats,
                "unique_output_sha256": len(set(hashes)),
                "all_outputs_bit_identical": len(set(hashes)) == 1,
                "max_abs_drift_from_first": max_abs,
                "first_output_sha256": hashes[0],
            }
        )
        print(json.dumps(rows[-1]), flush=True)

    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "synthetic_exact_shape_operator_repeat_stability",
        "mode": args.mode,
        "device": torch.xpu.get_device_name(0),
        "seed": args.seed,
        "shape": {
            "experts": experts,
            "hidden_size": hidden,
            "intermediate_size": intermediate,
            "experts_per_token": top_k,
            "group_size": group_size,
        },
        "rows": rows,
        "notes": [
            "Fixed inputs, routing, weights, and scales were reused for every repeat.",
            "This diagnostic does not establish end-to-end model determinism or quality.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
