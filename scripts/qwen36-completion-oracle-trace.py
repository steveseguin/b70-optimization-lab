#!/usr/bin/env python3
"""Record raw completion token traces for Qwen3.6 oracle-draft probes."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_TOKENIZER = (
    "/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8"
    "/snapshots/cced56592e8c8935f8220836b4baa04dfd389118"
)


def post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return {
            "status": resp.status,
            "headers": {key.lower(): value for key, value in resp.headers.items()},
            "json": json.loads(resp.read().decode("utf-8")),
        }


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def repeated_text(tokenizer: Any, target_tokens: int, seed_text: str) -> str:
    seed_ids = tokenizer.encode(seed_text, add_special_tokens=False)
    if not seed_ids:
        raise ValueError("seed text produced no tokens")
    ids = (seed_ids * ((target_tokens + len(seed_ids) - 1) // len(seed_ids)))[:target_tokens]
    return tokenizer.decode(ids, skip_special_tokens=True)


def fit_prompt(
    tokenizer: Any,
    *,
    target_tokens: int,
    prefix: str,
    filler: str,
    suffix: str,
) -> str:
    prefix_ids = tokenizer.encode(prefix, add_special_tokens=False)
    filler_ids = tokenizer.encode(filler, add_special_tokens=False)
    suffix_ids = tokenizer.encode(suffix, add_special_tokens=False)
    if not filler_ids:
        raise ValueError("filler produced no tokens")
    body_budget = max(0, target_tokens - len(prefix_ids) - len(suffix_ids))
    body_ids = (filler_ids * ((body_budget + len(filler_ids) - 1) // len(filler_ids)))[:body_budget]
    ids = prefix_ids + body_ids + suffix_ids
    return tokenizer.decode(ids[:target_tokens], skip_special_tokens=True)


def make_cases(tokenizer: Any, prompt_tokens: int) -> list[dict[str, Any]]:
    return [
        {
            "name": "natural_latency_plan",
            "prompt": fit_prompt(
                tokenizer,
                target_tokens=prompt_tokens,
                prefix=(
                    "Write a technical latency plan for an Intel Arc Pro B70 "
                    "Qwen3.6 INT8 inference server.\n\n"
                ),
                filler=(
                    "The current service uses vLLM XPU, tensor parallelism, graph "
                    "capture, Quark W8A8 INT8 weights, and exact quality canaries. "
                    "Speculative decoding must preserve final verifier output. "
                ),
                suffix=(
                    "\n\nContinue with dense numbered engineering notes. Focus on "
                    "single-request decode speed, reliability gates, and no quality loss.\n"
                ),
            ),
        },
        {
            "name": "repetitive_kernel_notes",
            "prompt": repeated_text(
                tokenizer,
                prompt_tokens,
                (
                    "Intel XPU decode verifier bucket route graph token timing. "
                    "Preserve exact output while measuring multi token verification. "
                ),
            ),
        },
    ]


def completion(
    *,
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    timeout: int,
    seed: int,
    logprobs: int | None,
    request_id: str | None,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": 0,
        "top_p": 1.0,
        "seed": seed,
        "return_token_ids": True,
    }
    if request_id is not None:
        payload["request_id"] = request_id
    if logprobs is not None:
        payload["logprobs"] = logprobs
    started_unix = time.time()
    started = time.perf_counter()
    response = post_json(f"{base_url.rstrip('/')}/v1/completions", payload, timeout)
    finished_unix = time.time()
    elapsed = time.perf_counter() - started
    data = response["json"]
    choice = data["choices"][0]
    return {
        "request_started_at_unix": started_unix,
        "request_finished_at_unix": finished_unix,
        "elapsed_s": elapsed,
        "response_status": response["status"],
        "response_id": data.get("id"),
        "response_created": data.get("created"),
        "response_model": data.get("model"),
        "response_headers": {
            key: response["headers"][key]
            for key in (
                "x-request-id",
                "x-correlation-id",
                "x-vllm-request-id",
            )
            if key in response["headers"]
        },
        "request_id": request_id,
        "text": choice.get("text") or "",
        "finish_reason": choice.get("finish_reason"),
        "usage": data.get("usage"),
        "logprobs": choice.get("logprobs"),
        "response_output_token_ids": choice.get("token_ids"),
        "response_prompt_token_ids": choice.get("prompt_token_ids"),
    }


def normalize_completion_logprobs(
    tokenizer: Any,
    logprobs: dict[str, Any] | None,
) -> list[dict[str, Any]] | None:
    if not logprobs:
        return None
    tokens = logprobs.get("tokens") or []
    token_logprobs = logprobs.get("token_logprobs") or []
    text_offsets = logprobs.get("text_offset") or []
    top_logprobs = logprobs.get("top_logprobs") or []
    rows: list[dict[str, Any]] = []
    for index, token_text in enumerate(tokens):
        token_ids = tokenizer.encode(token_text, add_special_tokens=False)
        row: dict[str, Any] = {
            "index": index,
            "token_text": token_text,
            "token_ids": token_ids,
            "token_id": token_ids[0] if len(token_ids) == 1 else None,
            "token_logprob": (
                float(token_logprobs[index])
                if index < len(token_logprobs) and token_logprobs[index] is not None
                else None
            ),
            "text_offset": (
                int(text_offsets[index]) if index < len(text_offsets) else None
            ),
            "top": [],
        }
        top = top_logprobs[index] if index < len(top_logprobs) else None
        if isinstance(top, dict):
            entries = []
            for text, value in top.items():
                ids = tokenizer.encode(text, add_special_tokens=False)
                entries.append({
                    "text": text,
                    "token_ids": ids,
                    "token_id": ids[0] if len(ids) == 1 else None,
                    "logprob": float(value) if value is not None else None,
                })
            entries.sort(
                key=lambda item: (
                    -(item["logprob"] if item["logprob"] is not None else -1e30),
                    item["text"],
                )
            )
            row["top"] = entries
        rows.append(row)
    return rows


def first_diff(a: list[int], b: list[int]) -> dict[str, Any]:
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
        return {"index": limit, "a_len": len(a), "b_len": len(b)}
    return {"index": None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--model", default="qwen36-35b-a3b-fp8")
    parser.add_argument("--tokenizer", default=DEFAULT_TOKENIZER)
    parser.add_argument("--prompt-tokens", type=int, default=512)
    parser.add_argument("--output-tokens", type=int, default=128)
    parser.add_argument("--seed", type=int, default=20260611)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--baseline-json", type=Path)
    parser.add_argument("--request-id-prefix", default=None)
    parser.add_argument(
        "--case",
        action="append",
        default=None,
        help="Only run the named case. May be passed more than once.",
    )
    parser.add_argument(
        "--logprobs",
        type=int,
        default=None,
        help="Request generated-token top logprobs from the completions API.",
    )
    args = parser.parse_args()

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, trust_remote_code=True)
    baseline_by_name: dict[str, dict[str, Any]] = {}
    if args.baseline_json:
        baseline = json.loads(args.baseline_json.read_text())
        baseline_by_name = {item["name"]: item for item in baseline.get("cases", [])}

    cases = []
    comparisons: dict[str, Any] = {}
    selected_cases = set(args.case or [])
    all_cases = [
        case for case in make_cases(tokenizer, args.prompt_tokens)
        if not selected_cases or case["name"] in selected_cases
    ]
    unknown_cases = selected_cases - {case["name"] for case in all_cases}
    if unknown_cases:
        raise ValueError(f"Unknown case name(s): {sorted(unknown_cases)}")

    for case_index, case in enumerate(all_cases):
        prompt = case["prompt"]
        prompt_ids = tokenizer.encode(prompt, add_special_tokens=False)
        request_id = (
            f"{args.request_id_prefix}-{case_index:06d}"
            if args.request_id_prefix
            else None
        )
        result = completion(
            base_url=args.base_url,
            model=args.model,
            prompt=prompt,
            max_tokens=args.output_tokens,
            timeout=args.timeout,
            seed=args.seed,
            logprobs=args.logprobs,
            request_id=request_id,
        )
        retokenized_output_ids = tokenizer.encode(
            result["text"], add_special_tokens=False)
        response_output_token_ids = result.get("response_output_token_ids")
        api_output_ids = (
            [int(value) for value in response_output_token_ids]
            if isinstance(response_output_token_ids, list)
            else []
        )
        output_ids = api_output_ids or retokenized_output_ids
        normalized_logprobs = normalize_completion_logprobs(
            tokenizer, result.get("logprobs"))
        record = {
            "name": case["name"],
            "seed": args.seed,
            "max_tokens": args.output_tokens,
            "prompt_sha256": sha256_text(prompt),
            "prompt": prompt,
            "prompt_token_count": len(prompt_ids),
            "prompt_token_ids": prompt_ids,
            "prompt_token_ids_head": prompt_ids[:32],
            "prompt_token_ids_tail": prompt_ids[-64:],
            **result,
            "text_sha256": sha256_text(result["text"]),
            "output_token_count": len(output_ids),
            "output_token_ids": output_ids,
            "output_token_ids_source": (
                "api_token_ids" if api_output_ids else "retokenized_text"
            ),
            "retokenized_output_token_count": len(retokenized_output_ids),
            "retokenized_output_token_ids": retokenized_output_ids,
            "api_vs_retokenized_output_token_ids_match": (
                api_output_ids == retokenized_output_ids
                if api_output_ids else None
            ),
            "normalized_logprobs": normalized_logprobs,
        }
        base = baseline_by_name.get(case["name"])
        if base:
            comparisons[case["name"]] = {
                "text_match": record["text"] == base.get("text"),
                "output_token_ids_match": output_ids == base.get("output_token_ids"),
                "output_token_diff": first_diff(output_ids, base.get("output_token_ids", [])),
                "baseline_response_id": base.get("response_id"),
                "current_response_id": record.get("response_id"),
            }
        cases.append(record)

    output = {
        "base_url": args.base_url.rstrip("/"),
        "model": args.model,
        "tokenizer": args.tokenizer,
        "prompt_tokens": args.prompt_tokens,
        "output_tokens": args.output_tokens,
        "seed": args.seed,
        "request_id_prefix": args.request_id_prefix,
        "cases": cases,
        "baseline_json": str(args.baseline_json) if args.baseline_json else None,
        "baseline_comparisons": comparisons,
        "baseline_match_all": (
            all(
                row.get("output_token_ids_match") and row.get("text_match")
                for row in comparisons.values()
            )
            if comparisons
            else None
        ),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "output_json": str(args.output_json),
        "case_count": len(cases),
        "baseline_match_all": output["baseline_match_all"],
        "output_token_counts": {
            item["name"]: item["output_token_count"] for item in cases
        },
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
