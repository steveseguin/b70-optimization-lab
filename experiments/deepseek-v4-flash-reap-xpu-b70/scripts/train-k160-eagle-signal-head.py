#!/usr/bin/env python3
"""Train or evaluate the one-layer K160 EAGLE signal-milestone head."""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

import torch
import torch.distributed as dist
import torch.nn as nn
import torch.nn.functional as F
from safetensors import safe_open

HIDDEN_SIZE = 4096
VOCAB_SIZE = 129280
FEATURE_BOUNDARIES = (4, 22, 43)


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
        self.attn_norm = RMSNorm(width)
        self.q_proj = nn.Linear(width, width, bias=False)
        self.k_proj = nn.Linear(width, kv_width, bias=False)
        self.v_proj = nn.Linear(width, kv_width, bias=False)
        self.o_proj = nn.Linear(width, width, bias=False)
        self.mlp_norm = RMSNorm(width)
        self.gate_up = nn.Linear(width, 2 * config.intermediate_size, bias=False)
        self.down = nn.Linear(config.intermediate_size, width, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        normed = self.attn_norm(x)
        batch, sequence, _ = normed.shape
        q = self.q_proj(normed).view(
            batch, sequence, self.num_heads, self.head_dim
        ).transpose(1, 2)
        k = self.k_proj(normed).view(
            batch, sequence, self.num_kv_heads, self.head_dim
        ).transpose(1, 2)
        v = self.v_proj(normed).view(
            batch, sequence, self.num_kv_heads, self.head_dim
        ).transpose(1, 2)
        repeat = self.num_heads // self.num_kv_heads
        k = k.repeat_interleave(repeat, dim=1)
        v = v.repeat_interleave(repeat, dim=1)
        attended = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        attended = attended.transpose(1, 2).reshape(batch, sequence, -1)
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
            norm(features[:, index]) for index, norm in enumerate(self.feature_norms)
        ]
        return self.feature_fusion(torch.cat(normalized, dim=-1))

    def step(
        self,
        feature_state: torch.Tensor,
        previous_token_ids: torch.Tensor,
        sequence: list[torch.Tensor],
    ) -> tuple[torch.Tensor, torch.Tensor, list[torch.Tensor]]:
        token = F.embedding(previous_token_ids, self.target_embedding)
        token = self.token_projection(token)
        current = self.input_fusion(torch.cat((token, feature_state), dim=-1))
        sequence = [*sequence, current]
        decoded = self.decoder(torch.stack(sequence, dim=1))[:, -1]
        projected = self.feature_output_adapter(decoded)
        logits = F.linear(self.output_norm(projected), self.target_lm_head)
        return decoded, logits, sequence

    def forward(
        self, batch: dict[str, torch.Tensor]
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        return teacher_forced_loss(self, batch)


def load_frozen_target_tensors(model_root: Path) -> tuple[torch.Tensor, torch.Tensor]:
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
    return embedding, lm_head


def eligible_anchors(keys: torch.Tensor, positions: torch.Tensor) -> torch.Tensor:
    if keys.numel() < 7:
        return torch.empty(0, dtype=torch.int64)
    eligible = (keys[:-6] == keys[6:]) & (positions[6:] == positions[:-6] + 6)
    return torch.nonzero(eligible, as_tuple=False).flatten()


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
        while True:
            if not self.shard_order:
                self.shard_order = self.shards.copy()
                self.rng.shuffle(self.shard_order)
            path = self.shard_order.pop()
            with safe_open(path, framework="pt", device="cpu") as tensors:
                current = {name: tensors.get_tensor(name) for name in tensors.keys()}
            anchors = eligible_anchors(current["request_key"], current["position_id"])
            if anchors.numel() >= self.batch_size:
                generator = torch.Generator().manual_seed(self.rng.randrange(2**31))
                self.anchor_order = anchors[torch.randperm(anchors.numel(), generator=generator)]
                self.current = current
                self.anchor_offset = 0
                return

    def next_batch(self) -> dict[str, torch.Tensor]:
        if (
            self.current is None
            or self.anchor_offset + self.batch_size > self.anchor_order.numel()
        ):
            self._next_shard()
        assert self.current is not None
        anchors = self.anchor_order[
            self.anchor_offset : self.anchor_offset + self.batch_size
        ]
        self.anchor_offset += self.batch_size
        offsets = torch.arange(7).unsqueeze(0)
        shifted = anchors.unsqueeze(1) + offsets
        labels = self.current["next_target_token_id"][shifted]
        previous = torch.cat(
            (
                self.current["input_token_id"][anchors].unsqueeze(1),
                labels[:, :-1],
            ),
            dim=1,
        )
        return {
            "features": self.current["features_bf16"][anchors],
            "previous": previous,
            "labels": labels,
            "target_final": self.current["target_final_hidden_bf16"][shifted],
        }


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
    if device.type == "xpu":
        return torch.autocast(device_type="xpu", dtype=torch.bfloat16)
    return contextlib.nullcontext()


def normalized_feature_loss(predicted: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
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
    state = model.fused_feature(batch["features"])
    sequence: list[torch.Tensor] = []
    total = torch.zeros((), device=state.device)
    ce_value = torch.zeros((), device=state.device)
    feature_value = torch.zeros((), device=state.device)
    weights = POSITION_WEIGHTS.to(state.device)
    for position in range(7):
        state, logits, sequence = model.step(
            state, batch["previous"][:, position], sequence
        )
        ce = F.cross_entropy(logits.float(), batch["labels"][:, position].long())
        projected = model.feature_output_adapter(state)
        feature = normalized_feature_loss(
            projected, batch["target_final"][:, position]
        )
        total = total + weights[position] * (ce + feature)
        ce_value = ce_value + ce.detach()
        feature_value = feature_value + feature.detach()
    return total / 7, {"ce": ce_value / 7, "feature": feature_value / 7}


def move_batch(batch: dict[str, torch.Tensor], device: torch.device) -> dict[str, torch.Tensor]:
    return {
        name: tensor.to(device=device, non_blocking=device.type == "xpu")
        for name, tensor in batch.items()
    }


def train(args: argparse.Namespace) -> int:
    device, rank, local_rank, world_size = initialize_distributed(args.device)
    torch.manual_seed(args.seed + rank)
    shards = sorted(args.data_dir.glob("features-*.safetensors"))
    stream = ShardStream(shards, rank, world_size, args.microbatch, args.seed)
    embedding, lm_head = load_frozen_target_tensors(args.model_root)
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
        return args.learning_rate * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * progress)))

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
        if rank == 0:
            row = {
                "step": step + 1,
                "loss": float(total_value),
                "ce": float(ce_value),
                "feature_regularization": float(feature_value),
                "learning_rate": lr,
                "gradient_norm": float(grad_norm),
                "elapsed_s": time.time() - started,
            }
            with metrics_path.open("a") as stream_file:
                stream_file.write(json.dumps(row) + "\n")
            if step == 0 or (step + 1) % args.log_every == 0:
                print(json.dumps(row), flush=True)
    if rank == 0:
        checkpoint = {
            "schema_version": "k160-eagle-signal-head-v1",
            "head_config": asdict(HeadConfig()),
            "state_dict": model.state_dict(),
            "trainable_parameters": trainable_parameters,
            "target_revision": "7c360e1cd4a5168099dbc54d16d929bf6df04990",
            "feature_boundaries": FEATURE_BOUNDARIES,
            "training_steps": args.steps,
            "microbatch_per_rank": args.microbatch,
            "gradient_accumulation": args.gradient_accumulation,
            "world_size": world_size,
            "effective_anchors_per_update": (
                args.microbatch * args.gradient_accumulation * world_size
            ),
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
    embedding, lm_head = load_frozen_target_tensors(args.model_root)
    model = K160EagleSignalHead(HeadConfig(), embedding, lm_head)
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    model = model.to(device).eval()
    shards = sorted(args.data_dir.glob("features-*.safetensors"))
    accepted = torch.zeros(7, dtype=torch.int64)
    cycles = 0
    category_counts: dict[str, dict[str, object]] = {}
    with args.request_manifest.open() as stream:
        request_rows = [json.loads(line) for line in stream if line.strip()]
    category_by_key = {int(row["request_key"]): row["category"] for row in request_rows}
    captured_key_order: list[int] = []
    seen_keys: set[int] = set()
    for shard in shards:
        with safe_open(shard, framework="pt", device="cpu") as tensors:
            shard_keys = tensors.get_tensor("request_key")
        for key in shard_keys.tolist():
            key = int(key)
            if key not in seen_keys:
                seen_keys.add(key)
                captured_key_order.append(key)
    if set(captured_key_order) - set(category_by_key):
        if len(captured_key_order) != len(request_rows):
            raise RuntimeError(
                "captured internal request count differs from DEV manifest"
            )
        category_by_key = {
            key: row["category"]
            for key, row in zip(captured_key_order, request_rows, strict=True)
        }
    for shard in shards:
        with safe_open(shard, framework="pt", device="cpu") as tensors:
            data = {name: tensors.get_tensor(name) for name in tensors.keys()}
        anchors = eligible_anchors(data["request_key"], data["position_id"])
        if args.max_anchors and cycles >= args.max_anchors:
            break
        if args.max_anchors:
            anchors = anchors[: max(0, args.max_anchors - cycles)]
        for offset in range(0, anchors.numel(), args.eval_batch):
            chosen = anchors[offset : offset + args.eval_batch]
            shifted = chosen.unsqueeze(1) + torch.arange(7).unsqueeze(0)
            features = data["features_bf16"][chosen].to(device)
            labels = data["next_target_token_id"][shifted]
            previous = data["input_token_id"][chosen].to(device)
            keys = data["request_key"][chosen]
            state = model.fused_feature(features)
            sequence: list[torch.Tensor] = []
            survived = torch.ones(chosen.numel(), dtype=torch.bool)
            predictions = []
            with autocast_context(device):
                for position in range(7):
                    state, logits, sequence = model.step(state, previous, sequence)
                    predicted = logits.argmax(dim=-1)
                    predictions.append(predicted.cpu())
                    previous = predicted
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
    conditional = []
    marginal = []
    for position, count in enumerate(accepted.tolist()):
        marginal.append(count / cycles if cycles else 0.0)
        denominator = cycles if position == 0 else int(accepted[position - 1])
        conditional.append(count / denominator if denominator else 0.0)
    overall = accepted.sum().item() / (7 * cycles) if cycles else 0.0
    mean_p2_p7 = sum(conditional[1:]) / 6
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
        "category_counts": category_counts,
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
    train_parser.add_argument("--model-root", type=Path, required=True)
    train_parser.add_argument("--output-dir", type=Path, required=True)
    train_parser.add_argument("--resume-checkpoint", type=Path)
    train_parser.add_argument("--device", choices=("xpu", "cpu"), default="xpu")
    train_parser.add_argument("--steps", type=int, default=500)
    train_parser.add_argument("--microbatch", type=int, default=8)
    train_parser.add_argument("--gradient-accumulation", type=int, default=8)
    train_parser.add_argument("--learning-rate", type=float, default=2e-4)
    train_parser.add_argument("--weight-decay", type=float, default=0.05)
    train_parser.add_argument("--seed", type=int, default=160719)
    train_parser.add_argument("--log-every", type=int, default=10)
    train_parser.set_defaults(function=train)

    eval_parser = subparsers.add_parser("evaluate")
    eval_parser.add_argument("--data-dir", type=Path, required=True)
    eval_parser.add_argument("--request-manifest", type=Path, required=True)
    eval_parser.add_argument("--model-root", type=Path, required=True)
    eval_parser.add_argument("--checkpoint", type=Path, required=True)
    eval_parser.add_argument("--output", type=Path, required=True)
    eval_parser.add_argument("--device", choices=("xpu", "cpu"), default="xpu")
    eval_parser.add_argument("--eval-batch", type=int, default=8)
    eval_parser.add_argument("--max-anchors", type=int, default=0)
    eval_parser.set_defaults(function=evaluate)
    args = parser.parse_args()
    return args.function(args)


if __name__ == "__main__":
    raise SystemExit(main())
