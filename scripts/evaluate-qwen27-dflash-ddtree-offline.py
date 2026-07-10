#!/usr/bin/env python3
"""Offline DDTree acceptance oracle for corrected Qwen27 DFlash traces.

This diagnostic runs DFlash once per anchor and evaluation pass, converts the
parallel draft logits to per-position log probabilities, and builds the
liranringel/ddtree best-first tree for each requested node budget. The accepted
path is read from target-owned continuation labels stored in each trace.

This is an offline acceptance diagnostic. It is not endpoint throughput and is
not eligible for LocalMaxxing submission.
"""

from __future__ import annotations

import argparse
import heapq
import importlib.util
import json
import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Sequence

import torch


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_TRAIN_SCRIPT = SCRIPT_DIR / "train-qwen27-dflash-offline.py"
DEFAULT_DRAFT = "/mnt/fast-ai/llm-cache/hf/manual/z-lab--Qwen3.6-27B-DFlash"
DEFAULT_TARGET = (
    "/mnt/fast-ai/llm-cache/hf/hub/"
    "models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/"
    "f5750c90b3776db658594df5fe8051098226dd8e"
)
DEFAULT_CORPUS = (
    "/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/"
    "qwen27-dflash-aux-v8-corrected5-v6b-4gpu-20260710T040000Z/"
    "shard-3/dataset"
)
DEFAULT_NODE_BUDGETS = "16,32,64,128,256,512,1024"
DDTREE_REFERENCE = "/home/steve/src/ddtree/ddtree.py:build_ddtree_tree"
CLASSIFICATION = (
    "diagnostic_offline_ddtree_acceptance_oracle_not_throughput_not_localmaxxing"
)


@dataclass(frozen=True)
class DDTree:
    """Timing-free structural result from the official best-first algorithm."""

    node_token_ids: tuple[int, ...]
    node_depths: tuple[int, ...]
    parents: tuple[int, ...]
    child_maps: tuple[dict[int, int], ...]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Measure offline target-owned acceptance of official DDTree "
            "best-first trees built from corrected Qwen27 DFlash logits. "
            "This is diagnostic only, not throughput or LocalMaxxing evidence."
        )
    )
    parser.add_argument(
        "--draft-dir",
        default=DEFAULT_DRAFT,
        help="DFlash checkpoint directory (default: current Qwen27 draft).",
    )
    parser.add_argument(
        "--target-model",
        default=DEFAULT_TARGET,
        help=(
            "Target checkpoint providing the embedding and endpoint INT8 "
            "LM-head weights."
        ),
    )
    parser.add_argument(
        "--corpus-dir",
        "--heldout-dir",
        "--dataset-dir",
        dest="corpus_dirs",
        action="append",
        default=[],
        help=(
            "Corrected qwen36_eagle_sequence_v2 directory. May repeat. A "
            "corpus root is resolved to shard-3/dataset."
        ),
    )
    parser.add_argument(
        "--train-script",
        default=str(DEFAULT_TRAIN_SCRIPT),
        help="Training helper loaded with importlib for shared DFlash semantics.",
    )
    parser.add_argument("--dflash-source", default="/home/steve/src/dflash")
    parser.add_argument(
        "--node-budgets",
        "--tree-budgets",
        "--tree-budget",
        dest="node_budgets",
        default=DEFAULT_NODE_BUDGETS,
        help="Comma-separated DDTree node budgets, excluding the root.",
    )
    parser.add_argument("--draft-tokens", type=int, default=8)
    parser.add_argument("--min-context", type=int, default=16)
    parser.add_argument("--max-context", type=int, default=160)
    parser.add_argument(
        "--heldout-starts",
        type=int,
        default=2048,
        help="Maximum sampled heldout anchors; 0 uses every valid anchor.",
    )
    parser.add_argument(
        "--eval-repeats",
        type=int,
        default=3,
        help="Positive odd number of evaluation passes; medians are reported.",
    )
    parser.add_argument(
        "--deterministic-one-pass",
        "--one-pass",
        action="store_true",
        help=(
            "Use one seeded pass and request deterministic PyTorch algorithms; "
            "overrides --eval-repeats."
        ),
    )
    parser.add_argument("--seed", type=int, default=27)
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
        help="Write anchor-count progress to stderr; 0 disables it.",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional JSON output path. The complete report is also printed.",
    )
    return parser.parse_args(argv)


