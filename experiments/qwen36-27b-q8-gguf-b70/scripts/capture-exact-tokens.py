#!/usr/bin/env python3
"""Capture llama.cpp native completion token IDs for a fixed prompt suite."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import math
import statistics
import time
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def is_token_id(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_nonempty_token_id_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(is_token_id(token) for token in value)
    )


def computed_prompt_tok_s(prompt_n: Any, prompt_ms: Any) -> float | None:
    if (
        not is_token_id(prompt_n)
        or prompt_n <= 0
        or not isinstance(prompt_ms, (int, float))
        or isinstance(prompt_ms, bool)
        or not math.isfinite(prompt_ms)
        or prompt_ms <= 0
    ):
        return None
    return prompt_n * 1000.0 / prompt_ms


def post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.load(response)
    if not isinstance(result, dict):
        raise RuntimeError(f"non-object response from {url}")
    return result


def stream_completion(
    url: str, payload: dict[str, Any], timeout: int
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    token_ids: list[int] = []
    token_offsets_s: list[float] = []
    content_parts: list[str] = []
    final: dict[str, Any] | None = None
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw in response:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            event = json.loads(data)
            if not isinstance(event, dict):
                raise RuntimeError("non-object SSE event from native completion")
            tokens = event.get("tokens")
            if isinstance(tokens, list) and tokens:
                if not is_nonempty_token_id_list(tokens):
                    raise RuntimeError("non-integer native completion token ID")
                now = time.perf_counter() - started
                token_ids.extend(tokens)
                token_offsets_s.extend([now] * len(tokens))
            content = event.get("content")
            if isinstance(content, str) and content:
                content_parts.append(content)
            if event.get("stop") is True:
                final = event
    ended = time.perf_counter()
    elapsed_s = ended - started
    if final is None:
        raise RuntimeError("native completion stream did not return a final event")
    return {
        "token_ids": token_ids,
        "token_offsets_s": token_offsets_s,
        "content": "".join(content_parts),
        "final": final,
        "request_started_perf_s": started,
        "request_ended_perf_s": ended,
        "elapsed_s": elapsed_s,
    }


def summarize(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "p10": None, "median": None, "mean": None}
    ordered = sorted(values)
    p10_index = max(0, int(0.1 * (len(ordered) - 1)))
    return {
        "count": len(values),
        "p10": ordered[p10_index],
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
    }


def interval_metric(
    offsets: list[float | None], start_index: int, end_index: int, name: str
) -> dict[str, Any]:
    endpoints_available = (
        len(offsets) > end_index
        and offsets[start_index] is not None
        and offsets[end_index] is not None
    )
    interval_count = end_index - start_index if endpoints_available else 0
    duration_s = None
    tok_s = None
    if endpoints_available:
        duration_s = offsets[end_index] - offsets[start_index]  # type: ignore[operator]
        if duration_s > 0:
            tok_s = interval_count / duration_s
    return {
        "name": name,
        "event_count": interval_count + 1 if endpoints_available else 0,
        "interval_count": interval_count,
        "numerator": interval_count,
        "start_event_index": start_index if endpoints_available else None,
        "end_event_index": end_index if endpoints_available else None,
        "start_generated_token_number": start_index + 1 if endpoints_available else None,
        "end_generated_token_number": end_index + 1 if endpoints_available else None,
        "duration_s": duration_s,
        "tok_s": tok_s,
    }


def unique_subsequence_positions(
    complete: list[int], streamed: list[int]
) -> list[int] | None:
    """Return the unique streamed->complete index mapping, or fail closed."""
    n_complete = len(complete)
    n_streamed = len(streamed)
    if n_streamed > n_complete:
        return None

    # Count alignments, capped at two because only uniqueness matters.
    counts = [[0] * (n_streamed + 1) for _ in range(n_complete + 1)]
    counts[n_complete][n_streamed] = 1
    for complete_i in range(n_complete - 1, -1, -1):
        counts[complete_i][n_streamed] = 1
        for streamed_i in range(n_streamed - 1, -1, -1):
            ways = counts[complete_i + 1][streamed_i]
            if complete[complete_i] == streamed[streamed_i]:
                ways += counts[complete_i + 1][streamed_i + 1]
            counts[complete_i][streamed_i] = min(2, ways)
    if counts[0][0] != 1:
        return None

    positions: list[int] = []
    complete_i = 0
    streamed_i = 0
    while streamed_i < n_streamed:
        if complete_i >= n_complete:
            return None
        skip_ways = counts[complete_i + 1][streamed_i]
        match_ways = 0
        if complete[complete_i] == streamed[streamed_i]:
            match_ways = counts[complete_i + 1][streamed_i + 1]
        if match_ways == 1 and skip_ways == 0:
            positions.append(complete_i)
            complete_i += 1
            streamed_i += 1
        elif skip_ways == 1 and match_ways == 0:
            complete_i += 1
        else:
            return None
    return positions


def load_prompt_builder(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("long_context_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load prompt builder: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.make_prompt


def load_prompts(
    path: Path, prompt_builder_path: Path | None = None, band: str | None = None
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    raw = json.loads(path.read_text())
    if isinstance(raw, list):
        if prompt_builder_path is not None or band is not None:
            raise SystemExit("--prompt-builder/--band require a paired context suite")
        meta = {"suite_id": path.stem, "version": None}
        entries = raw
    elif "pairs" in raw:
        if prompt_builder_path is None or band is None:
            raise SystemExit(
                "paired context suites require both --prompt-builder and --band"
            )
        pairs = [pair for pair in raw["pairs"] if pair.get("band") == band]
        if len(pairs) != 1 or len(pairs[0].get("cases", [])) != 2:
            raise SystemExit(f"paired context suite needs exactly two cases for {band}")
        make_prompt = load_prompt_builder(prompt_builder_path)
        meta = {key: value for key, value in raw.items() if key != "pairs"}
        meta["selected_band"] = band
        entries = [
            {
                "id": case["id"],
                "prompt": make_prompt(case),
                "calibrated_prompt_tokens": case["calibrated_prompt_tokens"],
            }
            for case in pairs[0]["cases"]
        ]
    else:
        if prompt_builder_path is not None or band is not None:
            raise SystemExit("--prompt-builder/--band require a paired context suite")
        meta = {key: value for key, value in raw.items() if key != "prompts"}
        entries = raw["prompts"]
    prompts: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if isinstance(entry, dict):
            prompt = str(entry["prompt"])
            prompt_id = str(entry.get("id", f"prompt-{index:02d}"))
        else:
            prompt = str(entry)
            prompt_id = f"prompt-{index:02d}"
        prompts.append(
            {
                "id": prompt_id,
                "prompt": prompt,
                "calibrated_prompt_tokens": (
                    int(entry["calibrated_prompt_tokens"])
                    if isinstance(entry, dict)
                    and "calibrated_prompt_tokens" in entry
                    else None
                ),
            }
        )
    return meta, prompts


def load_oracle(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise SystemExit(f"oracle is not a JSON object: {path}")
    return value


def oracle_baseline_valid(
    oracle: dict[str, Any], rows: list[dict[str, Any]]
) -> bool:
    oracle_rows = oracle.get("rows") or []
    oracle_prompt_ids = [
        row.get("prompt_id") for row in oracle_rows if isinstance(row, dict)
    ]
    return (
        isinstance(oracle_rows, list)
        and (oracle.get("intrinsic_gate") or {}).get("passed") is True
        and (oracle.get("oracle_comparison") or {}).get("status")
        == "BASELINE_CAPTURE_READY"
        and len(oracle_rows) == len(rows)
        and len(oracle_prompt_ids) == len(rows)
        and len(set(oracle_prompt_ids)) == len(rows)
        and set(oracle_prompt_ids) == {row["prompt_id"] for row in rows}
        and all(
            isinstance(row, dict)
            and is_nonempty_token_id_list(row.get("token_ids"))
            and isinstance(row.get("content_sha256"), str)
            and bool(row.get("content_sha256"))
            and isinstance(row.get("rendered_prompt_sha256"), str)
            and bool(row.get("rendered_prompt_sha256"))
            for row in oracle_rows
        )
    )


def compare_prefix_oracle(
    prefix_oracle: dict[str, Any], rows: list[dict[str, Any]]
) -> tuple[bool, list[dict[str, Any]]]:
    prefix_rows = {
        row.get("prompt_id"): row
        for row in prefix_oracle.get("rows", [])
        if isinstance(row, dict) and isinstance(row.get("prompt_id"), str)
    }
    results = []
    for row in rows:
        expected = prefix_rows.get(row["prompt_id"])
        expected_tokens = expected.get("token_ids") if expected else None
        results.append(
            {
                "prompt_id": row["prompt_id"],
                "expected_token_count": (
                    len(expected_tokens) if isinstance(expected_tokens, list) else None
                ),
                "rendered_prompt_exact": bool(expected)
                and row["rendered_prompt_sha256"]
                == expected.get("rendered_prompt_sha256"),
                "token_prefix_exact": isinstance(expected_tokens, list)
                and row["token_ids"][: len(expected_tokens)] == expected_tokens,
            }
        )
    passed = oracle_baseline_valid(prefix_oracle, rows) and all(
        item["rendered_prompt_exact"] and item["token_prefix_exact"]
        for item in results
    )
    return passed, results


def positive_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def full_512_prompt_processing_valid(row: dict[str, Any]) -> bool:
    prompt_n = row.get("stream_prompt_n")
    prompt_ms = row.get("stream_prompt_ms")
    reported_rate = row.get("stream_prompt_per_second")
    computed_rate = computed_prompt_tok_s(prompt_n, prompt_ms)
    return (
        is_token_id(prompt_n)
        and prompt_n > 0
        and positive_finite_number(prompt_ms)
        and positive_finite_number(reported_rate)
        and positive_finite_number(computed_rate)
        and math.isclose(reported_rate, computed_rate, rel_tol=1e-6, abs_tol=1e-6)
        and positive_finite_number(row.get("service_prompt_tok_s_to_first_token"))
    )


def prepare_post_512_canary(
    suite_path: Path,
    oracle: dict[str, Any],
    prompt_id: str,
    model_sha256: str,
    seed: int,
) -> dict[str, Any]:
    suite_meta, prompts = load_prompts(suite_path)
    matching_prompts = [entry for entry in prompts if entry["id"] == prompt_id]
    oracle_rows = oracle.get("rows")
    oracle_identity = oracle.get("run_identity") or {}
    if not isinstance(oracle_rows, list):
        raise SystemExit("post-512 canary oracle rows are missing")
    oracle_prompt_ids = [
        row.get("prompt_id") for row in oracle_rows if isinstance(row, dict)
    ]
    matching_oracle_rows = [
        row
        for row in oracle_rows
        if isinstance(row, dict) and row.get("prompt_id") == prompt_id
    ]
    suite_sha256 = hashlib.sha256(suite_path.read_bytes()).hexdigest()
    reference_valid = (
        len(matching_prompts) == 1
        and len(matching_oracle_rows) == 1
        and len(oracle_prompt_ids) == len(oracle_rows)
        and len(set(oracle_prompt_ids)) == len(oracle_rows)
        and (oracle.get("intrinsic_gate") or {}).get("passed") is True
        and (oracle.get("oracle_comparison") or {}).get("status")
        == "BASELINE_CAPTURE_READY"
        and oracle_identity.get("suite_sha256") == suite_sha256
        and oracle_identity.get("model_sha256") == model_sha256
        and oracle_identity.get("max_tokens") == 128
        and oracle_identity.get("seed") == seed
        and oracle_identity.get("temperature") == 0
        and oracle_identity.get("top_p") == 1
        and oracle_identity.get("cache_prompt") is False
        and oracle_identity.get("return_tokens") is True
        and oracle_identity.get("stream") is True
        and oracle_identity.get("exact_token_replay") is True
        and oracle_identity.get("ignore_eos", False) is False
    )
    if not reference_valid:
        raise SystemExit("post-512 canary suite/oracle identity is invalid")

    prompt_entry = matching_prompts[0]
    expected = matching_oracle_rows[0]
    expected_tokens = expected.get("token_ids")
    expected_content = expected.get("content")
    expected_prompt_sha256 = hashlib.sha256(prompt_entry["prompt"].encode()).hexdigest()
    expected_row_valid = (
        isinstance(expected_tokens, list)
        and len(expected_tokens) == 128
        and all(is_token_id(token) for token in expected_tokens)
        and isinstance(expected_content, str)
        and expected.get("prompt_sha256") == expected_prompt_sha256
        and isinstance(expected.get("rendered_prompt_sha256"), str)
        and expected.get("content_sha256")
        == hashlib.sha256(expected_content.encode()).hexdigest()
        and is_token_id(expected.get("token_count"))
        and expected.get("token_count") == 128
        and is_token_id(expected.get("final_predicted_n"))
        and expected.get("final_predicted_n") == 128
        and is_token_id(expected.get("cache_n"))
        and expected.get("cache_n") == 0
        and expected.get("truncated") is False
        and expected.get("stop_type") == "limit"
    )
    if not expected_row_valid:
        raise SystemExit("post-512 canary oracle row is incomplete or failed")
    return {
        "suite_id": suite_meta.get("suite_id"),
        "suite_sha256": suite_sha256,
        "prompt_id": prompt_id,
        "prompt": prompt_entry["prompt"],
        "prompt_sha256": expected_prompt_sha256,
        "expected": expected,
    }


def analyze_post_512_canary(
    prepared: dict[str, Any],
    rendered: str,
    response: dict[str, Any],
    expected_slot_id: int = 0,
) -> dict[str, Any]:
    expected = prepared["expected"]
    tokens = response.get("tokens")
    content = response.get("content")
    timings = response.get("timings")
    rendered_sha256 = hashlib.sha256(rendered.encode()).hexdigest()
    token_ids_valid = (
        isinstance(tokens, list)
        and len(tokens) == 128
        and all(is_token_id(token) for token in tokens)
    )
    content_valid = isinstance(content, str)
    checks = {
        "rendered_prompt_exact": (
            rendered_sha256 == expected.get("rendered_prompt_sha256")
        ),
        "token_ids_exact": token_ids_valid and tokens == expected.get("token_ids"),
        "content_exact": content_valid and content == expected.get("content"),
        "slot_id_exact": (
            is_token_id(response.get("id_slot"))
            and response.get("id_slot") == expected_slot_id
        ),
        "token_count_128": token_ids_valid,
        "stop_type_limit": response.get("stop_type") == "limit",
        "not_truncated": response.get("truncated") is False,
        "timings_present": isinstance(timings, dict),
        "cache_n_zero": (
            isinstance(timings, dict)
            and is_token_id(timings.get("cache_n"))
            and timings.get("cache_n") == 0
        ),
        "predicted_n_128": (
            isinstance(timings, dict)
            and is_token_id(timings.get("predicted_n"))
            and timings.get("predicted_n") == 128
        ),
    }
    return {
        "prompt_id": prepared["prompt_id"],
        "slot_id_requested": expected_slot_id,
        "slot_id_observed": response.get("id_slot"),
        "prompt_sha256": prepared["prompt_sha256"],
        "rendered_prompt_sha256": rendered_sha256,
        "token_ids": tokens if token_ids_valid else None,
        "token_ids_sha256": (
            hashlib.sha256(
                json.dumps(tokens, separators=(",", ":")).encode()
            ).hexdigest()
            if token_ids_valid
            else None
        ),
        "content": content if content_valid else None,
        "content_sha256": (
            hashlib.sha256(content.encode()).hexdigest() if content_valid else None
        ),
        "cache_n": timings.get("cache_n") if isinstance(timings, dict) else None,
        "predicted_n": (
            timings.get("predicted_n") if isinstance(timings, dict) else None
        ),
        "stop_type": response.get("stop_type"),
        "truncated": response.get("truncated"),
        "timings": timings if isinstance(timings, dict) else None,
        "checks": checks,
        "passed": all(checks.values()),
    }


def capture_post_512_canary(
    base_url: str,
    timeout: int,
    seed: int,
    prepared: dict[str, Any],
    slot_id: int = 0,
) -> dict[str, Any]:
    rendered = post_json(
        f"{base_url}/apply-template",
        {"messages": [{"role": "user", "content": prepared["prompt"]}]},
        timeout,
    ).get("prompt")
    if not isinstance(rendered, str) or not rendered:
        raise RuntimeError("post-512 canary returned an empty rendered prompt")
    response = post_json(
        f"{base_url}/completion",
        {
            "prompt": rendered,
            "n_predict": 128,
            "temperature": 0,
            "top_p": 1,
            "seed": seed,
            "cache_prompt": False,
            "return_tokens": True,
            "ignore_eos": False,
            "id_slot": slot_id,
            "stream": False,
        },
        timeout,
    )
    return analyze_post_512_canary(prepared, rendered, response, slot_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:19460")
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--prompt-builder", type=Path)
    parser.add_argument("--band", choices=("short", "middle", "near32k"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--oracle-json", type=Path)
    parser.add_argument("--prefix-oracle-json", type=Path)
    parser.add_argument("--max-prompts", type=int)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--ignore-eos", action="store_true")
    parser.add_argument("--require-exact-token-count", action="store_true")
    parser.add_argument("--require-full-512-metric", action="store_true")
    parser.add_argument("--require-post-512-canary", action="store_true")
    parser.add_argument("--post-512-canary-suite", type=Path)
    parser.add_argument("--post-512-canary-oracle", type=Path)
    parser.add_argument("--post-512-canary-oracle-sha256")
    parser.add_argument("--post-512-canary-prompt-id")
    parser.add_argument("--slot-id", type=int)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--runtime-sha256", required=True)
    parser.add_argument("--cache-type-k", required=True)
    parser.add_argument("--cache-type-v", required=True)
    parser.add_argument("--ctx-size", type=int, required=True)
    parser.add_argument("--sycl-dnn-enabled", type=int, choices=(0, 1), required=True)
    parser.add_argument("--sycl-opt-enabled", type=int, choices=(0, 1), required=True)
    args = parser.parse_args()

    protected_inputs = [args.suite]
    if args.prompt_builder is not None:
        protected_inputs.append(args.prompt_builder)
    if args.oracle_json is not None:
        protected_inputs.append(args.oracle_json)
    if args.prefix_oracle_json is not None:
        protected_inputs.append(args.prefix_oracle_json)
    if args.post_512_canary_suite is not None:
        protected_inputs.append(args.post_512_canary_suite)
    if args.post_512_canary_oracle is not None:
        protected_inputs.append(args.post_512_canary_oracle)
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.out}")
    if any(args.out.resolve() == path.resolve() for path in protected_inputs):
        raise SystemExit("output path must not overwrite an input or oracle")
    for path in protected_inputs:
        if not path.is_file():
            raise SystemExit(f"required input is not a file: {path}")
    parsed_base = urlparse(args.base_url)
    if (
        parsed_base.scheme != "http"
        or parsed_base.hostname not in ("127.0.0.1", "localhost")
        or parsed_base.port is None
        or parsed_base.path not in ("", "/")
        or parsed_base.query
        or parsed_base.fragment
    ):
        raise SystemExit("--base-url must be a loopback HTTP origin with an explicit port")
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")

    if args.max_tokens < 100:
        raise SystemExit("--max-tokens must be at least 100")
    if args.require_full_512_metric and args.max_tokens != 512:
        raise SystemExit("--require-full-512-metric requires --max-tokens 512")
    if args.require_full_512_metric and not args.require_exact_token_count:
        raise SystemExit(
            "--require-full-512-metric also requires --require-exact-token-count"
        )
    canary_options = (
        args.post_512_canary_suite,
        args.post_512_canary_oracle,
        args.post_512_canary_oracle_sha256,
        args.post_512_canary_prompt_id,
    )
    if any(value is not None for value in canary_options) and not args.require_post_512_canary:
        raise SystemExit("post-512 canary options require --require-post-512-canary")
    if args.require_post_512_canary:
        if not args.require_full_512_metric or args.max_tokens != 512:
            raise SystemExit(
                "--require-post-512-canary requires the full-512 metric gate"
            )
        if any(value is None for value in canary_options):
            raise SystemExit(
                "--require-post-512-canary requires its suite, oracle, oracle SHA-256, and prompt ID"
            )
        if args.slot_id not in (None, 0):
            raise SystemExit("post-512 c1 canary requires main slot ID 0 or automatic")
        oracle_digest = str(args.post_512_canary_oracle_sha256)
        if len(oracle_digest) != 64 or any(
            character not in "0123456789abcdef" for character in oracle_digest
        ):
            raise SystemExit("post-512 canary oracle SHA-256 must be lowercase hex")
        actual_oracle_digest = hashlib.sha256(
            args.post_512_canary_oracle.read_bytes()
        ).hexdigest()
        if actual_oracle_digest != oracle_digest:
            raise SystemExit("post-512 canary oracle SHA-256 mismatch")
    if args.slot_id is not None and args.slot_id < 0:
        raise SystemExit("--slot-id must be nonnegative")

    if (args.prompt_builder is None) != (args.band is None):
        raise SystemExit("--prompt-builder and --band must be supplied together")
    suite_meta, prompts = load_prompts(args.suite, args.prompt_builder, args.band)
    if args.max_prompts is not None:
        if args.max_prompts <= 0:
            raise SystemExit("--max-prompts must be positive")
        prompts = prompts[: args.max_prompts]
    if not prompts:
        raise SystemExit("no prompts selected")

    post_512_canary_prepared: dict[str, Any] | None = None
    post_512_canary_oracle_sha256: str | None = None
    if args.require_post_512_canary:
        post_512_canary_oracle = load_oracle(args.post_512_canary_oracle)
        if post_512_canary_oracle is None:
            raise SystemExit("post-512 canary oracle is missing")
        post_512_canary_prepared = prepare_post_512_canary(
            args.post_512_canary_suite,
            post_512_canary_oracle,
            args.post_512_canary_prompt_id,
            args.model_sha256,
            args.seed,
        )
        post_512_canary_oracle_sha256 = hashlib.sha256(
            args.post_512_canary_oracle.read_bytes()
        ).hexdigest()

    base_url = args.base_url.rstrip("/")
    rows: list[dict[str, Any]] = []
    stream_captures: list[dict[str, Any]] = []
    for entry in prompts:
        prompt = entry["prompt"]
        rendered = post_json(
            f"{base_url}/apply-template",
            {"messages": [{"role": "user", "content": prompt}]},
            args.timeout,
        ).get("prompt")
        if not isinstance(rendered, str) or not rendered:
            raise RuntimeError(f"empty rendered prompt for {entry['id']}")
        request_payload = {
            "prompt": rendered,
            "n_predict": args.max_tokens,
            "temperature": 0,
            "top_p": 1,
            "seed": args.seed,
            "cache_prompt": False,
            "return_tokens": True,
            "ignore_eos": args.ignore_eos,
        }
        if args.slot_id is not None:
            request_payload["id_slot"] = args.slot_id
        response = stream_completion(
            f"{base_url}/completion",
            {**request_payload, "stream": True},
            args.timeout,
        )
        streamed_tokens = response["token_ids"]
        if not is_nonempty_token_id_list(streamed_tokens):
            raise RuntimeError(f"missing streamed token IDs for {entry['id']}")
        stream_captures.append(
            {
                "entry": entry,
                "prompt": prompt,
                "rendered": rendered,
                "request_payload": request_payload,
                "response": response,
                "streamed_tokens": streamed_tokens,
            }
        )

    # Keep the measured pass cold with respect to identical-prompt replays: all
    # timed streams finish before the exact-token replay pass begins.
    for capture in stream_captures:
        entry = capture["entry"]
        prompt = capture["prompt"]
        rendered = capture["rendered"]
        request_payload = capture["request_payload"]
        response = capture["response"]
        streamed_tokens = capture["streamed_tokens"]
        exact_response = post_json(
            f"{base_url}/completion",
            {**request_payload, "stream": False},
            args.timeout,
        )
        tokens = exact_response.get("tokens")
        if not is_nonempty_token_id_list(tokens):
            raise RuntimeError(f"missing replay token IDs for {entry['id']}")
        streamed_content = response["content"]
        exact_content = exact_response.get("content")
        if not isinstance(streamed_content, str) or not isinstance(exact_content, str):
            raise RuntimeError(f"missing completion content for {entry['id']}")
        stream_final = response["final"]
        stream_timings = stream_final.get("timings")
        exact_timings = exact_response.get("timings")
        stream_cache_n = (
            stream_timings.get("cache_n")
            if isinstance(stream_timings, dict)
            else None
        )
        exact_cache_n = (
            exact_timings.get("cache_n")
            if isinstance(exact_timings, dict)
            else None
        )
        stream_predicted_n = (
            stream_timings.get("predicted_n")
            if isinstance(stream_timings, dict)
            else None
        )
        exact_predicted_n = (
            exact_timings.get("predicted_n")
            if isinstance(exact_timings, dict)
            else None
        )
        stream_prompt_n = (
            stream_timings.get("prompt_n")
            if isinstance(stream_timings, dict)
            else None
        )
        stream_prompt_ms = (
            stream_timings.get("prompt_ms")
            if isinstance(stream_timings, dict)
            else None
        )
        stream_prompt_per_second = (
            stream_timings.get("prompt_per_second")
            if isinstance(stream_timings, dict)
            else None
        )
        stream_prompt_per_second_computed = computed_prompt_tok_s(
            stream_prompt_n, stream_prompt_ms
        )
        stream_prompt_rate_reported_consistent = (
            positive_finite_number(stream_prompt_per_second)
            and positive_finite_number(stream_prompt_per_second_computed)
            and math.isclose(
                stream_prompt_per_second,
                stream_prompt_per_second_computed,
                rel_tol=1e-6,
                abs_tol=1e-6,
            )
        )
        streamed_offsets = response["token_offsets_s"]
        stream_id_slot = stream_final.get("id_slot")
        exact_id_slot = exact_response.get("id_slot")
        stream_positions = unique_subsequence_positions(tokens, streamed_tokens)
        complete_offsets: list[float | None] = [None] * len(tokens)
        if stream_positions is not None and len(stream_positions) == len(streamed_offsets):
            for complete_i, offset in zip(stream_positions, streamed_offsets):
                complete_offsets[complete_i] = offset
        missing_stream_indices = (
            sorted(set(range(len(tokens))) - set(stream_positions))
            if stream_positions is not None
            else None
        )
        primary_metric = interval_metric(
            complete_offsets, 0, 99, "tok_s_1_100_intervals_after_ttft"
        )
        full_512_metric = interval_metric(
            complete_offsets, 0, 511, "tok_s_1_512_intervals_after_ttft"
        )
        request_elapsed_s = response["elapsed_s"]
        ttft_s = complete_offsets[0] if complete_offsets else None
        full_512_after_ttft_tok_s = None
        full_512_wall_tok_s = None
        if (
            len(tokens) >= 512
            and isinstance(ttft_s, (int, float))
            and request_elapsed_s > ttft_s
        ):
            full_512_after_ttft_tok_s = 512 / (request_elapsed_s - ttft_s)
            if request_elapsed_s > 0:
                full_512_wall_tok_s = 512 / request_elapsed_s
        rows.append(
            {
                "prompt_id": entry["id"],
                "calibrated_prompt_tokens": entry["calibrated_prompt_tokens"],
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "rendered_prompt_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
                "token_ids": tokens,
                "token_ids_sha256": hashlib.sha256(
                    json.dumps(tokens, separators=(",", ":")).encode()
                ).hexdigest(),
                "token_count": len(tokens),
                "final_predicted_n": exact_predicted_n,
                "stream_final_predicted_n": stream_predicted_n,
                "stream_token_ids": streamed_tokens,
                "stream_token_count": len(streamed_tokens),
                "stream_alignment_unique": stream_positions is not None,
                "stream_to_complete_positions": stream_positions,
                "stream_missing_complete_indices": missing_stream_indices,
                "stream_token_ids_complete": streamed_tokens == tokens,
                "stream_content_matches_replay": streamed_content == exact_content,
                "token_event_offsets_s": complete_offsets,
                "primary_metric": primary_metric,
                "full_512_metric": full_512_metric,
                "request_elapsed_s": request_elapsed_s,
                "request_started_perf_s": response["request_started_perf_s"],
                "request_ended_perf_s": response["request_ended_perf_s"],
                "ttft_s": ttft_s,
                "stream_prompt_n": stream_prompt_n,
                "stream_prompt_ms": stream_prompt_ms,
                "stream_prompt_per_second": stream_prompt_per_second,
                "stream_prompt_per_second_computed": (
                    stream_prompt_per_second_computed
                ),
                "stream_prompt_rate_reported_consistent": (
                    stream_prompt_rate_reported_consistent
                ),
                "service_prompt_tok_s_to_first_token": (
                    stream_prompt_n / ttft_s
                    if isinstance(stream_prompt_n, (int, float))
                    and isinstance(ttft_s, (int, float))
                    and ttft_s > 0
                    else None
                ),
                "full_512_after_ttft_tok_s": full_512_after_ttft_tok_s,
                "full_512_wall_tok_s": full_512_wall_tok_s,
                "content_sha256": hashlib.sha256(exact_content.encode()).hexdigest(),
                "content": exact_content,
                "cache_n": exact_cache_n,
                "stream_cache_n": stream_cache_n,
                "tokens_cached_native_semantics": exact_response.get("tokens_cached"),
                "stream_tokens_cached_native_semantics": stream_final.get("tokens_cached"),
                "tokens_evaluated": exact_response.get("tokens_evaluated"),
                "truncated": exact_response.get("truncated"),
                "stream_truncated": stream_final.get("truncated"),
                "stop_type": exact_response.get("stop_type"),
                "stream_stop_type": stream_final.get("stop_type"),
                "stop_type_matches_replay": (
                    stream_final.get("stop_type") == exact_response.get("stop_type")
                ),
                "id_slot": exact_id_slot,
                "stream_id_slot": stream_id_slot,
                "id_slot_matches_request": (
                    (
                        is_token_id(stream_id_slot)
                        and is_token_id(exact_id_slot)
                        and stream_id_slot == exact_id_slot
                    )
                    if args.slot_id is None
                    else (
                        is_token_id(stream_id_slot)
                        and is_token_id(exact_id_slot)
                        and stream_id_slot == args.slot_id
                        and exact_id_slot == args.slot_id
                    )
                ),
                "timings": exact_timings if isinstance(exact_timings, dict) else None,
                "stream_timings": (
                    stream_timings if isinstance(stream_timings, dict) else None
                ),
            }
        )

    post_512_canary: dict[str, Any] | None = None
    if post_512_canary_prepared is not None:
        post_512_canary = capture_post_512_canary(
            base_url, args.timeout, args.seed, post_512_canary_prepared
        )
        post_512_canary.update(
            {
                "suite_path": str(args.post_512_canary_suite),
                "suite_sha256": post_512_canary_prepared["suite_sha256"],
                "oracle_path": str(args.post_512_canary_oracle),
                "oracle_sha256": post_512_canary_oracle_sha256,
                "execution_order": "after_all_timed_streams_and_all_main_replays",
            }
        )

    suite_sha256 = hashlib.sha256(args.suite.read_bytes()).hexdigest()
    prompt_builder_sha256 = (
        hashlib.sha256(args.prompt_builder.read_bytes()).hexdigest()
        if args.prompt_builder is not None
        else None
    )
    intrinsic_pass = (
        len(rows) == len(prompts)
        and len({row["prompt_sha256"] for row in rows}) == len(rows)
        and len({row["prompt_id"] for row in rows}) == len(rows)
        and all(
            is_token_id(row["cache_n"])
            and is_token_id(row["stream_cache_n"])
            and row["cache_n"] == 0
            and row["stream_cache_n"] == 0
            for row in rows
        )
        and all(
            row["truncated"] is False and row["stream_truncated"] is False
            for row in rows
        )
        and all(
            row["token_count"] == args.max_tokens
            if args.require_exact_token_count
            else row["token_count"] >= 100
            for row in rows
        )
        and all(
            is_token_id(row["final_predicted_n"])
            and row["final_predicted_n"] == row["token_count"]
            for row in rows
        )
        and all(
            is_token_id(row["stream_final_predicted_n"])
            and row["stream_final_predicted_n"] == row["token_count"]
            for row in rows
        )
        and all(row["stream_alignment_unique"] is True for row in rows)
        and all(row["stream_content_matches_replay"] is True for row in rows)
        and all(row["stop_type_matches_replay"] is True for row in rows)
        and all(row["id_slot_matches_request"] is True for row in rows)
        and all(row["primary_metric"]["interval_count"] == 99 for row in rows)
        and all(
            row["calibrated_prompt_tokens"] is None
            or (
                is_token_id(row["stream_prompt_n"])
                and row["stream_prompt_n"] == row["calibrated_prompt_tokens"]
                and isinstance(row["timings"], dict)
                and is_token_id(row["timings"].get("prompt_n"))
                and row["timings"].get("prompt_n")
                == row["calibrated_prompt_tokens"]
            )
            for row in rows
        )
        and all(
            isinstance(row["primary_metric"]["tok_s"], (int, float))
            and row["primary_metric"]["tok_s"] > 0
            for row in rows
        )
        and (
            not args.require_full_512_metric
            or all(full_512_prompt_processing_valid(row) for row in rows)
        )
        and (
            not args.require_full_512_metric
            or all(
                row["full_512_metric"]["interval_count"] == 511
                and isinstance(row["full_512_metric"]["tok_s"], (int, float))
                and row["full_512_metric"]["tok_s"] > 0
                and isinstance(row["full_512_after_ttft_tok_s"], (int, float))
                and row["full_512_after_ttft_tok_s"] > 0
                and isinstance(row["full_512_wall_tok_s"], (int, float))
                and row["full_512_wall_tok_s"] > 0
                and row["stop_type"] == "limit"
                and row["stream_stop_type"] == "limit"
                for row in rows
            )
        )
        and (
            not args.require_post_512_canary
            or (
                isinstance(post_512_canary, dict)
                and post_512_canary.get("passed") is True
            )
        )
    )
    oracle = load_oracle(args.oracle_json)
    prefix_oracle = load_oracle(args.prefix_oracle_json)
    prefix_comparison: dict[str, Any] | None = None
    if prefix_oracle is not None:
        prefix_passed, prefix_results = compare_prefix_oracle(prefix_oracle, rows)
        prefix_comparison = {
            "passed": prefix_passed,
            "status": "PASS_PREFIX_ORACLE_EXACT" if prefix_passed else "FAIL_PREFIX_ORACLE_EXACT",
            "oracle_json": str(args.prefix_oracle_json),
            "oracle_sha256": hashlib.sha256(
                args.prefix_oracle_json.read_bytes()
            ).hexdigest(),
            "rows": prefix_results,
        }
        intrinsic_pass = intrinsic_pass and prefix_passed
    comparison: dict[str, Any]
    exit_code = 0
    if oracle is None:
        comparison = {
            "status": (
                "BASELINE_CAPTURE_READY"
                if intrinsic_pass
                else "FAIL_BASELINE_CAPTURE"
            ),
            "passed": None,
            "oracle_json": None,
        }
        exit_code = 0 if intrinsic_pass else 1
    else:
        oracle_identity = oracle.get("run_identity") or {}
        oracle_rows = oracle.get("rows") or []
        oracle_valid = oracle_baseline_valid(oracle, rows)
        oracle_by_id = {
            row.get("prompt_id"): row
            for row in oracle_rows
            if isinstance(row, dict) and isinstance(row.get("prompt_id"), str)
        }
        row_results = []
        for row in rows:
            expected = oracle_by_id.get(row["prompt_id"])
            exact = bool(expected) and expected.get("token_ids") == row["token_ids"]
            rendered_prompt_exact = bool(expected) and expected.get(
                "rendered_prompt_sha256"
            ) == row["rendered_prompt_sha256"]
            content_exact = bool(expected) and expected.get(
                "content_sha256"
            ) == row["content_sha256"]
            row_results.append(
                {
                    "prompt_id": row["prompt_id"],
                    "token_exact": exact,
                    "rendered_prompt_exact": rendered_prompt_exact,
                    "content_exact": content_exact,
                }
            )
        identity_fields = {
            "suite_sha256": suite_sha256,
            "model_sha256": args.model_sha256,
            "cache_type_k": args.cache_type_k,
            "cache_type_v": args.cache_type_v,
            "ctx_size": args.ctx_size,
            "max_tokens": args.max_tokens,
            "seed": args.seed,
            "temperature": 0,
            "top_p": 1,
            "cache_prompt": False,
            "return_tokens": True,
            "stream": True,
            "exact_token_replay": True,
            "replay_order": "all_streaming_rows_then_all_non_streaming_replays",
        }
        if args.ignore_eos or "ignore_eos" in oracle_identity:
            identity_fields["ignore_eos"] = args.ignore_eos
        if args.slot_id is not None or "slot_id" in oracle_identity:
            identity_fields["slot_id"] = args.slot_id
        if args.band is not None or "band" in oracle_identity:
            identity_fields["band"] = args.band
        if prompt_builder_sha256 is not None or "prompt_builder_sha256" in oracle_identity:
            identity_fields["prompt_builder_sha256"] = prompt_builder_sha256
        identity_results = {
            key: oracle_identity.get(key) == value
            for key, value in identity_fields.items()
        }
        identity_match = all(identity_results.values())
        prompt_ids_match = oracle_identity.get("prompt_ids") == [
            row["prompt_id"] for row in rows
        ]
        passed = (
            intrinsic_pass
            and oracle_valid
            and identity_match
            and prompt_ids_match
            and len(oracle_by_id) == len(rows)
            and all(
                item["token_exact"]
                and item["rendered_prompt_exact"]
                and item["content_exact"]
                for item in row_results
            )
        )
        comparison = {
            "status": "PASS_ORACLE_EXACT" if passed else "FAIL_ORACLE_EXACT",
            "passed": passed,
            "oracle_valid_baseline": oracle_valid,
            "oracle_json": str(args.oracle_json),
            "oracle_sha256": hashlib.sha256(args.oracle_json.read_bytes()).hexdigest(),
            "suite_identity_match": identity_match,
            "identity_fields": identity_results,
            "prompt_ids_match": prompt_ids_match,
            "rows": row_results,
            "runtime_sha256_same": (
                oracle_identity.get("runtime_sha256") == args.runtime_sha256
            ),
            "runtime_selector_same": {
                "sycl_dnn_enabled": (
                    oracle_identity.get("sycl_dnn_enabled")
                    == args.sycl_dnn_enabled
                ),
                "sycl_opt_enabled": (
                    oracle_identity.get("sycl_opt_enabled")
                    == args.sycl_opt_enabled
                ),
            },
        }
        exit_code = 0 if passed else 1

    result = {
        "run_identity": {
            "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
            "base_url": base_url,
            "suite_path": str(args.suite),
            "suite_id": suite_meta.get("suite_id"),
            "suite_sha256": suite_sha256,
            "prompt_builder_path": (
                str(args.prompt_builder) if args.prompt_builder is not None else None
            ),
            "prompt_builder_sha256": prompt_builder_sha256,
            "band": args.band,
            "prompt_ids": [row["prompt_id"] for row in rows],
            "max_tokens": args.max_tokens,
            "ignore_eos": args.ignore_eos,
            "require_exact_token_count": args.require_exact_token_count,
            "require_full_512_metric": args.require_full_512_metric,
            "require_post_512_canary": args.require_post_512_canary,
            "post_512_canary_suite_path": (
                str(args.post_512_canary_suite)
                if args.post_512_canary_suite is not None
                else None
            ),
            "post_512_canary_suite_sha256": (
                post_512_canary_prepared["suite_sha256"]
                if post_512_canary_prepared is not None
                else None
            ),
            "post_512_canary_oracle_path": (
                str(args.post_512_canary_oracle)
                if args.post_512_canary_oracle is not None
                else None
            ),
            "post_512_canary_oracle_sha256": post_512_canary_oracle_sha256,
            "post_512_canary_prompt_id": args.post_512_canary_prompt_id,
            "post_512_canary_slot_id": 0 if args.require_post_512_canary else None,
            "slot_id": args.slot_id,
            "seed": args.seed,
            "temperature": 0,
            "top_p": 1,
            "model_sha256": args.model_sha256,
            "runtime_sha256": args.runtime_sha256,
            "cache_type_k": args.cache_type_k,
            "cache_type_v": args.cache_type_v,
            "ctx_size": args.ctx_size,
            "sycl_dnn_enabled": args.sycl_dnn_enabled,
            "sycl_opt_enabled": args.sycl_opt_enabled,
            "api": "llama.cpp /apply-template, streaming timing, deterministic non-streaming token replay",
            "cache_prompt": False,
            "return_tokens": True,
            "stream": True,
            "exact_token_replay": True,
            "replay_order": "all_streaming_rows_then_all_non_streaming_replays",
        },
        "oracle_comparison": comparison,
        "prefix_oracle_comparison": prefix_comparison,
        "intrinsic_gate": {
            "passed": intrinsic_pass,
            "rows_complete": len(rows) == len(prompts),
            "prompts_unique": len({row["prompt_sha256"] for row in rows}) == len(rows),
            "prompt_ids_unique": len({row["prompt_id"] for row in rows}) == len(rows),
            "native_cache_n_all_zero": all(
                is_token_id(row["cache_n"])
                and is_token_id(row["stream_cache_n"])
                and row["cache_n"] == 0
                and row["stream_cache_n"] == 0
                for row in rows
            ),
            "native_tokens_cached_note": "tokens_cached is current retained prompt state in this llama.cpp API; cache_n is the cache-reuse count",
            "not_truncated_all": all(
                row["truncated"] is False and row["stream_truncated"] is False
                for row in rows
            ),
            "token_count_requirement": (
                "exactly max_tokens" if args.require_exact_token_count else "at least 100"
            ),
            "token_count_requirement_passed_all": all(
                row["token_count"] == args.max_tokens
                if args.require_exact_token_count
                else row["token_count"] >= 100
                for row in rows
            ),
            "replay_token_ids_match_final_predicted_n_all": all(
                is_token_id(row["final_predicted_n"])
                and row["final_predicted_n"] == row["token_count"]
                for row in rows
            ),
            "stream_final_predicted_n_matches_replay_count_all": all(
                is_token_id(row["stream_final_predicted_n"])
                and row["stream_final_predicted_n"] == row["token_count"]
                for row in rows
            ),
            "stream_alignment_unique_all": all(
                row["stream_alignment_unique"] is True for row in rows
            ),
            "stream_content_matches_replay_all": all(
                row["stream_content_matches_replay"] is True for row in rows
            ),
            "stream_stop_type_matches_replay_all": all(
                row["stop_type_matches_replay"] is True for row in rows
            ),
            "slot_id_matches_request_all": all(
                row["id_slot_matches_request"] is True for row in rows
            ),
            "primary_interval_count_99_all": all(
                row["primary_metric"]["interval_count"] == 99 for row in rows
            ),
            "calibrated_prompt_tokens_match_all": all(
                row["calibrated_prompt_tokens"] is None
                or (
                    is_token_id(row["stream_prompt_n"])
                    and row["stream_prompt_n"] == row["calibrated_prompt_tokens"]
                    and isinstance(row["timings"], dict)
                    and is_token_id(row["timings"].get("prompt_n"))
                    and row["timings"].get("prompt_n")
                    == row["calibrated_prompt_tokens"]
                )
                for row in rows
            ),
            "primary_rate_positive_all": all(
                isinstance(row["primary_metric"]["tok_s"], (int, float))
                and row["primary_metric"]["tok_s"] > 0
                for row in rows
            ),
            "full_512_prompt_processing_fields_required": (
                args.require_full_512_metric
            ),
            "full_512_prompt_processing_fields_passed_all": (
                not args.require_full_512_metric
                or all(full_512_prompt_processing_valid(row) for row in rows)
            ),
            "full_512_metric_required": args.require_full_512_metric,
            "full_512_interval_count_511_all": (
                not args.require_full_512_metric
                or all(
                    row["full_512_metric"]["interval_count"] == 511 for row in rows
                )
            ),
            "full_512_rates_positive_all": (
                not args.require_full_512_metric
                or all(
                    isinstance(row["full_512_metric"]["tok_s"], (int, float))
                    and row["full_512_metric"]["tok_s"] > 0
                    and isinstance(row["full_512_after_ttft_tok_s"], (int, float))
                    and row["full_512_after_ttft_tok_s"] > 0
                    and isinstance(row["full_512_wall_tok_s"], (int, float))
                    and row["full_512_wall_tok_s"] > 0
                    and row["stop_type"] == "limit"
                    and row["stream_stop_type"] == "limit"
                    for row in rows
                )
            ),
            "post_512_canary_required": args.require_post_512_canary,
            "post_512_canary_passed": (
                not args.require_post_512_canary
                or (
                    isinstance(post_512_canary, dict)
                    and post_512_canary.get("passed") is True
                )
            ),
        },
        "summary": {
            "primary_metric_name": "median_tok_s_1_100_intervals_after_ttft",
            "event_count_per_row_required": 100,
            "interval_count_per_row_required": 99,
            "numerator_per_row": 99,
            "tok_s_1_100_intervals_after_ttft": summarize(
                [
                    row["primary_metric"]["tok_s"]
                    for row in rows
                    if isinstance(row["primary_metric"]["tok_s"], (int, float))
                ]
            ),
            "tok_s_1_512_intervals_after_ttft": summarize(
                [
                    row["full_512_metric"]["tok_s"]
                    for row in rows
                    if isinstance(row["full_512_metric"]["tok_s"], (int, float))
                ]
            ),
            "full_512_after_ttft_tok_s": summarize(
                [
                    row["full_512_after_ttft_tok_s"]
                    for row in rows
                    if isinstance(row["full_512_after_ttft_tok_s"], (int, float))
                ]
            ),
            "full_512_wall_tok_s": summarize(
                [
                    row["full_512_wall_tok_s"]
                    for row in rows
                    if isinstance(row["full_512_wall_tok_s"], (int, float))
                ]
            ),
            "ttft_s": summarize(
                [
                    row["ttft_s"]
                    for row in rows
                    if isinstance(row["ttft_s"], (int, float))
                ]
            ),
            "native_stream_prompt_tok_s": summarize(
                [
                    row["stream_prompt_per_second"]
                    for row in rows
                    if isinstance(row["stream_prompt_per_second"], (int, float))
                ]
            ),
            "computed_stream_prompt_tok_s": summarize(
                [
                    row["stream_prompt_per_second_computed"]
                    for row in rows
                    if isinstance(
                        row["stream_prompt_per_second_computed"], (int, float)
                    )
                ]
            ),
            "service_prompt_tok_s_to_first_token": summarize(
                [
                    row["service_prompt_tok_s_to_first_token"]
                    for row in rows
                    if isinstance(
                        row["service_prompt_tok_s_to_first_token"], (int, float)
                    )
                ]
            ),
        },
        "post_512_canary": post_512_canary,
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "out": str(args.out),
                "rows": len(rows),
                "status": comparison["status"],
            },
            sort_keys=True,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
