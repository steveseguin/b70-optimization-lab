#!/usr/bin/env python3
"""Raw-exactness and timing gate for Laguna M12 paged attention blocks."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import time
from pathlib import Path

import torch

from vllm_xpu_kernels.flash_attn_interface import flash_attn_varlen_func


PROMPT_TOKENS = (90, 132, 110, 102, 112, 89, 149, 111, 125, 140, 229, 112, 863)
OFFSETS = (0, 33, 66, 99)
Q_WIDTH = 12
Q_HEADS = 12
KV_HEADS = 2
HEAD_DIM = 128


def tensor_hash(tensor: torch.Tensor) -> str:
    raw = tensor.cpu().contiguous().view(torch.uint8).numpy().tobytes()
    return hashlib.sha256(raw).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pack_cache(logical: torch.Tensor, block_size: int) -> torch.Tensor:
    blocks = (logical.shape[0] + block_size - 1) // block_size
    cache = torch.zeros(
        (blocks, block_size, KV_HEADS, HEAD_DIM),
        dtype=logical.dtype,
        device=logical.device,
    )
    cache.view(-1, KV_HEADS, HEAD_DIM)[: logical.shape[0]].copy_(logical)
    return cache


def run_attention(
    query: torch.Tensor,
    key: torch.Tensor,
    value: torch.Tensor,
    context: int,
    block_size: int,
    local: bool,
    out: torch.Tensor,
) -> torch.Tensor:
    assert key.shape[1] == block_size
    assert value.shape[1] == block_size
    blocks = key.shape[0]
    cu_q = torch.arange(Q_WIDTH + 1, dtype=torch.int32, device=query.device)
    seq_k = context + torch.arange(
        1, Q_WIDTH + 1, dtype=torch.int32, device=query.device
    )
    block_table = (
        torch.arange(blocks, dtype=torch.int32, device=query.device)
        .unsqueeze(0)
        .expand(Q_WIDTH, -1)
        .contiguous()
    )
    flash_attn_varlen_func(
        q=query,
        k=key,
        v=value,
        out=out,
        cu_seqlens_q=cu_q,
        max_seqlen_q=1,
        seqused_k=seq_k,
        max_seqlen_k=context + Q_WIDTH,
        softmax_scale=HEAD_DIM**-0.5,
        causal=False,
        window_size=(511, 0) if local else (-1, -1),
        block_table=block_table,
        fa_version=2,
    )
    return out


def timed_ms(call, iterations: int) -> float:
    for _ in range(5):
        call()
    torch.xpu.synchronize()
    started = time.perf_counter()
    for _ in range(iterations):
        call()
    torch.xpu.synchronize()
    return (time.perf_counter() - started) * 1000.0 / iterations


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rank", type=int, required=True, choices=range(4))
    parser.add_argument("--seeds", type=int, default=2)
    parser.add_argument("--timing-iterations", type=int, default=20)
    parser.add_argument("--minimum-projected-saving-ms", type=float, default=1.13)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    torch.xpu.set_device(0)
    contexts = tuple(prompt + offset for prompt in PROMPT_TOKENS for offset in OFFSETS)
    results: list[dict[str, object]] = []
    exact = 0
    total = 0

    for local in (False, True):
        for case_index, context in enumerate(contexts):
            timings_64: list[float] = []
            timings_32: list[float] = []
            last_hash = ""
            case_exact = True
            for seed_index in range(args.seeds):
                torch.manual_seed(
                    73100
                    + args.rank * 100_000
                    + int(local) * 10_000
                    + case_index * 10
                    + seed_index
                )
                max_len = context + Q_WIDTH
                query = torch.randn(
                    (Q_WIDTH, Q_HEADS, HEAD_DIM),
                    dtype=torch.bfloat16,
                    device="xpu",
                )
                logical_k = torch.randn(
                    (max_len, KV_HEADS, HEAD_DIM),
                    dtype=torch.bfloat16,
                    device="xpu",
                )
                logical_v = torch.randn_like(logical_k)
                key64 = pack_cache(logical_k, 64)
                value64 = pack_cache(logical_v, 64)
                key32 = pack_cache(logical_k, 32)
                value32 = pack_cache(logical_v, 32)
                out64 = torch.empty_like(query)
                out32 = torch.empty_like(query)

                run_attention(query, key64, value64, context, 64, local, out64)
                run_attention(query, key32, value32, context, 32, local, out32)
                torch.xpu.synchronize()
                equal = torch.equal(out64, out32)
                exact += int(equal)
                total += 1
                case_exact = case_exact and equal
                last_hash = tensor_hash(out32)

                if seed_index == 0:
                    calls = (
                        (
                            lambda: run_attention(
                                query, key64, value64, context, 64, local, out64
                            ),
                            lambda: run_attention(
                                query, key32, value32, context, 32, local, out32
                            ),
                        )
                        if case_index % 2 == 0
                        else (
                            lambda: run_attention(
                                query, key32, value32, context, 32, local, out32
                            ),
                            lambda: run_attention(
                                query, key64, value64, context, 64, local, out64
                            ),
                        )
                    )
                    first = timed_ms(calls[0], args.timing_iterations)
                    second = timed_ms(calls[1], args.timing_iterations)
                    if case_index % 2 == 0:
                        timings_64.append(first)
                        timings_32.append(second)
                    else:
                        timings_32.append(first)
                        timings_64.append(second)

            results.append(
                {
                    "attention": "sliding" if local else "full",
                    "context": context,
                    "exact": case_exact,
                    "page64_ms": sum(timings_64) / len(timings_64),
                    "page32_ms": sum(timings_32) / len(timings_32),
                    "last_page32_hash": last_hash,
                }
            )

    torch.xpu.synchronize()
    full = [row for row in results if row["attention"] == "full"]
    sliding = [row for row in results if row["attention"] == "sliding"]
    full64 = sum(float(row["page64_ms"]) for row in full) / len(full)
    full32 = sum(float(row["page32_ms"]) for row in full) / len(full)
    sliding64 = sum(float(row["page64_ms"]) for row in sliding) / len(sliding)
    sliding32 = sum(float(row["page32_ms"]) for row in sliding) / len(sliding)
    projected64 = 12 * full64 + 36 * sliding64
    projected32 = 12 * full32 + 36 * sliding32
    saving = projected64 - projected32
    passed = exact == total and saving >= args.minimum_projected_saving_ms
    fa2_module = Path(
        importlib.import_module("vllm_xpu_kernels._vllm_fa2_C").__file__
    ).resolve()
    mapped_attn = sorted(
        {
            Path(line.rsplit(maxsplit=1)[-1]).resolve()
            for line in Path("/proc/self/maps").read_text().splitlines()
            if "libattn_kernels_xe_2.so" in line
        }
    )
    payload = {
        "schema": "laguna-exact-attn-page-size-component-v1",
        "rank": args.rank,
        "device": torch.xpu.get_device_name(0),
        "contexts": list(contexts),
        "seeds": args.seeds,
        "exact": f"{exact}/{total}",
        "raw_exact_passed": exact == total,
        "full_page64_mean_ms": full64,
        "full_page32_mean_ms": full32,
        "sliding_page64_mean_ms": sliding64,
        "sliding_page32_mean_ms": sliding32,
        "projected_page64_ms": projected64,
        "projected_page32_ms": projected32,
        "projected_saving_ms": saving,
        "minimum_projected_saving_ms": args.minimum_projected_saving_ms,
        "status": "PASS" if passed else "STOP",
        "native": {
            "fa2_module": str(fa2_module),
            "fa2_sha256": file_hash(fa2_module),
            "mapped_attn_libraries": [
                {"path": str(path), "sha256": file_hash(path)} for path in mapped_attn
            ],
        },
        "cases": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
