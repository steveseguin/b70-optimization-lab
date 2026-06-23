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
        "completion_tokens": completion_tokens,
        "tok_s_wall": tok_s_wall,
        "tok_s_after_ttft": tok_s_after_ttft,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text": text,
        "text_preview": text[:240],
    }


def make_prompt(target_tokens: int) -> str:
    seed = (
        "Gemma B70 decode benchmark. Continue with concise technical prose. "
        "Use the word benchmark frequently so tokenization remains stable. "
    )
    # This is intentionally approximate; authoritative token counts come from
    # the server usage block when available.
    return ((seed * ((target_tokens // 18) + 2))[: target_tokens * 6]) + "\n\nAnswer:"


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
        "tok_s_after_ttft": stats("tok_s_after_ttft"),
        "tok_s_wall": stats("tok_s_wall"),
        "ttft_s": stats("ttft_s"),
        "elapsed_s": stats("elapsed_s"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18260")
    parser.add_argument("--model", default="gemma4-26b-a4b-q8")
    parser.add_argument("--api-mode", choices=("chat", "completions"), default="chat")
    parser.add_argument("--prompt-tokens", type=int, default=512)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--repeats", type=int, default=8)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--allow-missing-usage", action="store_true")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    prompt = make_prompt(args.prompt_tokens)
    rows = [
        stream_completion(
            args.base_url,
            args.model,
            prompt,
            args.max_tokens,
            args.timeout,
            args.api_mode,
            args.seed,
            args.allow_missing_usage,
        )
        for _ in range(args.repeats)
    ]
    run_identity = {
        "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "base_url": args.base_url,
        "model": args.model,
        "api_mode": args.api_mode,
        "seed": args.seed,
        "prompt_tokens_requested": args.prompt_tokens,
        "max_tokens": args.max_tokens,
        "repeats": args.repeats,
        "usage_required": not args.allow_missing_usage,
    }
    result = {
        "run_identity": run_identity,
        "summary": summarize(rows),
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
