#!/usr/bin/env python3
"""Cross-process exactness probe for Qwen3.8 paged FP16 FA2 attention."""

import argparse
import hashlib
import json
from pathlib import Path

import torch
from vllm import _custom_ops as ops
from vllm_xpu_kernels.flash_attn_interface import flash_attn_varlen_func


LENGTHS = (48, 49, 52, 53, 55, 56, 57, 59, 65, 71, 75, 78)
Q_HEADS = 24
KV_HEADS = 4
HEAD_DIM = 256
BLOCK_SIZE = 64
DECODE_STEPS = 32


def digest(*tensors: torch.Tensor) -> str:
    value = hashlib.sha256()
    for tensor in tensors:
        cpu = tensor.detach().contiguous().cpu().view(torch.uint8)
        value.update(cpu.numpy().tobytes())
    return value.hexdigest()


def fixed_randn(shape, seed: int) -> torch.Tensor:
    generator = torch.Generator(device="cpu").manual_seed(seed)
    return (torch.randn(shape, generator=generator, dtype=torch.float32) * 0.125).to(torch.float16)


def write_cache(key, value, key_cache, value_cache, slots, scale):
    ops.reshape_and_cache_flash(
        key, value, key_cache, value_cache, slots, "auto", scale, scale
    )


def attention(query, key_cache, value_cache, length, block_table, cu_q, scale):
    output = torch.empty_like(query)
    return flash_attn_varlen_func(
        q=query,
        k=key_cache,
        v=value_cache,
        out=output,
        max_seqlen_q=query.shape[0],
        cu_seqlens_q=cu_q,
        max_seqlen_k=length,
        seqused_k=torch.tensor([length], dtype=torch.int32, device=query.device),
        softmax_scale=0.0625,
        causal=True,
        block_table=block_table,
        k_descale=scale.expand(1, KV_HEADS),
        v_descale=scale.expand(1, KV_HEADS),
        fa_version=2,
    )


@torch.inference_mode()
def run_case(length: int, device: str):
    total = length + DECODE_STEPS
    blocks = (total + BLOCK_SIZE - 1) // BLOCK_SIZE
    q = fixed_randn((length, Q_HEADS, HEAD_DIM), 1000 + length).to(device)
    k = fixed_randn((total, KV_HEADS, HEAD_DIM), 2000 + length).to(device)
    v = fixed_randn((total, KV_HEADS, HEAD_DIM), 3000 + length).to(device)
    slots = torch.arange(length, dtype=torch.long, device=device)
    block_table = torch.arange(blocks, dtype=torch.int32, device=device).reshape(1, -1)
    cu_prefill = torch.tensor([0, length], dtype=torch.int32, device=device)
    cu_decode = torch.tensor([0, 1], dtype=torch.int32, device=device)
    scale = torch.ones(1, dtype=torch.float32, device=device)

    prefill_outputs = []
    prefill_caches = []
    for _ in range(4):
        kc = torch.zeros((blocks, BLOCK_SIZE, KV_HEADS, HEAD_DIM), dtype=torch.float16, device=device)
        vc = torch.zeros_like(kc)
        write_cache(k[:length], v[:length], kc, vc, slots, scale)
        output = attention(q, kc, vc, length, block_table, cu_prefill, scale)
        torch.xpu.synchronize()
        prefill_caches.append(digest(kc, vc))
        prefill_outputs.append(digest(output))

    kc = torch.zeros((blocks, BLOCK_SIZE, KV_HEADS, HEAD_DIM), dtype=torch.float16, device=device)
    vc = torch.zeros_like(kc)
    write_cache(k[:length], v[:length], kc, vc, slots, scale)
    decode_hashes = []
    for step in range(DECODE_STEPS):
        position = length + step
        write_cache(
            k[position : position + 1],
            v[position : position + 1],
            kc,
            vc,
            torch.tensor([position], dtype=torch.long, device=device),
            scale,
        )
        q_step = fixed_randn((1, Q_HEADS, HEAD_DIM), 4000 + length * 100 + step).to(device)
        output = attention(q_step, kc, vc, position + 1, block_table, cu_decode, scale)
        torch.xpu.synchronize()
        decode_hashes.append(digest(output))

    result = {
        "length": length,
        "prefill_cache_hashes": sorted(set(prefill_caches)),
        "prefill_output_hashes": sorted(set(prefill_outputs)),
        "decode_trajectory_sha256": hashlib.sha256("".join(decode_hashes).encode()).hexdigest(),
        "final_cache_sha256": digest(kc, vc),
        "input_sha256": digest(q, k, v),
    }
    del q, k, v, kc, vc
    torch.xpu.empty_cache()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    device = "xpu:0"
    torch.xpu.set_device(device)
    cases = [run_case(length, device) for length in LENGTHS]
    value = {
        "schema": "neural.download.qwen38-paged-fa2-cross-process.raw.v1",
        "device": torch.xpu.get_device_name(0),
        "torch": torch.__version__,
        "dimensions": {"q_heads": Q_HEADS, "kv_heads": KV_HEADS, "head_dim": HEAD_DIM, "block_size": BLOCK_SIZE},
        "decode_steps": DECODE_STEPS,
        "cases": cases,
    }
    Path(args.out).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
