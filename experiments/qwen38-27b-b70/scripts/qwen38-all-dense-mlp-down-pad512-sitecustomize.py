"""Apply synchronized M=512 down projection to every dense MLP prefill."""

import hashlib
import json
import os
from pathlib import Path

OUTPUT = os.environ.get("VLLM_XPU_DECODER_LAYER_TRACE_OUT")
PAD_TOKENS = 512

if OUTPUT:
    import torch
    from vllm.model_executor.models.qwen2_moe import Qwen2MoeMLP

    _original_forward = Qwen2MoeMLP.forward
    _trace_written = False

    def _hash_tensor(tensor):
        value = tensor.detach()
        raw = value.contiguous().cpu().reshape(-1).view(torch.uint8)
        return {
            "dtype": str(value.dtype),
            "shape": list(value.shape),
            "stride": list(value.stride()),
            "sha256": hashlib.sha256(raw.numpy().tobytes()).hexdigest(),
        }

    def _forward_with_deterministic_down(self, x):
        global _trace_written
        if (
            x.device.type != "xpu"
            or x.ndim != 2
            or not (32 < x.shape[0] < PAD_TOKENS)
            or self.expert_gate is not None
        ):
            return _original_forward(self, x)

        num_tokens = x.shape[0]
        # Bracket each cross-stream oneDNN primitive while validating the safe
        # model-wide repair. D50 will replace host completion with asynchronous
        # event dependencies after the complete-output gate passes.
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
        output = padded_output[:num_tokens]

        if not _trace_written:
            stages = {
                "mlp_input": _hash_tensor(x),
                "down_pad512_output": _hash_tensor(output),
            }
            payload = {
                "schema": "neural.download.qwen38-all-dense-mlp-pad512.raw.v1",
                "call_index": 2,
                "layer_index": 0,
                "positions": {"boundary": "all-dense-mlp-prefill-pad512"},
                "hidden_states": stages["mlp_input"],
                "residual": stages["down_pad512_output"],
                "stages": stages,
            }
            destination = Path(OUTPUT)
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            temporary.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n"
            )
            os.replace(temporary, destination)
            _trace_written = True
        return output

    Qwen2MoeMLP.forward = _forward_with_deterministic_down
