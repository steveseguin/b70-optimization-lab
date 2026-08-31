"""Capture every decoder-layer boundary at one late decode call."""

import hashlib
import json
import os
from pathlib import Path

OUTPUT = os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_OUT")
TARGET_CALL = int(os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_CALL", "62"))

if OUTPUT:
    import torch
    from vllm.model_executor.models.qwen3_5 import Qwen3_5DecoderLayer

    _original_forward = Qwen3_5DecoderLayer.forward
    _snapshots = {}

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
        call_index = getattr(self, "_neural_download_all_layer_call", 0)
        self._neural_download_all_layer_call = call_index + 1
        input_tensor = kwargs.get("hidden_states", args[0] if args else None)
        result = _original_forward(self, *args, **kwargs)
        if call_index != TARGET_CALL:
            return result

        hidden_states, residual = result
        if not all(
            isinstance(value, torch.Tensor)
            for value in (input_tensor, hidden_states, residual)
        ):
            raise RuntimeError("D40 expected tensor decoder boundaries")
        _snapshots[self.layer_idx] = {
            "input": input_tensor.detach().clone(),
            "hidden": hidden_states.detach().clone(),
            "residual": residual.detach().clone(),
        }
        if self.layer_idx != 63:
            return result

        if sorted(_snapshots) != list(range(64)):
            raise RuntimeError(f"D40 missing layers: {sorted(_snapshots)}")
        positions = kwargs.get("positions", args[2] if len(args) > 2 else None)
        stages = {}
        for layer_idx in range(64):
            for boundary, tensor in _snapshots[layer_idx].items():
                stages[f"layer_{layer_idx:02d}_{boundary}"] = _hash_tensor(tensor)
        payload = {
            "schema": "neural.download.qwen38-all-decoder-layers.raw.v1",
            "call_index": call_index,
            "layer_index": 63,
            "positions": _hash_tensor(positions),
            "hidden_states": stages["layer_63_hidden"],
            "residual": stages["layer_63_residual"],
            "stages": stages,
        }
        destination = Path(OUTPUT)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        os.replace(temporary, destination)
        return result

    Qwen3_5DecoderLayer.forward = _forward_and_trace
