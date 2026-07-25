#!/usr/bin/env python3
"""Phase 0 cycle-attribution arm: record config, real cold suite, 512 tokens.

Diagnostic only. Produces cycle attribution, never a throughput claim. Each
prompt is a separate single generation on a cold engine with prefix caching
disabled; `cached_tokens` is asserted zero for every prompt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

TARGET = Path("/mnt/fast-ai/llm-models/laguna-s-2.1/int4")
DRAFT = Path("/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4")
TARGET_REVISION = "4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb"
DRAFT_REVISION = "5e07c246915c86dc6920fead03d019989224f2ba"
SUITE = Path(
    "/home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/"
    "realistic-suite-v1.json"
)
MAX_TOKENS = 512


def die(message: str) -> None:
    raise SystemExit(f"Laguna phase0 attribution arm: {message}")


def load_prompts() -> list[str]:
    suite = json.loads(SUITE.read_text())
    if suite.get("suite_id") != "laguna-s-2.1-realistic-cold-v1":
        die("suite identity drift")
    prompts = suite["prompts"]
    if not isinstance(prompts, list) or len(prompts) != 13:
        die("suite must contain the fixed 13 real cold prompts")
    texts: list[str] = []
    for entry in prompts:
        text = entry["prompt"] if isinstance(entry, dict) else entry
        if not isinstance(text, str) or not text.strip():
            die("empty or non-text prompt")
        texts.append(text)
    if len({hashlib.sha256(t.encode()).hexdigest() for t in texts}) != 13:
        die("prompts are not unique")
    return texts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        die("output already exists")

    if os.environ.get("VLLM_XPU_LAGUNA_CYCLE_ATTRIBUTION_ROOT") is None:
        die("attribution root is not armed")

    prompts = load_prompts()

    from vllm import LLM, SamplingParams

    llm = LLM(
        model=str(TARGET),
        revision=TARGET_REVISION,
        tokenizer=str(TARGET),
        tokenizer_revision=TARGET_REVISION,
        trust_remote_code=True,
        dtype="bfloat16",
        tensor_parallel_size=4,
        data_parallel_size=1,
        pipeline_parallel_size=1,
        distributed_executor_backend="mp",
        enable_expert_parallel=True,
        all2all_backend="allgather_reducescatter",
        max_model_len=8192,
        max_num_batched_tokens=8192,
        max_num_seqs=1,
        block_size=64,
        kv_cache_dtype="bfloat16",
        gpu_memory_utilization=0.90,
        enable_prefix_caching=False,
        async_scheduling=False,
        generation_config="vllm",
        enforce_eager=False,
        speculative_config={
            "method": "dflash",
            "model": str(DRAFT),
            "revision": DRAFT_REVISION,
            "num_speculative_tokens": 7,
            "draft_sample_method": "greedy",
            "rejection_sample_method": "standard",
        },
        compilation_config={
            "mode": "NONE",
            "cudagraph_mode": "PIECEWISE",
            "cudagraph_capture_sizes": [8],
            "max_cudagraph_capture_size": 8,
        },
    )
    params = SamplingParams(
        temperature=0.0, top_p=1.0, max_tokens=MAX_TOKENS, seed=1, ignore_eos=True
    )

    rows: list[dict[str, Any]] = []
    run_started_ns = time.monotonic_ns()
    for index, prompt in enumerate(prompts):
        started_ns = time.monotonic_ns()
        generated = llm.generate([prompt], params, use_tqdm=False)
        wall_ns = time.monotonic_ns() - started_ns
        if len(generated) != 1 or len(generated[0].outputs) != 1:
            die(f"prompt {index}: unexpected generation shape")
        output = generated[0].outputs[0]
        cached = getattr(generated[0], "num_cached_tokens", None)
        if cached != 0:
            die(f"prompt {index}: cached_tokens={cached}, must be 0")
        if len(output.token_ids) != MAX_TOKENS or output.finish_reason != "length":
            die(
                f"prompt {index}: expected {MAX_TOKENS} length-limited tokens, "
                f"got {len(output.token_ids)} finish={output.finish_reason!r}"
            )
        rows.append(
            {
                "index": index,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "prompt_tokens": len(generated[0].prompt_token_ids),
                "completion_tokens": len(output.token_ids),
                "cached_tokens": cached,
                "finish_reason": output.finish_reason,
                "wall_ns": wall_ns,
                "token_ids_sha256": hashlib.sha256(
                    ",".join(str(t) for t in output.token_ids).encode()
                ).hexdigest(),
            }
        )

    payload = {
        "schema": "laguna-phase0-cycle-attribution-arm-v1",
        "diagnostic_only": True,
        "not_benchmark_or_submission_evidence": True,
        "max_tokens": MAX_TOKENS,
        "prompts": len(prompts),
        "one_active_generation": True,
        "prefix_caching": False,
        "all_cache_zero": all(row["cached_tokens"] == 0 for row in rows),
        "run_wall_ns": time.monotonic_ns() - run_started_ns,
        "rows": rows,
    }
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(f"phase0 attribution arm complete: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
