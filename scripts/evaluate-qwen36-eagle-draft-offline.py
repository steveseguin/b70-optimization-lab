#!/usr/bin/env python3
"""Offline acceptance evaluator for local Qwen 3.6 EAGLE draft checkpoints.

The endpoint EAGLE smoke loop is expensive and currently blocked from TP4 by
XPU health. This script gives a cheap draft-quality gate over hidden-state
dataset shards:

  hidden_state[t] + sampled_next_token_ids[t] -> sampled_next_token_ids[t + 1]

It simulates autoregressive draft rollout and counts consecutive greedy-token
matches against the target stream. It does not claim endpoint speed or quality;
it is a draft iteration tool.
"""

from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import torch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset-dir",
        required=True,
        action="append",
        help="Directory containing qwen36_eagle_sequence_v1 .pt files. May repeat.",
    )
    parser.add_argument("--draft-dir", required=True)
    parser.add_argument("--target-model", required=True)
    parser.add_argument("--trainer-script", default="")
    parser.add_argument("--max-steps", type=int, default=5)
    parser.add_argument("--max-samples", type=int, default=0)
    parser.add_argument("--max-starts", type=int, default=512)
    parser.add_argument("--start-stride", type=int, default=1)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--dtype", default="bfloat16",
                        choices=("float32", "bfloat16", "float16"))
    parser.add_argument("--topk", type=int, default=3)
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


def load_trainer_module(path: str) -> Any:
    if not path:
        path = str(Path(__file__).with_name("train-qwen36-eagle1-draft.py"))
    spec = importlib.util.spec_from_file_location("qwen36_eagle_trainer", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load trainer module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def shape_from_config(module: Any, draft_dir: str) -> Any:
    shape = module.DraftShape()
    config_path = os.path.join(draft_dir, "config.json")
    if not os.path.exists(config_path):
        return shape
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    mapping = {
        "hidden_size": "hidden_size",
        "intermediate_size": "intermediate_size",
        "num_hidden_layers": "num_hidden_layers",
        "num_attention_heads": "num_attention_heads",
        "num_key_value_heads": "num_key_value_heads",
        "head_dim": "head_dim",
        "vocab_size": "vocab_size",
        "max_position_embeddings": "max_position_embeddings",
        "rope_theta": "rope_theta",
        "rms_norm_eps": "rms_norm_eps",
    }
    for config_key, attr in mapping.items():
        if config_key in config:
            setattr(shape, attr, config[config_key])
    return shape


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
    model: Any,
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
        pred_seq = model(current_hidden, current_ids, current_positions)
        pred_hidden = pred_seq[:, -1, :]
        logits = model.logits(pred_hidden)
        proposed = int(torch.argmax(logits, dim=-1).item())
        target = int(next_ids[target_index].item())
        if topk > 1:
            k = min(topk, logits.shape[-1])
            top_indices = torch.topk(logits, k=k, dim=-1).indices[0]
            topk_hit = bool((top_indices == target).any().item())
        else:
            topk_hit = proposed == target
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
        next_position = positions[target_index:target_index + 1].to(device=device)
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
            [current_positions, next_position.view(1, 1)],
            dim=1,
        )
    return {"accepted": accepted, "rows": rows}


def main() -> int:
    args = parse_args()
    if args.max_steps < 1:
        raise ValueError("--max-steps must be >= 1")
    if args.start_stride < 1:
        raise ValueError("--start-stride must be >= 1")
    device = choose_device(args.device)
    dtype = dtype_from_name(args.dtype)
    module = load_trainer_module(args.trainer_script)
    shape = shape_from_config(module, args.draft_dir)

    embed_weight, lm_head_weight = module.load_target_shared_weights(
        args.target_model)
    model = module.Eagle1Draft(
        shape,
        embed_weight.to(device=device, dtype=dtype),
        lm_head_weight.to(device=device, dtype=dtype),
    ).to(device=device, dtype=dtype)
    module.load_init(model, args.draft_dir)
    model.eval()

    paths = iter_sample_paths(args.dataset_dir, args.max_samples)
    start_time = time.perf_counter()
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
                    step_index = int(row["step"]) - 1
                    conditional_den[step_index] += 1
                    if row["match"]:
                        exact_hits[step_index] += 1
                    if row["topk_hit"]:
                        topk_hits[step_index] += 1
                if len(examples) < 20 and (accepted < args.max_steps):
                    examples.append({
                        "sample": os.path.basename(path),
                        "family": family,
                        "prompt_id": prompt_id,
                        "start": start,
                        "accepted": accepted,
                        "rows": rows,
                    })
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
            if args.print_every and starts and starts % args.print_every == 0:
                print(json.dumps({
                    "processed_starts": starts,
                    "mean_accepted": accepted_total / starts,
                    "sample_index": sample_index,
                }, sort_keys=True), flush=True)
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
            "exact_hits": exact_hits[i],
            "exact_rate": exact_hits[i] / den if den else 0.0,
            "topk_hits": topk_hits[i],
            "topk_rate": topk_hits[i] / den if den else 0.0,
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
        "mean_accepted": accepted_total / starts,
        "acceptance_histogram": {str(i): hist[i] for i in range(len(hist))},
        "per_step": per_step,
        "elapsed_s": elapsed,
        "starts_per_s": starts / elapsed if elapsed else 0.0,
        "family_rows": family_rows,
        "sample_rows": sample_rows[:200],
        "first_mismatch_examples": examples,
    }
    text = json.dumps(summary, indent=2, sort_keys=True)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
            f.write("\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
