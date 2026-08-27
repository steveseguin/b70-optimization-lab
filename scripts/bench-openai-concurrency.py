#!/usr/bin/env python3
"""Benchmark concurrent OpenAI-compatible completions against a live endpoint."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import statistics
import time
import urllib.request
from pathlib import Path
from typing import Any

def request_json(url: str, timeout: int) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def repeated_text(tokenizer: Any, target_tokens: int, seed: str) -> str:
    seed_ids = tokenizer.encode(seed, add_special_tokens=False)
    if not seed_ids:
        raise ValueError("benchmark seed produced no tokens")
    repeats = (target_tokens + len(seed_ids) - 1) // len(seed_ids)
    ids = (seed_ids * repeats)[:target_tokens]
    return tokenizer.decode(ids, skip_special_tokens=True)


def build_prompt(
    tokenizer: Any,
    target_tokens: int,
    label: str,
    shared_prefix_tokens: int = 0,
    prompt_salt: str = "",
) -> str:
    if shared_prefix_tokens > 0:
        if shared_prefix_tokens >= target_tokens:
            raise ValueError("--shared-prefix-tokens must be smaller than --prompt-tokens")
        shared_seed = (
            "Shared LAN website generation system prompt. "
            "Follow the fixed house style, accessibility rules, component names, "
            "CSS reset, routing structure, and deployment constraints. "
        )
        unique_seed = (
            f"Unique user request lane {label} salt {prompt_salt}. "
            "This section contains request-specific copy, assets, layout notes, "
            "content requirements, and implementation details. "
        )
        prompt = (
            repeated_text(tokenizer, shared_prefix_tokens, shared_seed)
            + "\n\n"
            + repeated_text(tokenizer, target_tokens - shared_prefix_tokens, unique_seed)
        )
    else:
        seed = (
            f"Qwen B70 concurrency benchmark lane {label} salt {prompt_salt}. "
            "Preserve the context and continue the repeated benchmark word. "
        )
        prompt = repeated_text(tokenizer, target_tokens, seed)
    return (
        f"{prompt}\n\n"
        "Task: continue with the word benchmark separated by spaces. "
        "Do not stop early.\n\nAnswer: benchmark benchmark benchmark"
    )


def stream_completion(
    base_url: str,
    model: str,
    prompt: str,
    output_tokens: int,
    seed: int,
    timeout: int,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": output_tokens,
        "temperature": 0,
        "top_p": 1.0,
        "seed": seed,
        "stream": True,
        "stream_options": {"include_usage": True},
        "ignore_eos": True,
    }
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    started = time.perf_counter()
    first_text_at: float | None = None
    ended: float | None = None
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
            if event.get("error"):
                raise RuntimeError("completion stream returned an error event")
            if event.get("usage"):
                usage = event["usage"]
            for choice in event.get("choices", []):
                token_text = choice.get("text") or ""
                if token_text:
                    if first_text_at is None:
                        first_text_at = time.perf_counter()
                    chunks += 1
                    text_parts.append(token_text)
    ended = time.perf_counter()

    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")
    if type(prompt_tokens) is not int or prompt_tokens <= 0:
        raise RuntimeError("completion stream ended without valid prompt-token usage")
    if type(completion_tokens) is not int or completion_tokens != output_tokens:
        raise RuntimeError("completion stream ended without valid completion-token usage")
    if type(total_tokens) is not int or total_tokens != prompt_tokens + completion_tokens:
        raise RuntimeError("completion stream ended without consistent total-token usage")
    if first_text_at is None or chunks <= 0:
        raise RuntimeError("completion stream ended without generated text")
    elapsed_s = ended - started
    ttft_s = None if first_text_at is None else first_text_at - started
    post_ttft_s = None if first_text_at is None else ended - first_text_at
    tok_s_out_after_ttft = None
    tok_s_out_wall = None
    tok_s_total_wall = None
    if isinstance(completion_tokens, int) and completion_tokens > 0:
        tok_s_out_wall = completion_tokens / elapsed_s
        if post_ttft_s and post_ttft_s > 0:
            tok_s_out_after_ttft = completion_tokens / post_ttft_s
    if isinstance(total_tokens, int) and total_tokens > 0:
        tok_s_total_wall = total_tokens / elapsed_s

    text = "".join(text_parts)
    return {
        "started_s": started,
        "first_text_at_s": first_text_at,
        "ended_s": ended,
        "elapsed_s": elapsed_s,
        "ttft_s": ttft_s,
        "post_ttft_s": post_ttft_s,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "tok_s_out_wall": tok_s_out_wall,
        "tok_s_out_after_ttft": tok_s_out_after_ttft,
        "tok_s_total_wall": tok_s_total_wall,
        "chunks": chunks,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text_preview": text[:160],
    }


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    starts = [r["started_s"] for r in records]
    ends = [r["ended_s"] for r in records]
    firsts = [r["first_text_at_s"] for r in records if r.get("first_text_at_s")]
    completion_tokens = [
        r.get("completion_tokens") for r in records if isinstance(r.get("completion_tokens"), int)
    ]
    prompt_tokens = [
        r.get("prompt_tokens") for r in records if isinstance(r.get("prompt_tokens"), int)
    ]
    total_completion = sum(completion_tokens)
    total_prompt = sum(prompt_tokens)
    wall_s = max(ends) - min(starts)
    decode_wall_s_from_first = None if not firsts else max(ends) - min(firsts)

    def stats(key: str) -> dict[str, float] | None:
        values = [r[key] for r in records if isinstance(r.get(key), (int, float))]
        if not values:
            return None
        return {
            "mean": statistics.fmean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
        }

    return {
        "requests": len(records),
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "wall_s": wall_s,
        "aggregate_output_tok_s_wall": total_completion / wall_s if wall_s > 0 else None,
        "decode_wall_s_from_first_text": decode_wall_s_from_first,
        "aggregate_output_tok_s_from_first_text": (
            None
            if not decode_wall_s_from_first or decode_wall_s_from_first <= 0
            else total_completion / decode_wall_s_from_first
        ),
        "per_request_tok_s_out_after_ttft": stats("tok_s_out_after_ttft"),
        "per_request_tok_s_out_wall": stats("tok_s_out_wall"),
        "per_request_ttft_s": stats("ttft_s"),
        "per_request_elapsed_s": stats("elapsed_s"),
    }


def main() -> int:
    from transformers import AutoTokenizer

    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--tokenizer", required=True)
    parser.add_argument("--prompt-tokens", type=int, default=2048)
    parser.add_argument(
        "--shared-prefix-tokens",
        type=int,
        default=0,
        help="If >0, build prompts with this many identical leading tokens and the remaining prompt as unique per request.",
    )
    parser.add_argument(
        "--prompt-salt",
        default="",
        help="Added only to the unique per-request prompt section. Useful for prefix-cache tests that keep the shared prefix warm while changing the unique tail.",
    )
    parser.add_argument("--output-tokens", type=int, default=512)
    parser.add_argument("--concurrency", type=int, action="append", required=True)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--seed", type=int, default=20260606)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    model_payload = request_json(f"{base_url}/v1/models", args.timeout)
    model_info = model_payload["data"][0]
    model = model_info["id"]
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, trust_remote_code=True)

    prompts = {
        n: [
            build_prompt(
                tokenizer,
                args.prompt_tokens,
                f"c{n}-{i}",
                args.shared_prefix_tokens,
                args.prompt_salt,
            )
            for i in range(n)
        ]
        for n in args.concurrency
    }

    output: dict[str, Any] = {
        "base_url": base_url,
        "model": model,
        "model_info": model_info,
        "tokenizer": args.tokenizer,
        "requested_prompt_tokens": args.prompt_tokens,
        "shared_prefix_tokens": args.shared_prefix_tokens,
        "prompt_salt": args.prompt_salt,
        "requested_output_tokens": args.output_tokens,
        "warmups": args.warmups,
        "scenarios": {},
    }

    for warmup in range(args.warmups):
        stream_completion(
            base_url,
            model,
            prompts[args.concurrency[0]][0],
            min(64, args.output_tokens),
            args.seed + warmup,
            args.timeout,
        )

    for concurrency in args.concurrency:
        records: list[dict[str, Any]] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [
                executor.submit(
                    stream_completion,
                    base_url,
                    model,
                    prompt,
                    args.output_tokens,
                    args.seed + concurrency * 1000 + index,
                    args.timeout,
                )
                for index, prompt in enumerate(prompts[concurrency])
            ]
            for future in concurrent.futures.as_completed(futures):
                records.append(future.result())
        records.sort(key=lambda item: item["started_s"])
        summary = summarize(records)
        output["scenarios"][f"c{concurrency}"] = {
            "concurrency": concurrency,
            "records": records,
            "summary": summary,
        }
        print(
            json.dumps(
                {
                    "concurrency": concurrency,
                    "prompt_tokens_each": records[0].get("prompt_tokens") if records else None,
                    "completion_tokens_each": records[0].get("completion_tokens") if records else None,
                    "aggregate_output_tok_s_wall": summary["aggregate_output_tok_s_wall"],
                    "aggregate_output_tok_s_from_first_text": summary[
                        "aggregate_output_tok_s_from_first_text"
                    ],
                    "mean_per_request_tok_s_after_ttft": (
                        summary["per_request_tok_s_out_after_ttft"]["mean"]
                        if summary["per_request_tok_s_out_after_ttft"]
                        else None
                    ),
                    "mean_ttft_s": (
                        summary["per_request_ttft_s"]["mean"]
                        if summary["per_request_ttft_s"]
                        else None
                    ),
                },
                sort_keys=True,
            )
        )

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, indent=2) + "\n")
    print(f"wrote {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
