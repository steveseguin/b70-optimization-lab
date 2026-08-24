#!/usr/bin/env python3
"""Check repeat stability of the Qwen3.5 XPU GDN prefill fallback kernel.

This is an exact-dimension synthetic operator diagnostic, not model throughput
or a model-quality evaluation.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import torch

from vllm.model_executor.layers.fla.ops.fused_sigmoid_gating import (
    fused_sigmoid_gating_delta_rule_update,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=25)
    parser.add_argument("--seed", type=int, default=20260824)
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    device = torch.device("xpu:0")
    heads_k = 16
    heads_v = 32
    head_k_dim = 128
    head_v_dim = 128
    prompt_tokens = 128

    rows = []
    for batch_size in (1, 4, 64):
        total_tokens = batch_size * prompt_tokens
        q = torch.randn(
            1,
            total_tokens,
            heads_k,
            head_k_dim,
            dtype=torch.float16,
            device=device,
        )
        k = torch.randn_like(q)
        v = torch.randn(
            1,
            total_tokens,
            heads_v,
            head_v_dim,
            dtype=torch.float16,
            device=device,
        )
        a = torch.randn(
            total_tokens, heads_v, dtype=torch.float16, device=device
        ).clamp_(-8, 4)
        b = torch.randn(
            total_tokens, heads_v, dtype=torch.float16, device=device
        )
        a_log = torch.randn(heads_v, dtype=torch.float32, device=device).clamp_(
            -4, 2
        )
        dt_bias = torch.randn(heads_v, dtype=torch.float32, device=device)
        initial_state = torch.randn(
            batch_size,
            heads_v,
            head_v_dim,
            head_k_dim,
            dtype=torch.float32,
            device=device,
        )
        cu_seqlens = torch.arange(
            0,
            total_tokens + 1,
            prompt_tokens,
            dtype=torch.int32,
            device=device,
        )

        def invoke() -> tuple[torch.Tensor, torch.Tensor]:
            return fused_sigmoid_gating_delta_rule_update(
                A_log=a_log,
                a=a,
                b=b,
                dt_bias=dt_bias,
                q=q,
                k=k,
                v=v,
                initial_state=initial_state,
                inplace_final_state=False,
                cu_seqlens=cu_seqlens,
                use_qk_l2norm_in_kernel=True,
                store_last_only=True,
            )

        reference_output, reference_state = invoke()
        torch.xpu.synchronize()
        reference_output = reference_output.clone()
        reference_state = reference_state.clone()
        output_identical = True
        state_identical = True
        output_max_abs_drift = 0.0
        state_max_abs_drift = 0.0
        for _ in range(args.repeats - 1):
            output, state = invoke()
            torch.xpu.synchronize()
            output_identical = output_identical and bool(
                torch.equal(output, reference_output)
            )
            state_identical = state_identical and bool(
                torch.equal(state, reference_state)
            )
            output_max_abs_drift = max(
                output_max_abs_drift,
                float((output.float() - reference_output.float()).abs().max()),
            )
            state_max_abs_drift = max(
                state_max_abs_drift,
                float((state - reference_state).abs().max()),
            )
        row = {
            "batch_size": batch_size,
            "tokens_per_sequence": prompt_tokens,
            "total_tokens": total_tokens,
            "repeats": args.repeats,
            "output_bit_identical": output_identical,
            "state_bit_identical": state_identical,
            "output_max_abs_drift": output_max_abs_drift,
            "state_max_abs_drift": state_max_abs_drift,
        }
        rows.append(row)
        print(json.dumps(row), flush=True)
        del reference_output, reference_state
        torch.xpu.empty_cache()

    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "synthetic_exact_dimension_gdn_prefill_repeat_stability",
        "device": torch.xpu.get_device_name(0),
        "seed": args.seed,
        "shape": {
            "key_heads": heads_k,
            "value_heads": heads_v,
            "key_head_dim": head_k_dim,
            "value_head_dim": head_v_dim,
        },
        "kernel": "fused_sigmoid_gating_delta_rule_update(store_last_only=True)",
        "rows": rows,
        "notes": [
            "Inputs and initial states were fixed across every repeat.",
            "This does not establish full-model determinism, quality, or throughput.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
