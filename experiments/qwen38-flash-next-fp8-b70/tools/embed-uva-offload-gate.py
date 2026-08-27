#!/usr/bin/env python3
"""Bounded XPU gate for Qwen4Exp's directly constructed embedding offload."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import tempfile
import time

import torch
from torch import nn

from vllm.model_executor.offloader.base import NoopOffloader, set_offloader
from vllm.model_executor.offloader.uva import UVAOffloader
from vllm.models.qwen4_exp.amd.model import _maybe_offload_embed_tokens


ROWS = 62_080
HIDDEN = 2_560
EXPECTED_BYTES = ROWS * HIDDEN * 2
PREFIX = "language_model.model"
SELECTOR = "embed_tokens.weight"


def tensor_sha256(tensor: torch.Tensor) -> str:
    return hashlib.sha256(tensor.contiguous().view(torch.uint8).numpy()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()

    assert torch.xpu.device_count() >= 1
    device = torch.device("xpu:0")
    torch.manual_seed(38)
    torch.xpu.manual_seed_all(38)

    started = time.monotonic()
    embedding = nn.Embedding(ROWS, HIDDEN, dtype=torch.bfloat16, device=device)
    indices = torch.tensor([0, 1, 31_039, 62_079], dtype=torch.long, device=device)
    before = embedding(indices).detach().cpu()
    torch.xpu.synchronize()

    offloader = UVAOffloader(
        cpu_offload_max_bytes=int(12.25 * 1024**3),
        cpu_offload_params={SELECTOR},
    )
    assert offloader.uva_offloading, "gate requires real XPU UVA, not fallback copying"
    set_offloader(offloader)
    try:
        _maybe_offload_embed_tokens(embedding, PREFIX)
        assert getattr(embedding.weight, "_vllm_is_uva_offloaded", False)
        assert embedding.weight.device.type == "xpu"
        assert offloader.cpu_offload_bytes == EXPECTED_BYTES
        after = embedding(indices).detach().cpu()
        torch.xpu.synchronize()
    finally:
        set_offloader(NoopOffloader())

    torch.testing.assert_close(after, before, rtol=0, atol=0)
    result = {
        "schema_version": 1,
        "status": "pass",
        "purpose": "exact TP4 rank-local input-embedding UVA offload gate",
        "device": str(device),
        "torch_version": torch.__version__,
        "shape": [ROWS, HIDDEN],
        "dtype": "torch.bfloat16",
        "prefix": PREFIX,
        "selector": SELECTOR,
        "expected_and_observed_offload_bytes": EXPECTED_BYTES,
        "uva_offloading": True,
        "weight_device_after": str(embedding.weight.device),
        "sample_indices": indices.cpu().tolist(),
        "sample_sha256_before": tensor_sha256(before),
        "sample_sha256_after": tensor_sha256(after),
        "exact_sample_match": True,
        "elapsed_seconds": time.monotonic() - started,
        "script_sha256": hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
        "environment": {
            name: os.environ.get(name)
            for name in (
                "PYTHONPATH",
                "LD_LIBRARY_PATH",
                "ZE_AFFINITY_MASK",
                "VLLM_TARGET_DEVICE",
            )
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=args.output.parent, prefix=f".{args.output.name}.", delete=False
    ) as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = pathlib.Path(handle.name)
    os.replace(temporary, args.output)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
