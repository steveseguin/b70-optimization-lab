#!/usr/bin/env python3
"""Small deterministic canary suite for an OpenAI-compatible endpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path
from typing import Any


RED_PNG_1X1 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/"
    "pLvAAAAAElFTkSuQmCC"
)


def post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def make_cases() -> list[dict[str, Any]]:
    red_data_url = f"data:image/png;base64,{RED_PNG_1X1}"
    return [
        {
            "name": "exact_ok",
            "messages": [
                {"role": "user", "content": "Reply with exactly: OK"},
            ],
            "max_tokens": 8,
            "expected": "OK",
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
                },
            ],
            "max_tokens": 12,
            "expected": "satin cobalt orbit",
        },
        {
            "name": "small_arithmetic",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "A crate has 3 red cubes and 4 blue cubes. "
                        "Answer only the total number of cubes."
                    ),
                },
            ],
            "max_tokens": 8,
            "expected": "7",
        },
        {
            "name": "red_image",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What color is this image? Answer one word."},
                        {"type": "image_url", "image_url": {"url": red_data_url}},
                    ],
                },
            ],
            "max_tokens": 8,
            "expected_contains": "red",
        },
    ]


def run_case(
    base_url: str,
    model: str,
    case: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": case["messages"],
        "max_tokens": case["max_tokens"],
        "temperature": 0,
        "top_p": 1.0,
        "seed": 20260607,
    }
    started = time.perf_counter()
    data = post_json(f"{base_url.rstrip('/')}/v1/chat/completions", payload, timeout)
    elapsed = time.perf_counter() - started
    content = data["choices"][0]["message"].get("content") or ""
    normalized = content.strip()
    expected = case.get("expected")
    expected_contains = case.get("expected_contains")
    expected_pass = True
    if expected is not None:
        expected_pass = normalized == expected
    if expected_contains is not None:
        expected_pass = expected_contains.lower() in normalized.lower()
    return {
        "name": case["name"],
        "elapsed_s": elapsed,
        "content": content,
        "normalized": normalized,
        "sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "usage": data.get("usage"),
        "expected": expected,
        "expected_contains": expected_contains,
        "expected_pass": expected_pass,
    }


def compare_to_baseline(
    current: dict[str, Any], baseline_path: Path | None
) -> dict[str, Any]:
    if baseline_path is None:
        return {}
    baseline = json.loads(baseline_path.read_text())
    baseline_by_name = {item["name"]: item for item in baseline["results"]}
    comparisons: dict[str, Any] = {}
    for item in current["results"]:
        base_item = baseline_by_name.get(item["name"])
        if base_item is None:
            comparisons[f"{item['name']}_baseline_present"] = False
            continue
        comparisons[f"{item['name']}_same_hash"] = item["sha256"] == base_item["sha256"]
        comparisons[f"{item['name']}_same_text"] = (
            item["normalized"] == base_item["normalized"]
        )
    return comparisons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--baseline-json", type=Path, default=None)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    model = args.model
    if model is None:
        models = json.loads(
            urllib.request.urlopen(
                f"{args.base_url.rstrip('/')}/v1/models", timeout=args.timeout
            )
            .read()
            .decode("utf-8")
        )
        model = models["data"][0]["id"]

    output: dict[str, Any] = {
        "base_url": args.base_url.rstrip("/"),
        "model": model,
        "results": [],
    }
    for case in make_cases():
        item = run_case(args.base_url, model, case, args.timeout)
        output["results"].append(item)
        print(
            json.dumps(
                {
                    "name": item["name"],
                    "expected_pass": item["expected_pass"],
                    "elapsed_s": round(item["elapsed_s"], 3),
                    "normalized": item["normalized"],
                    "sha256": item["sha256"][:16],
                },
                sort_keys=True,
            )
        )

    output["expected_pass_all"] = all(item["expected_pass"] for item in output["results"])
    output["comparisons"] = compare_to_baseline(output, args.baseline_json)
    output["baseline_match_all"] = all(output["comparisons"].values())

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, indent=2) + "\n")
    print(f"wrote {args.output_json}")
    if not output["expected_pass_all"]:
        return 1
    if output["comparisons"] and not output["baseline_match_all"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
