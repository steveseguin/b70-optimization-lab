#!/usr/bin/env python3
"""Audit DFlash adaptation inputs and emit an exact-Q4 capture plan.

This is an identity gate.  It deliberately refuses to reinterpret AutoRound
target features as active GGUF Q4_0 target features.  The emitted plan can be
consumed by ``collect-qwen27-dflash-q4-training-corpus.py`` after a native
capture session implements the declared guarded trace contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = Path(
    "/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/"
    "qwen27-dflash-aux-v8-corrected5-v6b-4gpu-20260710T040000Z"
)
DEFAULT_SUITE = (
    ROOT
    / "experiments/qwen36-27b-autoround-int4-b70/eagle-chat-corpus-v6b-suite.json"
)
DEFAULT_BENCHMARK = (
    ROOT / "repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json"
)
DEFAULT_TARGET = (
    "/mnt/usb-models/models/qwen36-27b-mtp-gguf/Qwen3.6-27B-Q4_0.gguf"
)
DEFAULT_DRAFT = (
    "/mnt/usb-models/models/qwen36-27b-dflash-native/"
    "Qwen3.6-27B-DFlash-Q8_0.gguf"
)
DEFAULT_TARGET_SHA256 = (
    "20c9c45d4d25b492b82117960b5f715ef9daff75e4e14c4fb878fa3793fb379a"
)
DEFAULT_DRAFT_SHA256 = (
    "c37b84724fa58cc5c6b545d8b96f8617a8c3bd7f018bf608feef4d3460e0575e"
)
NATIVE_SOURCE = Path("/home/steve/src/llama.cpp/common/speculative.cpp")
RUNTIME_TREE = Path("/home/steve/src/llama.cpp")
TARGET_LAYERS = [2, 17, 32, 47, 62]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit the retained AutoRound DFlash corpus against the active "
            "GGUF Q4_0 product and write a guarded native capture plan."
        )
    )
    parser.add_argument("--existing-corpus-root", default=str(DEFAULT_CORPUS))
    parser.add_argument("--suite", default=str(DEFAULT_SUITE))
    parser.add_argument("--benchmark-suite", default=str(DEFAULT_BENCHMARK))
    parser.add_argument("--target-model", default=DEFAULT_TARGET)
    parser.add_argument("--target-model-sha256", default=DEFAULT_TARGET_SHA256)
    parser.add_argument("--draft-model", default=DEFAULT_DRAFT)
    parser.add_argument("--draft-model-sha256", default=DEFAULT_DRAFT_SHA256)
    parser.add_argument("--runtime-tree", default=str(RUNTIME_TREE))
    parser.add_argument("--native-source", default=str(NATIVE_SOURCE))
    parser.add_argument("--out", required=True)
    return parser.parse_args(argv)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def prompt_text(row: dict[str, Any]) -> str:
    if row.get("prompt"):
        return str(row["prompt"])
    return json.dumps(row.get("messages") or [], sort_keys=True)


def prompt_sha256(row: dict[str, Any]) -> str:
    return hashlib.sha256(prompt_text(row).encode("utf-8")).hexdigest()


def load_suite(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {"suite_id": path.stem}, payload
    rows = payload.get("prompts")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path}: missing non-empty prompts list")
    return {key: value for key, value in payload.items() if key != "prompts"}, rows


def run_git(runtime_tree: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(runtime_tree), *args], text=True
    ).strip()


def runtime_identity(runtime_tree: Path) -> dict[str, Any]:
    commit = run_git(runtime_tree, "rev-parse", "HEAD")
    diff = subprocess.check_output(
        ["git", "-C", str(runtime_tree), "diff", "--binary"]
    )
    return {
        "tree": str(runtime_tree.resolve()),
        "commit": commit,
        "dirty": bool(diff),
        "dirty_patch_sha256": hashlib.sha256(diff).hexdigest(),
    }


def collector_identities(corpus_root: Path) -> tuple[list[dict[str, Any]], set[str]]:
    summaries = sorted(corpus_root.glob("shard-*/collector-summary.json"))
    if not summaries:
        raise FileNotFoundError(f"No collector summaries under {corpus_root}")
    rows: list[dict[str, Any]] = []
    models: set[str] = set()
    for path in summaries:
        summary = json.loads(path.read_text(encoding="utf-8"))
        model = str(summary.get("model") or "")
        models.add(model)
        rows.append(
            {
                "path": str(path.resolve()),
                "model": model,
                "tokenizer": summary.get("tokenizer"),
                "api_mode": summary.get("api_mode"),
                "request_extra_json": summary.get("request_extra_json"),
                "start_index": summary.get("start_index"),
                "num_prompts": summary.get("num_prompts"),
                "families": summary.get("families"),
            }
        )
    return rows, models


def family_split(
    suite_rows: list[dict[str, Any]], collector_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    train_families = {
        str(family)
        for collector in collector_rows[:3]
        for family in (collector.get("families") or [])
    }
    heldout_families = {
        str(family) for family in (collector_rows[3].get("families") or [])
    }
    overlap = sorted(train_families & heldout_families)
    train = [row for row in suite_rows if str(row.get("family")) in train_families]
    heldout = [
        row for row in suite_rows if str(row.get("family")) in heldout_families
    ]
    return {
        "unit": "prompt family; task and variant remain nested within family",
        "train_families": sorted(train_families),
        "heldout_families": sorted(heldout_families),
        "family_overlap": overlap,
        "train_prompts": len(train),
        "heldout_prompts": len(heldout),
        "all_suite_prompts_assigned": len(train) + len(heldout) == len(suite_rows),
        "train_prompt_sha256s": sorted(prompt_sha256(row) for row in train),
        "heldout_prompt_sha256s": sorted(prompt_sha256(row) for row in heldout),
    }


def hook_inventory(native_source: Path) -> dict[str, Any]:
    text = native_source.read_text(encoding="utf-8")
    required = "LLAMA_DFLASH_TARGET_TRACE_CAPTURE_DIR"
    existing_lmhead = "LLAMA_DFLASH_LMHEAD_CAPTURE"
    return {
        "source": str(native_source.resolve()),
        "required_hook": required,
        "required_hook_present": required in text,
        "existing_lmhead_hook_present": existing_lmhead in text,
        "existing_lmhead_hook_is_sufficient": False,
        "reason": (
            "The LM-head hook captures final DFlash decoder activations only. "
            "Training needs target layer-input rows, linear target token IDs, "
            "positions, and prompt/generation boundaries."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    corpus_root = Path(args.existing_corpus_root).expanduser()
    suite_path = Path(args.suite).expanduser()
    benchmark_path = Path(args.benchmark_suite).expanduser()
    runtime_tree = Path(args.runtime_tree).expanduser()
    native_source = Path(args.native_source).expanduser()
    suite_meta, suite_rows = load_suite(suite_path)
    benchmark_meta, benchmark_rows = load_suite(benchmark_path)
    collector_rows, collector_models = collector_identities(corpus_root)
    split = family_split(suite_rows, collector_rows)
    suite_hashes = {prompt_sha256(row) for row in suite_rows}
    benchmark_hashes = {prompt_sha256(row) for row in benchmark_rows}
    overlap = sorted(suite_hashes & benchmark_hashes)
    hooks = hook_inventory(native_source)
    active_runtime = runtime_identity(runtime_tree)

    exact_target_match = collector_models == {"qwen36-27b-mtp-gguf-q4_0"}
    ready = bool(
        exact_target_match
        and not overlap
        and not split["family_overlap"]
        and split["all_suite_prompts_assigned"]
        and hooks["required_hook_present"]
    )
    result = {
        "schema": "qwen27_dflash_q4_adaptation_capture_plan_v1",
        "classification": (
            "diagnostic_capture_plan_not_training_not_endpoint_not_localmaxxing"
        ),
        "status": "ready_for_capture" if ready else "blocked_before_training",
        "training_authorized": ready,
        "decision": (
            "Do not train on the retained corpus: its target features and labels "
            "come from Webhie AutoRound INT4, not the active GGUF Q4_0 target. "
            "Install the guarded native target-feature hook in a non-protected "
            "worktree, then capture exact linear Q4 target traces."
        ),
        "existing_corpus": {
            "root": str(corpus_root.resolve()),
            "format": "qwen36_eagle_sequence_v2",
            "sample_prompts": len(suite_rows),
            "collector_models": sorted(collector_models),
            "collectors": collector_rows,
            "exact_active_target_match": exact_target_match,
            "no_thinking_request": {
                "chat_template_kwargs": {"enable_thinking": False}
            },
            "suitable_for": (
                "AutoRound-only exploratory replay and architectural ranking"
            ),
            "not_suitable_for": (
                "active GGUF Q4_0 adaptation gate or native Q8 draft merge"
            ),
        },
        "active_product": {
            "target_model": os.path.realpath(args.target_model),
            "target_quantization": "Q4_0",
            "target_model_sha256": args.target_model_sha256,
            "draft_model": os.path.realpath(args.draft_model),
            "draft_quantization": "Q8_0",
            "draft_model_sha256": args.draft_model_sha256,
            "draft_kv": "f16",
            "target_kv": "q8_0",
            "reasoning": "off",
            "runtime": active_runtime,
        },
        "prompt_policy": {
            "suite": str(suite_path.resolve()),
            "suite_sha256": sha256_file(suite_path),
            "suite_id": suite_meta.get("suite_id"),
            "suite_prompts": len(suite_rows),
            "benchmark_suite": str(benchmark_path.resolve()),
            "benchmark_suite_sha256": sha256_file(benchmark_path),
            "benchmark_suite_id": benchmark_meta.get("suite_id"),
            "benchmark_prompts": len(benchmark_rows),
            "exact_prompt_hash_overlap": overlap,
            "benchmark_leakage_gate_passed": not overlap,
            "split": split,
            "heldout_warning": (
                "The v6b heldout families were adaptively inspected in prior "
                "AutoRound screens. They are valid for a bounded screen, not a "
                "final confirmatory claim."
            ),
        },
        "adapter_screen": {
            "selected_scope": "layer-position-bias",
            "selection_reason": (
                "Smallest existing additive scope with a prior repeatable positive "
                "signal; target-fusion has only 25 parameters but already closed "
                "near +0.023 visible token."
            ),
            "block_width": 6,
            "trainable_parameters": 5 * 6 * 5120,
            "initialization": "zero; exact source checkpoint at step zero",
            "prior_autoround_result": {
                "block_width": 5,
                "best_visible_token_delta": 0.06640391793462934,
                "learning_rate": 0.0003,
                "steps": 4000,
            },
            "smallest_lora_alternative": {
                "scope": "layer-position-lora",
                "rank": 32,
                "prior_block_width": 5,
                "prior_trainable_parameters_approx": 8_200_000,
                "prior_visible_token_delta": 0.1006,
            },
            "hard_gate": {
                "minimum_mean_accepted_drafts_B6": 4.0,
                "minimum_mean_visible_tokens_B6": 5.0,
                "early_stop": (
                    "Stop after the first two heldout checkpoints if the candidate "
                    "is below 3.5 visible tokens and the second checkpoint improves "
                    "by less than 0.10; do not expand scope on mismatched traces."
                ),
            },
        },
        "native_capture": {
            "hook_inventory": hooks,
            "capture_mode": "linear_target_no_speculation",
            "required_server_contract": {
                "reasoning": "off",
                "temperature": 0,
                "ctx_checkpoints": 0,
                "prompt_cache": "disabled",
                "spec_type": "draft-dflash",
                "spec_draft_n_max": 0,
                "spec_draft_n_min": 0,
                "spec_draft_p_min": 0.0,
                "spec_draft_type_k": "f16",
                "spec_draft_type_v": "f16",
                "target_layer_input_ids": TARGET_LAYERS,
            },
            "why_n_max_zero": (
                "The DFlash process hook still extracts target layer inputs, while "
                "every target decode row follows the actual linear greedy target "
                "path instead of a speculative candidate path."
            ),
            "required_trace_schema": {
                "session": "qwen27_dflash_native_capture_session_v1",
                "request": "qwen27_dflash_native_target_trace_v1",
                "per_request_fields": [
                    "prompt_sha256",
                    "target_model_sha256",
                    "runtime_commit",
                    "runtime_dirty_patch_sha256",
                    "target_layer_input_ids",
                    "input_token_ids",
                    "sampled_next_token_ids",
                    "positions",
                    "num_prompt_tokens",
                    "aux_hidden_states_f32_or_bf16",
                    "payload_sha256",
                ],
                "required_feature_shape": ["tokens", 5, 5120],
            },
            "collector": str(
                (ROOT / "scripts/collect-qwen27-dflash-q4-training-corpus.py").resolve()
            ),
        },
        "blockers": [
            "retained corpus target is AutoRound INT4, not active GGUF Q4_0",
            (
                "native target-feature capture hook is absent from the protected "
                "runtime; existing LM-head hook is insufficient"
            ),
        ],
        "localmaxxing_eligible": False,
    }
    output_path = Path(args.out).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output_path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
