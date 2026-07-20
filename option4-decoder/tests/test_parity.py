from __future__ import annotations

from pathlib import Path
import sys

import torch
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from option4_decoder import (  # noqa: E402
    FixedAddressCommandGraph,
    GraphState,
    TensorAddress,
    compare_tensor_bits,
)


def test_bitwise_parity_distinguishes_nan_payloads() -> None:
    left = torch.tensor([0x7FC00001], dtype=torch.int32).view(torch.float32)
    right = left.clone()
    assert compare_tensor_bits("same_nan", left, right).exact
    right = torch.tensor([0x7FC00002], dtype=torch.int32).view(torch.float32)
    report = compare_tensor_bits("different_nan", left, right)
    assert not report.exact
    assert report.mismatch_bytes == 1


def test_address_identity_includes_backing_storage_size() -> None:
    backing = torch.empty(128, dtype=torch.uint8)
    view = backing[8:24]
    identity = TensorAddress.capture("view", view)
    assert identity.storage_offset == 8
    assert identity.storage_data_ptr == backing.data_ptr()
    assert identity.storage_nbytes == 128


def test_parity_qualification_fails_closed() -> None:
    graph = FixedAddressCommandGraph(lambda: {}, {})
    graph.state = GraphState.BUILT
    with pytest.raises(RuntimeError, match="exact parity"):
        graph.mark_parity_qualified(exact=False)
