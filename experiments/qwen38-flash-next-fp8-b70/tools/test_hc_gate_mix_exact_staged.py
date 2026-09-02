#!/usr/bin/env python3
"""CPU contracts for the exact staged HC gate-mix candidate."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest
import torch


CORE_PATH = Path(__file__).with_name("hc_gate_mix_exact_staged.py")
SPEC = importlib.util.spec_from_file_location("q38_hc_gate_mix_exact", CORE_PATH)
assert SPEC is not None and SPEC.loader is not None
CORE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CORE)


def _inputs(seed: int, scale: float = 1.0) -> tuple[torch.Tensor, torch.Tensor]:
    generator = torch.Generator(device="cpu").manual_seed(seed)
    x = (
        torch.randn(
            (1, CORE.HYPER_HIDDEN_SIZE),
            generator=generator,
            dtype=torch.bfloat16,
        )
        * scale
    ).contiguous()
    gate = (
        torch.randn(
            (1, CORE.HYPER_HIDDEN_SIZE),
            generator=generator,
            dtype=torch.bfloat16,
        )
        * scale
    ).contiguous()
    return x, gate


def _sha256(tensor: torch.Tensor) -> str:
    return hashlib.sha256(
        tensor.contiguous().view(torch.uint8).numpy().tobytes()
    ).hexdigest()


def _assert_byte_exact(actual: torch.Tensor, expected: torch.Tensor) -> None:
    assert actual.dtype == expected.dtype
    assert actual.shape == expected.shape
    assert torch.equal(
        actual.contiguous().view(torch.uint8),
        expected.contiguous().view(torch.uint8),
    )


@pytest.mark.parametrize("seed", [20260826, 20260827, 20260830])
@pytest.mark.parametrize("scale", [2.0**-8, 0.1, 1.0, 8.0, 2.0**8])
def test_candidate_is_exact_at_production_shape(seed: int, scale: float) -> None:
    x, gate = _inputs(seed, scale)
    authority = CORE.torch_authority_hc_gate_mix(x, gate)
    candidate = CORE.exact_staged_hc_gate_mix(x, gate)
    assert candidate.dtype == torch.bfloat16
    assert candidate.shape == (1, CORE.HIDDEN_SIZE)
    _assert_byte_exact(candidate, authority)


def test_one_hundred_changing_inputs_are_exact_and_distinct() -> None:
    hashes: list[str] = []
    for offset in range(100):
        x, gate = _inputs(20261000 + offset, 0.125 + offset / 32)
        authority = CORE.torch_authority_hc_gate_mix(x, gate)
        candidate = CORE.exact_staged_hc_gate_mix(x, gate)
        _assert_byte_exact(candidate, authority)
        hashes.append(_sha256(candidate))
    assert len(set(hashes)) == 100


def test_every_finite_bf16_x_encoding_is_covered_exactly() -> None:
    # Sigmoid arithmetic is unchanged.  Exhaust the finite BF16 values through
    # the changed implicit-promotion and reduction/output path in seven exact
    # production-shape invocations.
    bits = torch.arange(65536, dtype=torch.int32).to(torch.uint16)
    exponent = bits & 0x7F80
    finite = bits[exponent != 0x7F80].view(torch.bfloat16)
    gate_bits = torch.tensor(
        [0x0000, 0x8000, 0x3F80, 0xBF80, 0x41BE, 0xC1BE, 0x7E00, 0xFE00],
        dtype=torch.uint16,
    ).view(torch.bfloat16)
    calls = (finite.numel() + CORE.HYPER_HIDDEN_SIZE - 1) // CORE.HYPER_HIDDEN_SIZE
    for call in range(calls):
        start = call * CORE.HYPER_HIDDEN_SIZE
        values = finite[start : start + CORE.HYPER_HIDDEN_SIZE]
        if values.numel() < CORE.HYPER_HIDDEN_SIZE:
            values = torch.cat(
                [values, finite[: CORE.HYPER_HIDDEN_SIZE - values.numel()]]
            )
        x = values.reshape(1, -1).contiguous()
        repeats = (CORE.HYPER_HIDDEN_SIZE + gate_bits.numel() - 1) // gate_bits.numel()
        gate = gate_bits.repeat(repeats)[: CORE.HYPER_HIDDEN_SIZE]
        gate = gate.roll(call).reshape(1, -1).contiguous()
        authority = CORE.torch_authority_hc_gate_mix(x, gate)
        candidate = CORE.exact_staged_hc_gate_mix(x, gate)
        _assert_byte_exact(candidate, authority)


def test_inputs_are_not_mutated_and_output_does_not_alias() -> None:
    x, gate = _inputs(19)
    x_before = x.clone()
    gate_before = gate.clone()
    output = CORE.exact_staged_hc_gate_mix(x, gate)
    _assert_byte_exact(x, x_before)
    _assert_byte_exact(gate, gate_before)
    assert output.untyped_storage().data_ptr() not in {
        x.untyped_storage().data_ptr(),
        gate.untyped_storage().data_ptr(),
    }


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("dtype", "x and gate must be BF16"),
        ("shape", "requires x"),
        ("gate_shape", "same shape"),
        ("hc", "requires hc_count=4"),
        ("stride", "contiguous"),
    ],
)
def test_contract_rejects_wrong_identity(mutation: str, message: str) -> None:
    x, gate = _inputs(23)
    hc_count = 4
    if mutation == "dtype":
        x = x.float()
        gate = gate.float()
    elif mutation == "shape":
        x = x[:, :-4].contiguous()
        gate = gate[:, :-4].contiguous()
    elif mutation == "gate_shape":
        gate = gate[:, :-4].contiguous()
    elif mutation == "hc":
        hc_count = 2
    elif mutation == "stride":
        x = torch.empty(1, CORE.HYPER_HIDDEN_SIZE * 2, dtype=torch.bfloat16)[:, ::2]
    with pytest.raises((TypeError, ValueError), match=message):
        CORE.exact_staged_hc_gate_mix(x, gate, hc_count)
