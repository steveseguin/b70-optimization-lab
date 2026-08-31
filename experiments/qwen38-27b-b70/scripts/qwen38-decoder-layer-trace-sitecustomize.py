"""Diagnostic-only selected decoder-layer trace installed as sitecustomize."""

import hashlib
import json
import os
from pathlib import Path

OUTPUT = os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_OUT")
TARGET_CALL = int(os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_CALL", "60"))
TARGET_LAYER = int(os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_LAYER", "31"))

if OUTPUT:
    import torch
    from vllm.model_executor.models.qwen3_5 import Qwen3_5DecoderLayer

    _original_forward = Qwen3_5DecoderLayer.forward

    def _hash_tensor(tensor):
        value = tensor.detach()
        raw = value.contiguous().cpu().reshape(-1).view(torch.uint8)
        return {
            "dtype": str(value.dtype), "shape": list(value.shape),
            "stride": list(value.stride()),
            "sha256": hashlib.sha256(raw.numpy().tobytes()).hexdigest(),
        }

    def _forward_and_trace(self, *args, **kwargs):
        call_index = getattr(self, "_neural_download_layer_trace_call", 0)
        self._neural_download_layer_trace_call = call_index + 1
        result = _original_forward(self, *args, **kwargs)
        if self.layer_idx == TARGET_LAYER and call_index == TARGET_CALL:
            hidden_states, residual = result
            positions = kwargs.get("positions", args[2] if len(args) > 2 else None)
            if not all(isinstance(x, torch.Tensor) for x in
                       (hidden_states, residual, positions)):
                raise RuntimeError("D10 expected tensor layer outputs and positions")
            payload = {
                "schema": "neural.download.qwen38-decoder-layer-trace.raw.v1",
                "call_index": call_index, "layer_index": self.layer_idx,
                "positions": _hash_tensor(positions),
                "hidden_states": _hash_tensor(hidden_states),
                "residual": _hash_tensor(residual),
            }
            destination = Path(OUTPUT)
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            os.replace(temporary, destination)
        return result

    Qwen3_5DecoderLayer.forward = _forward_and_trace
