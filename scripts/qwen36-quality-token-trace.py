#!/usr/bin/env python3
"""Token-level trace for Qwen3.6 quality prompts.

This is a diagnostic companion to qwen36-text-quality-suite.py. It builds the
same exact, repeat, and long-context prompts, records output token IDs with the
selected tokenizer, and optionally compares against an accepted baseline JSON.

It is intended for verifier-preserving speculative decoding work, where final
quality failures are rare and the useful question is "where did the output first
diverge from the accepted path?"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any


def post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(url: str, timeout: int) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def repeated_token_text(tokenizer: Any, target_tokens: int, seed_text: str) -> str:
    ids = tokenizer.encode(seed_text, add_special_tokens=False)
    if not ids:
        raise ValueError("seed text produced no tokens")
    repeated = (ids * ((target_tokens + len(ids) - 1) // len(ids)))[:target_tokens]
    return tokenizer.decode(repeated, skip_special_tokens=True)


def make_cases(tokenizer: Any, long_context_tokens: int) -> list[dict[str, Any]]:
    exact_cases = [
        {
            "name": "exact_ok",
            "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
            "max_tokens": 8,
        },
        {
            "name": "copy_phrase",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Copy this exact phrase and nothing else:\n"
                        "satin cobalt orbit"
                    ),
                }
            ],
            "max_tokens": 16,
        },
        {
            "name": "arithmetic",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "There are 9 crates. Each crate has 7 bolts. "
                        "Three bolts are discarded. Answer only the final number."
                    ),
                }
            ],
            "max_tokens": 16,
        },
        {
            "name": "json_schema",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Return only compact JSON with keys answer and unit. "
                        "Question: 12 plus 30. Unit: widgets."
                    ),
                }
            ],
            "max_tokens": 64,
        },
        {
            "name": "repeat_colors",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Give exactly four comma-separated lowercase color words, "
                        "sorted alphabetically, with no extra text."
                    ),
                }
            ],
            "max_tokens": 32,
        },
    ]

    needle = "B70_QWEN36_NEEDLE_20260609"
    first = repeated_token_text(
        tokenizer,
        long_context_tokens // 2,
        "Long context quality filler about scheduling kernels and preserving semantics. ",
    )
    second = repeated_token_text(
        tokenizer,
        max(1, long_context_tokens - long_context_tokens // 2),
        "Additional filler text about graph replay, collectives, and stable output. ",
    )
    prompt = (
        f"{first}\n\nImportant needle: {needle}\n\n{second}\n\n"
        "Question: what is the exact needle string? Answer only the string."
    )
    exact_cases.append({
        "name": "long_context_needle",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 64,
        "needle": needle,
        "requested_context_tokens": long_context_tokens,
    })
    return exact_cases


def chat_completion(
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    timeout: int,
    seed: int,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0,
        "top_p": 1.0,
        "seed": seed,
    }
    started = time.perf_counter()
    data = post_json(f"{base_url.rstrip('/')}/v1/chat/completions", payload, timeout)
    elapsed = time.perf_counter() - started
    content = data["choices"][0]["message"].get("content") or ""
    return {
        "content": content,
        "normalized": normalize(content),
        "sha256": sha256_text(normalize(content)),
        "elapsed_s": elapsed,
        "usage": data.get("usage"),
        "finish_reason": data["choices"][0].get("finish_reason"),
    }


def first_token_diff(a: list[int], b: list[int]) -> dict[str, Any]:
    limit = min(len(a), len(b))
    for index in range(limit):
        if a[index] != b[index]:
            return {
                "index": index,
                "a": a[index],
                "b": b[index],
                "a_context": a[max(0, index - 8):index + 8],
                "b_context": b[max(0, index - 8):index + 8],
            }
    if len(a) != len(b):
        return {
            "index": limit,
            "a": None if len(a) == limit else a[limit],
            "b": None if len(b) == limit else b[limit],
            "a_len": len(a),
            "b_len": len(b),
        }
    return {"index": None}


def trace_case(
    base_url: str,
    model: str,
    tokenizer: Any,
    case: dict[str, Any],
    timeout: int,
    seed: int,
) -> dict[str, Any]:
    result = chat_completion(
        base_url,
        model,
        case["messages"],
        case["max_tokens"],
        timeout,
        seed,
    )
    prompt_text = "\n".join(message["content"] for message in case["messages"])
    prompt_token_ids = tokenizer.encode(prompt_text, add_special_tokens=False)
    output_token_ids = tokenizer.encode(result["normalized"], add_special_tokens=False)
    return {
        "name": case["name"],
        "seed": seed,
        "max_tokens": case["max_tokens"],
        "prompt_sha256": sha256_text(prompt_text),
        "prompt_token_count": len(prompt_token_ids),
        "prompt_token_ids_head": prompt_token_ids[:32],
        "prompt_token_ids_tail": prompt_token_ids[-32:],
        "needle": case.get("needle"),
        "requested_context_tokens": case.get("requested_context_tokens"),
        **result,
        "output_token_count": len(output_token_ids),
        "output_token_ids": output_token_ids,
    }


def baseline_cases(baseline: dict[str, Any], tokenizer: Any) -> dict[str, dict[str, Any]]:
    if "cases" in baseline:
        return {item["name"]: item for item in baseline["cases"]}

    items: dict[str, dict[str, Any]] = {}
    for item in baseline.get("exact_cases", []):
        output_ids = tokenizer.encode(item.get("normalized", ""), add_special_tokens=False)
        items[item["name"]] = {**item, "output_token_ids": output_ids}
    repeat = baseline.get("repeat_case")
    if repeat and repeat.get("runs"):
        first = repeat["runs"][0]
        output_ids = tokenizer.encode(first.get("normalized", ""), add_special_tokens=False)
        items["repeat_colors"] = {**first, "name": "repeat_colors",
                                  "output_token_ids": output_ids}
    long_case = baseline.get("long_context_case")
    if long_case:
        output_ids = tokenizer.encode(long_case.get("normalized", ""),
                                      add_special_tokens=False)
        items["long_context_needle"] = {
            **long_case,
            "name": "long_context_needle",
            "output_token_ids": output_ids,
        }
    return items


def compare_to_baseline(
    cases: list[dict[str, Any]],
    baseline_path: Path | None,
    tokenizer: Any,
) -> dict[str, Any]:
    if baseline_path is None:
        return {}
    baseline = json.loads(baseline_path.read_text())
    prior_cases = baseline_cases(baseline, tokenizer)
    comparisons: dict[str, Any] = {}
    for item in cases:
        prior = prior_cases.get(item["name"])
        key = item["name"]
        comparisons[key] = {"present": prior is not None}
        if prior is None:
            continue
        prior_ids = prior.get("output_token_ids") or []
        current_ids = item.get("output_token_ids") or []
        comparisons[key].update({
            "same_normalized": item.get("normalized") == prior.get("normalized"),
            "same_sha256": item.get("sha256") == prior.get("sha256"),
            "same_output_token_ids": current_ids == prior_ids,
            "first_token_diff": first_token_diff(current_ids, prior_ids),
            "current_normalized": item.get("normalized"),
            "baseline_normalized": prior.get("normalized"),
        })
    return comparisons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default=None)
    parser.add_argument("--tokenizer", required=True)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--seed", type=int, default=20260609)
    parser.add_argument("--long-context-tokens", type=int, default=8192)
    parser.add_argument("--repeat-runs", type=int, default=1)
    parser.add_argument("--baseline-json", type=Path)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    from transformers import AutoTokenizer

    base_url = args.base_url.rstrip("/")
    model = args.model
    if model is None:
        models = get_json(f"{base_url}/v1/models", args.timeout)
        model = models["data"][0]["id"]
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, trust_remote_code=True)

    cases = []
    seed = args.seed
    for case in make_cases(tokenizer, args.long_context_tokens):
        runs = args.repeat_runs if case["name"] == "repeat_colors" else 1
        for repeat_idx in range(runs):
            traced = trace_case(
                base_url,
                model,
                tokenizer,
                case,
                args.timeout,
                seed + repeat_idx,
            )
            if runs > 1:
                traced["repeat_idx"] = repeat_idx
            cases.append(traced)
        seed += 1000

    output = {
        "base_url": base_url,
        "model": model,
        "tokenizer": args.tokenizer,
        "seed": args.seed,
        "cases": cases,
        "baseline_json": str(args.baseline_json) if args.baseline_json else None,
        "baseline_comparisons": compare_to_baseline(
            cases, args.baseline_json, tokenizer),
    }
    output["baseline_match_all"] = all(
        value.get("same_output_token_ids", False)
        for value in output["baseline_comparisons"].values()
    ) if output["baseline_comparisons"] else None

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, indent=2) + "\n")
    summary = {
        "base_url": base_url,
        "model": model,
        "cases": len(cases),
        "baseline_match_all": output["baseline_match_all"],
        "output_json": str(args.output_json),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
