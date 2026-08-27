#!/usr/bin/env python3
"""Compare the historical open-choice repeat with a prescribed-answer repeat.

The client is inert unless ``--execute`` is supplied. The probe changes no
server setting and requests one greedy token plus returned top scores so an
open-choice near tie can be separated from prescribed-answer instability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


SCHEMA = "qwen38-repeat-sensitivity-v1"
DEFAULT_SEED = 20261609
BLUE_TOKEN_ID = 11855
BLACK_TOKEN_ID = 11124
PHASES = {
    "open_choice": (
        "Give exactly four comma-separated lowercase color words, sorted "
        "alphabetically, with no extra text."
    ),
    "fixed_set": (
        "Sort exactly these four color words alphabetically and reply with only "
        "the comma-separated lowercase list: yellow, red, green, blue"
    ),
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def required_named_scores_present(scores: list[dict[str, Any]]) -> bool:
    """Require both explicitly requested comparison tokens in the response."""
    returned = {item.get("token") for item in scores}
    return {"blue", "black"}.issubset(returned)


def validate_base_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base URL must be absolute http(s)")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("base URL cannot contain credentials, query, or fragment")
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "")
    )


def payload(model: str, prompt: str, seed: int) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1,
        "temperature": 0,
        "top_p": 1.0,
        "seed": seed,
        "logprobs": True,
        "top_logprobs": 0,
        "logprob_token_ids": [BLUE_TOKEN_ID, BLACK_TOKEN_ID],
        "chat_template_kwargs": {"enable_thinking": False},
    }


def get_json(url: str, timeout: int) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(
    url: str, body: dict[str, Any], timeout: int, request_id: str
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Request-Id": request_id},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def run_phase(
    base_url: str,
    model: str,
    phase: str,
    repeats: int,
    timeout: int,
    seed: int,
    request_prefix: str,
) -> dict[str, Any]:
    body = payload(model, PHASES[phase], seed)
    runs = []
    for index in range(repeats):
        request_id = f"{request_prefix}-{phase}-{index:04d}"
        started = time.perf_counter()
        response = post_json(
            f"{base_url}/v1/chat/completions", body, timeout, request_id
        )
        elapsed_s = time.perf_counter() - started
        choice = response["choices"][0]
        content = choice["message"].get("content") or ""
        normalized = normalize(content)
        usage = response.get("usage") or {}
        details = usage.get("prompt_tokens_details") or {}
        logprob_content = ((choice.get("logprobs") or {}).get("content") or [])
        first_scores = [] if not logprob_content else logprob_content[0].get(
            "top_logprobs", []
        )
        runs.append(
            {
                "index": index,
                "request_id": request_id,
                "content": content,
                "normalized": normalized,
                "sha256": sha256_text(normalized),
                "elapsed_s": elapsed_s,
                "usage": usage,
                "cached_tokens": details.get("cached_tokens"),
                "first_token": None if not logprob_content else logprob_content[0],
                "first_token_top_scores": first_scores,
            }
        )
    counts: dict[str, int] = {}
    for item in runs:
        counts[item["normalized"]] = counts.get(item["normalized"], 0) + 1
    return {
        "phase": phase,
        "prompt": PHASES[phase],
        "request": body,
        "runs": runs,
        "content_counts": counts,
        "unique_hash_count": len({item["sha256"] for item in runs}),
        "cached_tokens_all_zero": all(item["cached_tokens"] == 0 for item in runs),
        "top_scores_present_all": all(
            required_named_scores_present(item["first_token_top_scores"])
            for item in runs
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:19638")
    parser.add_argument("--model")
    parser.add_argument("--repeats", type=int, default=32)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--request-prefix", default="qwen38-repeat-sensitivity")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.repeats < 1 or args.repeats > 128:
        parser.error("--repeats must be between 1 and 128")
    base_url = validate_base_url(args.base_url)
    model = args.model
    if args.plan:
        model = model or "<live-model-id>"
        print(json.dumps({
            "schema": SCHEMA,
            "network_requests": 0,
            "output_writes": 0,
            "base_url": base_url,
            "repeats_per_phase": args.repeats,
            "requests": {name: payload(model, prompt, args.seed) for name, prompt in PHASES.items()},
        }, indent=2, sort_keys=True))
        return 0
    if args.out is None:
        parser.error("--execute requires --out")
    if args.out.exists():
        parser.error(f"refusing to overwrite {args.out}")
    if model is None:
        model = get_json(f"{base_url}/v1/models", args.timeout)["data"][0]["id"]
    phases = {
        name: run_phase(
            base_url, model, name, args.repeats, args.timeout, args.seed,
            args.request_prefix,
        )
        for name in PHASES
    }
    fixed = phases["fixed_set"]
    fixed_first_token_pass = set(fixed["content_counts"]) == {"blue"}
    cache_pass = all(item["cached_tokens_all_zero"] for item in phases.values())
    score_pass = all(item["top_scores_present_all"] for item in phases.values())
    output = {
        "schema": SCHEMA,
        "base_url": base_url,
        "model": model,
        "seed": args.seed,
        "repeats_per_phase": args.repeats,
        "interpretation": {
            "open_choice_is_sensitivity_probe": True,
            "fixed_set_first_token_expected": "blue",
            "fixed_set_first_token_pass": fixed_first_token_pass,
            "cache_zero_pass": cache_pass,
            "top_scores_present_pass": score_pass,
            "pass": fixed_first_token_pass and cache_pass and score_pass,
        },
        "phases": phases,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output["interpretation"], sort_keys=True))
    return 0 if output["interpretation"]["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
