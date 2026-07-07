#!/usr/bin/env python3
"""Train a top-k reranker for Qwen27 Ex0bit EAGLE3 diagnostics.

This is an offline research tool, not an endpoint benchmark. The frozen draft
still produces full logits and a top-k candidate list. The default diagonal
reranker learns a cheap reweighting of candidate LM-head dot products:

    score(c) = alpha * draft_logit(c)
             + dot(pred_hidden * lm_head_weight[c], diag)
             + rank_bias[rank(c)]

The MLP variant replaces the diagonal term with a small MLP over
``pred_hidden * lm_head_weight[c]`` for each candidate.

It can only choose among candidates the draft already placed in top-k. If this
does not improve heldout accepted depth, top-k branch/rerank is not worth
backend work. If it does, the next step is endpoint integration with exact
target verification; this script alone makes no throughput or quality claim.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", required=True, action="append")
    parser.add_argument("--heldout-dir", required=True, action="append")
    parser.add_argument("--draft-dir", required=True)
    parser.add_argument("--target-model", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--topk", type=int, default=8)
    parser.add_argument("--rollout-steps", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-2)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--reranker-type",
                        default="diag",
                        choices=("diag", "mlp"))
    parser.add_argument("--reranker-hidden", type=int, default=128)
    parser.add_argument("--max-train-rows", type=int, default=0)
    parser.add_argument("--max-heldout-starts", type=int, default=0)
    parser.add_argument("--eval-every", type=int, default=250)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--dtype", default="bfloat16",
                        choices=("float32", "bfloat16", "float16"))
    parser.add_argument("--seed", type=int, default=0)
    return parser.parse_args()


def load_module(name: str, filename: str) -> Any:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class DiagTopKReranker(nn.Module):
    def __init__(self, hidden_size: int, topk: int) -> None:
        super().__init__()
        self.diag = nn.Parameter(torch.zeros(hidden_size, dtype=torch.float32))
        self.alpha = nn.Parameter(torch.tensor(1.0, dtype=torch.float32))
        self.rank_bias = nn.Parameter(torch.zeros(topk, dtype=torch.float32))

    def forward(
        self,
        *,
        pred_hidden: torch.Tensor,
        candidate_weights: torch.Tensor,
        candidate_logits: torch.Tensor,
    ) -> torch.Tensor:
        hidden = pred_hidden.to(torch.float32)
        weights = candidate_weights.to(torch.float32)
        logits = candidate_logits.to(torch.float32)
        diag_score = (weights * hidden.unsqueeze(1) * self.diag.view(1, 1, -1)).sum(
            dim=-1)
        return self.alpha * logits + diag_score + self.rank_bias.view(1, -1)


class MlpTopKReranker(nn.Module):
    def __init__(self, hidden_size: int, topk: int, reranker_hidden: int) -> None:
        super().__init__()
        self.alpha = nn.Parameter(torch.tensor(1.0, dtype=torch.float32))
        self.rank_bias = nn.Parameter(torch.zeros(topk, dtype=torch.float32))
        self.net = nn.Sequential(
            nn.Linear(hidden_size, reranker_hidden),
            nn.SiLU(),
            nn.Linear(reranker_hidden, 1),
        )

    def forward(
        self,
        *,
        pred_hidden: torch.Tensor,
        candidate_weights: torch.Tensor,
        candidate_logits: torch.Tensor,
    ) -> torch.Tensor:
        hidden = pred_hidden.to(torch.float32)
        weights = candidate_weights.to(torch.float32)
        logits = candidate_logits.to(torch.float32)
        features = weights * hidden.unsqueeze(1)
        flat = features.reshape(-1, features.shape[-1])
        mlp_score = self.net(flat).reshape(features.shape[0], features.shape[1])
        return self.alpha * logits + mlp_score + self.rank_bias.view(1, -1)


def make_reranker(
    *,
    reranker_type: str,
    hidden_size: int,
    topk: int,
    reranker_hidden: int,
) -> nn.Module:
    if reranker_type == "diag":
        return DiagTopKReranker(hidden_size, topk)
    if reranker_type == "mlp":
        return MlpTopKReranker(hidden_size, topk, reranker_hidden)
    raise ValueError(reranker_type)


def candidate_weights_for(model: Any, candidate_ids: torch.Tensor) -> torch.Tensor:
    return model.lm_head.weight.detach()[candidate_ids]


def train_batch(
    *,
    model: Any,
    reranker: DiagTopKReranker,
    batch: tuple[torch.Tensor, ...],
    device: torch.device,
    dtype: torch.dtype,
    topk: int,
) -> tuple[torch.Tensor | None, dict[str, int | float]]:
    aux, input_windows, position_windows, labels = batch
    batch_size = int(labels.shape[0])
    steps = int(labels.shape[1])
    aux = aux.to(device=device, dtype=dtype).reshape(batch_size, 1, -1)
    input_windows = input_windows.to(device=device)
    position_windows = position_windows.to(device=device)
    labels = labels.to(device=device)
    with torch.no_grad():
        current_hidden = model.combine_hidden_states(aux)
    current_ids = input_windows[:, :1]
    current_positions = position_windows[:, :1]
    losses: list[torch.Tensor] = []
    covered = 0
    trainable = 0
    correct_before = 0
    correct_after = 0
    for step in range(steps):
        with torch.no_grad():
            pred = model(current_ids, current_positions, current_hidden)[:, -1, :]
            logits = model.lm_head(pred).float() * float(model.shape.logit_scale)
            cand_logits, cand_ids = torch.topk(logits, k=topk, dim=-1)
        step_labels = labels[:, step]
        mask = step_labels != -100
        if torch.any(mask):
            covered += int(mask.sum().item())
            hits = cand_ids == step_labels.view(-1, 1)
            train_mask = mask & hits.any(dim=-1)
            if torch.any(train_mask):
                target_pos = hits[train_mask].to(torch.float32).argmax(dim=-1)
                cand_weights = candidate_weights_for(model, cand_ids[train_mask])
                scores = reranker(
                    pred_hidden=pred[train_mask],
                    candidate_weights=cand_weights,
                    candidate_logits=cand_logits[train_mask],
                )
                losses.append(F.cross_entropy(scores, target_pos))
                trainable += int(train_mask.sum().item())
                correct_before += int((cand_ids[train_mask, 0]
                                      == step_labels[train_mask]).sum().item())
                correct_after += int(
                    (scores.argmax(dim=-1) == target_pos).sum().item())
        if step + 1 < input_windows.shape[1]:
            with torch.no_grad():
                current_hidden = torch.cat(
                    [current_hidden, pred.reshape(batch_size, 1, -1)], dim=1)
                current_ids = torch.cat(
                    [current_ids, input_windows[:, step + 1:step + 2]], dim=1)
                current_positions = torch.cat(
                    [
                        current_positions,
                        position_windows[:, step + 1:step + 2],
                    ],
                    dim=1,
                )
    if not losses:
        return None, {
            "covered": covered,
            "trainable": trainable,
            "correct_before": correct_before,
            "correct_after": correct_after,
            "loss": 0.0,
        }
    loss = torch.stack(losses).mean()
    return loss, {
        "covered": covered,
        "trainable": trainable,
        "correct_before": correct_before,
        "correct_after": correct_after,
        "loss": float(loss.detach().item()),
    }


def evaluate_start_reranked(
    *,
    model: Any,
    reranker: DiagTopKReranker,
    aux_hidden: torch.Tensor,
    next_ids: torch.Tensor,
    positions: torch.Tensor,
    start: int,
    max_steps: int,
    topk: int,
    device: torch.device,
    dtype: torch.dtype,
) -> dict[str, Any]:
    aux_row = aux_hidden[start:start + 1].reshape(1, 1, -1)
    with torch.no_grad():
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
        with torch.no_grad():
            pred_seq = model(current_ids, current_positions, current_hidden)
            pred_hidden = pred_seq[:, -1, :]
            logits = model.lm_head(pred_hidden).float() * float(model.shape.logit_scale)
            cand_logits, cand_ids = torch.topk(logits, k=topk, dim=-1)
            cand_weights = candidate_weights_for(model, cand_ids)
            scores = reranker(
                pred_hidden=pred_hidden,
                candidate_weights=cand_weights,
                candidate_logits=cand_logits,
            )
            selected_rank = int(scores.argmax(dim=-1).item())
            selected_draft = cand_ids[0, selected_rank:selected_rank + 1]
            proposed = int(model.target_ids_for_draft_ids(selected_draft)[0].item())
            top1_proposed = int(
                model.target_ids_for_draft_ids(cand_ids[0, :1])[0].item())
        target = int(next_ids[target_index].item())
        top1_match = top1_proposed == target
        topk_hit = bool(
            (model.target_ids_for_draft_ids(cand_ids[0]) == target).any().item())
        matched = proposed == target
        rows.append({
            "step": step + 1,
            "target_index": target_index,
            "proposed": proposed,
            "target": target,
            "selected_rank": selected_rank,
            "match": matched,
            "top1_match": top1_match,
            "topk_hit": topk_hit,
        })
        if not matched:
            break
        accepted += 1
        with torch.no_grad():
            current_hidden = torch.cat(
                [current_hidden, pred_hidden.view(1, 1, -1)], dim=1)
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


def evaluate_reranker(
    *,
    eval_mod: Any,
    model: Any,
    reranker: DiagTopKReranker,
    dataset_dirs: list[str],
    max_steps: int,
    max_starts: int,
    topk: int,
    device: torch.device,
    dtype: torch.dtype,
) -> dict[str, Any]:
    paths = eval_mod.iter_sample_paths(dataset_dirs, 0)
    starts = 0
    accepted_total = 0
    hist = [0 for _ in range(max_steps + 1)]
    conditional_den = [0 for _ in range(max_steps)]
    accept_hits = [0 for _ in range(max_steps)]
    top1_hits = [0 for _ in range(max_steps)]
    topk_hits = [0 for _ in range(max_steps)]
    start_time = time.perf_counter()
    with torch.no_grad():
        for path in paths:
            sample = eval_mod.torch_load(path)
            if sample.get("format") != "qwen36_eagle_sequence_v2":
                continue
            if "aux_hidden_states" not in sample or "sampled_next_token_ids" not in sample:
                continue
            aux_hidden = sample["aux_hidden_states"]
            next_ids = sample["sampled_next_token_ids"].to(torch.long)
            length = min(aux_hidden.shape[0], next_ids.shape[0])
            if length <= max_steps + 1:
                continue
            positions = eval_mod.make_positions(sample, length)
            available_starts = max(0, length - max_steps - 1)
            for start in range(available_starts):
                if max_starts > 0 and starts >= max_starts:
                    break
                result = evaluate_start_reranked(
                    model=model,
                    reranker=reranker,
                    aux_hidden=aux_hidden,
                    next_ids=next_ids,
                    positions=positions,
                    start=start,
                    max_steps=max_steps,
                    topk=topk,
                    device=device,
                    dtype=dtype,
                )
                accepted = int(result["accepted"])
                starts += 1
                accepted_total += accepted
                hist[accepted] += 1
                for row in result["rows"]:
                    idx = int(row["step"]) - 1
                    conditional_den[idx] += 1
                    if row["match"]:
                        accept_hits[idx] += 1
                    if row["top1_match"]:
                        top1_hits[idx] += 1
                    if row["topk_hit"]:
                        topk_hits[idx] += 1
                if max_starts > 0 and starts >= max_starts:
                    break
            if max_starts > 0 and starts >= max_starts:
                break
    elapsed = time.perf_counter() - start_time
    per_step = []
    for i, den in enumerate(conditional_den):
        per_step.append({
            "step": i + 1,
            "conditional_denominator": den,
            "accept_hits": accept_hits[i],
            "accept_rate": accept_hits[i] / den if den else 0.0,
            "top1_hits": top1_hits[i],
            "top1_rate": top1_hits[i] / den if den else 0.0,
            "topk_hits": topk_hits[i],
            "topk_rate": topk_hits[i] / den if den else 0.0,
            "unconditional_accept_rate": accept_hits[i] / starts if starts else 0.0,
        })
    return {
        "valid_headline_throughput": False,
        "purpose": "diagnostic_qwen27_eagle3_topk_reranker",
        "topk": topk,
        "starts": starts,
        "mean_accepted": accepted_total / starts if starts else 0.0,
        "acceptance_histogram": {str(i): hist[i] for i in range(len(hist))},
        "per_step": per_step,
        "elapsed_s": elapsed,
        "starts_per_s": starts / elapsed if elapsed else 0.0,
    }


def main() -> int:
    args = parse_args()
    if args.topk < 2:
        raise ValueError("--topk must be >= 2")
    if args.rollout_steps < 1:
        raise ValueError("--rollout-steps must be >= 1")
    torch.manual_seed(args.seed)

    eval_mod = load_module("qwen27_eagle3_eval", "evaluate-qwen27-ex0bit-eagle3-offline.py")
    train_mod = load_module("qwen27_eagle3_train", "train-qwen27-ex0bit-eagle3-adapter.py")
    device = eval_mod.choose_device(args.device)
    dtype = eval_mod.dtype_from_name(args.dtype)

    model = eval_mod.load_model(
        draft_dir=args.draft_dir,
        target_model=args.target_model,
        device=device,
        dtype=dtype,
    )
    model.eval()
    for param in model.parameters():
        param.requires_grad_(False)

    target_to_draft = train_mod.make_target_to_draft(model)
    train_dataset, train_summary = train_mod.load_windows(
        dataset_dirs=args.dataset_dir,
        target_to_draft=target_to_draft,
        rollout_steps=args.rollout_steps,
        max_rows=args.max_train_rows,
    )
    loader = DataLoader(train_dataset,
                        batch_size=args.batch_size,
                        shuffle=True,
                        drop_last=False)

    reranker = make_reranker(
        reranker_type=args.reranker_type,
        hidden_size=model.shape.hidden_size,
        topk=args.topk,
        reranker_hidden=args.reranker_hidden,
    ).to(device)
    opt = torch.optim.AdamW(reranker.parameters(),
                            lr=args.lr,
                            weight_decay=args.weight_decay)
    metrics: list[dict[str, Any]] = []
    step = 0
    start_time = time.perf_counter()
    for epoch in range(args.epochs):
        for batch in loader:
            step += 1
            opt.zero_grad(set_to_none=True)
            loss, stats = train_batch(
                model=model,
                reranker=reranker,
                batch=batch,
                device=device,
                dtype=dtype,
                topk=args.topk,
            )
            if loss is None:
                continue
            loss.backward()
            opt.step()
            if args.eval_every and step % args.eval_every == 0:
                row = {
                    "elapsed_s": time.perf_counter() - start_time,
                    "epoch": epoch,
                    "step": step,
                    "batch_loss": stats["loss"],
                    "batch_covered": stats["covered"],
                    "batch_trainable": stats["trainable"],
                    "batch_top1_rate": (
                        stats["correct_before"] / stats["trainable"]
                        if stats["trainable"] else 0.0
                    ),
                    "batch_rerank_rate": (
                        stats["correct_after"] / stats["trainable"]
                        if stats["trainable"] else 0.0
                    ),
                    "alpha": float(reranker.alpha.detach().cpu().item()),
                    "reranker_weight_abs_mean": float(
                        torch.cat([
                            p.detach().flatten().to("cpu", dtype=torch.float32).abs()
                            for p in reranker.parameters()
                        ]).mean().item()),
                }
                metrics.append(row)
                print(json.dumps(row, sort_keys=True), flush=True)

    heldout = evaluate_reranker(
        eval_mod=eval_mod,
        model=model,
        reranker=reranker,
        dataset_dirs=args.heldout_dir,
        max_steps=args.rollout_steps,
        max_starts=args.max_heldout_starts,
        topk=args.topk,
        device=device,
        dtype=dtype,
    )
    os.makedirs(args.out_dir, exist_ok=True)
    torch.save(
        {
            "state_dict": {
                key: value.detach().cpu()
                for key, value in reranker.state_dict().items()
            },
            "topk": args.topk,
            "reranker_type": args.reranker_type,
            "reranker_hidden": args.reranker_hidden,
        },
        os.path.join(args.out_dir, "reranker.pt"),
    )
    summary = {
        "valid_headline_throughput": False,
        "classification": "diagnostic_only",
        "script": str(Path(__file__).resolve()),
        "draft_dir": args.draft_dir,
        "target_model": args.target_model,
        "dataset_dir": args.dataset_dir,
        "heldout_dir": args.heldout_dir,
        "topk": args.topk,
        "reranker_type": args.reranker_type,
        "reranker_hidden": args.reranker_hidden,
        "rollout_steps": args.rollout_steps,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "weight_decay": args.weight_decay,
        "device": str(device),
        "dtype": args.dtype,
        "train_summary": train_summary,
        "metrics": metrics,
        "heldout": heldout,
        "final_alpha": float(reranker.alpha.detach().cpu().item()),
        "final_rank_bias": reranker.rank_bias.detach().cpu().tolist(),
        "final_reranker_weight_abs_mean": float(
            torch.cat([
                p.detach().flatten().to("cpu", dtype=torch.float32).abs()
                for p in reranker.parameters()
            ]).mean().item()),
    }
    out_path = os.path.join(args.out_dir, "summary.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps({
        "out": out_path,
        "heldout_mean_accepted": heldout["mean_accepted"],
        "hist": heldout["acceptance_histogram"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
