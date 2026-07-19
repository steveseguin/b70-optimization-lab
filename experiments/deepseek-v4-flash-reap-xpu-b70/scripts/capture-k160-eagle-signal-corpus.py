#!/usr/bin/env python3
"""Drive one-active-generation K160 feature capture from a prompt manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any

CATEGORY_SHARES = {
    "prose": 0.45,
    "code": 0.15,
    "math": 0.15,
    "extraction": 0.15,
    "low-locality": 0.10,
}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def request_key(request_id: str) -> int:
    digest = hashlib.sha256(request_id.encode()).digest()
    return int.from_bytes(digest[:8], "little") & ((1 << 63) - 1)


def metrics(base_url: str, timeout: int) -> dict[str, float]:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/metrics", timeout=timeout) as r:
        text = r.read().decode()
    result = {"running": 0.0, "waiting": 0.0}
    names = {
        "vllm:num_requests_running": "running",
        "vllm:num_requests_waiting": "waiting",
    }
    for line in text.splitlines():
        for metric_name, key in names.items():
            if line.startswith(metric_name + "{") or line.startswith(metric_name + " "):
                result[key] += float(line.rsplit(" ", 1)[-1])
    return result


def post(
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    request_id: str,
    timeout: int,
) -> dict[str, Any]:
    cache_salt = str(uuid.uuid4())
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "top_p": 1,
        "seed": 1,
        "stream": False,
        "return_token_ids": True,
        "cache_salt": cache_salt,
        "request_id": request_id,
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Request-Id": request_id},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = json.load(response)
    elapsed = time.perf_counter() - started
    choice = raw["choices"][0]
    message = choice.get("message") or {}
    usage = raw.get("usage") or {}
    output_text = message.get("content") or ""
    token_ids = (
        choice.get("token_ids")
        or message.get("token_ids")
        or raw.get("token_ids")
        or []
    )
    return {
        "response_id": raw["id"],
        "elapsed_s": elapsed,
        "finish_reason": choice.get("finish_reason"),
        "usage": usage,
        "cached_tokens": (usage.get("prompt_tokens_details") or {}).get(
            "cached_tokens"
        ),
        "output_text": output_text,
        "output_sha256": sha(output_text),
        "output_token_ids": token_ids,
        "cache_salt_sha256": sha(cache_salt),
    }


def render_prompt(
    base_url: str,
    model: str,
    prompt: str,
    request_id: str,
    timeout: int,
) -> list[int]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1,
        "temperature": 0,
        "request_id": request_id,
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions/render",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = json.load(response)
    return [int(token_id) for token_id in raw["token_ids"]]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--model", default="deepseek-v4-flash-k160")
    parser.add_argument("--prompts", type=Path, required=True)
    parser.add_argument("--split", choices=("train", "dev", "smoke"), required=True)
    parser.add_argument("--target-tokens", type=int, required=True)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--arm-file", type=Path)
    args = parser.parse_args()

    prompts = load_jsonl(args.prompts)
    if not prompts:
        raise RuntimeError("prompt manifest is empty")
    if args.split in {"train", "dev"} and any(
        item["split"] != args.split for item in prompts
    ):
        raise RuntimeError("prompt manifest split does not match requested split")
    quotas = {
        category: int(args.target_tokens * share)
        for category, share in CATEGORY_SHARES.items()
    }
    quotas["prose"] += args.target_tokens - sum(quotas.values())
    if args.split == "smoke":
        quotas = {name: 0 for name in CATEGORY_SHARES}
        quotas["prose"] = args.target_tokens

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise FileExistsError(args.output)
    prompt_queues = {
        category: [item for item in prompts if item["category"] == category]
        for category in CATEGORY_SHARES
    }
    counts = {category: 0 for category in CATEGORY_SHARES}
    indices = {category: 0 for category in CATEGORY_SHARES}
    namespace = {"train": "eagletrain", "dev": "eagledev", "smoke": "eaglesmoke"}[
        args.split
    ]
    started = time.time()
    if args.arm_file is not None:
        args.arm_file.parent.mkdir(parents=True, exist_ok=True)
        args.arm_file.touch(exist_ok=False)
    with args.output.open("x") as stream:
        request_index = 0
        while any(counts[name] < quotas[name] for name in quotas):
            category = max(quotas, key=lambda name: quotas[name] - counts[name])
            if counts[category] >= quotas[category]:
                continue
            queue = prompt_queues[category]
            index = indices[category]
            if index >= len(queue):
                raise RuntimeError(f"exhausted unique {category} prompts")
            item = queue[index]
            indices[category] += 1
            remaining = quotas[category] - counts[category]
            max_tokens = min(args.max_tokens, remaining)
            request_id = (
                f"{namespace}-{request_index:06d}-{item['prompt_sha256'][:12]}"
            )
            prompt_token_ids = render_prompt(
                args.base_url,
                args.model,
                item["prompt"],
                request_id,
                args.timeout,
            )
            before = metrics(args.base_url, args.timeout)
            if before["running"] != 0 or before["waiting"] != 0:
                raise RuntimeError(f"endpoint busy before {request_id}: {before}")
            response = post(
                args.base_url,
                args.model,
                item["prompt"],
                max_tokens,
                request_id,
                args.timeout,
            )
            after = metrics(args.base_url, args.timeout)
            if after["running"] != 0 or after["waiting"] != 0:
                raise RuntimeError(f"endpoint not idle after {request_id}: {after}")
            cached = response["cached_tokens"]
            if cached not in (0, None):
                raise RuntimeError(f"cached tokens were nonzero for {request_id}")
            completion_tokens = int(response["usage"].get("completion_tokens") or 0)
            if completion_tokens <= 0:
                raise RuntimeError(f"no completion tokens for {request_id}")
            counts[category] += completion_tokens
            row = {
                "schema_version": "k160-eagle-capture-request-v1",
                "split": args.split,
                "category": category,
                "request_index": request_index,
                "request_id": request_id,
                "request_key": request_key(response["response_id"]),
                "prompt_id": item["prompt_id"],
                "prompt_sha256": item["prompt_sha256"],
                "source_id": item["source_id"],
                "source_revision": item["source_revision"],
                "prompt_token_ids": prompt_token_ids,
                "max_tokens": max_tokens,
                "response": response,
                "cumulative_category_tokens": counts[category],
            }
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            request_index += 1
            if request_index % 20 == 0:
                print(
                    json.dumps(
                        {
                            "requests": request_index,
                            "completion_tokens": sum(counts.values()),
                            "counts": counts,
                            "elapsed_s": time.time() - started,
                        }
                    ),
                    flush=True,
                )
    print(
        json.dumps(
            {
                "requests": request_index,
                "completion_tokens": sum(counts.values()),
                "counts": counts,
                "quotas": quotas,
                "elapsed_s": time.time() - started,
            },
            indent=2,
        )
    )
    if args.arm_file is not None:
        args.arm_file.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
