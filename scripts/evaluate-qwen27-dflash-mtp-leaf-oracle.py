#!/usr/bin/env python3
"""Offline DFlash DDTree plus intrinsic-MTP leaf acceptance oracle.

This is a target-owned acceptance diagnostic, not a throughput benchmark. It
uses no cache/history reuse and is never eligible for LocalMaxxing submission.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Sequence

import torch
import torch.nn.functional as F
from safetensors.torch import load_file


ROOT = Path(__file__).resolve().parents[1]
DDTREE_SCRIPT = ROOT / "scripts/evaluate-qwen27-dflash-ddtree-offline.py"
MTP_SCRIPT = ROOT / "scripts/evaluate-qwen27-intrinsic-mtp-offline.py"
TRAIN_SCRIPT = ROOT / "scripts/train-qwen27-dflash-offline.py"
DEFAULT_CORPUS = (
    "/mnt/usb-models/llm-optimization-artifacts/qwen27-dflash/"
    "fullcontext-fixed-suite-20260711T071359Z/corpus/shard-3/dataset"
)
DEFAULT_DRAFT = "/mnt/fast-ai/llm-cache/hf/manual/z-lab--Qwen3.6-27B-DFlash"
DEFAULT_TARGET = (
    "/mnt/fast-ai/llm-cache/hf/hub/"
    "models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/"
    "f5750c90b3776db658594df5fe8051098226dd8e"
)
CLASSIFICATION = (
    "diagnostic_offline_dflash_mtp_leaf_acceptance_not_throughput_"
    "not_localmaxxing"
)


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


def parse_ints(value: str) -> tuple[int, ...]:
    values = tuple(dict.fromkeys(int(piece.strip()) for piece in value.split(",")))
    if not values or any(value < 1 for value in values):
        raise ValueError("Expected a comma-separated list of positive integers")
    return values


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-dir", default=DEFAULT_CORPUS)
    parser.add_argument("--draft-dir", default=DEFAULT_DRAFT)
    parser.add_argument("--target-model", default=DEFAULT_TARGET)
    parser.add_argument("--dflash-source", default="/home/steve/src/dflash")
    parser.add_argument("--draft-tokens", type=int, default=15)
    parser.add_argument("--tree-budget", type=int, default=15)
    parser.add_argument("--equal-row-budget", type=int, default=19)
    parser.add_argument("--leaf-counts", default="1,2,4,8")
    parser.add_argument("--metric-tokens", type=int, default=100)
    parser.add_argument("--max-context", type=int, default=160)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--seed", type=int, default=20260711)
    parser.add_argument("--out", required=True)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument(
        "--merge-report",
        action="append",
        default=[],
        help="Merge existing shard reports instead of loading models.",
    )
    return parser.parse_args(argv)


def apply_endpoint_lm_head(
    hidden: torch.Tensor, lm_head: dict[str, torch.Tensor]
) -> torch.Tensor:
    flat = hidden.reshape(-1, hidden.shape[-1]).contiguous()
    if "int8_t" not in lm_head:
        return F.linear(flat, lm_head["bf16"])
    hidden_q, hidden_scale = torch.ops._xpu_C.per_token_quant_int8_xpu(flat)
    return torch.ops._xpu_C.int8_gemm_w8a8(
        hidden_q,
        hidden_scale,
        lm_head["int8_t"],
        lm_head["scales"],
        torch.bfloat16,
        None,
    )


def target_path(tree: Any, labels: torch.Tensor) -> tuple[int, int]:
    row = 0
    accepted = 0
    for token_id in labels.to(device="cpu", dtype=torch.long).tolist():
        child = tree.child_maps[row].get(int(token_id))
        if child is None:
            break
        row = child
        accepted += 1
    return accepted, row


def parent_scores(tree: Any, log_probs: torch.Tensor) -> list[tuple[float, int]]:
    path_log_probs = [0.0] * len(tree.parents)
    scores: list[tuple[float, int]] = []
    for row, (token_id, depth) in enumerate(
        zip(tree.node_token_ids, tree.node_depths), start=1
    ):
        parent = int(tree.parents[row])
        path_log_probs[row] = path_log_probs[parent] + float(
            log_probs[depth - 1, token_id].item()
        )
        covered = 0.0
        if depth < log_probs.shape[0]:
            covered = sum(
                math.exp(float(log_probs[depth, child_token].item()))
                for child_token in tree.child_maps[row]
            )
        uncovered = max(1.0e-12, 1.0 - min(covered, 1.0))
        scores.append((path_log_probs[row] + math.log(uncovered), row))
    return sorted(scores, reverse=True)


def pick_novel_token(
    logits: torch.Tensor, existing_children: dict[int, int]
) -> int:
    k = min(16, logits.numel())
    for token_id in torch.topk(logits, k=k).indices.to("cpu").tolist():
        if int(token_id) not in existing_children:
            return int(token_id)
    raise RuntimeError("Could not find a novel MTP leaf token in top-16")


def load_mtp_model(mtp: ModuleType, target_model: str, device: torch.device) -> Any:
    config = mtp.load_config(target_model)
    shape = mtp.shape_from_config(config)
    tensors = load_file(
        os.path.join(target_model, "model_extra_tensors.safetensors"),
        device="cpu",
    )
    embed = mtp.load_indexed_tensor(
        target_model, "model.language_model.embed_tokens.weight"
    )
    lm_head = mtp.load_indexed_tensor(target_model, "lm_head.weight")
    return mtp.IntrinsicMTP(
        shape=shape,
        tensors=tensors,
        embed_weight=embed,
        lm_head_weight=lm_head,
        device=device,
        dtype=torch.bfloat16,
        use_official_rope=True,
        draft_lm_head="int4-dequant",
        draft_lm_head_group_size=128,
        draft_lm_head_scale_dtype="bf16",
    ).eval()


def candidate_tokens(
    *,
    mtp_model: Any,
    hidden_rows: torch.Tensor,
    token_ids: torch.Tensor,
    positions: torch.Tensor,
    child_maps: Sequence[dict[int, int]],
) -> dict[int, int]:
    if hidden_rows.shape[0] == 0:
        return {}
    predicted_hidden = mtp_model(
        hidden_rows.unsqueeze(1),
        token_ids.view(-1, 1),
        positions.view(-1, 1),
        spec_step_idx=0,
    )
    logits = mtp_model.logits(predicted_hidden[:, -1, :])
    return {
        row: pick_novel_token(logits[index], child_maps[row])
        for index, row in enumerate(range(1, len(child_maps)))
    }


def summarize_records(
    records: list[dict[str, Any]], leaf_counts: tuple[int, ...], metric_tokens: int
) -> dict[str, Any]:
    if not records:
        raise ValueError("No records to summarize")
    policies = ["base", "equal_row", "proxy_all", "target_hidden_upper"] + [
        f"leaf_{count}" for count in leaf_counts
    ]
    anchor_means = {
        policy: statistics.fmean(float(row[f"{policy}_visible"]) for row in records)
        for policy in policies
    }
    grouped: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    for row in records:
        grouped[str(row["prompt_id"])][int(row["start"])] = row

    paired_anchor_deltas: dict[str, dict[str, Any]] = {}
    for policy in policies:
        if policy == "base":
            continue
        deltas = [
            int(row[f"{policy}_visible"]) - int(row["base_visible"])
            for row in records
        ]
        prompt_means = {
            prompt_id: statistics.fmean(
                int(row[f"{policy}_visible"]) - int(row["base_visible"])
                for row in rows_by_start.values()
            )
            for prompt_id, rows_by_start in sorted(grouped.items())
        }
        prompt_values = list(prompt_means.values())
        rng = random.Random(20260711)
        bootstrap_means = sorted(
            statistics.fmean(rng.choices(prompt_values, k=len(prompt_values)))
            for _ in range(20_000)
        )
        paired_anchor_deltas[policy] = {
            "mean": statistics.fmean(deltas),
            "median": statistics.median(deltas),
            "improved_anchors": sum(delta > 0 for delta in deltas),
            "unchanged_anchors": sum(delta == 0 for delta in deltas),
            "regressed_anchors": sum(delta < 0 for delta in deltas),
            "prompt_cluster_means": prompt_means,
            "prompt_cluster_bootstrap_95_ci": [
                bootstrap_means[int(0.025 * len(bootstrap_means))],
                bootstrap_means[int(0.975 * len(bootstrap_means)) - 1],
            ],
        }

    simulations: dict[str, dict[str, Any]] = {}
    for policy in policies:
        prompt_rows = []
        for prompt_id, rows_by_start in sorted(grouped.items()):
            start = min(rows_by_start)
            generated = 0
            cycles = 0
            while generated < metric_tokens:
                row = rows_by_start.get(start)
                if row is None:
                    raise RuntimeError(
                        f"Missing {prompt_id} anchor at start={start} during simulation"
                    )
                visible = min(
                    int(row[f"{policy}_visible"]), metric_tokens - generated
                )
                if visible < 1:
                    raise RuntimeError(f"Invalid visible count {visible}")
                start += visible
                generated += visible
                cycles += 1
            prompt_rows.append(
                {
                    "prompt_id": prompt_id,
                    "generated_tokens": generated,
                    "verifier_cycles": cycles,
                    "tokens_per_cycle": generated / cycles,
                }
            )
        values = [row["tokens_per_cycle"] for row in prompt_rows]
        simulations[policy] = {
            "prompts": len(prompt_rows),
            "median_tokens_per_cycle": statistics.median(values),
            "mean_tokens_per_cycle": statistics.fmean(values),
            "min_tokens_per_cycle": min(values),
            "rows": prompt_rows,
        }

    return {
        "anchor_count": len(records),
        "prompt_count": len(grouped),
        "anchor_mean_visible": anchor_means,
        "anchor_mean_delta_vs_base": {
            policy: anchor_means[policy] - anchor_means["base"]
            for policy in policies
            if policy != "base"
        },
        "paired_anchor_delta_vs_base": paired_anchor_deltas,
        "first_100_simulation": simulations,
    }


def merge_reports(args: argparse.Namespace) -> int:
    reports = [json.loads(Path(path).read_text()) for path in args.merge_report]
    records = [row for report in reports for row in report["records"]]
    leaf_counts = parse_ints(args.leaf_counts)
    result = dict(reports[0])
    result.update(
        {
            "merged": True,
            "source_reports": [os.path.realpath(path) for path in args.merge_report],
            "shard_index": None,
            "num_shards": len(reports),
            "summary": summarize_records(records, leaf_counts, args.metric_tokens),
            "records": sorted(
                records, key=lambda row: (row["prompt_id"], row["start"])
            ),
        }
    )
    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.merge_report:
        return merge_reports(args)
    if args.draft_tokens < 1 or args.tree_budget < 1:
        raise ValueError("Draft tokens and tree budget must be positive")
    if not 0 <= args.shard_index < args.num_shards:
        raise ValueError("Invalid shard index")
    leaf_counts = parse_ints(args.leaf_counts)
    torch.manual_seed(args.seed)
    if hasattr(torch, "xpu") and torch.xpu.is_available():
        torch.xpu.manual_seed_all(args.seed)

    ddtree = load_module(DDTREE_SCRIPT, "_qwen27_dflash_ddtree_leaf_oracle")
    mtp = load_module(MTP_SCRIPT, "_qwen27_intrinsic_mtp_leaf_oracle")
    helpers = ddtree.load_training_helpers(str(TRAIN_SCRIPT))
    paths = helpers.sample_paths([args.corpus_dir])
    paths = [
        path
        for index, path in enumerate(sorted(paths))
        if index % args.num_shards == args.shard_index
    ]
    if not paths:
        raise RuntimeError("Shard contains no corpus files")

    runtime_args = SimpleNamespace(
        dflash_source=args.dflash_source,
        draft_dir=args.draft_dir,
        target_model=args.target_model,
        draft_tokens=args.draft_tokens,
        train_scope="fc",
        position_rank=64,
        resume_adapter="",
        lm_head_mode="int8-ste",
        device=args.device,
    )
    dflash_model, embedding, target_lm_head = helpers.load_runtime(runtime_args)
    device = torch.device(args.device)
    mtp_model = load_mtp_model(mtp, args.target_model, device)
    records: list[dict[str, Any]] = []

    with torch.inference_mode():
        for path_index, path in enumerate(paths, start=1):
            sample = helpers.torch_load(path)
            prompt_id = str(sample.get("prompt_id") or Path(path).stem)
            start0 = int(sample["num_prompt_tokens"]) - 1
            target_ids = sample["sampled_next_token_ids"].to(torch.long)
            sample_positions = sample["positions"].to(torch.long)
            final_hidden = sample["hidden_state"].to(torch.bfloat16)
            last_start = start0 + args.metric_tokens - 1
            if last_start + args.draft_tokens + 1 >= target_ids.numel():
                raise RuntimeError(
                    f"{prompt_id} lacks the extra continuation label required "
                    "for a depth-15 MTP leaf"
                )

            for start in range(start0, last_start + 1):
                target_hidden, noise_embedding, position_ids, labels = (
                    helpers.make_block(
                        sample=sample,
                        start=start,
                        draft_tokens=args.draft_tokens,
                        max_context=args.max_context,
                        mask_token_id=dflash_model.mask_token_id,
                        embedding=embedding,
                        device=args.device,
                    )
                )
                draft_full_hidden = helpers.endpoint_mixed_dflash_forward(
                    model=dflash_model,
                    target_hidden=target_hidden,
                    noise_embedding=noise_embedding,
                    position_ids=position_ids,
                )
                draft_hidden = draft_full_hidden[:, 1:, :].squeeze(0)
                logits = apply_endpoint_lm_head(draft_hidden, target_lm_head)
                log_probs = ddtree.per_position_log_probabilities(logits)
                tree = ddtree.build_ddtree_tree(log_probs, args.tree_budget)
                equal_tree = ddtree.build_ddtree_tree(
                    log_probs, args.equal_row_budget
                )
                base_accepted, last_row = target_path(tree, labels)
                equal_accepted, _ = target_path(equal_tree, labels)

                node_depths = torch.tensor(
                    tree.node_depths, dtype=torch.long, device=device
                )
                node_tokens = torch.tensor(
                    tree.node_token_ids, dtype=torch.long, device=device
                )
                proxy_hidden = torch.stack(
                    [draft_hidden[depth - 1] for depth in tree.node_depths]
                )
                proxy_positions = (
                    sample_positions[start].to(device=device) + node_depths
                )
                proxy_candidates = candidate_tokens(
                    mtp_model=mtp_model,
                    hidden_rows=proxy_hidden,
                    token_ids=node_tokens,
                    positions=proxy_positions,
                    child_maps=tree.child_maps,
                )
                ranked_parents = [row for _, row in parent_scores(tree, log_probs)]

                next_target = int(target_ids[start + base_accepted + 1])
                proxy_all_accepted = base_accepted + int(
                    last_row in proxy_candidates
                    and proxy_candidates[last_row] == next_target
                )
                row_result: dict[str, Any] = {
                    "prompt_id": prompt_id,
                    "sample": Path(path).name,
                    "start": start,
                    "generation_offset": start - start0,
                    "base_visible": 1 + base_accepted,
                    "equal_row_visible": 1 + equal_accepted,
                    "proxy_all_visible": 1 + proxy_all_accepted,
                    "base_last_row": last_row,
                    "ranked_parent_rows": ranked_parents,
                }
                for leaf_count in leaf_counts:
                    selected = set(ranked_parents[:leaf_count])
                    accepted = base_accepted + int(
                        last_row in selected
                        and proxy_candidates[last_row] == next_target
                    )
                    row_result[f"leaf_{leaf_count}_visible"] = 1 + accepted

                target_parent_index = start + base_accepted
                target_parent_hidden = final_hidden[
                    target_parent_index : target_parent_index + 1
                ].to(device=device)
                target_parent_token = target_ids[
                    target_parent_index : target_parent_index + 1
                ].to(device=device)
                target_parent_position = sample_positions[
                    target_parent_index : target_parent_index + 1
                ].to(device=device)
                target_prediction = mtp_model(
                    target_parent_hidden.unsqueeze(1),
                    target_parent_token.view(1, 1),
                    target_parent_position.view(1, 1),
                    spec_step_idx=0,
                )
                target_logits = mtp_model.logits(target_prediction[:, -1, :])[0]
                target_candidate = int(torch.argmax(target_logits).item())
                row_result["target_hidden_upper_visible"] = 1 + base_accepted + int(
                    target_candidate == next_target
                )
                records.append(row_result)

            if args.progress_every and path_index % args.progress_every == 0:
                print(
                    f"shard {args.shard_index}: prompts {path_index}/{len(paths)} "
                    f"anchors={len(records)}",
                    file=sys.stderr,
                    flush=True,
                )

    result = {
        "classification": CLASSIFICATION,
        "diagnostic": True,
        "offline": True,
        "throughput_benchmark": False,
        "localmaxxing_eligible": False,
        "interpretation": (
            "Target-owned acceptance only. DFlash-hidden MTP leaves are an "
            "implementable proxy without branch KV; target_hidden_upper uses "
            "causally unavailable future target hidden state and is only an "
            "upper bound."
        ),
        "corpus_dir": os.path.realpath(args.corpus_dir),
        "draft_dir": os.path.realpath(args.draft_dir),
        "target_model": os.path.realpath(args.target_model),
        "device": args.device,
        "seed": args.seed,
        "draft_tokens": args.draft_tokens,
        "tree_budget": args.tree_budget,
        "equal_row_budget": args.equal_row_budget,
        "leaf_counts": list(leaf_counts),
        "metric_tokens": args.metric_tokens,
        "parent_selection": (
            "descending path_probability_times_uncovered_dflash_child_mass"
        ),
        "mtp_rope": (
            "vllm_get_rope"
            if mtp_model.rope is not None
            else "local_text_only_neox_rope_fallback"
        ),
        "mtp_leaf_head": "runtime-style INT4 dequant, group128, BF16 scales",
        "mtp_leaf_semantics": (
            "one independent spec_step_idx=0 MTP forward from the DFlash "
            "pre-LM-head hidden row and node token; no branch/history KV"
        ),
        "shard_index": args.shard_index,
        "num_shards": args.num_shards,
        "summary": summarize_records(records, leaf_counts, args.metric_tokens),
        "records": records,
    }
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
