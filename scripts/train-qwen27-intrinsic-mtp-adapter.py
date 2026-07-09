#!/usr/bin/env python3
"""Train Qwen3.6 27B intrinsic-MTP parameters offline.

This script is an experimental draft-acceptance tool. It trains a small,
optionally mergeable subset of the built-in Qwen MTP module against recorded
target hidden-state sequence shards. FC, position-FC, position-adapter, and
norm-only scopes export an updated model_extra_tensors.safetensors candidate;
deeper attention/MLP scopes export diagnostic dense updates only because the
endpoint checkpoint stores those weights as GPTQ-packed tensors. This does not
change the target model or produce a throughput claim; endpoint validation is
still required.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
from safetensors.torch import load_file, save_file


def load_eval_module() -> Any:
    path = Path(__file__).with_name("evaluate-qwen27-intrinsic-mtp-offline.py")
    spec = importlib.util.spec_from_file_location("qwen27_intrinsic_mtp_eval", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load evaluator module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EVAL = load_eval_module()


NORM_ATTRS = [
    "pre_fc_norm_embedding",
    "pre_fc_norm_hidden",
    "input_layernorm",
    "post_attention_layernorm",
    "q_norm",
    "k_norm",
    "final_norm",
]
ATTN_ATTRS = [
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "input_layernorm",
    "post_attention_layernorm",
    "q_norm",
    "k_norm",
]
MLP_ATTRS = [
    "gate_proj",
    "up_proj",
    "down_proj",
    "post_attention_layernorm",
    "final_norm",
]
MERGEABLE_MODEL_EXTRA_ATTRS = set(["fc", *NORM_ATTRS])
POSITION_FC_SCOPES = {"position-fc", "position-fc-norms"}
POSITION_ADAPTER_SCOPE = "position-adapter"
POSITION_ADAPTER_INIT_STD = 0.01


@dataclass(frozen=True)
class StartRef:
    sample_index: int
    start: int


def parse_position_fc_indices(value: str) -> tuple[int, ...]:
    if not value.strip():
        return ()
    indices: list[int] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            raise argparse.ArgumentTypeError(
                "position FC indices must be comma-separated integers"
            )
        try:
            index = int(item)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"invalid position FC index {item!r}"
            ) from exc
        if index < 0:
            raise argparse.ArgumentTypeError(
                f"position FC index must be non-negative, got {index}"
            )
        if index in indices:
            raise argparse.ArgumentTypeError(
                f"duplicate position FC index {index}"
            )
        indices.append(index)
    return tuple(sorted(indices))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default=EVAL.DEFAULT_MODEL_DIR)
    parser.add_argument(
        "--dataset-dir",
        default=[],
        action="append",
        help="Directory containing qwen36_eagle_sequence_v1 .pt files. May repeat.",
    )
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max-steps", type=int, default=3)
    parser.add_argument("--heldout-samples", type=int, default=4)
    parser.add_argument("--train-starts", type=int, default=2048)
    parser.add_argument("--heldout-starts", type=int, default=768)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--lr", type=float, default=2e-6)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=27)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--dtype", default="bfloat16",
                        choices=("float32", "bfloat16", "float16"))
    parser.add_argument(
        "--draft-lm-head",
        default="bf16",
        choices=("bf16", "int4-dequant"),
        help="Offline drafter logit head; int4-dequant matches endpoint draft INT4.",
    )
    parser.add_argument("--draft-lm-head-group-size", type=int, default=128)
    parser.add_argument(
        "--draft-lm-head-scale-dtype",
        default="bf16",
        choices=("bf16", "fp16", "fp32"),
    )
    parser.add_argument(
        "--scope",
        default="fc",
        choices=(
            "fc",
            "fc-norms",
            "position-fc",
            "position-fc-norms",
            POSITION_ADAPTER_SCOPE,
            "attn",
            "mlp",
            "attn-mlp",
            "all-dense",
        ),
        help=(
            "MTP parameter subset to train. position-fc scopes clone one FC per "
            "--max-steps position; position-adapter trains one post-MTP residual "
            "adapter per existing position FC and freezes those FCs; "
            "attn/mlp/attn-mlp/all-dense are diagnostic only unless a later GPTQ "
            "re-quant/export path is added."
        ),
    )
    parser.add_argument(
        "--position-adapter-rank",
        type=int,
        default=64,
        help="Low-rank width used by the position-adapter scope.",
    )
    parser.add_argument(
        "--freeze-position-fcs",
        type=parse_position_fc_indices,
        default=(),
        metavar="INDICES",
        help=(
            "Comma-separated zero-based position FC indices to keep frozen and "
            "exclude from the optimizer, for example 0 or 0,2."
        ),
    )
    parser.add_argument(
        "--loss-mode",
        default="all-steps",
        choices=("all-steps", "conditional-prefix"),
        help=(
            "Training loss weighting. all-steps preserves the existing mean over "
            "every rollout step; conditional-prefix includes a row at a later "
            "step only while its prior greedy proposal prefix matched."
        ),
    )
    parser.add_argument("--eval-every", type=int, default=0)
    parser.add_argument("--print-every", type=int, default=50)
    return parser.parse_args()


def load_samples(paths: list[str]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for path in paths:
        sample = EVAL.torch_load(path)
        if not str(sample.get("format", "")).startswith("qwen36_eagle_sequence_v"):
            continue
        if "hidden_state" not in sample or "sampled_next_token_ids" not in sample:
            continue
        sample.pop("aux_hidden_states", None)
        length = min(sample["hidden_state"].shape[0],
                     sample["sampled_next_token_ids"].shape[0])
        if length < 8:
            continue
        sample["_path"] = path
        sample["_length"] = length
        sample["_positions"] = EVAL.make_positions(sample, length)
        samples.append(sample)
    if not samples:
        raise FileNotFoundError("No usable qwen36_eagle_sequence_v1 samples found")
    return samples


def collect_starts(samples: list[dict[str, Any]], max_steps: int,
                   limit: int) -> list[StartRef]:
    refs: list[StartRef] = []
    for sample_index, sample in enumerate(samples):
        length = int(sample["_length"])
        for start in range(0, max(0, length - max_steps - 1)):
            refs.append(StartRef(sample_index=sample_index, start=start))
    if limit > 0 and len(refs) > limit:
        refs = random.sample(refs, limit)
    return refs


def position_fc_name(index: int) -> str:
    return f"position_fcs.{index}"


def position_fc_index(name: str) -> int | None:
    prefix = "position_fcs."
    if not name.startswith(prefix):
        return None
    value = name.removeprefix(prefix)
    if not value.isdigit() or str(int(value)) != value:
        return None
    return int(value)


def position_adapter_name(index: int, direction: str) -> str:
    if direction not in {"down", "up"}:
        raise ValueError(f"Unknown position adapter direction {direction!r}")
    return f"position_adapters.{index}.{direction}"


def position_adapter_parts(name: str) -> tuple[int, str] | None:
    match = EVAL.DIAGNOSTIC_POSITION_ADAPTER_ATTR_RE.fullmatch(name)
    if match is None:
        return None
    return int(match.group(1)), match.group(2)


def model_tensor(model: torch.nn.Module, name: str) -> torch.Tensor:
    index = position_fc_index(name)
    if index is not None:
        return model.position_fcs[index]
    adapter = position_adapter_parts(name)
    if adapter is not None:
        index, direction = adapter
        return getattr(model, f"position_adapter_{direction}")[index]
    return getattr(model, name)


def make_trainable(
    model: torch.nn.Module,
    scope: str,
    max_steps: int | None = None,
    frozen_position_fc_indices: tuple[int, ...] = (),
    position_adapter_rank: int = 64,
    position_adapter_seed: int = 27,
) -> list[torch.nn.Parameter]:
    position_params: list[torch.nn.Parameter] = []
    position_adapter_params: list[torch.nn.Parameter] = []
    frozen_indices = tuple(sorted(set(frozen_position_fc_indices)))
    position_adapter_initialization = ""
    if scope == POSITION_ADAPTER_SCOPE:
        if frozen_indices:
            raise ValueError(
                "--freeze-position-fcs is unnecessary for position-adapter; "
                "all existing position FCs are frozen"
            )
        if max_steps is None or max_steps < 1:
            raise ValueError("position-adapter scope requires max_steps >= 1")
        if position_adapter_rank < 1:
            raise ValueError("--position-adapter-rank must be >= 1")
        position_fc_count = int(getattr(model, "position_fc_count", 0))
        if position_fc_count != max_steps:
            raise ValueError(
                "position-adapter scope requires one existing position FC per "
                f"rollout step; found {position_fc_count}, expected {max_steps}"
            )
        for index, position_fc in enumerate(model.position_fcs):
            if tuple(position_fc.shape) != tuple(model.fc.shape):
                raise ValueError(
                    f"position_fcs.{index} shape {tuple(position_fc.shape)} does "
                    f"not match mtp.fc.weight shape {tuple(model.fc.shape)}"
                )
            position_fc.requires_grad_(False)

        hidden_size = int(model.fc.shape[0])
        generator = torch.Generator(device="cpu")
        generator.manual_seed(position_adapter_seed)
        adapter_down: list[torch.nn.Parameter] = []
        adapter_up: list[torch.nn.Parameter] = []
        for _ in range(max_steps):
            down = torch.empty(
                (position_adapter_rank, hidden_size), dtype=torch.float32
            )
            torch.nn.init.normal_(
                down,
                mean=0.0,
                std=POSITION_ADAPTER_INIT_STD,
                generator=generator,
            )
            adapter_down.append(torch.nn.Parameter(
                down.to(device=model.fc.device, dtype=model.fc.dtype)
            ))
            adapter_up.append(torch.nn.Parameter(torch.zeros(
                (hidden_size, position_adapter_rank),
                device=model.fc.device,
                dtype=model.fc.dtype,
            )))
        model.position_adapter_down = torch.nn.ParameterList(adapter_down)
        model.position_adapter_up = torch.nn.ParameterList(adapter_up)
        model.position_adapter_count = max_steps
        model.position_adapter_rank = position_adapter_rank
        model.position_adapter_down_keys = tuple(
            f"mtp.position_adapters.{index}.down.weight"
            for index in range(max_steps)
        )
        model.position_adapter_up_keys = tuple(
            f"mtp.position_adapters.{index}.up.weight"
            for index in range(max_steps)
        )
        model.position_adapter_keys = tuple(
            key
            for index in range(max_steps)
            for key in (
                model.position_adapter_down_keys[index],
                model.position_adapter_up_keys[index],
            )
        )
        position_adapter_params = [
            parameter
            for index in range(max_steps)
            for parameter in (adapter_down[index], adapter_up[index])
        ]
        names = [
            position_adapter_name(index, direction)
            for index in range(max_steps)
            for direction in ("down", "up")
        ]
        shared_names: list[str] = []
        trainable_indices: tuple[int, ...] = ()
        frozen_indices = tuple(range(max_steps))
        position_fc_initialization = "loaded_existing_frozen"
        position_adapter_initialization = (
            f"down_normal_std_{POSITION_ADAPTER_INIT_STD:g}_seed_"
            f"{position_adapter_seed};up_zeros"
        )
    elif scope in POSITION_FC_SCOPES:
        if max_steps is None or max_steps < 1:
            raise ValueError("position-fc scopes require max_steps >= 1")
        invalid_indices = [
            index for index in frozen_indices
            if index < 0 or index >= max_steps
        ]
        if invalid_indices:
            raise ValueError(
                "--freeze-position-fcs indices must be less than --max-steps; "
                f"got {invalid_indices} with max_steps={max_steps}"
            )
        model.position_fcs = torch.nn.ParameterList([
            torch.nn.Parameter(model.fc.detach().clone())
            for _ in range(max_steps)
        ])
        model.position_fc_count = max_steps
        model.position_fc_keys = tuple(
            f"mtp.position_fcs.{index}.weight" for index in range(max_steps)
        )
        trainable_indices = tuple(
            index for index in range(max_steps) if index not in frozen_indices
        )
        for index in frozen_indices:
            model.position_fcs[index].requires_grad_(False)
        position_params = [model.position_fcs[index] for index in trainable_indices]
        names = [position_fc_name(index) for index in trainable_indices]
        if scope == "position-fc-norms":
            names.extend(NORM_ATTRS)
        shared_names = NORM_ATTRS if scope == "position-fc-norms" else []
        position_fc_initialization = "cloned_from_mtp.fc.weight"
    elif frozen_indices:
        raise ValueError("--freeze-position-fcs requires a position-fc scope")
    elif scope == "fc":
        names = ["fc"]
        shared_names = names
        trainable_indices = ()
        position_fc_initialization = ""
    elif scope == "fc-norms":
        names = ["fc", *NORM_ATTRS]
        shared_names = names
        trainable_indices = ()
        position_fc_initialization = ""
    elif scope == "attn":
        names = ATTN_ATTRS
        shared_names = names
        trainable_indices = ()
        position_fc_initialization = ""
    elif scope == "mlp":
        names = MLP_ATTRS
        shared_names = names
        trainable_indices = ()
        position_fc_initialization = ""
    elif scope == "attn-mlp":
        names = sorted(set([*ATTN_ATTRS, *MLP_ATTRS]))
        shared_names = names
        trainable_indices = ()
        position_fc_initialization = ""
    elif scope == "all-dense":
        names = sorted(set(["fc", *NORM_ATTRS, *ATTN_ATTRS, *MLP_ATTRS]))
        shared_names = names
        trainable_indices = ()
        position_fc_initialization = ""
    else:
        raise ValueError(scope)

    params = [*position_params, *position_adapter_params]
    for name in shared_names:
        tensor = getattr(model, name)
        param = torch.nn.Parameter(tensor.detach().clone())
        setattr(model, name, param)
        params.append(param)
    model._diagnostic_trainable_names = list(names)
    model._diagnostic_trainable_param_count = sum(p.numel() for p in params)
    model._position_fc_trainable_count = len(position_params)
    model._position_fc_trainable_param_count = sum(
        p.numel() for p in position_params
    )
    model._position_fc_frozen_indices = frozen_indices
    model._position_fc_trainable_indices = trainable_indices
    model._position_fc_initialization = position_fc_initialization
    model._position_adapter_trainable_count = (
        int(getattr(model, "position_adapter_count", 0))
        if position_adapter_params else 0
    )
    model._position_adapter_trainable_tensor_count = len(position_adapter_params)
    model._position_adapter_trainable_param_count = sum(
        p.numel() for p in position_adapter_params
    )
    model._position_adapter_initialization = position_adapter_initialization
    model._position_adapter_seed = (
        position_adapter_seed if position_adapter_params else None
    )
    return params


def build_batch(
    samples: list[dict[str, Any]],
    refs: list[StartRef],
    device: torch.device,
    dtype: torch.dtype,
    max_steps: int,
) -> dict[str, torch.Tensor]:
    hidden_rows = []
    ids_rows = []
    position_rows = []
    target_rows = []
    target_position_rows = []
    for ref in refs:
        sample = samples[ref.sample_index]
        start = ref.start
        hidden = sample["hidden_state"][start].to(torch.float32)
        next_ids = sample["sampled_next_token_ids"].to(torch.long)
        positions = sample["_positions"].to(torch.long)
        hidden_rows.append(hidden)
        ids_rows.append(next_ids[start])
        position_rows.append(positions[start])
        target_rows.append(next_ids[start + 1:start + 1 + max_steps])
        target_position_rows.append(positions[start + 1:start + 1 + max_steps])
    return {
        "hidden": torch.stack(hidden_rows, dim=0).to(device=device, dtype=dtype).view(
            len(refs), 1, -1),
        "ids": torch.stack(ids_rows, dim=0).to(device=device).view(len(refs), 1),
        "positions": torch.stack(position_rows, dim=0).to(device=device).view(
            len(refs), 1),
        "targets": torch.stack(target_rows, dim=0).to(device=device),
        "target_positions": torch.stack(target_position_rows, dim=0).to(
            device=device),
    }


def rollout_loss(
    model: Any,
    batch: dict[str, torch.Tensor],
    max_steps: int,
    loss_mode: str = "all-steps",
) -> tuple[torch.Tensor, list[float]]:
    if loss_mode not in {"all-steps", "conditional-prefix"}:
        raise ValueError(f"Unknown loss mode {loss_mode!r}")
    current_hidden = batch["hidden"]
    current_ids = batch["ids"]
    current_positions = batch["positions"]
    targets = batch["targets"]
    target_positions = batch["target_positions"]
    losses: list[torch.Tensor] = []
    conditional_loss_sum: torch.Tensor | None = None
    conditional_loss_rows = 0
    alive = torch.ones(
        targets.shape[0], dtype=torch.bool, device=targets.device
    )
    accs: list[float] = []
    for step in range(max_steps):
        pred_seq = model(
            current_hidden,
            current_ids,
            current_positions,
            spec_step_idx=step,
        )
        pred_hidden = pred_seq[:, -1, :]
        logits = model.logits(pred_hidden)
        target = targets[:, step]
        if loss_mode == "all-steps":
            losses.append(F.cross_entropy(logits.float(), target))
        else:
            per_row_loss = F.cross_entropy(
                logits.float(), target, reduction="none"
            )
            active_loss = per_row_loss[alive]
            if active_loss.numel():
                step_loss_sum = active_loss.sum()
                conditional_loss_sum = (
                    step_loss_sum if conditional_loss_sum is None
                    else conditional_loss_sum + step_loss_sum
                )
                conditional_loss_rows += active_loss.numel()
        proposed = torch.argmax(logits, dim=-1)
        accs.append(float((proposed == target).float().mean().item()))
        if loss_mode == "conditional-prefix":
            alive = alive & proposed.detach().eq(target)
        current_hidden = torch.cat([current_hidden, pred_hidden[:, None, :]], dim=1)
        current_ids = torch.cat([current_ids, target[:, None]], dim=1)
        current_positions = torch.cat(
            [current_positions, target_positions[:, step:step + 1]],
            dim=1,
        )
    if loss_mode == "all-steps":
        return torch.stack(losses).mean(), accs
    if conditional_loss_sum is None or conditional_loss_rows == 0:
        raise RuntimeError("conditional-prefix loss selected no rows")
    return conditional_loss_sum / conditional_loss_rows, accs


def evaluate_batched(
    model: Any,
    samples: list[dict[str, Any]],
    refs: list[StartRef],
    device: torch.device,
    dtype: torch.dtype,
    max_steps: int,
    batch_size: int,
) -> dict[str, Any]:
    hist = [0 for _ in range(max_steps + 1)]
    conditional_den = [0 for _ in range(max_steps)]
    exact_hits = [0 for _ in range(max_steps)]
    accepted_total = 0
    starts = 0
    with torch.no_grad():
        for offset in range(0, len(refs), batch_size):
            batch_refs = refs[offset:offset + batch_size]
            batch = build_batch(samples, batch_refs, device, dtype, max_steps)
            current_hidden = batch["hidden"]
            current_ids = batch["ids"]
            current_positions = batch["positions"]
            targets = batch["targets"]
            target_positions = batch["target_positions"]
            alive = torch.ones(len(batch_refs), dtype=torch.bool, device=device)
            accepted = torch.zeros(len(batch_refs), dtype=torch.long, device=device)
            for step in range(max_steps):
                pred_seq = model(
                    current_hidden,
                    current_ids,
                    current_positions,
                    spec_step_idx=step,
                )
                pred_hidden = pred_seq[:, -1, :]
                logits = model.logits(pred_hidden)
                proposed = torch.argmax(logits, dim=-1)
                target = targets[:, step]
                matches = proposed == target
                active = alive.clone()
                conditional_den[step] += int(active.sum().item())
                exact_hits[step] += int((matches & active).sum().item())
                accepted += (matches & active).to(torch.long)
                alive = alive & matches
                current_hidden = torch.cat([current_hidden, pred_hidden[:, None, :]],
                                           dim=1)
                current_ids = torch.cat([current_ids, target[:, None]], dim=1)
                current_positions = torch.cat(
                    [current_positions, target_positions[:, step:step + 1]],
                    dim=1,
                )
            for value in accepted.detach().cpu().tolist():
                hist[int(value)] += 1
                accepted_total += int(value)
                starts += 1
    return {
        "starts": starts,
        "mean_accepted_draft_tokens": accepted_total / starts if starts else 0.0,
        "mean_visible_tokens_if_k_step_spec": 1.0 + (
            accepted_total / starts if starts else 0.0
        ),
        "histogram_accepted_draft_tokens": {
            str(i): hist[i] for i in range(len(hist)) if hist[i]
        },
        "conditional_exact": [
            exact_hits[i] / conditional_den[i] if conditional_den[i] else 0.0
            for i in range(max_steps)
        ],
        "conditional_denominators": conditional_den,
    }


def save_candidate(out_dir: Path, model: Any, base_tensors: dict[str, torch.Tensor],
                   args: argparse.Namespace, before: dict[str, Any],
                   after: dict[str, Any], elapsed_s: float) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    trainable_names = list(getattr(model, "_diagnostic_trainable_names", []))
    trainable_param_count = int(
        getattr(model, "_diagnostic_trainable_param_count", 0))
    position_fc_count = int(getattr(model, "position_fc_count", 0))
    position_fc_keys = [
        f"mtp.position_fcs.{index}.weight"
        for index in range(position_fc_count)
    ]
    position_fc_trainable_count = int(
        getattr(model, "_position_fc_trainable_count", 0))
    position_fc_trainable_param_count = int(
        getattr(model, "_position_fc_trainable_param_count", 0))
    position_fc_frozen_indices = list(
        getattr(model, "_position_fc_frozen_indices", ()))
    position_fc_trainable_indices = list(
        getattr(model, "_position_fc_trainable_indices", ()))
    position_fc_total_param_count = sum(
        model.position_fcs[index].numel()
        for index in range(position_fc_count)
    )
    position_adapter_count = int(getattr(model, "position_adapter_count", 0))
    position_adapter_rank = int(getattr(model, "position_adapter_rank", 0))
    position_adapter_keys = [
        key
        for index in range(position_adapter_count)
        for key in (
            f"mtp.position_adapters.{index}.down.weight",
            f"mtp.position_adapters.{index}.up.weight",
        )
    ]
    position_adapter_trainable_count = int(
        getattr(model, "_position_adapter_trainable_count", 0))
    position_adapter_trainable_tensor_count = int(
        getattr(model, "_position_adapter_trainable_tensor_count", 0))
    position_adapter_trainable_param_count = int(
        getattr(model, "_position_adapter_trainable_param_count", 0))
    position_adapter_total_param_count = sum(
        model.position_adapter_down[index].numel()
        + model.position_adapter_up[index].numel()
        for index in range(position_adapter_count)
    )

    diagnostic_names = list(trainable_names)
    if position_fc_count:
        diagnostic_names = [
            position_fc_name(index) for index in range(position_fc_count)
        ] + [
            name for name in trainable_names if position_fc_index(name) is None
        ]
    dense_updates = {
        f"dense.{name}": model_tensor(model, name).detach().cpu().to(torch.bfloat16)
        for name in diagnostic_names
    }
    dense_update_path = ""
    if dense_updates:
        dense_update_path = "diagnostic_dense_updates.safetensors"
        save_file(dense_updates, str(out_dir / dense_update_path))

    endpoint_candidate_compatible = all(
        name in MERGEABLE_MODEL_EXTRA_ATTRS
        or position_fc_index(name) is not None
        or position_adapter_parts(name) is not None
        for name in trainable_names
    )
    model_extra_export = ""
    model_extra_metadata: dict[str, str] = {}
    if endpoint_candidate_compatible:
        model_extra_export = "model_extra_tensors.safetensors"
        tensors = {k: v.detach().cpu() for k, v in base_tensors.items()}
        tensors["mtp.fc.weight"] = model.fc.detach().cpu().to(torch.bfloat16)
        if position_fc_count:
            tensors = {
                key: value for key, value in tensors.items()
                if EVAL.POSITION_FC_KEY_RE.fullmatch(key) is None
            }
        for index, key in enumerate(position_fc_keys):
            tensors[key] = model.position_fcs[index].detach().cpu().to(
                torch.bfloat16
            )
        if position_adapter_count:
            tensors = {
                key: value for key, value in tensors.items()
                if EVAL.POSITION_ADAPTER_KEY_RE.fullmatch(key) is None
            }
        for index in range(position_adapter_count):
            tensors[f"mtp.position_adapters.{index}.down.weight"] = (
                model.position_adapter_down[index].detach().cpu().to(
                    torch.bfloat16
                )
            )
            tensors[f"mtp.position_adapters.{index}.up.weight"] = (
                model.position_adapter_up[index].detach().cpu().to(torch.bfloat16)
            )
        for name, key in [
            ("pre_fc_norm_embedding", "mtp.pre_fc_norm_embedding.weight"),
            ("pre_fc_norm_hidden", "mtp.pre_fc_norm_hidden.weight"),
            ("input_layernorm", "mtp.layers.0.input_layernorm.weight"),
            ("post_attention_layernorm",
             "mtp.layers.0.post_attention_layernorm.weight"),
            ("q_norm", "mtp.layers.0.self_attn.q_norm.weight"),
            ("k_norm", "mtp.layers.0.self_attn.k_norm.weight"),
            ("final_norm", "mtp.norm.weight"),
        ]:
            value = getattr(model, name)
            if isinstance(value, torch.nn.Parameter):
                tensors[key] = value.detach().cpu().to(torch.bfloat16)
        if position_adapter_count:
            model_extra_metadata = {
                "xpu_mtp_position_adapter_count": str(position_adapter_count),
                "xpu_mtp_position_adapter_rank": str(position_adapter_rank),
                "xpu_mtp_position_adapter_step_indexing": (
                    "zero_based_spec_step_idx_post_final_norm_residual"
                ),
            }
            save_file(
                tensors,
                str(out_dir / model_extra_export),
                metadata=model_extra_metadata,
            )
        else:
            save_file(tensors, str(out_dir / model_extra_export))
    summary = {
        "purpose": "diagnostic_intrinsic_mtp_mergeable_adapter_training",
        "valid_headline_throughput": False,
        "headline_warning": (
            "Offline draft acceptance only; endpoint strict fresh validation is "
            "required before any throughput claim or LocalMaxxing submission."
        ),
        "model_dir": args.model_dir,
        "dataset_dirs": args.dataset_dir,
        "scope": args.scope,
        "draft_lm_head": args.draft_lm_head,
        "draft_lm_head_group_size": args.draft_lm_head_group_size,
        "draft_lm_head_scale_dtype": args.draft_lm_head_scale_dtype,
        "loss_mode": getattr(args, "loss_mode", "all-steps"),
        "max_steps": args.max_steps,
        "trainable_names": trainable_names,
        "trainable_param_count": trainable_param_count,
        "diagnostic_dense_update_names": diagnostic_names,
        "position_fc_count": position_fc_count,
        "position_fc_keys": position_fc_keys,
        "position_fc_frozen_indices": position_fc_frozen_indices,
        "position_fc_trainable_indices": position_fc_trainable_indices,
        "position_fc_trainable_count": position_fc_trainable_count,
        "position_fc_trainable_param_count": position_fc_trainable_param_count,
        "position_fc_total_param_count": position_fc_total_param_count,
        "position_fc_initialization": getattr(
            model, "_position_fc_initialization", ""
        ),
        "position_fc_step_indexing": (
            "zero_based_spec_step_idx" if position_fc_count else ""
        ),
        "position_adapter_count": position_adapter_count,
        "position_adapter_rank": position_adapter_rank,
        "position_adapter_keys": position_adapter_keys,
        "position_adapter_trainable_count": position_adapter_trainable_count,
        "position_adapter_trainable_tensor_count": (
            position_adapter_trainable_tensor_count
        ),
        "position_adapter_trainable_param_count": (
            position_adapter_trainable_param_count
        ),
        "position_adapter_total_param_count": position_adapter_total_param_count,
        "position_adapter_initialization": getattr(
            model, "_position_adapter_initialization", ""
        ),
        "position_adapter_seed": getattr(model, "_position_adapter_seed", None),
        "position_adapter_step_indexing": (
            "zero_based_spec_step_idx_post_final_norm_residual"
            if position_adapter_count else ""
        ),
        "model_extra_metadata": model_extra_metadata,
        "skipped_no_trainable_prefix_batches": int(
            getattr(model, "_skipped_no_trainable_prefix_batches", 0)
        ),
        "endpoint_candidate_compatible": endpoint_candidate_compatible,
        "diagnostic_dense_update_path": dense_update_path,
        "train_starts": args.train_starts,
        "heldout_starts": args.heldout_starts,
        "heldout_samples": args.heldout_samples,
        "batch_size": args.batch_size,
        "epochs": args.epochs,
        "lr": args.lr,
        "weight_decay": args.weight_decay,
        "seed": args.seed,
        "before": before,
        "after": after,
        "elapsed_s": elapsed_s,
        "export": model_extra_export or dense_update_path,
        "model_extra_export": model_extra_export,
    }
    (out_dir / "training_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    args.dataset_dir = [d for d in args.dataset_dir if d]
    if not args.dataset_dir:
        args.dataset_dir = [EVAL.DEFAULT_DATASET_DIR]
    if args.max_steps < 1:
        raise ValueError("--max-steps must be >= 1")
    if (args.scope == POSITION_ADAPTER_SCOPE
            and args.position_adapter_rank < 1):
        raise ValueError("--position-adapter-rank must be >= 1")
    if args.freeze_position_fcs and args.scope not in POSITION_FC_SCOPES:
        raise ValueError("--freeze-position-fcs requires a position-fc scope")
    invalid_frozen_indices = [
        index for index in args.freeze_position_fcs
        if index >= args.max_steps
    ]
    if invalid_frozen_indices:
        raise ValueError(
            "--freeze-position-fcs indices must be less than --max-steps; "
            f"got {invalid_frozen_indices} with max_steps={args.max_steps}"
        )
    if (args.scope == "position-fc"
            and len(args.freeze_position_fcs) == args.max_steps):
        raise ValueError("position-fc scope must leave at least one FC trainable")
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = EVAL.choose_device(args.device)
    dtype = EVAL.dtype_from_name(args.dtype)
    paths = EVAL.iter_sample_paths(args.dataset_dir, 0)
    samples = load_samples(paths)
    if args.heldout_samples <= 0 or args.heldout_samples >= len(samples):
        raise ValueError("--heldout-samples must leave at least one train sample")
    train_samples = samples[:-args.heldout_samples]
    heldout_samples = samples[-args.heldout_samples:]
    train_refs = collect_starts(train_samples, args.max_steps, args.train_starts)
    heldout_refs = collect_starts(heldout_samples, args.max_steps,
                                  args.heldout_starts)
    random.shuffle(train_refs)

    config = EVAL.load_config(args.model_dir)
    shape = EVAL.shape_from_config(config)
    base_tensors = load_file(os.path.join(args.model_dir,
                                          "model_extra_tensors.safetensors"),
                             device="cpu")
    embed = EVAL.load_indexed_tensor(args.model_dir,
                                     "model.language_model.embed_tokens.weight")
    lm_head = EVAL.load_indexed_tensor(args.model_dir, "lm_head.weight")
    model = EVAL.IntrinsicMTP(
        shape=shape,
        tensors=base_tensors,
        embed_weight=embed,
        lm_head_weight=lm_head,
        device=device,
        dtype=dtype,
        use_official_rope=False,
        draft_lm_head=args.draft_lm_head,
        draft_lm_head_group_size=args.draft_lm_head_group_size,
        draft_lm_head_scale_dtype=args.draft_lm_head_scale_dtype,
    ).eval()
    params = make_trainable(
        model,
        args.scope,
        args.max_steps,
        args.freeze_position_fcs,
        position_adapter_rank=args.position_adapter_rank,
        position_adapter_seed=args.seed,
    )
    if not params:
        raise ValueError("scope and freeze settings leave no trainable parameters")
    for param in params:
        param.requires_grad_(True)
    optimizer = torch.optim.AdamW(params, lr=args.lr,
                                  weight_decay=args.weight_decay)

    before = evaluate_batched(model, heldout_samples, heldout_refs, device, dtype,
                              args.max_steps, max(1, args.batch_size))
    print(f"[intrinsic-mtp-train] before heldout={before}", flush=True)
    started = time.perf_counter()
    step = 0
    skipped_no_trainable_prefix_batches = 0
    for epoch in range(args.epochs):
        random.shuffle(train_refs)
        for offset in range(0, len(train_refs), args.batch_size):
            batch_refs = train_refs[offset:offset + args.batch_size]
            if len(batch_refs) < 1:
                continue
            batch = build_batch(train_samples, batch_refs, device, dtype,
                                args.max_steps)
            optimizer.zero_grad(set_to_none=True)
            loss, accs = rollout_loss(
                model, batch, args.max_steps, args.loss_mode
            )
            if not loss.requires_grad:
                skipped_no_trainable_prefix_batches += 1
                continue
            loss.backward()
            if args.grad_clip > 0:
                torch.nn.utils.clip_grad_norm_(params, args.grad_clip)
            optimizer.step()
            step += 1
            if args.print_every > 0 and step % args.print_every == 0:
                print(
                    f"[intrinsic-mtp-train] epoch={epoch + 1}/{args.epochs} "
                    f"step={step} loss={float(loss.item()):.4f} "
                    f"teacher_acc={[round(a, 4) for a in accs]}",
                    flush=True,
                )
            if args.eval_every > 0 and step % args.eval_every == 0:
                mid = evaluate_batched(model, heldout_samples, heldout_refs, device,
                                       dtype, args.max_steps,
                                       max(1, args.batch_size))
                print(f"[intrinsic-mtp-train] mid heldout={mid}", flush=True)

    model._skipped_no_trainable_prefix_batches = (
        skipped_no_trainable_prefix_batches
    )
    after = evaluate_batched(model, heldout_samples, heldout_refs, device, dtype,
                             args.max_steps, max(1, args.batch_size))
    print(f"[intrinsic-mtp-train] after heldout={after}", flush=True)
    save_candidate(Path(args.out_dir), model, base_tensors, args, before, after,
                   time.perf_counter() - started)
    print(f"wrote {args.out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
