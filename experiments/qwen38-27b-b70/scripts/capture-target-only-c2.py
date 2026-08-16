#!/usr/bin/env python3
"""Capture an exact, cache-cold two-slot target-only llama.cpp run."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import threading
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


PROMPTS = (
    "Write a precise explanation of why a binary search is logarithmic. Include one small worked example and no code.",
    "Compare optimistic and pessimistic locking for a high-contention database table. Give two concrete tradeoffs for each.",
    "Explain how a write-ahead log protects a database transaction after a power failure. Use one concrete example.",
    "Describe three practical differences between processes and threads. Be precise and avoid analogies.",
)


def post_json(url: str, payload: dict, timeout: int) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def token_hash(tokens: list[int]) -> str:
    return hashlib.sha256(json.dumps(tokens, separators=(",", ":")).encode()).hexdigest()


def payload(prompt: str, slot: int, n_predict: int, stream: bool) -> dict:
    return {
        "prompt": prompt,
        "n_predict": n_predict,
        "temperature": 0,
        "top_p": 1,
        "seed": 1,
        "cache_prompt": False,
        "return_tokens": True,
        "ignore_eos": True,
        "id_slot": slot,
        "stream": stream,
    }


def stream_one(base_url: str, slot: int, prompt: str, n_predict: int, timeout: int,
               barrier: threading.Barrier) -> dict:
    parsed = urlparse(base_url)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=timeout)
    connection.connect()
    barrier.wait(timeout=30)
    started = time.perf_counter()
    connection.request(
        "POST",
        "/completion",
        body=json.dumps(payload(prompt, slot, n_predict, True)).encode(),
        headers={"Content-Type": "application/json"},
    )
    response = connection.getresponse()
    if response.status != 200:
        raise RuntimeError(f"slot {slot}: HTTP {response.status}")
    tokens: list[int] = []
    offsets: list[float] = []
    final: dict | None = None
    while True:
        raw = response.readline()
        if not raw:
            break
        line = raw.decode(errors="strict").strip()
        if not line.startswith("data:"):
            continue
        body = line[5:].strip()
        if body == "[DONE]":
            break
        event = json.loads(body)
        event_tokens = event.get("tokens")
        if isinstance(event_tokens, list) and event_tokens:
            now = time.perf_counter() - started
            tokens.extend(event_tokens)
            offsets.extend([now] * len(event_tokens))
        if event.get("stop") is True:
            final = event
    ended = time.perf_counter()
    connection.close()
    if final is None or len(tokens) != n_predict or len(offsets) != n_predict:
        raise RuntimeError(f"slot {slot}: incomplete stream ({len(tokens)} tokens)")
    return {
        "slot": slot,
        "tokens": tokens,
        "token_offsets_s": offsets,
        "started_perf_s": started,
        "ended_perf_s": ended,
        "final": final,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18089")
    parser.add_argument("--n-predict", type=int, default=256)
    parser.add_argument("--concurrency", type=int, default=2, choices=range(1, len(PROMPTS) + 1))
    parser.add_argument("--prompt-offset", type=int, default=0, choices=range(len(PROMPTS)))
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    concurrency = args.concurrency
    if args.prompt_offset + concurrency > len(PROMPTS):
        parser.error("prompt-offset + concurrency exceeds the fixed prompt set")
    prompts = PROMPTS[args.prompt_offset:args.prompt_offset + concurrency]

    base_url = args.base_url.rstrip("/")
    with urllib.request.urlopen(f"{base_url}/health", timeout=10) as response:
        if response.status != 200:
            raise RuntimeError("server is not healthy")

    sequential = []
    for slot, prompt in enumerate(prompts):
        result = post_json(
            f"{base_url}/completion",
            payload(prompt, slot, args.n_predict, False),
            args.timeout,
        )
        tokens = result.get("tokens")
        timings = result.get("timings") or {}
        if not isinstance(tokens, list) or len(tokens) != args.n_predict:
            raise RuntimeError(f"slot {slot}: invalid sequential oracle")
        if timings.get("cache_n") != 0:
            raise RuntimeError(f"slot {slot}: sequential oracle was not cache-cold")
        sequential.append({
            "slot": slot,
            "token_ids_sha256": token_hash(tokens),
            "tokens": tokens,
            "timings": timings,
        })

    release: list[float] = []
    barrier = threading.Barrier(concurrency + 1, action=lambda: release.append(time.perf_counter()))
    concurrent: list[dict | None] = [None] * concurrency
    errors: list[str] = []

    def worker(slot: int) -> None:
        try:
            concurrent[slot] = stream_one(
                base_url, slot, prompts[slot], args.n_predict, args.timeout, barrier
            )
        except BaseException as exc:  # preserve worker failures in the packet
            errors.append(repr(exc))
            try:
                barrier.abort()
            except BaseException:
                pass

    threads = [
        threading.Thread(target=worker, args=(slot,), daemon=True)
        for slot in range(concurrency)
    ]
    for thread in threads:
        thread.start()
    barrier.wait(timeout=30)
    for thread in threads:
        thread.join(timeout=args.timeout + 30)
    if errors or any(thread.is_alive() for thread in threads) or any(row is None for row in concurrent):
        raise RuntimeError(f"concurrent capture failed: {errors}")

    rows = [row for row in concurrent if row is not None]
    first_times = [row["started_perf_s"] + row["token_offsets_s"][0] for row in rows]
    last_times = [row["started_perf_s"] + row["token_offsets_s"][-1] for row in rows]
    per_request = [
        (args.n_predict - 1) / (last - first)
        for first, last in zip(first_times, last_times)
    ]
    aggregate_d = (concurrency * (args.n_predict - 1)) / (max(last_times) - min(first_times))
    wall = max(row["ended_perf_s"] for row in rows) - release[0]
    exact = [
        row["tokens"] == sequential[row["slot"]]["tokens"]
        for row in rows
    ]
    cache_cold = [
        (row["final"].get("timings") or {}).get("cache_n") == 0
        for row in rows
    ]
    result = {
        "test": f"Qwen3.8 target-only TP2 ordinary concurrency {concurrency}",
        "concurrency": concurrency,
        "prompt_offset": args.prompt_offset,
        "n_predict_per_request": args.n_predict,
        "speculation": False,
        "cache_prompt": False,
        "sequential_oracles": [
            {key: value for key, value in row.items() if key != "tokens"}
            for row in sequential
        ],
        "concurrent": [
            {
                "slot": row["slot"],
                "token_ids_sha256": token_hash(row["tokens"]),
                "exact_to_sequential_oracle": exact[index],
                "cache_n": (row["final"].get("timings") or {}).get("cache_n"),
                "conventional_d_tok_s": per_request[index],
                "ttft_s": row["token_offsets_s"][0],
            }
            for index, row in enumerate(rows)
        ],
        "aggregate_conventional_d_tok_s": aggregate_d,
        "aggregate_wall_tok_s": concurrency * args.n_predict / wall,
        "fairness_min_over_max": min(per_request) / max(per_request),
        "all_exact": all(exact),
        "all_cache_cold": all(cache_cold),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["all_exact"] and result["all_cache_cold"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
