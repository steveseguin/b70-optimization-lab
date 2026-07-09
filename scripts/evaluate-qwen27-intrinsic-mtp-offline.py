#!/usr/bin/env python3
"""Offline acceptance probe for Qwen3.6 27B's intrinsic MTP drafter.

This is a diagnostic tool, not a benchmark. It replays short draft rollouts from
recorded target hidden-state sequence shards and measures how often the model's
own MTP module predicts the target stream:

    hidden_state[t] + sampled_next_token_ids[t] -> sampled_next_token_ids[t + 1]

The result answers whether MTP-weight adaptation is a plausible path to higher
accepted tokens per verifier step before spending endpoint/GPU time on vLLM
integration. It must not be submitted or advertised as headline throughput.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
from safetensors.torch import load_file


DEFAULT_MODEL_DIR = (
    "/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/"
    "snapshots/f5750c90b3776db658594df5fe8051098226dd8e"
)
DEFAULT_DATASET_DIR = (
    "/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/"
    "qwen27-eagledata-v2-chat-calib-20260704T101119Z/dataset-metadata-v2"
)
POSITION_FC_KEY_RE = re.compile(r"^mtp\.position_fcs\.(\d+)\.weight$")
POSITION_ADAPTER_KEY_RE = re.compile(
    r"^mtp\.position_adapters\.(\d+)\.(down|up)\.weight$"
)
DIAGNOSTIC_POSITION_FC_ATTR_RE = re.compile(r"^position_fcs\.(\d+)$")
DIAGNOSTIC_POSITION_ADAPTER_ATTR_RE = re.compile(
    r"^position_adapters\.(\d+)\.(down|up)$"
)


@dataclass(frozen=True)
class QwenMTPShape:
    hidden_size: int
    intermediate_size: int
    vocab_size: int
    num_heads: int
    num_kv_heads: int
    head_dim: int
    rms_norm_eps: float
    rope_theta: float
    rope_parameters: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model-dir",
        default=DEFAULT_MODEL_DIR,
        help="Qwen3.6 27B AutoRound snapshot containing model_extra_tensors.",
    )
    parser.add_argument(
        "--model-extra-path",
        default="",
        help=(
            "Optional replacement model_extra_tensors.safetensors, for evaluating "
            "mergeable intrinsic-MTP training candidates."
        ),
    )
    parser.add_argument(
        "--diagnostic-dense-update-path",
        default="",
        help=(
            "Optional diagnostic_dense_updates.safetensors produced by the "
            "offline trainer. Keys are dense.<attribute>; this is not an "
            "endpoint-compatible model artifact."
        ),
    )
    parser.add_argument(
        "--dataset-dir",
        default=[],
        action="append",
        help="Directory containing qwen36_eagle_sequence_v1 .pt files. May repeat.",
    )
    parser.add_argument("--max-steps", type=int, default=3)
    parser.add_argument("--max-samples", type=int, default=0)
    parser.add_argument("--max-starts", type=int, default=256)
    parser.add_argument("--start-stride", type=int, default=1)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--dtype", default="bfloat16",
                        choices=("float32", "bfloat16", "float16"))
    parser.add_argument(
        "--draft-lm-head",
        default="bf16",
        choices=("bf16", "int4-dequant"),
        help=(
            "Logit head used by the offline drafter. int4-dequant matches the "
            "endpoint VLLM_XPU_DRAFT_LM_HEAD_INT4 quantization recipe, then "
            "dequantizes for diagnostic PyTorch matmul."
        ),
    )
    parser.add_argument("--draft-lm-head-group-size", type=int, default=128)
    parser.add_argument(
        "--draft-lm-head-scale-dtype",
        default="bf16",
        choices=("bf16", "fp16", "fp32"),
    )
    parser.add_argument("--topk", type=int, default=5)
    parser.add_argument(
        "--skip-official-rope",
        action="store_true",
        help="Use the local fallback RoPE instead of importing vLLM get_rope.",
    )
    parser.add_argument("--out", default="")
    parser.add_argument("--print-every", type=int, default=25)
    return parser.parse_args()


def dtype_from_name(name: str) -> torch.dtype:
    return {
        "float32": torch.float32,
        "bfloat16": torch.bfloat16,
        "float16": torch.float16,
    }[name]


def choose_device(name: str) -> torch.device:
    if name != "auto":
        return torch.device(name)
    if hasattr(torch, "xpu") and torch.xpu.is_available():
        return torch.device("xpu:0")
    if torch.cuda.is_available():
        return torch.device("cuda:0")
    return torch.device("cpu")


def torch_load(path: str) -> dict[str, Any]:
    try:
        return torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        return torch.load(path, map_location="cpu")


def load_config(model_dir: str) -> dict[str, Any]:
    with open(os.path.join(model_dir, "config.json"), "r", encoding="utf-8") as f:
        config = json.load(f)
    return config.get("text_config") or config


def shape_from_config(config: dict[str, Any]) -> QwenMTPShape:
    return QwenMTPShape(
        hidden_size=int(config["hidden_size"]),
        intermediate_size=int(config["intermediate_size"]),
        vocab_size=int(config["vocab_size"]),
        num_heads=int(config["num_attention_heads"]),
        num_kv_heads=int(config["num_key_value_heads"]),
        head_dim=int(config.get("head_dim") or (
            int(config["hidden_size"]) // int(config["num_attention_heads"])
        )),
        rms_norm_eps=float(config.get("rms_norm_eps", 1e-6)),
        rope_theta=float(config.get("rope_theta", 10000000.0)),
        rope_parameters=dict(config.get("rope_parameters") or {}),
    )


def load_indexed_tensor(model_dir: str, name: str) -> torch.Tensor:
    index_path = os.path.join(model_dir, "model.safetensors.index.json")
    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)
    shard = index["weight_map"][name]
    return load_file(os.path.join(model_dir, shard), device="cpu")[name]


def unpack_gptq_packed_rows(qweight: torch.Tensor, bits: int = 4) -> torch.Tensor:
    """Unpack AutoGPTQ/AutoRound qweight from [in//pack, out] to [in, out]."""
    pack = 32 // bits
    mask = (1 << bits) - 1
    qw = qweight.to(torch.int64) & 0xFFFFFFFF
    pieces = [((qw >> (bits * i)) & mask).to(torch.int16) for i in range(pack)]
    return torch.stack(pieces, dim=1).reshape(qweight.shape[0] * pack,
                                              qweight.shape[1])


def unpack_gptq_qzeros(qzeros: torch.Tensor, out_features: int,
                       bits: int = 4) -> torch.Tensor:
    """Unpack GPTQ qzeros from [groups, out//pack] to [groups, out].

    AutoGPTQ stores zero points offset by -1, so runtime zero = unpacked + 1.
    Symmetric AutoRound checkpoints normally unpack to all 7 -> zero point 8.
    """
    unpacked = unpack_gptq_packed_rows(qzeros, bits=bits)
    # qzeros packs output columns, not input rows, so transpose the conceptual
    # pack by reshaping back to [groups, out].
    groups = qzeros.shape[0]
    pack = 32 // bits
    qw = qzeros.to(torch.int64) & 0xFFFFFFFF
    pieces = [((qw >> (bits * i)) & ((1 << bits) - 1)).to(torch.int16)
              for i in range(pack)]
    zeros = torch.stack(pieces, dim=2).reshape(groups, qzeros.shape[1] * pack)
    if zeros.shape[1] < out_features:
        raise ValueError(
            f"qzeros unpacked only {zeros.shape[1]} outputs, expected {out_features}"
        )
    return zeros[:, :out_features].to(torch.float32) + 1.0


def dequant_gptq_linear(tensors: dict[str, torch.Tensor], prefix: str,
                        group_size: int = 128) -> torch.Tensor:
    """Return dense [in_features, out_features] weight from an AutoRound W4 shard."""
    qweight = tensors[f"{prefix}.qweight"]
    scales = tensors[f"{prefix}.scales"].to(torch.float32)
    unpacked = unpack_gptq_packed_rows(qweight).to(torch.float32)
    zeros = unpack_gptq_qzeros(tensors[f"{prefix}.qzeros"], qweight.shape[1])
    in_features, out_features = unpacked.shape
    if scales.shape != zeros.shape:
        raise ValueError(f"{prefix}: scales {scales.shape} != zeros {zeros.shape}")
    group_ids = torch.arange(in_features, dtype=torch.long) // group_size
    return (unpacked - zeros[group_ids]) * scales[group_ids]


def qwen_rms_norm(x: torch.Tensor, weight: torch.Tensor,
                  eps: float) -> torch.Tensor:
    orig_dtype = x.dtype
    x_float = x.float()
    var = x_float.pow(2).mean(dim=-1, keepdim=True)
    out = x_float * torch.rsqrt(var + eps)
    return (out * (weight.float() + 1.0)).to(orig_dtype)


def qwen_rms_norm_residual(
    x: torch.Tensor,
    residual: torch.Tensor,
    weight: torch.Tensor,
    eps: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    merged = x + residual
    return qwen_rms_norm(merged, weight, eps), merged


def quantize_lm_head_int4_dequant(
    weight: torch.Tensor,
    *,
    group_size: int = 128,
    scale_dtype_name: str = "bf16",
    out_dtype: torch.dtype = torch.bfloat16,
    device: torch.device,
    chunk_rows: int = 2048,
) -> torch.Tensor:
    """Approximate endpoint VLLM_XPU_DRAFT_LM_HEAD_INT4 as dense dequant.

    vLLM stores unsigned int4 nibbles with symmetric zero point 8 and per
    vocab-row/per-hidden-group scales. For offline diagnostics we do not need the
    packed representation; dequantizing once gives the same ranked-logit surface
    up to matmul kernel rounding differences.
    """
    if weight.shape[1] % group_size != 0:
        raise ValueError(
            f"group_size {group_size} must divide hidden size {weight.shape[1]}"
        )
    scale_dtype = {
        "fp16": torch.float16,
        "float16": torch.float16,
        "bf16": torch.bfloat16,
        "bfloat16": torch.bfloat16,
        "fp32": torch.float32,
        "float32": torch.float32,
    }[scale_dtype_name]
    num_tokens, hidden = weight.shape
    num_groups = hidden // group_size
    out = torch.empty((num_tokens, hidden), dtype=out_dtype, device=device)
    with torch.no_grad():
        for start in range(0, num_tokens, max(1, chunk_rows)):
            end = min(start + chunk_rows, num_tokens)
            w = weight[start:end].to(device=device, dtype=torch.float32)
            grouped = w.view(end - start, num_groups, group_size)
            scales = grouped.abs().amax(dim=2).clamp_min(1.0e-10) / 7.0
            scales = scales.to(scale_dtype).to(torch.float32)
            q = torch.round(grouped / scales.unsqueeze(-1)).clamp(-8, 7)
            out[start:end].copy_((q * scales.unsqueeze(-1)).reshape(
                end - start, hidden).to(out_dtype))
            del w, grouped, scales, q
    return out


def make_official_rope(shape: QwenMTPShape, device: torch.device,
                       disabled: bool) -> Any | None:
    if disabled:
        return None
    vllm_src = "/home/steve/src/vllm"
    if os.path.isdir(vllm_src) and vllm_src not in sys.path:
        sys.path.insert(0, vllm_src)
    try:
        from vllm.model_executor.layers.rotary_embedding import get_rope
        rope = get_rope(
            head_size=shape.head_dim,
            max_position=262144,
            rope_parameters=shape.rope_parameters,
            is_neox_style=True,
        )
        return rope.to(device) if hasattr(rope, "to") else rope
    except Exception as exc:
        print(
            "[intrinsic-mtp] vLLM get_rope unavailable outside a vLLM config "
            f"context ({type(exc).__name__}: {exc}); using local text-only "
            "Neox RoPE fallback.",
            file=sys.stderr,
            flush=True,
        )
        return None


def fallback_apply_rope(
    positions: torch.Tensor,
    q: torch.Tensor,
    k: torch.Tensor,
    shape: QwenMTPShape,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Small fallback RoPE. Prefer official vLLM RoPE for reported numbers."""
    rotary_dim = int(shape.head_dim *
                     float(shape.rope_parameters.get("partial_rotary_factor", 1.0)))
    if rotary_dim <= 0:
        return q, k
    rotary_dim = (rotary_dim // 2) * 2
    device = q.device
    inv_freq = 1.0 / (
        shape.rope_theta
        ** (torch.arange(0, rotary_dim, 2, device=device).float() / rotary_dim)
    )
    freqs = torch.outer(positions.to(device=device).float(), inv_freq)
    cos = freqs.cos().to(q.dtype)
    sin = freqs.sin().to(q.dtype)

    def apply(x: torch.Tensor) -> torch.Tensor:
        x_shape = x.shape
        x = x.view(x_shape[0], -1, shape.head_dim)
        x_rot = x[..., :rotary_dim]
        x_pass = x[..., rotary_dim:]
        x1, x2 = x_rot.chunk(2, dim=-1)
        c = cos[:, None, :x1.shape[-1]]
        s = sin[:, None, :x1.shape[-1]]
        rotated = torch.cat([x1 * c - x2 * s, x2 * c + x1 * s], dim=-1)
        return torch.cat([rotated, x_pass], dim=-1).reshape(x_shape)

    return apply(q), apply(k)


def find_position_fcs(
    tensors: dict[str, torch.Tensor],
) -> list[tuple[str, torch.Tensor]]:
    indexed: dict[int, tuple[str, torch.Tensor]] = {}
    for key, tensor in tensors.items():
        match = POSITION_FC_KEY_RE.fullmatch(key)
        if match is None:
            continue
        index = int(match.group(1))
        if index in indexed:
            raise ValueError(f"Duplicate position FC index {index} in {key!r}")
        indexed[index] = (key, tensor)
    if not indexed:
        return []
    expected = list(range(len(indexed)))
    actual = sorted(indexed)
    if actual != expected:
        raise ValueError(
            "Position FC keys must be contiguous and zero-based; "
            f"found indices {actual}, expected {expected}"
        )
    return [indexed[index] for index in expected]


def find_position_adapters(
    tensors: dict[str, torch.Tensor],
    hidden_size: int,
) -> tuple[list[tuple[str, torch.Tensor, str, torch.Tensor]], int]:
    indexed: dict[int, dict[str, tuple[str, torch.Tensor]]] = {}
    for key, tensor in tensors.items():
        match = POSITION_ADAPTER_KEY_RE.fullmatch(key)
        if match is None:
            continue
        index = int(match.group(1))
        direction = match.group(2)
        indexed.setdefault(index, {})[direction] = (key, tensor)
    if not indexed:
        return [], 0

    expected = list(range(len(indexed)))
    actual = sorted(indexed)
    if actual != expected:
        raise ValueError(
            "Position adapter keys must be contiguous and zero-based; "
            f"found indices {actual}, expected {expected}"
        )

    adapters: list[tuple[str, torch.Tensor, str, torch.Tensor]] = []
    adapter_rank = 0
    for index in expected:
        parts = indexed[index]
        missing = sorted({"down", "up"} - set(parts))
        if missing:
            raise ValueError(
                f"Position adapter {index} is missing {missing} weight key(s)"
            )
        down_key, down = parts["down"]
        up_key, up = parts["up"]
        if down.ndim != 2:
            raise ValueError(
                f"{down_key} must have shape [rank, H], got {tuple(down.shape)}"
            )
        rank = int(down.shape[0])
        if rank < 1 or tuple(down.shape[1:]) != (hidden_size,):
            raise ValueError(
                f"{down_key} must have shape [rank, {hidden_size}] with rank > 0, "
                f"got {tuple(down.shape)}"
            )
        if tuple(up.shape) != (hidden_size, rank):
            raise ValueError(
                f"{up_key} must have shape [{hidden_size}, {rank}], "
                f"got {tuple(up.shape)}"
            )
        if adapter_rank and rank != adapter_rank:
            raise ValueError(
                "Position adapter ranks must match; "
                f"adapter 0 has rank {adapter_rank}, adapter {index} has rank {rank}"
            )
        adapter_rank = rank
        adapters.append((down_key, down, up_key, up))
    return adapters, adapter_rank


class IntrinsicMTP(torch.nn.Module):
    def __init__(
        self,
        *,
        shape: QwenMTPShape,
        tensors: dict[str, torch.Tensor],
        embed_weight: torch.Tensor,
        lm_head_weight: torch.Tensor,
        device: torch.device,
        dtype: torch.dtype,
        use_official_rope: bool,
        draft_lm_head: str = "bf16",
        draft_lm_head_group_size: int = 128,
        draft_lm_head_scale_dtype: str = "bf16",
    ) -> None:
        super().__init__()
        self.shape = shape
        self.device = device
        self.dtype = dtype
        self.rope = make_official_rope(shape, device, not use_official_rope)

        def dense(prefix: str) -> torch.Tensor:
            return dequant_gptq_linear(tensors, prefix).to(device=device,
                                                           dtype=dtype)

        self.embed = embed_weight.to(device=device, dtype=dtype)
        self.draft_lm_head = draft_lm_head
        if draft_lm_head == "int4-dequant":
            self.lm_head = quantize_lm_head_int4_dequant(
                lm_head_weight,
                group_size=draft_lm_head_group_size,
                scale_dtype_name=draft_lm_head_scale_dtype,
                out_dtype=dtype,
                device=device,
            )
        else:
            self.lm_head = lm_head_weight.to(device=device, dtype=dtype)
        self.fc = tensors["mtp.fc.weight"].to(device=device, dtype=dtype)
        position_fcs = find_position_fcs(tensors)
        self.position_fc_keys = tuple(key for key, _ in position_fcs)
        self.position_fcs = [
            tensor.to(device=device, dtype=dtype) for _, tensor in position_fcs
        ]
        for key, position_fc in zip(self.position_fc_keys, self.position_fcs):
            if position_fc.shape != self.fc.shape:
                raise ValueError(
                    f"{key} shape {tuple(position_fc.shape)} does not match "
                    f"mtp.fc.weight shape {tuple(self.fc.shape)}"
                )
        self.position_fc_count = len(self.position_fcs)
        position_adapters, position_adapter_rank = find_position_adapters(
            tensors, shape.hidden_size
        )
        self.position_adapter_down_keys = tuple(
            down_key for down_key, _, _, _ in position_adapters
        )
        self.position_adapter_up_keys = tuple(
            up_key for _, _, up_key, _ in position_adapters
        )
        self.position_adapter_keys = tuple(
            key
            for down_key, _, up_key, _ in position_adapters
            for key in (down_key, up_key)
        )
        self.position_adapter_down = [
            down.to(device=device, dtype=dtype)
            for _, down, _, _ in position_adapters
        ]
        self.position_adapter_up = [
            up.to(device=device, dtype=dtype)
            for _, _, _, up in position_adapters
        ]
        self.position_adapter_count = len(position_adapters)
        self.position_adapter_rank = position_adapter_rank
        if (self.position_fc_count and self.position_adapter_count
                and self.position_fc_count != self.position_adapter_count):
            raise ValueError(
                "Position FC and adapter counts must match when both are present; "
                f"found {self.position_fc_count} FCs and "
                f"{self.position_adapter_count} adapters"
            )
        self.pre_fc_norm_embedding = tensors[
            "mtp.pre_fc_norm_embedding.weight"].to(device=device, dtype=dtype)
        self.pre_fc_norm_hidden = tensors["mtp.pre_fc_norm_hidden.weight"].to(
            device=device, dtype=dtype)
        self.input_layernorm = tensors[
            "mtp.layers.0.input_layernorm.weight"].to(device=device, dtype=dtype)
        self.post_attention_layernorm = tensors[
            "mtp.layers.0.post_attention_layernorm.weight"].to(
                device=device, dtype=dtype)
        self.q_norm = tensors["mtp.layers.0.self_attn.q_norm.weight"].to(
            device=device, dtype=dtype)
        self.k_norm = tensors["mtp.layers.0.self_attn.k_norm.weight"].to(
            device=device, dtype=dtype)
        self.final_norm = tensors["mtp.norm.weight"].to(device=device, dtype=dtype)

        self.q_proj = dense("mtp.layers.0.self_attn.q_proj")
        self.k_proj = dense("mtp.layers.0.self_attn.k_proj")
        self.v_proj = dense("mtp.layers.0.self_attn.v_proj")
        self.o_proj = dense("mtp.layers.0.self_attn.o_proj")
        self.gate_proj = dense("mtp.layers.0.mlp.gate_proj")
        self.up_proj = dense("mtp.layers.0.mlp.up_proj")
        self.down_proj = dense("mtp.layers.0.mlp.down_proj")

    def matmul(self, x: torch.Tensor, weight_in_out: torch.Tensor) -> torch.Tensor:
        return x.matmul(weight_in_out)

    def self_attention(self, hidden: torch.Tensor,
                       positions: torch.Tensor) -> torch.Tensor:
        bsz, seq_len, hidden_size = hidden.shape
        flat = hidden.reshape(bsz * seq_len, hidden_size)
        q_gate = self.matmul(flat, self.q_proj)
        k = self.matmul(flat, self.k_proj)
        v = self.matmul(flat, self.v_proj)
        q_gate = q_gate.view(bsz * seq_len, self.shape.num_heads,
                             self.shape.head_dim * 2)
        q, gate = torch.chunk(q_gate, 2, dim=-1)
        q = q.reshape(bsz * seq_len, self.shape.num_heads * self.shape.head_dim)
        gate = gate.reshape(bsz * seq_len,
                            self.shape.num_heads * self.shape.head_dim)
        k = k.view(bsz * seq_len, self.shape.num_kv_heads, self.shape.head_dim)

        q = qwen_rms_norm(
            q.view(bsz * seq_len, self.shape.num_heads, self.shape.head_dim),
            self.q_norm,
            self.shape.rms_norm_eps,
        ).reshape(bsz * seq_len, self.shape.num_heads * self.shape.head_dim)
        k = qwen_rms_norm(k, self.k_norm, self.shape.rms_norm_eps).reshape(
            bsz * seq_len, self.shape.num_kv_heads * self.shape.head_dim)

        flat_positions = positions.reshape(-1)
        if self.rope is not None:
            q, k = self.rope(flat_positions.to(self.device), q, k)
        else:
            q, k = fallback_apply_rope(flat_positions, q, k, self.shape)

        q = q.view(bsz, seq_len, self.shape.num_heads,
                   self.shape.head_dim).permute(0, 2, 1, 3)
        k = k.view(bsz, seq_len, self.shape.num_kv_heads,
                   self.shape.head_dim).permute(0, 2, 1, 3)
        v = v.view(bsz, seq_len, self.shape.num_kv_heads,
                   self.shape.head_dim).permute(0, 2, 1, 3)
        repeat = self.shape.num_heads // self.shape.num_kv_heads
        if repeat > 1:
            k = k.repeat_interleave(repeat, dim=1)
            v = v.repeat_interleave(repeat, dim=1)
        scores = torch.matmul(q.float(), k.float().transpose(-2, -1))
        scores *= 1.0 / math.sqrt(float(self.shape.head_dim))
        causal = torch.triu(
            torch.ones(seq_len, seq_len, device=self.device, dtype=torch.bool),
            diagonal=1,
        )
        scores = scores.masked_fill(causal[None, None, :, :], float("-inf"))
        probs = F.softmax(scores, dim=-1).to(self.dtype)
        attn = torch.matmul(probs, v)
        attn = attn.permute(0, 2, 1, 3).contiguous().view(
            bsz * seq_len, self.shape.num_heads * self.shape.head_dim)
        attn = attn * torch.sigmoid(gate)
        return self.matmul(attn, self.o_proj).view(bsz, seq_len, hidden_size)

    def fc_for_step(self, spec_step_idx: int) -> torch.Tensor:
        if spec_step_idx < 0:
            raise IndexError(f"spec_step_idx must be non-negative, got {spec_step_idx}")
        if not self.position_fcs:
            return self.fc
        if spec_step_idx >= len(self.position_fcs):
            raise IndexError(
                f"spec_step_idx {spec_step_idx} has no position FC; artifact "
                f"contains {len(self.position_fcs)} position FCs"
            )
        return self.position_fcs[spec_step_idx]

    def position_adapter_for_step(
        self, spec_step_idx: int
    ) -> tuple[torch.Tensor, torch.Tensor] | None:
        if not self.position_adapter_count:
            return None
        if not 0 <= spec_step_idx < self.position_adapter_count:
            raise IndexError(
                f"spec_step_idx {spec_step_idx} has no position adapter; artifact "
                f"contains {self.position_adapter_count} adapters"
            )
        return (
            self.position_adapter_down[spec_step_idx],
            self.position_adapter_up[spec_step_idx],
        )

    def forward(self, hidden_states: torch.Tensor, input_ids: torch.Tensor,
                positions: torch.Tensor, spec_step_idx: int = 0) -> torch.Tensor:
        embeds = self.embed[input_ids.to(self.device)]
        embeds = qwen_rms_norm(embeds, self.pre_fc_norm_embedding,
                               self.shape.rms_norm_eps)
        hidden = qwen_rms_norm(hidden_states, self.pre_fc_norm_hidden,
                               self.shape.rms_norm_eps)
        fc = self.fc_for_step(spec_step_idx)
        hidden = self.matmul(torch.cat([embeds, hidden], dim=-1), fc.t())

        residual = hidden
        hidden = qwen_rms_norm(hidden, self.input_layernorm,
                               self.shape.rms_norm_eps)
        hidden = self.self_attention(hidden, positions)
        hidden, residual = qwen_rms_norm_residual(
            hidden, residual, self.post_attention_layernorm,
            self.shape.rms_norm_eps)
        gate = self.matmul(hidden, self.gate_proj)
        up = self.matmul(hidden, self.up_proj)
        hidden = self.matmul(F.silu(gate) * up, self.down_proj)
        hidden, _ = qwen_rms_norm_residual(hidden, residual, self.final_norm,
                                           self.shape.rms_norm_eps)
        position_adapter = self.position_adapter_for_step(spec_step_idx)
        if position_adapter is not None:
            adapter_down, adapter_up = position_adapter
            adapter = F.silu(F.linear(hidden, adapter_down))
            hidden = hidden + F.linear(adapter, adapter_up)
        return hidden

    def logits(self, hidden: torch.Tensor) -> torch.Tensor:
        return F.linear(hidden, self.lm_head)


def apply_diagnostic_dense_updates(
    model: IntrinsicMTP,
    update_path: str,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> list[str]:
    updates = load_file(update_path, device="cpu")
    applied: list[str] = []
    position_updates: dict[int, torch.Tensor] = {}
    position_adapter_updates: dict[int, dict[str, torch.Tensor]] = {}
    for key, value in updates.items():
        if not key.startswith("dense."):
            continue
        attr = key.removeprefix("dense.")
        position_match = DIAGNOSTIC_POSITION_FC_ATTR_RE.fullmatch(attr)
        if position_match is not None:
            position_updates[int(position_match.group(1))] = value
            applied.append(attr)
            continue
        adapter_match = DIAGNOSTIC_POSITION_ADAPTER_ATTR_RE.fullmatch(attr)
        if adapter_match is not None:
            index = int(adapter_match.group(1))
            direction = adapter_match.group(2)
            position_adapter_updates.setdefault(index, {})[direction] = value
            applied.append(attr)
            continue
        if not hasattr(model, attr):
            raise KeyError(
                f"Diagnostic dense update {key!r} maps to unknown attribute "
                f"{attr!r}")
        setattr(model, attr, value.to(device=device, dtype=dtype))
        applied.append(attr)
    if position_updates:
        expected = list(range(len(position_updates)))
        actual = sorted(position_updates)
        if actual != expected:
            raise ValueError(
                "Diagnostic position FC updates must be contiguous and zero-based; "
                f"found indices {actual}, expected {expected}"
            )
        model.position_fcs = [
            position_updates[index].to(device=device, dtype=dtype)
            for index in expected
        ]
        for index, position_fc in enumerate(model.position_fcs):
            if position_fc.shape != model.fc.shape:
                raise ValueError(
                    f"dense.position_fcs.{index} shape "
                    f"{tuple(position_fc.shape)} does not match mtp.fc.weight "
                    f"shape {tuple(model.fc.shape)}"
                )
        model.position_fc_keys = tuple(
            f"mtp.position_fcs.{index}.weight" for index in expected
        )
        model.position_fc_count = len(model.position_fcs)
    if position_adapter_updates:
        adapter_tensors = {
            f"mtp.position_adapters.{index}.{direction}.weight": value
            for index, parts in position_adapter_updates.items()
            for direction, value in parts.items()
        }
        position_adapters, adapter_rank = find_position_adapters(
            adapter_tensors, model.shape.hidden_size
        )
        if (model.position_fc_count
                and len(position_adapters) != model.position_fc_count):
            raise ValueError(
                "Diagnostic position adapter count must match position FC count; "
                f"found {len(position_adapters)} adapters and "
                f"{model.position_fc_count} FCs"
            )
        model.position_adapter_down_keys = tuple(
            down_key for down_key, _, _, _ in position_adapters
        )
        model.position_adapter_up_keys = tuple(
            up_key for _, _, up_key, _ in position_adapters
        )
        model.position_adapter_keys = tuple(
            key
            for down_key, _, up_key, _ in position_adapters
            for key in (down_key, up_key)
        )
        model.position_adapter_down = [
            down.to(device=device, dtype=dtype)
            for _, down, _, _ in position_adapters
        ]
        model.position_adapter_up = [
            up.to(device=device, dtype=dtype)
            for _, _, _, up in position_adapters
        ]
        model.position_adapter_count = len(position_adapters)
        model.position_adapter_rank = adapter_rank
    if not applied:
        raise ValueError(f"No dense.* updates found in {update_path}")
    return sorted(applied)


def iter_sample_paths(dataset_dirs: list[str], max_samples: int) -> list[str]:
    paths: list[str] = []
    for dataset_dir in dataset_dirs:
        paths.extend(sorted(glob.glob(os.path.join(dataset_dir, "*.pt"))))
    if max_samples > 0:
        paths = paths[:max_samples]
    if not paths:
        raise FileNotFoundError(f"No .pt samples found in {dataset_dirs}")
    return paths


def make_positions(sample: dict[str, Any], length: int) -> torch.Tensor:
    if "positions" in sample:
        positions = sample["positions"][:length].to(torch.long)
        if positions.numel() == length and torch.all(positions >= 0):
            return positions
    return torch.arange(length, dtype=torch.long)


def evaluate_start(
    *,
    model: IntrinsicMTP,
    hidden: torch.Tensor,
    next_ids: torch.Tensor,
    positions: torch.Tensor,
    start: int,
    max_steps: int,
    topk: int,
    device: torch.device,
    dtype: torch.dtype,
) -> dict[str, Any]:
    current_hidden = hidden[start:start + 1].to(device=device, dtype=dtype)
    current_ids = next_ids[start:start + 1].to(device=device).view(1, 1)
    current_positions = positions[start:start + 1].to(device=device).view(1, 1)
    current_hidden = current_hidden.view(1, 1, -1)

    accepted = 0
    rows: list[dict[str, int | bool]] = []
    for step in range(max_steps):
        target_index = start + step + 1
        if target_index >= next_ids.shape[0]:
            break
        pred_seq = model(
            current_hidden,
            current_ids,
            current_positions,
            spec_step_idx=step,
        )
        pred_hidden = pred_seq[:, -1, :]
        logits = model.logits(pred_hidden)
        proposed = int(torch.argmax(logits, dim=-1).item())
        target = int(next_ids[target_index].item())
        k = min(topk, logits.shape[-1])
        top_indices = torch.topk(logits, k=k, dim=-1).indices[0]
        topk_hit = bool((top_indices == target).any().item())
        matched = proposed == target
        rows.append({
            "step": step + 1,
            "target_index": target_index,
            "proposed": proposed,
            "target": target,
            "match": matched,
            "topk_hit": topk_hit,
        })
        if not matched:
            break
        accepted += 1
        current_hidden = torch.cat(
            [current_hidden, pred_hidden.view(1, 1, -1)],
            dim=1,
        )
        current_ids = torch.cat(
            [current_ids, next_ids[target_index:target_index + 1]
             .to(device=device).view(1, 1)],
            dim=1,
        )
        current_positions = torch.cat(
            [current_positions, positions[target_index:target_index + 1]
             .to(device=device).view(1, 1)],
            dim=1,
        )
    return {"accepted": accepted, "rows": rows}


def summarize(args: argparse.Namespace, paths: list[str], model: IntrinsicMTP,
              device: torch.device, dtype: torch.dtype) -> dict[str, Any]:
    started = time.perf_counter()
    starts = 0
    accepted_total = 0
    hist = [0 for _ in range(args.max_steps + 1)]
    conditional_den = [0 for _ in range(args.max_steps)]
    exact_hits = [0 for _ in range(args.max_steps)]
    topk_hits = [0 for _ in range(args.max_steps)]
    sample_rows: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []
    family_stats: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"samples": 0, "starts": 0, "accepted": 0}
    )

    with torch.no_grad():
        for sample_index, path in enumerate(paths):
            sample = torch_load(path)
            if not str(sample.get("format", "")).startswith(
                "qwen36_eagle_sequence_v"):
                continue
            request_metadata = sample.get("request_metadata") or {}
            family = str(
                sample.get("family")
                or request_metadata.get("family")
                or "unknown"
            )
            prompt_id = sample.get("prompt_id") or request_metadata.get("prompt_id")
            hidden = sample["hidden_state"].to(torch.float32)
            if "sampled_next_token_ids" not in sample:
                continue
            next_ids = sample["sampled_next_token_ids"].to(torch.long)
            length = min(hidden.shape[0], next_ids.shape[0])
            if length <= args.max_steps + 1:
                continue
            positions = make_positions(sample, length)
            available_starts = max(0, length - args.max_steps - 1)
            sample_starts = 0
            sample_accepted = 0
            for start in range(0, available_starts, args.start_stride):
                if args.max_starts > 0 and starts >= args.max_starts:
                    break
                result = evaluate_start(
                    model=model,
                    hidden=hidden,
                    next_ids=next_ids,
                    positions=positions,
                    start=start,
                    max_steps=args.max_steps,
                    topk=args.topk,
                    device=device,
                    dtype=dtype,
                )
                accepted = int(result["accepted"])
                starts += 1
                sample_starts += 1
                accepted_total += accepted
                sample_accepted += accepted
                hist[accepted] += 1
                rows = result["rows"]
                for row in rows:
                    step_idx = int(row["step"]) - 1
                    conditional_den[step_idx] += 1
                    exact_hits[step_idx] += int(bool(row["match"]))
                    topk_hits[step_idx] += int(bool(row["topk_hit"]))
                if rows and not rows[-1]["match"] and len(examples) < 12:
                    examples.append({
                        "sample": os.path.basename(path),
                        "prompt_id": prompt_id,
                        "family": family,
                        "start": start,
                        "accepted": accepted,
                        "first_mismatch": rows[-1],
                    })
                if args.max_starts > 0 and starts >= args.max_starts:
                    break
            if sample_starts:
                family_stats[family]["samples"] = int(family_stats[family]["samples"]) + 1
                family_stats[family]["starts"] = int(family_stats[family]["starts"]) + sample_starts
                family_stats[family]["accepted"] = (
                    float(family_stats[family]["accepted"]) + sample_accepted
                )
                sample_rows.append({
                    "sample": os.path.basename(path),
                    "prompt_id": prompt_id,
                    "family": family,
                    "starts": sample_starts,
                    "mean_accepted": sample_accepted / sample_starts,
                })
            if args.print_every > 0 and (sample_index + 1) % args.print_every == 0:
                mean = accepted_total / starts if starts else 0.0
                print(
                    f"[intrinsic-mtp] samples={sample_index + 1} starts={starts} "
                    f"mean_accepted={mean:.4f}",
                    flush=True,
                )
            if args.max_starts > 0 and starts >= args.max_starts:
                break

    family_summary: dict[str, dict[str, float | int]] = {}
    for family, vals in sorted(family_stats.items()):
        starts_f = int(vals["starts"])
        accepted_f = float(vals["accepted"])
        family_summary[family] = {
            "samples": int(vals["samples"]),
            "starts": starts_f,
            "mean_accepted": accepted_f / starts_f if starts_f else 0.0,
        }

    return {
        "purpose": "diagnostic_intrinsic_mtp_offline_acceptance_probe",
        "valid_headline_throughput": False,
        "headline_warning": (
            "Offline draft acceptance only; not an endpoint speed, not a "
            "fresh-response throughput claim, not LocalMaxxing-submit eligible."
        ),
        "model_dir": args.model_dir,
        "model_extra_path": args.model_extra_path or (
            os.path.join(args.model_dir, "model_extra_tensors.safetensors")
        ),
        "dataset_dirs": args.dataset_dir,
        "num_files_seen": len(paths),
        "max_steps": args.max_steps,
        "max_samples": args.max_samples,
        "max_starts": args.max_starts,
        "start_stride": args.start_stride,
        "device": str(device),
        "dtype": str(dtype).replace("torch.", ""),
        "draft_lm_head": getattr(model, "draft_lm_head", "bf16"),
        "position_fc_count": model.position_fc_count,
        "position_fc_keys": list(model.position_fc_keys),
        "position_fc_selection": (
            "zero_based_spec_step_idx" if model.position_fc_count
            else "shared_mtp.fc.weight"
        ),
        "position_adapter_count": model.position_adapter_count,
        "position_adapter_rank": model.position_adapter_rank,
        "position_adapter_keys": list(model.position_adapter_keys),
        "position_adapter_selection": (
            "zero_based_spec_step_idx_post_final_norm_residual"
            if model.position_adapter_count else "none"
        ),
        "rope": "vllm_get_rope" if model.rope is not None else (
            "local_text_only_neox_rope_fallback"
        ),
        "starts": starts,
        "mean_accepted_draft_tokens": accepted_total / starts if starts else 0.0,
        "mean_visible_tokens_if_k_step_spec": (
            1.0 + accepted_total / starts if starts else 0.0
        ),
        "histogram_accepted_draft_tokens": {
            str(i): hist[i] for i in range(len(hist)) if hist[i]
        },
        "conditional_exact": [
            exact_hits[i] / conditional_den[i] if conditional_den[i] else 0.0
            for i in range(args.max_steps)
        ],
        "conditional_topk": [
            topk_hits[i] / conditional_den[i] if conditional_den[i] else 0.0
            for i in range(args.max_steps)
        ],
        "conditional_denominators": conditional_den,
        "families": family_summary,
        "samples": sample_rows[:200],
        "first_mismatch_examples": examples,
        "elapsed_s": time.perf_counter() - started,
    }


def main() -> int:
    args = parse_args()
    args.dataset_dir = [d for d in args.dataset_dir if d]
    if not args.dataset_dir:
        args.dataset_dir = [DEFAULT_DATASET_DIR]
    if args.max_steps < 1:
        raise ValueError("--max-steps must be >= 1")
    if args.start_stride < 1:
        raise ValueError("--start-stride must be >= 1")
    device = choose_device(args.device)
    dtype = dtype_from_name(args.dtype)

    config = load_config(args.model_dir)
    shape = shape_from_config(config)
    model_extra_path = args.model_extra_path or os.path.join(
        args.model_dir, "model_extra_tensors.safetensors")
    tensors = load_file(model_extra_path, device="cpu")
    embed = load_indexed_tensor(args.model_dir,
                                "model.language_model.embed_tokens.weight")
    lm_head = load_indexed_tensor(args.model_dir, "lm_head.weight")
    model = IntrinsicMTP(
        shape=shape,
        tensors=tensors,
        embed_weight=embed,
        lm_head_weight=lm_head,
        device=device,
        dtype=dtype,
        use_official_rope=not args.skip_official_rope,
        draft_lm_head=args.draft_lm_head,
        draft_lm_head_group_size=args.draft_lm_head_group_size,
        draft_lm_head_scale_dtype=args.draft_lm_head_scale_dtype,
    ).eval()
    diagnostic_dense_updates = []
    if args.diagnostic_dense_update_path:
        diagnostic_dense_updates = apply_diagnostic_dense_updates(
            model,
            args.diagnostic_dense_update_path,
            device=device,
            dtype=dtype,
        )

    paths = iter_sample_paths(args.dataset_dir, args.max_samples)
    summary = summarize(args, paths, model, device, dtype)
    summary["diagnostic_dense_update_path"] = args.diagnostic_dense_update_path
    summary["diagnostic_dense_updates_applied"] = diagnostic_dense_updates
    text = json.dumps(summary, indent=2, sort_keys=True)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {out_path}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
