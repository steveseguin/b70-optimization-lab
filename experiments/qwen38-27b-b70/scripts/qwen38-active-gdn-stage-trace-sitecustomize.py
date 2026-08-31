"""Trace the exact active five-argument packaged XPU GDN forward."""

import hashlib
import json
import os
from pathlib import Path

OUTPUT = os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_OUT")
TARGET_CALL = int(os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_CALL", "2"))
TARGET_LAYER = int(os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_LAYER", "0"))

if OUTPUT:
    import torch
    from vllm.model_executor.layers.mamba.gdn import qwen_gdn_linear_attn as qgdn
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
        call_index = getattr(self, "_neural_download_active_gdn_call", 0)
        self._neural_download_active_gdn_call = call_index + 1
        if self.layer_idx != TARGET_LAYER or call_index != TARGET_CALL:
            return _original_forward_xpu(self, hidden_states)

        num_tokens = hidden_states.size(0)
        projected_qkvz, _ = self.in_proj_qkvz(hidden_states)
        if qgdn._use_deterministic_xpu_quantized_prefill(num_tokens):
            projected_ba = qgdn._deterministic_xpu_quantized_prefill(
                self.in_proj_ba, hidden_states
            )
        else:
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
            self.prefix,
        )
        original_shape = output_gate.shape
        core_2d = core_pre_norm.reshape(-1, core_pre_norm.shape[-1])
        gate_2d = output_gate.reshape(-1, output_gate.shape[-1])
        after_norm_2d = self.norm(core_2d, gate_2d)
        after_norm = after_norm_2d.reshape(original_shape)
        flattened = after_norm.flatten(-2)
        if qgdn._use_deterministic_xpu_quantized_prefill(num_tokens):
            output = qgdn._deterministic_xpu_quantized_prefill(
                self.out_proj, flattened
            )
        else:
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
            "schema": "neural.download.qwen38-active-gdn-stage-trace.raw.v1",
            "call_index": call_index,
            "layer_index": self.layer_idx,
            "positions": {"boundary": "active-five-argument-gdn-stages"},
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
