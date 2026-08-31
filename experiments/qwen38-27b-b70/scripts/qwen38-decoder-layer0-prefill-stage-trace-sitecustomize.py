"""Synchronizing stage trace for layer-0 Qwen3.5 decoder prefill."""

import hashlib
import json
import os
from pathlib import Path

OUTPUT = os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_OUT")
TARGET_CALL = int(os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_CALL", "2"))
TARGET_LAYER = int(os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_LAYER", "0"))

if OUTPUT:
    import torch
    from vllm.model_executor.models.qwen3_5 import Qwen3_5DecoderLayer

    _original_forward = Qwen3_5DecoderLayer.forward

    def _hash_tensor(tensor):
        value = tensor.detach()
        raw = value.contiguous().cpu().reshape(-1).view(torch.uint8)
        return {
            "dtype": str(value.dtype),
            "shape": list(value.shape),
            "stride": list(value.stride()),
            "sha256": hashlib.sha256(raw.numpy().tobytes()).hexdigest(),
        }

    def _forward_and_trace(self, hidden_states, residual, positions=None, **kwargs):
        call_index = getattr(self, "_neural_download_layer_stage_call", 0)
        self._neural_download_layer_stage_call = call_index + 1
        if self.layer_idx != TARGET_LAYER or call_index != TARGET_CALL:
            return _original_forward(
                self,
                hidden_states,
                residual,
                positions=positions,
                **kwargs,
            )

        # D45 is a TP1 dense-model diagnostic. Fail closed rather than silently
        # diverging from the production forward if that preregistered shape
        # changes.
        assert not self.use_attn_reduce_scatter_for_moe
        assert not self.layer_scale
        assert self.layer_type == "linear_attention"

        stages = {"hidden_input": _hash_tensor(hidden_states)}
        if residual is None:
            residual = hidden_states
            hidden_states = self.input_layernorm(hidden_states)
        else:
            hidden_states, residual = self.input_layernorm(hidden_states, residual)
        stages["after_input_norm"] = _hash_tensor(hidden_states)
        stages["residual_after_input_norm"] = _hash_tensor(residual)

        hidden_states = self.linear_attn(hidden_states=hidden_states)
        stages["attention_output"] = _hash_tensor(hidden_states)

        hidden_states, residual = self.post_attention_layernorm(
            hidden_states, residual
        )
        stages["after_post_attention_norm"] = _hash_tensor(hidden_states)
        stages["residual_after_attention"] = _hash_tensor(residual)

        hidden_states = self.mlp(hidden_states)
        stages["mlp_output"] = _hash_tensor(hidden_states)

        payload = {
            "schema": "neural.download.qwen38-decoder-layer-stage-trace.raw.v1",
            "call_index": call_index,
            "layer_index": self.layer_idx,
            "positions": _hash_tensor(positions),
            "hidden_states": stages["mlp_output"],
            "residual": stages["residual_after_attention"],
            "stages": stages,
        }
        destination = Path(OUTPUT)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        os.replace(temporary, destination)
        return hidden_states, residual

    Qwen3_5DecoderLayer.forward = _forward_and_trace
