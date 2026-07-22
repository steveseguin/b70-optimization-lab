#!/usr/bin/env python3
"""Gate Laguna's exact TP4 paged-decode specialization on one visible XPU."""

from __future__ import annotations

import argparse
import hashlib
import json
import math

import torch

import vllm_xpu_kernels.flash_attn_interface as fa


def reference(
    query: torch.Tensor,
    key_cache: torch.Tensor,
    value_cache: torch.Tensor,
    kv_len: int,
) -> torch.Tensor:
    """Independent CPU FP32 reference for one contiguous paged sequence."""
    q = query.cpu().float() * (query.shape[-1]**-0.5)
    k = key_cache.cpu().float().reshape(-1, 2, 128)[:kv_len]
    v = value_cache.cpu().float().reshape(-1, 2, 128)[:kv_len]
    k = torch.repeat_interleave(k, 9, dim=1)
    v = torch.repeat_interleave(v, 9, dim=1)
    scores = torch.einsum("qhd,khd->hqk", q, k)
    probs = torch.softmax(scores, dim=-1)
    return torch.einsum("hqk,khd->qhd", probs, v).to(torch.bfloat16)


def run_case(seed: int, kv_len: int) -> tuple[torch.Tensor, dict[str, object]]:
    torch.manual_seed(seed)
    query = torch.randn((1, 18, 128), dtype=torch.bfloat16, device="xpu:0")
    key_cache = torch.randn(
        (3, 64, 2, 128), dtype=torch.bfloat16, device="xpu:0"
    )
    value_cache = torch.randn_like(key_cache)
    cu_query_lens = torch.tensor([0, 1], dtype=torch.int32, device="xpu:0")
    seq_k = torch.tensor([kv_len], dtype=torch.int32, device="xpu:0")
    block_table = torch.tensor([[0, 1, 2]], dtype=torch.int32, device="xpu:0")

    expected = reference(query, key_cache, value_cache, kv_len)
    actual = fa.flash_attn_varlen_func(
        query,
        key_cache,
        value_cache,
        1,
        cu_query_lens,
        kv_len,
        seqused_k=seq_k,
        softmax_scale=1 / math.sqrt(128),
        causal=False,
        block_table=block_table,
        window_size=(511, 0),
        fa_version=2,
    )
    actual_cpu = actual.cpu()
    torch.testing.assert_close(actual_cpu, expected, atol=1e-2, rtol=1e-2)
    delta = (actual_cpu.float() - expected.float()).abs()
    digest = hashlib.sha256(actual_cpu.view(torch.uint8).numpy().tobytes()).hexdigest()
    return actual_cpu, {
        "seed": seed,
        "kv_len": kv_len,
        "output_sha256": digest,
        "max_abs_error": float(delta.max()),
        "mean_abs_error": float(delta.mean()),
        "finite": bool(torch.isfinite(actual_cpu).all()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--physical-card", type=int, required=True)
    args = parser.parse_args()

    if not torch.xpu.is_available() or torch.xpu.device_count() != 1:
        raise RuntimeError(
            "Gate requires exactly one visible XPU; "
            f"got available={torch.xpu.is_available()} count={torch.xpu.device_count()}"
        )
    torch.xpu.set_device(0)

    def forbid_fallback(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("compiled paged-decode kernel was not selected")

    fa._fallback_varlen_attn = forbid_fallback
    first, first_result = run_case(21000 + args.physical_card, 37)
    second, second_result = run_case(22000 + args.physical_card, 129)
    if torch.equal(first, second):
        raise AssertionError("changed inputs produced identical outputs")

    print(
        json.dumps(
            {
                "status": "PASS",
                "physical_card": args.physical_card,
                "visible_xpus": torch.xpu.device_count(),
                "device_name": torch.xpu.get_device_name(0),
                "tuple": "16,128,64,false,true,false",
                "changed_output": True,
                "cases": [first_result, second_result],
                "extension": getattr(fa._vllm_fa2_C, "__file__", None),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
