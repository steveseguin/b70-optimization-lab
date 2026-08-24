#!/usr/bin/env python3
"""Repeat the exact Qwen3.5 packed GDN decode segment on XPU.

The probe restores fixed input, convolution state, and recurrent state before
each eager call or graph replay. It is an operator diagnostic, not model
throughput or quality evidence.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import torch

from vllm.model_executor.layers.fla.ops.fused_recurrent import (
    fused_recurrent_gated_delta_rule_packed_decode,
)
from vllm.model_executor.layers.mamba.ops.causal_conv1d import (
    causal_conv1d_update,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=25)
    parser.add_argument("--seed", type=int, default=20260824)
    parser.add_argument("--mode", choices=("eager", "graph"), default="graph")
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    device = torch.device("xpu:0")
    heads_k = 16
    heads_v = 32
    head_k_dim = 128
    head_v_dim = 128
    conv_width = 4
    mixed_dim = 2 * heads_k * head_k_dim + heads_v * head_v_dim
    rows = []

    for batch_size in (1, 4, 64):
        mixed_backup = torch.randn(
            batch_size, mixed_dim, dtype=torch.float16, device=device
        )
        mixed_qkv = torch.empty_like(mixed_backup)
        a = torch.randn(
            batch_size, heads_v, dtype=torch.float16, device=device
        ).clamp_(-8, 4)
        b = torch.randn(
            batch_size, heads_v, dtype=torch.float16, device=device
        )
        a_log = torch.randn(heads_v, dtype=torch.float32, device=device).clamp_(
            -4, 2
        )
        dt_bias = torch.randn(heads_v, dtype=torch.float32, device=device)
        conv_weights = torch.randn(
            mixed_dim, conv_width, dtype=torch.float16, device=device
        )
        conv_bias = torch.randn(mixed_dim, dtype=torch.float16, device=device)
        conv_state_backup = torch.randn(
            batch_size + 1,
            mixed_dim,
            conv_width - 1,
            dtype=torch.float16,
            device=device,
        )
        conv_state = torch.empty_like(conv_state_backup)
        recurrent_state_backup = torch.randn(
            batch_size + 1,
            heads_v,
            head_v_dim,
            head_k_dim,
            dtype=torch.float32,
            device=device,
        )
        recurrent_state = torch.empty_like(recurrent_state_backup)
        state_indices = torch.arange(
            1, batch_size + 1, dtype=torch.int32, device=device
        )
        out = torch.empty(
            batch_size,
            1,
            heads_v,
            head_v_dim,
            dtype=torch.float16,
            device=device,
        )

        def invoke() -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
            mixed_qkv.copy_(mixed_backup)
            conv_state.copy_(conv_state_backup)
            recurrent_state.copy_(recurrent_state_backup)
            mixed_after_conv = causal_conv1d_update(
                mixed_qkv,
                conv_state,
                conv_weights,
                conv_bias,
                "silu",
                conv_state_indices=state_indices,
                validate_data=False,
            )
            fused_recurrent_gated_delta_rule_packed_decode(
                mixed_qkv=mixed_after_conv,
                a=a,
                b=b,
                A_log=a_log,
                dt_bias=dt_bias,
                scale=head_k_dim**-0.5,
                initial_state=recurrent_state,
                out=out,
                ssm_state_indices=state_indices,
                use_qk_l2norm_in_kernel=True,
            )
            return out, conv_state, recurrent_state

        invoke()
        torch.xpu.synchronize()
        if args.mode == "graph":
            graph = torch.xpu.XPUGraph()
            with torch.xpu.graph(graph):
                captured = invoke()

            def measured_invoke() -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
                graph.replay()
                return captured

        else:
            measured_invoke = invoke

        reference = tuple(value.clone() for value in measured_invoke())
        torch.xpu.synchronize()
        bit_identical = [True, True, True]
        max_abs_drift = [0.0, 0.0, 0.0]
        for _ in range(args.repeats - 1):
            observed = measured_invoke()
            torch.xpu.synchronize()
            for index, (actual, expected) in enumerate(zip(observed, reference)):
                bit_identical[index] = bit_identical[index] and bool(
                    torch.equal(actual, expected)
                )
                max_abs_drift[index] = max(
                    max_abs_drift[index],
                    float((actual.float() - expected.float()).abs().max()),
                )
        row = {
            "batch_size": batch_size,
            "repeats": args.repeats,
            "output_bit_identical": bit_identical[0],
            "conv_state_bit_identical": bit_identical[1],
            "recurrent_state_bit_identical": bit_identical[2],
            "output_max_abs_drift": max_abs_drift[0],
            "conv_state_max_abs_drift": max_abs_drift[1],
            "recurrent_state_max_abs_drift": max_abs_drift[2],
        }
        rows.append(row)
        print(json.dumps(row), flush=True)
        if args.mode == "graph":
            del captured
        del reference
        torch.xpu.empty_cache()

    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "synthetic_exact_dimension_gdn_decode_repeat_stability",
        "mode": args.mode,
        "device": torch.xpu.get_device_name(0),
        "seed": args.seed,
        "shape": {
            "key_heads": heads_k,
            "value_heads": heads_v,
            "key_head_dim": head_k_dim,
            "value_head_dim": head_v_dim,
            "conv_width": conv_width,
            "mixed_qkv_dim": mixed_dim,
        },
        "rows": rows,
        "notes": [
            "Fixed projected input and states were restored before every call.",
            "The captured segment includes causal_conv1d_update and the packed recurrent update.",
            "This does not establish full-model determinism, quality, or throughput.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
