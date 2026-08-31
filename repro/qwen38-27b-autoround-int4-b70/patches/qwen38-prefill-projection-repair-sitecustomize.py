"""Qwen3.8 TP1 medium-prefill INT4 projection determinism repair.

Enable explicitly with ``VLLM_XPU_QWEN38_PREFILL_PROJECTION_REPAIR=1``.
Decode and row counts outside ``32 < M < 512`` retain their original path.
"""

import os


if os.environ.get("VLLM_XPU_QWEN38_PREFILL_PROJECTION_REPAIR") == "1":
    import torch
    from vllm.model_executor.models.qwen2_moe import Qwen2MoeMLP
    from vllm.model_executor.models.qwen3_next import Qwen3NextAttention

    PAD_TOKENS = 512
    SMALL_PAD_TOKENS = int(
        os.environ.get("VLLM_XPU_QWEN38_PREFILL_SMALL_PAD_TOKENS", "512")
    )
    if SMALL_PAD_TOKENS not in (128, 512):
        raise RuntimeError("small prefill pad must be 128 or 512 tokens")
    SYNCHRONIZE = (
        os.environ.get("VLLM_XPU_QWEN38_PREFILL_PROJECTION_SYNCHRONIZE", "1")
        != "0"
    )
    _original_mlp_forward = Qwen2MoeMLP.forward
    _original_attention_forward = Qwen3NextAttention.forward

    def _in_repair_band(tensor):
        return (
            tensor.device.type == "xpu"
            and tensor.ndim == 2
            and 32 < tensor.shape[0] < PAD_TOKENS
        )

    def _sync():
        if SYNCHRONIZE:
            torch.xpu.synchronize()

    def _target_tokens(num_tokens):
        if num_tokens <= SMALL_PAD_TOKENS:
            return SMALL_PAD_TOKENS
        return PAD_TOKENS

    def _mlp_forward_with_deterministic_down(self, x):
        if not _in_repair_band(x) or self.expert_gate is not None:
            return _original_mlp_forward(self, x)
        num_tokens = x.shape[0]
        target_tokens = _target_tokens(num_tokens)
        _sync()
        gate_up, _ = self.gate_up_proj(x)
        _sync()
        activated = self.act_fn(gate_up)
        padded = torch.zeros(
            (target_tokens, activated.shape[-1]),
            dtype=activated.dtype,
            device=activated.device,
        )
        padded[:num_tokens].copy_(activated)
        _sync()
        padded_output, _ = self.down_proj(padded)
        _sync()
        return padded_output[:num_tokens]

    def _attention_forward_with_deterministic_projections(
        self, positions, hidden_states
    ):
        if not _in_repair_band(hidden_states):
            return _original_attention_forward(self, positions, hidden_states)
        num_tokens = hidden_states.shape[0]
        target_tokens = _target_tokens(num_tokens)
        padded_hidden = torch.zeros(
            (target_tokens, hidden_states.shape[-1]),
            dtype=hidden_states.dtype,
            device=hidden_states.device,
        )
        padded_hidden[:num_tokens].copy_(hidden_states)
        _sync()
        padded_qkv, _ = self.qkv_proj(padded_hidden)
        _sync()
        qkv = padded_qkv[:num_tokens]
        q, k, v, gate = self._project_qkv_gate(qkv, positions)
        attention_output = self.attn(q, k, v)
        if gate is not None:
            attention_output = attention_output * torch.sigmoid(gate)
        padded_attention = torch.zeros(
            (target_tokens, attention_output.shape[-1]),
            dtype=attention_output.dtype,
            device=attention_output.device,
        )
        padded_attention[:num_tokens].copy_(attention_output)
        _sync()
        padded_output, _ = self.o_proj(padded_attention)
        _sync()
        return padded_output[:num_tokens]

    Qwen2MoeMLP.forward = _mlp_forward_with_deterministic_down
    Qwen3NextAttention.forward = _attention_forward_with_deterministic_projections
