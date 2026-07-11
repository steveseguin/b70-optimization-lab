#!/usr/bin/env python3
"""Check ordered in-place XPU KV-cache slot compaction.

This is a correctness diagnostic, not endpoint throughput. The synthetic cache
uses the same non-contiguous ``[K/V, block, token, head, dim]`` view produced
when K/V planes are interleaved in the underlying allocation. Source/destination
pairs deliberately overlap, so implementations must preserve pair order.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

import torch


CLASSIFICATION = "correctness_diagnostic_not_benchmark_not_localmaxxing"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument(
        "--kernel-prefix",
        type=Path,
        default=Path("/home/steve/src/vllm-xpu-kernels"),
    )
    return parser.parse_args()


def reference_copy(
    cache: torch.Tensor,
    source_slots: list[int],
    destination_slots: list[int],
) -> None:
    block_size = cache.shape[2]
    for source_slot, destination_slot in zip(source_slots, destination_slots):
        source_block, source_offset = divmod(source_slot, block_size)
        destination_block, destination_offset = divmod(
            destination_slot, block_size
        )
        staged = cache[:, source_block, source_offset].clone()
        cache[:, destination_block, destination_offset].copy_(staged)


def main() -> int:
    args = parse_args()
    kernel_prefix = str(args.kernel_prefix.expanduser().resolve())
    if kernel_prefix not in sys.path:
        sys.path.insert(0, kernel_prefix)
    importlib.import_module("vllm_xpu_kernels._xpu_C")

    device = torch.device(args.device)
    source_list = [2, 3, 7, 10]
    destination_list = [1, 2, 3, 4]
    reports = []
    passed = True
    for dtype in (torch.bfloat16, torch.float16, torch.float32):
        # Interleave K/V by block, then expose the production logical layout.
        storage = torch.arange(
            6 * 2 * 16 * 4 * 8,
            dtype=torch.float32,
            device=device,
        ).reshape(6, 2, 16, 4, 8)
        cache = storage.to(dtype).permute(1, 0, 2, 3, 4)
        expected = cache.clone()
        reference_copy(expected, source_list, destination_list)

        source_slots = torch.tensor(source_list, dtype=torch.int64, device=device)
        destination_slots = torch.tensor(
            destination_list, dtype=torch.int64, device=device
        )
        torch.ops._xpu_C.kv_cache_copy_slots(
            cache, source_slots, destination_slots
        )
        torch.xpu.synchronize(device)
        exact = torch.equal(cache, expected)
        passed &= exact
        reports.append(
            {
                "dtype": str(dtype),
                "exact": exact,
                "shape": list(cache.shape),
                "stride": list(cache.stride()),
                "contiguous": cache.is_contiguous(),
            }
        )

    print(
        json.dumps(
            {
                "classification": CLASSIFICATION,
                "passed": passed,
                "source_slots": source_list,
                "destination_slots": destination_list,
                "reports": reports,
            },
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
