#!/usr/bin/env python3
"""Bitwise comparison for Laguna eager/compiled parity packets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch


LAYER_STAGES = (
    "attn_norm",
    "attn_norm_residual",
    "attn_out",
    "post_attn_norm",
    "post_attn_residual",
    "mlp_out",
    "layer_hidden",
    "layer_residual",
)

ATTENTION_STAGES = (
    "qkv",
    "q_norm",
    "k_norm",
    "v",
    "rope_q",
    "rope_k",
    "attn_kernel",
    "gate_raw",
    "gate_softplus",
    "gated_attn",
)


def bitwise_equal(left: torch.Tensor, right: torch.Tensor) -> bool:
    return left.shape == right.shape and torch.equal(
        left.contiguous().view(torch.uint8), right.contiguous().view(torch.uint8)
    )


def tensor_result(name: str, left: torch.Tensor, right: torch.Tensor) -> dict:
    equal = bitwise_equal(left, right)
    result = {
        "name": name,
        "equal": equal,
        "dtype": str(left.dtype),
        "shape": list(left.shape),
    }
    if not equal and left.shape == right.shape:
        byte_left = left.contiguous().view(torch.uint8)
        byte_right = right.contiguous().view(torch.uint8)
        result["differing_bytes"] = int((byte_left != byte_right).sum().item())
        if left.is_floating_point():
            result["differing_elements"] = int((left != right).sum().item())
            result["max_abs_diff"] = float(
                (left.float() - right.float()).abs().max().item()
            )
    return result


def ordered_names(packet: dict) -> list[str]:
    buffers = packet["buffers"]
    names = ["_parity_embedding"]
    layer_ids = sorted(
        {
            int(name.split(".")[1])
            for name in buffers
            if name.startswith("layers.") and "._parity_" in name
        }
    )
    for layer_id in layer_ids:
        names.extend(
            (
                f"layers.{layer_id}._parity_attn_norm",
                f"layers.{layer_id}._parity_attn_norm_residual",
            )
        )
        names.extend(
            f"layers.{layer_id}.self_attn._parity_{stage}"
            for stage in ATTENTION_STAGES
        )
        names.extend(
            f"layers.{layer_id}.self_attn.o_proj._parity_{stage}"
            for stage in ("input", "local", "output")
        )
        names.extend(
            f"layers.{layer_id}._parity_{stage}" for stage in LAYER_STAGES[2:]
        )
    names.extend(("_parity_final_residual", "_parity_final_norm"))
    return [name for name in names if name in buffers]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("eager_dir", type=Path)
    parser.add_argument("compiled_dir", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    rows = []
    first_divergence = None
    for rank in range(4):
        eager_path = next(args.eager_dir.glob(f"*-rank{rank}.pt"))
        compiled_path = next(args.compiled_dir.glob(f"*-rank{rank}.pt"))
        eager = torch.load(eager_path, map_location="cpu", weights_only=False)
        compiled = torch.load(compiled_path, map_location="cpu", weights_only=False)
        comparisons = [
            tensor_result(
                name, eager["buffers"][name], compiled["buffers"][name]
            )
            for name in ordered_names(eager)
        ]
        comparisons.append(
            tensor_result("hidden_states", eager["hidden_states"], compiled["hidden_states"])
        )
        if eager["logits"] is not None and compiled["logits"] is not None:
            comparisons.append(
                tensor_result("logits", eager["logits"], compiled["logits"])
            )
        rank_first = next((row for row in comparisons if not row["equal"]), None)
        if first_divergence is None and rank_first is not None:
            first_divergence = {"rank": rank, **rank_first}
        rows.append(
            {
                "rank": rank,
                "input_id_equal": int(eager["input_id"]) == int(compiled["input_id"]),
                "position_equal": int(eager["position"]) == int(compiled["position"]),
                "first_divergence": rank_first,
                "comparisons": comparisons,
            }
        )

    result = {
        "status": "PASS" if first_divergence is None else "FAIL",
        "first_divergence": first_divergence,
        "ranks": rows,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered)
    print(rendered, end="")
    return 0 if first_divergence is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
