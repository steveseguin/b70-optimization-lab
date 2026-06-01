#!/usr/bin/env python3
"""Run a small quality smoke against an OpenAI-compatible endpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_PROMPTS = [
    (
        "You are a precise assistant. Answer in three short numbered points. "
        "Explain why tensor parallel inference can be communication-bound on "
        "four PCIe GPUs, and include one concrete mitigation that preserves "
        "model quality."
    ),
    (
        "A user asks whether speculative decoding can change answer quality. "
        "Give a concise, technically accurate answer and mention one validation "
        "step before publishing a benchmark."
    ),
    (
        "Write a short Python function named median_latency_ms that accepts a "
        "list of floating point seconds and returns the median in milliseconds. "
        "Include only the function."
    ),
]


def post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def get_json(url: str, timeout: float) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read())


def text_quality_stats(text: str) -> dict[str, Any]:
    printable_chars = sum(
        1 for char in text if char.isprintable() and not char.isspace()
    )
    control_nonspace_chars = sum(
        1 for char in text if not char.isprintable() and not char.isspace()
    )
    return {
        "chars": len(text),
        "printable_nonspace_text_chars": printable_chars,
        "control_nonspace_text_chars": control_nonspace_chars,
        "nul_char_count": text.count("\x00"),
        "nontrivial_text": printable_chars > 0,
        "control_char_output": control_nonspace_chars > 0 or "\x00" in text,
    }


def parse_prompt_requirement(raw: str) -> tuple[int, str]:
    prefix, sep, value = raw.partition(":")
    if not sep:
        raise ValueError(f"missing ':' separator in {raw!r}")
    index = int(prefix)
    if index < 0:
        raise ValueError("prompt index must be non-negative")
    return index, value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18082")
    parser.add_argument("--model", default=None)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--prompt", action="append", default=None)
    parser.add_argument("--require-prompt-substring", action="append", default=[])
    parser.add_argument("--require-prompt-regex", action="append", default=[])
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    model = args.model
    if model is None:
        models = get_json(f"{base_url}/v1/models", args.timeout)
        model = models["data"][0]["id"]

    prompts = args.prompt or DEFAULT_PROMPTS
    substring_requirements = [
        parse_prompt_requirement(raw) for raw in args.require_prompt_substring
    ]
    regex_requirements = [
        (index, re.compile(pattern, flags=re.MULTILINE))
        for index, pattern in (
            parse_prompt_requirement(raw) for raw in args.require_prompt_regex
        )
    ]

    started = time.perf_counter()
    prompt_records = []
    failure_reasons = []
    for index, prompt in enumerate(prompts):
        response = post_json(
            f"{base_url}/v1/chat/completions",
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": args.max_tokens,
            },
            args.timeout,
        )
        message = response["choices"][0]["message"]
        content = message.get("content") or ""
        reasoning = (
            message.get("reasoning")
            or message.get("reasoning_content")
            or message.get("reasoning_text")
            or ""
        )
        text = content if content.strip() else reasoning
        quality = text_quality_stats(text)
        prompt_records.append(
            {
                "prompt_index": index,
                "text": text,
                "content": content,
                "reasoning": reasoning,
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "quality": quality,
                "usage": response.get("usage"),
            }
        )
        if not quality["nontrivial_text"]:
            failure_reasons.append(f"prompt {index}: no printable text")
        if quality["control_char_output"]:
            failure_reasons.append(f"prompt {index}: control or NUL output")

    for index, substring in substring_requirements:
        if index >= len(prompt_records) or substring not in prompt_records[index]["text"]:
            failure_reasons.append(f"prompt {index}: missing substring {substring!r}")
    for index, pattern in regex_requirements:
        if index >= len(prompt_records) or not pattern.search(
            prompt_records[index]["text"]
        ):
            failure_reasons.append(f"prompt {index}: missing regex {pattern.pattern!r}")

    combined_text = "\n---\n".join(record["text"] for record in prompt_records)
    record = {
        "base_url": base_url,
        "model": model,
        "elapsed_s": time.perf_counter() - started,
        "combined_text_sha256": hashlib.sha256(combined_text.encode()).hexdigest(),
        "passed": not failure_reasons,
        "failure_reasons": failure_reasons,
        "prompts": prompts,
        "prompt_records": prompt_records,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n")
    print(
        json.dumps(
            {
                "passed": record["passed"],
                "failure_reasons": failure_reasons,
                "combined_text_sha256": record["combined_text_sha256"],
                "elapsed_s": record["elapsed_s"],
            },
            indent=2,
        )
    )
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
