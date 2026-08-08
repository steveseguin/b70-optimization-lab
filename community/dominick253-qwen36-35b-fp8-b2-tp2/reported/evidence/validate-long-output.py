#!/usr/bin/env python3
"""Long-output corruption and stability test for Qwen3.6-35B FP8 on port 8001."""

import argparse
import json
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROMPTS = [
    """Write a detailed technical guide about building a reliable distributed job queue.
Use at least 18 titled sections. Include failure modes, recovery logic, idempotency,
backpressure, observability, deployment, and testing. Write at least 2200 words.
Do not use filler. Continue until the guide is complete.""",
    """Create a complete Python 3 implementation of a persistent task scheduler using only
standard-library modules. Include type hints, SQLite storage, retries, leases, graceful
shutdown, structured logging, and unit tests. Explain the design after the code. Produce
at least 1800 words and do not omit implementation details.""",
    """Explain how transformer inference servers handle prefill, decode, continuous batching,
paged KV cache, tensor parallelism, quantized weights, and quantized KV cache. Include
trade-offs, failure analysis, equations where useful, and a production checklist. Write
at least 2200 words in coherent prose.""",
]

BAD_RUN = re.compile(r"([!?.;,])\1{9,}")
STRUCTURAL_SEPARATOR = re.compile(r"^[\s\-_=*#]{10,}$")
TOKEN_RE = re.compile(r"\S+")


def post_json(url: str, payload: dict, timeout: int) -> tuple[dict, float]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read()
    return json.loads(body), time.perf_counter() - started


def longest_identical_character_run(text: str) -> int:
    longest = current = 0
    previous = None
    for character in text:
        if character.isspace():
            previous = None
            current = 0
            continue
        if character == previous:
            current += 1
        else:
            previous = character
            current = 1
        longest = max(longest, current)
    return longest


def validate(text: str, completion_tokens: int, minimum_tokens: int) -> list[str]:
    errors = []
    stripped = text.strip()
    tokens = TOKEN_RE.findall(stripped)
    if not stripped:
        errors.append("empty output")
    if completion_tokens < minimum_tokens:
        errors.append(f"short output: {completion_tokens} tokens < {minimum_tokens}")
    if "!!!!" in text:
        errors.append("contains !!!!")
    match = BAD_RUN.search(text)
    if match:
        errors.append(f"punctuation collapse: {match.group(0)[:32]!r}")
    non_structural_text = "\n".join(
        line for line in text.splitlines() if not STRUCTURAL_SEPARATOR.fullmatch(line)
    )
    longest = longest_identical_character_run(non_structural_text)
    if longest >= 16:
        errors.append(f"identical-character run: {longest}")
    if tokens:
        unique_ratio = len(set(tokens)) / len(tokens)
        if unique_ratio < 0.08:
            errors.append(f"low token diversity: {unique_ratio:.4f}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001/v1")
    parser.add_argument("--model", default="qwen36-35b-fp8")
    parser.add_argument("--runs", type=int, default=9)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--minimum-tokens", type=int, default=1200)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--output", default="/home/dom/scripts/results/qwen36-35b-fp8-long.json")
    args = parser.parse_args()

    endpoint = args.base_url.rstrip("/") + "/chat/completions"
    results = []
    failures = 0

    for run in range(args.runs):
        payload = {
            "model": args.model,
            "messages": [{"role": "user", "content": PROMPTS[run % len(PROMPTS)]}],
            "temperature": 0.6,
            "top_p": 0.95,
            "top_k": 20,
            "max_tokens": args.max_tokens,
            "seed": 1000 + run,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        try:
            response, elapsed = post_json(endpoint, payload, args.timeout)
            choice = response["choices"][0]
            message = choice["message"]
            text = message.get("content") or ""
            reasoning = message.get("reasoning_content") or ""
            full_text = reasoning + "\n" + text
            usage = response.get("usage") or {}
            completion_tokens = int(usage.get("completion_tokens") or 0)
            errors = validate(full_text, completion_tokens, args.minimum_tokens)
            if not text.strip():
                errors.append("empty visible output")
            record = {
                "run": run + 1,
                "elapsed_seconds": round(elapsed, 3),
                "completion_tokens": completion_tokens,
                "tokens_per_second": round(completion_tokens / elapsed, 3) if elapsed else 0,
                "finish_reason": choice.get("finish_reason"),
                "characters": len(text),
                "reasoning_characters": len(reasoning),
                "errors": errors,
                "reasoning_content": reasoning,
                "text": text,
            }
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError) as exc:
            record = {"run": run + 1, "errors": [f"request failure: {exc!r}"], "text": ""}

        results.append(record)
        if record["errors"]:
            failures += 1
            print(f"FAIL run={run + 1}: {record['errors']}", flush=True)
        else:
            print(
                f"PASS run={run + 1} tokens={record['completion_tokens']} "
                f"seconds={record['elapsed_seconds']} tok/s={record['tokens_per_second']}",
                flush=True,
            )

    rates = [r["tokens_per_second"] for r in results if not r["errors"]]
    summary = {
        "endpoint": endpoint,
        "model": args.model,
        "runs": args.runs,
        "failures": failures,
        "passed": failures == 0,
        "median_tokens_per_second": round(statistics.median(rates), 3) if rates else 0,
        "results": results,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))
    print(f"Saved: {output}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
