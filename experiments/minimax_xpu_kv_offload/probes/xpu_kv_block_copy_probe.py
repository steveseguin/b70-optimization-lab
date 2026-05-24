#!/usr/bin/env python3
"""Probe XPU KV block copies against a pinned CPU backing store.

This models the core data movement needed by vLLM CPU KV offload:

- GPU/XPU KV pages are represented as rows of int8 bytes.
- CPU offload pages can be larger than GPU pages by `block_size_factor`.
- GPU logical block N maps into CPU block N // block_size_factor and sub-block
  N % block_size_factor.
- Copies run on a torch.xpu stream and verify exact round-trip bytes.

The implementation intentionally uses PyTorch slice copies instead of vLLM's
CUDA-only `swap_blocks_batch` custom op. This is a correctness and feasibility
probe, not the final optimized worker.
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


def make_pattern(num_blocks: int, page_size: int, device: torch.device) -> torch.Tensor:
    block_ids = torch.arange(num_blocks, dtype=torch.int32, device=device)[:, None]
    byte_ids = torch.arange(page_size, dtype=torch.int32, device=device)[None, :]
    # int8 view keeps byte-level data compact while generating deterministic,
    # block-specific content for exact round-trip verification.
    return ((block_ids * 17 + byte_ids * 31) & 0x7F).to(torch.int8)


def copy_gpu_to_cpu(
    gpu_tensor: torch.Tensor,
    cpu_tensor: torch.Tensor,
    gpu_block_ids: torch.Tensor,
    cpu_logical_block_ids: torch.Tensor,
    block_size_factor: int,
) -> None:
    page_size = gpu_tensor.shape[1]
    for gpu_id, logical_id in zip(gpu_block_ids.tolist(), cpu_logical_block_ids.tolist()):
        cpu_block = logical_id // block_size_factor
        sub_block = logical_id % block_size_factor
        start = sub_block * page_size
        end = start + page_size
        cpu_tensor[cpu_block, start:end].copy_(gpu_tensor[gpu_id], non_blocking=True)


def copy_cpu_to_gpu(
    cpu_tensor: torch.Tensor,
    gpu_tensor: torch.Tensor,
    cpu_logical_block_ids: torch.Tensor,
    gpu_block_ids: torch.Tensor,
    block_size_factor: int,
) -> None:
    page_size = gpu_tensor.shape[1]
    for logical_id, gpu_id in zip(cpu_logical_block_ids.tolist(), gpu_block_ids.tolist()):
        cpu_block = logical_id // block_size_factor
        sub_block = logical_id % block_size_factor
        start = sub_block * page_size
        end = start + page_size
        gpu_tensor[gpu_id].copy_(cpu_tensor[cpu_block, start:end], non_blocking=True)


def copy_gpu_to_cpu_indexed(
    gpu_tensor: torch.Tensor,
    cpu_tensor: torch.Tensor,
    gpu_block_ids: torch.Tensor,
    cpu_logical_block_ids: torch.Tensor,
    block_size_factor: int,
) -> None:
    page_size = gpu_tensor.shape[1]
    cpu_view = cpu_tensor.view(cpu_tensor.shape[0] * block_size_factor, page_size)
    cpu_view.index_copy_(
        0,
        cpu_logical_block_ids,
        gpu_tensor.index_select(0, gpu_block_ids.to(gpu_tensor.device)),
    )


def copy_cpu_to_gpu_indexed(
    cpu_tensor: torch.Tensor,
    gpu_tensor: torch.Tensor,
    cpu_logical_block_ids: torch.Tensor,
    gpu_block_ids: torch.Tensor,
    block_size_factor: int,
) -> None:
    page_size = gpu_tensor.shape[1]
    cpu_view = cpu_tensor.view(cpu_tensor.shape[0] * block_size_factor, page_size)
    gpu_tensor.index_copy_(
        0,
        gpu_block_ids.to(gpu_tensor.device),
        cpu_view.index_select(0, cpu_logical_block_ids),
    )


def copy_gpu_to_cpu_slice(
    gpu_tensor: torch.Tensor,
    cpu_tensor: torch.Tensor,
    gpu_start: int,
    cpu_logical_start: int,
    count: int,
    block_size_factor: int,
) -> None:
    page_size = gpu_tensor.shape[1]
    cpu_view = cpu_tensor.view(cpu_tensor.shape[0] * block_size_factor, page_size)
    cpu_view[cpu_logical_start : cpu_logical_start + count].copy_(
        gpu_tensor[gpu_start : gpu_start + count], non_blocking=True
    )


def copy_cpu_to_gpu_slice(
    cpu_tensor: torch.Tensor,
    gpu_tensor: torch.Tensor,
    cpu_logical_start: int,
    gpu_start: int,
    count: int,
    block_size_factor: int,
) -> None:
    page_size = gpu_tensor.shape[1]
    cpu_view = cpu_tensor.view(cpu_tensor.shape[0] * block_size_factor, page_size)
    gpu_tensor[gpu_start : gpu_start + count].copy_(
        cpu_view[cpu_logical_start : cpu_logical_start + count], non_blocking=True
    )


def run_case(
    *,
    device: torch.device,
    num_tensors: int,
    num_gpu_blocks: int,
    num_cpu_blocks: int,
    page_size: int,
    block_size_factor: int,
    transfer_blocks: int,
    offset: int,
    repeats: int,
    mode: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "num_tensors": num_tensors,
        "num_gpu_blocks": num_gpu_blocks,
        "num_cpu_blocks": num_cpu_blocks,
        "page_size": page_size,
        "block_size_factor": block_size_factor,
        "transfer_blocks": transfer_blocks,
        "offset": offset,
        "repeats": repeats,
        "mode": mode,
        "ok": False,
    }

    logical_capacity = num_cpu_blocks * block_size_factor
    if offset + transfer_blocks > min(num_gpu_blocks, logical_capacity):
        result["error"] = "transfer range exceeds GPU or CPU logical capacity"
        return result

    if not hasattr(torch, "xpu") or not torch.xpu.is_available():
        result["error"] = "torch.xpu unavailable"
        return result

    try:
        gpu_tensors = [
            make_pattern(num_gpu_blocks, page_size, device) + tensor_idx
            for tensor_idx in range(num_tensors)
        ]
        cpu_tensors = [
            torch.zeros(
                (num_cpu_blocks, page_size * block_size_factor),
                dtype=torch.int8,
                device="cpu",
                pin_memory=True,
            )
            for _ in range(num_tensors)
        ]
        restored_tensors = [
            torch.empty_like(gpu_tensor, device=device) for gpu_tensor in gpu_tensors
        ]
        for restored in restored_tensors:
            restored.fill_(-1)

        gpu_ids = torch.arange(offset, offset + transfer_blocks, dtype=torch.int64)
        cpu_logical_ids = torch.arange(
            offset, offset + transfer_blocks, dtype=torch.int64
        )

        stream = torch.xpu.Stream()
        Event = torch.xpu.Event
        start_event = Event(enable_timing=True)
        after_store_event = Event(enable_timing=True)
        end_event = Event(enable_timing=True)

        # Warm one tiny copy so stream/context setup is not counted as heavily.
        with torch.xpu.stream(stream):
            cpu_tensors[0][0, :page_size].copy_(gpu_tensors[0][0], non_blocking=True)
        stream.synchronize()

        t0 = time.perf_counter()
        with torch.xpu.stream(stream):
            start_event.record()
            for _ in range(repeats):
                for gpu_tensor, cpu_tensor in zip(gpu_tensors, cpu_tensors):
                    if mode == "slice":
                        copy_gpu_to_cpu_slice(
                            gpu_tensor,
                            cpu_tensor,
                            offset,
                            offset,
                            transfer_blocks,
                            block_size_factor,
                        )
                    elif mode == "indexed":
                        copy_gpu_to_cpu_indexed(
                            gpu_tensor,
                            cpu_tensor,
                            gpu_ids,
                            cpu_logical_ids,
                            block_size_factor,
                        )
                    else:
                        copy_gpu_to_cpu(
                            gpu_tensor,
                            cpu_tensor,
                            gpu_ids,
                            cpu_logical_ids,
                            block_size_factor,
                        )
            after_store_event.record()
            for _ in range(repeats):
                for cpu_tensor, restored in zip(cpu_tensors, restored_tensors):
                    if mode == "slice":
                        copy_cpu_to_gpu_slice(
                            cpu_tensor,
                            restored,
                            offset,
                            offset,
                            transfer_blocks,
                            block_size_factor,
                        )
                    elif mode == "indexed":
                        copy_cpu_to_gpu_indexed(
                            cpu_tensor,
                            restored,
                            cpu_logical_ids,
                            gpu_ids,
                            block_size_factor,
                        )
                    else:
                        copy_cpu_to_gpu(
                            cpu_tensor,
                            restored,
                            cpu_logical_ids,
                            gpu_ids,
                            block_size_factor,
                        )
            end_event.record()
        stream.synchronize()
        t1 = time.perf_counter()

        expected_slices = [
            gpu_tensor[offset : offset + transfer_blocks] for gpu_tensor in gpu_tensors
        ]
        restored_slices = [
            restored[offset : offset + transfer_blocks] for restored in restored_tensors
        ]
        ok = all(
            torch.equal(expected, restored)
            for expected, restored in zip(expected_slices, restored_slices)
        )

        transfer_bytes_one_way = num_tensors * transfer_blocks * page_size * repeats
        store_ms = start_event.elapsed_time(after_store_event)
        load_ms = after_store_event.elapsed_time(end_event)
        result.update(
            {
                "ok": bool(ok),
                "cpu_tensors_pinned": all(t.is_pinned() for t in cpu_tensors),
                "transfer_bytes_one_way": transfer_bytes_one_way,
                "wall_seconds_roundtrip": t1 - t0,
                "wall_roundtrip_gbps": gbps(transfer_bytes_one_way * 2, t1 - t0),
                "event_store_gpu_to_cpu_ms": store_ms,
                "event_load_cpu_to_gpu_ms": load_ms,
                "event_store_gpu_to_cpu_gbps": gbps(
                    transfer_bytes_one_way, store_ms / 1000.0
                ),
                "event_load_cpu_to_gpu_gbps": gbps(
                    transfer_bytes_one_way, load_ms / 1000.0
                ),
            }
        )
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device-index", type=int, default=0)
    parser.add_argument("--num-tensors", type=int, default=4)
    parser.add_argument("--num-gpu-blocks", type=int, default=2048)
    parser.add_argument("--num-cpu-blocks", type=int, default=1024)
    parser.add_argument("--page-size", type=int, default=16 * 1024)
    parser.add_argument("--block-size-factor", type=int, default=2)
    parser.add_argument("--transfer-blocks", type=int, nargs="+", default=[64, 256, 1024])
    parser.add_argument("--offset", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=4)
    parser.add_argument(
        "--mode", choices=["loop", "indexed", "slice"], default="slice"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report: dict[str, Any] = {
        "torch_version": torch.__version__,
        "has_torch_xpu": hasattr(torch, "xpu"),
        "args": vars(args) | {"output": str(args.output) if args.output else None},
    }

    if not hasattr(torch, "xpu") or not torch.xpu.is_available():
        report["error"] = "torch.xpu unavailable"
    else:
        device = torch.device(f"xpu:{args.device_index}")
        report["device"] = str(device)
        try:
            report["device_name"] = torch.xpu.get_device_name(args.device_index)
        except Exception as exc:  # noqa: BLE001
            report["device_name_error"] = f"{type(exc).__name__}: {exc}"
        report["cases"] = [
            run_case(
                device=device,
                num_tensors=args.num_tensors,
                num_gpu_blocks=args.num_gpu_blocks,
                num_cpu_blocks=args.num_cpu_blocks,
                page_size=args.page_size,
                block_size_factor=args.block_size_factor,
                transfer_blocks=blocks,
                offset=args.offset,
                repeats=args.repeats,
                mode=args.mode,
            )
            for blocks in args.transfer_blocks
        ]

    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")

    if report.get("error"):
        return 1
    cases = report.get("cases", [])
    return 0 if cases and all(case.get("ok") for case in cases) else 2


if __name__ == "__main__":
    raise SystemExit(main())
