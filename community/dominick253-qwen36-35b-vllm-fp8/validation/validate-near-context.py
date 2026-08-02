#!/usr/bin/env python3
"""Run a bounded near-context retrieval and immediate next-request gate."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {body}") from exc


def get_json(url: str, timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def content_from(response: dict[str, Any]) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"invalid chat response shape: {exc}") from exc
    if not isinstance(content, str):
        raise RuntimeError("assistant content is not a string")
    return content.strip()


def build_prompt(line_count: int, sentinel: str) -> str:
    prefix = (
        "This is a long deterministic key-value archive.\n"
        f"The exact retrieval key is {sentinel}.\n"
        "Ignore the neutral records below.\n"
    )
    filler = "\n".join(
        f"Record {index:06d}: alpha beta gamma delta epsilon zeta eta theta."
        for index in range(line_count)
    )
    suffix = (
        "\nEnd of archive. Return only the exact retrieval key stated near the "
        "beginning, with no punctuation or explanation."
    )
    return prefix + filler + suffix


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--configured-max-model-len", type=int, default=262_144)
    parser.add_argument("--target-prompt-tokens", type=int, default=261_800)
    parser.add_argument("--max-output-tokens", type=int, default=32)
    parser.add_argument("--sentinel", default="PR15-NEAR256K-6F2A9C")
    parser.add_argument("--next-sentinel", default="PR15-AFTER256K-READY")
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    if args.configured_max_model_len <= 0 or args.configured_max_model_len > 262_144:
        raise SystemExit("configured model length must be between 1 and the audited 262144 limit")
    if args.target_prompt_tokens <= 0 or args.max_output_tokens <= 0:
        raise SystemExit("token targets must be greater than zero")
    if args.target_prompt_tokens + args.max_output_tokens > args.configured_max_model_len:
        raise SystemExit("target prompt plus maximum output exceeds configured model length")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise SystemExit(f"output directory is not empty: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tokenize_url = f"{args.base_url.rstrip('/')}/tokenize"
    chat_url = f"{args.base_url.rstrip('/')}/v1/chat/completions"
    models_url = f"{args.base_url.rstrip('/')}/v1/models"

    models_response = get_json(models_url, args.timeout)
    matching_models = [
        item
        for item in models_response.get("data", [])
        if isinstance(item, dict) and item.get("id") == args.model
    ]
    if len(matching_models) != 1:
        raise SystemExit(f"served model identity is absent or ambiguous: {args.model}")
    endpoint_max_model_len = matching_models[0].get("max_model_len")
    if endpoint_max_model_len != args.configured_max_model_len:
        raise SystemExit(
            "endpoint max_model_len does not match --configured-max-model-len: "
            f"{endpoint_max_model_len!r} != {args.configured_max_model_len!r}"
        )

    count_cache: dict[int, int] = {}

    def token_count(line_count: int) -> int:
        if line_count not in count_cache:
            payload = {
                "model": args.model,
                "messages": [{"role": "user", "content": build_prompt(line_count, args.sentinel)}],
                "chat_template_kwargs": {"enable_thinking": False},
            }
            response = post_json(tokenize_url, payload, args.timeout)
            count_cache[line_count] = int(response["count"])
        return count_cache[line_count]

    low, high = 0, 1024
    if token_count(low) > args.target_prompt_tokens:
        raise SystemExit("target prompt length is smaller than the fixed prompt envelope")
    while token_count(high) <= args.target_prompt_tokens:
        low, high = high, high * 2
    while low + 1 < high:
        middle = (low + high) // 2
        if token_count(middle) <= args.target_prompt_tokens:
            low = middle
        else:
            high = middle

    prompt = build_prompt(low, args.sentinel)
    prompt_tokens = token_count(low)
    if prompt_tokens > args.target_prompt_tokens:
        raise RuntimeError("prompt-size search exceeded its requested token target")
    if prompt_tokens + args.max_output_tokens > args.configured_max_model_len:
        raise RuntimeError("actual prompt plus maximum output exceeds configured model length")
    prompt_path = args.output_dir / "near-context-prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    request_payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": args.max_output_tokens,
        "temperature": 0,
        "seed": 1,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    (args.output_dir / "near-context-request.json").write_text(
        json.dumps(request_payload, indent=2) + "\n", encoding="utf-8"
    )
    started = time.monotonic()
    response = post_json(chat_url, request_payload, args.timeout)
    elapsed = time.monotonic() - started
    (args.output_dir / "near-context-response.json").write_text(
        json.dumps(response, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    retrieval_content = content_from(response)
    finish_reason = response["choices"][0].get("finish_reason")
    response_model = response.get("model")
    usage = response.get("usage") or {}
    usage_prompt_tokens = usage.get("prompt_tokens")
    usage_completion_tokens = usage.get("completion_tokens")
    usage_total_tokens = usage.get("total_tokens")
    retrieval_pass = (
        retrieval_content == args.sentinel
        and finish_reason == "stop"
        and response_model == args.model
        and usage_prompt_tokens == prompt_tokens
        and isinstance(usage_completion_tokens, int)
        and 0 < usage_completion_tokens <= args.max_output_tokens
        and usage_total_tokens == usage_prompt_tokens + usage_completion_tokens
    )

    next_payload = {
        "model": args.model,
        "messages": [
            {
                "role": "user",
                "content": f"Reply with exactly {args.next_sentinel}.",
            }
        ],
        "max_tokens": 32,
        "temperature": 0,
        "seed": 1,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    (args.output_dir / "next-request.json").write_text(
        json.dumps(next_payload, indent=2) + "\n", encoding="utf-8"
    )
    next_tokenize_response = post_json(
        tokenize_url,
        {
            "model": args.model,
            "messages": next_payload["messages"],
            "chat_template_kwargs": next_payload["chat_template_kwargs"],
        },
        args.timeout,
    )
    next_prompt_tokens = int(next_tokenize_response["count"])
    next_started = time.monotonic()
    next_response = post_json(chat_url, next_payload, args.timeout)
    next_elapsed = time.monotonic() - next_started
    (args.output_dir / "next-response.json").write_text(
        json.dumps(next_response, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    next_content = content_from(next_response)
    next_finish_reason = next_response["choices"][0].get("finish_reason")
    next_response_model = next_response.get("model")
    next_usage = next_response.get("usage") or {}
    next_completion_tokens = next_usage.get("completion_tokens")
    next_pass = (
        next_content == args.next_sentinel
        and next_finish_reason == "stop"
        and next_response_model == args.model
        and next_usage.get("prompt_tokens") == next_prompt_tokens
        and isinstance(next_completion_tokens, int)
        and 0 < next_completion_tokens <= next_payload["max_tokens"]
        and next_usage.get("total_tokens") == next_prompt_tokens + next_completion_tokens
    )

    summary = {
        "schema": "community-near-context-gate-v1",
        "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "base_url": args.base_url,
        "model": args.model,
        "configured_max_model_len": args.configured_max_model_len,
        "endpoint_max_model_len": endpoint_max_model_len,
        "target_prompt_tokens": args.target_prompt_tokens,
        "actual_prompt_tokens": prompt_tokens,
        "max_output_tokens": args.max_output_tokens,
        "reserved_prompt_plus_max_output_tokens": prompt_tokens + args.max_output_tokens,
        "line_count": low,
        "prompt_bytes": len(prompt.encode("utf-8")),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "sentinel": args.sentinel,
        "retrieval_content": retrieval_content,
        "retrieval_finish_reason": finish_reason,
        "retrieval_response_model": response_model,
        "retrieval_elapsed_seconds": elapsed,
        "retrieval_usage": response.get("usage"),
        "retrieval_pass": retrieval_pass,
        "next_sentinel": args.next_sentinel,
        "next_content": next_content,
        "next_finish_reason": next_finish_reason,
        "next_response_model": next_response_model,
        "next_expected_prompt_tokens": next_prompt_tokens,
        "next_elapsed_seconds": next_elapsed,
        "next_usage": next_usage,
        "next_request_pass": next_pass,
        "overall_pass": retrieval_pass and next_pass,
    }
    summary_path = args.output_dir / "near-context-summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
