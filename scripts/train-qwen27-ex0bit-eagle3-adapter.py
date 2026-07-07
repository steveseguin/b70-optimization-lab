#!/usr/bin/env python3
"""Fine-tune Ex0bit EAGLE3/DFlash weights on Qwen27 aux-hidden samples.

This is a bounded diagnostic trainer for target-matching a stronger drafter. It
does not produce a benchmark claim by itself; exported checkpoints must pass the
offline acceptance evaluator before endpoint work is justified.

Initial intended lane:

  --train-scope lm-head

which freezes the Ex0bit EAGLE3 body and adapts only the compressed draft LM
head over target-owned qwen36_eagle_sequence_v2 samples.

Use ``--rollout-steps > 1`` to train the autoregressive failure mode directly:
step 1 starts from target aux hidden states, then later steps feed the draft's
own predicted hidden states plus teacher token IDs. This is still diagnostic;
the exported checkpoint must pass the offline rollout evaluator before endpoint
work is justified.
"""

from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import shutil
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
from safetensors.torch import save_file
from torch.utils.data import DataLoader, TensorDataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", required=True, action="append")
    parser.add_argument("--heldout-dir", action="append", default=[])
    parser.add_argument("--draft-dir", required=True)
    parser.add_argument("--target-model", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--max-train-rows", type=int, default=0)
    parser.add_argument("--max-heldout-rows", type=int, default=4096)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--dtype", default="bfloat16",
                        choices=("float32", "bfloat16", "float16"))
    parser.add_argument(
        "--aux-count",
        type=int,
        default=0,
        help=(
            "Expected aux hidden-state count. 0 infers it from the draft "
            "checkpoint. Use 5 with corpora collected from aux layers "
            "1,16,31,46,61."
        ),
    )
    parser.add_argument(
        "--aux-source-target-slots",
        default="",
        help=(
            "Comma-separated target aux slots used when expanding a smaller "
            "source fc.weight into --aux-count. Default maps source 3 slots "
            "to [0, mid, last]."
        ),
    )
    parser.add_argument(
        "--train-scope",
        default="lm-head",
        choices=("lm-head", "fc-lm-head", "all"),
    )
    parser.add_argument("--eval-every", type=int, default=100)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--rollout-steps",
        type=int,
        default=1,
        help=(
            "Train N autoregressive draft steps. 1 preserves the original "
            "teacher-forced row objective; >1 trains later steps using prior "
            "predicted hidden states and teacher token IDs."
        ),
    )
    parser.add_argument(
        "--rollout-loss-decay",
        type=float,
        default=1.0,
        help=(
            "Multiplicative weight decay per rollout step. 1.0 weights every "
            "step equally; 0.5 halves the loss weight each later step."
        ),
    )
    parser.add_argument(
        "--rollout-survival-mode",
        default="none",
        choices=("none", "hard"),
        help=(
            "When hard, compute primary rollout loss only for prefixes that "
            "would still be alive under greedy accepted-prefix evaluation."
        ),
    )
    parser.add_argument(
        "--rollout-dead-loss-floor",
        type=float,
        default=0.0,
        help=(
            "Optional CE weight multiplier for covered rows after their prefix "
            "has died under --rollout-survival-mode=hard. 0 trains only live "
            "prefixes; small values preserve some late-step signal."
        ),
    )
    parser.add_argument(
        "--rollout-rank-loss-weight",
        type=float,
        default=0.0,
        help=(
            "Optional live-prefix argmax-margin loss weight. This penalizes "
            "the strongest non-target logit beating or approaching the target."
        ),
    )
    parser.add_argument(
        "--rollout-rank-margin",
        type=float,
        default=0.0,
        help="Margin used by --rollout-rank-loss-weight.",
    )
    parser.add_argument(
        "--hidden-loss-weight",
        type=float,
        default=0.0,
        help=(
            "Optional target-hidden distillation weight. When >0, train the "
            "draft hidden trajectory to match the next target hidden_state row "
            "in addition to token CE. This is diagnostic and preserves the "
            "exported checkpoint format."
        ),
    )
    parser.add_argument(
        "--hidden-loss-type",
        default="cosine",
        choices=("cosine", "mse"),
        help="Hidden distillation loss used with --hidden-loss-weight.",
    )
    return parser.parse_args()


