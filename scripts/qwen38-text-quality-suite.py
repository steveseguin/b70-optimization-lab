#!/usr/bin/env python3
"""Text-only quality checks for Qwen3.8 OpenAI-compatible endpoints.

The suite is intended for speed candidates where model quality must not change.
It keeps checks deterministic and machine-readable:

- short exact-answer, arithmetic, factual, logic, and code canaries;
- JSON parse/schema canary;
- same-prompt repeat hash stability;
- long-context needle recall.

Use --baseline-json to require exact normalized-output/hash parity with a prior
run, for example a BF16 fallback or a known-good optimized profile.
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


def post_json(
    url: str,
    payload: dict[str, Any],
    timeout: int,
    *,
    request_id: str | None = None,
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if request_id:
        headers["X-Request-Id"] = request_id
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
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


def extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    candidates = [stripped]
    match = re.search(r"\{.*\}", stripped, flags=re.S)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def chat_completion(
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    timeout: int,
    *,
    seed: int,
    chat_template_kwargs: dict[str, Any] | None,
    request_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0,
        "top_p": 1.0,
        "seed": seed,
    }
    if chat_template_kwargs is not None:
        payload["chat_template_kwargs"] = chat_template_kwargs
    started = time.perf_counter()
    data = post_json(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        payload,
        timeout,
        request_id=request_id,
    )
    elapsed = time.perf_counter() - started
    content = data["choices"][0]["message"].get("content") or ""
    return {
        "request_id": request_id,
        "content": content,
        "normalized": normalize(content),
        "sha256": sha256_text(normalize(content)),
        "elapsed_s": elapsed,
        "usage": data.get("usage"),
    }


def make_exact_cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "exact_ok",
            "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
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
                }
            ],
            "max_tokens": 16,
            "expected": "satin cobalt orbit",
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
            "expected": "60",
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
            "json_expected_fields": {"answer": "42", "unit": "widgets"},
        },
        {
            "name": "factual",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "What is the chemical symbol for gold? "
                        "Answer with only the symbol."
                    ),
                }
            ],
            "max_tokens": 8,
            "expected": "Au",
        },
        {
            "name": "logic",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "All cobalt widgets are metal. Widget Z is cobalt. "
                        "Is Widget Z metal? Answer only yes or no."
                    ),
                }
            ],
            "max_tokens": 8,
            "expected": "yes",
        },
        {
            "name": "code_execution",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "What does this Python expression evaluate to? "
                        "Answer only the integer: sum(i * i for i in range(4))"
                    ),
                }
            ],
            "max_tokens": 8,
            "expected": "14",
        },
    ]


def run_exact_cases(
    base_url: str,
    model: str,
    timeout: int,
    seed: int,
    chat_template_kwargs: dict[str, Any] | None,
    request_delay_s: float,
    request_id_prefix: str,
) -> list[dict[str, Any]]:
    results = []
    for index, case in enumerate(make_exact_cases()):
        result = chat_completion(
            base_url,
            model,
            case["messages"],
            case["max_tokens"],
            timeout,
            seed=seed + index,
            chat_template_kwargs=chat_template_kwargs,
            request_id=f"{request_id_prefix}-exact-{index:02d}-{case['name']}",
        )
        if request_delay_s > 0:
            time.sleep(request_delay_s)
        item = {
            "name": case["name"],
            **result,
            "expected": case.get("expected"),
            "json_expected_fields": case.get("json_expected_fields"),
            "pass": False,
        }
        if "expected" in case:
            item["pass"] = result["normalized"] == case["expected"]
        else:
            parsed = extract_json_object(result["content"])
            item["json_parsed"] = parsed
            expected_fields = case["json_expected_fields"]
            item["pass"] = isinstance(parsed, dict) and all(
                str(parsed.get(key)) == expected
                for key, expected in expected_fields.items()
            )
        results.append(item)
    return results


def run_repeat_case(
    base_url: str,
    model: str,
    timeout: int,
    seed: int,
    repeats: int,
    chat_template_kwargs: dict[str, Any] | None,
    request_delay_s: float,
    request_id_prefix: str,
) -> dict[str, Any]:
    expected = "blue, green, red, yellow"
    prompt = (
        "Sort exactly these four color words alphabetically and reply "
        "with only the comma-separated lowercase list: "
        "yellow, red, green, blue"
    )
    messages = [
        {
            "role": "user",
            "content": prompt,
        }
    ]
    runs = []
    for index in range(repeats):
        runs.append(chat_completion(
            base_url,
            model,
            messages,
            32,
            timeout,
            seed=seed,
            chat_template_kwargs=chat_template_kwargs,
            request_id=f"{request_id_prefix}-repeat-{index:04d}",
        ))
        if request_delay_s > 0:
            time.sleep(request_delay_s)
    hashes = [item["sha256"] for item in runs]
    texts = [item["normalized"] for item in runs]
    return {
        "name": "repeat_hash_stability",
        "protocol": "fixed-set-v2",
        "prompt": prompt,
        "repeats": repeats,
        "hashes": hashes,
        "texts": texts,
        "expected": expected,
        "unique_hashes": sorted(set(hashes)),
        "pass": len(set(hashes)) == 1 and all(text == expected for text in texts),
        "runs": runs,
    }


def repeated_token_text(tokenizer: Any, target_tokens: int, seed_text: str) -> str:
    ids = tokenizer.encode(seed_text, add_special_tokens=False)
    if not ids:
        raise ValueError("seed text produced no tokens")
    repeated = (ids * ((target_tokens + len(ids) - 1) // len(ids)))[:target_tokens]
    return tokenizer.decode(repeated, skip_special_tokens=True)


def run_long_context_case(
    base_url: str,
    model: str,
    tokenizer_path: str,
    timeout: int,
    seed: int,
    target_tokens: int,
    chat_template_kwargs: dict[str, Any] | None,
    request_id_prefix: str,
) -> dict[str, Any]:
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, trust_remote_code=True)
    needle = "B70_QWEN38_NEEDLE_20260816"
    first = repeated_token_text(
        tokenizer,
        target_tokens // 2,
        "Long context quality filler about scheduling kernels and preserving semantics. ",
    )
    second = repeated_token_text(
        tokenizer,
        max(1, target_tokens - target_tokens // 2),
        "Additional filler text about graph replay, collectives, and stable output. ",
    )
    prompt = (
        f"{first}\n\nImportant needle: {needle}\n\n{second}\n\n"
        "Question: what is the exact needle string? Answer only the string."
    )
    actual_prompt_tokens = len(tokenizer.encode(prompt, add_special_tokens=False))
    result = chat_completion(
        base_url,
        model,
        [{"role": "user", "content": prompt}],
        64,
        timeout,
        seed=seed,
        chat_template_kwargs=chat_template_kwargs,
        request_id=f"{request_id_prefix}-long-context",
    )
    return {
        "name": "long_context_needle",
        "requested_context_tokens": target_tokens,
        "actual_prompt_tokens": actual_prompt_tokens,
        "needle": needle,
        **result,
        "pass": needle in result["normalized"],
    }


def compare_to_baseline(current: dict[str, Any], baseline_path: Path | None) -> dict[str, Any]:
    if baseline_path is None:
        return {}
    baseline = json.loads(baseline_path.read_text())
    comparisons: dict[str, Any] = {}

    base_exact = {item["name"]: item for item in baseline.get("exact_cases", [])}
    for item in current.get("exact_cases", []):
        prior = base_exact.get(item["name"])
        comparisons[f"exact:{item['name']}:present"] = prior is not None
        if prior is not None:
            comparisons[f"exact:{item['name']}:same_normalized"] = (
                item["normalized"] == prior.get("normalized")
            )
            comparisons[f"exact:{item['name']}:same_hash"] = (
                item["sha256"] == prior.get("sha256")
            )

    prior_repeat = baseline.get("repeat_case", {})
    current_repeat = current.get("repeat_case", {})
    if prior_repeat:
        comparisons["repeat:protocol_same"] = (
            current_repeat.get("protocol", "open-choice-v1")
            == prior_repeat.get("protocol", "open-choice-v1")
        )
        comparisons["repeat:all_hashes_same"] = (
            current_repeat.get("unique_hashes")
            == prior_repeat.get("unique_hashes")
        )
        comparisons["repeat:aggregate_pass_same"] = (
            current_repeat.get("pass") == prior_repeat.get("pass")
        )

    prior_long = baseline.get("long_context_case")
    current_long = current.get("long_context_case")
    if prior_long and current_long:
        comparisons["long_context:same_hash"] = (
            current_long.get("sha256") == prior_long.get("sha256")
        )
        comparisons["long_context:same_pass"] = (
            current_long.get("pass") == prior_long.get("pass")
        )

    return comparisons


def baseline_result(
    comparisons: dict[str, Any], baseline_requested: bool
) -> tuple[str, bool | None]:
    """Return an explicit baseline status without treating an empty set as a pass."""
    if not baseline_requested:
        return "not_run", None
    matched = bool(comparisons) and all(comparisons.values())
    return ("passed" if matched else "failed"), matched


def quality_exit_code(
    pass_all: bool, baseline_match_all: bool | None, require_baseline: bool
) -> int:
    if not pass_all:
        return 1
    if require_baseline:
        return 0 if baseline_match_all is True else 1
    return 0 if baseline_match_all is not False else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default=None)
    parser.add_argument("--tokenizer", required=True)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--seed", type=int, default=20260609)
    parser.add_argument("--repeat-runs", type=int, default=8)
    parser.add_argument(
        "--request-id-prefix",
        default="qwen38-quality",
        help="Prefix for deterministic X-Request-Id headers used by trace filters.",
    )
    parser.add_argument(
        "--request-delay-s",
        type=float,
        default=0.0,
        help="Sleep after each short chat request; useful for slot-reuse race probes.",
    )
    parser.add_argument("--long-context-tokens", type=int, default=8192)
    parser.add_argument("--skip-long-context", action="store_true")
    parser.add_argument("--baseline-json", type=Path, default=None)
    parser.add_argument(
        "--require-baseline",
        action="store_true",
        help="Fail unless --baseline-json is supplied and every comparison matches.",
    )
    parser.add_argument(
        "--chat-template-kwargs-json",
        default=None,
        help='JSON object passed as chat_template_kwargs, e.g. {"enable_thinking": false}',
    )
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    if args.require_baseline and args.baseline_json is None:
        parser.error("--require-baseline requires --baseline-json")

    base_url = args.base_url.rstrip("/")
    model = args.model
    if model is None:
        models = get_json(f"{base_url}/v1/models", args.timeout)
        model = models["data"][0]["id"]
    chat_template_kwargs = None
    if args.chat_template_kwargs_json:
        parsed = json.loads(args.chat_template_kwargs_json)
        if not isinstance(parsed, dict):
            raise SystemExit("--chat-template-kwargs-json must decode to an object")
        chat_template_kwargs = parsed

    output: dict[str, Any] = {
        "base_url": base_url,
        "model": model,
        "tokenizer": args.tokenizer,
        "chat_template_kwargs": chat_template_kwargs,
        "request_delay_s": args.request_delay_s,
        "request_id_prefix": args.request_id_prefix,
        "seed": args.seed,
        "exact_cases": run_exact_cases(
            base_url,
            model,
            args.timeout,
            args.seed,
            chat_template_kwargs,
            args.request_delay_s,
            args.request_id_prefix,
        ),
        "repeat_case": run_repeat_case(
            base_url,
            model,
            args.timeout,
            args.seed + 1000,
            args.repeat_runs,
            chat_template_kwargs,
            args.request_delay_s,
            args.request_id_prefix,
        ),
        "long_context_case": None,
    }
    if not args.skip_long_context:
        output["long_context_case"] = run_long_context_case(
            base_url,
            model,
            args.tokenizer,
            args.timeout,
            args.seed + 2000,
            args.long_context_tokens,
            chat_template_kwargs,
            args.request_id_prefix,
        )

    checks = [item["pass"] for item in output["exact_cases"]]
    checks.append(output["repeat_case"]["pass"])
    if output["long_context_case"] is not None:
        checks.append(output["long_context_case"]["pass"])
    output["pass_all"] = all(checks)
    output["baseline_comparisons"] = compare_to_baseline(output, args.baseline_json)
    output["baseline_status"], output["baseline_match_all"] = baseline_result(
        output["baseline_comparisons"], args.baseline_json is not None
    )

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, indent=2) + "\n")

    print(
        json.dumps(
            {
                "base_url": base_url,
                "model": model,
                "pass_all": output["pass_all"],
                "baseline_status": output["baseline_status"],
                "baseline_match_all": output["baseline_match_all"],
                "exact": {item["name"]: item["pass"] for item in output["exact_cases"]},
                "repeat_pass": output["repeat_case"]["pass"],
                "long_context_pass": (
                    None
                    if output["long_context_case"] is None
                    else output["long_context_case"]["pass"]
                ),
                "output_json": str(args.output_json),
            },
            sort_keys=True,
        )
    )
    return quality_exit_code(
        output["pass_all"], output["baseline_match_all"], args.require_baseline
    )


if __name__ == "__main__":
    raise SystemExit(main())
