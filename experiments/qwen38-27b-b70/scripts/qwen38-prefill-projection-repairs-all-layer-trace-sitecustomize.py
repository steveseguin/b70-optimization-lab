"""Repair medium-prefill INT4 projections and trace every decoder layer."""

import hashlib
import json
import os
from pathlib import Path

OUTPUT = os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_OUT")
TARGET_CALL = int(os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_CALL", "2"))
PAD_TOKENS = 512

if OUTPUT:
    import torch
    from vllm.model_executor.models.qwen2_moe import Qwen2MoeMLP
    from vllm.model_executor.models.qwen3_5 import Qwen3_5DecoderLayer
    from vllm.model_executor.models.qwen3_next import Qwen3NextAttention

    _original_mlp_forward = Qwen2MoeMLP.forward
    _original_attention_forward = Qwen3NextAttention.forward

    def _in_repair_band(tensor):
        return (
            tensor.device.type == "xpu"
            and tensor.ndim == 2
            and 32 < tensor.shape[0] < PAD_TOKENS
        )

    def _mlp_forward_with_deterministic_down(self, x):
        if not _in_repair_band(x) or self.expert_gate is not None:
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

    def _attention_forward_with_deterministic_projections(
        self, positions, hidden_states
    ):
        if not _in_repair_band(hidden_states):
            return _original_attention_forward(self, positions, hidden_states)
        num_tokens = hidden_states.shape[0]
        padded_hidden = torch.zeros(
            (PAD_TOKENS, hidden_states.shape[-1]),
            dtype=hidden_states.dtype,
            device=hidden_states.device,
        )
        padded_hidden[:num_tokens].copy_(hidden_states)
        torch.xpu.synchronize()
        padded_qkv, _ = self.qkv_proj(padded_hidden)
        torch.xpu.synchronize()
        qkv = padded_qkv[:num_tokens]
        q, k, v, gate = self._project_qkv_gate(qkv, positions)
        attention_output = self.attn(q, k, v)
        if gate is not None:
            attention_output = attention_output * torch.sigmoid(gate)
        padded_attention = torch.zeros(
            (PAD_TOKENS, attention_output.shape[-1]),
            dtype=attention_output.dtype,
            device=attention_output.device,
        )
        padded_attention[:num_tokens].copy_(attention_output)
        torch.xpu.synchronize()
        padded_output, _ = self.o_proj(padded_attention)
        torch.xpu.synchronize()
        return padded_output[:num_tokens]

    Qwen2MoeMLP.forward = _mlp_forward_with_deterministic_down
    Qwen3NextAttention.forward = _attention_forward_with_deterministic_projections
    _original_decoder_forward = Qwen3_5DecoderLayer.forward
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

    def _decoder_forward_and_trace(self, *args, **kwargs):
        call_index = getattr(self, "_neural_download_prefill_layer_call", 0)
        self._neural_download_prefill_layer_call = call_index + 1
        input_tensor = kwargs.get("hidden_states", args[0] if args else None)
        result = _original_decoder_forward(self, *args, **kwargs)
        if call_index != TARGET_CALL:
            return result

        hidden_states, residual = result
        if not all(
            isinstance(value, torch.Tensor)
            for value in (input_tensor, hidden_states, residual)
        ):
            raise RuntimeError("D53 expected tensor decoder boundaries")
        _snapshots[self.layer_idx] = {
            "input": _hash_tensor(input_tensor),
            "hidden": _hash_tensor(hidden_states),
            "residual": _hash_tensor(residual),
        }
        if self.layer_idx != 63:
            return result

        if sorted(_snapshots) != list(range(64)):
            raise RuntimeError(f"D53 missing layers: {sorted(_snapshots)}")
        positions = kwargs.get("positions", args[2] if len(args) > 2 else None)
        stages = {}
        for layer_idx in range(64):
            for boundary, digest in _snapshots[layer_idx].items():
                stages[f"layer_{layer_idx:02d}_{boundary}"] = digest
        payload = {
            "schema": "neural.download.qwen38-prefill-projection-repairs.raw.v1",
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

    Qwen3_5DecoderLayer.forward = _decoder_forward_and_trace
