#!/usr/bin/env python3
"""Bounded postflight compute and free-memory receipt for the four B70s."""

import argparse
import hashlib
import json
from pathlib import Path

import torch


EXPECTED_DEVICES = 4
ELEMENTS = 4096
MINIMUM_FREE_FRACTION = 0.90


def fail(message: str) -> None:
    raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        fail(f"refusing to overwrite {args.output}")

    count = torch.xpu.device_count()
    if count != EXPECTED_DEVICES:
        fail(f"expected {EXPECTED_DEVICES} visible XPUs, got {count}")

    expected = torch.arange(ELEMENTS, dtype=torch.int32) * 3 + 7
    rows: list[dict[str, int | float | str]] = []
    for index in range(count):
        device = torch.device(f"xpu:{index}")
        actual = torch.arange(ELEMENTS, dtype=torch.int32, device=device) * 3 + 7
        torch.xpu.synchronize(device)
        actual_cpu = actual.cpu()
        if not torch.equal(actual_cpu, expected):
            fail(f"XPU {index} postflight arithmetic mismatch")
        torch.xpu.empty_cache()
        free_bytes, total_bytes = torch.xpu.mem_get_info(index)
        free_fraction = free_bytes / total_bytes
        if free_fraction < MINIMUM_FREE_FRACTION:
            fail(
                f"XPU {index} free-memory fraction {free_fraction:.6f} is below "
                f"{MINIMUM_FREE_FRACTION:.2f}"
            )
        rows.append(
            {
                "device_index": index,
                "free_bytes": free_bytes,
                "total_bytes": total_bytes,
                "free_fraction": free_fraction,
                "output_sha256": hashlib.sha256(
                    actual_cpu.numpy().tobytes()
                ).hexdigest(),
            }
        )

    payload = {
        "schema_version": 1,
        "status": "passed",
        "device_count": count,
        "elements_per_device": ELEMENTS,
        "minimum_free_fraction": MINIMUM_FREE_FRACTION,
        "devices": rows,
    }
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    if temporary.exists():
        fail(f"refusing to overwrite {temporary}")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(args.output)


if __name__ == "__main__":
    main()
