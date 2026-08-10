#!/usr/bin/env python3
"""One cold OpenAI text-completion stream per fixed realistic prompt.

The pinned llama.cpp runtime exposes per-token IDs in ``__verbose.tokens`` on
the text-completions route when ``verbose`` and ``return_tokens`` are enabled.
Preparation is deliberately separate so template rendering completes before
the metrics-before snapshot that brackets the scored generation requests.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import statistics
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SUITE_SHA256 = "df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def validate_base_url(value: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.port is None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "base URL must be a loopback HTTP origin with an explicit port"
        )
    return value.rstrip("/")


def post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError(f"unexpected response origin/status from {url}")
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError(f"non-object response from {url}")
    return value


def load_suite(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    if sha256_bytes(path.read_bytes()) != SUITE_SHA256:
        raise ValueError("fixed suite SHA-256 mismatch")
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or not isinstance(value.get("prompts"), list):
        raise ValueError("fixed suite is malformed")
    prompts: list[dict[str, str]] = []
    for item in value["prompts"]:
        if not isinstance(item, dict):
            raise ValueError("fixed suite prompt is malformed")
        prompt_id = item.get("id")
        prompt = item.get("prompt")
        if not isinstance(prompt_id, str) or not isinstance(prompt, str):
            raise ValueError("fixed suite prompt identity is malformed")
        prompts.append({"id": prompt_id, "prompt": prompt})
    return {key: item for key, item in value.items() if key != "prompts"}, prompts


def atomic_output(path: Path, value: Any) -> None:
    if path.exists():
        raise ValueError(f"refusing to overwrite output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def prepare(args: argparse.Namespace) -> int:
    base_url = validate_base_url(args.base_url)
    suite_meta, prompts = load_suite(args.suite)
    rows = []
    for index, item in enumerate(prompts):
        rendered = post_json(
            f"{base_url}/apply-template",
            {"messages": [{"role": "user", "content": item["prompt"]}]},
            args.timeout,
        ).get("prompt")
        if not isinstance(rendered, str) or not rendered:
            raise ValueError(f"empty rendered prompt for {item['id']}")
        rows.append(
            {
                "prompt_index": index,
                "prompt_id": item["id"],
                "prompt_sha256": sha256_bytes(item["prompt"].encode()),
                "rendered_prompt": rendered,
                "rendered_prompt_sha256": sha256_bytes(rendered.encode()),
            }
        )
    atomic_output(
        args.output,
        {
            "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
            "base_url": base_url,
            "suite_path": str(args.suite.resolve()),
            "suite_sha256": SUITE_SHA256,
            "suite": suite_meta,
            "generation_requests": 0,
            "rows": rows,
        },
    )
    return 0


def safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", value).strip("-")[:180]


def stream_once(
    base_url: str,
    model: str,
    prompt: str,
    request_id: str,
    timeout: int,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": 512,
        "temperature": 0,
        "top_p": 1,
        "seed": 1,
        "stream": True,
        "stream_options": {"include_usage": True},
        "cache_prompt": False,
        "verbose": True,
        "return_tokens": True,
        "ignore_eos": False,
        "id_slot": 0,
    }
    request = urllib.request.Request(
        f"{base_url}/v1/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Request-Id": request_id},
        method="POST",
    )
    started_epoch = time.time()
    started = time.perf_counter()
    text_parts: list[str] = []
    streamed_ids: list[int] = []
    offsets: list[float] = []
    complete_positions: list[int] = []
    final_verbose_tokens: list[int] | None = None
    final_verbose_content: str | None = None
    final_usage: dict[str, Any] | None = None
    final_timings: dict[str, Any] | None = None
    response_ids: list[str] = []
    finish_reasons: list[str] = []
    final_event_count = 0
    done_count = 0
    usage_event_count = 0
    final_timings_event_count = 0
    partial_timings_events: list[dict[str, Any]] = []
    token_event_count = 0
    final_verbose: dict[str, Any] | None = None
    requested_url = f"{base_url}/v1/completions"
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200 or response.geturl() != requested_url:
            raise ValueError("scored completion redirected or returned non-200")
        response_request_id = response.headers.get("X-Request-Id")
        for raw in response:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            encoded = line[5:].strip()
            if encoded == "[DONE]":
                done_count += 1
                break
            event = json.loads(encoded)
            if not isinstance(event, dict):
                raise ValueError("OpenAI stream event is not an object")
            if isinstance(event.get("id"), str):
                response_ids.append(event["id"])
            choices = event.get("choices")
            is_final = False
            event_text = ""
            if isinstance(choices, list):
                for choice in choices:
                    if not isinstance(choice, dict):
                        continue
                    reason = choice.get("finish_reason")
                    if isinstance(reason, str):
                        finish_reasons.append(reason)
                        is_final = True
                    text = choice.get("text")
                    if isinstance(text, str) and text and not is_final:
                        text_parts.append(text)
                        event_text += text
            verbose = event.get("__verbose")
            event_ids = verbose.get("tokens") if isinstance(verbose, dict) else None
            if isinstance(event_ids, list) and all(
                isinstance(token, int) and not isinstance(token, bool) and token >= 0
                for token in event_ids
            ):
                if is_final:
                    final_verbose_tokens = event_ids
                    final_verbose = verbose
                    content = verbose.get("content")
                    if isinstance(content, str):
                        final_verbose_content = content
                elif event_ids:
                    if verbose.get("stop") is not False or verbose.get("id_slot") != 0:
                        raise ValueError(
                            "partial verbose token event identity mismatch"
                        )
                    predicted = verbose.get("tokens_predicted")
                    if not isinstance(predicted, int) or predicted < len(event_ids):
                        raise ValueError("partial verbose token position is malformed")
                    positions = list(range(predicted - len(event_ids), predicted))
                    if verbose.get("content") != event_text:
                        raise ValueError("partial OAI/native content mismatch")
                    if complete_positions and positions[0] <= complete_positions[-1]:
                        raise ValueError(
                            "partial verbose token positions are not increasing"
                        )
                    now = time.perf_counter() - started
                    streamed_ids.extend(event_ids)
                    offsets.extend([now] * len(event_ids))
                    complete_positions.extend(positions)
                    token_event_count += 1
            if is_final:
                final_event_count += 1
            if isinstance(event.get("usage"), dict):
                final_usage = event["usage"]
                usage_event_count += 1
            if isinstance(event.get("timings"), dict):
                if is_final:
                    final_timings = event["timings"]
                    final_timings_event_count += 1
                else:
                    partial_timings_events.append(event["timings"])
    ended = time.perf_counter()
    if (
        final_usage is None
        or final_timings is None
        or final_verbose_tokens is None
        or final_verbose_content is None
        or final_verbose is None
    ):
        raise ValueError("stream lacks exactly attributable final usage/timings/tokens")
    streamed_content = "".join(text_parts)
    if final_event_count != 1:
        raise ValueError("stream must contain exactly one final event")
    if final_verbose_tokens or final_verbose_content:
        raise ValueError("pinned OAI final stream event unexpectedly retained payload")
    if not response_ids or len(set(response_ids)) != 1:
        raise ValueError("stream response ID is missing or inconsistent")
    if (
        done_count != 1
        or usage_event_count != 1
        or final_timings_event_count != 1
        or len(partial_timings_events) > 1
    ):
        raise ValueError("stream final/usage/timing cardinality mismatch")
    if (
        final_verbose.get("stop") is not True
        or final_verbose.get("id_slot") != 0
        or final_verbose.get("tokens") != []
        or final_verbose.get("content") != ""
    ):
        raise ValueError("final verbose stream identity mismatch")
    completion_n = final_usage.get("completion_tokens")
    if (
        not isinstance(completion_n, int)
        or isinstance(completion_n, bool)
        or not 100 <= completion_n <= 512
        or final_timings.get("predicted_n") != completion_n
        or final_verbose.get("tokens_predicted") != completion_n
        or not complete_positions
        or complete_positions[-1] >= completion_n
    ):
        raise ValueError("final generated-token cardinality mismatch")
    prompt_n = final_usage.get("prompt_tokens")
    predicted_ms = final_timings.get("predicted_ms")
    predicted_per_second = final_timings.get("predicted_per_second")
    if (
        not isinstance(prompt_n, int)
        or isinstance(prompt_n, bool)
        or prompt_n <= 0
        or final_usage.get("total_tokens") != prompt_n + completion_n
        or (final_usage.get("prompt_tokens_details") or {}).get("cached_tokens") != 0
        or final_timings.get("cache_n") != 0
        or not isinstance(predicted_ms, (int, float))
        or isinstance(predicted_ms, bool)
        or predicted_ms <= 0
        or not isinstance(predicted_per_second, (int, float))
        or isinstance(predicted_per_second, bool)
        or predicted_per_second <= 0
        or not math.isclose(
            float(predicted_per_second),
            1000 * completion_n / float(predicted_ms),
            rel_tol=1e-6,
            abs_tol=1e-6,
        )
        or final_verbose.get("prompt") != prompt
    ):
        raise ValueError("final usage/timing/prompt binding mismatch")
    if partial_timings_events and any(
        partial_timings_events[0].get(key) != final_timings.get(key)
        for key in ("predicted_n", "predicted_ms", "predicted_per_second")
    ):
        raise ValueError("partial/final timing evidence mismatch")
    stop_type = final_verbose.get("stop_type")
    expected_finish = "length" if stop_type == "limit" else "stop"
    if (
        final_verbose.get("truncated") is not False
        or stop_type not in {"limit", "eos", "word"}
        or finish_reasons != [expected_finish]
    ):
        raise ValueError("final stop semantics mismatch")
    first = offsets[0] if offsets else None
    elapsed = ended - started
    return {
        "request_id": request_id,
        "response_x_request_id": response_request_id,
        "response_ids": response_ids,
        "finish_reasons": finish_reasons,
        "final_event_count": final_event_count,
        "done_count": done_count,
        "usage_event_count": usage_event_count,
        "final_timings_event_count": final_timings_event_count,
        "partial_timings_events": partial_timings_events,
        "token_event_count": token_event_count,
        "request_started_epoch_s": started_epoch,
        "elapsed_s": elapsed,
        "ttft_s": first,
        "post_ttft_s": elapsed - first if first is not None else None,
        "stream_token_id_count": len(streamed_ids),
        "token_ids": streamed_ids,
        "token_id_offsets_s": offsets,
        "stream_complete_positions": complete_positions,
        "stream_position_token_offsets": [
            {"complete_position": position, "token_id": token, "offset_s": offset}
            for position, token, offset in zip(
                complete_positions, streamed_ids, offsets
            )
        ],
        "final_verbose_tokens": final_verbose_tokens,
        "final_verbose_content": final_verbose_content,
        "final_verbose": final_verbose,
        "final_prompt_sha256": sha256_bytes(
            str(final_verbose.get("prompt", "")).encode()
        ),
        "usage": final_usage,
        "timings": final_timings,
        "prompt_tokens": final_usage.get("prompt_tokens"),
        "completion_tokens": final_usage.get("completion_tokens"),
        "cached_tokens": (final_usage.get("prompt_tokens_details") or {}).get(
            "cached_tokens"
        ),
        "tok_s_wall_full": (
            final_usage.get("completion_tokens") / elapsed
            if isinstance(final_usage.get("completion_tokens"), int) and elapsed > 0
            else None
        ),
        "tok_s_after_ttft_full": (
            final_usage.get("completion_tokens") / (elapsed - first)
            if isinstance(final_usage.get("completion_tokens"), int)
            and first is not None
            and elapsed > first
            else None
        ),
        "sha256": sha256_bytes(streamed_content.encode()),
        "content": streamed_content,
        "stream_content_sha256": sha256_bytes(streamed_content.encode()),
        "final_payload_intentionally_empty": True,
        "request_payload": payload,
    }


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] * (1 - position + low) + ordered[high] * (position - low)


def stats(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "p10": None, "median": None, "mean": None}
    return {
        "count": len(values),
        "p10": percentile(values, 0.1),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
    }


def run(args: argparse.Namespace) -> int:
    base_url = validate_base_url(args.base_url)
    prepared = json.loads(args.prepared.read_text())
    rows_in = prepared.get("rows") if isinstance(prepared, dict) else None
    if (
        not isinstance(rows_in, list)
        or len(rows_in) != 12
        or prepared.get("suite_sha256") != SUITE_SHA256
        or prepared.get("generation_requests") != 0
        or prepared.get("base_url") != base_url
    ):
        raise ValueError("prepared suite artifact is invalid")
    rows = []
    suite_id = prepared.get("suite", {}).get("suite_id")
    for index, item in enumerate(rows_in):
        request_id = safe_id(f"bench-{suite_id}-{index:02d}-{item['prompt_id']}")
        row = stream_once(
            base_url,
            args.model,
            item["rendered_prompt"],
            request_id,
            args.timeout,
        )
        row.update(
            {
                "prompt_index": index,
                "prompt_id": item["prompt_id"],
                "prompt_sha256": item["prompt_sha256"],
                "rendered_prompt_sha256": item["rendered_prompt_sha256"],
                "token_timing_source": "llamacpp_oai_completion_verbose_token_ids",
            }
        )
        rows.append(row)
    cache_zero = all(row["cached_tokens"] == 0 for row in rows)
    enough = all(row["stream_token_id_count"] >= 100 for row in rows)
    result = {
        "run_identity": {
            "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
            "base_url": base_url,
            "model": args.model,
            "api_mode": "completions",
            "suite_path": prepared.get("suite_path"),
            "suite": prepared.get("suite"),
            "suite_sha256": SUITE_SHA256,
            "prepared_path": str(args.prepared.resolve()),
            "prepared_sha256": sha256_bytes(args.prepared.read_bytes()),
            "prompt_count": 12,
            "max_tokens": 512,
            "seed": 1,
            "temperature": 0,
            "top_p": 1,
            "ignore_eos": False,
            "request_extra": {
                "cache_prompt": False,
                "ignore_eos": False,
                "id_slot": 0,
                "return_tokens": True,
                "verbose": True,
            },
            "return_token_ids": True,
            "generation_requests_per_prompt": 1,
            "replay_requests": 0,
        },
        "realistic_final_gate": {
            "passed": len(rows) == 12 and cache_zero and enough,
            "metric_tokens": 100,
            "token_timing_source": "llamacpp_oai_completion_verbose_token_ids",
        },
        "fresh_response_validity": {
            "valid": len(rows) == 12 and cache_zero and enough,
            "each_prompt_run_once": True,
            "cached_tokens_all_zero": cache_zero,
            "history_acceleration": False,
            "ngram_history_acceleration": False,
            "response_reuse": False,
            "context_checkpoints_or_prefix_reuse": False,
        },
        "metric_accounting": {
            "schema": "realistic-window-accounting-v2-oracle-aligned",
            "timestamped_events": 100,
            "inter_token_intervals": 99,
            "timing_source": "llamacpp_oai_completion_verbose_token_ids",
        },
        "summary": {
            "client_full_after_ttft_tok_s": stats(
                [float(row["tok_s_after_ttft_full"]) for row in rows]
            ),
            "native_predicted_tok_s": stats(
                [float(row["timings"]["predicted_per_second"]) for row in rows]
            ),
        },
        "rows": rows,
    }
    atomic_output(args.output, result)
    return 0 if result["realistic_final_gate"]["passed"] else 1


def forensic_once(
    base_url: str,
    model: str,
    prompt: str,
    request_id: str,
    timeout: int,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": 512,
        "temperature": 0,
        "top_p": 1,
        "seed": 1,
        "stream": False,
        "cache_prompt": False,
        "verbose": True,
        "return_tokens": True,
        "ignore_eos": False,
        "id_slot": 0,
    }
    request = urllib.request.Request(
        f"{base_url}/v1/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Request-Id": request_id},
        method="POST",
    )
    started = time.perf_counter()
    requested_url = f"{base_url}/v1/completions"
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200 or response.geturl() != requested_url:
            raise ValueError("forensic completion redirected or returned non-200")
        response_request_id = response.headers.get("X-Request-Id")
        value = json.load(response)
    elapsed = time.perf_counter() - started
    if not isinstance(value, dict):
        raise ValueError("forensic response is not an object")
    choices = value.get("choices")
    verbose = value.get("__verbose")
    usage = value.get("usage")
    timings = value.get("timings")
    if (
        not isinstance(choices, list)
        or len(choices) != 1
        or not isinstance(choices[0], dict)
        or not isinstance(verbose, dict)
        or not isinstance(usage, dict)
        or not isinstance(timings, dict)
    ):
        raise ValueError("forensic response schema mismatch")
    tokens = verbose.get("tokens")
    content = verbose.get("content")
    if (
        not isinstance(tokens, list)
        or not all(
            isinstance(token, int) and not isinstance(token, bool) and token >= 0
            for token in tokens
        )
        or not isinstance(content, str)
        or choices[0].get("text") != content
        or verbose.get("stop") is not True
        or verbose.get("id_slot") != 0
    ):
        raise ValueError("forensic native payload mismatch")
    completion_n = usage.get("completion_tokens")
    prompt_n = usage.get("prompt_tokens")
    predicted_ms = timings.get("predicted_ms")
    predicted_per_second = timings.get("predicted_per_second")
    stop_type = verbose.get("stop_type")
    expected_finish = "length" if stop_type == "limit" else "stop"
    response_id = value.get("id")
    if (
        not isinstance(response_id, str)
        or not response_id
        or not isinstance(completion_n, int)
        or isinstance(completion_n, bool)
        or completion_n != len(tokens)
        or not 100 <= completion_n <= 512
        or not isinstance(prompt_n, int)
        or isinstance(prompt_n, bool)
        or prompt_n <= 0
        or usage.get("total_tokens") != prompt_n + completion_n
        or (usage.get("prompt_tokens_details") or {}).get("cached_tokens") != 0
        or timings.get("cache_n") != 0
        or timings.get("predicted_n") != completion_n
        or verbose.get("tokens_predicted") != completion_n
        or verbose.get("prompt") != prompt
        or verbose.get("truncated") is not False
        or stop_type not in {"limit", "eos", "word"}
        or choices[0].get("finish_reason") != expected_finish
        or not isinstance(predicted_ms, (int, float))
        or isinstance(predicted_ms, bool)
        or predicted_ms <= 0
        or not isinstance(predicted_per_second, (int, float))
        or isinstance(predicted_per_second, bool)
        or predicted_per_second <= 0
        or not math.isclose(
            float(predicted_per_second),
            1000 * completion_n / float(predicted_ms),
            rel_tol=1e-6,
            abs_tol=1e-6,
        )
    ):
        raise ValueError("forensic completion binding mismatch")
    return {
        "request_id": request_id,
        "response_x_request_id": response_request_id,
        "response_id": response_id,
        "finish_reason": choices[0].get("finish_reason"),
        "choice_text": choices[0].get("text"),
        "elapsed_s": elapsed,
        "token_ids": tokens,
        "token_count": len(tokens),
        "content": content,
        "content_sha256": sha256_bytes(content.encode()),
        "usage": usage,
        "timings": timings,
        "verbose": verbose,
        "request_payload": payload,
    }


def forensic(args: argparse.Namespace) -> int:
    base_url = validate_base_url(args.base_url)
    prepared = json.loads(args.prepared.read_text())
    rows_in = prepared.get("rows") if isinstance(prepared, dict) else None
    if (
        not isinstance(rows_in, list)
        or len(rows_in) != 12
        or prepared.get("suite_sha256") != SUITE_SHA256
        or prepared.get("generation_requests") != 0
        or prepared.get("base_url") != base_url
    ):
        raise ValueError("prepared suite artifact is invalid")
    rows = []
    suite_id = prepared.get("suite", {}).get("suite_id")
    for index, item in enumerate(rows_in):
        request_id = safe_id(f"forensic-{suite_id}-{index:02d}-{item['prompt_id']}")
        row = forensic_once(
            base_url,
            args.model,
            item["rendered_prompt"],
            request_id,
            args.timeout,
        )
        row.update(
            {
                "prompt_index": index,
                "prompt_id": item["prompt_id"],
                "prompt_sha256": item["prompt_sha256"],
                "rendered_prompt_sha256": item["rendered_prompt_sha256"],
            }
        )
        rows.append(row)
    result = {
        "run_identity": {
            "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
            "base_url": base_url,
            "model": args.model,
            "api_mode": "completions",
            "evidence_class": "unscored-fresh-forensic-support",
            "suite_sha256": SUITE_SHA256,
            "prepared_path": str(args.prepared.resolve()),
            "prepared_sha256": sha256_bytes(args.prepared.read_bytes()),
            "prompt_count": 12,
            "max_tokens": 512,
            "seed": 1,
            "temperature": 0,
            "top_p": 1,
            "ignore_eos": False,
            "request_extra": {
                "cache_prompt": False,
                "ignore_eos": False,
                "id_slot": 0,
                "return_tokens": True,
                "verbose": True,
            },
            "generation_requests_per_prompt": 1,
            "replay_requests": 0,
        },
        "rows": rows,
    }
    atomic_output(args.output, result)
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--base-url", required=True)
    prep.add_argument("--suite", type=Path, required=True)
    prep.add_argument("--output", type=Path, required=True)
    prep.add_argument("--timeout", type=int, default=900)
    prep.set_defaults(handler=prepare)
    capture = commands.add_parser("run")
    capture.add_argument("--base-url", required=True)
    capture.add_argument("--model", required=True)
    capture.add_argument("--prepared", type=Path, required=True)
    capture.add_argument("--output", type=Path, required=True)
    capture.add_argument("--timeout", type=int, default=900)
    capture.set_defaults(handler=run)
    support = commands.add_parser("forensic")
    support.add_argument("--base-url", required=True)
    support.add_argument("--model", required=True)
    support.add_argument("--prepared", type=Path, required=True)
    support.add_argument("--output", type=Path, required=True)
    support.add_argument("--timeout", type=int, default=900)
    support.set_defaults(handler=forensic)
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        return args.handler(args)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"once-only OpenAI capture failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
