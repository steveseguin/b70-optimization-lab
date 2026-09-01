"""Diagnostic-only compiled-piece row mapping for Qwen3.8 R77."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import weakref
from typing import Any


_ENABLED = os.environ.get("VLLM_XPU_PW_BOUNDARY_TRACE", "0") == "1"


if _ENABLED:
    import torch

    from vllm.compilation.piecewise_backend import PiecewiseBackend

    _ORIGINAL_CALL = PiecewiseBackend.__call__
    _LOCK = threading.Lock()
    _CALL_COUNTS: weakref.WeakKeyDictionary[Any, int] = weakref.WeakKeyDictionary()
    _LINES = 0

    def _env_int(name: str, default: int) -> int:
        try:
            return int(os.environ.get(name, str(default)) or str(default))
        except ValueError:
            return default

    def _rank() -> int:
        try:
            from vllm.distributed import get_tensor_model_parallel_rank

            return int(get_tensor_model_parallel_rank())
        except Exception:
            try:
                return int(os.environ.get("LOCAL_RANK", "0") or "0")
            except ValueError:
                return 0

    def _tensor_record(tensor: torch.Tensor) -> dict[str, Any]:
        value = tensor.detach()
        requested_row = _env_int("VLLM_XPU_PW_BOUNDARY_TRACE_ROW", 0)
        record: dict[str, Any] = {
            "shape": list(value.shape),
            "stride": list(value.stride()),
            "dtype": str(value.dtype),
            "device": str(value.device),
            "requested_row": requested_row,
        }
        if value.numel() == 0:
            record["empty"] = True
            return record

        # Record tiny one-dimensional inputs in full. Piece zero's first input
        # is the packed token-id vector, so this proves request-to-row mapping
        # without guessing from scheduler admission order.
        if value.ndim == 1 and value.numel() <= 16:
            try:
                record["all_values"] = value.contiguous().cpu().tolist()
            except Exception as exc:
                record["all_values_error"] = repr(exc)

        if value.ndim == 0:
            if requested_row != 0:
                record["digest_skipped"] = "scalar-row-out-of-range"
                return record
            row = value
        else:
            if requested_row < 0 or requested_row >= value.shape[0]:
                record["digest_skipped"] = "row-out-of-range"
                return record
            row = value[requested_row]
        max_numel = _env_int("VLLM_XPU_PW_BOUNDARY_TRACE_MAX_ROW_NUMEL", 65536)
        record["row_numel"] = int(row.numel())
        if max_numel > 0 and row.numel() > max_numel:
            record["digest_skipped"] = "row_numel"
            return record
        try:
            native = row.contiguous().cpu().reshape(-1)
            raw = native.view(torch.uint8).numpy().tobytes()
            record["row_sha256"] = hashlib.sha256(raw).hexdigest()
            head = _env_int("VLLM_XPU_PW_BOUNDARY_TRACE_HEAD", 4)
            if head > 0:
                record["head"] = native[:head].to(torch.float32).tolist()
        except Exception as exc:
            record["digest_error"] = repr(exc)
        return record

    def _tensor_records(value: Any, limit: int) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []

        def visit(item: Any, path: str) -> None:
            if len(records) >= limit:
                return
            if isinstance(item, torch.Tensor):
                records.append({"path": path, **_tensor_record(item)})
            elif isinstance(item, (tuple, list)):
                for index, child in enumerate(item):
                    visit(child, f"{path}[{index}]")
            elif isinstance(item, dict):
                for key, child in item.items():
                    visit(child, f"{path}.{key}")

        visit(value, "$")
        return records

    def _trace_call(backend: Any, *args: Any) -> Any:
        global _LINES
        output = _ORIGINAL_CALL(backend, *args)
        rank = _rank()
        rank_filter = os.environ.get("VLLM_XPU_PW_BOUNDARY_TRACE_RANK", "0")
        if rank_filter not in ("*", "all", str(rank)):
            return output

        with _LOCK:
            call_index = _CALL_COUNTS.get(backend, 0)
            _CALL_COUNTS[backend] = call_index + 1
            max_lines = _env_int("VLLM_XPU_PW_BOUNDARY_TRACE_MAX_LINES", 30000)
            if max_lines > 0 and _LINES >= max_lines:
                return output
            _LINES += 1

        tensor_limit = _env_int("VLLM_XPU_PW_BOUNDARY_TRACE_TENSOR_LIMIT", 4)
        vllm_backend = getattr(backend, "vllm_backend", None)
        record = {
            "schema": "neural.download.qwen38-piecewise-row-map-trace.v1",
            "ts": time.time(),
            "pid": os.getpid(),
            "tp_rank": rank,
            "trace_row": _env_int("VLLM_XPU_PW_BOUNDARY_TRACE_ROW", 0),
            "model_prefix": getattr(vllm_backend, "prefix", ""),
            "piecewise_index": getattr(backend, "piecewise_compile_index", None),
            "total_piecewise_compiles": getattr(backend, "total_piecewise_compiles", None),
            "submod_name": getattr(backend, "submod_name", ""),
            "call_index": call_index,
            "inputs": _tensor_records(args, tensor_limit),
            "outputs": _tensor_records(output, tensor_limit),
        }
        os.write(
            2,
            (
                "NEURAL_DOWNLOAD_PWTRACE "
                + json.dumps(record, separators=(",", ":"), default=str)
                + "\n"
            ).encode("utf-8"),
        )
        return output

    PiecewiseBackend.__call__ = _trace_call
