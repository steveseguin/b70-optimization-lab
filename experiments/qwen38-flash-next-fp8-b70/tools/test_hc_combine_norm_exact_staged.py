#!/usr/bin/env python3
"""CPU contracts for the exact staged HC combine+norm candidate."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest
import torch


CORE_PATH = Path(__file__).with_name("hc_combine_norm_exact_staged.py")
SPEC = importlib.util.spec_from_file_location("q38_hc_exact_staged", CORE_PATH)
assert SPEC is not None and SPEC.loader is not None
CORE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CORE)


def _inputs(seed: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    generator = torch.Generator(device="cpu").manual_seed(seed)
    residual = (
        torch.randn(
            (1, CORE.HYPER_HIDDEN_SIZE),
            generator=generator,
            dtype=torch.bfloat16,
        )
        * 0.1
    ).contiguous()
    block = (
        torch.randn((1, CORE.HIDDEN_SIZE), generator=generator, dtype=torch.bfloat16)
        * 0.1
    ).contiguous()
    injection = (
        torch.randn((1, CORE.HC_COUNT), generator=generator, dtype=torch.bfloat16) * 2.0
    ).contiguous()
    return residual, block, injection


def _hash_pair(values: tuple[torch.Tensor, torch.Tensor]) -> str:
    digest = hashlib.sha256()
    for tensor in values:
        digest.update(tensor.contiguous().view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


@pytest.mark.parametrize("seed", [20260826, 20260827, 20260830])
def test_candidate_is_exact_at_production_shape(seed: int) -> None:
    residual, block, injection = _inputs(seed)
    generator = torch.Generator(device="cpu").manual_seed(seed + 100)
    weight = (
        torch.randn(
            (CORE.HYPER_HIDDEN_SIZE,),
            generator=generator,
            dtype=torch.bfloat16,
        )
        * 0.01
    ).contiguous()
    affine = CORE.build_exact_norm_affine(weight)
    CORE.validate_exact_norm_affine(weight, affine)
    authority = CORE.torch_authority_hc_combine_norm(
        residual, block, injection, weight, 1e-6
    )
    candidate = CORE.exact_staged_hc_combine_norm(
        residual, block, injection, affine, 1e-6
    )
    assert torch.equal(candidate[0], authority[0])
    assert torch.equal(candidate[1], authority[1])


def test_one_hundred_changing_inputs_are_exact_and_distinct() -> None:
    weight_generator = torch.Generator(device="cpu").manual_seed(20260901)
    weight = (
        torch.randn(
            (CORE.HYPER_HIDDEN_SIZE,),
            generator=weight_generator,
            dtype=torch.bfloat16,
        )
        * 0.01
    ).contiguous()
    affine = CORE.build_exact_norm_affine(weight)
    hashes: list[str] = []
    for offset in range(100):
        residual, block, injection = _inputs(20261000 + offset)
        authority = CORE.torch_authority_hc_combine_norm(
            residual, block, injection, weight, 1e-6
        )
        candidate = CORE.exact_staged_hc_combine_norm(
            residual, block, injection, affine, 1e-6
        )
        assert all(torch.equal(a, b) for a, b in zip(authority, candidate))
        hashes.append(_hash_pair(candidate))
    assert len(set(hashes)) == 100


def _bf16_values(bits: list[int], count: int) -> torch.Tensor:
    values = torch.tensor(bits, dtype=torch.uint16).view(torch.bfloat16)
    repeats = (count + values.numel() - 1) // values.numel()
    return values.repeat(repeats)[:count].contiguous()


def test_adversarial_finite_bf16_values_preserve_both_outputs() -> None:
    # Includes signed zero, subnormals, normal-boundary values, the retained
    # SiLU mismatch trigger 0x41be, and large finite magnitudes without NaNs.
    bits = [
        0x0000,
        0x8000,
        0x0001,
        0x8001,
        0x007F,
        0x807F,
        0x0080,
        0x8080,
        0x3F80,
        0xBF80,
        0x41BE,
        0xC1BE,
        0x7E00,
        0xFE00,
    ]
    residual = _bf16_values(bits, CORE.HYPER_HIDDEN_SIZE).reshape(1, -1)
    block = _bf16_values(list(reversed(bits)), CORE.HIDDEN_SIZE).reshape(1, -1)
    injection = _bf16_values([0x41BE, 0xC1BE, 0x0001, 0x8001], 4).reshape(1, 4)
    weight = _bf16_values([0x0000, 0x3A80, 0xBA80, 0x3F00], 10240)
    affine = CORE.build_exact_norm_affine(weight)
    authority = CORE.torch_authority_hc_combine_norm(
        residual, block, injection, weight, 1e-6
    )
    candidate = CORE.exact_staged_hc_combine_norm(
        residual, block, injection, affine, 1e-6
    )
    assert all(torch.equal(a, b) for a, b in zip(authority, candidate))


def test_affine_validation_rejects_one_bit_change() -> None:
    weight = torch.zeros(CORE.HYPER_HIDDEN_SIZE, dtype=torch.bfloat16)
    affine = CORE.build_exact_norm_affine(weight)
    affine[17] = torch.nextafter(
        affine[17], torch.tensor(float("inf"), dtype=torch.float32)
    )
    with pytest.raises(ValueError, match="cached norm affine differs"):
        CORE.validate_exact_norm_affine(weight, affine)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("dtype", "residual must be BF16"),
        ("shape", "requires D=10240"),
        ("hc", "requires hc_count=4"),
    ],
)
def test_contract_rejects_wrong_identity(mutation: str, message: str) -> None:
    residual, block, injection = _inputs(9)
    weight = torch.zeros(CORE.HYPER_HIDDEN_SIZE, dtype=torch.bfloat16)
    affine = CORE.build_exact_norm_affine(weight)
    hc_count = 4
    if mutation == "dtype":
        residual = residual.float()
    elif mutation == "shape":
        residual = residual[:, :-4].contiguous()
    elif mutation == "hc":
        hc_count = 2
    with pytest.raises((TypeError, ValueError), match=message):
        CORE.exact_staged_hc_combine_norm(
            residual, block, injection, affine, 1e-6, hc_count
        )
