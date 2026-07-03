#!/usr/bin/env python3
"""Cold realistic prompt-suite benchmark for OpenAI-compatible endpoints."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import statistics
import time
import urllib.request
from pathlib import Path
from typing import Any


def post_stream(
    *,
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    timeout: int,
    api_mode: str,
    seed: int | None,
    request_extra: dict[str, Any],
    return_token_ids: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
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
    if api_mode == "chat":
        endpoint = "chat/completions"
        payload["messages"] = [{"role": "user", "content": prompt}]
    else:
        endpoint = "completions"
        payload["prompt"] = prompt
    payload.update(request_extra)

    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/{endpoint}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    started = time.perf_counter()
    first_text_at: float | None = None
    text_parts: list[str] = []
    chunk_offsets: list[float] = []
    token_id_offsets: list[float] = []
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
                    token_id_offsets.extend(
                        [now - started] * len(choice_token_ids)
                    )
                if api_mode == "chat":
                    delta = choice.get("delta") or {}
                    token_text = delta.get("content") or ""
                    if token_text:
                        content_delta_count += 1
                    else:
                        token_text = delta.get("reasoning") or ""
                        if token_text:
                            reasoning_delta_count += 1
                else:
                    token_text = choice.get("text") or ""
                if not token_text:
                    continue
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
    tok_s_wall = None
    tok_s_after_ttft_full = None
    if isinstance(completion_tokens, int) and completion_tokens > 0:
        tok_s_wall = completion_tokens / elapsed_s
        if post_ttft_s and post_ttft_s > 0:
            tok_s_after_ttft_full = completion_tokens / post_ttft_s

    return {
        "elapsed_s": elapsed_s,
        "ttft_s": ttft_s,
        "post_ttft_s": post_ttft_s,
        "chunk_count": len(chunk_offsets),
        "stream_token_id_count": len(token_id_offsets),
        "content_delta_count": content_delta_count,
        "reasoning_delta_count": reasoning_delta_count,
        "chunk_offsets_s": chunk_offsets,
        "token_id_offsets_s": token_id_offsets,
        "usage": usage,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "tok_s_wall_full": tok_s_wall,
        "tok_s_after_ttft_full": tok_s_after_ttft_full,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text_preview": text[:320],
    }


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * pct
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {
            "count": 0,
            "p10": None,
            "median": None,
            "mean": None,
            "min": None,
            "max": None,
            "stdev": None,
        }
    return {
        "count": len(values),
        "p10": percentile(values, 0.10),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "min": min(values),
        "max": max(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
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


def load_suite(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    suite = json.loads(path.read_text())
    if isinstance(suite, list):
        meta = {"suite_id": path.stem, "version": None}
        prompts = suite
    else:
        meta = {k: v for k, v in suite.items() if k != "prompts"}
        prompts = suite["prompts"]
    out = []
    for index, item in enumerate(prompts):
        prompt = item["prompt"] if isinstance(item, dict) else str(item)
        prompt_id = item.get("id", f"prompt-{index:02d}") if isinstance(item, dict) else f"prompt-{index:02d}"
        out.append({"id": prompt_id, "prompt": prompt})
    return meta, out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18260")
    parser.add_argument("--model", default="gemma4-26b-a4b-q8")
    parser.add_argument("--api-mode", choices=("chat", "completions"), default="chat")
    parser.add_argument(
        "--suite",
        type=Path,
        default=Path("repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json"),
    )
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--metric-tokens", type=int, default=100)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--return-token-ids",
        action="store_true",
        help=(
            "Request vLLM stream token_ids and use cumulative token-id timing "
            "for the primary tokens-1-100 metric. This is required when text "
            "chunks contain multiple generated tokens."
        ),
    )
    parser.add_argument(
        "--request-extra-json",
        default="{}",
        help=(
            "JSON object merged into every request payload. Use for "
            "model-specific controls such as "
            "'{\"chat_template_kwargs\":{\"enable_thinking\":false}}'."
        ),
    )
    args = parser.parse_args()
    request_extra = json.loads(args.request_extra_json)
    if not isinstance(request_extra, dict):
        raise SystemExit("--request-extra-json must decode to a JSON object")

    suite_meta, prompts = load_suite(args.suite)
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(prompts):
        prompt = item["prompt"]
        row = post_stream(
            base_url=args.base_url,
            model=args.model,
            prompt=prompt,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
            api_mode=args.api_mode,
            seed=args.seed,
            request_extra=request_extra,
            return_token_ids=args.return_token_ids,
        )
        row["prompt_index"] = index
        row["prompt_id"] = item["id"]
        row["prompt_sha256"] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if args.return_token_ids and row.get("stream_token_id_count"):
            offsets = row["token_id_offsets_s"]
            timing_source = "openai_stream_token_ids_chunk_timestamp"
        else:
            offsets = row["chunk_offsets_s"]
            timing_source = "openai_stream_content_or_reasoning_delta"
        if len(offsets) >= args.metric_tokens:
            duration = offsets[args.metric_tokens - 1] - offsets[0]
            row["tok_s_1_100_after_ttft"] = (
                None if duration <= 0 else args.metric_tokens / duration
            )
        else:
            row["tok_s_1_100_after_ttft"] = None
        row["chunk_count_equals_completion_tokens"] = (
            row.get("chunk_count") == row.get("completion_tokens")
        )
        row["metric_chunk_events_at_least_window"] = (
            row.get("chunk_count") >= args.metric_tokens
        )
        row["metric_token_id_events_at_least_window"] = (
            row.get("stream_token_id_count") >= args.metric_tokens
        )
        row["token_timing_source"] = timing_source
        row["cached_tokens"] = cached_tokens(row)
        rows.append(row)

    metric_values = [
        float(row["tok_s_1_100_after_ttft"])
        for row in rows
        if isinstance(row.get("tok_s_1_100_after_ttft"), (int, float))
    ]
    full_values = [
        float(row["tok_s_after_ttft_full"])
        for row in rows
        if isinstance(row.get("tok_s_after_ttft_full"), (int, float))
    ]
    wall_values = [
        float(row["tok_s_wall_full"])
        for row in rows
        if isinstance(row.get("tok_s_wall_full"), (int, float))
    ]
    ttft_values = [
        float(row["ttft_s"]) * 1000.0
        for row in rows
        if isinstance(row.get("ttft_s"), (int, float))
    ]
    cached_values = [row.get("cached_tokens") for row in rows]
    prompt_hashes = [row["prompt_sha256"] for row in rows]
    completion_counts = [row.get("completion_tokens") for row in rows]
    chunk_counts = [row.get("chunk_count") for row in rows]
    token_id_counts = [row.get("stream_token_id_count") for row in rows]
    chunk_counts_match = [bool(row.get("chunk_count_equals_completion_tokens")) for row in rows]
    chunks_cover_metric = [
        isinstance(v, int) and v >= args.metric_tokens for v in chunk_counts
    ]
    token_ids_cover_metric = [
        isinstance(v, int) and v >= args.metric_tokens for v in token_id_counts
    ]
    metric_events_cover = (
        token_ids_cover_metric if args.return_token_ids else chunks_cover_metric
    )
    token_timing_source = (
        "openai_stream_token_ids_chunk_timestamp"
        if args.return_token_ids else
        "openai_stream_content_or_reasoning_delta"
    )

    gate = {
        "passed": (
            len(rows) == len(prompts)
            and len(metric_values) == len(rows)
            and all(isinstance(v, int) and v == 0 for v in cached_values)
            and len(set(prompt_hashes)) == len(prompt_hashes)
            and all(metric_events_cover)
            and all(isinstance(v, int) and v >= args.metric_tokens for v in completion_counts)
        ),
        "required_policy": "fixed realistic prompt suite; each prompt once; cached_tokens=0 every row; no repeated/warmed prompt averaging; metric is median tokens 1-100 after TTFT",
        "metric_name": "median_tok_s_1_100_after_ttft",
        "metric_tokens": args.metric_tokens,
        "token_timing_source": token_timing_source,
        "return_token_ids_requested": args.return_token_ids,
        "cached_tokens_all_zero": all(isinstance(v, int) and v == 0 for v in cached_values),
        "cached_tokens": cached_values,
        "prompts_unique": len(set(prompt_hashes)) == len(prompt_hashes),
        "chunk_count_matches_completion_tokens_all": all(chunk_counts_match),
        "chunk_count_matches_completion_tokens_note": (
            "Informational only: llama.cpp usage may count an EOS/final token that "
            "is not emitted as a text delta. Promotion requires enough streamed "
            "text deltas to measure the first metric window."
        ),
        "metric_chunk_events_at_least_window": all(chunks_cover_metric),
        "chunk_counts": chunk_counts,
        "metric_token_id_events_at_least_window": all(token_ids_cover_metric),
        "stream_token_id_counts": token_id_counts,
        "completion_tokens_at_least_metric_window": all(
            isinstance(v, int) and v >= args.metric_tokens for v in completion_counts
        ),
    }
    summary = {
        "tok_s_1_100_after_ttft": stats(metric_values),
        "tok_s_after_ttft_full": stats(full_values),
        "tok_s_wall_full": stats(wall_values),
        "ttft_ms": stats(ttft_values),
    }
    fresh_response_validity = {
        "valid": gate["passed"],
        "classification": "fresh-response" if gate["passed"] else "invalid-or-incomplete",
        "suite_id": suite_meta.get("suite_id"),
        "suite_version": suite_meta.get("version"),
        "prompts_are_unique": gate["prompts_unique"],
        "prompt_count": len(prompts),
        "each_prompt_run_once": len(rows) == len(prompts),
        "cached_tokens_all_zero": gate["cached_tokens_all_zero"],
        "cached_tokens": cached_values,
        "history_acceleration": False,
        "ngram_history_acceleration": False,
        "response_reuse": False,
        "context_checkpoints_or_prefix_reuse": False,
        "primary_metric_name": gate["metric_name"],
        "primary_metric_tokens": args.metric_tokens,
        "token_timing_source": gate["token_timing_source"],
        "return_token_ids_requested": args.return_token_ids,
        "chat_reasoning_delta_counts": [
            row.get("reasoning_delta_count") for row in rows
        ],
        "note": (
            "Fixed realistic suite; each prompt is sent once as a cold response. "
            "Do not average synthetic repeated prompts, warmed continuations, "
            "or n-gram/history-accelerated rows into this metric."
        ),
    }
    result = {
        "run_identity": {
            "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
            "base_url": args.base_url,
            "model": args.model,
            "api_mode": args.api_mode,
            "suite_path": str(args.suite),
            "suite": suite_meta,
            "prompt_count": len(prompts),
            "max_tokens": args.max_tokens,
            "seed": args.seed,
            "request_extra": request_extra,
            "return_token_ids": args.return_token_ids,
        },
        "realistic_final_gate": gate,
        "fresh_response_validity": fresh_response_validity,
        "summary": summary,
        "prompt_sha256s": prompt_hashes,
        "output_sha256s": [row["sha256"] for row in rows],
        "rows": rows,
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    print(text)
    return 0 if gate["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
