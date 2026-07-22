#!/usr/bin/env python3
"""Live tokenizer and fresh greedy correctness gate for Laguna."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

from transformers import AutoTokenizer


TOKEN_PROBES = [
    "camelCase HTTPServer XMLParser snake_case",
    "don't we're I'll you've wouldn't",
    "naïve café 東京 ✓ emoji🙂",
    "line one\nline two\n\nparagraph three\r\nlast",
    'def helloWorld(x: int) -> str:\n    return f"Value={x}"',
    "/東京.\n/_",
]

DETERMINISM_PROMPT = (
    "Write a Python function named merge_intervals that merges overlapping closed "
    "integer intervals. Include type hints, do not mutate the input, and give two "
    "assert-based examples."
)

QUALITY_PROMPTS = [
    (
        "coding-merge",
        DETERMINISM_PROMPT,
        ("merge_intervals", "def ", "assert"),
    ),
    (
        "coding-debug",
        "Fix this Python function and explain both bugs: def mean(xs): return "
        "sum(xs) // len(xs). It must support floats and reject an empty input. "
        "Include focused tests.",
        ("def mean", "ValueError", "/"),
    ),
    (
        "coding-sql",
        "Write a PostgreSQL query that returns the latest order per customer from "
        "orders(customer_id, order_id, created_at, total), deterministically breaking "
        "timestamp ties by the greatest order_id. Explain the index you would add.",
        ("customer_id", "order_id", "index"),
    ),
    (
        "arithmetic",
        "Compute 137 * 29, subtract 845, then divide the remainder by 23. Show the "
        "quotient and leftover and verify the multiplication.",
        ("3973", "3128", "136"),
    ),
    (
        "factual",
        "What is the capital of Canada? Name the city, the province it is in, and "
        "distinguish it from Canada's most populous city.",
        ("Ottawa", "Ontario", "Toronto"),
    ),
]


def post(base_url: str, route: str, payload: dict) -> dict:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/{route.lstrip('/')}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=900) as response:
        return json.load(response)


def cached_tokens(response: dict) -> int | None:
    return (
        response.get("usage", {})
        .get("prompt_tokens_details", {})
        .get("cached_tokens")
    )


def completion(base_url: str, model: str, prompt: str, max_tokens: int) -> dict:
    response = post(
        base_url,
        "/v1/chat/completions",
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "top_p": 1,
            "seed": 1,
            "max_tokens": max_tokens,
            "return_token_ids": True,
            "chat_template_kwargs": {"enable_thinking": False},
        },
    )
    choice = response["choices"][0]
    text = choice["message"].get("content") or choice["message"].get("reasoning") or ""
    token_ids = choice.get("token_ids") or []
    return {
        "text": text,
        "token_ids": token_ids,
        "output_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "cached_tokens": cached_tokens(response),
        "usage": response.get("usage"),
        "finish_reason": choice.get("finish_reason"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--model", default="laguna-s-2.1-int4")
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(
        args.model_path, local_files_only=True, fix_mistral_regex=True
    )
    tokenizer_rows = []
    for text in TOKEN_PROBES:
        expected = tokenizer.encode(text, add_special_tokens=False)
        actual = post(
            args.base_url,
            "/tokenize",
            {"model": args.model, "prompt": text, "add_special_tokens": False},
        )["tokens"]
        decoded = post(
            args.base_url,
            "/detokenize",
            {"model": args.model, "tokens": actual},
        )["prompt"]
        tokenizer_rows.append(
            {
                "text": text,
                "ids": actual,
                "ids_equal": actual == expected,
                "roundtrip_equal": decoded == text,
            }
        )

    deterministic = [
        completion(args.base_url, args.model, DETERMINISM_PROMPT, 128)
        for _ in range(3)
    ]
    determinism_pass = (
        len({tuple(row["token_ids"]) for row in deterministic}) == 1
        and len({row["output_sha256"] for row in deterministic}) == 1
        and all(row["cached_tokens"] == 0 for row in deterministic)
    )

    quality_rows = []
    for prompt_id, prompt, required in QUALITY_PROMPTS:
        row = completion(args.base_url, args.model, prompt, 192)
        lowered = row["text"].lower()
        row.update(
            {
                "prompt_id": prompt_id,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "required_fragments": required,
                "required_fragments_present": all(
                    fragment.lower() in lowered for fragment in required
                ),
                "coherent_shape": (
                    len(row["text"]) >= 80
                    and "�" not in row["text"]
                    and len(set(row["text"])) >= 20
                ),
            }
        )
        quality_rows.append(row)

    passed = (
        all(row["ids_equal"] and row["roundtrip_equal"] for row in tokenizer_rows)
        and determinism_pass
        and all(
            row["cached_tokens"] == 0
            and row["required_fragments_present"]
            and row["coherent_shape"]
            for row in quality_rows
        )
    )
    result = {
        "status": "PASS" if passed else "FAIL",
        "tokenizer": {"status": "PASS" if all(r["ids_equal"] and r["roundtrip_equal"] for r in tokenizer_rows) else "FAIL", "rows": tokenizer_rows},
        "determinism": {"status": "PASS" if determinism_pass else "FAIL", "rows": deterministic},
        "quality": {"status": "PASS" if all(r["cached_tokens"] == 0 and r["required_fragments_present"] and r["coherent_shape"] for r in quality_rows) else "FAIL", "rows": quality_rows},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": result["status"],
        "tokenizer": result["tokenizer"]["status"],
        "determinism": result["determinism"]["status"],
        "quality": result["quality"]["status"],
        "determinism_hashes": [r["output_sha256"] for r in deterministic],
        "quality_hashes": [r["output_sha256"] for r in quality_rows],
    }, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
