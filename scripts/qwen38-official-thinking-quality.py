#!/usr/bin/env python3
"""Bounded official-mode quality gate for Qwen3.8 Flash-Next.

This is a model-quality screen, not a throughput benchmark. It uses Qwen's
published thinking-mode sampler and requires vLLM to expose parsed reasoning
and final-answer fields separately.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any


OFFICIAL_SAMPLING = {
    "temperature": 1.0,
    "top_p": 0.95,
    "top_k": 20,
    "min_p": 0.0,
    "presence_penalty": 0.0,
    "repetition_penalty": 1.0,
}
SCOUT_ORDER = ["code_execution", "logic", "arithmetic", "copy_phrase"]
GRID_SEEDS = [2026082711, 2026082712, 2026082713]


def cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "exact_ok",
            "prompt": "Reply with exactly: OK",
            "expected": "OK",
            "match": "exact",
        },
        {
            "name": "copy_phrase",
            "prompt": "Copy this exact phrase and nothing else:\nsatin cobalt orbit",
            "expected": "satin cobalt orbit",
            "match": "exact",
        },
        {
            "name": "arithmetic",
            "prompt": (
                "There are 9 crates. Each crate has 7 bolts. Three bolts are "
                "discarded. Answer only the final number."
            ),
            "expected": "60",
            "match": "exact",
        },
        {
            "name": "json_schema",
            "prompt": (
                "Return only compact JSON with keys answer and unit. "
                "Question: 12 plus 30. Unit: widgets."
            ),
            "json_expected_fields": {"answer": "42", "unit": "widgets"},
            "match": "json_fields",
        },
        {
            "name": "factual",
            "prompt": "What is the chemical symbol for gold? Answer with only the symbol.",
            "expected": "Au",
            "match": "exact",
        },
        {
            "name": "logic",
            "prompt": (
                "All cobalt widgets are metal. Widget Z is cobalt. "
                "Is Widget Z metal? Answer only yes or no."
            ),
            "expected": "yes",
            "match": "casefold",
        },
        {
            "name": "code_execution",
            "prompt": (
                "What does this Python expression evaluate to? "
                "Answer only the integer: sum(i * i for i in range(4))"
            ),
            "expected": "14",
            "match": "exact",
        },
    ]


def grid_schedule() -> list[tuple[int, dict[str, Any]]]:
    """Return every prescribed case at each frozen grid seed."""
    return [(seed, case) for seed in GRID_SEEDS for case in cases()]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def extract_json_object(text: str) -> dict[str, Any] | None:
    candidates = [text.strip()]
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def answer_pass(case: dict[str, Any], final: str) -> tuple[bool, Any]:
    normalized = normalize(final)
    match = case["match"]
    if match == "exact":
        return normalized == case["expected"], normalized
    if match == "casefold":
        return normalized.casefold() == case["expected"].casefold(), normalized
    if match == "json_fields":
        parsed = extract_json_object(final)
        expected = case["json_expected_fields"]
        passed = isinstance(parsed, dict) and all(
            str(parsed.get(key)) == value for key, value in expected.items()
        )
        return passed, parsed
    raise ValueError(f"unknown match mode: {match}")


def post_case(
    base_url: str,
    model: str,
    case: dict[str, Any],
    seed: int,
    timeout: int,
    request_id: str,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": case["prompt"]}],
        "max_tokens": 1024,
        **OFFICIAL_SAMPLING,
        "seed": seed,
        "reasoning_effort": "xhigh",
        "chat_template_kwargs": {
            "enable_thinking": True,
            "preserve_thinking": True,
        },
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Request-Id": request_id},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.load(response)
    elapsed = time.perf_counter() - started
    choice = data["choices"][0]
    message = choice["message"]
    reasoning = message.get("reasoning_content") or message.get("reasoning") or ""
    final = message.get("content") or ""
    usage = data.get("usage") or {}
    details = usage.get("prompt_tokens_details") or {}
    semantic_pass, parsed_answer = answer_pass(case, final)
    structural = {
        "reasoning_nonempty": bool(reasoning.strip()),
        "final_nonempty": bool(final.strip()),
        "finish_reason_stop": choice.get("finish_reason") == "stop",
        "cached_tokens_zero": details.get("cached_tokens") == 0,
        "created_cache_tokens_zero": details.get("created_cache_tokens") == 0,
        "usage_complete": (
            isinstance(usage.get("prompt_tokens"), int)
            and isinstance(usage.get("completion_tokens"), int)
            and usage.get("total_tokens")
            == usage.get("prompt_tokens") + usage.get("completion_tokens")
        ),
    }
    return {
        "request_id": request_id,
        "case": case["name"],
        "seed": seed,
        "sampling": OFFICIAL_SAMPLING,
        "reasoning_effort": "xhigh",
        "max_tokens": 1024,
        "elapsed_seconds": elapsed,
        "finish_reason": choice.get("finish_reason"),
        "reasoning": reasoning,
        "final": final,
        "parsed_answer": parsed_answer,
        "semantic_pass": semantic_pass,
        "structural": structural,
        "pass": semantic_pass and all(structural.values()),
        "usage": usage,
    }


def write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--request-id-prefix", default="q38fn-official-quality")
    args = parser.parse_args()

    by_name = {case["name"]: case for case in cases()}
    state: dict[str, Any] = {
        "schema": "qwen38-official-thinking-quality-v1",
        "status": "running",
        "model": args.model,
        "base_url": args.base_url.rstrip("/"),
        "official_sampling": OFFICIAL_SAMPLING,
        "reasoning_effort": "xhigh",
        "max_tokens": 1024,
        "scout_order": SCOUT_ORDER,
        "grid_seeds": GRID_SEEDS,
        "scout": [],
        "grid": [],
    }
    write_state(args.output_json, state)

    try:
        for index, name in enumerate(SCOUT_ORDER):
            result = post_case(
                args.base_url,
                args.model,
                by_name[name],
                2026082701 + index,
                args.timeout,
                f"{args.request_id_prefix}-scout-{index:02d}-{name}",
            )
            state["scout"].append(result)
            write_state(args.output_json, state)
            if not result["pass"]:
                state["status"] = (
                    "inconclusive-output-limit"
                    if result["finish_reason"] == "length"
                    else "failed-scout"
                )
                write_state(args.output_json, state)
                return 1

        for index, (seed, case) in enumerate(grid_schedule()):
            result = post_case(
                args.base_url,
                args.model,
                case,
                seed,
                args.timeout,
                f"{args.request_id_prefix}-grid-{seed}-{index:02d}-{case['name']}",
            )
            state["grid"].append(result)
            write_state(args.output_json, state)
            if not result["pass"]:
                state["status"] = (
                    "inconclusive-output-limit"
                    if result["finish_reason"] == "length"
                    else "failed-grid"
                )
                write_state(args.output_json, state)
                return 1
    except Exception as error:
        state["status"] = "request-error"
        state["error"] = f"{type(error).__name__}: {error}"
        write_state(args.output_json, state)
        raise

    state["status"] = "passed"
    state["scout_passed"] = len(state["scout"]) == 4
    state["grid_passed"] = len(state["grid"]) == 21
    state["all_cached_tokens_zero"] = all(
        row["structural"]["cached_tokens_zero"] for row in state["scout"] + state["grid"]
    )
    state["all_created_cache_tokens_zero"] = all(
        row["structural"]["created_cache_tokens_zero"] for row in state["scout"] + state["grid"]
    )
    write_state(args.output_json, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
