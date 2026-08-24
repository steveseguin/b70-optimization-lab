#!/usr/bin/env python3
"""Concurrent completion benchmark for a vLLM OpenAI endpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any


def get_json(url: str, timeout: int = 30) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read())


def request_completion(
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    seed: int,
    timeout: int,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": False,
        "seed": seed,
        "ignore_eos": True,
    }
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    elapsed = time.perf_counter() - t0
    choices = data.get("choices") or []
    text = choices[0].get("text") if choices else ""
    usage = data.get("usage") or {}
    return {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "elapsed_s": elapsed,
        "tok_s_out": usage.get("completion_tokens", 0) / elapsed if elapsed > 0 else 0,
        "text": text,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--model", default=None)
    parser.add_argument("--prompt", default="Summarize the likely bottlenecks in an Intel XPU inference server and propose concrete next steps.")
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument(
        "--unique-prompts",
        action="store_true",
        help="Append the deterministic request seed to each prompt for per-request correctness comparisons.",
    )
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    model = args.model
    if model is None:
        model = get_json(f"{base_url}/v1/models")["data"][0]["id"]

    results: list[dict[str, Any]] = []
    lock = threading.Lock()
    errors: list[str] = []

    def worker(seed: int) -> None:
        try:
            prompt = args.prompt
            if args.unique_prompts:
                prompt += f"\nDeterministic request lane: {seed}."
            r = request_completion(
                base_url, model, prompt, args.max_tokens, seed, args.timeout
            )
            r["seed"] = seed
            with lock:
                results.append(r)
        except Exception as exc:
            with lock:
                errors.append(repr(exc))

    total_requests = args.concurrency * args.repeats
    seeds = list(range(total_requests))
    threads: list[threading.Thread] = []
    t0 = time.perf_counter()
    for i in range(total_requests):
        t = threading.Thread(target=worker, args=(seeds[i],))
        t.start()
        threads.append(t)
        # Launch in waves to respect concurrency.
        if (i + 1) % args.concurrency == 0:
            for t in threads[-args.concurrency :]:
                t.join()
    for t in threads:
        if t.is_alive():
            t.join()
    wall = time.perf_counter() - t0

    if errors:
        print(json.dumps({"errors": errors}, indent=2))
        return 1

    completion_tokens = [r["completion_tokens"] for r in results]
    elapsed = [r["elapsed_s"] for r in results]
    per_req = [r["tok_s_out"] for r in results]
    aggregate = sum(completion_tokens) / wall if wall > 0 else 0

    out = {
        "model": model,
        "concurrency": args.concurrency,
        "repeats": args.repeats,
        "total_requests": total_requests,
        "max_tokens": args.max_tokens,
        "wall_s": wall,
        "aggregate_tok_s_out": aggregate,
        "per_request_tok_s_out": {
            "mean": statistics.mean(per_req),
            "median": statistics.median(per_req),
            "min": min(per_req),
            "max": max(per_req),
        },
        "elapsed_s": {
            "mean": statistics.mean(elapsed),
            "median": statistics.median(elapsed),
            "min": min(elapsed),
            "max": max(elapsed),
        },
        "completion_tokens": {
            "mean": statistics.mean(completion_tokens),
            "sum": sum(completion_tokens),
        },
        "response_sha256": sorted(
            hashlib.sha256(r["text"].encode("utf-8")).hexdigest()
            for r in results
        ),
        "response_sha256_by_seed": {
            str(r["seed"]): hashlib.sha256(r["text"].encode("utf-8")).hexdigest()
            for r in sorted(results, key=lambda item: item["seed"])
        },
    }
    print(json.dumps(out, indent=2))
    if args.out:
        args.out.write_text(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
