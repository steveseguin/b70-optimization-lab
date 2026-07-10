#!/usr/bin/env python3
"""Evaluate or adapt Qwen3.6-27B DFlash on target-owned XPU traces.

This is an offline draft-quality pre-gate, not a throughput benchmark. It uses
``qwen36_eagle_sequence_v2`` samples containing target auxiliary hidden states
and target-greedy continuations. For each anchor it reconstructs the DFlash
inference block:

* target context features end at the anchor;
* the first block token is the target-owned next token;
* the remaining positions are mask tokens predicted in parallel;
* acceptance is the longest exact prefix against subsequent target tokens.

The target model is never changed. Any exported draft must still pass a real
target-verified endpoint gate before it can support a speed or quality claim.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import torch
import torch.nn.functional as F
from safetensors import safe_open
from safetensors.torch import save_file


DEFAULT_DRAFT = "/mnt/fast-ai/llm-cache/hf/manual/z-lab--Qwen3.6-27B-DFlash"
DEFAULT_TARGET = (
    "/mnt/fast-ai/llm-cache/hf/hub/"
    "models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/"
    "f5750c90b3776db658594df5fe8051098226dd8e"
)


@dataclass(frozen=True)
class Anchor:
    path: str
    start: int
    family: str
    prompt_id: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", action="append", required=True)
    parser.add_argument("--heldout-dir", action="append", default=[])
    parser.add_argument("--draft-dir", default=DEFAULT_DRAFT)
    parser.add_argument("--target-model", default=DEFAULT_TARGET)
    parser.add_argument("--dflash-source", default="/home/steve/src/dflash")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument(
        "--lm-head-mode",
        choices=("bf16", "int8-ste"),
        default="int8-ste",
        help=(
            "Draft-token head used by the offline gate. int8-ste matches the "
            "endpoint INT8/BF16-scale forward and uses BF16 straight-through "
            "gradients during training."
        ),
    )
    parser.add_argument("--draft-tokens", type=int, default=8)
    parser.add_argument("--min-context", type=int, default=16)
    parser.add_argument("--max-context", type=int, default=160)
    parser.add_argument("--train-starts", type=int, default=0)
    parser.add_argument("--heldout-starts", type=int, default=2048)
    parser.add_argument(
        "--eval-repeats",
        type=int,
        default=3,
        help="Odd repeat count for baseline/final per-anchor median acceptance.",
    )
    parser.add_argument("--steps", type=int, default=0)
    parser.add_argument("--lr", type=float, default=1e-6)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=27)
    parser.add_argument("--eval-every", type=int, default=100)
    parser.add_argument("--log-every", type=int, default=20)
    parser.add_argument(
        "--loss-mode",
        choices=("all", "position-decay", "accept-until-fail"),
        default="accept-until-fail",
    )
    parser.add_argument(
        "--position-decay",
        type=float,
        default=0.7788007830714049,
        help=(
            "Per-position multiplier for position-decay loss. The default is "
            "exp(-1/4), matching the DFlash paper's gamma=4 for block size 8."
        ),
    )
    parser.add_argument(
        "--train-scope",
        choices=("fc", "fc-norm", "layers", "all-draft"),
        default="fc",
    )
    parser.add_argument(
        "--lr-schedule", choices=("constant", "cosine"), default="cosine"
    )
    parser.add_argument(
        "--resume-adapter",
        default="",
        help="Optional safetensors file containing named draft parameters.",
    )
    return parser.parse_args()


def torch_load(path: str) -> dict[str, Any]:
    try:
        return torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        return torch.load(path, map_location="cpu")


def sample_paths(dataset_dirs: Iterable[str]) -> list[str]:
    paths: list[str] = []
    for dataset_dir in dataset_dirs:
        paths.extend(sorted(glob.glob(os.path.join(dataset_dir, "*.pt"))))
    if not paths:
        raise FileNotFoundError(f"No .pt samples found under {list(dataset_dirs)}")
    return paths


def sample_length(sample: dict[str, Any]) -> int:
    return min(
        int(sample["aux_hidden_states"].shape[0]),
        int(sample["sampled_next_token_ids"].shape[0]),
        int(sample["positions"].shape[0]),
    )


def collect_anchors(
    paths: list[str],
    *,
    draft_tokens: int,
    min_context: int,
    limit: int,
    seed: int,
) -> list[Anchor]:
    anchors: list[Anchor] = []
    for path in paths:
        sample = torch_load(path)
        if sample.get("format") != "qwen36_eagle_sequence_v2":
            continue
        aux = sample.get("aux_hidden_states")
        if not torch.is_tensor(aux) or tuple(aux.shape[1:]) != (5, 5120):
            continue
        length = sample_length(sample)
        family = str(sample.get("family") or "unknown")
        prompt_id = str(sample.get("prompt_id") or Path(path).stem)
        first = max(0, min_context - 1)
        last_exclusive = length - draft_tokens
        for start in range(first, max(first, last_exclusive)):
            anchors.append(
                Anchor(path=path, start=start, family=family, prompt_id=prompt_id)
            )
    rng = random.Random(seed)
    rng.shuffle(anchors)
    if limit > 0:
        anchors = anchors[:limit]
    if not anchors:
        raise RuntimeError("No valid five-aux DFlash anchors were found")
    return anchors


def load_named_tensor(model_dir: str, name: str) -> torch.Tensor:
    index_path = os.path.join(model_dir, "model.safetensors.index.json")
    index = json.loads(Path(index_path).read_text())
    shard = index["weight_map"][name]
    with safe_open(
        os.path.join(model_dir, shard), framework="pt", device="cpu"
    ) as handle:
        return handle.get_tensor(name)


def load_runtime(
    args: argparse.Namespace,
) -> tuple[Any, torch.Tensor, dict[str, torch.Tensor]]:
    sys.path.insert(0, args.dflash_source)
    from dflash.model import DFlashDraftModel
    from transformers import Qwen3Config

    config = Qwen3Config.from_pretrained(args.draft_dir, local_files_only=True)
    config._attn_implementation = "eager"
    model = DFlashDraftModel.from_pretrained(
        args.draft_dir,
        config=config,
        local_files_only=True,
        dtype=torch.bfloat16,
    )
    if args.resume_adapter:
        named_parameters = dict(model.named_parameters())
        with safe_open(
            args.resume_adapter, framework="pt", device="cpu"
        ) as handle:
            for name in handle.keys():
                if name not in named_parameters:
                    raise KeyError(f"Unknown draft adapter parameter: {name}")
                named_parameters[name].data.copy_(handle.get_tensor(name))
    model = model.to(args.device)
    embedding = load_named_tensor(
        args.target_model, "model.language_model.embed_tokens.weight"
    ).to(args.device)
    lm_head_bf16 = load_named_tensor(args.target_model, "lm_head.weight").to(
        args.device
    )
    embedding.requires_grad_(False)
    lm_head_bf16.requires_grad_(False)
    lm_head = {"bf16": lm_head_bf16}
    if args.lm_head_mode == "int8-ste":
        import vllm_xpu_kernels._xpu_C  # noqa: F401

        required = ("per_token_quant_int8_xpu", "int8_gemm_w8a8")
        missing = [name for name in required if not hasattr(torch.ops._xpu_C, name)]
        if missing:
            raise RuntimeError(f"Missing XPU INT8 LM-head ops: {missing}")
        with torch.no_grad():
            weight_f = lm_head_bf16.float()
            scales = weight_f.abs().amax(dim=1).clamp_min(1.0e-10) / 127.0
            weight_q_t = (
                torch.round(weight_f / scales.view(-1, 1))
                .clamp(-127, 127)
                .to(torch.int8)
                .t()
                .contiguous()
            )
            lm_head["int8_t"] = weight_q_t
            lm_head["scales"] = scales.to(torch.bfloat16).contiguous()
            del weight_f, scales
    return model, embedding, lm_head


class SampleCache:
    def __init__(self) -> None:
        self.path = ""
        self.sample: dict[str, Any] | None = None

    def get(self, path: str) -> dict[str, Any]:
        if path != self.path:
            self.path = path
            self.sample = torch_load(path)
        assert self.sample is not None
        return self.sample


def make_block(
    *,
    sample: dict[str, Any],
    start: int,
    draft_tokens: int,
    max_context: int,
    mask_token_id: int,
    embedding: torch.Tensor,
    device: str,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    context_first = max(0, start + 1 - max_context)
    aux = sample["aux_hidden_states"][context_first : start + 1]
    target_hidden = aux.reshape(1, aux.shape[0], -1).to(
        device=device, dtype=torch.bfloat16, non_blocking=True
    )
    target_ids = sample["sampled_next_token_ids"].to(torch.long)
    block_len = draft_tokens + 1
    block_ids = torch.full(
        (1, block_len), mask_token_id, dtype=torch.long, device=device
    )
    block_ids[0, 0] = target_ids[start].to(device)
    noise_embedding = F.embedding(block_ids, embedding)

    context_positions = sample["positions"][context_first : start + 1].to(
        device=device, dtype=torch.long, non_blocking=True
    )
    noise_positions = sample["positions"][start].to(device=device) + torch.arange(
        1, block_len + 1, device=device, dtype=torch.long
    )
    position_ids = torch.cat((context_positions, noise_positions)).unsqueeze(0)
    labels = target_ids[start + 1 : start + 1 + draft_tokens].to(
        device=device, non_blocking=True
    )
    return target_hidden, noise_embedding, position_ids, labels


def draft_logits(
    *,
    model: Any,
    lm_head: dict[str, torch.Tensor],
    target_hidden: torch.Tensor,
    noise_embedding: torch.Tensor,
    position_ids: torch.Tensor,
) -> torch.Tensor:
    hidden = model(
        target_hidden=target_hidden,
        noise_embedding=noise_embedding,
        position_ids=position_ids,
        use_cache=False,
    )
    hidden = hidden[:, 1:]
    hidden_flat = hidden.reshape(-1, hidden.shape[-1]).contiguous()
    if "int8_t" not in lm_head:
        return F.linear(hidden_flat, lm_head["bf16"])
    with torch.no_grad():
        hidden_q, hidden_scale = torch.ops._xpu_C.per_token_quant_int8_xpu(
            hidden_flat
        )
        int8_logits = torch.ops._xpu_C.int8_gemm_w8a8(
            hidden_q,
            hidden_scale,
            lm_head["int8_t"],
            lm_head["scales"],
            torch.bfloat16,
            None,
        )
    if model.training:
        bf16_logits = F.linear(hidden_flat, lm_head["bf16"])
        # Forward values and token IDs match the endpoint INT8 head exactly;
        # gradients use the frozen BF16 head as a straight-through estimator.
        int8_logits = bf16_logits + (int8_logits - bf16_logits).detach()
    return int8_logits


def accepted_prefix(prediction: torch.Tensor, labels: torch.Tensor) -> int:
    return int((prediction == labels).to(torch.int64).cumprod(0).sum().item())


def evaluate(
    *,
    model: Any,
    embedding: torch.Tensor,
    lm_head: dict[str, torch.Tensor],
    anchors: list[Anchor],
    args: argparse.Namespace,
    include_records: bool = True,
) -> dict[str, Any]:
    model.eval()
    cache = SampleCache()
    histogram: Counter[int] = Counter()
    step_correct = [0] * args.draft_tokens
    step_alive = [0] * args.draft_tokens
    by_family: dict[str, list[int]] = defaultdict(list)
    prefixes: list[int] = []
    records: list[dict[str, Any]] = []
    started = time.perf_counter()
    with torch.inference_mode():
        for anchor in anchors:
            tensors = make_block(
                sample=cache.get(anchor.path),
                start=anchor.start,
                draft_tokens=args.draft_tokens,
                max_context=args.max_context,
                mask_token_id=model.mask_token_id,
                embedding=embedding,
                device=args.device,
            )
            logits = draft_logits(
                model=model,
                lm_head=lm_head,
                target_hidden=tensors[0],
                noise_embedding=tensors[1],
                position_ids=tensors[2],
            )
            pred = logits.argmax(-1)
            labels = tensors[3]
            prefix = accepted_prefix(pred, labels)
            prefixes.append(prefix)
            if include_records:
                records.append(
                    {
                        "prompt_id": anchor.prompt_id,
                        "family": anchor.family,
                        "sample": Path(anchor.path).name,
                        "start": anchor.start,
                        "accepted_drafts": prefix,
                    }
                )
            histogram[prefix] += 1
            by_family[anchor.family].append(prefix)
            alive = True
            for index in range(args.draft_tokens):
                if alive:
                    step_alive[index] += 1
                    correct = bool((pred[index] == labels[index]).item())
                    if correct:
                        step_correct[index] += 1
                    else:
                        alive = False
    elapsed = time.perf_counter() - started
    mean_prefix = sum(prefixes) / len(prefixes)
    result = {
        "anchors": len(prefixes),
        "draft_tokens": args.draft_tokens,
        "mean_accepted_drafts": mean_prefix,
        "visible_tokens_per_step": 1.0 + mean_prefix,
        "full_accept_rate": histogram[args.draft_tokens] / len(prefixes),
        "histogram": {str(k): histogram[k] for k in range(args.draft_tokens + 1)},
        "conditional_exact_by_position": [
            step_correct[i] / step_alive[i] if step_alive[i] else 0.0
            for i in range(args.draft_tokens)
        ],
        "alive_rows_by_position": step_alive,
        "per_family": {
            family: {
                "anchors": len(values),
                "mean_accepted_drafts": sum(values) / len(values),
            }
            for family, values in sorted(by_family.items())
        },
        "elapsed_s": elapsed,
        "anchors_per_s": len(prefixes) / elapsed if elapsed else None,
    }
    if include_records:
        result["records"] = records
    return result


def evaluate_repeated(
    *,
    model: Any,
    embedding: torch.Tensor,
    lm_head: dict[str, torch.Tensor],
    anchors: list[Anchor],
    args: argparse.Namespace,
) -> dict[str, Any]:
    if args.eval_repeats < 1 or args.eval_repeats % 2 == 0:
        raise ValueError("--eval-repeats must be a positive odd integer")
    runs = [
        evaluate(
            model=model,
            embedding=embedding,
            lm_head=lm_head,
            anchors=anchors,
            args=args,
        )
        for _ in range(args.eval_repeats)
    ]
    if len(runs) == 1:
        runs[0]["evaluation_repeats"] = 1
        return runs[0]

    by_key: dict[tuple[str, str, int], list[int]] = defaultdict(list)
    templates: dict[tuple[str, str, int], dict[str, Any]] = {}
    for run in runs:
        for record in run["records"]:
            key = (
                str(record["prompt_id"]),
                str(record["sample"]),
                int(record["start"]),
            )
            by_key[key].append(int(record["accepted_drafts"]))
            templates[key] = record
    if any(len(values) != len(runs) for values in by_key.values()):
        raise RuntimeError("Repeated evaluation records did not align")

    records = []
    histogram: Counter[int] = Counter()
    by_family: dict[str, list[int]] = defaultdict(list)
    for key in sorted(by_key):
        accepted = int(statistics.median(by_key[key]))
        record = dict(templates[key])
        record["accepted_drafts"] = accepted
        record["repeat_values"] = by_key[key]
        records.append(record)
        histogram[accepted] += 1
        by_family[str(record["family"])].append(accepted)
    mean_prefix = sum(row["accepted_drafts"] for row in records) / len(records)
    result = dict(runs[0])
    result.update(
        {
            "mean_accepted_drafts": mean_prefix,
            "visible_tokens_per_step": 1.0 + mean_prefix,
            "full_accept_rate": histogram[args.draft_tokens] / len(records),
            "histogram": {
                str(index): histogram[index]
                for index in range(args.draft_tokens + 1)
            },
            "per_family": {
                family: {
                    "anchors": len(values),
                    "mean_accepted_drafts": sum(values) / len(values),
                }
                for family, values in sorted(by_family.items())
            },
            "records": records,
            "evaluation_repeats": len(runs),
            "repeat_visible_tokens_per_step": [
                run["visible_tokens_per_step"] for run in runs
            ],
            "elapsed_s": sum(run["elapsed_s"] for run in runs),
        }
    )
    result["anchors_per_s"] = (
        len(records) * len(runs) / result["elapsed_s"]
        if result["elapsed_s"]
        else None
    )
    return result


def loss_weights(
    *,
    logits: torch.Tensor,
    labels: torch.Tensor,
    mode: str,
    decay: float,
) -> torch.Tensor:
    count = labels.numel()
    if mode == "all":
        return torch.ones(count, device=logits.device, dtype=torch.float32)
    if mode == "position-decay":
        positions = torch.arange(count, device=logits.device, dtype=torch.float32)
        return torch.pow(torch.tensor(decay, device=logits.device), positions)
    prediction = logits.detach().argmax(-1)
    correct = prediction.eq(labels)
    alive_before = torch.cat(
        (
            torch.ones(1, device=logits.device, dtype=torch.bool),
            correct[:-1].to(torch.int64).cumprod(0).bool(),
        )
    )
    # Include the first failure: it is the token that must be repaired to
    # lengthen the verifier-accepted prefix. Ignore positions beyond it.
    return alive_before.to(torch.float32)


def configure_training(model: Any, scope: str) -> list[torch.nn.Parameter]:
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    if scope in ("fc", "fc-norm"):
        model.fc.weight.requires_grad_(True)
    if scope == "fc-norm":
        model.hidden_norm.weight.requires_grad_(True)
    if scope == "layers":
        for parameter in model.layers.parameters():
            parameter.requires_grad_(True)
        for parameter in model.norm.parameters():
            parameter.requires_grad_(True)
    if scope == "all-draft":
        for parameter in model.parameters():
            parameter.requires_grad_(True)
    parameters = [
        parameter for parameter in model.parameters() if parameter.requires_grad
    ]
    if not parameters:
        raise RuntimeError(f"No trainable parameters for scope {scope}")
    return parameters


def train(
    *,
    model: Any,
    embedding: torch.Tensor,
    lm_head: dict[str, torch.Tensor],
    train_anchors: list[Anchor],
    heldout_anchors: list[Anchor],
    baseline: dict[str, Any],
    args: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any]]:
    parameters = configure_training(model, args.train_scope)
    optimizer = torch.optim.AdamW(
        parameters,
        lr=args.lr,
        weight_decay=args.weight_decay,
        foreach=False,
    )
    scheduler = None
    if args.lr_schedule == "cosine":
        warmup_steps = max(1, int(args.steps * 0.04))

        def lr_multiplier(step: int) -> float:
            if step < warmup_steps:
                return step / warmup_steps
            progress = (step - warmup_steps) / max(1, args.steps - warmup_steps)
            return 0.5 * (1.0 + math.cos(math.pi * min(progress, 1.0)))

        scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_multiplier)
    rng = random.Random(args.seed + 991)
    cache = SampleCache()
    losses: list[float] = []
    eval_history: list[dict[str, Any]] = [{"step": 0, "metrics": baseline}]
    started = time.perf_counter()
    model.train()
    for step in range(1, args.steps + 1):
        anchor = train_anchors[(step - 1) % len(train_anchors)]
        if (step - 1) % len(train_anchors) == 0:
            rng.shuffle(train_anchors)
            anchor = train_anchors[0]
        tensors = make_block(
            sample=cache.get(anchor.path),
            start=anchor.start,
            draft_tokens=args.draft_tokens,
            max_context=args.max_context,
            mask_token_id=model.mask_token_id,
            embedding=embedding,
            device=args.device,
        )
        logits = draft_logits(
            model=model,
            lm_head=lm_head,
            target_hidden=tensors[0],
            noise_embedding=tensors[1],
            position_ids=tensors[2],
        )
        labels = tensors[3]
        per_position = F.cross_entropy(
            logits.float(), labels, reduction="none"
        )
        weights = loss_weights(
            logits=logits,
            labels=labels,
            mode=args.loss_mode,
            decay=args.position_decay,
        )
        loss = (per_position * weights).sum() / weights.sum().clamp_min(1.0)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(parameters, args.grad_clip)
        optimizer.step()
        if scheduler is not None:
            scheduler.step()
        losses.append(float(loss.detach().item()))
        if args.log_every and step % args.log_every == 0:
            recent = losses[-args.log_every :]
            print(
                json.dumps(
                    {
                        "step": step,
                        "loss": sum(recent) / len(recent),
                        "lr": optimizer.param_groups[0]["lr"],
                        "elapsed_s": time.perf_counter() - started,
                    }
                ),
                flush=True,
            )
        if args.eval_every and step % args.eval_every == 0:
            metrics = evaluate(
                model=model,
                embedding=embedding,
                lm_head=lm_head,
                anchors=heldout_anchors,
                args=args,
                include_records=False,
            )
            eval_history.append({"step": step, "metrics": metrics})
            print(json.dumps(eval_history[-1]), flush=True)
            model.train()
    final = evaluate_repeated(
        model=model,
        embedding=embedding,
        lm_head=lm_head,
        anchors=heldout_anchors,
        args=args,
    )
    final_history = {
        "step": args.steps,
        "metrics": final,
        "final_repeated": True,
    }
    if eval_history and eval_history[-1]["step"] == args.steps:
        eval_history[-1] = final_history
    else:
        eval_history.append(final_history)
    training = {
        "steps": args.steps,
        "lr": args.lr,
        "weight_decay": args.weight_decay,
        "loss_mode": args.loss_mode,
        "position_decay": args.position_decay,
        "train_scope": args.train_scope,
        "lr_schedule": args.lr_schedule,
        "mean_loss": sum(losses) / len(losses) if losses else None,
        "last_loss": losses[-1] if losses else None,
        "elapsed_s": time.perf_counter() - started,
        "eval_history": eval_history,
    }
    return final, training


def main() -> int:
    args = parse_args()
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    train_paths = sample_paths(args.dataset_dir)
    heldout_paths = sample_paths(args.heldout_dir or args.dataset_dir)
    train_anchors = collect_anchors(
        train_paths,
        draft_tokens=args.draft_tokens,
        min_context=args.min_context,
        limit=args.train_starts,
        seed=args.seed,
    )
    heldout_anchors = collect_anchors(
        heldout_paths,
        draft_tokens=args.draft_tokens,
        min_context=args.min_context,
        limit=args.heldout_starts,
        seed=args.seed + 1,
    )
    # Evaluation order does not affect the metric. Group by source file so the
    # single-sample cache avoids rereading multi-megabyte trace tensors for
    # every anchor.
    heldout_anchors.sort(key=lambda anchor: (anchor.path, anchor.start))
    model, embedding, lm_head = load_runtime(args)
    baseline = evaluate_repeated(
        model=model,
        embedding=embedding,
        lm_head=lm_head,
        anchors=heldout_anchors,
        args=args,
    )
    final = baseline
    training = None
    if args.steps > 0:
        final, training = train(
            model=model,
            embedding=embedding,
            lm_head=lm_head,
            train_anchors=train_anchors,
            heldout_anchors=heldout_anchors,
            baseline=baseline,
            args=args,
        )
        save_file(
            {
                name: parameter.detach().to("cpu").contiguous()
                for name, parameter in model.named_parameters()
                if parameter.requires_grad
            },
            str(out_dir / "dflash_adapter.safetensors"),
        )

    result = {
        "classification": "diagnostic_offline_dflash_acceptance_not_endpoint_not_localmaxxing",
        "draft_dir": os.path.realpath(args.draft_dir),
        "target_model": os.path.realpath(args.target_model),
        "dataset_dirs": [os.path.realpath(path) for path in args.dataset_dir],
        "heldout_dirs": [
            os.path.realpath(path) for path in (args.heldout_dir or args.dataset_dir)
        ],
        "device": args.device,
        "seed": args.seed,
        "draft_tokens": args.draft_tokens,
        "lm_head_mode": args.lm_head_mode,
        "min_context": args.min_context,
        "max_context": args.max_context,
        "train_anchor_count": len(train_anchors),
        "heldout_anchor_count": len(heldout_anchors),
        "eval_repeats": args.eval_repeats,
        "baseline": baseline,
        "final": final,
        "training": training,
        "decision_rule": (
            "Endpoint work requires a prompt-clustered acceptance improvement "
            "with a conservative throughput projection near or above 100 tok/s; "
            "offline acceptance alone is never a speed or quality claim."
        ),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
