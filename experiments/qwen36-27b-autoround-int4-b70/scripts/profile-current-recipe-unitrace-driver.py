#!/usr/bin/env python3
"""Retained driver for the closed, excessively intrusive Qwen27 unitrace lane."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--unitrace", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--warmup-tokens", type=int, default=128)
    parser.add_argument("--profile-tokens", type=int, default=8)
    return parser.parse_args()


def token_record(outputs: list[Any]) -> dict[str, Any]:
    token_ids = [
        int(token) for request in outputs for token in request.outputs[0].token_ids
    ]
    payload = ",".join(map(str, token_ids)).encode()
    return {
        "count": len(token_ids),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "token_ids": token_ids,
    }


def main() -> int:
    args = parse_args()
    for name in ("warmup_tokens", "profile_tokens"):
        if getattr(args, name) < 1:
            raise ValueError(f"--{name.replace('_', '-')} must be positive")

    from vllm import LLM, SamplingParams

    started = time.perf_counter()
    llm = LLM(
        model=args.model,
        tokenizer=args.model,
        trust_remote_code=True,
        tensor_parallel_size=1,
        max_model_len=2048,
        max_num_seqs=1,
        max_num_batched_tokens=1024,
        gpu_memory_utilization=0.95,
        enable_prefix_caching=False,
        generation_config="vllm",
        compilation_config={
            "cudagraph_mode": "PIECEWISE",
            "max_cudagraph_capture_size": 8,
        },
        speculative_config={
            "method": "qwen3_next_mtp",
            "num_speculative_tokens": 3,
        },
    )
    init_s = time.perf_counter() - started

    warmup_params = SamplingParams(
        temperature=0,
        max_tokens=args.warmup_tokens,
        ignore_eos=True,
        seed=27,
    )
    profile_params = SamplingParams(
        temperature=0,
        max_tokens=args.profile_tokens,
        ignore_eos=True,
        seed=29,
    )
    warmup_prompt = "Return a concise checklist for checking a backup."
    profile_prompt = (
        "A monitoring service reports intermittent packet loss after a router "
        "update. Give an ordered incident investigation."
    )

    warmup_started = time.perf_counter()
    warmup = llm.generate([warmup_prompt], warmup_params, use_tqdm=False)
    warmup_s = time.perf_counter() - warmup_started

    subprocess.run(
        [args.unitrace, "--resume", args.session],
        check=True,
    )
    profile_started = time.perf_counter()
    profiled = llm.generate([profile_prompt], profile_params, use_tqdm=False)
    profile_s = time.perf_counter() - profile_started

    result = {
        "classification": "diagnostic_level_zero_kernel_profile_not_headline",
        "valid_headline_throughput": False,
        "topology": "offline_llm_v1_multiprocessing_disabled",
        "model": args.model,
        "init_s": init_s,
        "warmup_s": warmup_s,
        "profile_s_under_unitrace": profile_s,
        "warmup": token_record(warmup),
        "profiled": token_record(profiled),
    }
    Path(args.output).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
