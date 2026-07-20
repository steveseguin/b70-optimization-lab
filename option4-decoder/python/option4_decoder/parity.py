"""Bitwise tensor comparison used by the Phase 0 replay gate."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import torch


@dataclass(frozen=True)
class BitwiseParityReport:
    name: str
    exact: bool
    mismatch_bytes: int
    total_bytes: int
    first_mismatch_byte: int | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def compare_tensor_bits(
    name: str, actual: torch.Tensor, expected: torch.Tensor
) -> BitwiseParityReport:
    if actual.shape != expected.shape:
        raise ValueError(f"{name}: shape mismatch {actual.shape} != {expected.shape}")
    if actual.dtype != expected.dtype:
        raise ValueError(f"{name}: dtype mismatch {actual.dtype} != {expected.dtype}")
    actual_bytes = actual.contiguous().view(torch.uint8).flatten()
    expected_bytes = expected.contiguous().view(torch.uint8).flatten()
    mismatch = actual_bytes != expected_bytes
    mismatch_bytes = int(torch.count_nonzero(mismatch).item())
    first = None
    if mismatch_bytes:
        first = int(torch.nonzero(mismatch, as_tuple=False)[0].item())
    return BitwiseParityReport(
        name=name,
        exact=mismatch_bytes == 0,
        mismatch_bytes=mismatch_bytes,
        total_bytes=actual_bytes.numel(),
        first_mismatch_byte=first,
    )
