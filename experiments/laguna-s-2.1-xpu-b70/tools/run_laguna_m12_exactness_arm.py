#!/usr/bin/env python3
"""One eager arm at a chosen exact verifier width, for M=12 exactness proving.

Diagnostic. Emits token ids only; no timing, no throughput, no submission.
Run once per width and compare the token ids across arms: M=8 is already proved
exact against the canonical q=1 teacher, so M=12 equalling M=8 establishes
M=12 exactness transitively.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

TARGET = Path("/mnt/fast-ai/llm-models/laguna-s-2.1/int4")
DRAFT = Path("/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4")
TARGET_REVISION = "4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb"
DRAFT_REVISION = "5e07c246915c86dc6920fead03d019989224f2ba"
SUITE = Path(
    "/home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/"
    "realistic-suite-v1.json"
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--speculative-tokens", type=int, required=True)
    ap.add_argument("--max-tokens", type=int, default=128)
    ap.add_argument("--prompts", type=int, default=13)
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit("output exists")

    max_m = int(os.environ.get("VLLM_XPU_LAGUNA_EXACT_MAX_M", "8"))
    if args.speculative_tokens + 1 > max_m:
        raise SystemExit(
            f"speculative tokens {args.speculative_tokens} needs "
            f"VLLM_XPU_LAGUNA_EXACT_MAX_M >= {args.speculative_tokens + 1}"
        )

    suite = json.loads(SUITE.read_text())
    prompts = [p["prompt"] for p in suite["prompts"]][: args.prompts]

    from vllm import LLM, SamplingParams

    kwargs = dict(
        model=str(TARGET),
        revision=TARGET_REVISION,
        tokenizer=str(TARGET),
        tokenizer_revision=TARGET_REVISION,
        trust_remote_code=True,
        dtype="bfloat16",
        tensor_parallel_size=4,
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
        enforce_eager=True,
    )
    if args.speculative_tokens > 0:
        kwargs["speculative_config"] = {
            "method": "dflash",
            "model": str(DRAFT),
            "revision": DRAFT_REVISION,
            "num_speculative_tokens": args.speculative_tokens,
            "draft_sample_method": "greedy",
            "rejection_sample_method": "standard",
        }
    llm = LLM(**kwargs)
    params = SamplingParams(
        temperature=0.0, top_p=1.0, max_tokens=args.max_tokens, seed=1,
        ignore_eos=True,
    )

    rows = []
    for index, prompt in enumerate(prompts):
        out = llm.generate([prompt], params, use_tqdm=False)
        o = out[0].outputs[0]
        cached = getattr(out[0], "num_cached_tokens", None)
        if cached != 0:
            raise SystemExit(f"prompt {index}: cached_tokens={cached}")
        ids = list(o.token_ids)
        rows.append(
            {
                "index": index,
                "completion_tokens": len(ids),
                "cached_tokens": cached,
                "token_ids": ids,
                "token_ids_sha256": hashlib.sha256(
                    ",".join(str(t) for t in ids).encode()
                ).hexdigest(),
            }
        )

    args.out.write_text(
        json.dumps(
            {
                "schema": "laguna-m12-exactness-arm-v1",
                "diagnostic_only": True,
                "not_benchmark_or_submission_evidence": True,
                "speculative_tokens": args.speculative_tokens,
                "exact_max_m": max_m,
                "max_tokens": args.max_tokens,
                "rows": rows,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(f"arm complete: spec={args.speculative_tokens} max_m={max_m}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
