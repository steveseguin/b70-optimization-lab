#!/usr/bin/env python3
"""Offline B=6/9/16 DFlash block-width and attention-contract oracle.

The input is a corrected ``qwen36_eagle_sequence_v2`` corpus containing
target-owned continuations and the five DFlash feature taps.  Every requested
width is evaluated at the same sampled anchors, using the largest width when
selecting eligible anchors.  This lets the report distinguish truncation from
the real bidirectional-width effect: changing the number of mask rows can
change even rows 1..5.

This diagnostic is deliberately not an endpoint throughput benchmark and is
never LocalMaxxing eligible.  It does not alter prompts or target outputs.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import random
import sys
import time
from collections import Counter, defaultdict
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
DEFAULT_CORPUS_ROOT = (
    "/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/"
    "qwen27-dflash-aux-v8-corrected5-v6b-4gpu-20260710T040000Z"
)
DEFAULT_NATIVE_FIXTURE_MANIFEST = (
    SCRIPT_DIR.parent / "data/qwen27-q6k-m6-top1-real-fixture-20260713.json"
)
CLASSIFICATION = (
    "diagnostic_offline_dflash_width_oracle_not_throughput_not_localmaxxing"
)
ATTENTION_MODES = ("public-noncausal", "endpoint-mixed")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare source-BF16 DFlash logits and target-owned acceptance at "
            "B=6/9/16 on identical corrected-trace anchors."
        )
    )
    parser.add_argument(
        "--corpus-dir",
        action="append",
        default=[],
        help=(
            "Direct qwen36_eagle_sequence_v2 directory, shard directory, or "
            "corrected four-shard corpus root. May repeat."
        ),
    )
    parser.add_argument("--draft-dir", default=DEFAULT_DRAFT)
    parser.add_argument("--target-model", default=DEFAULT_TARGET)
    parser.add_argument("--dflash-source", default="/home/steve/src/dflash")
    parser.add_argument("--train-script", default=str(DEFAULT_TRAIN_SCRIPT))
    parser.add_argument(
        "--widths",
        default="6,9,16",
        help="Comma-separated total block widths (one seed plus mask rows).",
    )
    parser.add_argument(
        "--attention-modes",
        default=",".join(ATTENTION_MODES),
        help="Comma-separated source attention modes.",
    )
    parser.add_argument("--min-context", type=int, default=16)
    parser.add_argument("--max-context", type=int, default=160)
    parser.add_argument(
        "--anchors",
        type=int,
        default=128,
        help="Deterministically sampled common anchors; 0 uses all anchors.",
    )
    parser.add_argument("--seed", type=int, default=20260713)
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--progress-every", type=int, default=8)
    parser.add_argument(
        "--native-fixture-manifest",
        default=str(DEFAULT_NATIVE_FIXTURE_MANIFEST),
        help=(
            "Optional retained native-Q8 B=6 fixture manifest. It is recorded "
            "as unmatched evidence only; its prompt is not mixed into the oracle."
        ),
    )
    parser.add_argument("--out", required=True)
    return parser.parse_args(argv)


def parse_widths(value: str) -> tuple[int, ...]:
    try:
        widths = tuple(dict.fromkeys(int(piece.strip()) for piece in value.split(",")))
    except ValueError as exc:
        raise ValueError("--widths must be comma-separated integers") from exc
    if not widths or any(width < 2 for width in widths):
        raise ValueError("Every block width must be at least two")
    return tuple(sorted(widths))


def parse_attention_modes(value: str) -> tuple[str, ...]:
    modes = tuple(dict.fromkeys(piece.strip() for piece in value.split(",")))
    if not modes or any(mode not in ATTENTION_MODES for mode in modes):
        raise ValueError(
            "--attention-modes must contain only " + ",".join(ATTENTION_MODES)
        )
    return modes


def load_training_helpers(path: str) -> ModuleType:
    helper_path = Path(path).expanduser().resolve()
    if not helper_path.is_file():
        raise FileNotFoundError(f"Training helper does not exist: {helper_path}")
    module_name = "_qwen27_dflash_width_oracle_helpers"
    spec = importlib.util.spec_from_file_location(module_name, helper_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load training helper: {helper_path}")
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
        raise AttributeError(f"Training helper missing shared API: {missing}")
    return module


def resolve_corpus_dirs(values: Sequence[str]) -> list[str]:
    resolved: list[str] = []
    for raw in values or [DEFAULT_CORPUS_ROOT]:
        path = Path(raw).expanduser()
        direct_candidates = (path, path / "dataset")
        direct = next(
            (
                candidate
                for candidate in direct_candidates
                if candidate.is_dir() and next(candidate.glob("*.pt"), None)
            ),
            None,
        )
        if direct is not None:
            resolved.append(str(direct.resolve()))
            continue
        shards = sorted(path.glob("shard-*/dataset"))
        valid_shards = [
            shard
            for shard in shards
            if shard.is_dir() and next(shard.glob("*.pt"), None)
        ]
        if not valid_shards:
            raise FileNotFoundError(f"No sequence samples found under {path}")
        resolved.extend(str(shard.resolve()) for shard in valid_shards)
    return list(dict.fromkeys(resolved))


class DeltaAccumulator:
    """Streaming full-logit and top-1 comparison without retaining logits."""

    def __init__(self, rows: int) -> None:
        self.rows = rows
        self.comparisons = 0
        self.values = 0
        self.abs_sum = 0.0
        self.square_sum = 0.0
        self.max_abs = 0.0
        self.row_top1_matches = [0] * rows

    def add(self, reference: torch.Tensor, candidate: torch.Tensor) -> None:
        rows = min(self.rows, reference.shape[0], candidate.shape[0])
        if rows != self.rows or reference.shape[1] != candidate.shape[1]:
            raise ValueError(
                f"Cannot compare {tuple(reference.shape)} and "
                f"{tuple(candidate.shape)} for {self.rows} rows"
            )
        ref = reference[:rows].float()
        cand = candidate[:rows].float()
        delta = cand - ref
        self.comparisons += 1
        self.values += delta.numel()
        self.abs_sum += float(delta.abs().sum().item())
        self.square_sum += float(delta.square().sum().item())
        self.max_abs = max(self.max_abs, float(delta.abs().max().item()))
        matches = ref.argmax(-1).eq(cand.argmax(-1)).to("cpu").tolist()
        for index, matched in enumerate(matches):
            self.row_top1_matches[index] += int(matched)

    def summary(self) -> dict[str, Any]:
        denominator = max(1, self.values)
        comparisons = max(1, self.comparisons)
        return {
            "anchor_comparisons": self.comparisons,
            "rows_compared": self.rows,
            "logit_values_compared": self.values,
            "mean_abs_logit_delta": self.abs_sum / denominator,
            "rms_logit_delta": math.sqrt(self.square_sum / denominator),
            "max_abs_logit_delta": self.max_abs,
            "top1_agreement_by_row": [
                count / comparisons for count in self.row_top1_matches
            ],
            "top1_agreement_all_rows": (
                sum(self.row_top1_matches) / (comparisons * self.rows)
            ),
        }


def metric_key(mode: str, width: int) -> str:
    return f"{mode}::B{width}"


def summarize_records(
    records: list[dict[str, Any]], draft_tokens: int
) -> dict[str, Any]:
    prefixes = [int(record["accepted_drafts"]) for record in records]
    histogram = Counter(prefixes)
    by_family: dict[str, list[int]] = defaultdict(list)
    for record, prefix in zip(records, prefixes):
        by_family[str(record["family"])].append(prefix)
    alive = [sum(prefix >= index for prefix in prefixes) for index in range(draft_tokens)]
    correct = [sum(prefix > index for prefix in prefixes) for index in range(draft_tokens)]
    mean = sum(prefixes) / len(prefixes)
    return {
        "anchors": len(records),
        "draft_tokens": draft_tokens,
        "mean_accepted_drafts": mean,
        "visible_tokens_per_step": 1.0 + mean,
        "full_accept_rate": histogram[draft_tokens] / len(records),
        "histogram": {
            str(index): histogram[index] for index in range(draft_tokens + 1)
        },
        "conditional_exact_by_position": [
            correct[index] / alive[index] if alive[index] else 0.0
            for index in range(draft_tokens)
        ],
        "alive_rows_by_position": alive,
        "per_family": {
            family: {
                "anchors": len(values),
                "mean_accepted_drafts": sum(values) / len(values),
            }
            for family, values in sorted(by_family.items())
        },
    }


def paired_effect(
    reference: list[dict[str, Any]], candidate: list[dict[str, Any]]
) -> dict[str, Any]:
    if len(reference) != len(candidate) or not reference:
        raise ValueError("Paired oracle records must have equal non-zero lengths")
    deltas: list[int] = []
    changed_id_rows = 0
    changed_id_anchors = 0
    for left, right in zip(reference, candidate):
        left_key = (left["sample"], int(left["start"]))
        right_key = (right["sample"], int(right["start"]))
        if left_key != right_key:
            raise RuntimeError(f"Paired oracle records do not align: {left_key} != {right_key}")
        deltas.append(
            int(right["accepted_drafts"]) - int(left["accepted_drafts"])
        )
        id_changes = sum(
            int(left_id) != int(right_id)
            for left_id, right_id in zip(
                left["first_five_predicted_ids"],
                right["first_five_predicted_ids"],
            )
        )
        changed_id_rows += id_changes
        changed_id_anchors += int(id_changes > 0)
    mean_delta = sum(deltas) / len(deltas)
    if len(deltas) > 1:
        variance = sum((delta - mean_delta) ** 2 for delta in deltas) / (
            len(deltas) - 1
        )
        standard_error = math.sqrt(variance / len(deltas))
    else:
        standard_error = 0.0
    return {
        "anchors": len(deltas),
        "mean_accepted_drafts_delta": mean_delta,
        "mean_visible_tokens_delta": mean_delta,
        "paired_standard_error": standard_error,
        "normal_95pct_interval": [
            mean_delta - 1.96 * standard_error,
            mean_delta + 1.96 * standard_error,
        ],
        "acceptance_changed_anchors": sum(delta != 0 for delta in deltas),
        "acceptance_improved_anchors": sum(delta > 0 for delta in deltas),
        "acceptance_worsened_anchors": sum(delta < 0 for delta in deltas),
        "first_five_id_changed_anchors": changed_id_anchors,
        "first_five_id_changed_rows": changed_id_rows,
    }


def load_native_fixture(path: str) -> dict[str, Any]:
    if not path:
        return {"status": "not_requested"}
    manifest_path = Path(path).expanduser()
    if not manifest_path.is_file():
        return {
            "status": "manifest_missing",
            "manifest": str(manifest_path),
        }
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    identity = manifest.get("identity", {})
    reference = manifest.get("production_reference", [])
    return {
        "status": "retained_unmatched_B6_only",
        "interpretation": (
            "This native Q8/F16-KV fixture is from a different prompt and "
            "target runtime. Its IDs are retained as implementation evidence, "
            "not compared numerically with the disjoint oracle anchors. No "
            "same-trace native B=9/B=16 artifacts existed at evaluation time."
        ),
        "manifest": str(manifest_path.resolve()),
        "fixture": manifest.get("fixture", {}),
        "identity": identity,
        "first_five_ids": [int(row["argmax_id"]) for row in reference[:5]],
    }


def anchor_set_sha256(anchors: Sequence[Any]) -> str:
    digest = hashlib.sha256()
    for anchor in anchors:
        digest.update(os.path.realpath(anchor.path).encode())
        digest.update(b"\0")
        digest.update(str(anchor.start).encode())
        digest.update(b"\0")
    return digest.hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    widths = parse_widths(args.widths)
    attention_modes = parse_attention_modes(args.attention_modes)
    if args.anchors < 0:
        raise ValueError("--anchors must be non-negative")
    if args.max_context < args.min_context:
        raise ValueError("--max-context must be >= --min-context")
    random.seed(args.seed)
    torch.manual_seed(args.seed)

    helpers = load_training_helpers(args.train_script)
    corpus_dirs = resolve_corpus_dirs(args.corpus_dir)
    paths = helpers.sample_paths(corpus_dirs)
    max_draft_tokens = max(widths) - 1
    anchors = helpers.collect_anchors(
        paths,
        draft_tokens=max_draft_tokens,
        min_context=args.min_context,
        limit=args.anchors,
        seed=args.seed,
    )
    anchors.sort(key=lambda anchor: (anchor.path, anchor.start))

    runtime_args = SimpleNamespace(
        dflash_source=args.dflash_source,
        draft_dir=args.draft_dir,
        target_model=args.target_model,
        draft_tokens=max_draft_tokens,
        train_scope="fc",
        position_rank=64,
        resume_adapter="",
        lm_head_mode="bf16",
        device=args.device,
    )
    model, embedding, lm_head = helpers.load_runtime(runtime_args)
    model.eval()
    cache = helpers.SampleCache()
    records_by_key: dict[str, list[dict[str, Any]]] = {
        metric_key(mode, width): []
        for mode in attention_modes
        for width in widths
    }
    width_deltas: dict[str, DeltaAccumulator] = {}
    base_width = min(widths)
    common_rows = base_width - 1
    for mode in attention_modes:
        for width in widths:
            if width != base_width:
                width_deltas[f"{mode}::B{base_width}_vs_B{width}"] = (
                    DeltaAccumulator(common_rows)
                )
    attention_deltas = {
        f"public-noncausal_vs_endpoint-mixed::B{width}": DeltaAccumulator(width - 1)
        for width in widths
        if set(ATTENTION_MODES).issubset(attention_modes)
    }

    started = time.perf_counter()
    with torch.inference_mode():
        for anchor_index, anchor in enumerate(anchors, start=1):
            sample = cache.get(anchor.path)
            prompt_sha256 = str(sample.get("prompt_sha256") or "")
            logits_by_key: dict[str, torch.Tensor] = {}
            for width in widths:
                draft_tokens = width - 1
                target_hidden, noise_embedding, position_ids, labels = (
                    helpers.make_block(
                        sample=sample,
                        start=anchor.start,
                        draft_tokens=draft_tokens,
                        max_context=args.max_context,
                        mask_token_id=model.mask_token_id,
                        embedding=embedding,
                        device=args.device,
                    )
                )
                labels_cpu = labels.to(device="cpu", dtype=torch.long)
                for mode in attention_modes:
                    logits = helpers.draft_logits(
                        model=model,
                        lm_head=lm_head,
                        target_hidden=target_hidden,
                        noise_embedding=noise_embedding,
                        position_ids=position_ids,
                        attention_mode=mode,
                    )
                    if tuple(logits.shape[:1]) != (draft_tokens,):
                        raise RuntimeError(
                            f"{mode} B={width} returned logits {tuple(logits.shape)}"
                        )
                    prediction = logits.argmax(-1).to(device="cpu", dtype=torch.long)
                    accepted = helpers.accepted_prefix(prediction, labels_cpu)
                    key = metric_key(mode, width)
                    logits_by_key[key] = logits
                    records_by_key[key].append(
                        {
                            "prompt_id": anchor.prompt_id,
                            "prompt_sha256": prompt_sha256,
                            "family": anchor.family,
                            "task": anchor.task,
                            "variant": anchor.variant,
                            "scenario": anchor.scenario,
                            "sample": Path(anchor.path).name,
                            "start": anchor.start,
                            "block_width": width,
                            "accepted_drafts": int(accepted),
                            "first_five_predicted_ids": prediction[:5].tolist(),
                            "first_five_target_ids": labels_cpu[:5].tolist(),
                            "first_five_exact": prediction[:5].eq(labels_cpu[:5]).tolist(),
                        }
                    )

            for mode in attention_modes:
                reference = logits_by_key[metric_key(mode, base_width)]
                for width in widths:
                    if width == base_width:
                        continue
                    accumulator = width_deltas[
                        f"{mode}::B{base_width}_vs_B{width}"
                    ]
                    accumulator.add(reference, logits_by_key[metric_key(mode, width)])
            if set(ATTENTION_MODES).issubset(attention_modes):
                for width in widths:
                    attention_deltas[
                        f"public-noncausal_vs_endpoint-mixed::B{width}"
                    ].add(
                        logits_by_key[metric_key("public-noncausal", width)],
                        logits_by_key[metric_key("endpoint-mixed", width)],
                    )
            if args.progress_every and (
                anchor_index % args.progress_every == 0
                or anchor_index == len(anchors)
            ):
                elapsed = time.perf_counter() - started
                print(
                    f"width-oracle anchors={anchor_index}/{len(anchors)} "
                    f"elapsed_s={elapsed:.1f}",
                    file=sys.stderr,
                    flush=True,
                )

    elapsed = time.perf_counter() - started
    metrics = {
        key: summarize_records(records, int(key.rsplit("B", 1)[1]) - 1)
        for key, records in records_by_key.items()
    }
    paired_acceptance_effects: dict[str, dict[str, Any]] = {}
    for mode in attention_modes:
        reference = records_by_key[metric_key(mode, base_width)]
        for width in widths:
            if width == base_width:
                continue
            key = f"{mode}::B{base_width}_vs_B{width}"
            paired_acceptance_effects[key] = paired_effect(
                reference, records_by_key[metric_key(mode, width)]
            )
    if set(ATTENTION_MODES).issubset(attention_modes):
        for width in widths:
            key = f"public-noncausal_vs_endpoint-mixed::B{width}"
            paired_acceptance_effects[key] = paired_effect(
                records_by_key[metric_key("public-noncausal", width)],
                records_by_key[metric_key("endpoint-mixed", width)],
            )
    result = {
        "classification": CLASSIFICATION,
        "diagnostic": True,
        "offline": True,
        "throughput_benchmark": False,
        "localmaxxing_eligible": False,
        "interpretation": (
            "Source-checkpoint block logits and acceptance against retained "
            "target-owned continuations. This is not endpoint speed or quality evidence."
        ),
        "corpus_contract": {
            "format": "qwen36_eagle_sequence_v2",
            "feature_taps": "source post-layer [1,16,31,46,61]",
            "feature_shape_per_token": [5, 5120],
            "labels": "target-owned sampled_next_token_ids",
            "prompt_policy": "retained disjoint generated corpus; no prompt mutation",
            "corpus_dirs": corpus_dirs,
            "sample_files": len(paths),
        },
        "source_runtime": {
            "draft_dir": os.path.realpath(args.draft_dir),
            "draft_weight_dtype": "bfloat16",
            "target_model_for_embedding_and_lm_head": os.path.realpath(
                args.target_model
            ),
            "lm_head_mode": "bf16",
            "dflash_source": os.path.realpath(args.dflash_source),
            "attention_modes": list(attention_modes),
            "device": args.device,
        },
        "widths": list(widths),
        "seed": args.seed,
        "min_context": args.min_context,
        "max_context": args.max_context,
        "anchor_count": len(anchors),
        "anchor_set_sha256": anchor_set_sha256(anchors),
        "common_anchor_selection_width": max(widths),
        "elapsed_s": elapsed,
        "dflash_forwards": len(anchors) * len(widths) * len(attention_modes),
        "metrics": metrics,
        "paired_acceptance_effects": paired_acceptance_effects,
        "width_effect_first_rows": {
            key: accumulator.summary()
            for key, accumulator in width_deltas.items()
        },
        "attention_contract_effect": {
            key: accumulator.summary()
            for key, accumulator in attention_deltas.items()
        },
        "records": records_by_key,
        "native_q8_f16_kv_evidence": load_native_fixture(
            args.native_fixture_manifest
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output_path = Path(args.out).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
