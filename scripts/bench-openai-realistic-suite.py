#!/usr/bin/env python3
"""Cold realistic prompt-suite benchmark for OpenAI-compatible endpoints."""

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


PROMOTION_OUTPUT_TOKENS = 512
MIN_PROMOTION_PROMPT_CLASSES = 5
PROMOTION_PROMPT_CLASSES = {
    "incident-retrospective": "operations",
    "code-review": "code",
    "customer-email": "prose",
    "sql-debugging": "code",
    "release-plan": "operations",
    "benchmark-analysis": "analysis",
    "architecture-tradeoff": "analysis",
    "bug-report-synthesis": "operations",
    "technical-guide": "documentation",
    "risk-register": "structured-writing",
    "performance-hypotheses": "analysis",
    "decision-memo": "prose",
}


def native_cached_tokens(event: dict[str, Any]) -> int | None:
    """Return reused prompt tokens, not native ``tokens_cached`` slot length."""
    timings = event.get("timings")
    if isinstance(timings, dict) and isinstance(timings.get("cache_n"), int):
        return timings["cache_n"]
    value = event.get("prompt_tokens_cached")
    if isinstance(value, int):
        return value
    return None


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
    system_prompt: str | None,
    request_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any]
    if api_mode == "native":
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        template_req = urllib.request.Request(
            f"{base_url.rstrip('/')}/apply-template",
            data=json.dumps({"messages": messages}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(template_req, timeout=timeout) as template_resp:
            rendered = json.loads(template_resp.read())["prompt"]
        payload = {
            "prompt": rendered,
            "n_predict": max_tokens,
            "temperature": 0,
            "stream": True,
            "return_tokens": True,
        }
    else:
        payload = {
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
        payload["messages"] = []
        if system_prompt:
            payload["messages"].append({"role": "system", "content": system_prompt})
        payload["messages"].append({"role": "user", "content": prompt})
    elif api_mode == "completions":
        endpoint = "completions"
        payload["prompt"] = prompt
    else:
        endpoint = "completion"
    payload.update(request_extra)

    headers = {"Content-Type": "application/json"}
    if request_id:
        headers["X-Request-Id"] = request_id

    endpoint_url = (
        f"{base_url.rstrip('/')}/{endpoint}"
        if api_mode == "native"
        else f"{base_url.rstrip('/')}/v1/{endpoint}"
    )
    req = urllib.request.Request(
        endpoint_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    started_epoch_s = time.time()
    started = time.perf_counter()
    first_text_at: float | None = None
    first_text_epoch_s: float | None = None
    text_parts: list[str] = []
    chunk_offsets: list[float] = []
    token_id_offsets: list[float] = []
    token_ids: list[int] = []
    response_ids: list[str] = []
    content_delta_count = 0
    reasoning_delta_count = 0
    usage: dict[str, Any] = {}
    response_x_request_id: str | None = None
    logprob_content: list[dict[str, Any]] = []
    finish_reasons: list[str] = []

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        response_x_request_id = resp.headers.get("X-Request-Id")
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            event = json.loads(data)
            event_id = event.get("id")
            if isinstance(event_id, str):
                response_ids.append(event_id)
            if event.get("usage"):
                usage = event["usage"]
            if api_mode == "native":
                choice_token_ids = event.get("tokens")
                if isinstance(choice_token_ids, list):
                    now = time.perf_counter()
                    token_ids.extend(int(token_id) for token_id in choice_token_ids)
                    if first_text_at is None and choice_token_ids:
                        first_text_at = now
                        first_text_epoch_s = time.time()
                    token_id_offsets.extend(
                        [now - started] * len(choice_token_ids)
                    )
                token_text = event.get("content") or ""
                if token_text:
                    now = time.perf_counter()
                    if first_text_at is None:
                        first_text_at = now
                        first_text_epoch_s = time.time()
                    text_parts.append(token_text)
                    chunk_offsets.append(now - started)
                if event.get("stop"):
                    completion_count = event.get("tokens_predicted")
                    prompt_count = event.get("tokens_evaluated")
                    native_cached = native_cached_tokens(event)
                    usage = {
                        "completion_tokens": completion_count,
                        "prompt_tokens": prompt_count,
                        "total_tokens": (
                            completion_count + prompt_count
                            if isinstance(completion_count, int)
                            and isinstance(prompt_count, int)
                            else None
                        ),
                        "prompt_tokens_details": {
                            "cached_tokens": native_cached,
                        },
                    }
                continue
            verbose_event = event.get("__verbose")
            verbose_token_ids = (
                verbose_event.get("tokens")
                if isinstance(verbose_event, dict)
                else None
            )
            if isinstance(verbose_token_ids, list):
                now = time.perf_counter()
                token_ids.extend(int(token_id) for token_id in verbose_token_ids)
                if first_text_at is None and verbose_token_ids:
                    first_text_at = now
                    first_text_epoch_s = time.time()
                token_id_offsets.extend(
                    [now - started] * len(verbose_token_ids)
                )
            for choice in event.get("choices", []):
                finish_reason = choice.get("finish_reason")
                if isinstance(finish_reason, str):
                    finish_reasons.append(finish_reason)
                choice_logprobs = choice.get("logprobs")
                if isinstance(choice_logprobs, dict):
                    content_logprobs = choice_logprobs.get("content")
                    if isinstance(content_logprobs, list):
                        logprob_content.extend(
                            item for item in content_logprobs if isinstance(item, dict)
                        )
                choice_token_ids = choice.get("token_ids")
                if isinstance(choice_token_ids, list):
                    now = time.perf_counter()
                    token_ids.extend(int(token_id) for token_id in choice_token_ids)
                    if first_text_at is None and choice_token_ids:
                        first_text_at = now
                        first_text_epoch_s = time.time()
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
                    first_text_epoch_s = time.time()
                text_parts.append(token_text)
                chunk_offsets.append(now - started)

    ended_epoch_s = time.time()
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
        "request_id": request_id,
        "response_x_request_id": response_x_request_id,
        "response_id_first": response_ids[0] if response_ids else None,
        "response_id_last": response_ids[-1] if response_ids else None,
        "request_started_epoch_s": started_epoch_s,
        "first_text_epoch_s": first_text_epoch_s,
        "request_ended_epoch_s": ended_epoch_s,
        "ttft_s": ttft_s,
        "post_ttft_s": post_ttft_s,
        "chunk_count": len(chunk_offsets),
        "stream_token_id_count": len(token_id_offsets),
        "content_delta_count": content_delta_count,
        "reasoning_delta_count": reasoning_delta_count,
        "chunk_offsets_s": chunk_offsets,
        "token_id_offsets_s": token_id_offsets,
        "token_ids": token_ids,
        "logprob_content": logprob_content,
        "finish_reasons": finish_reasons,
        "usage": usage,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "tok_s_wall_full": tok_s_wall,
        "tok_s_after_ttft_full": tok_s_after_ttft_full,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text": text,
        "text_preview": text[:320],
    }


def safe_request_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", value).strip("-")[:180]


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


def class_balanced_stats(
    rows: list[dict[str, Any]], value_key: str
) -> dict[str, Any]:
    """Give each prompt class equal weight in the published median."""
    grouped: dict[str, list[float]] = {}
    for row in rows:
        prompt_class = row.get("prompt_class")
        value = row.get(value_key)
        if (
            isinstance(prompt_class, str)
            and prompt_class != "unclassified"
            and isinstance(value, (int, float))
        ):
            grouped.setdefault(prompt_class, []).append(float(value))
    class_medians = {
        prompt_class: statistics.median(values)
        for prompt_class, values in sorted(grouped.items())
    }
    result: dict[str, Any] = stats(list(class_medians.values()))
    result["aggregation"] = "median-of-prompt-class-medians"
    result["class_medians"] = class_medians
    result["class_prompt_counts"] = {
        prompt_class: len(grouped[prompt_class]) for prompt_class in class_medians
    }
    return result


def cached_tokens(row: dict[str, Any]) -> int | None:
    usage = row.get("usage")
    if not isinstance(usage, dict):
        return None
    details = usage.get("prompt_tokens_details")
    if not isinstance(details, dict):
        return None
    value = details.get("cached_tokens")
    return value if isinstance(value, int) else None


def event_window_rates(
    offsets: list[float], event_count: int
) -> tuple[float | None, float | None]:
    """Return legacy inclusive-event and conventional interval rates."""
    if event_count <= 1 or len(offsets) < event_count:
        return None, None
    duration = offsets[event_count - 1] - offsets[0]
    if duration <= 0:
        return None, None
    return event_count / duration, (event_count - 1) / duration


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
        prompt_class = (
            item.get("prompt_class") if isinstance(item, dict) else None
        ) or PROMOTION_PROMPT_CLASSES.get(prompt_id)
        out.append(
            {
                "id": prompt_id,
                "prompt": prompt,
                "prompt_class": prompt_class or "unclassified",
            }
        )
    return meta, out


def promotion_gate_failures(
    *,
    screening_passed: bool,
    selected_prompt_ids: list[str],
    completed_prompt_count: int,
    suite_prompt_count: int,
    max_tokens: int,
    metric_tokens: int,
    completion_counts: list[Any],
    ignore_eos: bool,
    prompt_classes: list[str],
) -> list[str]:
    """Return fail-closed reasons that keep a run out of public promotion.

    A short or filtered run can still be useful screening evidence.  It must
    never call itself the realistic *final* gate, however, because the lab's
    publication policy requires the complete fixed suite and full 512-token
    response cap with enough natural output to cover the declared metric.
    Keep this check independent of summary statistics so payload
    builders can re-validate raw evidence rather than trusting a stored
    boolean.
    """
    failures: list[str] = []
    if not screening_passed:
        failures.append("fresh_response_screening_failed")
    if selected_prompt_ids:
        failures.append("prompt_subset_selected")
    if completed_prompt_count != suite_prompt_count:
        failures.append("fixed_suite_incomplete")
    if suite_prompt_count < 12:
        failures.append("fixed_suite_has_fewer_than_12_prompts")
    if max_tokens != PROMOTION_OUTPUT_TOKENS:
        failures.append("max_tokens_must_equal_512")
    if metric_tokens != 100:
        failures.append("metric_window_must_equal_100_events")
    if not completion_counts or any(
        not isinstance(value, int) or value < 100 for value in completion_counts
    ):
        failures.append("every_completion_must_cover_100_event_metric")
    if ignore_eos:
        failures.append("ignore_eos_must_be_disabled")
    classified = {
        value for value in prompt_classes
        if isinstance(value, str) and value and value != "unclassified"
    }
    if len(prompt_classes) != suite_prompt_count or len(classified) < MIN_PROMOTION_PROMPT_CLASSES:
        failures.append("fixed_suite_lacks_varied_prompt_classes")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18260")
    parser.add_argument("--model", default="gemma4-26b-a4b-q8")
    parser.add_argument(
        "--api-mode", choices=("chat", "completions", "native"), default="chat"
    )
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
        "--prompt-id",
        action="append",
        default=[],
        help="Run only this suite prompt ID; repeat for a bounded subset.",
    )
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
    parser.add_argument(
        "--require-natural-eos",
        action="store_true",
        help=(
            "Reject ignore_eos=true and require a recorded stop/length reason. "
            "A length finish means the declared 512-token cap was reached; it "
            "is not mislabeled as a natural EOS token."
        ),
    )
    parser.add_argument(
        "--allow-screening",
        action="store_true",
        help=(
            "Return success for a fresh-response diagnostic that does not meet "
            "the full promotion gate. The JSON still records "
            "realistic_final_gate.passed=false and cannot be submitted."
        ),
    )
    args = parser.parse_args()
    request_extra = json.loads(args.request_extra_json)
    if not isinstance(request_extra, dict):
        raise SystemExit("--request-extra-json must decode to a JSON object")
    if args.require_natural_eos and request_extra.get("ignore_eos") is True:
        raise SystemExit("--require-natural-eos rejects ignore_eos=true")

    suite_meta, prompts = load_suite(args.suite)
    suite_prompt_count = len(prompts)
    if args.prompt_id:
        requested = set(args.prompt_id)
        selected = [item for item in prompts if item["id"] in requested]
        found = {item["id"] for item in selected}
        missing = sorted(requested - found)
        if missing:
            raise SystemExit(f"unknown --prompt-id values: {', '.join(missing)}")
        prompts = selected
    system_prompt = suite_meta.get("system_prompt")
    if system_prompt is not None and not isinstance(system_prompt, str):
        raise SystemExit("suite system_prompt must be a string when present")
    rows: list[dict[str, Any]] = []
    suite_id = safe_request_id(str(suite_meta.get("suite_id") or args.suite.stem))
    for index, item in enumerate(prompts):
        prompt = item["prompt"]
        request_id = safe_request_id(
            f"bench-{suite_id}-{index:02d}-{item['id']}"
        )
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
            system_prompt=system_prompt,
            request_id=request_id,
        )
        row["prompt_index"] = index
        row["prompt_id"] = item["id"]
        row["prompt_class"] = item["prompt_class"]
        row["prompt_sha256"] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if args.return_token_ids and row.get("stream_token_id_count"):
            offsets = row["token_id_offsets_s"]
            timing_source = "openai_stream_token_ids_chunk_timestamp"
        else:
            offsets = row["chunk_offsets_s"]
            timing_source = "openai_stream_content_or_reasoning_delta"
        legacy_rate, interval_rate = event_window_rates(offsets, args.metric_tokens)
        row["tok_s_1_100_after_ttft"] = legacy_rate
        row["tok_s_1_100_after_ttft_legacy_inclusive_events"] = legacy_rate
        row["tok_s_1_100_intervals_after_ttft"] = interval_rate
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
    interval_metric_values = [
        float(row["tok_s_1_100_intervals_after_ttft"])
        for row in rows
        if isinstance(
            row.get("tok_s_1_100_intervals_after_ttft"), (int, float)
        )
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
    finish_reasons = [row.get("finish_reasons") for row in rows]
    finish_reasons_known = [
        isinstance(values, list)
        and bool(values)
        and all(value in ("stop", "length") for value in values)
        for values in finish_reasons
    ]
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

    screening_passed = (
        len(rows) == len(prompts)
        and len(metric_values) == len(rows)
        and all(isinstance(v, int) and v == 0 for v in cached_values)
        and len(set(prompt_hashes)) == len(prompt_hashes)
        and all(metric_events_cover)
        and all(
            isinstance(v, int) and v >= args.metric_tokens
            for v in completion_counts
        )
        and (not args.require_natural_eos or all(finish_reasons_known))
    )
    promotion_failures = promotion_gate_failures(
        screening_passed=screening_passed,
        selected_prompt_ids=args.prompt_id,
        completed_prompt_count=len(rows),
        suite_prompt_count=suite_prompt_count,
        max_tokens=args.max_tokens,
        metric_tokens=args.metric_tokens,
        completion_counts=completion_counts,
        ignore_eos=request_extra.get("ignore_eos") is True,
        prompt_classes=[item["prompt_class"] for item in prompts],
    )
    gate = {
        "passed": not promotion_failures,
        "gate_scope": "performance-workload-only",
        "overall_public_promotion_requires_independent_quality_attestation": True,
        "promotion_failures": promotion_failures,
        "required_policy": (
            "complete fixed varied-prompt suite; every prompt exactly once; "
            "cached_tokens=0 every row; no prompt subset, prompt/KV/history/"
            "response reuse, ignore_eos, or warmed-prompt averaging; exactly "
            "a 512-token natural-completion cap with every response covering "
            "the 100-event metric; primary metric is the median of the per-"
            "prompt-class medians for the 99 intervals between generated "
            "events 1-100"
        ),
        "suite_prompt_count": suite_prompt_count,
        "completed_prompt_count": len(rows),
        "full_suite_selected": not args.prompt_id and len(rows) == suite_prompt_count,
        "prompt_classes": sorted({row["prompt_class"] for row in rows}),
        "required_distinct_prompt_classes": MIN_PROMOTION_PROMPT_CLASSES,
        "required_output_cap_tokens": PROMOTION_OUTPUT_TOKENS,
        "requested_output_cap_tokens": args.max_tokens,
        "completion_tokens_cover_metric_all": all(
            isinstance(v, int) and v >= args.metric_tokens
            for v in completion_counts
        ),
        "metric_name": "median_tok_s_1_100_after_ttft",
        "preferred_metric_name": (
            "median_of_prompt_class_medians_tok_s_1_100_intervals_after_ttft"
        ),
        "preferred_metric_aggregation": "median-of-prompt-class-medians",
        "metric_tokens": args.metric_tokens,
        "metric_events": args.metric_tokens,
        "metric_intervals": args.metric_tokens - 1,
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
        "natural_eos_required": args.require_natural_eos,
        "ignore_eos": request_extra.get("ignore_eos") is True,
        "finish_reasons_known_all": all(finish_reasons_known),
        "finish_reasons": finish_reasons,
    }
    summary = {
        "tok_s_1_100_after_ttft": stats(metric_values),
        "tok_s_1_100_after_ttft_legacy_inclusive_events": stats(metric_values),
        "tok_s_1_100_intervals_after_ttft": stats(interval_metric_values),
        "class_balanced_tok_s_1_100_intervals_after_ttft": (
            class_balanced_stats(
                rows, "tok_s_1_100_intervals_after_ttft"
            )
        ),
        "tok_s_after_ttft_full": stats(full_values),
        "tok_s_wall_full": stats(wall_values),
        "ttft_ms": stats(ttft_values),
    }
    fresh_response_validity = {
        "valid": screening_passed,
        "performance_gate_eligible": gate["passed"],
        "overall_public_promotion_eligible": False,
        "classification": (
            "promotion-grade-fresh-response"
            if gate["passed"]
            else "fresh-response-screening"
            if screening_passed
            else "invalid-or-incomplete"
        ),
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
        "preferred_metric_name": gate["preferred_metric_name"],
        "preferred_metric_aggregation": gate[
            "preferred_metric_aggregation"
        ],
        "primary_metric_accounting": "legacy-inclusive-events",
        "preferred_metric_accounting": "inter-token-intervals",
        "metric_window_generated_events": args.metric_tokens,
        "metric_window_intervals": args.metric_tokens - 1,
        "token_timing_source": gate["token_timing_source"],
        "return_token_ids_requested": args.return_token_ids,
        "chat_reasoning_delta_counts": [
            row.get("reasoning_delta_count") for row in rows
        ],
        "note": (
            "Fixed realistic suite; each prompt is sent once as a cold response. "
            "Do not average synthetic repeated prompts, warmed continuations, "
            "or n-gram/history-accelerated rows into this metric. Passing this "
            "artifact certifies only the performance workload; publication also "
            "requires a hash-bound independent quality/determinism attestation."
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
            "suite_prompt_count": suite_prompt_count,
            "prompt_classes": sorted({item["prompt_class"] for item in prompts}),
            "max_tokens": args.max_tokens,
            "seed": args.seed,
            "request_extra": request_extra,
            "system_prompt": system_prompt,
            "return_token_ids": args.return_token_ids,
            "selected_prompt_ids": args.prompt_id,
            "require_natural_eos": args.require_natural_eos,
            "allow_screening": args.allow_screening,
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
    return 0 if gate["passed"] or (args.allow_screening and screening_passed) else 2


if __name__ == "__main__":
    raise SystemExit(main())
