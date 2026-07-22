#!/usr/bin/env python3
"""Gate every Laguna TP4 FlashAttention tuple on one visible XPU."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass

import torch

import vllm_xpu_kernels.flash_attn_interface as fa


@dataclass(frozen=True)
class Case:
    phase: str
    sliding: bool
    query_len: int
    kv_len: int
    seed_offset: int

    @property
    def query_heads(self) -> int:
        return 18 if self.sliding else 12

    @property
    def tuple_string(self) -> str:
        if self.phase == "decode":
            qgroup = 16 if self.sliding else 8
            return (
                f"{qgroup},128,64,false,"
                f"{'true' if self.sliding else 'false'},false"
            )
        return (
            "128,true,"
            f"{'false,true' if self.sliding else 'true,false'},false,false"
        )


CASES = (
    Case("prefill", False, 64, 64, 0),
    Case("prefill", True, 64, 64, 1),
    Case("chunk_prefill", False, 13, 577, 2),
    Case("chunk_prefill", True, 13, 577, 3),
    Case("decode", False, 1, 129, 4),
    Case("decode", True, 1, 577, 5),
)


def reference(
    query: torch.Tensor,
    key_cache: torch.Tensor,
    value_cache: torch.Tensor,
    *,
    query_len: int,
    kv_len: int,
    sliding: bool,
    causal: bool,
) -> torch.Tensor:
    """Independent CPU FP32 bottom-right-aligned GQA reference."""
    q = query.cpu().float() * (query.shape[-1] ** -0.5)
    k = key_cache.cpu().float().reshape(-1, 2, 128)[:kv_len]
    v = value_cache.cpu().float().reshape(-1, 2, 128)[:kv_len]
    repeats = query.shape[1] // 2
    k = torch.repeat_interleave(k, repeats, dim=1)
    v = torch.repeat_interleave(v, repeats, dim=1)
    scores = torch.einsum("qhd,khd->hqk", q, k)

    q_positions = torch.arange(query_len) + kv_len - query_len
    k_positions = torch.arange(kv_len)
    valid = torch.ones((query_len, kv_len), dtype=torch.bool)
    if causal:
        valid &= k_positions[None, :] <= q_positions[:, None]
    if sliding:
        valid &= k_positions[None, :] >= q_positions[:, None] - 511
        valid &= k_positions[None, :] <= q_positions[:, None]
    scores.masked_fill_(~valid[None, :, :], float("-inf"))
    probs = torch.softmax(scores, dim=-1)
    return torch.einsum("hqk,khd->qhd", probs, v).to(torch.bfloat16)


def run_case(case: Case, seed: int) -> tuple[torch.Tensor, dict[str, object]]:
    torch.manual_seed(seed)
    num_pages = math.ceil(case.kv_len / 64)
    query = torch.randn(
        (case.query_len, case.query_heads, 128),
        dtype=torch.bfloat16,
        device="xpu:0",
    )
    key_cache = torch.randn(
        (num_pages, 64, 2, 128), dtype=torch.bfloat16, device="xpu:0"
    )
    value_cache = torch.randn_like(key_cache)
    cu_query_lens = torch.tensor(
        [0, case.query_len], dtype=torch.int32, device="xpu:0"
    )
    seq_k = torch.tensor([case.kv_len], dtype=torch.int32, device="xpu:0")
    block_table = torch.arange(
        num_pages, dtype=torch.int32, device="xpu:0"
    ).unsqueeze(0)

    causal = case.phase != "decode"
    expected = reference(
        query,
        key_cache,
        value_cache,
        query_len=case.query_len,
        kv_len=case.kv_len,
        sliding=case.sliding,
        causal=causal,
    )
    actual = fa.flash_attn_varlen_func(
        query,
        key_cache,
        value_cache,
        case.query_len,
        cu_query_lens,
        case.kv_len,
        seqused_k=seq_k,
        softmax_scale=1 / math.sqrt(128),
        causal=causal,
        block_table=block_table,
        window_size=(511, 0) if case.sliding else None,
        fa_version=2,
    )
    actual_cpu = actual.cpu()
    torch.testing.assert_close(actual_cpu, expected, atol=1e-2, rtol=1e-2)
    delta = (actual_cpu.float() - expected.float()).abs()
    digest = hashlib.sha256(actual_cpu.view(torch.uint8).numpy().tobytes()).hexdigest()
    return actual_cpu, {
        "phase": case.phase,
        "attention": "sliding" if case.sliding else "full",
        "tuple": case.tuple_string,
        "seed": seed,
        "query_len": case.query_len,
        "kv_len": case.kv_len,
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
        raise AssertionError("compiled Laguna attention kernel was not selected")

    fa._fallback_varlen_attn = forbid_fallback
    rows = []
    outputs = []
    for case in CASES:
        output, row = run_case(case, 31000 + 100 * args.physical_card + case.seed_offset)
        outputs.append(output)
        rows.append(row)
    if len({row["output_sha256"] for row in rows}) != len(rows):
        raise AssertionError("changed cases produced duplicate output hashes")

    print(
        json.dumps(
            {
                "status": "PASS",
                "physical_card": args.physical_card,
                "visible_xpus": torch.xpu.device_count(),
                "device_name": torch.xpu.get_device_name(0),
                "unique_tuples": sorted({case.tuple_string for case in CASES}),
                "cases": rows,
                "extension": getattr(fa._vllm_fa2_C, "__file__", None),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
