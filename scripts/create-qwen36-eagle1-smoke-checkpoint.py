#!/usr/bin/env python3
"""Create a tiny vLLM-loadable EAGLE-1 draft checkpoint for Qwen 3.6 smoke tests.

This checkpoint is intentionally untrained. Its job is to validate the vLLM
EAGLE loader, draft KV setup, target embedding/head sharing, and XPU launch
path before spending time on larger hidden-state export or draft training.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import OrderedDict

import torch
from safetensors.torch import save_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--hidden-size", type=int, default=2048)
    parser.add_argument("--intermediate-size", type=int, default=4096)
    parser.add_argument("--num-attention-heads", type=int, default=16)
    parser.add_argument("--num-key-value-heads", type=int, default=2)
    parser.add_argument("--head-dim", type=int, default=128)
    parser.add_argument("--vocab-size", type=int, default=248320)
    parser.add_argument("--max-position-embeddings", type=int, default=262144)
    parser.add_argument("--dtype", default="bfloat16",
                        choices=("float32", "float16", "bfloat16"))
    parser.add_argument("--std", type=float, default=0.002)
    return parser.parse_args()


def dtype_from_name(name: str) -> torch.dtype:
    if name == "float32":
        return torch.float32
    if name == "float16":
        return torch.float16
    if name == "bfloat16":
        return torch.bfloat16
    raise ValueError(name)


def randn(shape: tuple[int, ...], *, generator: torch.Generator,
          dtype: torch.dtype, std: float) -> torch.Tensor:
    return (torch.randn(shape, generator=generator, dtype=torch.float32) * std).to(
        dtype)


def main() -> int:
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    dtype = dtype_from_name(args.dtype)
    gen = torch.Generator(device="cpu")
    gen.manual_seed(args.seed)

    h = args.hidden_size
    i = args.intermediate_size
    q = args.num_attention_heads * args.head_dim
    kv = args.num_key_value_heads * args.head_dim

    weights: "OrderedDict[str, torch.Tensor]" = OrderedDict()

    # EAGLE-1 adapter that mixes target token embedding and target hidden state.
    weights["fc.weight"] = randn((h, 2 * h), generator=gen, dtype=dtype, std=args.std)

    # One Llama decoder layer. The first EAGLE layer disables input_layernorm in
    # vLLM, so only post_attention_layernorm is present.
    prefix = "layers.0"
    weights[f"{prefix}.self_attn.q_proj.weight"] = randn(
        (q, h), generator=gen, dtype=dtype, std=args.std)
    weights[f"{prefix}.self_attn.k_proj.weight"] = randn(
        (kv, h), generator=gen, dtype=dtype, std=args.std)
    weights[f"{prefix}.self_attn.v_proj.weight"] = randn(
        (kv, h), generator=gen, dtype=dtype, std=args.std)
    weights[f"{prefix}.self_attn.o_proj.weight"] = randn(
        (h, q), generator=gen, dtype=dtype, std=args.std)
    weights[f"{prefix}.post_attention_layernorm.weight"] = torch.ones(
        (h,), dtype=dtype)
    weights[f"{prefix}.mlp.gate_proj.weight"] = randn(
        (i, h), generator=gen, dtype=dtype, std=args.std)
    weights[f"{prefix}.mlp.up_proj.weight"] = randn(
        (i, h), generator=gen, dtype=dtype, std=args.std)
    weights[f"{prefix}.mlp.down_proj.weight"] = randn(
        (h, i), generator=gen, dtype=dtype, std=args.std)

    config = {
        "architectures": ["LlamaForCausalLM"],
        "model_type": "llama",
        "vocab_size": args.vocab_size,
        "hidden_size": h,
        "intermediate_size": i,
        "num_hidden_layers": 1,
        "num_attention_heads": args.num_attention_heads,
        "num_key_value_heads": args.num_key_value_heads,
        "head_dim": args.head_dim,
        "hidden_act": "silu",
        "max_position_embeddings": args.max_position_embeddings,
        "rms_norm_eps": 1e-6,
        "rope_theta": 10000000.0,
        "attention_bias": False,
        "attention_dropout": 0.0,
        "tie_word_embeddings": False,
        "bos_token_id": 248044,
        "eos_token_id": 248044,
        "pad_token_id": None,
        "torch_dtype": args.dtype,
        "dtype": args.dtype,
        "draft_vocab_size": args.vocab_size,
    }
    generation_config = {
        "bos_token_id": 248044,
        "eos_token_id": 248044,
        "pad_token_id": None,
    }

    with open(os.path.join(args.out_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, sort_keys=True)
        f.write("\n")
    with open(
        os.path.join(args.out_dir, "generation_config.json"),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(generation_config, f, indent=2, sort_keys=True)
        f.write("\n")
    save_file(weights, os.path.join(args.out_dir, "model.safetensors"))

    summary = {
        "out_dir": args.out_dir,
        "dtype": args.dtype,
        "seed": args.seed,
        "num_tensors": len(weights),
        "num_parameters": sum(t.numel() for t in weights.values()),
        "hidden_size": h,
        "intermediate_size": i,
        "num_attention_heads": args.num_attention_heads,
        "num_key_value_heads": args.num_key_value_heads,
        "head_dim": args.head_dim,
        "omits_embed_tokens": True,
        "omits_lm_head": True,
        "expected_vllm_method": "eagle",
    }
    with open(os.path.join(args.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
