#!/usr/bin/env python3
"""Cold long-context prompt-processing gate for OpenAI-compatible endpoints."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import statistics
import time
import urllib.request
from pathlib import Path
from typing import Any


FILLER_WORDS = (
    "benchmark latency memory throughput validation repeatability scheduler "
    "cache kernel sycl level-zero b70 q8 deterministic prompt prefill context "
    "retrieval service quality hash verifier decode stable measurement "
)


def stream_chat(
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    timeout: int,
    seed: int | None,
    request_extra: dict[str, Any],
    return_token_ids: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "top_p": 1,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if seed is not None:
        payload["seed"] = seed
    if return_token_ids:
        payload["return_token_ids"] = True
    payload.update(request_extra)

    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    started = time.perf_counter()
    first_text_at: float | None = None
    text_parts: list[str] = []
    chunk_offsets: list[float] = []
    token_id_offsets: list[float] = []
    token_ids: list[int] = []
    content_delta_count = 0
    reasoning_delta_count = 0
    usage: dict[str, Any] = {}
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            event = json.loads(data)
            if event.get("usage"):
                usage = event["usage"]
            for choice in event.get("choices", []):
                choice_token_ids = choice.get("token_ids")
                if isinstance(choice_token_ids, list):
                    now = time.perf_counter()
                    if first_text_at is None and choice_token_ids:
                        first_text_at = now
                    token_ids.extend(int(token_id) for token_id in choice_token_ids)
                    token_id_offsets.extend(
                        [now - started] * len(choice_token_ids)
                    )

                delta = choice.get("delta") or {}
                token_text = delta.get("content") or ""
                if token_text:
                    content_delta_count += 1
                else:
                    token_text = delta.get("reasoning") or ""
                    if token_text:
                        reasoning_delta_count += 1

                if token_text:
                    now = time.perf_counter()
                    if first_text_at is None:
                        first_text_at = now
                    text_parts.append(token_text)
                    chunk_offsets.append(now - started)

    ended = time.perf_counter()
    text = "".join(text_parts)
    completion_tokens = usage.get("completion_tokens")
    prompt_tokens = usage.get("prompt_tokens")
    elapsed_s = ended - started
    ttft_s = None if first_text_at is None else first_text_at - started
    post_ttft_s = None if first_text_at is None else ended - first_text_at
    tok_s_after_ttft = None
    tok_s_wall = None
    if isinstance(completion_tokens, int) and completion_tokens > 0:
        tok_s_wall = completion_tokens / elapsed_s
        if post_ttft_s and post_ttft_s > 0:
            tok_s_after_ttft = completion_tokens / post_ttft_s

    return {
        "elapsed_s": elapsed_s,
        "ttft_s": ttft_s,
        "post_ttft_s": post_ttft_s,
        "chunk_count": len(chunk_offsets),
        "stream_token_id_count": len(token_id_offsets),
        "token_ids": token_ids,
        "token_ids_complete": (
            isinstance(completion_tokens, int)
            and completion_tokens > 0
            and len(token_ids) == completion_tokens
        ),
        "token_ids_sha256": (
            hashlib.sha256(
                json.dumps(token_ids, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            if token_ids
            else None
        ),
        "content_delta_count": content_delta_count,
        "reasoning_delta_count": reasoning_delta_count,
        "chunk_offsets_s": chunk_offsets,
        "token_id_offsets_s": token_id_offsets,
        "usage": usage,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "tok_s_wall": tok_s_wall,
        "tok_s_after_ttft": tok_s_after_ttft,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text": text,
        "text_preview": text[:320],
    }


def expected_json(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case["id"],
        "project_code": case["project_code"],
        "answer_phrase": case["answer_phrase"],
        "sort_order": case["sort_order"],
        "arithmetic_result": int(case["arithmetic_result"]),
    }


def fact_block(case: dict[str, Any]) -> str:
    expected = expected_json(case)
    return (
        f"\nBEGIN LONG CONTEXT FACT BLOCK {case['id']}\n"
        f"case_id: {expected['case_id']}\n"
        f"project_code: {expected['project_code']}\n"
        f"answer_phrase: {expected['answer_phrase']}\n"
        f"sort_order: {expected['sort_order']}\n"
        f"arithmetic_result: {expected['arithmetic_result']}\n"
        f"END LONG CONTEXT FACT BLOCK {case['id']}\n"
    )


def filler(case: dict[str, Any], chars: int, salt: str) -> str:
    if chars <= 0:
        return ""
    nonce = hashlib.sha256(f"{case['id']}:{salt}".encode("utf-8")).hexdigest()[:16]
    block = (
        f"{FILLER_WORDS} case {case['id']} filler {salt} nonce {nonce}. "
        "Ignore this filler unless it is inside the named fact block. "
    )
    return (block * ((chars // len(block)) + 2))[:chars]


def make_prompt(case: dict[str, Any]) -> str:
    target_chars = max(1200, int(case["target_prompt_tokens"]) * 6)
    facts = fact_block(case)
    task = (
        "\nTask: using only the named fact block above, return exactly one JSON "
        "object with keys case_id, project_code, answer_phrase, sort_order, and "
        "arithmetic_result. Do not add markdown or explanatory text.\n"
    )
    header = (
        "You are validating long-context retrieval quality and prompt "
        "processing. Most of this prompt is filler. Only the fact block named "
        f"{case['id']} is authoritative.\n\n"
    )
    filler_chars = max(0, target_chars - len(header) - len(facts) - len(task))
    pos = case.get("needle_position", "middle")
    if pos == "early":
        before_chars = filler_chars // 10
    elif pos == "late":
        before_chars = (filler_chars * 9) // 10
    else:
        before_chars = filler_chars // 2
    after_chars = filler_chars - before_chars
    return (
        header
        + filler(case, before_chars, "before")
        + facts
        + filler(case, after_chars, "after")
        + task
    )


def extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    candidates = [stripped]
    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if match:
        candidates.insert(0, match.group(0))
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def validate(case: dict[str, Any], text: str) -> dict[str, Any]:
    expected = expected_json(case)
    parsed = extract_json_object(text)
    fields: dict[str, bool] = {}
    if parsed is None:
        fields = {key: False for key in expected}
        return {
            "pass": False,
            "parsed_json": None,
            "expected": expected,
            "field_pass": fields,
            "error": "no JSON object parsed",
        }
    for key, exp in expected.items():
        got = parsed.get(key)
        if key == "arithmetic_result":
            fields[key] = got == exp
        else:
            fields[key] = str(got).strip() == str(exp)
    return {
        "pass": all(fields.values()),
        "parsed_json": parsed,
        "expected": expected,
        "field_pass": fields,
    }


def cached_tokens(row: dict[str, Any]) -> int | None:
    usage = row.get("usage")
    if not isinstance(usage, dict):
        return None
    details = usage.get("prompt_tokens_details")
    if not isinstance(details, dict):
        return None
    value = details.get("cached_tokens")
    return value if isinstance(value, int) else None


def stats(rows: list[dict[str, Any]], key: str) -> dict[str, float] | None:
    vals = [row[key] for row in rows if isinstance(row.get(key), (int, float))]
    if not vals:
        return None
    mean = statistics.fmean(vals)
    return {
        "count": len(vals),
        "mean": mean,
        "median": statistics.median(vals),
        "min": min(vals),
        "max": max(vals),
        "p10": sorted(vals)[max(0, int(0.1 * (len(vals) - 1)))],
        "stdev": statistics.stdev(vals) if len(vals) > 1 else 0.0,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cached = [cached_tokens(row) for row in rows]
    known_cached = [value for value in cached if value is not None]
    prompt_hashes = [row["prompt_sha256"] for row in rows]
    for row in rows:
        prompt_tokens = row.get("prompt_tokens")
        ttft_s = row.get("ttft_s")
        row["prefill_tok_s_approx"] = (
            prompt_tokens / ttft_s
            if isinstance(prompt_tokens, int)
            and isinstance(ttft_s, (int, float))
            and ttft_s > 0
            else None
        )
    quality_all = all((row.get("validation") or {}).get("pass") for row in rows)
    cached_all_zero = (
        len(known_cached) == len(rows) and all(value == 0 for value in known_cached)
    )
    prompts_unique = len(prompt_hashes) == len(set(prompt_hashes))
    return {
        "requests": len(rows),
        "quality_pass_all": quality_all,
        "cached_tokens_all_zero": cached_all_zero,
        "cached_tokens": cached,
        "prompts_unique": prompts_unique,
        "long_context_gate": {
            "passed": bool(rows) and quality_all and cached_all_zero and prompts_unique,
            "required_policy": (
                "fixed deterministic long-context suite; each prompt once; "
                "cached_tokens=0 every row; exact JSON retrieval fields pass"
            ),
        },
        "prompt_tokens": stats(rows, "prompt_tokens"),
        "completion_tokens": stats(rows, "completion_tokens"),
        "ttft_s": stats(rows, "ttft_s"),
        "prefill_tok_s_approx": stats(rows, "prefill_tok_s_approx"),
        "tok_s_after_ttft": stats(rows, "tok_s_after_ttft"),
        "tok_s_wall": stats(rows, "tok_s_wall"),
    }


def load_cases(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    suite = json.loads(args.suite.read_text())
    cases = list(suite["cases"])
    if args.case_id:
        wanted = set(args.case_id)
        cases = [case for case in cases if case["id"] in wanted]
    if args.max_target_prompt_tokens is not None:
        cases = [
            case for case in cases
            if int(case["target_prompt_tokens"]) <= args.max_target_prompt_tokens
        ]
    if not cases:
        raise SystemExit("No long-context suite cases selected")
    return suite, cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18260")
    parser.add_argument("--model", default="gemma4-26b-a4b-q8")
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--max-target-prompt-tokens", type=int)
    parser.add_argument("--max-tokens", type=int, default=96)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--request-extra-json",
        default="{}",
        help=(
            "JSON object merged into every request payload, for example "
            "'{\"chat_template_kwargs\":{\"enable_thinking\":false}}'."
        ),
    )
    parser.add_argument(
        "--return-token-ids",
        action="store_true",
        help=(
            "Request vLLM stream token_ids so TTFT/decode timing is still "
            "available when text deltas are coalesced or routed through "
            "reasoning fields."
        ),
    )
    args = parser.parse_args()
    request_extra = json.loads(args.request_extra_json)
    if not isinstance(request_extra, dict):
        raise SystemExit("--request-extra-json must decode to a JSON object")

    suite, cases = load_cases(args)
    rows: list[dict[str, Any]] = []
    prompt_hashes = []
    for case in cases:
        prompt = make_prompt(case)
        prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        prompt_hashes.append(prompt_sha256)
        row = stream_chat(
            args.base_url,
            args.model,
            prompt,
            args.max_tokens,
            args.timeout,
            args.seed,
            request_extra,
            args.return_token_ids,
        )
        row.update({
            "case_id": case["id"],
            "target_prompt_tokens": case["target_prompt_tokens"],
            "needle_position": case["needle_position"],
            "prompt_sha256": prompt_sha256,
            "prompt_chars": len(prompt),
            "prompt_preview": prompt[:320],
            "validation": validate(case, row["text"]),
        })
        row["cached_tokens"] = cached_tokens(row)
        rows.append(row)

    run_identity = {
        "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "base_url": args.base_url,
        "model": args.model,
        "suite": str(args.suite),
        "suite_id": suite.get("suite_id"),
        "suite_sha256": hashlib.sha256(args.suite.read_bytes()).hexdigest(),
        "case_ids": [case["id"] for case in cases],
        "max_target_prompt_tokens": args.max_target_prompt_tokens,
        "max_tokens": args.max_tokens,
        "seed": args.seed,
        "api_mode": "chat",
        "request_extra": request_extra,
        "return_token_ids": args.return_token_ids,
        "prompt_sha256s": prompt_hashes,
    }
    result = {
        "run_identity": run_identity,
        "summary": summarize(rows),
        "rows": rows,
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    print(text)
    return 0 if result["summary"]["long_context_gate"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
