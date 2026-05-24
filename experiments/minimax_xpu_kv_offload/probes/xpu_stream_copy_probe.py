#!/usr/bin/env python3
"""Probe PyTorch XPU host/device copy primitives for CPU KV offload.

This intentionally uses small transfer sizes by default so it can run while the
normal 32K MiniMax server is loaded. Larger transfer sweeps should be run after
stopping the server.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import torch


def gbps(num_bytes: int, seconds: float) -> float | None:
    if seconds <= 0:
        return None
    return num_bytes / seconds / 1e9


def has_attr_chain(root: Any, names: list[str]) -> bool:
    obj = root
    for name in names:
        if not hasattr(obj, name):
            return False
        obj = getattr(obj, name)
    return True


def run_size(size_bytes: int, device: torch.device) -> dict[str, Any]:
    result: dict[str, Any] = {
        "size_bytes": size_bytes,
        "size_mib": size_bytes / (1024 * 1024),
        "ok": False,
    }

    if size_bytes <= 0:
        result["error"] = "size must be positive"
        return result

    try:
        src = torch.empty(size_bytes, dtype=torch.uint8, device="cpu", pin_memory=True)
        src.copy_(torch.arange(size_bytes, dtype=torch.uint8))
        dst = torch.empty_like(src, device=device)
        back = torch.empty_like(src, device="cpu", pin_memory=True)

        xpu = torch.xpu
        stream = xpu.Stream() if hasattr(xpu, "Stream") else None
        stream_context = xpu.stream(stream) if stream is not None else None

        Event = getattr(xpu, "Event", None)
        start_event = Event(enable_timing=True) if Event is not None else None
        mid_event = Event(enable_timing=True) if Event is not None else None
        end_event = Event(enable_timing=True) if Event is not None else None

        t0 = time.perf_counter()
        if stream_context is not None:
            with stream_context:
                if start_event is not None:
                    start_event.record()
                dst.copy_(src, non_blocking=True)
                if mid_event is not None:
                    mid_event.record()
                back.copy_(dst, non_blocking=True)
                if end_event is not None:
                    end_event.record()
            stream.synchronize()
        else:
            dst.copy_(src)
            back.copy_(dst)
            xpu.synchronize()
        t1 = time.perf_counter()

        ok = torch.equal(src, back)
        result.update(
            {
                "ok": bool(ok),
                "src_is_pinned": bool(src.is_pinned()),
                "back_is_pinned": bool(back.is_pinned()),
                "wall_seconds_roundtrip": t1 - t0,
                "wall_roundtrip_gbps": gbps(size_bytes * 2, t1 - t0),
            }
        )

        if start_event is not None and mid_event is not None and end_event is not None:
            try:
                h2d_ms = start_event.elapsed_time(mid_event)
                d2h_ms = mid_event.elapsed_time(end_event)
                result.update(
                    {
                        "event_h2d_ms": h2d_ms,
                        "event_d2h_ms": d2h_ms,
                        "event_h2d_gbps": gbps(size_bytes, h2d_ms / 1000.0),
                        "event_d2h_gbps": gbps(size_bytes, d2h_ms / 1000.0),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                result["event_timing_error"] = f"{type(exc).__name__}: {exc}"

    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sizes-mib",
        nargs="+",
        type=int,
        default=[1, 4, 16, 64],
        help="Transfer sizes to test in MiB.",
    )
    parser.add_argument("--device-index", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report: dict[str, Any] = {
        "torch_version": torch.__version__,
        "has_torch_xpu": hasattr(torch, "xpu"),
        "sizes_mib_requested": args.sizes_mib,
    }

    if not hasattr(torch, "xpu"):
        report["error"] = "torch.xpu is unavailable"
    else:
        xpu = torch.xpu
        report["xpu"] = {
            "is_available": bool(xpu.is_available()),
            "device_count": int(xpu.device_count()) if xpu.is_available() else 0,
            "has_stream": hasattr(xpu, "Stream"),
            "has_stream_context": hasattr(xpu, "stream"),
            "has_event": hasattr(xpu, "Event"),
            "has_current_stream": hasattr(xpu, "current_stream"),
            "has_synchronize": hasattr(xpu, "synchronize"),
            "has_memory_stats": has_attr_chain(xpu, ["memory_stats"]),
        }

        if xpu.is_available():
            device = torch.device(f"xpu:{args.device_index}")
            report["device"] = str(device)
            try:
                report["device_name"] = xpu.get_device_name(args.device_index)
            except Exception as exc:  # noqa: BLE001
                report["device_name_error"] = f"{type(exc).__name__}: {exc}"
            report["transfers"] = [
                run_size(size_mib * 1024 * 1024, device)
                for size_mib in args.sizes_mib
            ]
        else:
            report["error"] = "torch.xpu reports unavailable"

    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")

    if report.get("error"):
        return 1
    transfers = report.get("transfers", [])
    return 0 if transfers and all(item.get("ok") for item in transfers) else 2


if __name__ == "__main__":
    raise SystemExit(main())
