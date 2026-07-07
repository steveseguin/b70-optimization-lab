#!/usr/bin/env python3
"""Offline acceptance probe for Ex0bit Qwen3.6-27B EAGLE3/DFlash drafts.

This is a diagnostic gate, not a throughput benchmark. It consumes target-owned
Qwen27 hidden-state dataset v2 samples:

  aux_hidden_states[t]      = three target auxiliary hidden states
  sampled_next_token_ids[t] = target greedy token after row t

and simulates greedy EAGLE3 draft rollout:

  fc(cat(aux hidden at t)) + sampled_next_token_ids[t]
      -> proposed token for sampled_next_token_ids[t + 1]

The result answers whether a draft checkpoint has enough accepted-token depth on
fresh realistic prompts to justify endpoint integration/kernel work.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from safetensors.torch import load_file


@dataclass
class Eagle3Shape:
    hidden_size: int
    intermediate_size: int
    num_hidden_layers: int
    num_attention_heads: int
    num_key_value_heads: int
    head_dim: int
    vocab_size: int
    draft_vocab_size: int
    rope_theta: float
    rms_norm_eps: float
    attention_bias: bool
    norm_before_fc: bool
    norm_before_residual: bool
    logit_scale: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset-dir",
        required=True,
        action="append",
        help="Directory containing qwen36_eagle_sequence_v2 .pt files. May repeat.",
    )
    parser.add_argument("--draft-dir", required=True)
    parser.add_argument("--target-model", required=True)
    parser.add_argument("--max-steps", type=int, default=5)
    parser.add_argument("--max-samples", type=int, default=0)
    parser.add_argument("--max-starts", type=int, default=512)
    parser.add_argument("--start-stride", type=int, default=1)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--dtype", default="bfloat16",
                        choices=("float32", "bfloat16", "float16"))
    parser.add_argument("--topk", type=int, default=5)
    parser.add_argument(
        "--accept-mode",
        default="top1",
        choices=("top1", "topk-oracle"),
        help=(
            "Diagnostic acceptance rule. top1 is the real linear-draft path. "
            "topk-oracle accepts if the target token appears anywhere in the "
            "draft top-k and continues with the verified target token; this is "
            "an upper-bound probe for future tree/rerank verifier work, not a "
            "valid endpoint throughput claim."
        ),
    )
    parser.add_argument("--out", default="")
    parser.add_argument("--print-every", type=int, default=50)
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


def load_config(draft_dir: str) -> dict[str, Any]:
    path = os.path.join(draft_dir, "config.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def shape_from_config(config: dict[str, Any]) -> Eagle3Shape:
    return Eagle3Shape(
        hidden_size=int(config["hidden_size"]),
        intermediate_size=int(config["intermediate_size"]),
        num_hidden_layers=int(config.get("num_hidden_layers", 1)),
        num_attention_heads=int(config["num_attention_heads"]),
        num_key_value_heads=int(config["num_key_value_heads"]),
        head_dim=int(config.get("head_dim", 128)),
        vocab_size=int(config["vocab_size"]),
        draft_vocab_size=int(config.get("draft_vocab_size", config["vocab_size"])),
        rope_theta=float(config.get("rope_theta", 10000.0)),
        rms_norm_eps=float(config.get("rms_norm_eps", 1e-5)),
        attention_bias=bool(config.get("attention_bias", False)),
        norm_before_fc=bool(config.get("norm_before_fc", False)),
        norm_before_residual=bool(config.get("norm_before_residual", False)),
        logit_scale=float(config.get("logit_scale", 1.0)),
    )


def load_target_embed_weight(target_model: str) -> torch.Tensor:
    index_path = os.path.join(target_model, "model.safetensors.index.json")
    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)
    weight_map = index["weight_map"]
    name = "model.language_model.embed_tokens.weight"
    shard = weight_map[name]
    tensors = load_file(os.path.join(target_model, shard), device="cpu")
    return tensors[name]


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


class RMSNorm(nn.Module):
    def __init__(self, hidden_size: int, eps: float) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.ones(hidden_size))
        self.eps = eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        original_dtype = x.dtype
        x_float = x.to(torch.float32)
        variance = x_float.pow(2).mean(dim=-1, keepdim=True)
        out = x_float * torch.rsqrt(variance + self.eps)
        return (out.to(original_dtype) * self.weight)


def fused_add_rms_norm(
    x: torch.Tensor,
    residual: torch.Tensor,
    norm: RMSNorm,
) -> tuple[torch.Tensor, torch.Tensor]:
    residual = (x.to(torch.float32) + residual.to(torch.float32)).to(x.dtype)
    return norm(residual), residual


def apply_neox_rope(
    x: torch.Tensor,
    cos: torch.Tensor,
    sin: torch.Tensor,
) -> torch.Tensor:
    x1, x2 = torch.chunk(x, 2, dim=-1)
    return torch.cat((x1 * cos - x2 * sin, x2 * cos + x1 * sin), dim=-1)


class Eagle3DraftLayer(nn.Module):
    def __init__(self, shape: Eagle3Shape, layer_idx: int) -> None:
        super().__init__()
        if layer_idx != 0:
            raise NotImplementedError("Only the observed one-layer Ex0bit draft is wired")
        self.shape = shape
        self.layer_idx = layer_idx
        h = shape.hidden_size
        i = shape.intermediate_size
        qkv_in = 2 * h if layer_idx == 0 else h
        self.input_layernorm = RMSNorm(h, shape.rms_norm_eps)
        self.hidden_norm = RMSNorm(h, shape.rms_norm_eps)
        self.q_proj = nn.Linear(qkv_in,
                                shape.num_attention_heads * shape.head_dim,
                                bias=shape.attention_bias)
        self.k_proj = nn.Linear(qkv_in,
                                shape.num_key_value_heads * shape.head_dim,
                                bias=shape.attention_bias)
        self.v_proj = nn.Linear(qkv_in,
                                shape.num_key_value_heads * shape.head_dim,
                                bias=shape.attention_bias)
        self.o_proj = nn.Linear(shape.num_attention_heads * shape.head_dim, h,
                                bias=False)
        self.post_attention_layernorm = RMSNorm(h, shape.rms_norm_eps)
        self.gate_proj = nn.Linear(h, i, bias=False)
        self.up_proj = nn.Linear(h, i, bias=False)
        self.down_proj = nn.Linear(i, h, bias=False)
        inv_freq = 1.0 / (
            shape.rope_theta
            ** (torch.arange(0, shape.head_dim, 2, dtype=torch.float32)
                / shape.head_dim)
        )
        self.register_buffer("inv_freq", inv_freq, persistent=False)

    def _residual_norm(
        self,
        hidden_states: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        if self.shape.norm_before_residual:
            hidden_states = self.hidden_norm(hidden_states)
            residual = hidden_states
            return hidden_states, residual
        residual = hidden_states
        hidden_states = self.hidden_norm(hidden_states)
        return hidden_states, residual

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
        cos = freqs.cos().unsqueeze(1).to(q.dtype)
        sin = freqs.sin().unsqueeze(1).to(q.dtype)
        return apply_neox_rope(q, cos, sin), apply_neox_rope(k, cos, sin)

    def forward(
        self,
        positions: torch.Tensor,
        embeds: torch.Tensor,
        hidden_states: torch.Tensor,
        residual: torch.Tensor | None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        bsz, seq_len, _ = hidden_states.shape
        positions = positions.to(device=hidden_states.device, dtype=torch.long)
        embeds = self.input_layernorm(embeds)
        hidden_states, residual = self._residual_norm(hidden_states)
        hidden_states = torch.cat([embeds, hidden_states], dim=-1)

        q = self.q_proj(hidden_states).view(
            bsz, seq_len, self.shape.num_attention_heads, self.shape.head_dim)
        k = self.k_proj(hidden_states).view(
            bsz, seq_len, self.shape.num_key_value_heads, self.shape.head_dim)
        v = self.v_proj(hidden_states).view(
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
            torch.ones(seq_len, seq_len, device=scores.device, dtype=torch.bool),
            diagonal=1,
        )
        scores = scores.masked_fill(mask, float("-inf"))
        attn = torch.softmax(scores.float(), dim=-1).to(v.dtype)
        x = torch.matmul(attn, v).transpose(1, 2).contiguous().view(
            bsz, seq_len, self.shape.num_attention_heads * self.shape.head_dim)
        x = self.o_proj(x)
        x, residual = fused_add_rms_norm(
            x, residual, self.post_attention_layernorm)
        x = self.down_proj(F.silu(self.gate_proj(x)) * self.up_proj(x))
        return x, residual


class Ex0bitEagle3Draft(nn.Module):
    def __init__(
        self,
        shape: Eagle3Shape,
        embed_weight: torch.Tensor,
    ) -> None:
        super().__init__()
        self.shape = shape
        self.register_buffer("embed_weight", embed_weight, persistent=False)
        self.fc = nn.Linear(3 * shape.hidden_size, shape.hidden_size, bias=False)
        self.input_norm = (
            RMSNorm(3 * shape.hidden_size, shape.rms_norm_eps)
            if shape.norm_before_fc else None
        )
        self.layers = nn.ModuleList(
            [Eagle3DraftLayer(shape, i) for i in range(shape.num_hidden_layers)]
        )
        self.norm = RMSNorm(shape.hidden_size, shape.rms_norm_eps)
        self.lm_head = nn.Linear(
            shape.hidden_size,
            shape.draft_vocab_size,
            bias=False,
        )
        self.register_buffer("draft_id_to_target_id", None, persistent=False)

    def combine_hidden_states(self, aux_hidden: torch.Tensor) -> torch.Tensor:
        if self.input_norm is not None:
            aux_hidden = self.input_norm(aux_hidden)
        return self.fc(aux_hidden)

    def forward(
        self,
        input_ids: torch.Tensor,
        positions: torch.Tensor,
        hidden_states: torch.Tensor,
    ) -> torch.Tensor:
        embeds = F.embedding(input_ids, self.embed_weight).to(hidden_states.dtype)
        residual = None
        x = hidden_states
        for layer in self.layers:
            x, residual = layer(
                positions=positions,
                embeds=embeds,
                hidden_states=x,
                residual=residual,
            )
        if residual is None:
            return self.norm(x)
        x, _ = fused_add_rms_norm(x, residual, self.norm)
        return x

    def target_ids_for_draft_ids(self, draft_ids: torch.Tensor) -> torch.Tensor:
        if self.draft_id_to_target_id is None:
            return draft_ids
        base = torch.arange(
            self.shape.draft_vocab_size,
            device=draft_ids.device,
            dtype=self.draft_id_to_target_id.dtype,
        )
        targets = base + self.draft_id_to_target_id.to(draft_ids.device)
        return targets[draft_ids]

    def proposed_target_ids(self, hidden: torch.Tensor, k: int) -> torch.Tensor:
        logits = self.lm_head(hidden) * self.shape.logit_scale
        k = min(k, logits.shape[-1])
        draft_ids = torch.topk(logits, k=k, dim=-1).indices
        return self.target_ids_for_draft_ids(draft_ids)


def load_model(
    *,
    draft_dir: str,
    target_model: str,
    device: torch.device,
    dtype: torch.dtype,
) -> Ex0bitEagle3Draft:
    config = load_config(draft_dir)
    shape = shape_from_config(config)
    embed_weight = load_target_embed_weight(target_model).to(device=device, dtype=dtype)
    model = Ex0bitEagle3Draft(shape, embed_weight).to(device=device, dtype=dtype)
    tensors = load_file(os.path.join(draft_dir, "model.safetensors"), device="cpu")
    with torch.no_grad():
        model.fc.weight.copy_(tensors["fc.weight"].to(device=device, dtype=dtype))
        model.norm.weight.copy_(tensors["norm.weight"].to(device=device, dtype=dtype))
        model.lm_head.weight.copy_(
            tensors["lm_head.weight"].to(device=device, dtype=dtype))
        if "d2t" in tensors:
            model.draft_id_to_target_id = tensors["d2t"].to(
                device=device, dtype=torch.long)
        for i, layer in enumerate(model.layers):
            prefix = f"layers.{i}"
            layer.hidden_norm.weight.copy_(
                tensors[f"{prefix}.hidden_norm.weight"].to(
                    device=device, dtype=dtype))
            layer.input_layernorm.weight.copy_(
                tensors[f"{prefix}.input_layernorm.weight"].to(
                    device=device, dtype=dtype))
            layer.q_proj.weight.copy_(
                tensors[f"{prefix}.self_attn.q_proj.weight"].to(
                    device=device, dtype=dtype))
            layer.k_proj.weight.copy_(
                tensors[f"{prefix}.self_attn.k_proj.weight"].to(
                    device=device, dtype=dtype))
            layer.v_proj.weight.copy_(
                tensors[f"{prefix}.self_attn.v_proj.weight"].to(
                    device=device, dtype=dtype))
            layer.o_proj.weight.copy_(
                tensors[f"{prefix}.self_attn.o_proj.weight"].to(
                    device=device, dtype=dtype))
            layer.post_attention_layernorm.weight.copy_(
                tensors[f"{prefix}.post_attention_layernorm.weight"].to(
                    device=device, dtype=dtype))
            layer.gate_proj.weight.copy_(
                tensors[f"{prefix}.mlp.gate_proj.weight"].to(
                    device=device, dtype=dtype))
            layer.up_proj.weight.copy_(
                tensors[f"{prefix}.mlp.up_proj.weight"].to(
                    device=device, dtype=dtype))
            layer.down_proj.weight.copy_(
                tensors[f"{prefix}.mlp.down_proj.weight"].to(
                    device=device, dtype=dtype))
    model.eval()
    return model


def evaluate_start(
    *,
    model: Ex0bitEagle3Draft,
    aux_hidden: torch.Tensor,
    next_ids: torch.Tensor,
    positions: torch.Tensor,
    start: int,
    max_steps: int,
    topk: int,
    accept_mode: str,
    device: torch.device,
    dtype: torch.dtype,
) -> dict[str, Any]:
    aux_row = aux_hidden[start:start + 1].reshape(1, 1, -1)
    current_hidden = model.combine_hidden_states(
        aux_row.to(device=device, dtype=dtype))
    current_ids = next_ids[start:start + 1].to(device=device).view(1, 1)
    current_positions = positions[start:start + 1].to(device=device).view(1, 1)
    accepted = 0
    rows: list[dict[str, int | bool]] = []
    for step in range(max_steps):
        target_index = start + step + 1
        if target_index >= next_ids.shape[0]:
            break
        pred_seq = model(current_ids, current_positions, current_hidden)
        pred_hidden = pred_seq[:, -1, :]
        top_targets = model.proposed_target_ids(pred_hidden, max(1, topk))
        proposed = int(top_targets[0, 0].item())
        target = int(next_ids[target_index].item())
        top1_match = proposed == target
        topk_hit = bool((top_targets[0] == target).any().item())
        matched = top1_match if accept_mode == "top1" else topk_hit
        rows.append({
            "step": step + 1,
            "target_index": target_index,
            "proposed": proposed,
            "target": target,
            "match": matched,
            "top1_match": top1_match,
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
            [
                current_ids,
                next_ids[target_index:target_index + 1]
                .to(device=device).view(1, 1),
            ],
            dim=1,
        )
        current_positions = torch.cat(
            [
                current_positions,
                positions[target_index:target_index + 1]
                .to(device=device).view(1, 1),
            ],
            dim=1,
        )
    return {"accepted": accepted, "rows": rows}


def main() -> int:
    args = parse_args()
    if args.max_steps < 1:
        raise ValueError("--max-steps must be >= 1")
    if args.start_stride < 1:
        raise ValueError("--start-stride must be >= 1")
    if args.topk < 1:
        raise ValueError("--topk must be >= 1")
    device = choose_device(args.device)
    dtype = dtype_from_name(args.dtype)
    model = load_model(
        draft_dir=args.draft_dir,
        target_model=args.target_model,
        device=device,
        dtype=dtype,
    )
    paths = iter_sample_paths(args.dataset_dir, args.max_samples)

    start_time = time.perf_counter()
    starts = 0
    accepted_total = 0
    hist = [0 for _ in range(args.max_steps + 1)]
    conditional_den = [0 for _ in range(args.max_steps)]
    accept_hits = [0 for _ in range(args.max_steps)]
    exact_hits = [0 for _ in range(args.max_steps)]
    topk_hits = [0 for _ in range(args.max_steps)]
    sample_rows: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []
    family_stats: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"samples": 0, "starts": 0, "accepted": 0}
    )
    skipped_samples: list[dict[str, str]] = []

    with torch.no_grad():
        for sample_index, path in enumerate(paths):
            sample = torch_load(path)
            request_metadata = sample.get("request_metadata") or {}
            family = str(
                sample.get("family")
                or request_metadata.get("family")
                or "unknown"
            )
            prompt_id = sample.get("prompt_id") or request_metadata.get("prompt_id")
            if sample.get("format") != "qwen36_eagle_sequence_v2":
                skipped_samples.append({
                    "sample": os.path.basename(path),
                    "reason": "not qwen36_eagle_sequence_v2",
                })
                continue
            if "aux_hidden_states" not in sample:
                skipped_samples.append({
                    "sample": os.path.basename(path),
                    "reason": "missing aux_hidden_states",
                })
                continue
            if "sampled_next_token_ids" not in sample:
                skipped_samples.append({
                    "sample": os.path.basename(path),
                    "reason": "missing sampled_next_token_ids",
                })
                continue
            aux_hidden = sample["aux_hidden_states"]
            next_ids = sample["sampled_next_token_ids"].to(torch.long)
            length = min(aux_hidden.shape[0], next_ids.shape[0])
            if length <= args.max_steps + 1:
                skipped_samples.append({
                    "sample": os.path.basename(path),
                    "reason": "too short",
                })
                continue
            if aux_hidden.shape[1:] != (3, model.shape.hidden_size):
                skipped_samples.append({
                    "sample": os.path.basename(path),
                    "reason": f"bad aux shape {tuple(aux_hidden.shape)}",
                })
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
                    aux_hidden=aux_hidden,
                    next_ids=next_ids,
                    positions=positions,
                    start=start,
                    max_steps=args.max_steps,
                    topk=args.topk,
                    accept_mode=args.accept_mode,
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
                    step_index = int(row["step"]) - 1
                    conditional_den[step_index] += 1
                    if row["match"]:
                        accept_hits[step_index] += 1
                    if row["top1_match"]:
                        exact_hits[step_index] += 1
                    if row["topk_hit"]:
                        topk_hits[step_index] += 1
                if len(examples) < 20 and accepted < args.max_steps:
                    examples.append({
                        "sample": os.path.basename(path),
                        "family": family,
                        "prompt_id": prompt_id,
                        "start": start,
                        "accepted": accepted,
                        "rows": rows,
                    })
                if args.print_every and starts % args.print_every == 0:
                    print(json.dumps({
                        "processed_starts": starts,
                        "mean_accepted": accepted_total / starts,
                        "sample_index": sample_index,
                    }, sort_keys=True), flush=True)
            if sample_starts:
                family_stats[family]["samples"] += 1
                family_stats[family]["starts"] += sample_starts
                family_stats[family]["accepted"] += sample_accepted
                sample_rows.append({
                    "sample": os.path.basename(path),
                    "family": family,
                    "prompt_id": prompt_id,
                    "starts": sample_starts,
                    "mean_accepted": sample_accepted / sample_starts,
                    "tokens": int(length),
                })
            if args.max_starts > 0 and starts >= args.max_starts:
                break

    if starts == 0:
        raise RuntimeError("No evaluable start positions found")

    elapsed = time.perf_counter() - start_time
    per_step = []
    for i in range(args.max_steps):
        den = conditional_den[i]
        per_step.append({
            "step": i + 1,
            "conditional_denominator": den,
            "accept_hits": accept_hits[i],
            "accept_rate": accept_hits[i] / den if den else 0.0,
            "exact_hits": exact_hits[i],
            "exact_rate": exact_hits[i] / den if den else 0.0,
            "topk_hits": topk_hits[i],
            "topk_rate": topk_hits[i] / den if den else 0.0,
            "unconditional_accept_rate": accept_hits[i] / starts,
            "unconditional_exact_rate": exact_hits[i] / starts,
            "unconditional_topk_rate": topk_hits[i] / starts,
        })

    family_rows = []
    for family, stats_row in sorted(family_stats.items()):
        family_starts = int(stats_row["starts"])
        family_accepted = float(stats_row["accepted"])
        family_rows.append({
            "family": family,
            "samples": int(stats_row["samples"]),
            "starts": family_starts,
            "mean_accepted": (
                family_accepted / family_starts if family_starts else 0.0
            ),
        })

    summary = {
        "purpose": "diagnostic_ex0bit_eagle3_offline_acceptance",
        "valid_headline_throughput": False,
        "draft_dir": args.draft_dir,
        "target_model": args.target_model,
        "dataset_dir": args.dataset_dir,
        "samples_seen": len(paths),
        "starts": starts,
        "max_steps": args.max_steps,
        "start_stride": args.start_stride,
        "device": str(device),
        "dtype": args.dtype,
        "topk": args.topk,
        "accept_mode": args.accept_mode,
        "topk_oracle_valid_headline_throughput": False,
        "draft_vocab_size": model.shape.draft_vocab_size,
        "mean_accepted": accepted_total / starts,
        "acceptance_histogram": {str(i): hist[i] for i in range(len(hist))},
        "per_step": per_step,
        "elapsed_s": elapsed,
        "starts_per_s": starts / elapsed if elapsed else 0.0,
        "family_rows": family_rows,
        "sample_rows": sample_rows[:200],
        "first_mismatch_examples": examples,
        "skipped_samples": skipped_samples[:100],
        "script": str(Path(__file__).resolve()),
    }
    text = json.dumps(summary, indent=2, sort_keys=True)
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
            f.write("\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