def parse_node_budgets(value: str) -> tuple[int, ...]:
    pieces = [piece.strip() for piece in value.split(",")]
    if not pieces or any(not piece for piece in pieces):
        raise ValueError("--node-budgets must be a comma-separated integer list")
    try:
        budgets = [int(piece) for piece in pieces]
    except ValueError as exc:
        raise ValueError("--node-budgets must contain only base-10 integers") from exc
    if any(budget < 0 for budget in budgets):
        raise ValueError("--node-budgets values must be non-negative")
    return tuple(dict.fromkeys(budgets))


def resolve_corpus_dir(value: str) -> str:
    """Accept either a direct sample directory or a corrected corpus root."""

    path = Path(value).expanduser()
    candidates = (path, path / "shard-3" / "dataset", path / "dataset")
    for candidate in candidates:
        if candidate.is_dir() and next(candidate.glob("*.pt"), None) is not None:
            return str(candidate)
    return str(path)


def load_training_helpers(path: str) -> ModuleType:
    """Load the hyphenated training script without importing it as a package."""

    helper_path = Path(path).expanduser().resolve()
    if not helper_path.is_file():
        raise FileNotFoundError(f"Training helper does not exist: {helper_path}")
    module_name = "_qwen27_dflash_offline_training_helpers"
    spec = importlib.util.spec_from_file_location(module_name, helper_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create import spec for {helper_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    required = (
        "sample_paths",
        "collect_anchors",
        "load_runtime",
        "SampleCache",
        "make_block",
        "draft_logits",
        "accepted_prefix",
    )
    missing = [name for name in required if not hasattr(module, name)]
    if missing:
        raise AttributeError(
            f"Training helper {helper_path} is missing shared API: {missing}"
        )
    return module


def per_position_log_probabilities(logits: torch.Tensor) -> torch.Tensor:
    """Match DDTree's float32 log-normalization before best-first expansion."""

    if logits.ndim != 2:
        raise ValueError(f"Expected [positions, vocab] logits, got {logits.shape}")
    logits_float = logits.float()
    return logits_float - torch.logsumexp(logits_float, dim=-1, keepdim=True)


def build_ddtree_tree(log_probs: torch.Tensor, budget: int) -> DDTree:
    """Build the liranringel/ddtree best-first tree without timing imports.

    This is the structural heap portion of ``ddtree.py:build_ddtree_tree``.
    ``log_probs`` is already normalized per position, so no CUDA timing helper,
    target verifier, visibility tensor, or generation runtime is imported.
    The root is index 0 and is not counted against ``budget``.
    """

    if log_probs.ndim != 2:
        raise ValueError(
            f"Expected [positions, vocab] log probabilities, got {log_probs.shape}"
        )
    if budget < 0:
        raise ValueError("DDTree node budget must be non-negative")
    depth_limit, vocab_size = (int(size) for size in log_probs.shape)
    if budget == 0 or depth_limit == 0 or vocab_size == 0:
        return DDTree((), (), (-1,), ({},))

    topk = min(budget, vocab_size)
    top_log_probs, top_token_ids = torch.topk(log_probs, k=topk, dim=-1)
    top_log_probs_rows = top_log_probs.to(device="cpu", dtype=torch.float32).tolist()
    top_token_id_rows = top_token_ids.to(device="cpu", dtype=torch.long).tolist()

    first_log_weight = float(top_log_probs_rows[0][0])
    heap: list[tuple[float, tuple[int, ...], int, int, int, float]] = [
        (-first_log_weight, (0,), 0, 1, 0, first_log_weight)
    ]
    node_token_ids: list[int] = []
    node_depths: list[int] = []
    parents = [-1]
    child_maps: list[dict[int, int]] = [{}]

    while heap and len(node_token_ids) < budget:
        _, ranks, parent_index, depth, rank, log_weight = heapq.heappop(heap)
        token_id = int(top_token_id_rows[depth - 1][rank])
        current_index = len(node_token_ids) + 1
        node_token_ids.append(token_id)
        node_depths.append(depth)
        parents.append(parent_index)
        child_maps.append({})
        child_maps[parent_index][token_id] = current_index

        if rank + 1 < topk:
            sibling_ranks = ranks[:-1] + (rank + 1,)
            sibling_log_weight = (
                log_weight
                - float(top_log_probs_rows[depth - 1][rank])
                + float(top_log_probs_rows[depth - 1][rank + 1])
            )
            heapq.heappush(
                heap,
                (
                    -sibling_log_weight,
                    sibling_ranks,
                    parent_index,
                    depth,
                    rank + 1,
                    sibling_log_weight,
                ),
            )

        if depth < depth_limit:
            child_ranks = ranks + (0,)
            child_log_weight = log_weight + float(top_log_probs_rows[depth][0])
            heapq.heappush(
                heap,
                (
                    -child_log_weight,
                    child_ranks,
                    current_index,
                    depth + 1,
                    0,
                    child_log_weight,
                ),
            )

    return DDTree(
        tuple(node_token_ids),
        tuple(node_depths),
        tuple(parents),
        tuple(child_maps),
    )


def target_owned_accepted_depth(
    child_maps: Sequence[dict[int, int]], labels: torch.Tensor
) -> int:
    """Follow the recorded target-greedy path from the target-owned root."""

    current_index = 0
    accepted_depth = 0
    for token_id in labels.to(device="cpu", dtype=torch.long).tolist():
        next_index = child_maps[current_index].get(int(token_id))
        if next_index is None:
            break
        current_index = next_index
        accepted_depth += 1
    return accepted_depth


def record_key(record: dict[str, Any]) -> tuple[str, str, int]:
    return (
        str(record["prompt_id"]),
        str(record["sample"]),
        int(record["start"]),
    )


def evaluate_pass(
    *,
    helpers: ModuleType,
    model: Any,
    embedding: torch.Tensor,
    lm_head: dict[str, torch.Tensor],
    anchors: list[Any],
    budgets: tuple[int, ...],
    args: argparse.Namespace,
    repeat_index: int,
    repeat_count: int,
) -> tuple[
    dict[int, list[dict[str, Any]]],
    list[dict[str, Any]],
    int,
]:
    model.eval()
    cache = helpers.SampleCache()
    records_by_budget: dict[int, list[dict[str, Any]]] = {
        budget: [] for budget in budgets
    }
    vanilla_records: list[dict[str, Any]] = []
    forward_count = 0
    with torch.inference_mode():
        for anchor_index, anchor in enumerate(anchors, start=1):
            target_hidden, noise_embedding, position_ids, labels = helpers.make_block(
                sample=cache.get(anchor.path),
                start=anchor.start,
                draft_tokens=args.draft_tokens,
                max_context=args.max_context,
                mask_token_id=model.mask_token_id,
                embedding=embedding,
                device=args.device,
            )
            logits = helpers.draft_logits(
                model=model,
                lm_head=lm_head,
                target_hidden=target_hidden,
                noise_embedding=noise_embedding,
                position_ids=position_ids,
                attention_mode="endpoint-mixed",
            )
            forward_count += 1
            if logits.shape[0] != args.draft_tokens:
                raise RuntimeError(
                    "Shared DFlash forward returned "
                    f"{logits.shape[0]} positions, expected {args.draft_tokens}"
                )
            log_probs = per_position_log_probabilities(logits)
            common = {
                "prompt_id": anchor.prompt_id,
                "family": anchor.family,
                "task": anchor.task,
                "variant": anchor.variant,
                "scenario": anchor.scenario,
                "sample": Path(anchor.path).name,
                "start": anchor.start,
            }
            vanilla_accepted = helpers.accepted_prefix(
                logits.argmax(dim=-1), labels
            )
            vanilla_records.append(
                {
                    **common,
                    "accepted_depth": vanilla_accepted,
                    "visible_depth": 1 + vanilla_accepted,
                    "tree_node_count": args.draft_tokens,
                    "tree_max_depth": args.draft_tokens,
                }
            )
            for budget in budgets:
                tree = build_ddtree_tree(log_probs, budget)
                accepted_depth = target_owned_accepted_depth(tree.child_maps, labels)
                records_by_budget[budget].append(
                    {
                        **common,
                        "accepted_depth": accepted_depth,
                        "visible_depth": 1 + accepted_depth,
                        "tree_node_count": len(tree.node_token_ids),
                        "tree_max_depth": max(tree.node_depths, default=0),
                    }
                )
            if args.progress_every and (
                anchor_index % args.progress_every == 0 or anchor_index == len(anchors)
            ):
                print(
                    f"repeat {repeat_index + 1}/{repeat_count}: "
                    f"anchors {anchor_index}/{len(anchors)}",
                    file=sys.stderr,
                    flush=True,
                )
    if forward_count != len(anchors):
        raise RuntimeError(
            f"Expected one DFlash forward per anchor, got {forward_count} "
            f"for {len(anchors)} anchors"
        )
    return records_by_budget, vanilla_records, forward_count


def depth_summary(
    records: Sequence[dict[str, Any]], draft_tokens: int
) -> dict[str, Any]:
    accepted = [int(record["accepted_depth"]) for record in records]
    visible = [int(record["visible_depth"]) for record in records]
    accepted_histogram = Counter(accepted)
    visible_histogram = Counter(visible)
    count = len(records)
    return {
        "anchors": count,
        "mean_accepted_depth": sum(accepted) / count,
        "mean_visible_depth": sum(visible) / count,
        "full_horizon_accept_rate": accepted_histogram[draft_tokens] / count,
        "histogram": {
            "accepted_depth": {
                str(depth): accepted_histogram[depth]
                for depth in range(draft_tokens + 1)
            },
            "visible_depth": {
                str(depth): visible_histogram[depth]
                for depth in range(1, draft_tokens + 2)
            },
        },
    }


def grouped_summaries(
    records: Sequence[dict[str, Any]], field: str, draft_tokens: int
) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[str(record[field])].append(record)
    return {
        name: depth_summary(rows, draft_tokens) for name, rows in sorted(groups.items())
    }


def aggregate_budget_runs(
    *,
    budget: int,
    runs: Sequence[list[dict[str, Any]]],
    draft_tokens: int,
) -> dict[str, Any]:
    if not runs:
        raise ValueError("At least one evaluation run is required")
    expected_keys = {record_key(record) for record in runs[0]}
    accepted_by_key: dict[tuple[str, str, int], list[int]] = defaultdict(list)
    tree_depth_by_key: dict[tuple[str, str, int], list[int]] = defaultdict(list)
    tree_nodes_by_key: dict[tuple[str, str, int], list[int]] = defaultdict(list)
    templates: dict[tuple[str, str, int], dict[str, Any]] = {}
    repeat_mean_visible_depth: list[float] = []

    for run in runs:
        keys = {record_key(record) for record in run}
        if keys != expected_keys or len(run) != len(expected_keys):
            raise RuntimeError("Repeated DDTree evaluation records did not align")
        repeat_mean_visible_depth.append(
            sum(int(record["visible_depth"]) for record in run) / len(run)
        )
        for record in run:
            key = record_key(record)
            accepted_by_key[key].append(int(record["accepted_depth"]))
            tree_depth_by_key[key].append(int(record["tree_max_depth"]))
            tree_nodes_by_key[key].append(int(record["tree_node_count"]))
            templates[key] = record

    records: list[dict[str, Any]] = []
    disagreement_anchors = 0
    tree_shape_disagreement_anchors = 0
    for key in sorted(expected_keys):
        accepted_values = accepted_by_key[key]
        tree_depth_values = tree_depth_by_key[key]
        tree_node_values = tree_nodes_by_key[key]
        accepted_depth = int(statistics.median(accepted_values))
        record = {
            name: value
            for name, value in templates[key].items()
            if name
            not in {
                "accepted_depth",
                "visible_depth",
                "tree_node_count",
                "tree_max_depth",
            }
        }
        record.update(
            {
                "accepted_depth": accepted_depth,
                "visible_depth": 1 + accepted_depth,
                "tree_node_count": int(statistics.median(tree_node_values)),
                "tree_max_depth": int(statistics.median(tree_depth_values)),
            }
        )
        if len(runs) > 1:
            record["repeat_accepted_depths"] = accepted_values
            record["repeat_visible_depths"] = [1 + value for value in accepted_values]
            record["repeat_tree_max_depths"] = tree_depth_values
        if len(set(accepted_values)) > 1:
            disagreement_anchors += 1
        if len(set(zip(tree_node_values, tree_depth_values))) > 1:
            tree_shape_disagreement_anchors += 1
        records.append(record)

    result = {
        "node_budget": budget,
        **depth_summary(records, draft_tokens),
        "mean_tree_node_count": sum(
            int(record["tree_node_count"]) for record in records
        )
        / len(records),
        "mean_tree_max_depth": sum(int(record["tree_max_depth"]) for record in records)
        / len(records),
        "evaluation_repeats": len(runs),
        "repeat_disagreement_anchors": disagreement_anchors,
        "repeat_disagreement_anchor_fraction": disagreement_anchors / len(records),
        "repeat_exact_match_all": disagreement_anchors == 0,
        "repeat_tree_shape_disagreement_anchors": (tree_shape_disagreement_anchors),
        "repeat_mean_visible_depth": repeat_mean_visible_depth,
        "per_family": grouped_summaries(records, "family", draft_tokens),
        "per_scenario": grouped_summaries(records, "scenario", draft_tokens),
        "records": records,
    }
    return result


def validate_args(args: argparse.Namespace) -> int:
    if args.draft_tokens <= 0:
        raise ValueError("--draft-tokens must be positive")
    if args.min_context <= 0:
        raise ValueError("--min-context must be positive")
    if args.max_context <= 0:
        raise ValueError("--max-context must be positive")
    if args.heldout_starts < 0:
        raise ValueError("--heldout-starts must be non-negative")
    if args.progress_every < 0:
        raise ValueError("--progress-every must be non-negative")
    repeats = 1 if args.deterministic_one_pass else args.eval_repeats
    if repeats < 1 or repeats % 2 == 0:
        raise ValueError(
            "--eval-repeats must be a positive odd integer unless "
            "--deterministic-one-pass is used"
        )
    return repeats


def configure_randomness(seed: int, deterministic_one_pass: bool) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if hasattr(torch, "xpu") and torch.xpu.is_available():
        torch.xpu.manual_seed_all(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if deterministic_one_pass:
        torch.use_deterministic_algorithms(True, warn_only=True)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repeats = validate_args(args)
    budgets = parse_node_budgets(args.node_budgets)
    configure_randomness(args.seed, args.deterministic_one_pass)

    helpers = load_training_helpers(args.train_script)
    raw_corpus_dirs = args.corpus_dirs or [DEFAULT_CORPUS]
    corpus_dirs = [resolve_corpus_dir(path) for path in raw_corpus_dirs]
    paths = helpers.sample_paths(corpus_dirs)
    anchors = helpers.collect_anchors(
        paths,
        draft_tokens=args.draft_tokens,
        min_context=args.min_context,
        limit=args.heldout_starts,
        seed=args.seed + 1,
    )
    anchors.sort(key=lambda anchor: (anchor.path, anchor.start))

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
    model, embedding, lm_head = helpers.load_runtime(runtime_args)

    runs_by_budget: dict[int, list[list[dict[str, Any]]]] = {
        budget: [] for budget in budgets
    }
    vanilla_runs: list[list[dict[str, Any]]] = []
    total_forward_count = 0
    for repeat_index in range(repeats):
        pass_records, vanilla_records, forward_count = evaluate_pass(
            helpers=helpers,
            model=model,
            embedding=embedding,
            lm_head=lm_head,
            anchors=anchors,
            budgets=budgets,
            args=args,
            repeat_index=repeat_index,
            repeat_count=repeats,
        )
        total_forward_count += forward_count
        vanilla_runs.append(vanilla_records)
        for budget in budgets:
            runs_by_budget[budget].append(pass_records[budget])

    budget_results = {
        str(budget): aggregate_budget_runs(
            budget=budget,
            runs=runs_by_budget[budget],
            draft_tokens=args.draft_tokens,
        )
        for budget in budgets
    }
    vanilla_result = aggregate_budget_runs(
        budget=args.draft_tokens,
        runs=vanilla_runs,
        draft_tokens=args.draft_tokens,
    )
    vanilla_result["method"] = "single greedy DFlash trajectory"
    vanilla_result["node_budget"] = None
    result = {
        "classification": CLASSIFICATION,
        "diagnostic": True,
        "offline": True,
        "throughput_benchmark": False,
        "localmaxxing_eligible": False,
        "interpretation": (
            "Target-owned trace acceptance only; not endpoint throughput, "
            "quality, or LocalMaxxing evidence."
        ),
        "semantics": {
            "attention": "endpoint-mixed",
            "target_lm_head": (
                "endpoint INT8 weights with BF16 per-output-channel scales"
            ),
            "labels": "target-owned sampled_next_token_ids from each trace",
            "accepted_depth": (
                "target-owned continuation nodes present along the DDTree path"
            ),
            "visible_depth": "one target-owned root plus accepted_depth",
            "tree_builder": "liranringel/ddtree best-first heap expansion",
            "tree_builder_reference": DDTREE_REFERENCE,
            "vanilla_baseline": (
                "per-position greedy argmax from the same DFlash forward"
            ),
        },
        "draft_dir": os.path.realpath(args.draft_dir),
        "target_model": os.path.realpath(args.target_model),
        "corpus_dirs": [os.path.realpath(path) for path in corpus_dirs],
        "train_script": os.path.realpath(args.train_script),
        "dflash_source": os.path.realpath(args.dflash_source),
        "device": args.device,
        "seed": args.seed,
        "draft_tokens": args.draft_tokens,
        "attention_mode": "endpoint-mixed",
        "lm_head_mode": "int8-ste",
        "node_budgets": list(budgets),
        "min_context": args.min_context,
        "max_context": args.max_context,
        "heldout_anchor_count": len(anchors),
        "evaluation_repeats": repeats,
        "deterministic_one_pass": bool(args.deterministic_one_pass),
        "dflash_forwards_per_anchor_per_repeat": 1,
        "budgets_reuse_each_anchor_forward": True,
        "total_dflash_forwards": total_forward_count,
        "vanilla": vanilla_result,
        "budgets": budget_results,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        output_path = Path(args.out).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
