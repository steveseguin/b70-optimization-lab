#!/usr/bin/env python3
"""Bounded changing-value allocation/compute/copy probe for one visible XPU."""

from __future__ import annotations

import argparse
import hashlib
import json
import time

import torch


def stage(name: str, **fields: object) -> None:
    payload = {"stage": name, "monotonic": time.monotonic(), **fields}
    print(f"PROBE_STAGE {json.dumps(payload, sort_keys=True)}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--physical-rank", type=int, required=True, choices=range(4))
    args = parser.parse_args()

    stage("import-done", physical_rank=args.physical_rank)
    visible = torch.xpu.device_count()
    if visible != 1:
        raise RuntimeError(f"expected one affinity-visible XPU, got {visible}")
    torch.xpu.set_device(0)
    stage(
        "device-set",
        physical_rank=args.physical_rank,
        visible_device=0,
        device_name=torch.xpu.get_device_name(0),
    )

    host_input = torch.arange(4096, dtype=torch.float32)
    device_input = host_input.to("xpu")
    stage("tensor-allocated", physical_rank=args.physical_rank)
    device_output = (device_input * 3.25 + 7.5).square()
    copied = device_output.cpu()
    torch.xpu.synchronize()
    stage("compute-synchronized", physical_rank=args.physical_rank)

    expected = (host_input * 3.25 + 7.5).square()
    if not torch.equal(copied, expected):
        mismatches = int((copied != expected).sum().item())
        raise AssertionError(f"changing-value compute mismatch: {mismatches}")
    digest = hashlib.sha256(copied.numpy().tobytes()).hexdigest()
    stage("verify-ok", physical_rank=args.physical_rank, sha256=digest)
    print(
        f"PROBE_RESULT=PASS physical_rank={args.physical_rank} sha256={digest}",
        flush=True,
    )


if __name__ == "__main__":
    main()
