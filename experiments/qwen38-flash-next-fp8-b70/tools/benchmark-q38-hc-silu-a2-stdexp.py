#!/usr/bin/env python3
"""A2 correction gate layered on the frozen Qwen HC-SiLU A1 gate."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import torch


A1_GATE = Path(__file__).with_name("benchmark-q38-hc-silu-a1.py")
FAILED_REGION_START = 0x4100
FAILED_REGION_END = 0x423F
FAILED_REGION_REPEATS = 100


def load_a1():
    spec = importlib.util.spec_from_file_location("q38_hc_silu_a1", A1_GATE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load frozen A1 gate: {A1_GATE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


A1 = load_a1()
ORIGINAL_EXHAUSTIVE = A1.exhaustive_bf16_gate


def require_failed_region_parity(
    reference: torch.Tensor,
    candidate: torch.Tensor,
    raw_inputs: torch.Tensor,
) -> dict[str, int]:
    reference_bits = A1.tensor_bits(reference).flatten()
    candidate_bits = A1.tensor_bits(candidate).flatten()
    raw_bits = raw_inputs.flatten().to(torch.int32)
    if (
        reference_bits.shape != candidate_bits.shape
        or raw_bits.shape != reference_bits.shape
    ):
        A1.fail("failed-region: input/output shapes differ")
    reference_nan = A1.is_nan_bits(reference_bits)
    candidate_nan = A1.is_nan_bits(candidate_bits)
    nan_class_mismatch = reference_nan != candidate_nan
    value_mismatch = (~reference_nan) & (reference_bits != candidate_bits)
    mismatch = nan_class_mismatch | value_mismatch
    if mismatch.any():
        first = int(torch.nonzero(mismatch, as_tuple=False)[0].item())
        A1.fail(
            "failed-region mismatch: "
            f"input_bits=0x{int(raw_bits[first].item()):04x} "
            f"reference_bits=0x{int(reference_bits[first].item()):04x} "
            f"candidate_bits=0x{int(candidate_bits[first].item()):04x} "
            f"reference_nan={bool(reference_nan[first].item())} "
            f"candidate_nan={bool(candidate_nan[first].item())}"
        )
    return {
        "elements": int(reference_bits.numel()),
        "exact_non_nan": int((~reference_nan).sum().item()),
        "nan_class_only": int(reference_nan.sum().item()),
    }


def corrected_exhaustive(hc_module, device: torch.device) -> dict[str, object]:
    raw = torch.arange(
        FAILED_REGION_START, FAILED_REGION_END + 1, dtype=torch.int32
    ).to(torch.uint16)
    values = raw.view(torch.bfloat16)
    x = A1.production_input(values, device)
    input_before = A1.tensor_hash(x)
    reference = hc_module._hc_silu_torch(x, A1.HC_COUNT)
    A1.set_candidate(True)
    candidate = hc_module._hc_silu(x, A1.HC_COUNT)
    torch.xpu.synchronize(device)
    parity = require_failed_region_parity(reference, candidate, raw)
    reference_hash = A1.tensor_hash(reference)
    repeat_hashes = []
    for _ in range(FAILED_REGION_REPEATS):
        repeat_hashes.append(A1.tensor_hash(hc_module._hc_silu(x, A1.HC_COUNT)))
    torch.xpu.synchronize(device)
    if set(repeat_hashes) != {reference_hash}:
        A1.fail(
            "failed-region repeats differ from reference: "
            f"reference={reference_hash}, candidates={sorted(set(repeat_hashes))}"
        )
    if A1.tensor_hash(x) != input_before:
        A1.fail("failed-region calls mutated the production-stride input")
    full = ORIGINAL_EXHAUSTIVE(hc_module, device)
    return {
        "failed_region_precheck": {
            "raw_input_start_hex": f"0x{FAILED_REGION_START:04x}",
            "raw_input_end_hex": f"0x{FAILED_REGION_END:04x}",
            "production_stride": list(x.stride()),
            "repeat_count": len(repeat_hashes),
            "repeat_unique_sha256": sorted(set(repeat_hashes)),
            "reference_sha256": reference_hash,
            "input_sha256": input_before,
            **parity,
        },
        **full,
    }


A1.exhaustive_bf16_gate = corrected_exhaustive


if __name__ == "__main__":
    A1.main()
