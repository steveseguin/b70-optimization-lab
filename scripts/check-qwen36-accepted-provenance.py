#!/usr/bin/env python3
"""Check Qwen3.6 accepted graph-cache provenance and sentinel tokens."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_TOKENIZER = (
    "/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8"
    "/snapshots/cced56592e8c8935f8220836b4baa04dfd389118"
)
DEFAULT_BASELINE = (
    "data/qwen36-quark-int8-tp4-accepted-restored-current-oracle-baseline-20260612i.json"
)
DEFAULT_CACHE_FRAGMENT = (
    "/mnt/fast-ai/vllm-cache-exp/"
    "qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-gdn-reuseqkvzbaquant-clone-envclean-32k-noprefix"
)
DEFAULT_SENTINELS = (
    ("repetitive_kernel_notes", 14),
    ("natural_latency_plan", 17),
    ("natural_latency_plan", 25),
)


def request_json(url: str, timeout: int) -> dict[str, Any]:
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
    return tokenizer.decode((prefix_ids + body_ids + suffix_ids)[:target_tokens], skip_special_tokens=True)


def make_cases(tokenizer: Any, prompt_tokens: int) -> list[dict[str, str]]:
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
    seed: int,
    timeout: int,
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
    started_unix = time.time()
    started = time.perf_counter()
    response = post_json(f"{base_url.rstrip('/')}/v1/completions", payload, timeout)
    elapsed = time.perf_counter() - started
    data = response["json"]
    choice = data["choices"][0]
    return {
        "request_started_at_unix": started_unix,
        "request_finished_at_unix": time.time(),
        "elapsed_s": elapsed,
        "response_status": response["status"],
        "response_id": data.get("id"),
        "response_model": data.get("model"),
        "response_headers": {
            key: response["headers"][key]
            for key in ("x-request-id", "x-correlation-id", "x-vllm-request-id")
            if key in response["headers"]
        },
        "text": choice.get("text") or "",
        "finish_reason": choice.get("finish_reason"),
        "usage": data.get("usage"),
        "response_output_token_ids": choice.get("token_ids"),
    }


def first_diff(a: list[int], b: list[int]) -> dict[str, Any]:
    limit = min(len(a), len(b))
    for index in range(limit):
        if a[index] != b[index]:
            return {
                "index": index,
                "current": a[index],
                "baseline": b[index],
                "current_context": a[max(0, index - 8):index + 8],
                "baseline_context": b[max(0, index - 8):index + 8],
            }
    if len(a) != len(b):
        return {"index": limit, "current_len": len(a), "baseline_len": len(b)}
    return {"index": None}


def parse_log(log_path: Path | None, expected_cache_fragments: list[str]) -> dict[str, Any]:
    if log_path is None:
        return {
            "path": None,
            "exists": False,
            "cache_directories": [],
            "aot_paths": [],
            "expected_cache_fragments": expected_cache_fragments,
            "expected_cache_fragment_hits": {},
        }
    text = log_path.read_text(errors="replace") if log_path.exists() else ""
    cache_directories = sorted(set(
        re.findall(r"Using cache directory: (.*?) for vLLM's torch\.compile", text)
    ))
    aot_paths = sorted(set(
        re.findall(r"Directly load AOT compilation from path (.*)", text)
    ))
    graph_capture_lines = [
        line.strip()
        for line in text.splitlines()
        if "Graph capturing finished" in line or "Directly load the compiled graph" in line
    ][-16:]
    haystack = "\n".join(cache_directories + aot_paths + graph_capture_lines)
    return {
        "path": str(log_path),
        "exists": log_path.exists(),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if log_path.exists() else None,
        "cache_directories": cache_directories,
        "aot_paths": aot_paths,
        "graph_capture_lines_tail": graph_capture_lines,
        "expected_cache_fragments": expected_cache_fragments,
        "expected_cache_fragment_hits": {
            fragment: fragment in haystack for fragment in expected_cache_fragments
        },
    }


def load_baseline(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text())
    return {case["name"]: case for case in data.get("cases", [])}


def parse_sentinel(value: str) -> tuple[str, int, int | None]:
    parts = value.split(":")
    if len(parts) not in (2, 3):
        raise argparse.ArgumentTypeError("sentinel must be name:index or name:index:token_id")
    name = parts[0]
    try:
        index = int(parts[1])
        token_id = int(parts[2]) if len(parts) == 3 else None
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return name, index, token_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--model", default="qwen36-35b-a3b-fp8")
    parser.add_argument("--tokenizer", default=DEFAULT_TOKENIZER)
    parser.add_argument("--baseline-json", type=Path, default=Path(DEFAULT_BASELINE))
    parser.add_argument("--prompt-tokens", type=int, default=512)
    parser.add_argument("--output-tokens", type=int, default=32)
    parser.add_argument("--seed", type=int, default=20260611)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--log-path", type=Path)
    parser.add_argument(
        "--expected-cache-fragment",
        action="append",
        default=[DEFAULT_CACHE_FRAGMENT],
        help="Required substring in parsed cache/AOT paths. Repeatable.",
    )
    parser.add_argument(
        "--allow-missing-log",
        action="store_true",
        help="Do not fail when --log-path is omitted or missing.",
    )
    parser.add_argument(
        "--sentinel",
        type=parse_sentinel,
        action="append",
        default=[(name, index, None) for name, index in DEFAULT_SENTINELS],
        help="Sentinel as name:index or name:index:token_id. Defaults cover known graph/refill drift positions.",
    )
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    from transformers import AutoTokenizer

    base_url = args.base_url.rstrip("/")
    errors: list[str] = []
    model_payload = request_json(f"{base_url}/v1/models", args.timeout)
    model_info = model_payload.get("data", [{}])[0]
    if model_info.get("id") != args.model:
        errors.append(f"served model id mismatch: {model_info.get('id')} != {args.model}")

    baseline_by_name = load_baseline(args.baseline_json)
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, trust_remote_code=True)
    log_info = parse_log(args.log_path, args.expected_cache_fragment)
    if not log_info["exists"] and not args.allow_missing_log:
        errors.append("launch log is missing; pass --allow-missing-log to skip cache provenance failure")
    for fragment, hit in log_info["expected_cache_fragment_hits"].items():
        if not hit and not args.allow_missing_log:
            errors.append(f"expected cache fragment not found in launch log: {fragment}")

    cases: list[dict[str, Any]] = []
    for case in make_cases(tokenizer, args.prompt_tokens):
        result = completion(
            base_url=base_url,
            model=args.model,
            prompt=case["prompt"],
            max_tokens=args.output_tokens,
            seed=args.seed,
            timeout=args.timeout,
        )
        retokenized = tokenizer.encode(result["text"], add_special_tokens=False)
        api_ids = result["response_output_token_ids"]
        output_ids = [int(value) for value in api_ids] if isinstance(api_ids, list) else retokenized
        baseline = baseline_by_name.get(case["name"], {})
        baseline_ids = [int(value) for value in baseline.get("output_token_ids", [])]
        expected_prefix = baseline_ids[:args.output_tokens]
        prefix_match = output_ids[:args.output_tokens] == expected_prefix
        diff = first_diff(output_ids[:args.output_tokens], expected_prefix)
        if not prefix_match:
            errors.append(f"{case['name']} output prefix drift: {diff}")
        cases.append({
            "name": case["name"],
            "prompt_sha256": sha256_text(case["prompt"]),
            "prompt_token_count": len(tokenizer.encode(case["prompt"], add_special_tokens=False)),
            **result,
            "text_sha256": sha256_text(result["text"]),
            "output_token_count": len(output_ids),
            "output_token_ids": output_ids,
            "retokenized_output_token_ids": retokenized,
            "api_vs_retokenized_output_token_ids_match": (
                output_ids == retokenized if isinstance(api_ids, list) else None
            ),
            "baseline_prefix_token_ids": expected_prefix,
            "baseline_prefix_match": prefix_match,
            "baseline_prefix_diff": diff,
        })

    cases_by_name = {case["name"]: case for case in cases}
    sentinel_results: list[dict[str, Any]] = []
    for name, index, explicit_expected in args.sentinel:
        case = cases_by_name.get(name)
        baseline = baseline_by_name.get(name, {})
        baseline_ids = [int(value) for value in baseline.get("output_token_ids", [])]
        expected = explicit_expected
        if expected is None and index < len(baseline_ids):
            expected = baseline_ids[index]
        actual = None
        if case and index < len(case["output_token_ids"]):
            actual = case["output_token_ids"][index]
        ok = actual == expected and expected is not None
        sentinel = {
            "name": name,
            "index": index,
            "expected_token_id": expected,
            "actual_token_id": actual,
            "ok": ok,
        }
        if not ok:
            errors.append(f"sentinel failed: {sentinel}")
        sentinel_results.append(sentinel)

    output = {
        "ok": not errors,
        "errors": errors,
        "base_url": base_url,
        "model": args.model,
        "model_info": model_info,
        "tokenizer": args.tokenizer,
        "baseline_json": str(args.baseline_json),
        "prompt_tokens": args.prompt_tokens,
        "output_tokens": args.output_tokens,
        "seed": args.seed,
        "log": log_info,
        "sentinels": sentinel_results,
        "cases": cases,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "ok": output["ok"],
        "output_json": str(args.output_json),
        "errors": errors,
        "sentinels": sentinel_results,
        "case_prefix_matches": {
            case["name"]: case["baseline_prefix_match"] for case in cases
        },
    }, indent=2, sort_keys=True))
    return 0 if output["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
