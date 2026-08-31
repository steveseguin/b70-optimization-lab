"""Keep the dense-MLP repair active and split layer-3 prefill stages."""

import hashlib
import json
import os
from pathlib import Path

OUTPUT = os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_OUT")
TARGET_CALL = int(os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_CALL", "2"))
TARGET_LAYER = int(os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_LAYER", "3"))
PAD_TOKENS = 512

if OUTPUT:
    import torch
    from vllm.model_executor.models.qwen2_moe import Qwen2MoeMLP
    from vllm.model_executor.models.qwen3_5 import Qwen3_5DecoderLayer

    _original_mlp_forward = Qwen2MoeMLP.forward

    def _mlp_forward_with_deterministic_down(self, x):
        if (
            x.device.type != "xpu"
            or x.ndim != 2
            or not (32 < x.shape[0] < PAD_TOKENS)
            or self.expert_gate is not None
        ):
            return _original_mlp_forward(self, x)
        num_tokens = x.shape[0]
        torch.xpu.synchronize()
        gate_up, _ = self.gate_up_proj(x)
        torch.xpu.synchronize()
        activated = self.act_fn(gate_up)
        padded = torch.zeros(
            (PAD_TOKENS, activated.shape[-1]),
            dtype=activated.dtype,
            device=activated.device,
        )
        padded[:num_tokens].copy_(activated)
        torch.xpu.synchronize()
        padded_output, _ = self.down_proj(padded)
        torch.xpu.synchronize()
        return padded_output[:num_tokens]

    Qwen2MoeMLP.forward = _mlp_forward_with_deterministic_down
    _original_decoder_forward = Qwen3_5DecoderLayer.forward

    def _hash_tensor(tensor):
        value = tensor.detach()
        raw = value.contiguous().cpu().reshape(-1).view(torch.uint8)
        return {
            "dtype": str(value.dtype),
            "shape": list(value.shape),
            "stride": list(value.stride()),
            "sha256": hashlib.sha256(raw.numpy().tobytes()).hexdigest(),
        }

    def _decoder_forward_and_trace(
        self, hidden_states, residual, positions=None, **kwargs
    ):
        call_index = getattr(self, "_neural_download_layer_stage_call", 0)
        self._neural_download_layer_stage_call = call_index + 1
        if self.layer_idx != TARGET_LAYER or call_index != TARGET_CALL:
            return _original_decoder_forward(
                self,
                hidden_states,
                residual,
                positions=positions,
                **kwargs,
            )

        # D51 is a TP1 dense-model diagnostic at the first full-attention
        # layer. Fail closed if that preregistered production shape changes.
        assert not self.use_attn_reduce_scatter_for_moe
        assert not self.layer_scale
        assert self.layer_type == "full_attention"

        stages = {"hidden_input": _hash_tensor(hidden_states)}
        if residual is None:
            residual = hidden_states
            hidden_states = self.input_layernorm(hidden_states)
        else:
            hidden_states, residual = self.input_layernorm(hidden_states, residual)
        stages["after_input_norm"] = _hash_tensor(hidden_states)
        stages["residual_after_input_norm"] = _hash_tensor(residual)

        hidden_states = self.self_attn(
            hidden_states=hidden_states,
            positions=positions,
        )
        stages["attention_output"] = _hash_tensor(hidden_states)

        hidden_states, residual = self.post_attention_layernorm(
            hidden_states, residual
        )
        stages["after_post_attention_norm"] = _hash_tensor(hidden_states)
        stages["residual_after_attention"] = _hash_tensor(residual)

        hidden_states = self.mlp(hidden_states)
        stages["mlp_output"] = _hash_tensor(hidden_states)

        payload = {
            "schema": "neural.download.qwen38-mlppad-layer3-stage-trace.raw.v1",
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

    Qwen3_5DecoderLayer.forward = _decoder_forward_and_trace
