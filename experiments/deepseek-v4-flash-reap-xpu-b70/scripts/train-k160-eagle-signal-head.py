#!/usr/bin/env python3
"""Train or evaluate the one-layer K160 EAGLE signal-milestone head."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
import torch.distributed as dist
import torch.nn as nn
import torch.nn.functional as F
from safetensors import safe_open

HIDDEN_SIZE = 4096
VOCAB_SIZE = 129280
FEATURE_BOUNDARIES = (4, 22, 43)
CONTEXT_TOKENS = 128
TARGET_REVISION = "7c360e1cd4a5168099dbc54d16d929bf6df04990"
BASE_VLLM_COMMIT = "264c7f2f7df21ddeeab32ecca0353133344f1ac9"
CAPTURE_VLLM_COMMIT = "0e85361b220887f98639e9836fb0ffdfe8cf9a53"
XPU_KERNEL_COMMIT = "31315673737d95da0f79179c8f755260ef02c1d6"
ONECCL_COMMIT = "48fda4f0e074db005596d6899d5227d3f0316c12"


@dataclass(frozen=True)
class HeadConfig:
    hidden_size: int = HIDDEN_SIZE
    draft_width: int = 2048
    num_heads: int = 16
    num_kv_heads: int = 4
    head_dim: int = 128
    intermediate_size: int = 5504
    vocab_size: int = VOCAB_SIZE
    max_depth: int = 7
    context_tokens: int = CONTEXT_TOKENS
    feature_boundaries: tuple[int, ...] = FEATURE_BOUNDARIES


class RMSNorm(nn.Module):
    def __init__(self, width: int, eps: float = 1e-6):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(width))
        self.eps = eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        variance = x.float().pow(2).mean(dim=-1, keepdim=True)
        normalized = x.float() * torch.rsqrt(variance + self.eps)
        return normalized.to(x.dtype) * self.weight


class GQACausalBlock(nn.Module):
    def __init__(self, config: HeadConfig):
        super().__init__()
        width = config.draft_width
        kv_width = config.num_kv_heads * config.head_dim
        self.num_heads = config.num_heads
        self.num_kv_heads = config.num_kv_heads
        self.head_dim = config.head_dim
        self.context_tokens = config.context_tokens
        self.register_buffer(
            "rope_inv_freq",
            1.0
            / (
                10000
                ** (
                    torch.arange(0, config.head_dim, 2, dtype=torch.float32)
                    / config.head_dim
                )
            ),
            persistent=False,
        )
        self.attn_norm = RMSNorm(width)
        self.q_proj = nn.Linear(width, width, bias=False)
        self.k_proj = nn.Linear(width, kv_width, bias=False)
        self.v_proj = nn.Linear(width, kv_width, bias=False)
        self.o_proj = nn.Linear(width, width, bias=False)
        self.mlp_norm = RMSNorm(width)
        self.gate_up = nn.Linear(width, 2 * config.intermediate_size, bias=False)
        self.down = nn.Linear(config.intermediate_size, width, bias=False)

    def apply_rope(
        self, tensor: torch.Tensor, *, position_start: int = 0
    ) -> torch.Tensor:
        sequence = tensor.shape[-2]
        positions = torch.arange(
            position_start,
            position_start + sequence,
            device=tensor.device,
            dtype=torch.float32,
        )
        angles = torch.outer(positions, self.rope_inv_freq.to(tensor.device))
        cos = angles.cos().to(tensor.dtype)[None, None]
        sin = angles.sin().to(tensor.dtype)[None, None]
        even = tensor[..., 0::2]
        odd = tensor[..., 1::2]
        rotated = torch.stack((even * cos - odd * sin, even * sin + odd * cos), dim=-1)
        return rotated.flatten(-2)

    def forward(
        self, x: torch.Tensor, attention_mask: torch.Tensor | None = None
    ) -> torch.Tensor:
        residual = x[:, -1:]
        normed = self.attn_norm(x)
        batch, sequence, _ = normed.shape
        q = (
            self.q_proj(normed[:, -1:])
            .view(batch, 1, self.num_heads, self.head_dim)
            .transpose(1, 2)
        )
        k = (
            self.k_proj(normed)
            .view(batch, sequence, self.num_kv_heads, self.head_dim)
            .transpose(1, 2)
        )
        v = (
            self.v_proj(normed)
            .view(batch, sequence, self.num_kv_heads, self.head_dim)
            .transpose(1, 2)
        )
        q = self.apply_rope(q, position_start=sequence - 1)
        k = self.apply_rope(k)
        repeat = self.num_heads // self.num_kv_heads
        k = k.repeat_interleave(repeat, dim=1)
        v = v.repeat_interleave(repeat, dim=1)
        sdpa_mask = None
        if attention_mask is not None:
            if attention_mask.shape != (batch, sequence):
                raise ValueError("attention mask does not match decoder sequence")
            sdpa_mask = attention_mask[:, None, None, :]
        attended = F.scaled_dot_product_attention(
            q, k, v, attn_mask=sdpa_mask, is_causal=False
        )
        attended = attended.transpose(1, 2).reshape(batch, 1, -1)
        x = residual + self.o_proj(attended)
        gate, up = self.gate_up(self.mlp_norm(x)).chunk(2, dim=-1)
        return x + self.down(F.silu(gate) * up)


class K160EagleSignalHead(nn.Module):
    def __init__(
        self,
        config: HeadConfig,
        embedding: torch.Tensor,
        lm_head: torch.Tensor,
    ):
        super().__init__()
        self.config = config
        self.feature_norms = nn.ModuleList(
            RMSNorm(config.hidden_size) for _ in FEATURE_BOUNDARIES
        )
        self.feature_fusion = nn.Linear(
            len(FEATURE_BOUNDARIES) * config.hidden_size,
            config.draft_width,
            bias=False,
        )
        self.token_projection = nn.Linear(
            config.hidden_size, config.draft_width, bias=False
        )
        self.input_fusion = nn.Linear(
            2 * config.draft_width, config.draft_width, bias=False
        )
        self.decoder = GQACausalBlock(config)
        self.feature_output_adapter = nn.Linear(
            config.draft_width, config.hidden_size, bias=False
        )
        self.output_norm = RMSNorm(config.hidden_size)
        self.register_buffer("target_embedding", embedding, persistent=False)
        self.register_buffer("target_lm_head", lm_head, persistent=False)

    def fused_feature(self, features: torch.Tensor) -> torch.Tensor:
        normalized = [
            norm(value)
            for value, norm in zip(
                features.unbind(dim=-2), self.feature_norms, strict=True
            )
        ]
        return self.feature_fusion(torch.cat(normalized, dim=-1))

    def context_sequence(
        self, features: torch.Tensor, token_ids: torch.Tensor
    ) -> torch.Tensor:
        feature_state = self.fused_feature(features)
        token = F.embedding(token_ids, self.target_embedding).to(
            self.token_projection.weight.dtype
        )
        token = self.token_projection(token)
        return self.input_fusion(torch.cat((token, feature_state), dim=-1))

    def decode(
        self, sequence: torch.Tensor, attention_mask: torch.Tensor | None = None
    ) -> tuple[torch.Tensor, torch.Tensor]:
        decoded = self.decoder(sequence, attention_mask)[:, -1]
        projected = self.feature_output_adapter(decoded)
        head_input = self.output_norm(projected).to(self.target_lm_head.dtype)
        logits = F.linear(head_input, self.target_lm_head)
        return decoded, logits

    def step(
        self,
        feature_state: torch.Tensor,
        previous_token_ids: torch.Tensor,
        sequence: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        token = F.embedding(previous_token_ids, self.target_embedding).to(
            self.token_projection.weight.dtype
        )
        token = self.token_projection(token)
        current = self.input_fusion(torch.cat((token, feature_state), dim=-1))
        sequence = torch.cat((sequence[:, 1:], current.unsqueeze(1)), dim=1)
        attention_mask = torch.cat(
            (
                attention_mask[:, 1:],
                torch.ones(
                    (attention_mask.shape[0], 1),
                    dtype=torch.bool,
                    device=attention_mask.device,
                ),
            ),
            dim=1,
        )
        decoded, logits = self.decode(sequence, attention_mask)
        return decoded, logits, sequence, attention_mask

    def forward(
        self, batch: dict[str, torch.Tensor]
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        return teacher_forced_loss(self, batch)


def tensor_sha256(tensor: torch.Tensor) -> str:
    flat = tensor.detach().contiguous().view(torch.uint8).flatten()
    digest = hashlib.sha256()
    chunk_bytes = 64 * 1024 * 1024
    for start in range(0, flat.numel(), chunk_bytes):
        digest.update(memoryview(flat[start : start + chunk_bytes].numpy()))
    return digest.hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_frozen_target_tensors(
    model_root: Path,
) -> tuple[torch.Tensor, torch.Tensor, dict[str, object]]:
    with safe_open(
        model_root / "model-00001-of-00046.safetensors",
        framework="pt",
        device="cpu",
    ) as tensors:
        embedding = tensors.get_tensor("embed.weight")
    with safe_open(
        model_root / "model-00045-of-00046.safetensors",
        framework="pt",
        device="cpu",
    ) as tensors:
        lm_head = tensors.get_tensor("head.weight")
    if embedding.shape != (VOCAB_SIZE, HIDDEN_SIZE):
        raise RuntimeError(f"unexpected embedding shape: {embedding.shape}")
    if lm_head.shape != (VOCAB_SIZE, HIDDEN_SIZE):
        raise RuntimeError(f"unexpected LM-head shape: {lm_head.shape}")
    if embedding.dtype != torch.bfloat16 or lm_head.dtype != torch.bfloat16:
        raise RuntimeError("frozen target embedding and LM head must be BF16")
    identity = {
        "model_root": str(model_root.resolve()),
        "model_revision": TARGET_REVISION,
        "embedding_tensor": "model-00001-of-00046.safetensors:embed.weight",
        "embedding_sha256": tensor_sha256(embedding),
        "lm_head_tensor": "model-00045-of-00046.safetensors:head.weight",
        "lm_head_sha256": tensor_sha256(lm_head),
    }
    return embedding, lm_head, identity


def dataset_fingerprint(data_dir: Path, capture_validation: Path) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    manifest_paths = sorted(data_dir.glob("features-*.json"))
    shard_paths = sorted(data_dir.glob("features-*.safetensors"))
    if len(manifest_paths) != len(shard_paths):
        raise RuntimeError("capture shard and manifest counts differ")
    request_keys: set[int] = set()
    for index, (manifest_path, shard_path) in enumerate(
        zip(manifest_paths, shard_paths, strict=True)
    ):
        expected_stem = f"features-{index:06d}"
        if manifest_path.stem != expected_stem or shard_path.stem != expected_stem:
            raise RuntimeError("capture shard sequence is not contiguous")
        manifest = json.loads(manifest_path.read_text())
        if (
            manifest.get("schema_version") != "k160-eagle-training-capture-shard-v1"
            or manifest.get("feature_boundary_ids") != list(FEATURE_BOUNDARIES)
            or manifest.get("feature_reduction") != "post_mhc_mean_stream"
            or manifest.get("assistant_loss_mask") != "all_rows"
            or manifest.get("reset_after_shard") is not True
        ):
            raise RuntimeError(f"capture metadata contract mismatch: {manifest_path}")
        if manifest.get("shard") != shard_path.name:
            raise RuntimeError(f"capture manifest names wrong shard: {manifest_path}")
        actual_sha = file_sha256(shard_path)
        if manifest.get("sha256") != actual_sha:
            raise RuntimeError(f"capture shard checksum mismatch: {shard_path}")
        key = int(manifest["request_key"])
        if key in request_keys:
            raise RuntimeError("capture manifests contain duplicate request keys")
        request_keys.add(key)
        with safe_open(shard_path, framework="pt", device="cpu") as tensors:
            tensor_names = set(tensors.keys())
            actual_shapes = {
                name: tensors.get_slice(name).get_shape() for name in tensor_names
            }
        required = {
            "features_bf16",
            "target_final_hidden_bf16",
            "input_token_id",
            "next_target_token_id",
            "position_id",
            "request_key",
        }
        shard_rows = int(manifest["rows"])
        expected_dtypes = {
            "features_bf16": "torch.bfloat16",
            "target_final_hidden_bf16": "torch.bfloat16",
            "input_token_id": "torch.int32",
            "next_target_token_id": "torch.int32",
            "position_id": "torch.int32",
            "request_key": "torch.int64",
        }
        if {
            name: metadata.get("dtype")
            for name, metadata in manifest.get("tensors", {}).items()
        } != expected_dtypes:
            raise RuntimeError(f"capture tensor dtype mismatch: {shard_path}")
        if tensor_names != required:
            raise RuntimeError(f"capture tensor set mismatch: {shard_path}")
        expected_shapes = {
            "features_bf16": [shard_rows, 3, HIDDEN_SIZE],
            "target_final_hidden_bf16": [shard_rows, HIDDEN_SIZE],
            "input_token_id": [shard_rows],
            "next_target_token_id": [shard_rows],
            "position_id": [shard_rows],
            "request_key": [shard_rows],
        }
        if actual_shapes != expected_shapes:
            raise RuntimeError(f"capture tensor shape mismatch: {shard_path}")
        rows.append(
            {
                "shard": manifest["shard"],
                "sha256": actual_sha,
                "rows": shard_rows,
                "request_key": key,
            }
        )
    if not rows:
        raise RuntimeError(f"no capture manifests in {data_dir}")
    validation = json.loads(capture_validation.read_text())
    capture_fields = (validation.get("capture_identity") or {}).get("fields", {})
    expected_capture_fields = {
        "capture_base_vllm_commit": BASE_VLLM_COMMIT,
        "capture_patch_vllm_commit": CAPTURE_VLLM_COMMIT,
        "xpu_kernel_commit": XPU_KERNEL_COMMIT,
        "oneccl_commit": ONECCL_COMMIT,
        "model_revision": TARGET_REVISION,
        "feature_boundaries": "4,22,43",
        "feature_reduction": "post_mhc_mean_stream",
        "one_active_generation": "true",
        "speculation": "false",
    }
    if (
        validation.get("schema_version") != "k160-eagle-capture-validation-v1"
        or validation.get("alignment_passed") is not True
        or validation.get("target_token_alignment_passed") is not True
        or validation.get("request_key_mapping_mode") != "exact-replay-response-id-hash"
        or int(validation.get("captured_rows", -1))
        != sum(int(row["rows"]) for row in rows)
        or validation.get("other_prompt_set_disjoint") is not True
        or not isinstance(validation.get("other_request_manifest"), dict)
        or not isinstance(validation.get("other_prompt_set_sha256"), str)
        or any(
            capture_fields.get(key) != value
            for key, value in expected_capture_fields.items()
        )
    ):
        raise RuntimeError("capture validation does not satisfy training contract")
    matching_ranks = [
        result
        for result in validation.get("rank_results", [])
        if Path(result["rank_dir"]).resolve() == data_dir.resolve()
    ]
    if len(matching_ranks) != 1:
        raise RuntimeError("capture validation does not bind the selected rank dir")
    validated_shards = [
        {
            "shard": Path(item["path"]).name,
            "sha256": item["sha256"],
            "rows": int(item["rows"]),
        }
        for item in matching_ranks[0]["shards"]
    ]
    if validated_shards != [
        {key: row[key] for key in ("shard", "sha256", "rows")} for row in rows
    ]:
        raise RuntimeError("capture validation shard ledger differs from dataset")
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return {
        "data_dir": str(data_dir.resolve()),
        "shard_count": len(rows),
        "captured_rows": sum(int(row["rows"]) for row in rows),
        "ordered_manifest_sha256": hashlib.sha256(canonical).hexdigest(),
        "capture_validation": str(capture_validation.resolve()),
        "capture_validation_sha256": file_sha256(capture_validation),
        "request_manifest_sha256": validation["request_manifest"]["sha256"],
        "prompt_set_sha256": validation["prompt_set_sha256"],
        "other_request_manifest_sha256": validation["other_request_manifest"]["sha256"],
        "other_prompt_set_sha256": validation["other_prompt_set_sha256"],
        "other_prompt_set_disjoint": validation["other_prompt_set_disjoint"],
    }


def eligible_anchors(keys: torch.Tensor, positions: torch.Tensor) -> torch.Tensor:
    if keys.numel() < 7:
        return torch.empty(0, dtype=torch.int64)
    adjacent = (keys[1:] == keys[:-1]) & (positions[1:] == positions[:-1] + 1)
    bad_prefix = torch.cat(
        (torch.zeros(1, dtype=torch.int64), (~adjacent).to(torch.int64).cumsum(0))
    )
    anchors = torch.arange(0, keys.numel() - 6)
    start = anchors
    end = anchors + 6
    valid = (bad_prefix[end] - bad_prefix[start]) == 0
    return anchors[valid]


def context_rows_and_mask(
    keys: torch.Tensor, positions: torch.Tensor, anchors: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor]:
    offsets = torch.arange(-(CONTEXT_TOKENS - 1), 1).unsqueeze(0)
    rows = anchors.unsqueeze(1) + offsets
    in_bounds = rows >= 0
    safe_rows = rows.clamp(min=0)
    anchor_keys = keys[anchors].unsqueeze(1)
    anchor_positions = positions[anchors].unsqueeze(1)
    valid = (
        in_bounds
        & (keys[safe_rows] == anchor_keys)
        & (positions[safe_rows] == anchor_positions + offsets)
    )
    return safe_rows, valid


class ShardStream:
    def __init__(
        self,
        shards: list[Path],
        rank: int,
        world_size: int,
        batch_size: int,
        seed: int,
    ):
        self.shards = shards[rank::world_size]
        if not self.shards:
            raise RuntimeError(f"rank {rank} has no feature shards")
        self.batch_size = batch_size
        self.rng = random.Random(seed + rank)
        self.shard_order: list[Path] = []
        self.current: dict[str, torch.Tensor] | None = None
        self.anchor_order = torch.empty(0, dtype=torch.int64)
        self.anchor_offset = 0

    def _next_shard(self) -> None:
        for _ in range(len(self.shards)):
            if not self.shard_order:
                self.shard_order = self.shards.copy()
                self.rng.shuffle(self.shard_order)
            path = self.shard_order.pop()
            with safe_open(path, framework="pt", device="cpu") as tensors:
                current = {name: tensors.get_tensor(name) for name in tensors.keys()}
            anchors = eligible_anchors(current["request_key"], current["position_id"])
            if anchors.numel():
                generator = torch.Generator().manual_seed(self.rng.randrange(2**31))
                self.anchor_order = anchors[
                    torch.randperm(anchors.numel(), generator=generator)
                ]
                self.current = current
                self.anchor_offset = 0
                return
        raise RuntimeError("no assigned shard has an eligible seven-position anchor")

    def next_batch(self) -> dict[str, torch.Tensor]:
        parts: dict[str, list[torch.Tensor]] = {
            "context_features": [],
            "context_tokens": [],
            "context_mask": [],
            "labels": [],
            "target_final": [],
        }
        remaining = self.batch_size
        while remaining:
            if self.current is None or self.anchor_offset >= self.anchor_order.numel():
                self._next_shard()
            assert self.current is not None
            take = min(remaining, self.anchor_order.numel() - self.anchor_offset)
            anchors = self.anchor_order[self.anchor_offset : self.anchor_offset + take]
            self.anchor_offset += take
            remaining -= take
            shifted = anchors.unsqueeze(1) + torch.arange(7).unsqueeze(0)
            context_rows, context_mask = context_rows_and_mask(
                self.current["request_key"], self.current["position_id"], anchors
            )
            context_features = self.current["features_bf16"][context_rows]
            context_features = context_features.masked_fill(
                ~context_mask[..., None, None], 0
            )
            parts["context_features"].append(context_features)
            parts["context_tokens"].append(self.current["input_token_id"][context_rows])
            parts["context_mask"].append(context_mask)
            parts["labels"].append(self.current["next_target_token_id"][shifted])
            parts["target_final"].append(
                self.current["target_final_hidden_bf16"][shifted]
            )
        return {name: torch.cat(values, dim=0) for name, values in parts.items()}


def initialize_distributed(device_kind: str) -> tuple[torch.device, int, int, int]:
    local_rank = int(os.getenv("LOCAL_RANK", "0"))
    rank = int(os.getenv("RANK", "0"))
    world_size = int(os.getenv("WORLD_SIZE", "1"))
    if device_kind == "xpu":
        if not torch.xpu.is_available():
            raise RuntimeError("XPU requested but torch.xpu is unavailable")
        torch.xpu.set_device(local_rank)
        device = torch.device("xpu", local_rank)
        backend = "xccl"
    else:
        device = torch.device("cpu")
        backend = "gloo"
    if world_size > 1:
        dist.init_process_group(backend=backend)
    return device, rank, local_rank, world_size


def autocast_context(device: torch.device):
    if device.type in {"xpu", "cpu"}:
        return torch.autocast(device_type=device.type, dtype=torch.bfloat16)
    return contextlib.nullcontext()


def normalized_feature_loss(
    predicted: torch.Tensor, target: torch.Tensor
) -> torch.Tensor:
    predicted = F.rms_norm(predicted.float(), (predicted.shape[-1],))
    target = F.rms_norm(target.float(), (target.shape[-1],))
    smooth = F.smooth_l1_loss(predicted, target)
    cosine = 1 - F.cosine_similarity(predicted, target, dim=-1).mean()
    return 0.10 * smooth + 0.05 * cosine


POSITION_WEIGHTS = torch.tensor([1.0, 1.0, 1.1, 1.25, 1.4, 1.6, 1.8])
POSITION_WEIGHTS = POSITION_WEIGHTS / POSITION_WEIGHTS.mean()


def teacher_forced_loss(
    model: K160EagleSignalHead,
    batch: dict[str, torch.Tensor],
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    sequence = model.context_sequence(
        batch["context_features"], batch["context_tokens"]
    )
    attention_mask = batch["context_mask"]
    state, logits = model.decode(sequence, attention_mask)
    total = torch.zeros((), device=state.device)
    ce_value = torch.zeros((), device=state.device)
    feature_value = torch.zeros((), device=state.device)
    weights = POSITION_WEIGHTS.to(state.device)
    for position in range(7):
        if position:
            state, logits, sequence, attention_mask = model.step(
                state,
                batch["labels"][:, position - 1],
                sequence,
                attention_mask,
            )
        ce = F.cross_entropy(logits.float(), batch["labels"][:, position].long())
        projected = model.feature_output_adapter(state)
        feature = normalized_feature_loss(projected, batch["target_final"][:, position])
        total = total + weights[position] * (ce + feature)
        ce_value = ce_value + ce.detach()
        feature_value = feature_value + feature.detach()
    return total / 7, {"ce": ce_value / 7, "feature": feature_value / 7}


def move_batch(
    batch: dict[str, torch.Tensor], device: torch.device
) -> dict[str, torch.Tensor]:
    return {
        name: tensor.to(device=device, non_blocking=device.type == "xpu")
        for name, tensor in batch.items()
    }


def train(args: argparse.Namespace) -> int:
    device, rank, local_rank, world_size = initialize_distributed(args.device)
    torch.manual_seed(args.seed + rank)
    shards = sorted(args.data_dir.glob("features-*.safetensors"))
    stream = ShardStream(shards, rank, world_size, args.microbatch, args.seed)
    embedding, lm_head, target_tensor_identity = load_frozen_target_tensors(
        args.model_root
    )
    data_identity: dict[str, object] | None = None
    if rank == 0:
        data_identity = dataset_fingerprint(args.data_dir, args.capture_validation)
    if world_size > 1:
        objects = [data_identity]
        dist.broadcast_object_list(objects, src=0)
        data_identity = objects[0]
    assert data_identity is not None
    model = K160EagleSignalHead(HeadConfig(), embedding, lm_head).to(device)
    if args.resume_checkpoint:
        resume = torch.load(
            args.resume_checkpoint, map_location="cpu", weights_only=True
        )
        model.load_state_dict(resume["state_dict"], strict=True)
    trainable_parameters = sum(p.numel() for p in model.parameters())
    if world_size > 1:
        model_for_train: nn.Module = nn.parallel.DistributedDataParallel(
            model,
            device_ids=[local_rank] if device.type == "xpu" else None,
            broadcast_buffers=False,
        )
    else:
        model_for_train = model
    decay, no_decay = [], []
    for name, parameter in model.named_parameters():
        (no_decay if "norm" in name or parameter.ndim == 1 else decay).append(parameter)
    optimizer = torch.optim.AdamW(
        [
            {"params": decay, "weight_decay": args.weight_decay},
            {"params": no_decay, "weight_decay": 0.0},
        ],
        lr=args.learning_rate,
        betas=(0.9, 0.95),
        eps=1e-8,
    )
    warmup = max(1, int(args.steps * 0.03))

    def learning_rate(step: int) -> float:
        if step < warmup:
            return args.learning_rate * (step + 1) / warmup
        progress = (step - warmup) / max(1, args.steps - warmup)
        return args.learning_rate * (
            0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * progress))
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = args.output_dir / "training-metrics.jsonl"
    if rank == 0 and metrics_path.exists():
        raise FileExistsError(metrics_path)
    started = time.time()
    optimizer.zero_grad(set_to_none=True)
    for step in range(args.steps):
        total_value = torch.zeros((), device=device)
        ce_value = torch.zeros((), device=device)
        feature_value = torch.zeros((), device=device)
        for accumulation in range(args.gradient_accumulation):
            batch = move_batch(stream.next_batch(), device)
            sync_context = contextlib.nullcontext()
            if world_size > 1 and accumulation + 1 < args.gradient_accumulation:
                sync_context = model_for_train.no_sync()  # type: ignore[union-attr]
            with sync_context, autocast_context(device):
                loss, components = model_for_train(batch)
                loss = loss / args.gradient_accumulation
            loss.backward()
            total_value = total_value + loss.detach()
            ce_value += components["ce"] / args.gradient_accumulation
            feature_value += components["feature"] / args.gradient_accumulation
        grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        lr = learning_rate(step)
        for group in optimizer.param_groups:
            group["lr"] = lr
        optimizer.step()
        optimizer.zero_grad(set_to_none=True)
        metric_values = torch.stack((total_value, ce_value, feature_value))
        if world_size > 1:
            dist.all_reduce(metric_values, op=dist.ReduceOp.SUM)
            metric_values /= world_size
        if rank == 0:
            row = {
                "step": step + 1,
                "loss": float(metric_values[0]),
                "ce": float(metric_values[1]),
                "feature_regularization": float(metric_values[2]),
                "learning_rate": lr,
                "gradient_norm": float(grad_norm),
                "elapsed_s": time.time() - started,
            }
            with metrics_path.open("a") as stream_file:
                stream_file.write(json.dumps(row) + "\n")
            if step == 0 or (step + 1) % args.log_every == 0:
                print(json.dumps(row), flush=True)
            if (step + 1) % args.checkpoint_every == 0 and step + 1 < args.steps:
                torch.save(
                    {
                        "schema_version": "k160-eagle-signal-head-v1",
                        "head_config": asdict(HeadConfig()),
                        "state_dict": model.state_dict(),
                        "target_tensor_identity": target_tensor_identity,
                        "training_data_identity": data_identity,
                        "training_steps": step + 1,
                    },
                    args.output_dir / f"head-step-{step + 1:06d}.pt",
                )
    if rank == 0:
        checkpoint = {
            "schema_version": "k160-eagle-signal-head-v1",
            "head_config": asdict(HeadConfig()),
            "state_dict": model.state_dict(),
            "trainable_parameters": trainable_parameters,
            "target_revision": TARGET_REVISION,
            "feature_boundaries": FEATURE_BOUNDARIES,
            "training_steps": args.steps,
            "microbatch_per_rank": args.microbatch,
            "gradient_accumulation": args.gradient_accumulation,
            "world_size": world_size,
            "effective_anchors_per_update": (
                args.microbatch * args.gradient_accumulation * world_size
            ),
            "target_tensor_identity": target_tensor_identity,
            "training_data_identity": data_identity,
        }
        torch.save(checkpoint, args.output_dir / "head-final.pt")
        (args.output_dir / "training-config.json").write_text(
            json.dumps(
                {
                    key: str(value) if isinstance(value, Path) else value
                    for key, value in vars(args).items()
                }
                | {
                    "head_config": asdict(HeadConfig()),
                    "trainable_parameters": trainable_parameters,
                    "target_tensor_identity": target_tensor_identity,
                    "training_data_identity": data_identity,
                },
                indent=2,
            )
            + "\n"
        )
    if world_size > 1:
        dist.barrier()
        dist.destroy_process_group()
    return 0


@torch.inference_mode()
def evaluate(args: argparse.Namespace) -> int:
    device = torch.device(args.device)
    if device.type == "xpu":
        torch.xpu.set_device(0)
    embedding, lm_head, target_tensor_identity = load_frozen_target_tensors(
        args.model_root
    )
    model = K160EagleSignalHead(HeadConfig(), embedding, lm_head)
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    if (
        checkpoint.get("schema_version") != "k160-eagle-signal-head-v1"
        or checkpoint.get("head_config") != asdict(HeadConfig())
        or tuple(checkpoint.get("feature_boundaries", ())) != FEATURE_BOUNDARIES
    ):
        raise RuntimeError("checkpoint architecture contract mismatch")
    if checkpoint.get("target_tensor_identity") != target_tensor_identity:
        raise RuntimeError("checkpoint frozen target tensor identity mismatch")
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    model = model.to(device).eval()
    shards = sorted(args.data_dir.glob("features-*.safetensors"))
    data_identity = dataset_fingerprint(args.data_dir, args.capture_validation)
    training_data_identity = checkpoint.get("training_data_identity")
    if not isinstance(training_data_identity, dict):
        raise RuntimeError("checkpoint lacks training-data identity")
    if (
        data_identity["other_prompt_set_sha256"]
        != training_data_identity.get("prompt_set_sha256")
        or training_data_identity.get("other_prompt_set_sha256")
        != data_identity["prompt_set_sha256"]
        or data_identity["prompt_set_sha256"]
        == training_data_identity.get("prompt_set_sha256")
    ):
        raise RuntimeError("DEV capture is not reciprocally disjoint from training")
    accepted = torch.zeros(7, dtype=torch.int64)
    cycles = 0
    category_counts: dict[str, dict[str, object]] = {}
    with args.request_manifest.open() as stream:
        request_rows = [json.loads(line) for line in stream if line.strip()]
    if file_sha256(args.request_manifest) != data_identity["request_manifest_sha256"]:
        raise RuntimeError("DEV request manifest differs from capture validation")
    with args.replay_manifest.open() as stream:
        replay_rows = [json.loads(line) for line in stream if line.strip()]
    if len(replay_rows) != len(request_rows):
        raise RuntimeError("DEV replay and trajectory manifest lengths differ")
    category_by_key: dict[int, str] = {}
    prompt_hashes: set[str] = set()
    for index, (replay_row, trajectory) in enumerate(
        zip(replay_rows, request_rows, strict=True)
    ):
        if (
            int(replay_row["trajectory_index"]) != index
            or replay_row["trajectory_request_id"] != trajectory["request_id"]
        ):
            raise RuntimeError("DEV replay lineage does not match trajectories")
        key = int(replay_row["request_key"])
        if key in category_by_key:
            raise RuntimeError("DEV replay request-key collision")
        category_by_key[key] = trajectory["category"]
        prompt_hashes.add(trajectory["prompt_sha256"])
    evaluated_keys: set[int] = set()
    captured_rows = 0
    for shard in shards:
        with safe_open(shard, framework="pt", device="cpu") as tensors:
            data = {name: tensors.get_tensor(name) for name in tensors.keys()}
        anchors = eligible_anchors(data["request_key"], data["position_id"])
        captured_rows += int(data["request_key"].numel())
        if args.max_anchors and cycles >= args.max_anchors:
            break
        if args.max_anchors:
            anchors = anchors[: max(0, args.max_anchors - cycles)]
        for offset in range(0, anchors.numel(), args.eval_batch):
            chosen = anchors[offset : offset + args.eval_batch]
            shifted = chosen.unsqueeze(1) + torch.arange(7).unsqueeze(0)
            context_rows, context_mask = context_rows_and_mask(
                data["request_key"], data["position_id"], chosen
            )
            context_features = data["features_bf16"][context_rows]
            context_features = context_features.masked_fill(
                ~context_mask[..., None, None], 0
            ).to(device)
            context_tokens = data["input_token_id"][context_rows].to(device)
            context_mask = context_mask.to(device)
            labels = data["next_target_token_id"][shifted]
            keys = data["request_key"][chosen]
            evaluated_keys.update(map(int, keys.tolist()))
            survived = torch.ones(chosen.numel(), dtype=torch.bool)
            predictions = []
            with autocast_context(device):
                sequence = model.context_sequence(context_features, context_tokens)
                state, logits = model.decode(sequence, context_mask)
                previous_prediction = None
                for position in range(7):
                    if position:
                        assert previous_prediction is not None
                        state, logits, sequence, context_mask = model.step(
                            state, previous_prediction, sequence, context_mask
                        )
                    predicted = logits.argmax(dim=-1)
                    predictions.append(predicted.cpu())
                    previous_prediction = predicted
            for position, predicted in enumerate(predictions):
                survived &= predicted == labels[:, position]
                accepted[position] += survived.sum()
            for row_index, key in enumerate(keys.tolist()):
                category = category_by_key[int(key)]
                bucket = category_counts.setdefault(
                    category, {"cycles": 0, "accepted": [0] * 7}
                )
                bucket["cycles"] = int(bucket["cycles"]) + 1
                row_survived = True
                accepted_list = bucket["accepted"]
                assert isinstance(accepted_list, list)
                for position, predicted in enumerate(predictions):
                    row_survived &= int(predicted[row_index]) == int(
                        labels[row_index, position]
                    )
                    accepted_list[position] += int(row_survived)
            cycles += chosen.numel()
    if cycles == 0:
        raise RuntimeError("DEV evaluation found zero eligible 128-token anchors")
    conditional = []
    marginal = []
    for position, count in enumerate(accepted.tolist()):
        marginal.append(count / cycles if cycles else 0.0)
        denominator = cycles if position == 0 else int(accepted[position - 1])
        conditional.append(count / denominator if denominator else 0.0)
    overall = accepted.sum().item() / (7 * cycles) if cycles else 0.0
    mean_p2_p7 = sum(conditional[1:]) / 6
    category_metrics = {}
    for category, bucket in category_counts.items():
        category_cycles = int(bucket["cycles"])
        category_accepted = [int(value) for value in bucket["accepted"]]
        category_conditional = []
        for position, count in enumerate(category_accepted):
            denominator = (
                category_cycles if position == 0 else category_accepted[position - 1]
            )
            category_conditional.append(count / denominator if denominator else 0.0)
        category_metrics[category] = {
            **bucket,
            "conditional_acceptance": category_conditional,
            "overall_draft_token_acceptance": (
                sum(category_accepted) / (7 * category_cycles)
                if category_cycles
                else 0.0
            ),
        }
    result = {
        "schema_version": "k160-eagle-signal-offline-eval-v1",
        "cycles": cycles,
        "accepted_through_position_counts": accepted.tolist(),
        "marginal_acceptance": marginal,
        "conditional_acceptance": conditional,
        "p1": conditional[0],
        "mean_conditional_p2_p7": mean_p2_p7,
        "overall_draft_token_acceptance": overall,
        "emitted_tokens_per_cycle_estimate": 1 + accepted.sum().item() / cycles,
        "category_metrics": category_metrics,
        "coverage": {
            "captured_rows": captured_rows,
            "eligible_anchors": cycles,
            "request_count": len(request_rows),
            "requests_with_eligible_anchor": len(evaluated_keys),
            "requests_without_seven_token_anchor": (
                len(request_rows) - len(evaluated_keys)
            ),
        },
        "head_config": asdict(HeadConfig()),
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_sha256": file_sha256(args.checkpoint),
        "target_tensor_identity": target_tensor_identity,
        "evaluation_data_identity": data_identity,
        "request_manifest": str(args.request_manifest.resolve()),
        "request_manifest_sha256": file_sha256(args.request_manifest),
        "replay_manifest": str(args.replay_manifest.resolve()),
        "replay_manifest_sha256": file_sha256(args.replay_manifest),
        "prompt_set_sha256": hashlib.sha256(
            "\n".join(sorted(prompt_hashes)).encode()
        ).hexdigest(),
        "gate": {
            "p1_at_least_0_76": conditional[0] >= 0.76,
            "mean_conditional_p2_p7_above_0_75": mean_p2_p7 > 0.75,
            "overall_at_least_0_40": overall >= 0.40,
        },
    }
    result["gate"]["passed"] = all(result["gate"].values())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    train_parser = subparsers.add_parser("train")
    train_parser.add_argument("--data-dir", type=Path, required=True)
    train_parser.add_argument("--capture-validation", type=Path, required=True)
    train_parser.add_argument("--model-root", type=Path, required=True)
    train_parser.add_argument("--output-dir", type=Path, required=True)
    train_parser.add_argument("--resume-checkpoint", type=Path)
    train_parser.add_argument("--device", choices=("xpu", "cpu"), default="xpu")
    train_parser.add_argument("--steps", type=int, default=500)
    train_parser.add_argument("--microbatch", type=int, default=64)
    train_parser.add_argument("--gradient-accumulation", type=int, default=32)
    train_parser.add_argument("--learning-rate", type=float, default=2e-4)
    train_parser.add_argument("--weight-decay", type=float, default=0.05)
    train_parser.add_argument("--seed", type=int, default=160719)
    train_parser.add_argument("--log-every", type=int, default=10)
    train_parser.add_argument("--checkpoint-every", type=int, default=250)
    train_parser.set_defaults(function=train)

    eval_parser = subparsers.add_parser("evaluate")
    eval_parser.add_argument("--data-dir", type=Path, required=True)
    eval_parser.add_argument("--capture-validation", type=Path, required=True)
    eval_parser.add_argument("--request-manifest", type=Path, required=True)
    eval_parser.add_argument("--replay-manifest", type=Path, required=True)
    eval_parser.add_argument("--model-root", type=Path, required=True)
    eval_parser.add_argument("--checkpoint", type=Path, required=True)
    eval_parser.add_argument("--output", type=Path, required=True)
    eval_parser.add_argument("--device", choices=("xpu", "cpu"), default="xpu")
    eval_parser.add_argument("--eval-batch", type=int, default=64)
    eval_parser.add_argument("--max-anchors", type=int, default=0)
    eval_parser.set_defaults(function=evaluate)
    args = parser.parse_args()
    return args.function(args)


if __name__ == "__main__":
    raise SystemExit(main())
