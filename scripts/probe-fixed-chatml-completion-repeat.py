#!/usr/bin/env python3
"""Repeat fixed raw ChatML completion canaries against an OpenAI endpoint.

This bypasses /v1/chat/completions and sends the exact rendered prompt to
/v1/completions. It is intended to catch endpoint/runtime corruption below the
chat template layer.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


CASES: dict[str, dict[str, Any]] = {
    "color": {
        "user_prompt": (
            "Give exactly four comma-separated lowercase color words, "
            "sorted alphabetically, with no extra text."
        ),
        "max_tokens": 32,
        "expected_normalized": "blue, green, orange, red",
    },
    "json": {
        "user_prompt": (
            "Return only compact JSON with keys answer and unit. "
            "Question: 12 plus 30. Unit: widgets."
        ),
        "max_tokens": 64,
        "json_expected_fields": {"answer": "42", "unit": "widgets"},
    },
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def fixed_chatml_prompt(user_prompt: str) -> str:
    return (
        "<|im_start|>user\n"
        f"{user_prompt}<|im_end|>\n"
        "<|im_start|>assistant\n"
        "<think>\n\n</think>\n\n"
    )


def get_json(url: str, timeout: int) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


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


def row_passes(row: dict[str, Any], case: dict[str, Any]) -> bool:
    if "expected_normalized" in case:
        return row["normalized"] == case["expected_normalized"]
    expected_fields = case["json_expected_fields"]
    parsed = extract_json_object(row["text"])
    row["json_parsed"] = parsed
    return isinstance(parsed, dict) and all(
        str(parsed.get(key)) == expected
        for key, expected in expected_fields.items()
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--model", default=None)
    parser.add_argument("--tokenizer", required=True)
    parser.add_argument("--case", choices=sorted(CASES), required=True)
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--repeats", type=int, default=128)
    parser.add_argument("--seed", type=int, default=20260613)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--request-delay-s", type=float, default=0.0)
    parser.add_argument("--stop-on-mismatch", action="store_true")
    parser.add_argument(
        "--logprobs",
        type=int,
        default=0,
        help="Request completion logprobs/top_logprobs for mismatch diagnosis.",
    )
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    from transformers import AutoTokenizer

    base_url = args.base_url.rstrip("/")
    models = get_json(f"{base_url}/v1/models", args.timeout)
    model = args.model or models["data"][0]["id"]
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, trust_remote_code=True)

    case = dict(CASES[args.case])
    max_tokens = args.max_tokens or int(case["max_tokens"])
    prompt = fixed_chatml_prompt(case["user_prompt"])
    prompt_token_ids = tokenizer.encode(prompt, add_special_tokens=False)
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []

    for index in range(args.repeats):
        payload = {
            "model": model,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": 0,
            "top_p": 1.0,
            "seed": args.seed,
        }
        if args.logprobs > 0:
            payload["logprobs"] = args.logprobs
        started = time.perf_counter()
        try:
            data = post_json(f"{base_url}/v1/completions", payload, args.timeout)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            row = {
                "index": index,
                "text": "",
                "normalized": "",
                "token_ids": [],
                "finish_reason": None,
                "elapsed_s": time.perf_counter() - started,
                "usage": None,
                "http_error": {
                    "code": exc.code,
                    "reason": exc.reason,
                    "body": body,
                },
                "pass": False,
            }
            rows.append(row)
            mismatches.append(row)
            if args.stop_on_mismatch:
                break
            if args.request_delay_s > 0:
                time.sleep(args.request_delay_s)
            continue
        elapsed = time.perf_counter() - started
        choice = data["choices"][0]
        text = choice.get("text") or ""
        token_ids = tokenizer.encode(text, add_special_tokens=False)
        row = {
            "index": index,
            "text": text,
            "normalized": normalize(text),
            "token_ids": token_ids,
            "finish_reason": choice.get("finish_reason"),
            "elapsed_s": elapsed,
            "usage": data.get("usage"),
        }
        if args.logprobs > 0:
            row["response_token_ids"] = choice.get("token_ids")
            row["logprobs"] = choice.get("logprobs")
        row["pass"] = row_passes(row, case)
        rows.append(row)
        if not row["pass"]:
            mismatches.append(row)
            if args.stop_on_mismatch:
                break
        if args.request_delay_s > 0:
            time.sleep(args.request_delay_s)

    output = {
        "base_url": base_url,
        "model": model,
        "tokenizer": args.tokenizer,
        "case": args.case,
        "user_prompt": case["user_prompt"],
        "prompt": prompt,
        "prompt_token_ids": prompt_token_ids,
        "max_tokens": max_tokens,
        "repeats_requested": args.repeats,
        "repeats_completed": len(rows),
        "seed": args.seed,
        "request_delay_s": args.request_delay_s,
        "stop_on_mismatch": args.stop_on_mismatch,
        "logprobs": args.logprobs,
        "expected_normalized": case.get("expected_normalized"),
        "json_expected_fields": case.get("json_expected_fields"),
        "pass_all": not mismatches,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "unique_normalized": sorted({row["normalized"] for row in rows}),
        "rows": rows,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({
        "case": args.case,
        "pass_all": output["pass_all"],
        "repeats_completed": len(rows),
        "mismatch_count": len(mismatches),
        "output_json": str(args.output_json),
    }, sort_keys=True))
    return 0 if output["pass_all"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
