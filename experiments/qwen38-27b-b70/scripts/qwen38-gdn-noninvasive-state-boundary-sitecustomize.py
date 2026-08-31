"""Hash one GDN production forward boundary without reconstructing the call."""

import hashlib
import json
import os
from pathlib import Path

OUTPUT = os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_OUT")
TARGET_CALL = int(os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_CALL", "2"))
TARGET_LAYER = int(os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_LAYER", "0"))

if OUTPUT:
    import torch
    from vllm.model_executor.models.qwen3_5 import QwenGatedDeltaNetAttention

    _original_forward_xpu = QwenGatedDeltaNetAttention.forward_xpu

    def _hash_tensor(tensor):
        value = tensor.detach()
        raw = value.contiguous().cpu().reshape(-1).view(torch.uint8)
        return {
            "dtype": str(value.dtype),
            "shape": list(value.shape),
            "stride": list(value.stride()),
            "sha256": hashlib.sha256(raw.numpy().tobytes()).hexdigest(),
        }

    def _forward_xpu_and_trace(self, hidden_states):
        call_index = getattr(self, "_neural_download_gdn_boundary_call", 0)
        self._neural_download_gdn_boundary_call = call_index + 1
        if self.layer_idx != TARGET_LAYER or call_index != TARGET_CALL:
            return _original_forward_xpu(self, hidden_states)

        stages = {
            "hidden_input": _hash_tensor(hidden_states),
            "conv_state_before": _hash_tensor(self._xpu_conv_state),
            "ssm_state_before": _hash_tensor(self._xpu_ssm_state),
        }
        output = _original_forward_xpu(self, hidden_states)
        stages.update({
            "output": _hash_tensor(output),
            "conv_state_after": _hash_tensor(self._xpu_conv_state),
            "ssm_state_after": _hash_tensor(self._xpu_ssm_state),
        })
        payload = {
            "schema": "neural.download.qwen38-gdn-production-state-boundary.raw.v1",
            "call_index": call_index,
            "layer_index": self.layer_idx,
            "positions": {"boundary": "production-gdn-before-after"},
            "hidden_states": stages["hidden_input"],
            "residual": stages["output"],
            "stages": stages,
        }
        destination = Path(OUTPUT)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        os.replace(temporary, destination)
        return output

    QwenGatedDeltaNetAttention.forward_xpu = _forward_xpu_and_trace