def load_eval_module() -> Any:
    path = Path(__file__).with_name("evaluate-qwen27-ex0bit-eagle3-offline.py")
    spec = importlib.util.spec_from_file_location("qwen27_eagle3_eval", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load evaluator module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def torch_load(path: str) -> dict[str, Any]:
    try:
        return torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        return torch.load(path, map_location="cpu")


def iter_sample_paths(dataset_dirs: list[str]) -> list[str]:
    paths: list[str] = []
    for dataset_dir in dataset_dirs:
        paths.extend(sorted(glob.glob(os.path.join(dataset_dir, "*.pt"))))
    if not paths:
        raise FileNotFoundError(f"No .pt samples found in {dataset_dirs}")
    return paths


def make_positions(sample: dict[str, Any], length: int) -> torch.Tensor:
    if "positions" in sample:
        positions = sample["positions"][:length].to(torch.long)
        if positions.numel() == length and torch.all(positions >= 0):
            return positions
    return torch.arange(length, dtype=torch.long)


def make_target_to_draft(model: Any) -> torch.Tensor:
    mapping = torch.full(
        (model.shape.vocab_size,),
        -100,
        dtype=torch.long,
    )
    if model.draft_id_to_target_id is None:
        upper = min(model.shape.vocab_size, model.shape.draft_vocab_size)
        mapping[:upper] = torch.arange(upper, dtype=torch.long)
        return mapping
    d2t = model.draft_id_to_target_id.detach().to("cpu", dtype=torch.long)
    targets = torch.arange(d2t.numel(), dtype=torch.long) + d2t
    valid = (targets >= 0) & (targets < model.shape.vocab_size)
    draft_ids = torch.arange(d2t.numel(), dtype=torch.long)[valid]
    mapping[targets[valid]] = draft_ids
    return mapping


def load_rows(
    *,
    dataset_dirs: list[str],
    target_to_draft: torch.Tensor,
    max_rows: int,
    include_target_hidden: bool = False,
    expected_aux_count: int = 0,
    hidden_size: int = 0,
) -> tuple[TensorDataset, dict[str, Any]]:
    aux_rows: list[torch.Tensor] = []
    input_ids: list[torch.Tensor] = []
    positions: list[torch.Tensor] = []
    labels: list[torch.Tensor] = []
    target_hidden_rows: list[torch.Tensor] = []
    samples = 0
    rows = 0
    covered = 0
    hidden_rows = 0
    skipped_samples = 0
    for path in iter_sample_paths(dataset_dirs):
        sample = torch_load(path)
        if sample.get("format") != "qwen36_eagle_sequence_v2":
            skipped_samples += 1
            continue
        if "aux_hidden_states" not in sample or "sampled_next_token_ids" not in sample:
            skipped_samples += 1
            continue
        aux = sample["aux_hidden_states"]
        if expected_aux_count > 0 and aux.shape[1:] != (
            expected_aux_count,
            hidden_size,
        ):
            skipped_samples += 1
            continue
        next_ids = sample["sampled_next_token_ids"].to(torch.long)
        length = min(aux.shape[0], next_ids.shape[0])
        if length < 2:
            skipped_samples += 1
            continue
        if include_target_hidden and "hidden_state" not in sample:
            skipped_samples += 1
            continue
        pos = make_positions(sample, length)
        row_aux = aux[: length - 1].contiguous()
        row_inputs = next_ids[: length - 1].contiguous()
        row_positions = pos[: length - 1].contiguous()
        row_labels = target_to_draft[next_ids[1:length]].contiguous()
        row_target_hidden = None
        if include_target_hidden:
            hidden = sample["hidden_state"]
            row_target_hidden = hidden[1:length].contiguous()
        if max_rows and rows + int(row_labels.numel()) > max_rows:
            keep = max(0, max_rows - rows)
            row_aux = row_aux[:keep]
            row_inputs = row_inputs[:keep]
            row_positions = row_positions[:keep]
            row_labels = row_labels[:keep]
            if row_target_hidden is not None:
                row_target_hidden = row_target_hidden[:keep]
        if row_labels.numel() == 0:
            break
        aux_rows.append(row_aux)
        input_ids.append(row_inputs)
        positions.append(row_positions)
        labels.append(row_labels)
        if row_target_hidden is not None:
            target_hidden_rows.append(row_target_hidden)
            hidden_rows += int(row_target_hidden.shape[0])
        samples += 1
        rows += int(row_labels.numel())
        covered += int((row_labels != -100).sum().item())
        if max_rows and rows >= max_rows:
            break
    if rows == 0:
        raise RuntimeError("No trainable rows loaded")
    tensors = [
        torch.cat(aux_rows, dim=0),
        torch.cat(input_ids, dim=0),
        torch.cat(positions, dim=0),
        torch.cat(labels, dim=0),
    ]
    if include_target_hidden:
        if hidden_rows != rows:
            raise RuntimeError(
                f"Loaded {hidden_rows} target-hidden rows for {rows} labels")
        tensors.append(torch.cat(target_hidden_rows, dim=0))
    dataset = TensorDataset(*tensors)
    summary = {
        "dataset_dirs": dataset_dirs,
        "samples": samples,
        "rows": rows,
        "covered_rows": covered,
        "coverage": covered / rows if rows else 0.0,
        "include_target_hidden": include_target_hidden,
        "target_hidden_rows": hidden_rows,
        "skipped_samples": skipped_samples,
    }
    return dataset, summary


def load_windows(
    *,
    dataset_dirs: list[str],
    target_to_draft: torch.Tensor,
    rollout_steps: int,
    max_rows: int,
    include_target_hidden: bool = False,
    expected_aux_count: int = 0,
    hidden_size: int = 0,
) -> tuple[TensorDataset, dict[str, Any]]:
    aux_rows: list[torch.Tensor] = []
    input_windows: list[torch.Tensor] = []
    position_windows: list[torch.Tensor] = []
    label_windows: list[torch.Tensor] = []
    target_hidden_windows: list[torch.Tensor] = []
    samples = 0
    windows = 0
    rows = 0
    covered = 0
    hidden_rows = 0
    skipped_samples = 0
    for path in iter_sample_paths(dataset_dirs):
        sample = torch_load(path)
        if sample.get("format") != "qwen36_eagle_sequence_v2":
            skipped_samples += 1
            continue
        if "aux_hidden_states" not in sample or "sampled_next_token_ids" not in sample:
            skipped_samples += 1
            continue
        aux = sample["aux_hidden_states"]
        if expected_aux_count > 0 and aux.shape[1:] != (
            expected_aux_count,
            hidden_size,
        ):
            skipped_samples += 1
            continue
        next_ids = sample["sampled_next_token_ids"].to(torch.long)
        length = min(aux.shape[0], next_ids.shape[0])
        if length <= rollout_steps:
            skipped_samples += 1
            continue
        if include_target_hidden and "hidden_state" not in sample:
            skipped_samples += 1
            continue
        pos = make_positions(sample, length)
        available_starts = length - rollout_steps
        if max_rows:
            remaining_windows = max(0, (max_rows - rows) // rollout_steps)
            available_starts = min(available_starts, remaining_windows)
        if available_starts <= 0:
            break
        starts = torch.arange(available_starts, dtype=torch.long)
        offsets = torch.arange(rollout_steps + 1, dtype=torch.long)
        label_offsets = torch.arange(1, rollout_steps + 1, dtype=torch.long)
        input_idx = starts[:, None] + offsets[None, :]
        label_idx = starts[:, None] + label_offsets[None, :]
        row_aux = aux[starts].contiguous()
        row_inputs = next_ids[input_idx].contiguous()
        row_positions = pos[input_idx].contiguous()
        row_labels = target_to_draft[next_ids[label_idx]].contiguous()
        row_target_hidden = None
        if include_target_hidden:
            row_target_hidden = sample["hidden_state"][label_idx].contiguous()
        aux_rows.append(row_aux)
        input_windows.append(row_inputs)
        position_windows.append(row_positions)
        label_windows.append(row_labels)
        if row_target_hidden is not None:
            target_hidden_windows.append(row_target_hidden)
            hidden_rows += int(row_target_hidden.numel() // row_target_hidden.shape[-1])
        samples += 1
        windows += int(row_labels.shape[0])
        row_count = int(row_labels.numel())
        rows += row_count
        covered += int((row_labels != -100).sum().item())
        if max_rows and rows >= max_rows:
            break
    if rows == 0:
        raise RuntimeError("No rollout windows loaded")
    tensors = [
        torch.cat(aux_rows, dim=0),
        torch.cat(input_windows, dim=0),
        torch.cat(position_windows, dim=0),
        torch.cat(label_windows, dim=0),
    ]
    if include_target_hidden:
        if hidden_rows != rows:
            raise RuntimeError(
                f"Loaded {hidden_rows} target-hidden rows for {rows} labels")
        tensors.append(torch.cat(target_hidden_windows, dim=0))
    dataset = TensorDataset(*tensors)
    summary = {
        "dataset_dirs": dataset_dirs,
        "samples": samples,
        "windows": windows,
        "rows": rows,
        "covered_rows": covered,
        "coverage": covered / rows if rows else 0.0,
        "rollout_steps": rollout_steps,
        "include_target_hidden": include_target_hidden,
        "target_hidden_rows": hidden_rows,
        "skipped_samples": skipped_samples,
    }
    return dataset, summary


def hidden_distill_loss(
    pred: torch.Tensor,
    target_hidden: torch.Tensor,
    *,
    loss_type: str,
) -> torch.Tensor:
    pred_float = pred.to(torch.float32)
    target_float = target_hidden.to(device=pred.device, dtype=torch.float32)
    if loss_type == "cosine":
        return (1.0 - F.cosine_similarity(pred_float, target_float, dim=-1)).mean()
    if loss_type == "mse":
        return F.mse_loss(pred_float, target_float)
    raise ValueError(loss_type)


def configure_train_scope(model: Any, scope: str) -> list[torch.nn.Parameter]:
    model.requires_grad_(False)
    if scope == "lm-head":
        model.lm_head.requires_grad_(True)
    elif scope == "fc-lm-head":
        model.fc.requires_grad_(True)
        model.lm_head.requires_grad_(True)
    elif scope == "all":
        model.requires_grad_(True)
        if hasattr(model, "embed_weight"):
            model.embed_weight.requires_grad_(False)
    else:
        raise ValueError(scope)
    params = [p for p in model.parameters() if p.requires_grad]
    if not params:
        raise RuntimeError("No trainable parameters")
    return params


def evaluate_teacher_forced(
    *,
    model: Any,
    loader: DataLoader,
    device: torch.device,
    dtype: torch.dtype,
    max_batches: int = 0,
) -> dict[str, float | int]:
    model.eval()
    rows = 0
    covered = 0
    exact = 0
    loss_total = 0.0
    with torch.no_grad():
        for batch_idx, batch in enumerate(loader):
            if max_batches and batch_idx >= max_batches:
                break
            aux, input_ids, positions, labels = batch[:4]
            aux = aux.to(device=device, dtype=dtype).reshape(aux.shape[0], 1, -1)
            input_ids = input_ids.to(device=device).view(-1, 1)
            positions = positions.to(device=device).view(-1, 1)
            labels = labels.to(device=device)
            mask = labels != -100
            if not torch.any(mask):
                rows += int(labels.numel())
                continue
            hidden = model.combine_hidden_states(aux)
            pred = model(input_ids, positions, hidden)[:, -1, :]
            logits = model.lm_head(pred).float() * float(model.shape.logit_scale)
            loss = F.cross_entropy(logits[mask], labels[mask])
            proposed = torch.argmax(logits, dim=-1)
            exact += int((proposed[mask] == labels[mask]).sum().item())
            covered += int(mask.sum().item())
            rows += int(labels.numel())
            loss_total += float(loss.item()) * int(mask.sum().item())
    model.train()
    return {
        "rows": rows,
        "covered_rows": covered,
        "loss": loss_total / covered if covered else 0.0,
        "exact": exact,
        "exact_rate": exact / covered if covered else 0.0,
    }


def compute_rollout_loss(
    *,
    model: Any,
    aux: torch.Tensor,
    input_windows: torch.Tensor,
    position_windows: torch.Tensor,
    labels: torch.Tensor,
    target_hidden_windows: torch.Tensor | None,
    device: torch.device,
    dtype: torch.dtype,
    loss_decay: float,
    survival_mode: str,
    dead_loss_floor: float,
    rank_loss_weight: float,
    rank_margin: float,
    hidden_loss_weight: float,
    hidden_loss_type: str,
) -> tuple[torch.Tensor, dict[str, Any]]:
    batch = int(labels.shape[0])
    steps = int(labels.shape[1])
    aux = aux.to(device=device, dtype=dtype).reshape(batch, 1, -1)
    input_windows = input_windows.to(device=device)
    position_windows = position_windows.to(device=device)
    labels = labels.to(device=device)
    if target_hidden_windows is not None:
        target_hidden_windows = target_hidden_windows.to(device=device, dtype=dtype)
    current_hidden = model.combine_hidden_states(aux)
    current_ids = input_windows[:, :1]
    current_positions = position_windows[:, :1]
    loss_terms: list[torch.Tensor] = []
    loss_weight_total = 0.0
    alive = torch.ones(batch, dtype=torch.bool, device=device)
    covered_by_step: list[int] = []
    live_by_step: list[int] = []
    dead_by_step: list[int] = []
    exact_by_step: list[int] = []
    loss_by_step: list[float] = []
    rank_loss_by_step: list[float] = []
    hidden_loss_by_step: list[float] = []
    for step in range(steps):
        pred = model(current_ids, current_positions, current_hidden)[:, -1, :]
        logits = model.lm_head(pred).float() * float(model.shape.logit_scale)
        step_labels = labels[:, step]
        covered_mask = step_labels != -100
        if survival_mode == "hard":
            primary_mask = covered_mask & alive
            dead_mask = covered_mask & ~alive
        else:
            primary_mask = covered_mask
            dead_mask = torch.zeros_like(covered_mask)
        covered = int(covered_mask.sum().item())
        live = int(primary_mask.sum().item())
        dead = int(dead_mask.sum().item())
        covered_by_step.append(covered)
        live_by_step.append(live)
        dead_by_step.append(dead)
        exact = 0
        step_loss_value = 0.0
        rank_loss_value = 0.0
        hidden_loss_value = 0.0
        proposed = torch.argmax(logits, dim=-1)
        if live:
            step_loss = F.cross_entropy(
                logits[primary_mask], step_labels[primary_mask])
            weight = loss_decay ** step
            loss_terms.append(step_loss * weight)
            loss_weight_total += weight
            exact = int(
                (proposed[primary_mask] == step_labels[primary_mask])
                .sum()
                .item())
            step_loss_value = float(step_loss.detach().item())
            if rank_loss_weight > 0.0:
                rank_labels = step_labels[primary_mask]
                rank_logits = logits[primary_mask]
                target_logits = rank_logits.gather(
                    1, rank_labels.view(-1, 1)).squeeze(1)
                other_logits = rank_logits.clone()
                other_logits.scatter_(1, rank_labels.view(-1, 1), -float("inf"))
                max_other = other_logits.max(dim=-1).values
                rank_loss = F.softplus(
                    max_other - target_logits + rank_margin).mean()
                rank_weight = weight * rank_loss_weight
                loss_terms.append(rank_loss * rank_weight)
                loss_weight_total += rank_weight
                rank_loss_value = float(rank_loss.detach().item())
            if hidden_loss_weight > 0.0 and target_hidden_windows is not None:
                hidden_loss_mask = primary_mask
                target_hidden = target_hidden_windows[:, step, :]
                h_loss = hidden_distill_loss(
                    pred[hidden_loss_mask],
                    target_hidden[hidden_loss_mask],
                    loss_type=hidden_loss_type,
                )
                hidden_weight = weight * hidden_loss_weight
                loss_terms.append(h_loss * hidden_weight)
                loss_weight_total += hidden_weight
                hidden_loss_value = float(h_loss.detach().item())
        if dead and dead_loss_floor > 0.0:
            dead_loss = F.cross_entropy(logits[dead_mask], step_labels[dead_mask])
            dead_weight = (loss_decay ** step) * dead_loss_floor
            loss_terms.append(dead_loss * dead_weight)
            loss_weight_total += dead_weight
        exact_by_step.append(exact)
        loss_by_step.append(step_loss_value)
        rank_loss_by_step.append(rank_loss_value)
        hidden_loss_by_step.append(hidden_loss_value)
        if survival_mode == "hard":
            alive = alive & covered_mask & (proposed == step_labels)
        if step + 1 < input_windows.shape[1]:
            current_hidden = torch.cat(
                [current_hidden, pred.reshape(batch, 1, -1)],
                dim=1,
            )
            current_ids = torch.cat(
                [current_ids, input_windows[:, step + 1:step + 2]],
                dim=1,
            )
            current_positions = torch.cat(
                [current_positions, position_windows[:, step + 1:step + 2]],
                dim=1,
            )
    if not loss_terms:
        raise RuntimeError("Rollout batch has no covered labels")
    loss = torch.stack(loss_terms).sum() / max(loss_weight_total, 1e-12)
    stats = {
        "covered_by_step": covered_by_step,
        "live_by_step": live_by_step,
        "dead_by_step": dead_by_step,
        "exact_by_step": exact_by_step,
        "loss_by_step": loss_by_step,
        "rank_loss_by_step": rank_loss_by_step,
        "hidden_loss_by_step": hidden_loss_by_step,
        "exact_rate_by_step": [
            (exact_by_step[i] / live_by_step[i])
            if live_by_step[i] else 0.0
            for i in range(steps)
        ],
        "survival_mode": survival_mode,
        "dead_loss_floor": dead_loss_floor,
        "rank_loss_weight": rank_loss_weight,
        "rank_margin": rank_margin,
        "hidden_loss_weight": hidden_loss_weight,
        "hidden_loss_type": hidden_loss_type,
    }
    return loss, stats


def export_model(model: Any, out_dir: str, source_draft_dir: str,
                 meta: dict[str, Any]) -> None:
    os.makedirs(out_dir, exist_ok=True)
    state: dict[str, torch.Tensor] = {
        "fc.weight": model.fc.weight.detach().cpu().to(torch.bfloat16),
        "norm.weight": model.norm.weight.detach().cpu().to(torch.bfloat16),
        "lm_head.weight": model.lm_head.weight.detach().cpu().to(torch.bfloat16),
    }
    if model.draft_id_to_target_id is not None:
        state["d2t"] = model.draft_id_to_target_id.detach().cpu().to(torch.long)
    for i, layer in enumerate(model.layers):
        prefix = f"layers.{i}"
        state[f"{prefix}.hidden_norm.weight"] = (
            layer.hidden_norm.weight.detach().cpu().to(torch.bfloat16))
        state[f"{prefix}.input_layernorm.weight"] = (
            layer.input_layernorm.weight.detach().cpu().to(torch.bfloat16))
        state[f"{prefix}.self_attn.q_proj.weight"] = (
            layer.q_proj.weight.detach().cpu().to(torch.bfloat16))
        state[f"{prefix}.self_attn.k_proj.weight"] = (
            layer.k_proj.weight.detach().cpu().to(torch.bfloat16))
        state[f"{prefix}.self_attn.v_proj.weight"] = (
            layer.v_proj.weight.detach().cpu().to(torch.bfloat16))
        state[f"{prefix}.self_attn.o_proj.weight"] = (
            layer.o_proj.weight.detach().cpu().to(torch.bfloat16))
        state[f"{prefix}.post_attention_layernorm.weight"] = (
            layer.post_attention_layernorm.weight.detach().cpu().to(torch.bfloat16))
        state[f"{prefix}.mlp.gate_proj.weight"] = (
            layer.gate_proj.weight.detach().cpu().to(torch.bfloat16))
        state[f"{prefix}.mlp.up_proj.weight"] = (
            layer.up_proj.weight.detach().cpu().to(torch.bfloat16))
        state[f"{prefix}.mlp.down_proj.weight"] = (
            layer.down_proj.weight.detach().cpu().to(torch.bfloat16))
    model_path = os.path.join(out_dir, "model.safetensors")
    tmp_model_path = f"{model_path}.tmp.{os.getpid()}"
    try:
        save_file(state, tmp_model_path)
        os.replace(tmp_model_path, model_path)
    finally:
        if os.path.exists(tmp_model_path):
            os.unlink(tmp_model_path)
    for name in ("config.json", "generation_config.json", "tokenizer_config.json"):
        src = os.path.join(source_draft_dir, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(out_dir, name))
    with open(os.path.join(out_dir, "training_meta.json"), "w",
              encoding="utf-8") as f:
        json.dump(meta, f, indent=2, sort_keys=True)
        f.write("\n")


def main() -> int:
    args = parse_args()
    if args.epochs < 1:
        raise ValueError("--epochs must be >= 1")
    if args.batch_size < 1:
        raise ValueError("--batch-size must be >= 1")
    if args.rollout_steps < 1:
        raise ValueError("--rollout-steps must be >= 1")
    if args.rollout_loss_decay <= 0.0:
        raise ValueError("--rollout-loss-decay must be > 0")
    if args.rollout_dead_loss_floor < 0.0:
        raise ValueError("--rollout-dead-loss-floor must be >= 0")
    if args.rollout_rank_loss_weight < 0.0:
        raise ValueError("--rollout-rank-loss-weight must be >= 0")
    if args.hidden_loss_weight < 0.0:
        raise ValueError("--hidden-loss-weight must be >= 0")
    torch.manual_seed(args.seed)
    eval_module = load_eval_module()
    device = eval_module.choose_device(args.device)
    dtype = eval_module.dtype_from_name(args.dtype)
    model = eval_module.load_model(
        draft_dir=args.draft_dir,
        target_model=args.target_model,
        device=device,
        dtype=dtype,
        aux_count=args.aux_count,
        aux_source_target_slots=eval_module.parse_optional_int_list(
            args.aux_source_target_slots),
    )
    target_to_draft = make_target_to_draft(model)
    train_rows_dataset, train_summary = load_rows(
        dataset_dirs=args.dataset_dir,
        target_to_draft=target_to_draft,
        max_rows=args.max_train_rows,
        include_target_hidden=args.hidden_loss_weight > 0.0,
        expected_aux_count=model.aux_count,
        hidden_size=model.shape.hidden_size,
    )
    train_dataset = train_rows_dataset
    train_objective = "teacher_forced_rows"
    if args.rollout_steps > 1:
        train_dataset, rollout_train_summary = load_windows(
            dataset_dirs=args.dataset_dir,
            target_to_draft=target_to_draft,
            rollout_steps=args.rollout_steps,
            max_rows=args.max_train_rows,
            include_target_hidden=args.hidden_loss_weight > 0.0,
            expected_aux_count=model.aux_count,
            hidden_size=model.shape.hidden_size,
        )
        train_objective = "autoregressive_rollout_windows"
        train_summary = {
            "row_dataset": train_summary,
            "rollout_dataset": rollout_train_summary,
        }
    heldout_dataset = None
    heldout_summary = None
    if args.heldout_dir:
        heldout_dataset, heldout_summary = load_rows(
            dataset_dirs=args.heldout_dir,
            target_to_draft=target_to_draft,
            max_rows=args.max_heldout_rows,
            include_target_hidden=False,
            expected_aux_count=model.aux_count,
            hidden_size=model.shape.hidden_size,
        )
    generator = torch.Generator()
    generator.manual_seed(args.seed)
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        generator=generator,
    )
    heldout_loader = (
        DataLoader(heldout_dataset, batch_size=args.batch_size, shuffle=False)
        if heldout_dataset is not None else None
    )
    train_eval_loader = DataLoader(
        train_rows_dataset,
        batch_size=args.batch_size,
        shuffle=False,
    )
    trainable_params = configure_train_scope(model, args.train_scope)
    optimizer = torch.optim.AdamW(
        trainable_params,
        lr=args.lr,
        weight_decay=args.weight_decay,
    )
    metrics: list[dict[str, Any]] = []
    start = time.perf_counter()
    step = 0
    model.train()
    for epoch in range(args.epochs):
        for batch in train_loader:
            step += 1
            optimizer.zero_grad(set_to_none=True)
            if args.rollout_steps <= 1:
                if args.hidden_loss_weight > 0.0:
                    aux, input_ids, positions, labels, target_hidden = batch
                    target_hidden = target_hidden.to(device=device, dtype=dtype)
                else:
                    aux, input_ids, positions, labels = batch
                    target_hidden = None
                aux = aux.to(device=device, dtype=dtype).reshape(
                    aux.shape[0], 1, -1)
                input_ids = input_ids.to(device=device).view(-1, 1)
                positions = positions.to(device=device).view(-1, 1)
                labels = labels.to(device=device)
                mask = labels != -100
                if not torch.any(mask):
                    continue
                hidden = model.combine_hidden_states(aux)
                pred = model(input_ids, positions, hidden)[:, -1, :]
                logits = (
                    model.lm_head(pred).float() * float(model.shape.logit_scale))
                loss = F.cross_entropy(logits[mask], labels[mask])
                hidden_loss_value = 0.0
                if args.hidden_loss_weight > 0.0 and target_hidden is not None:
                    h_loss = hidden_distill_loss(
                        pred[mask],
                        target_hidden[mask],
                        loss_type=args.hidden_loss_type,
                    )
                    loss = loss + h_loss * args.hidden_loss_weight
                    hidden_loss_value = float(h_loss.detach().item())
                batch_stats = {
                    "hidden_loss": hidden_loss_value,
                    "hidden_loss_weight": args.hidden_loss_weight,
                    "hidden_loss_type": args.hidden_loss_type,
                }
            else:
                if args.hidden_loss_weight > 0.0:
                    (
                        aux,
                        input_windows,
                        position_windows,
                        labels,
                        target_hidden_windows,
                    ) = batch
                else:
                    aux, input_windows, position_windows, labels = batch
                    target_hidden_windows = None
                loss, batch_stats = compute_rollout_loss(
                    model=model,
                    aux=aux,
                    input_windows=input_windows,
                    position_windows=position_windows,
                    labels=labels,
                    target_hidden_windows=target_hidden_windows,
                    device=device,
                    dtype=dtype,
                    loss_decay=args.rollout_loss_decay,
                    survival_mode=args.rollout_survival_mode,
                    dead_loss_floor=args.rollout_dead_loss_floor,
                    rank_loss_weight=args.rollout_rank_loss_weight,
                    rank_margin=args.rollout_rank_margin,
                    hidden_loss_weight=args.hidden_loss_weight,
                    hidden_loss_type=args.hidden_loss_type,
                )
            loss.backward()
            optimizer.step()
            if args.eval_every and step % args.eval_every == 0:
                train_eval = evaluate_teacher_forced(
                    model=model,
                    loader=train_eval_loader,
                    device=device,
                    dtype=dtype,
                    max_batches=16,
                )
                row: dict[str, Any] = {
                    "step": step,
                    "epoch": epoch,
                    "train_loss_batch": float(loss.item()),
                    "train_objective": train_objective,
                    "train_probe": train_eval,
                    "elapsed_s": time.perf_counter() - start,
                }
                if batch_stats:
                    row["rollout_batch_probe"] = batch_stats
                if heldout_loader is not None:
                    row["heldout_probe"] = evaluate_teacher_forced(
                        model=model,
                        loader=heldout_loader,
                        device=device,
                        dtype=dtype,
                        max_batches=0,
                    )
                metrics.append(row)
                print(json.dumps(row, sort_keys=True), flush=True)
    final_train = evaluate_teacher_forced(
        model=model,
        loader=train_eval_loader,
        device=device,
        dtype=dtype,
        max_batches=0,
    )
    final_heldout = (
        evaluate_teacher_forced(
            model=model,
            loader=heldout_loader,
            device=device,
            dtype=dtype,
            max_batches=0,
        )
        if heldout_loader is not None else None
    )
    meta = {
        "purpose": "diagnostic_qwen27_ex0bit_eagle3_target_adaptation",
        "valid_headline_throughput": False,
        "draft_dir": args.draft_dir,
        "target_model": args.target_model,
        "out_dir": args.out_dir,
        "shape": asdict(model.shape),
        "aux_count": model.aux_count,
        "requested_aux_count": args.aux_count,
        "aux_source_target_slots": args.aux_source_target_slots,
        "train_scope": args.train_scope,
        "train_objective": train_objective,
        "rollout_steps": args.rollout_steps,
        "rollout_loss_decay": args.rollout_loss_decay,
        "rollout_survival_mode": args.rollout_survival_mode,
        "rollout_dead_loss_floor": args.rollout_dead_loss_floor,
        "rollout_rank_loss_weight": args.rollout_rank_loss_weight,
        "rollout_rank_margin": args.rollout_rank_margin,
        "hidden_loss_weight": args.hidden_loss_weight,
        "hidden_loss_type": args.hidden_loss_type,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "weight_decay": args.weight_decay,
        "dtype": args.dtype,
        "device": str(device),
        "train_summary": train_summary,
        "heldout_summary": heldout_summary,
        "final_train": final_train,
        "final_heldout": final_heldout,
        "metrics": metrics,
        "elapsed_s": time.perf_counter() - start,
    }
    export_model(model, args.out_dir, args.draft_dir, meta)
    print(json.dumps(meta, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
