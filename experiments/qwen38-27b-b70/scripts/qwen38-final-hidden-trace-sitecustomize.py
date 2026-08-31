"""Diagnostic-only final-hidden trace hook installed as sitecustomize.py."""

import hashlib
import json
import os
from pathlib import Path


OUTPUT = os.environ.get("VLLM_XPU_FINAL_HIDDEN_TRACE_OUT")
TARGET_CALL = int(os.environ.get("VLLM_XPU_FINAL_HIDDEN_TRACE_CALL", "60"))

if OUTPUT:
    import torch
    from vllm.model_executor.models.qwen3_5 import Qwen3_5Model

    _original_forward = Qwen3_5Model.forward

    def _hash_tensor(tensor):
        value = tensor.detach()
        raw = value.contiguous().cpu().reshape(-1).view(torch.uint8)
        return {
            "dtype": str(value.dtype),
            "shape": list(value.shape),
            "stride": list(value.stride()),
            "sha256": hashlib.sha256(raw.numpy().tobytes()).hexdigest(),
        }

    def _forward_and_trace(self, *args, **kwargs):
        call_index = getattr(self, "_neural_download_trace_call", 0)
        self._neural_download_trace_call = call_index + 1
        result = _original_forward(self, *args, **kwargs)
        if call_index == TARGET_CALL:
            input_ids = kwargs.get("input_ids", args[0] if args else None)
            positions = kwargs.get("positions", args[1] if len(args) > 1 else None)
            hidden_states = result[0] if isinstance(result, tuple) else result
            if not all(isinstance(x, torch.Tensor) for x in
                       (input_ids, positions, hidden_states)):
                raise RuntimeError("D9 expected tensor inputs and final hidden states")
            payload = {
                "schema": "neural.download.qwen38-final-hidden-trace.raw.v1",
                "call_index": call_index,
                "input_ids": _hash_tensor(input_ids),
                "positions": _hash_tensor(positions),
                "hidden_states": _hash_tensor(hidden_states),
            }
            destination = Path(OUTPUT)
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            os.replace(temporary, destination)
        return result

    Qwen3_5Model.forward = _forward_and_trace
