#!/usr/bin/env python3
"""Small OpenAI-compatible single-session decode benchmark and canary runner."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import statistics
import time
import urllib.request
from pathlib import Path
from typing import Any


def stream_completion(
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    timeout: int,
    api_mode: str,
    seed: int | None,
    allow_missing_usage: bool,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0,
        "top_p": 1,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if seed is not None:
        payload["seed"] = seed
    if api_mode == "chat":
        endpoint = "chat/completions"
        payload["messages"] = [{"role": "user", "content": prompt}]
    else:
        endpoint = "completions"
        payload["prompt"] = prompt
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/{endpoint}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    first_text_at: float | None = None
    text_parts: list[str] = []
    usage: dict[str, Any] = {}
    chunks = 0
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            event = json.loads(data)
            if event.get("usage"):
                usage = event["usage"]
            for choice in event.get("choices", []):
                if api_mode == "chat":
                    token_text = (choice.get("delta") or {}).get("content") or ""
                else:
                    token_text = choice.get("text") or ""
                if token_text:
                    if first_text_at is None:
                        first_text_at = time.perf_counter()
                    text_parts.append(token_text)
                    chunks += 1
    ended = time.perf_counter()
    text = "".join(text_parts)
    elapsed_s = ended - started
    post_ttft_s = None if first_text_at is None else ended - first_text_at
    completion_tokens = usage.get("completion_tokens")
    prompt_tokens = usage.get("prompt_tokens")
    if not isinstance(completion_tokens, int) and not allow_missing_usage:
        raise RuntimeError(
            "Server response did not include usage.completion_tokens; "
            "rerun with --allow-missing-usage only for a non-promoted diagnostic."
        )
    tok_s_after_ttft = None
    tok_s_wall = None
    if isinstance(completion_tokens, int) and completion_tokens > 0:
        tok_s_wall = completion_tokens / elapsed_s
        if post_ttft_s and post_ttft_s > 0:
            tok_s_after_ttft = completion_tokens / post_ttft_s
    return {
        "elapsed_s": elapsed_s,
        "ttft_s": None if first_text_at is None else first_text_at - started,
        "post_ttft_s": post_ttft_s,
        "chunks": chunks,
        "usage": usage,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "tok_s_wall": tok_s_wall,
        "tok_s_after_ttft": tok_s_after_ttft,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text": text,
        "text_preview": text[:240],
    }


def make_prompt(target_tokens: int, mode: str, variant: int = 0) -> str:
    unique = mode.endswith("-unique")
    base_mode = mode.removesuffix("-unique")
    unique_prefix = ""
    if unique:
        unique_prefix = (
            f"Unique benchmark instance {variant:04d}. "
            f"Deterministic nonce gemma-b70-{variant:04d}-"
            f"{(variant * 2654435761) & 0xffffffff:08x}.\n\n"
        )

    if mode == "long":
        return (
            "Write a long deterministic decode benchmark response. "
            "Continue until you reach the token limit. "
            "Use numbered lines from 001 onward. "
            "Each line must contain the words benchmark, latency, memory, "
            "throughput, validation, and repeatability. "
            "Do not summarize, do not conclude, and do not stop early. "
            "Begin now.\n\n"
        )

    if base_mode == "filled-long":
        prefix = (
            unique_prefix +
            "You are running a deterministic Gemma B70 decode benchmark. "
            "Read the reference context, then produce a long numbered response "
            "until the token limit is reached. Do not summarize early.\n\n"
            "Reference context:\n"
        )
        block = (
            "benchmark latency memory throughput validation repeatability "
            "scheduler cache kernel sycl level-zero b70 q8 deterministic "
            "single-session decode measurement "
        )
        if unique:
            block += (
                f"instance {variant:04d} nonce "
                f"{(variant * 1103515245 + 12345) & 0xffffffff:08x} "
            )
        body = (block * ((target_tokens // 16) + 8))[: max(0, target_tokens * 6)]
        suffix = (
            "\n\nTask: write numbered lines from 001 onward. Each line must "
            "include benchmark, latency, memory, throughput, validation, and "
            "repeatability. Continue until the token limit. Begin now.\n\n"
        )
        return prefix + body + suffix

    if base_mode == "filled-fixed-line":
        prefix = (
            unique_prefix +
            "You are running a deterministic Gemma B70 decode benchmark. "
            "Read the reference context, then produce a long numbered response "
            "until the token limit is reached. Do not summarize early.\n\n"
            "Reference context:\n"
        )
        block = (
            "benchmark latency memory throughput validation repeatability "
            "scheduler cache kernel sycl level-zero b70 q8 deterministic "
            "single-session decode measurement "
        )
        if unique:
            block += (
                f"instance {variant:04d} nonce "
                f"{(variant * 1103515245 + 12345) & 0xffffffff:08x} "
            )
        body = (block * ((target_tokens // 16) + 8))[: max(0, target_tokens * 6)]
        suffix = (
            "\n\nTask: write numbered lines from 001 onward. Each line must "
            "use exactly this format, with only the number changing:\n"
            "001. benchmark latency memory throughput validation repeatability\n"
            "Do not use commas, bullets, extra words, or a conclusion. Continue "
            "until the token limit. Begin now.\n\n"
        )
        return prefix + body + suffix

    seed = (
        "Gemma B70 decode benchmark. Continue with concise technical prose. "
        "Use the word benchmark frequently so tokenization remains stable. "
    )
    # This is intentionally approximate; authoritative token counts come from
    # the server usage block when available.
    return unique_prefix + ((seed * ((target_tokens // 18) + 2))[: target_tokens * 6]) + "\n\nAnswer:"


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def stats(key: str) -> dict[str, float] | None:
        vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
        if not vals:
            return None
        stdev = statistics.stdev(vals) if len(vals) > 1 else 0.0
        mean = statistics.fmean(vals)
        return {
            "mean": mean,
            "median": statistics.median(vals),
            "min": min(vals),
            "max": max(vals),
            "stdev": stdev,
            "cv": None if mean == 0 else stdev / mean,
        }

    return {
        "requests": len(rows),
        "completion_tokens_total": sum(
            r.get("completion_tokens") or 0
            for r in rows
            if isinstance(r.get("completion_tokens"), int)
        ),
        "prompt_tokens": stats("prompt_tokens"),
        "completion_tokens": stats("completion_tokens"),
        "tok_s_after_ttft": stats("tok_s_after_ttft"),
        "tok_s_wall": stats("tok_s_wall"),
        "ttft_s": stats("ttft_s"),
        "elapsed_s": stats("elapsed_s"),
    }


def cached_tokens(row: dict[str, Any]) -> int | None:
    usage = row.get("usage")
    if not isinstance(usage, dict):
        return None
    details = usage.get("prompt_tokens_details")
    if not isinstance(details, dict):
        return None
    value = details.get("cached_tokens")
    return value if isinstance(value, int) else None


def fresh_response_validity(rows: list[dict[str, Any]], prompts_are_unique: bool = False) -> dict[str, Any]:
    first_row = rows[0] if rows else {}
    cached = [cached_tokens(row) for row in rows]
    known_cached = [value for value in cached if value is not None]
    cached_all_zero = (
        len(known_cached) == len(rows) and all(value == 0 for value in known_cached)
    )
    prompt_hashes = [
        row.get("prompt_sha256") for row in rows
        if isinstance(row.get("prompt_sha256"), str)
    ]
    all_prompt_hashes_distinct = (
        len(prompt_hashes) == len(rows) and len(set(prompt_hashes)) == len(rows)
    )
    return {
        "headline_policy": (
            "Use row0 only as fresh-response headline. Later repeated-prompt "
            "rows are support-only unless each request uses an independently "
            "fresh prompt with no reusable continuation/history."
        ),
        "headline_row": 0 if rows else None,
        "headline_tok_s_after_ttft": first_row.get("tok_s_after_ttft"),
        "headline_tok_s_wall": first_row.get("tok_s_wall"),
        "headline_cached_tokens": cached_tokens(first_row) if rows else None,
        "cached_tokens_reported": bool(known_cached),
        "cached_tokens_all_zero": cached_all_zero,
        "all_cached_tokens": cached,
        "prompts_are_unique": prompts_are_unique,
        "all_prompt_hashes_distinct": all_prompt_hashes_distinct,
        "all_rows_fresh_response_mean_eligible": (
            bool(rows) and prompts_are_unique and all_prompt_hashes_distinct and cached_all_zero
        ),
        "repeated_prompt_rows_support_only": len(rows) > 1 and not prompts_are_unique,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18260")
    parser.add_argument("--model", default="gemma4-26b-a4b-q8")
    parser.add_argument("--api-mode", choices=("chat", "completions"), default="chat")
    parser.add_argument("--prompt-tokens", type=int, default=512)
    parser.add_argument(
        "--prompt-mode",
        choices=(
            "default",
            "long",
            "filled-long",
            "filled-fixed-line",
            "filled-long-unique",
            "filled-fixed-line-unique",
        ),
        default="default",
        help=(
            "Prompt style. 'default' preserves historical runs; 'long' is a "
            "short instruction that asks the model not to stop early; "
            "'filled-long' fills the requested prompt budget before asking for "
            "a max-token response; 'filled-fixed-line' uses the same filled "
            "shape but requests one exact repeated output line format. The "
            "'*-unique' variants create a deterministic different prompt per "
            "repeat so aggregate means can be audited as fresh-response rows."
        ),
    )
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--repeats", type=int, default=8)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--allow-missing-usage", action="store_true")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    prompts_are_unique = args.prompt_mode.endswith("-unique")
    prompts = [
        make_prompt(args.prompt_tokens, args.prompt_mode, i if prompts_are_unique else 0)
        for i in range(args.repeats)
    ]
    prompt_sha256 = hashlib.sha256(prompts[0].encode("utf-8")).hexdigest() if prompts else None
    rows = []
    for i, prompt in enumerate(prompts):
        row = stream_completion(
            args.base_url,
            args.model,
            prompt,
            args.max_tokens,
            args.timeout,
            args.api_mode,
            args.seed,
            args.allow_missing_usage,
        )
        row["prompt_variant"] = i if prompts_are_unique else 0
        row["prompt_sha256"] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        rows.append(row)
    run_identity = {
        "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "base_url": args.base_url,
        "model": args.model,
        "api_mode": args.api_mode,
        "seed": args.seed,
        "prompt_tokens_requested": args.prompt_tokens,
        "prompt_mode": args.prompt_mode,
        "prompt_chars": len(prompts[0]) if prompts else 0,
        "prompt_sha256": prompt_sha256,
        "prompt_sha256s": [
            hashlib.sha256(prompt.encode("utf-8")).hexdigest() for prompt in prompts
        ],
        "prompts_are_unique": prompts_are_unique,
        "prompt_preview": prompts[0][:240] if prompts else "",
        "max_tokens": args.max_tokens,
        "repeats": args.repeats,
        "usage_required": not args.allow_missing_usage,
    }
    result = {
        "run_identity": run_identity,
        "summary": summarize(rows),
        "fresh_response_validity": fresh_response_validity(rows, prompts_are_unique),
        "rows": rows,
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
