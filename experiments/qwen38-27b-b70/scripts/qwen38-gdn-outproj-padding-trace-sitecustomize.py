"""Diagnostic-only loaded GDN out-projection row-padding sweep."""

import hashlib
import json
import os
from pathlib import Path

OUTPUT = os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_OUT")
TARGET_CALL = int(os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_CALL", "2"))
TARGET_LAYER = int(os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_LAYER", "0"))
PAD_ROWS = (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)

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

    def _forward_xpu_and_sweep(self, hidden_states):
        call_index = getattr(self, "_neural_download_outproj_sweep_call", 0)
        self._neural_download_outproj_sweep_call = call_index + 1
        if self.layer_idx != TARGET_LAYER or call_index != TARGET_CALL:
            return _original_forward_xpu(self, hidden_states)

        num_tokens = hidden_states.size(0)
        projected_qkvz, _ = self.in_proj_qkvz(hidden_states)
        projected_ba, _ = self.in_proj_ba(hidden_states)
        core = torch.zeros(
            (num_tokens, self.num_v_heads // self.tp_size, self.head_v_dim),
            dtype=hidden_states.dtype,
            device=hidden_states.device,
        )
        gate = torch.empty_like(core)
        torch.ops.vllm.gdn_attention_core_xpu(
            core,
            gate,
            projected_qkvz,
            projected_ba,
            self._xpu_conv_state,
            self._xpu_ssm_state,
            self.prefix,
        )
        shape = gate.shape
        normalized = self.norm(
            core.reshape(-1, core.shape[-1]),
            gate.reshape(-1, gate.shape[-1]),
        ).reshape(shape).flatten(-2)

        retained = {}
        ordinary_output = None
        for rows in PAD_ROWS:
            repeats = []
            for _ in range(2):
                if rows == 1:
                    projection_input = normalized
                else:
                    projection_input = normalized.new_zeros(
                        (rows, normalized.shape[-1])
                    )
                    projection_input[0].copy_(normalized[0])
                projected, _ = self.out_proj(projection_input)
                repeats.append(projected[0])
                if rows == 1 and ordinary_output is None:
                    ordinary_output = projected
            retained[str(rows)] = repeats

        assert ordinary_output is not None
        variants = {
            rows: [_hash_tensor(value) for value in repeats]
            for rows, repeats in retained.items()
        }
        payload = {
            "schema": "neural.download.qwen38-gdn-outproj-padding.raw.v1",
            "call_index": call_index,
            "layer_index": self.layer_idx,
            "positions": {"boundary": "gdn-outproj-padding"},
            "hidden_states": variants["1"][0],
            "residual": _hash_tensor(normalized),
            "variants": variants,
        }
        destination = Path(OUTPUT)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        os.replace(temporary, destination)
        return ordinary_output

    QwenGatedDeltaNetAttention.forward_xpu = _forward_xpu_and_sweep
