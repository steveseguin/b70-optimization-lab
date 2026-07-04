#!/usr/bin/env python3
"""Train a small EAGLE-1 draft body from Qwen 3.6 target hidden-state samples.

This intentionally exports the same minimal checkpoint layout produced by
create-qwen36-eagle1-smoke-checkpoint.py: draft body only, no embed_tokens and
no lm_head. vLLM shares those target modules at serve time.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import shutil
from dataclasses import asdict, dataclass
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from safetensors.torch import load_file, save_file
from torch.utils.data import DataLoader, Dataset


@dataclass
class DraftShape:
    hidden_size: int = 2048
    intermediate_size: int = 4096
    num_hidden_layers: int = 1
    num_attention_heads: int = 16
    num_key_value_heads: int = 2
    head_dim: int = 128
    vocab_size: int = 248320
    max_position_embeddings: int = 262144
    rope_theta: float = 10000000.0
    rms_norm_eps: float = 1e-6


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset-dir",
        required=True,
        action="append",
        help="Dataset directory. May be passed multiple times.",
    )
    parser.add_argument("--target-model", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--init-checkpoint", default="")
    parser.add_argument(
        "--repeat-last-init-layer",
        action="store_true",
        help=(
            "When initializing a deeper draft from a shallower checkpoint, "
            "copy the last available checkpoint layer into extra layers "
            "instead of leaving them randomly initialized."
        ),
    )
    parser.add_argument(
        "--zero-extra-init-layer",
        action="store_true",
        help=(
            "When initializing a deeper draft from a shallower checkpoint, "
            "zero extra layer matrix weights while leaving norm weights at "
            "their defaults. This makes the extra layer start as a residual "
            "no-op for this draft architecture."
        ),
    )
    parser.add_argument(
        "--residual-extra-init-layer",
        action="store_true",
        help=(
            "When initializing a deeper draft from a shallower checkpoint, "
            "copy the last available layer into extra layers, then zero only "
            "their output projections. This starts as a residual no-op while "
            "leaving the extra layer trainable."
        ),
    )
    parser.add_argument(
        "--freeze-init-base-layers",
        action="store_true",
        help=(
            "Freeze fc and the layers loaded directly from the init checkpoint. "
            "Useful when training newly-added residual no-op layers without "
            "forgetting the accepted base draft."
        ),
    )
    parser.add_argument("--num-layers", type=int, default=1)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--max-len", type=int, default=256)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--train-dtype", default="float32",
                        choices=("float32", "bfloat16"))
    parser.add_argument("--export-dtype", default="bfloat16",
                        choices=("float32", "float16", "bfloat16"))
    parser.add_argument("--feature-loss-weight", type=float, default=1.0)
    parser.add_argument("--token-loss-weight", type=float, default=0.1)
    parser.add_argument(
        "--rollout-steps",
        type=int,
        default=1,
        help=(
            "Train multiple autoregressive draft steps. Step 1 matches the "
            "original teacher-forced objective; higher steps feed the prior "
            "predicted hidden state and teacher token ids."
        ),
    )
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--log-every", type=int, default=1)
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=0,
        help="Save an intermediate draft checkpoint every N optimizer steps.",
    )
    parser.add_argument("--shuffle-seed", type=int, default=0)
    parser.add_argument(
        "--hidden-size",
        type=int,
        default=0,
        help=(
            "Override draft hidden size. Defaults to target config/dataset "
            "hidden size because EAGLE hidden states must match the target."
        ),
    )
    parser.add_argument(
        "--intermediate-size",
        type=int,
        default=0,
        help=(
            "Override draft MLP intermediate size. Defaults to the compact "
            "trainer default, not the target model intermediate size."
        ),
    )
    parser.add_argument("--num-attention-heads", type=int, default=0)
    parser.add_argument("--num-key-value-heads", type=int, default=0)
    parser.add_argument("--head-dim", type=int, default=0)
    parser.add_argument("--vocab-size", type=int, default=0)
    parser.add_argument("--max-position-embeddings", type=int, default=0)
    parser.add_argument("--rope-theta", type=float, default=0.0)
    parser.add_argument("--rms-norm-eps", type=float, default=0.0)
    parser.add_argument(
        "--copy-target-draft-architecture",
        action="store_true",
        help=(
            "Also copy intermediate/head shape fields from target config. "
            "This is usually slower/larger than a compact draft; use only as "
            "an explicit experiment."
        ),
    )
    return parser.parse_args()


def dtype_from_name(name: str) -> torch.dtype:
    return {
        "float32": torch.float32,
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
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


def _target_text_config(target_model: str) -> dict[str, Any]:
    config_path = os.path.join(target_model, "config.json")
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    text_config = config.get("text_config")
    if isinstance(text_config, dict):
        return text_config
    language_config = config.get("language_config")
    if isinstance(language_config, dict):
        return language_config
    return config


def _set_shape_if_present(
    shape: DraftShape,
    config: dict[str, Any],
    config_key: str,
    attr: str,
) -> None:
    value = config.get(config_key)
    if value is None:
        return
    setattr(shape, attr, value)


def apply_target_shape(
    shape: DraftShape,
    target_model: str,
    *,
    copy_target_draft_architecture: bool,
) -> dict[str, Any]:
    """Apply target-facing dimensions from the target config.

    EAGLE draft hidden states and shared target embed/head tensors must match
    the target model. The draft's internal MLP/head topology can remain compact,
    so only copy those larger target architecture fields when explicitly asked.
    """
    config = _target_text_config(target_model)
    if not config:
        return {}

    for key in (
        "hidden_size",
        "vocab_size",
        "max_position_embeddings",
        "rope_theta",
        "rms_norm_eps",
    ):
        _set_shape_if_present(shape, config, key, key)

    if copy_target_draft_architecture:
        for key in (
            "intermediate_size",
            "num_attention_heads",
            "num_key_value_heads",
            "head_dim",
        ):
            _set_shape_if_present(shape, config, key, key)
    return config


def apply_shape_overrides(shape: DraftShape, args: argparse.Namespace) -> None:
    overrides = {
        "hidden_size": args.hidden_size,
        "intermediate_size": args.intermediate_size,
        "num_attention_heads": args.num_attention_heads,
        "num_key_value_heads": args.num_key_value_heads,
        "head_dim": args.head_dim,
        "vocab_size": args.vocab_size,
        "max_position_embeddings": args.max_position_embeddings,
        "rope_theta": args.rope_theta,
        "rms_norm_eps": args.rms_norm_eps,
    }
    for attr, value in overrides.items():
        if value:
            setattr(shape, attr, value)


def infer_dataset_hidden_size(dataset: "EagleDataset") -> int:
    first = torch_load(dataset.paths[0])
    hidden = first.get("hidden_state")
    if not isinstance(hidden, torch.Tensor) or hidden.ndim < 2:
        raise ValueError(
            f"{dataset.paths[0]} does not contain a 2-D hidden_state tensor"
        )
    return int(hidden.shape[-1])


def validate_shape(
    shape: DraftShape,
    *,
    dataset_hidden_size: int,
    embed_weight: torch.Tensor,
    lm_head_weight: torch.Tensor,
) -> None:
    errors: list[str] = []
    if shape.hidden_size != dataset_hidden_size:
        errors.append(
            f"shape.hidden_size={shape.hidden_size} but dataset hidden_size="
            f"{dataset_hidden_size}"
        )
    if embed_weight.ndim != 2:
        errors.append(f"embed weight must be 2-D, got {tuple(embed_weight.shape)}")
    else:
        if int(embed_weight.shape[1]) != shape.hidden_size:
            errors.append(
                f"embed hidden={int(embed_weight.shape[1])} but shape.hidden_size="
                f"{shape.hidden_size}"
            )
        if int(embed_weight.shape[0]) != shape.vocab_size:
            errors.append(
                f"embed vocab={int(embed_weight.shape[0])} but shape.vocab_size="
                f"{shape.vocab_size}"
            )
    if lm_head_weight.ndim != 2:
        errors.append(
            f"lm_head weight must be 2-D, got {tuple(lm_head_weight.shape)}"
        )
    else:
        if int(lm_head_weight.shape[1]) != shape.hidden_size:
            errors.append(
                f"lm_head hidden={int(lm_head_weight.shape[1])} but "
                f"shape.hidden_size={shape.hidden_size}"
            )
        if int(lm_head_weight.shape[0]) != shape.vocab_size:
            errors.append(
                f"lm_head vocab={int(lm_head_weight.shape[0])} but "
                f"shape.vocab_size={shape.vocab_size}"
            )
    if shape.num_key_value_heads < 1:
        errors.append("num_key_value_heads must be >= 1")
    if shape.num_attention_heads < 1:
        errors.append("num_attention_heads must be >= 1")
    if shape.num_attention_heads % shape.num_key_value_heads != 0:
        errors.append(
            "num_attention_heads must be divisible by num_key_value_heads "
            f"({shape.num_attention_heads} vs {shape.num_key_value_heads})"
        )
    if shape.head_dim < 1:
        errors.append("head_dim must be >= 1")
    if errors:
        raise ValueError("Invalid EAGLE draft shape:\n- " + "\n- ".join(errors))


class EagleDataset(Dataset):
    def __init__(self, dataset_dirs: list[str], max_len: int) -> None:
        self.paths: list[str] = []
        for dataset_dir in dataset_dirs:
            self.paths.extend(sorted(glob.glob(os.path.join(dataset_dir, "*.pt"))))
        if not self.paths:
            raise FileNotFoundError(f"No .pt samples found in {dataset_dirs}")
        self.max_len = max_len

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        data = torch_load(self.paths[index])
        hidden = data["hidden_state"][: self.max_len].to(torch.float32)
        input_ids = data["input_ids"][: self.max_len].to(torch.long)
        if "positions" in data:
            positions = data["positions"][: self.max_len].to(torch.long)
        else:
            positions = torch.arange(hidden.shape[0], dtype=torch.long)
        loss_mask = data["loss_mask"][: self.max_len].to(torch.float32)
        if "sampled_next_token_ids" in data:
            next_ids = data["sampled_next_token_ids"][: self.max_len].to(torch.long)
        else:
            next_ids = torch.empty_like(input_ids)
            next_ids[:-1] = input_ids[1:]
            next_ids[-1] = 0

        target = torch.zeros_like(hidden)
        target[:-1] = hidden[1:]
        draft_input_ids = next_ids.clone()
        target_token_ids = torch.zeros_like(input_ids)
        target_token_ids[:-1] = next_ids[1:]
        loss_mask = loss_mask.clone()
        if loss_mask.numel():
            loss_mask[-1] = 0
        return {
            "hidden": hidden,
            "draft_input_ids": draft_input_ids,
            "positions": positions,
            "target": target,
            "target_token_ids": target_token_ids,
            "loss_mask": loss_mask,
        }


def collate(samples: list[dict[str, torch.Tensor]]) -> dict[str, torch.Tensor]:
    max_len = max(s["hidden"].shape[0] for s in samples)
    hidden_size = samples[0]["hidden"].shape[-1]
    batch = {
        "hidden": torch.zeros(len(samples), max_len, hidden_size, dtype=torch.float32),
        "draft_input_ids": torch.zeros(len(samples), max_len, dtype=torch.long),
        "positions": torch.zeros(len(samples), max_len, dtype=torch.long),
        "target": torch.zeros(len(samples), max_len, hidden_size, dtype=torch.float32),
        "target_token_ids": torch.zeros(len(samples), max_len, dtype=torch.long),
        "loss_mask": torch.zeros(len(samples), max_len, dtype=torch.float32),
    }
    for i, sample in enumerate(samples):
        n = sample["hidden"].shape[0]
        for key in batch:
            batch[key][i, :n] = sample[key]
    return batch


class RMSNorm(nn.Module):
    def __init__(self, hidden_size: int, eps: float) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.ones(hidden_size))
        self.eps = eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        variance = x.pow(2).mean(dim=-1, keepdim=True)
        return self.weight * x * torch.rsqrt(variance + self.eps)


def fused_add_rms_norm(
    x: torch.Tensor,
    residual: torch.Tensor,
    norm: RMSNorm,
) -> tuple[torch.Tensor, torch.Tensor]:
    residual = (x.to(torch.float32) + residual.to(torch.float32)).to(x.dtype)
    return norm(residual), residual


def apply_neox_rope(x: torch.Tensor, cos: torch.Tensor,
                    sin: torch.Tensor) -> torch.Tensor:
    x1, x2 = torch.chunk(x, 2, dim=-1)
    return torch.cat((x1 * cos - x2 * sin, x2 * cos + x1 * sin), dim=-1)


class EagleDraftLayer(nn.Module):
    def __init__(
        self,
        shape: DraftShape,
        disable_input_layernorm: bool,
    ) -> None:
        super().__init__()
        self.shape = shape
        self.disable_input_layernorm = disable_input_layernorm
        h = shape.hidden_size
        i = shape.intermediate_size
        self.input_layernorm = (
            nn.Identity() if disable_input_layernorm
            else RMSNorm(h, shape.rms_norm_eps)
        )
        self.q_proj = nn.Linear(h, shape.num_attention_heads * shape.head_dim,
                                bias=False)
        self.k_proj = nn.Linear(h, shape.num_key_value_heads * shape.head_dim,
                                bias=False)
        self.v_proj = nn.Linear(h, shape.num_key_value_heads * shape.head_dim,
                                bias=False)
        self.o_proj = nn.Linear(shape.num_attention_heads * shape.head_dim, h,
                                bias=False)
        self.post_attention_layernorm = RMSNorm(h, shape.rms_norm_eps)
        self.gate_proj = nn.Linear(h, i, bias=False)
        self.up_proj = nn.Linear(h, i, bias=False)
        self.down_proj = nn.Linear(i, h, bias=False)

        inv_freq = 1.0 / (
            shape.rope_theta
            ** (torch.arange(0, shape.head_dim, 2, dtype=torch.float32) /
                shape.head_dim)
        )
        self.register_buffer("inv_freq", inv_freq, persistent=False)

    def _apply_rope(
        self,
        q: torch.Tensor,
        k: torch.Tensor,
        positions: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        if positions.dim() == 1:
            positions = positions.unsqueeze(0)
        freqs = positions.to(torch.float32).unsqueeze(-1) * self.inv_freq.to(
            positions.device).view(1, 1, -1)
        cos = freqs.cos().unsqueeze(1)
        sin = freqs.sin().unsqueeze(1)
        cos = cos.to(q.dtype)
        sin = sin.to(q.dtype)
        return apply_neox_rope(q, cos, sin), apply_neox_rope(k, cos, sin)

    def forward(
        self,
        hidden: torch.Tensor,
        residual: torch.Tensor | None,
        positions: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        bsz, seq_len, _ = hidden.shape
        if positions is None:
            positions = torch.arange(seq_len, device=hidden.device,
                                     dtype=torch.long).expand(bsz, seq_len)
        else:
            positions = positions.to(device=hidden.device, dtype=torch.long)
        if residual is None:
            residual = hidden
            x = self.input_layernorm(hidden)
        else:
            if isinstance(self.input_layernorm, nn.Identity):
                residual = hidden + residual
                x = hidden
            else:
                x, residual = fused_add_rms_norm(
                    hidden, residual, self.input_layernorm)

        q = self.q_proj(x).view(
            bsz, seq_len, self.shape.num_attention_heads, self.shape.head_dim)
        k = self.k_proj(x).view(
            bsz, seq_len, self.shape.num_key_value_heads, self.shape.head_dim)
        v = self.v_proj(x).view(
            bsz, seq_len, self.shape.num_key_value_heads, self.shape.head_dim)
        q = q.transpose(1, 2)
        k = k.transpose(1, 2)
        v = v.transpose(1, 2)
        q, k = self._apply_rope(q, k, positions)
        if self.shape.num_key_value_heads != self.shape.num_attention_heads:
            repeat = self.shape.num_attention_heads // self.shape.num_key_value_heads
            k = k.repeat_interleave(repeat, dim=1)
            v = v.repeat_interleave(repeat, dim=1)
        scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(
            self.shape.head_dim)
        mask = torch.triu(
            torch.ones(seq_len, seq_len, device=x.device, dtype=torch.bool),
            diagonal=1,
        )
        scores = scores.masked_fill(mask, float("-inf"))
        attn = torch.softmax(scores, dim=-1)
        x = torch.matmul(attn, v).transpose(1, 2).contiguous().view(
            bsz, seq_len, self.shape.num_attention_heads * self.shape.head_dim)
        x = self.o_proj(x)
        x, residual = fused_add_rms_norm(
            x, residual, self.post_attention_layernorm)
        x = self.down_proj(F.silu(self.gate_proj(x)) * self.up_proj(x))
        return x, residual


class Eagle1Draft(nn.Module):
    def __init__(
        self,
        shape: DraftShape,
        embed_weight: torch.Tensor,
        lm_head_weight: torch.Tensor,
    ) -> None:
        super().__init__()
        self.shape = shape
        h = shape.hidden_size
        self.register_buffer("embed_weight", embed_weight, persistent=False)
        self.register_buffer("lm_head_weight", lm_head_weight, persistent=False)
        self.fc = nn.Linear(2 * h, h, bias=False)
        self.layers = nn.ModuleList(
            EagleDraftLayer(shape, disable_input_layernorm=(i == 0))
            for i in range(shape.num_hidden_layers)
        )

    def forward(
        self,
        hidden: torch.Tensor,
        draft_input_ids: torch.Tensor,
        positions: torch.Tensor | None = None,
    ) -> torch.Tensor:
        embeds = F.embedding(draft_input_ids, self.embed_weight).to(hidden.dtype)
        x = self.fc(torch.cat([embeds, hidden], dim=-1))
        residual = None
        for layer in self.layers:
            x, residual = layer(x, residual, positions)
        return x + residual

    def logits(self, hidden: torch.Tensor) -> torch.Tensor:
        return F.linear(hidden, self.lm_head_weight)

    def export_state(self, dtype: torch.dtype) -> dict[str, torch.Tensor]:
        state = {
            "fc.weight": self.fc.weight.detach().cpu().to(dtype),
        }
        for i, layer in enumerate(self.layers):
            prefix = f"layers.{i}"
            if not layer.disable_input_layernorm:
                state[f"{prefix}.input_layernorm.weight"] = (
                    layer.input_layernorm.weight.detach().cpu().to(dtype)
                )
            state.update({
                f"{prefix}.self_attn.q_proj.weight":
                    layer.q_proj.weight.detach().cpu().to(dtype),
                f"{prefix}.self_attn.k_proj.weight":
                    layer.k_proj.weight.detach().cpu().to(dtype),
                f"{prefix}.self_attn.v_proj.weight":
                    layer.v_proj.weight.detach().cpu().to(dtype),
                f"{prefix}.self_attn.o_proj.weight":
                    layer.o_proj.weight.detach().cpu().to(dtype),
                f"{prefix}.post_attention_layernorm.weight":
                    layer.post_attention_layernorm.weight.detach().cpu().to(dtype),
                f"{prefix}.mlp.gate_proj.weight":
                    layer.gate_proj.weight.detach().cpu().to(dtype),
                f"{prefix}.mlp.up_proj.weight":
                    layer.up_proj.weight.detach().cpu().to(dtype),
                f"{prefix}.mlp.down_proj.weight":
                    layer.down_proj.weight.detach().cpu().to(dtype),
            })
        return state


def load_target_shared_weights(target_model: str) -> tuple[torch.Tensor, torch.Tensor]:
    index_path = os.path.join(target_model, "model.safetensors.index.json")
    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)
    weight_map = index["weight_map"]
    embed_name = "model.language_model.embed_tokens.weight"
    head_name = "lm_head.weight"
    shard_names = {weight_map[embed_name], weight_map[head_name]}
    loaded: dict[str, torch.Tensor] = {}
    for shard in shard_names:
        tensors = load_file(os.path.join(target_model, shard), device="cpu")
        for name in (embed_name, head_name):
            if name in tensors:
                loaded[name] = tensors[name]
    return loaded[embed_name], loaded[head_name]


def write_config(out_dir: str, shape: DraftShape, export_dtype: str) -> None:
    config = {
        "architectures": ["LlamaForCausalLM"],
        "model_type": "llama",
        "vocab_size": shape.vocab_size,
        "hidden_size": shape.hidden_size,
        "intermediate_size": shape.intermediate_size,
        "num_hidden_layers": shape.num_hidden_layers,
        "num_attention_heads": shape.num_attention_heads,
        "num_key_value_heads": shape.num_key_value_heads,
        "head_dim": shape.head_dim,
        "hidden_act": "silu",
        "max_position_embeddings": shape.max_position_embeddings,
        "rms_norm_eps": shape.rms_norm_eps,
        "rope_theta": shape.rope_theta,
        "attention_bias": False,
        "attention_dropout": 0.0,
        "tie_word_embeddings": False,
        "bos_token_id": 248044,
        "eos_token_id": 248044,
        "pad_token_id": None,
        "torch_dtype": export_dtype,
        "dtype": export_dtype,
        "draft_vocab_size": shape.vocab_size,
    }
    generation_config = {
        "bos_token_id": 248044,
        "eos_token_id": 248044,
        "pad_token_id": None,
    }
    with open(os.path.join(out_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, sort_keys=True)
        f.write("\n")
    with open(
        os.path.join(out_dir, "generation_config.json"),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(generation_config, f, indent=2, sort_keys=True)
        f.write("\n")


def save_draft_checkpoint(
    model: Eagle1Draft,
    out_dir: str,
    shape: DraftShape,
    export_dtype: torch.dtype,
    export_dtype_name: str,
    meta: dict[str, Any] | None = None,
) -> None:
    os.makedirs(out_dir, exist_ok=True)
    save_file(model.export_state(export_dtype),
              os.path.join(out_dir, "model.safetensors"))
    write_config(out_dir, shape, export_dtype_name)
    if meta is not None:
        with open(os.path.join(out_dir, "checkpoint_meta.json"), "w",
                  encoding="utf-8") as f:
            json.dump(meta, f, indent=2, sort_keys=True)
            f.write("\n")


def load_init(
    model: Eagle1Draft,
    init_dir: str,
    repeat_last_layer: bool = False,
    zero_extra_layer: bool = False,
    residual_extra_layer: bool = False,
) -> None:
    if not init_dir:
        return
    path = os.path.join(init_dir, "model.safetensors")
    if not os.path.exists(path):
        return
    weights = load_file(path, device="cpu")
    source_layer_ids = sorted({
        int(m.group(1))
        for name in weights
        if (m := re.match(r"layers\.(\d+)\.", name))
    })
    last_source_layer = source_layer_ids[-1] if source_layer_ids else None

    def source_name(name: str) -> str:
        if name in weights or zero_extra_layer or last_source_layer is None:
            return name
        if not repeat_last_layer and not residual_extra_layer:
            return name
        match = re.match(r"layers\.(\d+)\.(.+)", name)
        if not match:
            return name
        layer_id = int(match.group(1))
        if layer_id <= last_source_layer:
            return name
        candidate = f"layers.{last_source_layer}.{match.group(2)}"
        return candidate if candidate in weights else name

    with torch.no_grad():
        mapping: dict[str, torch.nn.Parameter] = {
            "fc.weight": model.fc.weight,
        }
        for i, layer in enumerate(model.layers):
            prefix = f"layers.{i}"
            if not layer.disable_input_layernorm:
                mapping[f"{prefix}.input_layernorm.weight"] = (
                    layer.input_layernorm.weight)
            mapping.update({
                f"{prefix}.self_attn.q_proj.weight": layer.q_proj.weight,
                f"{prefix}.self_attn.k_proj.weight": layer.k_proj.weight,
                f"{prefix}.self_attn.v_proj.weight": layer.v_proj.weight,
                f"{prefix}.self_attn.o_proj.weight": layer.o_proj.weight,
                f"{prefix}.post_attention_layernorm.weight":
                    layer.post_attention_layernorm.weight,
                f"{prefix}.mlp.gate_proj.weight": layer.gate_proj.weight,
                f"{prefix}.mlp.up_proj.weight": layer.up_proj.weight,
                f"{prefix}.mlp.down_proj.weight": layer.down_proj.weight,
            })
        for name, param in mapping.items():
            src_name = source_name(name)
            if src_name in weights:
                param.copy_(weights[src_name].to(param.dtype))
                if residual_extra_layer and last_source_layer is not None:
                    match = re.match(r"layers\.(\d+)\.(.+)", name)
                    if (
                        match
                        and int(match.group(1)) > last_source_layer
                        and match.group(2) in (
                            "self_attn.o_proj.weight",
                            "mlp.down_proj.weight",
                        )
                    ):
                        param.zero_()
            elif zero_extra_layer and last_source_layer is not None:
                match = re.match(r"layers\.(\d+)\.", name)
                if match and int(match.group(1)) > last_source_layer and param.ndim > 1:
                    param.zero_()


def infer_checkpoint_layer_ids(init_dir: str) -> list[int]:
    path = os.path.join(init_dir, "model.safetensors")
    if not init_dir or not os.path.exists(path):
        return []
    weights = load_file(path, device="cpu")
    return sorted({
        int(m.group(1))
        for name in weights
        if (m := re.match(r"layers\.(\d+)\.", name))
    })


def freeze_init_base_layers(model: Eagle1Draft, init_dir: str) -> int:
    source_layer_ids = infer_checkpoint_layer_ids(init_dir)
    if not source_layer_ids:
        return 0
    last_source_layer = source_layer_ids[-1]
    model.fc.requires_grad_(False)
    frozen_layers = 0
    for layer_id, layer in enumerate(model.layers):
        if layer_id <= last_source_layer:
            layer.requires_grad_(False)
            frozen_layers += 1
    return frozen_layers


def main() -> int:
    args = parse_args()
    shape = DraftShape()
    target_config = apply_target_shape(
        shape,
        args.target_model,
        copy_target_draft_architecture=args.copy_target_draft_architecture,
    )
    apply_shape_overrides(shape, args)
    if args.num_layers < 1:
        raise ValueError("--num-layers must be at least 1")
    shape.num_hidden_layers = args.num_layers
    device = choose_device(args.device)
    train_dtype = dtype_from_name(args.train_dtype)
    export_dtype = dtype_from_name(args.export_dtype)

    os.makedirs(args.out_dir, exist_ok=True)
    dataset = EagleDataset(args.dataset_dir, args.max_len)
    dataset_hidden_size = infer_dataset_hidden_size(dataset)
    embed_weight, lm_head_weight = load_target_shared_weights(args.target_model)
    validate_shape(
        shape,
        dataset_hidden_size=dataset_hidden_size,
        embed_weight=embed_weight,
        lm_head_weight=lm_head_weight,
    )
    embed_weight = embed_weight.to(device=device, dtype=train_dtype)
    lm_head_weight = lm_head_weight.to(device=device, dtype=train_dtype)

    model = Eagle1Draft(shape, embed_weight, lm_head_weight).to(
        device=device, dtype=train_dtype)
    load_init(
        model,
        args.init_checkpoint,
        args.repeat_last_init_layer,
        args.zero_extra_init_layer,
        args.residual_extra_init_layer,
    )
    frozen_layers = (
        freeze_init_base_layers(model, args.init_checkpoint)
        if args.freeze_init_base_layers else 0
    )
    model.train()

    generator = torch.Generator()
    generator.manual_seed(args.shuffle_seed)
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=True,
        collate_fn=collate,
        generator=generator,
    )
    trainable_params = [p for p in model.parameters() if p.requires_grad]
    if not trainable_params:
        raise RuntimeError("No trainable draft parameters remain")
    optim = torch.optim.AdamW(trainable_params, lr=args.lr)
    metrics: list[dict[str, float | int]] = []

    step = 0
    for epoch in range(args.epochs):
        for batch in loader:
            step += 1
            hidden = batch["hidden"].to(device=device, dtype=train_dtype)
            draft_input_ids = batch["draft_input_ids"].to(device=device)
            positions = batch["positions"].to(device=device)
            target = batch["target"].to(device=device, dtype=train_dtype)
            target_token_ids = batch["target_token_ids"].to(device=device)
            loss_mask = batch["loss_mask"].to(device=device, dtype=train_dtype)

            if args.rollout_steps <= 1:
                pred = model(hidden, draft_input_ids, positions)
                mask = loss_mask > 0
                feature_loss = F.smooth_l1_loss(pred[mask], target[mask])
                target_ids = target_token_ids[mask]
                logits = model.logits(pred[mask])
                token_loss = F.cross_entropy(logits.float(), target_ids)
                acc_logits = logits
                acc_target_ids = target_ids
                acc_mask_tokens = int(mask.sum().detach().cpu())
            else:
                max_rollout = min(args.rollout_steps, hidden.shape[1] - 1)
                if max_rollout < 1:
                    continue
                base_len = hidden.shape[1] - max_rollout
                current_hidden = hidden[:, :base_len]
                current_ids = draft_input_ids[:, :base_len]
                current_positions = positions[:, :base_len]
                feature_losses: list[torch.Tensor] = []
                token_losses: list[torch.Tensor] = []
                acc_logits = None
                acc_target_ids = None
                acc_mask_tokens = 0
                for rollout_idx in range(1, max_rollout + 1):
                    pred = model(current_hidden, current_ids, current_positions)
                    target_hidden = hidden[:, rollout_idx:rollout_idx + base_len]
                    target_ids_all = draft_input_ids[
                        :, rollout_idx:rollout_idx + base_len
                    ]
                    mask = loss_mask[:, rollout_idx:rollout_idx + base_len] > 0
                    if not torch.any(mask):
                        current_hidden = pred
                        current_ids = target_ids_all
                        current_positions = positions[
                            :, rollout_idx:rollout_idx + base_len
                        ]
                        continue
                    feature_losses.append(
                        F.smooth_l1_loss(pred[mask], target_hidden[mask])
                    )
                    logits = model.logits(pred[mask])
                    target_ids = target_ids_all[mask]
                    token_losses.append(
                        F.cross_entropy(logits.float(), target_ids)
                    )
                    acc_logits = logits
                    acc_target_ids = target_ids
                    acc_mask_tokens += int(mask.sum().detach().cpu())
                    current_hidden = pred
                    current_ids = target_ids_all
                    current_positions = positions[
                        :, rollout_idx:rollout_idx + base_len
                    ]
                if not feature_losses or not token_losses:
                    continue
                feature_loss = torch.stack(feature_losses).mean()
                token_loss = torch.stack(token_losses).mean()
            loss = (
                args.feature_loss_weight * feature_loss
                + args.token_loss_weight * token_loss
            )

            optim.zero_grad(set_to_none=True)
            loss.backward()
            if args.grad_clip > 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
            optim.step()

            with torch.no_grad():
                assert acc_logits is not None
                assert acc_target_ids is not None
                acc1 = (
                    acc_logits.argmax(dim=-1) == acc_target_ids
                ).float().mean()
                top3 = acc_logits.topk(3, dim=-1).indices
                acc3 = (
                    top3 == acc_target_ids[:, None]
                ).any(dim=-1).float().mean()
            row = {
                "epoch": epoch + 1,
                "step": step,
                "loss": float(loss.detach().cpu()),
                "feature_loss": float(feature_loss.detach().cpu()),
                "token_loss": float(token_loss.detach().cpu()),
                "top1": float(acc1.detach().cpu()),
                "top3": float(acc3.detach().cpu()),
                "tokens": (
                    acc_mask_tokens if args.rollout_steps > 1
                    else int(mask.sum().detach().cpu())
                ),
                "rollout_steps": int(args.rollout_steps),
            }
            metrics.append(row)
            if args.log_every and step % args.log_every == 0:
                print(json.dumps(row, sort_keys=True), flush=True)
            if args.checkpoint_every and step % args.checkpoint_every == 0:
                checkpoint_dir = os.path.join(
                    args.out_dir, "checkpoints", f"step-{step:06d}")
                save_draft_checkpoint(
                    model,
                    checkpoint_dir,
                    shape,
                    export_dtype,
                    args.export_dtype,
                    {"step_metrics": row},
                )

    save_draft_checkpoint(
        model, args.out_dir, shape, export_dtype, args.export_dtype)
    summary = {
        "dataset_dir": args.dataset_dir,
        "dataset_samples": len(dataset),
        "target_model": args.target_model,
        "init_checkpoint": args.init_checkpoint,
        "repeat_last_init_layer": args.repeat_last_init_layer,
        "zero_extra_init_layer": args.zero_extra_init_layer,
        "residual_extra_init_layer": args.residual_extra_init_layer,
        "freeze_init_base_layers": args.freeze_init_base_layers,
        "frozen_init_layers": frozen_layers,
        "out_dir": args.out_dir,
        "device": str(device),
        "train_dtype": args.train_dtype,
        "export_dtype": args.export_dtype,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "max_len": args.max_len,
        "rollout_steps": args.rollout_steps,
        "feature_loss_weight": args.feature_loss_weight,
        "token_loss_weight": args.token_loss_weight,
        "grad_clip": args.grad_clip,
        "checkpoint_every": args.checkpoint_every,
        "num_layers": args.num_layers,
        "shuffle_seed": args.shuffle_seed,
        "copy_target_draft_architecture": args.copy_target_draft_architecture,
        "dataset_hidden_size": dataset_hidden_size,
        "target_config_fields_used": {
            key: target_config.get(key)
            for key in (
                "hidden_size",
                "vocab_size",
                "max_position_embeddings",
                "rope_theta",
                "rms_norm_eps",
                "intermediate_size",
                "num_attention_heads",
                "num_key_value_heads",
                "head_dim",
            )
            if key in target_config
        },
        "shape": asdict(shape),
        "final_metrics": metrics[-1] if metrics else {},
    }
    with open(os.path.join(args.out_dir, "training_metrics.json"), "w",
              encoding="utf-8") as f:
        json.dump({"summary": summary, "steps": metrics}, f, indent=2,
                  sort_keys=True)
        f.write("\n")
    with open(os.path.join(args.out_dir, "summary.json"), "w",
              encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")
    src_script = os.path.abspath(__file__)
    try:
        shutil.copy2(src_script, os.path.join(args.out_dir, os.path.basename(src_script)))
    except OSError:
        pass
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
