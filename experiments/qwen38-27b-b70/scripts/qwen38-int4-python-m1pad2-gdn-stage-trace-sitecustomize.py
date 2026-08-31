"""Diagnostic INT4 M=1 padding plus production XPU GDN stage trace."""

import hashlib
import json
import os
from pathlib import Path

OUTPUT = os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_OUT")
TARGET_CALL = int(os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_CALL", "2"))
TARGET_LAYER = int(os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_LAYER", "0"))

if OUTPUT:
    import torch
    from vllm.model_executor.layers.quantization.inc.schemes.inc_wna16_linear import (
        INCXPULinearMethod,
    )
    from vllm.model_executor.models.qwen3_5 import QwenGatedDeltaNetAttention

    _original_apply_weights = INCXPULinearMethod.apply_weights

    def _apply_weights_with_python_m1_pad(
        self, layer, x, bias=None
    ):
        reshaped_x = x.reshape(-1, x.shape[-1])
        if reshaped_x.shape[0] != 1:
            return _original_apply_weights(self, layer, x, bias)

        out_shape = x.shape[:-1] + (layer.qweight.shape[1],)
        padded_x = reshaped_x.new_zeros((2, reshaped_x.shape[1]))
        padded_x[0].copy_(reshaped_x[0])
        padded_out = _original_apply_weights(self, layer, padded_x, bias)
        return padded_out[:1].reshape(out_shape)

    INCXPULinearMethod.apply_weights = _apply_weights_with_python_m1_pad

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
        call_index = getattr(self, "_neural_download_gdn_stage_call", 0)
        self._neural_download_gdn_stage_call = call_index + 1
        if self.layer_idx != TARGET_LAYER or call_index != TARGET_CALL:
            return _original_forward_xpu(self, hidden_states)

        num_tokens = hidden_states.size(0)
        projected_qkvz, _ = self.in_proj_qkvz(hidden_states)
        projected_ba, _ = self.in_proj_ba(hidden_states)
        core_pre_norm = torch.zeros(
            (num_tokens, self.num_v_heads // self.tp_size, self.head_v_dim),
            dtype=hidden_states.dtype,
            device=hidden_states.device,
        )
        output_gate = torch.empty_like(core_pre_norm)
        torch.ops.vllm.gdn_attention_core_xpu(
            core_pre_norm,
            output_gate,
            projected_qkvz,
            projected_ba,
            self._xpu_conv_state,
            self._xpu_ssm_state,
            self.prefix,
        )
        original_shape = output_gate.shape
        core_2d = core_pre_norm.reshape(-1, core_pre_norm.shape[-1])
        gate_2d = output_gate.reshape(-1, output_gate.shape[-1])
        after_norm_2d = self.norm(core_2d, gate_2d)
        after_norm = after_norm_2d.reshape(original_shape)
        flattened = after_norm.flatten(-2)
        output, _ = self.out_proj(flattened)

        stages = {
            "hidden_input": _hash_tensor(hidden_states),
            "projected_qkvz": _hash_tensor(projected_qkvz),
            "projected_ba": _hash_tensor(projected_ba),
            "core_pre_norm": _hash_tensor(core_pre_norm),
            "output_gate": _hash_tensor(output_gate),
            "after_norm": _hash_tensor(after_norm),
            "flattened": _hash_tensor(flattened),
            "output": _hash_tensor(output),
        }
        payload = {
            "schema": "neural.download.qwen38-gdn-stage-trace.raw.v1",
            "call_index": call_index,
            "layer_index": self.layer_idx,
            "positions": {"boundary": "gdn-stages"},
            "hidden_states": stages["output"],
            "residual": stages["core_pre_norm"],
            "stages": stages,
        }
        destination = Path(OUTPUT)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        os.replace(temporary, destination)
        return output

    QwenGatedDeltaNetAttention.forward_xpu = _forward_xpu_and_trace
