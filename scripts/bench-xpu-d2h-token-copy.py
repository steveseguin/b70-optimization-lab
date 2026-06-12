#!/usr/bin/env python3
"""Isolate tiny XPU-to-host token copy latency.

This is aimed at vLLM's async-output path, where a c1 decode request copies a
small int32 token-id tensor to host and then waits on an XPU event. The point is
to distinguish real D2H copy cost from upstream queue/dependency exposure.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import time
from pathlib import Path
from typing import Any, Callable


def parse_shape(value: str) -> tuple[int, ...]:
    parts = value.lower().replace("x", ",").split(",")
    try:
        shape = tuple(int(part.strip()) for part in parts if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"bad shape {value!r}") from exc
    if not shape or any(dim <= 0 for dim in shape):
        raise argparse.ArgumentTypeError(f"bad shape {value!r}")
    return shape


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="JSON output path")
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--warmup", type=int, default=200)
    parser.add_argument("--iters", type=int, default=3000)
    parser.add_argument(
        "--shape",
        action="append",
        type=parse_shape,
        help="Tensor shape, e.g. 1x1. May be repeated.",
    )
    parser.add_argument(
        "--no-pinned",
        action="store_true",
        help="Skip pinned CPU destination allocation attempts.",
    )
    parser.add_argument(
        "--save-samples",
        action="store_true",
        help="Include raw timing samples in the JSON.",
    )
    return parser.parse_args()


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * pct / 100.0
    low = math.floor(index)
    high = math.ceil(index)
    if low == high:
        return ordered[int(index)]
    return ordered[low] * (high - index) + ordered[high] * (index - low)


def summarize(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "min": None,
            "mean": None,
            "median": None,
            "p90": None,
            "p99": None,
            "max": None,
        }
    return {
        "count": len(values),
        "min": min(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "p90": percentile(values, 90),
        "p99": percentile(values, 99),
        "max": max(values),
    }


def ns_to_ms(value: int) -> float:
    return value / 1_000_000.0


def make_cpu_tensor(torch: Any, shape: tuple[int, ...], pinned: bool) -> tuple[Any, bool, str | None]:
    if not pinned:
        return torch.empty(shape, dtype=torch.int32, device="cpu"), False, None
    try:
        return torch.empty(shape, dtype=torch.int32, device="cpu", pin_memory=True), True, None
    except Exception as exc:  # noqa: BLE001 - record backend behavior
        return torch.empty(shape, dtype=torch.int32, device="cpu"), False, repr(exc)


def run_mode(
    *,
    name: str,
    fn: Callable[[], dict[str, float]],
    warmup: int,
    iters: int,
) -> dict[str, Any]:
    for _ in range(max(0, warmup)):
        fn()

    samples: dict[str, list[float]] = {}
    checksum = 0
    for _ in range(max(1, iters)):
        item = fn()
        checksum += 1
        for key, value in item.items():
            samples.setdefault(key, []).append(value)

    return {
        "mode": name,
        "checksum_iterations": checksum,
        "timings_ms": {key: summarize(values) for key, values in samples.items()},
        "_samples": samples,
    }


def main() -> None:
    args = parse_args()

    import torch

    if not hasattr(torch, "xpu") or not torch.xpu.is_available():
        raise SystemExit("torch.xpu is not available")

    torch.xpu.set_device(args.device)
    device = torch.device(args.device)
    shapes = args.shape or [(1, 1), (1, 8), (1, 32), (48, 1)]

    out: dict[str, Any] = {
        "schema": "bench-xpu-d2h-token-copy-v1",
        "created_unix": time.time(),
        "host": platform.node(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "device": str(device),
        "xpu_device_count": torch.xpu.device_count(),
        "env": {
            "ONEAPI_DEVICE_SELECTOR": os.environ.get("ONEAPI_DEVICE_SELECTOR"),
            "ZE_AFFINITY_MASK": os.environ.get("ZE_AFFINITY_MASK"),
            "SYCL_CACHE_PERSISTENT": os.environ.get("SYCL_CACHE_PERSISTENT"),
        },
        "warmup": args.warmup,
        "iters": args.iters,
        "records": [],
    }

    # Prime the context before measuring tiny operations.
    torch.empty((1,), dtype=torch.int32, device=device).fill_(7)
    torch.xpu.synchronize(device)

    for shape in shapes:
        src = torch.arange(math.prod(shape), dtype=torch.int32, device=device).reshape(shape)
        torch.xpu.synchronize(device)

        destinations: list[tuple[str, Any, bool, str | None]] = []
        if not args.no_pinned:
            dst, pinned, error = make_cpu_tensor(torch, shape, pinned=True)
            destinations.append(("pinned_cpu", dst, pinned, error))
        dst, pinned, error = make_cpu_tensor(torch, shape, pinned=False)
        destinations.append(("plain_cpu", dst, pinned, error))

        record: dict[str, Any] = {
            "shape": list(shape),
            "numel": math.prod(shape),
            "dtype": "torch.int32",
            "destinations": [],
        }

        for destination_name, dst, pinned, pin_error in destinations:
            event = torch.xpu.Event()
            stream = torch.xpu.Stream(device=device)

            def empty_sync() -> dict[str, float]:
                start = time.perf_counter_ns()
                torch.xpu.synchronize(device)
                end = time.perf_counter_ns()
                return {"total": ns_to_ms(end - start)}

            def empty_event_current() -> dict[str, float]:
                start = time.perf_counter_ns()
                event.record()
                submitted = time.perf_counter_ns()
                event.synchronize()
                end = time.perf_counter_ns()
                return {
                    "submit": ns_to_ms(submitted - start),
                    "wait": ns_to_ms(end - submitted),
                    "total": ns_to_ms(end - start),
                }

            def to_cpu_blocking() -> dict[str, float]:
                start = time.perf_counter_ns()
                cpu = src.to("cpu")
                first = int(cpu.reshape(-1)[0])
                end = time.perf_counter_ns()
                if first != 0:
                    raise RuntimeError("unexpected copy result")
                return {"total": ns_to_ms(end - start)}

            def copy_blocking_sync() -> dict[str, float]:
                start = time.perf_counter_ns()
                dst.copy_(src, non_blocking=False)
                submitted = time.perf_counter_ns()
                torch.xpu.synchronize(device)
                end = time.perf_counter_ns()
                if int(dst.reshape(-1)[0]) != 0:
                    raise RuntimeError("unexpected copy result")
                return {
                    "submit": ns_to_ms(submitted - start),
                    "wait": ns_to_ms(end - submitted),
                    "total": ns_to_ms(end - start),
                }

            def copy_nonblocking_current_event() -> dict[str, float]:
                start = time.perf_counter_ns()
                dst.copy_(src, non_blocking=True)
                event.record()
                submitted = time.perf_counter_ns()
                event.synchronize()
                end = time.perf_counter_ns()
                if int(dst.reshape(-1)[0]) != 0:
                    raise RuntimeError("unexpected copy result")
                return {
                    "submit": ns_to_ms(submitted - start),
                    "wait": ns_to_ms(end - submitted),
                    "total": ns_to_ms(end - start),
                }

            def copy_nonblocking_side_stream_event() -> dict[str, float]:
                start = time.perf_counter_ns()
                with torch.xpu.stream(stream):
                    dst.copy_(src, non_blocking=True)
                    event.record()
                submitted = time.perf_counter_ns()
                event.synchronize()
                end = time.perf_counter_ns()
                if int(dst.reshape(-1)[0]) != 0:
                    raise RuntimeError("unexpected copy result")
                return {
                    "submit": ns_to_ms(submitted - start),
                    "wait": ns_to_ms(end - submitted),
                    "total": ns_to_ms(end - start),
                }

            destination_record: dict[str, Any] = {
                "name": destination_name,
                "requested_pinned": destination_name == "pinned_cpu",
                "actual_pinned": pinned,
                "pin_error": pin_error,
                "modes": [],
            }
            for mode_name, mode_fn in (
                ("empty_sync", empty_sync),
                ("empty_event_current", empty_event_current),
                ("to_cpu_blocking", to_cpu_blocking),
                ("copy_blocking_sync", copy_blocking_sync),
                ("copy_nonblocking_current_event", copy_nonblocking_current_event),
                ("copy_nonblocking_side_stream_event", copy_nonblocking_side_stream_event),
            ):
                mode_result = run_mode(
                    name=mode_name,
                    fn=mode_fn,
                    warmup=args.warmup,
                    iters=args.iters,
                )
                if not args.save_samples:
                    mode_result.pop("_samples", None)
                destination_record["modes"].append(mode_result)

            record["destinations"].append(destination_record)

        out["records"].append(record)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    compact = {
        "out": str(out_path),
        "device": str(device),
        "records": [
            {
                "shape": record["shape"],
                "destinations": [
                    {
                        "name": destination["name"],
                        "actual_pinned": destination["actual_pinned"],
                        "modes": {
                            mode["mode"]: mode["timings_ms"].get("total", {})
                            for mode in destination["modes"]
                        },
                    }
                    for destination in record["destinations"]
                ],
            }
            for record in out["records"]
        ],
    }
    print(json.dumps(compact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
