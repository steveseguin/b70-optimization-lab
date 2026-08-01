#!/usr/bin/env python3
"""One-card component gate for the Laguna DFlash FP8 draft LM head."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path

import torch
import torch.nn.functional as F
from safetensors import safe_open

from vllm.model_executor.models.laguna_dflash import (
    _LAGUNA_DFLASH_FP8_LM_HEAD_SHAPE,
    _LagunaDFlashFP8LMHead,
    _quantize_laguna_dflash_weight,
)


ROWS = 11
HIDDEN = 3072
LOCAL_VOCAB = 25088
SEEDS = 8
WARMUP = 20
TIMING_BLOCKS = 21
CALLS_PER_BLOCK = 20


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_rank0_weight(shard: Path) -> torch.Tensor:
    with safe_open(shard, framework="pt", device="cpu") as handle:
        weight_slice = handle.get_slice("lm_head.weight")
        shape = tuple(weight_slice.get_shape())
        if shape != (LOCAL_VOCAB * 4, HIDDEN):
            raise RuntimeError(f"unexpected full LM-head shape: {shape}")
        weight = weight_slice[:LOCAL_VOCAB, :]
    if weight.dtype != torch.bfloat16 or not weight.is_contiguous():
        weight = weight.to(torch.bfloat16).contiguous()
    return weight


def make_hidden(seed: int) -> torch.Tensor:
    generator = torch.Generator(device="cpu").manual_seed(0xDFA5000 + seed)
    return (
        torch.randn((ROWS, HIDDEN), generator=generator, dtype=torch.float32)
        .mul_(0.25)
        .to(torch.bfloat16)
        .xpu()
    )


def event_block(callable_fn) -> float:
    start = torch.xpu.Event(enable_timing=True)
    end = torch.xpu.Event(enable_timing=True)
    start.record()
    for _ in range(CALLS_PER_BLOCK):
        callable_fn()
    end.record()
    torch.xpu.synchronize()
    return float(start.elapsed_time(end)) / CALLS_PER_BLOCK


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-shard", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.model_shard.is_file():
        raise SystemExit(f"missing model shard: {args.model_shard}")
    if not torch.xpu.is_available():
        raise SystemExit("XPU is unavailable")
    if _LAGUNA_DFLASH_FP8_LM_HEAD_SHAPE != (LOCAL_VOCAB, HIDDEN):
        raise SystemExit(
            "source LM-head contract drifted: "
            f"{_LAGUNA_DFLASH_FP8_LM_HEAD_SHAPE}"
        )

    weight_cpu = load_rank0_weight(args.model_shard)
    source_digest = hashlib.sha256(weight_cpu.view(torch.uint8).numpy()).hexdigest()
    weight = weight_cpu.xpu()
    source_ptr = weight.data_ptr()
    source_copy = weight.clone()
    quantized_t, scale = _quantize_laguna_dflash_weight(
        weight,
        expected_shape=(LOCAL_VOCAB, HIDDEN),
        label="component_draft_lm_head",
    )
    head = _LagunaDFlashFP8LMHead(quantized_t, scale).xpu()
    torch.xpu.synchronize()
    source_unchanged = torch.equal(weight, source_copy)
    non_aliasing = (
        source_ptr == weight.data_ptr()
        and source_ptr != head.weight.data_ptr()
        and source_ptr != head.weight_scale.data_ptr()
    )

    cases = []
    all_finite = True
    local_top1_equal = 0
    compared_rows = 0
    for seed in range(SEEDS):
        hidden = make_hidden(seed)
        incumbent = F.linear(hidden, weight)
        candidate = head.quant_method.apply(head, hidden)
        torch.xpu.synchronize()
        finite = bool(torch.isfinite(candidate).all().item())
        equal = incumbent.argmax(dim=-1) == candidate.argmax(dim=-1)
        equal_count = int(equal.sum().item())
        local_top1_equal += equal_count
        compared_rows += ROWS
        all_finite = all_finite and finite
        cases.append(
            {
                "seed": seed,
                "finite": finite,
                "local_top1_equal": equal_count,
                "rows": ROWS,
                "incumbent_abs_mean": float(incumbent.float().abs().mean().item()),
                "candidate_abs_mean": float(candidate.float().abs().mean().item()),
                "mean_abs_error": float(
                    (candidate.float() - incumbent.float()).abs().mean().item()
                ),
            }
        )

    hidden = make_hidden(0x51)
    out_incumbent = None
    out_candidate = None
    for _ in range(WARMUP):
        out_incumbent = F.linear(hidden, weight)
        out_candidate = head.quant_method.apply(head, hidden)
    torch.xpu.synchronize()
    incumbent_blocks = []
    candidate_blocks = []
    for block in range(TIMING_BLOCKS):
        if block % 2 == 0:
            incumbent_blocks.append(event_block(lambda: F.linear(hidden, weight)))
            candidate_blocks.append(
                event_block(lambda: head.quant_method.apply(head, hidden))
            )
        else:
            candidate_blocks.append(
                event_block(lambda: head.quant_method.apply(head, hidden))
            )
            incumbent_blocks.append(event_block(lambda: F.linear(hidden, weight)))
    incumbent_median = statistics.median(incumbent_blocks)
    candidate_median = statistics.median(candidate_blocks)
    saved_ms = incumbent_median - candidate_median
    speedup = incumbent_median / candidate_median
    materially_faster = candidate_median < incumbent_median * 0.90 and saved_ms > 0.05

    passed = (
        source_unchanged
        and non_aliasing
        and all_finite
        and tuple(out_incumbent.shape) == (ROWS, LOCAL_VOCAB)
        and tuple(out_candidate.shape) == (ROWS, LOCAL_VOCAB)
        and out_incumbent.dtype == torch.bfloat16
        and out_candidate.dtype == torch.bfloat16
        and materially_faster
    )
    report = {
        "schema": "laguna-dflash-fp8-lm-head-component-v1",
        "model_shard": str(args.model_shard.resolve()),
        "model_shard_sha256": sha256(args.model_shard),
        "rank0_weight_sha256": source_digest,
        "torch_version": torch.__version__,
        "device": torch.xpu.get_device_name(0),
        "rows": ROWS,
        "weight_shape": list(weight.shape),
        "fp8_weight_shape": list(head.weight.shape),
        "scale_shape": list(head.weight_scale.shape),
        "source_unchanged": source_unchanged,
        "non_aliasing": non_aliasing,
        "all_candidate_outputs_finite": all_finite,
        "local_top1_agreement": {
            "equal": local_top1_equal,
            "rows": compared_rows,
            "fraction": local_top1_equal / compared_rows,
            "note": "rank-0 local-vocabulary agreement only; endpoint target verification is authoritative",
        },
        "cases": cases,
        "timing": {
            "warmup_calls_per_arm": WARMUP,
            "blocks": TIMING_BLOCKS,
            "calls_per_block": CALLS_PER_BLOCK,
            "incumbent_blocks_ms_per_call": incumbent_blocks,
            "candidate_blocks_ms_per_call": candidate_blocks,
            "incumbent_median_ms": incumbent_median,
            "candidate_median_ms": candidate_median,
            "saved_ms": saved_ms,
            "speedup": speedup,
            "material_gate": "candidate < 0.90 * incumbent and saved_ms > 0.05",
            "materially_faster": materially_faster,
        },
        "passed": passed,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "source_unchanged": source_unchanged,
                "non_aliasing": non_aliasing,
                "all_candidate_outputs_finite": all_finite,
                "local_top1_agreement": report["local_top1_agreement"],
                "timing": report["timing"],
                "passed": passed,
            },
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
