#!/usr/bin/env python3
"""Exactness and core-timing gate for Laguna paired-row M12 attention."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import time
from pathlib import Path
from typing import Callable

import torch


PROMPT_TOKENS = (90, 132, 110, 102, 112, 89, 149, 111, 125, 140, 229, 112, 863)
OFFSETS = (0, 33, 66, 99)
SHORT_RECORD_CONTEXTS = tuple(
    prompt + offset for prompt in PROMPT_TOKENS for offset in OFFSETS
)
LONG_FULL_CONTEXTS = (8192, 16384, 24576, 32640)
Q_WIDTH = 12
Q_HEADS = 12
PACKED_BATCH = 6
PACKED_Q_HEADS = 24
KV_HEADS = 2
HEAD_DIM = 128
BLOCK_SIZE = 64
SELECTOR = "VLLM_XPU_LAGUNA_M12_PAIR_ATTN"


def profile_contract(name: str) -> dict[str, object]:
    if name == "short-record":
        return {
            "contexts": SHORT_RECORD_CONTEXTS,
            "attention_modes": (False, True),
            "full_layers": 12,
            "sliding_layers": 36,
            "minimum_projected_saving_ms": 1.5,
        }
    if name == "long-full":
        return {
            "contexts": LONG_FULL_CONTEXTS,
            "attention_modes": (False,),
            "full_layers": 12,
            "sliding_layers": 0,
            "minimum_projected_saving_ms": 0.25,
        }
    raise ValueError(f"unsupported paired-attention profile: {name}")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tensor_hash(tensor: torch.Tensor) -> str:
    raw = tensor.cpu().contiguous().view(torch.uint8).numpy().tobytes()
    return hashlib.sha256(raw).hexdigest()


def pack_query(query: torch.Tensor) -> torch.Tensor:
    if tuple(query.shape) != (Q_WIDTH, Q_HEADS, HEAD_DIM):
        raise ValueError(f"unexpected query shape: {tuple(query.shape)}")
    # [pair, temporal, kv, q-within-kv, d] ->
    # [pair, kv, temporal, q-within-kv, d].  Each physical KV group then
    # contains the earlier row's six heads followed by the later row's six.
    return (
        query.view(PACKED_BATCH, 2, KV_HEADS, Q_HEADS // KV_HEADS, HEAD_DIM)
        .permute(0, 2, 1, 3, 4)
        .reshape(PACKED_BATCH, PACKED_Q_HEADS, HEAD_DIM)
        .contiguous()
    )


def unpack_output(packed: torch.Tensor) -> torch.Tensor:
    if tuple(packed.shape) != (PACKED_BATCH, PACKED_Q_HEADS, HEAD_DIM):
        raise ValueError(f"unexpected packed output shape: {tuple(packed.shape)}")
    return (
        packed.view(PACKED_BATCH, KV_HEADS, 2, Q_HEADS // KV_HEADS, HEAD_DIM)
        .permute(0, 2, 1, 3, 4)
        .reshape(Q_WIDTH, Q_HEADS, HEAD_DIM)
        .contiguous()
    )


def host_contract_checks(
    contexts: tuple[int, ...] = SHORT_RECORD_CONTEXTS,
) -> dict[str, object]:
    marker = torch.arange(Q_WIDTH * Q_HEADS * HEAD_DIM, dtype=torch.int64).view(
        Q_WIDTH, Q_HEADS, HEAD_DIM
    )
    packed = pack_query(marker)
    restored = unpack_output(packed)
    if not torch.equal(marker, restored):
        raise AssertionError("pair layout is not invertible")

    for pair in range(PACKED_BATCH):
        for kv_head in range(KV_HEADS):
            source = marker[
                2 * pair : 2 * pair + 2,
                kv_head * 6 : (kv_head + 1) * 6,
            ].reshape(12, HEAD_DIM)
            physical = packed[pair, kv_head * 12 : (kv_head + 1) * 12]
            if not torch.equal(source, physical):
                raise AssertionError(
                    f"wrong physical layout for pair={pair}, kv={kv_head}"
                )

    for context in contexts:
        ordinary = context + torch.arange(1, Q_WIDTH + 1, dtype=torch.int32)
        paired = context + torch.arange(2, Q_WIDTH + 1, 2, dtype=torch.int32)
        if not torch.equal(paired, ordinary[1::2]):
            raise AssertionError(f"wrong paired staircase for context={context}")
        if not torch.equal(paired - 1, ordinary[0::2]):
            raise AssertionError(f"wrong earlier-row staircase for context={context}")

    return {
        "layout_roundtrip": True,
        "physical_kv_group_order": True,
        "paired_staircase": True,
        "contexts": len(contexts),
        "minimum_context": min(contexts),
        "maximum_context": max(contexts),
    }


def pack_cache(logical: torch.Tensor) -> torch.Tensor:
    blocks = (logical.shape[0] + BLOCK_SIZE - 1) // BLOCK_SIZE
    cache = torch.zeros(
        (blocks, BLOCK_SIZE, KV_HEADS, HEAD_DIM),
        dtype=logical.dtype,
        device=logical.device,
    )
    cache.view(-1, KV_HEADS, HEAD_DIM)[: logical.shape[0]].copy_(logical)
    return cache


def metadata(
    *, context: int, blocks: int, paired: bool, device: torch.device
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    batch = PACKED_BATCH if paired else Q_WIDTH
    cu_q = torch.arange(batch + 1, dtype=torch.int32, device=device)
    if paired:
        seq_k = context + torch.arange(
            2, Q_WIDTH + 1, 2, dtype=torch.int32, device=device
        )
    else:
        seq_k = context + torch.arange(1, Q_WIDTH + 1, dtype=torch.int32, device=device)
    block_table = (
        torch.arange(blocks, dtype=torch.int32, device=device)
        .unsqueeze(0)
        .expand(batch, -1)
        .contiguous()
    )
    return cu_q, seq_k, block_table


def attention_call(
    flash_attn_varlen_func: Callable[..., object],
    *,
    query: torch.Tensor,
    key: torch.Tensor,
    value: torch.Tensor,
    out: torch.Tensor,
    context: int,
    local: bool,
    paired: bool,
    cu_q: torch.Tensor,
    seq_k: torch.Tensor,
    block_table: torch.Tensor,
) -> torch.Tensor:
    expected_batch = PACKED_BATCH if paired else Q_WIDTH
    if query.shape[0] != expected_batch:
        raise AssertionError("query and metadata batch disagree")
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


def timed_ms(call: Callable[[], object], selector: str, iterations: int) -> float:
    os.environ[SELECTOR] = selector
    for _ in range(5):
        call()
    torch.xpu.synchronize()
    started = time.perf_counter()
    for _ in range(iterations):
        call()
    torch.xpu.synchronize()
    return (time.perf_counter() - started) * 1000.0 / iterations


def expected_failure(call: Callable[[], object], selector: str) -> str:
    os.environ[SELECTOR] = selector
    try:
        call()
        torch.xpu.synchronize()
    except Exception as exc:  # The native binding raises RuntimeError.
        return f"{type(exc).__name__}: {exc}"
    raise AssertionError(f"selector={selector!r} unexpectedly accepted invalid call")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rank", type=int, required=True, choices=range(4))
    parser.add_argument(
        "--profile",
        choices=("short-record", "long-full"),
        default="short-record",
    )
    parser.add_argument("--seeds", type=int, default=2)
    parser.add_argument("--timing-iterations", type=int, default=20)
    parser.add_argument("--minimum-projected-saving-ms", type=float)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--host-only", action="store_true")
    args = parser.parse_args()

    profile = profile_contract(args.profile)
    contexts = profile["contexts"]
    attention_modes = profile["attention_modes"]
    full_layers = int(profile["full_layers"])
    sliding_layers = int(profile["sliding_layers"])
    minimum_projected_saving_ms = (
        float(args.minimum_projected_saving_ms)
        if args.minimum_projected_saving_ms is not None
        else float(profile["minimum_projected_saving_ms"])
    )
    assert isinstance(contexts, tuple)
    assert isinstance(attention_modes, tuple)
    host_checks = host_contract_checks(contexts)
    if args.host_only:
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "profile": args.profile,
                    "host_checks": host_checks,
                },
                indent=2,
            )
        )
        return

    from vllm_xpu_kernels.flash_attn_interface import flash_attn_varlen_func

    if os.environ.get("ONEAPI_DEVICE_SELECTOR") != "level_zero:*":
        raise SystemExit("requires ONEAPI_DEVICE_SELECTOR=level_zero:*")
    if os.environ.get("ZE_AFFINITY_MASK") != str(args.rank):
        raise SystemExit("ZE_AFFINITY_MASK must equal --rank")
    if torch.xpu.device_count() != 1:
        raise SystemExit(
            f"expected exactly one visible XPU, saw {torch.xpu.device_count()}"
        )
    torch.xpu.set_device(0)
    device = torch.device("xpu", 0)
    cases: list[dict[str, object]] = []
    exact = 0
    total = 0
    native_rejections: dict[str, str] = {}

    for local in attention_modes:
        for case_index, context in enumerate(contexts):
            case_exact = True
            control_timings: list[float] = []
            paired_timings: list[float] = []
            output_hash = ""
            for seed_index in range(args.seeds):
                torch.manual_seed(
                    81700
                    + args.rank * 100_000
                    + int(local) * 10_000
                    + case_index * 10
                    + seed_index
                )
                max_len = context + Q_WIDTH
                query = torch.randn(
                    (Q_WIDTH, Q_HEADS, HEAD_DIM), dtype=torch.bfloat16, device=device
                )
                logical_k = torch.randn(
                    (max_len, KV_HEADS, HEAD_DIM), dtype=torch.bfloat16, device=device
                )
                logical_v = torch.randn_like(logical_k)
                key = pack_cache(logical_k)
                value = pack_cache(logical_v)
                packed_query = pack_query(query)
                control_out = torch.empty_like(query)
                packed_out = torch.empty_like(packed_query)
                control_meta = metadata(
                    context=context, blocks=key.shape[0], paired=False, device=device
                )
                paired_meta = metadata(
                    context=context, blocks=key.shape[0], paired=True, device=device
                )

                def control_call() -> torch.Tensor:
                    return attention_call(
                        flash_attn_varlen_func,
                        query=query,
                        key=key,
                        value=value,
                        out=control_out,
                        context=context,
                        local=local,
                        paired=False,
                        cu_q=control_meta[0],
                        seq_k=control_meta[1],
                        block_table=control_meta[2],
                    )

                def paired_call() -> torch.Tensor:
                    return attention_call(
                        flash_attn_varlen_func,
                        query=packed_query,
                        key=key,
                        value=value,
                        out=packed_out,
                        context=context,
                        local=local,
                        paired=True,
                        cu_q=paired_meta[0],
                        seq_k=paired_meta[1],
                        block_table=paired_meta[2],
                    )

                if not native_rejections:
                    native_rejections["invalid_literal"] = expected_failure(
                        control_call, "invalid"
                    )
                    native_rejections["selector_on_control_shape"] = expected_failure(
                        control_call, "1"
                    )

                os.environ[SELECTOR] = "0"
                control_call()
                os.environ[SELECTOR] = "1"
                paired_call()
                torch.xpu.synchronize()
                restored = unpack_output(packed_out)
                equal = torch.equal(control_out, restored)
                exact += int(equal)
                total += 1
                case_exact = case_exact and equal
                output_hash = tensor_hash(restored)

                if seed_index == 0:
                    if case_index % 2 == 0:
                        control_timings.append(
                            timed_ms(control_call, "0", args.timing_iterations)
                        )
                        paired_timings.append(
                            timed_ms(paired_call, "1", args.timing_iterations)
                        )
                    else:
                        paired_timings.append(
                            timed_ms(paired_call, "1", args.timing_iterations)
                        )
                        control_timings.append(
                            timed_ms(control_call, "0", args.timing_iterations)
                        )

            cases.append(
                {
                    "attention": "sliding" if local else "full",
                    "context": context,
                    "exact": case_exact,
                    "control_ms": sum(control_timings) / len(control_timings),
                    "paired_ms": sum(paired_timings) / len(paired_timings),
                    "last_paired_hash": output_hash,
                }
            )

    torch.xpu.synchronize()
    full = [row for row in cases if row["attention"] == "full"]
    sliding = [row for row in cases if row["attention"] == "sliding"]
    full_control = sum(float(row["control_ms"]) for row in full) / len(full)
    full_paired = sum(float(row["paired_ms"]) for row in full) / len(full)
    sliding_control = (
        sum(float(row["control_ms"]) for row in sliding) / len(sliding)
        if sliding
        else 0.0
    )
    sliding_paired = (
        sum(float(row["paired_ms"]) for row in sliding) / len(sliding)
        if sliding
        else 0.0
    )
    projected_control = full_layers * full_control + sliding_layers * sliding_control
    projected_paired = full_layers * full_paired + sliding_layers * sliding_paired
    saving = projected_control - projected_paired
    raw_exact = exact == total
    passed = raw_exact and saving >= minimum_projected_saving_ms

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
        "schema": "laguna-paired-row-attention-component-v2",
        "profile": args.profile,
        "rank": args.rank,
        "device": torch.xpu.get_device_name(0),
        "environment": {
            "ONEAPI_DEVICE_SELECTOR": os.environ.get("ONEAPI_DEVICE_SELECTOR"),
            "ZE_AFFINITY_MASK": os.environ.get("ZE_AFFINITY_MASK"),
            "LD_LIBRARY_PATH": os.environ.get("LD_LIBRARY_PATH"),
        },
        "host_checks": host_checks,
        "native_rejections": native_rejections,
        "contexts": list(contexts),
        "attention_modes": [
            "sliding" if local else "full" for local in attention_modes
        ],
        "projected_layer_counts": {
            "full": full_layers,
            "sliding": sliding_layers,
        },
        "seeds": args.seeds,
        "exact": f"{exact}/{total}",
        "raw_exact_passed": raw_exact,
        "full_control_mean_ms": full_control,
        "full_paired_mean_ms": full_paired,
        "sliding_control_mean_ms": sliding_control,
        "sliding_paired_mean_ms": sliding_paired,
        "projected_control_ms": projected_control,
        "projected_paired_ms": projected_paired,
        "projected_saving_ms": saving,
        "minimum_projected_saving_ms": minimum_projected_saving_ms,
        "timing_includes_pack_unpack": False,
        "status": "PASS" if passed else "STOP",
        "native": {
            "fa2_module": str(fa2_module),
            "fa2_sha256": file_hash(fa2_module),
            "mapped_attn_libraries": [
                {"path": str(path), "sha256": file_hash(path)} for path in mapped_attn
            ],
        },
        "cases": cases,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
