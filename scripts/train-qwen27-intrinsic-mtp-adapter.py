#!/usr/bin/env python3
"""Train mergeable Qwen3.6 27B intrinsic-MTP parameters offline.

This script is an experimental draft-acceptance tool. It trains a small,
mergeable subset of the built-in Qwen MTP module against recorded target
hidden-state sequence shards, then exports an updated
model_extra_tensors.safetensors candidate. It does not change the target model
or produce a throughput claim; endpoint validation is still required.
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


@dataclass(frozen=True)
class StartRef:
    sample_index: int
    start: int


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
        choices=("fc", "fc-norms"),
        help="Mergeable MTP parameter subset to train.",
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


def make_trainable(model: torch.nn.Module, scope: str) -> list[torch.nn.Parameter]:
    names = ["fc"]
    if scope == "fc-norms":
        names.extend([
            "pre_fc_norm_embedding",
            "pre_fc_norm_hidden",
            "input_layernorm",
            "post_attention_layernorm",
            "q_norm",
            "k_norm",
            "final_norm",
        ])

    params: list[torch.nn.Parameter] = []
    for name in names:
        tensor = getattr(model, name)
        param = torch.nn.Parameter(tensor.detach().clone())
        setattr(model, name, param)
        params.append(param)
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


def rollout_loss(model: Any, batch: dict[str, torch.Tensor],
                 max_steps: int) -> tuple[torch.Tensor, list[float]]:
    current_hidden = batch["hidden"]
    current_ids = batch["ids"]
    current_positions = batch["positions"]
    targets = batch["targets"]
    target_positions = batch["target_positions"]
    losses: list[torch.Tensor] = []
    accs: list[float] = []
    for step in range(max_steps):
        pred_seq = model(current_hidden, current_ids, current_positions)
        pred_hidden = pred_seq[:, -1, :]
        logits = model.logits(pred_hidden)
        target = targets[:, step]
        losses.append(F.cross_entropy(logits.float(), target))
        proposed = torch.argmax(logits, dim=-1)
        accs.append(float((proposed == target).float().mean().item()))
        current_hidden = torch.cat([current_hidden, pred_hidden[:, None, :]], dim=1)
        current_ids = torch.cat([current_ids, target[:, None]], dim=1)
        current_positions = torch.cat(
            [current_positions, target_positions[:, step:step + 1]],
            dim=1,
        )
    return torch.stack(losses).mean(), accs


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
                pred_seq = model(current_hidden, current_ids, current_positions)
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
    tensors = {k: v.detach().cpu() for k, v in base_tensors.items()}
    tensors["mtp.fc.weight"] = model.fc.detach().cpu().to(torch.bfloat16)
    for name, key in [
        ("pre_fc_norm_embedding", "mtp.pre_fc_norm_embedding.weight"),
        ("pre_fc_norm_hidden", "mtp.pre_fc_norm_hidden.weight"),
        ("input_layernorm", "mtp.layers.0.input_layernorm.weight"),
        ("post_attention_layernorm", "mtp.layers.0.post_attention_layernorm.weight"),
        ("q_norm", "mtp.layers.0.self_attn.q_norm.weight"),
        ("k_norm", "mtp.layers.0.self_attn.k_norm.weight"),
        ("final_norm", "mtp.norm.weight"),
    ]:
        value = getattr(model, name)
        if isinstance(value, torch.nn.Parameter):
            tensors[key] = value.detach().cpu().to(torch.bfloat16)
    save_file(tensors, str(out_dir / "model_extra_tensors.safetensors"))
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
        "max_steps": args.max_steps,
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
        "export": "model_extra_tensors.safetensors",
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
    params = make_trainable(model, args.scope)
    for param in params:
        param.requires_grad_(True)
    optimizer = torch.optim.AdamW(params, lr=args.lr,
                                  weight_decay=args.weight_decay)

    before = evaluate_batched(model, heldout_samples, heldout_refs, device, dtype,
                              args.max_steps, max(1, args.batch_size))
    print(f"[intrinsic-mtp-train] before heldout={before}", flush=True)
    started = time.perf_counter()
    step = 0
    for epoch in range(args.epochs):
        random.shuffle(train_refs)
        for offset in range(0, len(train_refs), args.batch_size):
            batch_refs = train_refs[offset:offset + args.batch_size]
            if len(batch_refs) < 1:
                continue
            batch = build_batch(train_samples, batch_refs, device, dtype,
                                args.max_steps)
            optimizer.zero_grad(set_to_none=True)
            loss, accs = rollout_loss(model, batch, args.max_steps)
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

    after = evaluate_batched(model, heldout_samples, heldout_refs, device, dtype,
                             args.max_steps, max(1, args.batch_size))
    print(f"[intrinsic-mtp-train] after heldout={after}", flush=True)
    save_candidate(Path(args.out_dir), model, base_tensors, args, before, after,
                   time.perf_counter() - started)
    print(f"wrote {args.out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
