"""Diagnostic-only CUDAGraph boundary fingerprints for Qwen3.8 R73.

The hook is installed only in a diagnostic image.  It wraps vLLM's Python
CUDAGraph dispatcher, not the captured model graph, and records the first row
of bounded tensor inputs/outputs after each replay.  Records go to stderr so
the ordinary container log remains the complete, host-independent artifact.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import weakref
from typing import Any


_ENABLED = os.environ.get("VLLM_XPU_CG_BOUNDARY_TRACE", "0") == "1"


if _ENABLED:
    import torch

    from vllm.compilation.cuda_graph import CUDAGraphWrapper
    from vllm.forward_context import get_forward_context, is_forward_context_available

    _ORIGINAL_CALL = CUDAGraphWrapper.__call__
    _LOCK = threading.Lock()
    _WRAPPER_IDS: weakref.WeakKeyDictionary[Any, int] = weakref.WeakKeyDictionary()
    _REPLAY_COUNTS: weakref.WeakKeyDictionary[Any, int] = weakref.WeakKeyDictionary()
    _NEXT_WRAPPER_ID = 0
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

    def _wrapper_identity(wrapper: Any) -> tuple[int, int]:
        global _NEXT_WRAPPER_ID
        with _LOCK:
            wrapper_id = _WRAPPER_IDS.get(wrapper)
            if wrapper_id is None:
                wrapper_id = _NEXT_WRAPPER_ID
                _NEXT_WRAPPER_ID += 1
                _WRAPPER_IDS[wrapper] = wrapper_id
            replay_index = _REPLAY_COUNTS.get(wrapper, 0)
            _REPLAY_COUNTS[wrapper] = replay_index + 1
        return wrapper_id, replay_index

    def _tensor_record(tensor: torch.Tensor) -> dict[str, Any]:
        value = tensor.detach()
        record: dict[str, Any] = {
            "shape": list(value.shape),
            "stride": list(value.stride()),
            "dtype": str(value.dtype),
            "device": str(value.device),
        }
        if value.numel() == 0:
            record["empty"] = True
            return record
        row = value if value.ndim == 0 else value[0]
        max_numel = _env_int("VLLM_XPU_CG_BOUNDARY_TRACE_MAX_ROW_NUMEL", 65536)
        record["row_numel"] = int(row.numel())
        if max_numel > 0 and row.numel() > max_numel:
            record["digest_skipped"] = "row_numel"
            return record
        try:
            native = row.contiguous().cpu()
            raw = native.view(torch.uint8).numpy().tobytes()
            record["row_sha256"] = hashlib.sha256(raw).hexdigest()
            flat = native.reshape(-1)
            head = _env_int("VLLM_XPU_CG_BOUNDARY_TRACE_HEAD", 4)
            if head > 0:
                record["head"] = flat[:head].to(torch.float32).tolist()
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

    def _trace_call(wrapper: Any, *args: Any, **kwargs: Any) -> Any:
        global _LINES
        context = get_forward_context() if is_forward_context_available() else None
        descriptor = None if context is None else context.batch_descriptor
        entry = (
            None
            if descriptor is None
            else wrapper.concrete_cudagraph_entries.get(descriptor)
        )
        is_replay = entry is not None and entry.cudagraph is not None
        output = _ORIGINAL_CALL(wrapper, *args, **kwargs)
        if not is_replay:
            return output

        rank = _rank()
        rank_filter = os.environ.get("VLLM_XPU_CG_BOUNDARY_TRACE_RANK", "0")
        if rank_filter not in ("*", "all", str(rank)):
            return output
        max_lines = _env_int("VLLM_XPU_CG_BOUNDARY_TRACE_MAX_LINES", 30000)
        with _LOCK:
            if max_lines > 0 and _LINES >= max_lines:
                return output
            _LINES += 1

        wrapper_id, replay_index = _wrapper_identity(wrapper)
        runnable = wrapper.runnable
        tensor_limit = _env_int("VLLM_XPU_CG_BOUNDARY_TRACE_TENSOR_LIMIT", 4)
        record = {
            "schema": "neural.download.qwen38-cudagraph-boundary-trace.v1",
            "ts": time.time(),
            "pid": os.getpid(),
            "tp_rank": rank,
            "wrapper_id": wrapper_id,
            "replay_index": replay_index,
            "runtime_mode": getattr(wrapper.runtime_mode, "name", str(wrapper.runtime_mode)),
            "batch_descriptor": str(descriptor),
            "submod_name": getattr(runnable, "submod_name", ""),
            "piecewise_index": getattr(runnable, "piecewise_compile_index", None),
            "total_piecewise_compiles": getattr(runnable, "total_piecewise_compiles", None),
            "is_first_graph": getattr(runnable, "is_first_graph", None),
            "is_last_graph": getattr(runnable, "is_last_graph", None),
            "inputs": _tensor_records(args, tensor_limit),
            "outputs": _tensor_records(output, tensor_limit),
        }
        os.write(
            2,
            (
                "NEURAL_DOWNLOAD_CGTRACE "
                + json.dumps(record, separators=(",", ":"), default=str)
                + "\n"
            ).encode("utf-8"),
        )
        return output

    CUDAGraphWrapper.__call__ = _trace_call
