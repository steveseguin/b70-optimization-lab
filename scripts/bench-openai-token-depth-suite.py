#!/usr/bin/env python3
"""Benchmark one exact token-depth fixture through /v1/completions.

The client is inert unless ``--execute`` is supplied.  ``--check`` and
``--plan`` only validate local input and describe the frozen request.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "openai-token-depth-fixture-v1"
RECEIPT_SCHEMA = "openai-token-depth-benchmark-v1"
ALLOWED_DEPTHS = (2048, 4096, 8192, 16384, 24576, 32768)
ALLOWED_FIXTURE_DEPTHS = (0, *ALLOWED_DEPTHS)
MAX_TOKENS = 128
METRIC_EVENTS = 100
METRIC_INTERVALS = METRIC_EVENTS - 1
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class FixtureCase:
    case_id: str
    depth: int
    prompt_token_ids: list[int]
    prompt_token_ids_sha256: str
    case_sha256: str


@dataclass(frozen=True)
class Fixture:
    path: Path
    fixture_id: str
    sha256: str
    provenance: dict[str, Any]
    provenance_sha256: str
    selected: FixtureCase
    case_count: int


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def token_ids_sha256(token_ids: list[int]) -> str:
    return sha256_bytes(canonical_bytes(token_ids))


def _plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_token_ids(value: Any, *, label: str, depth: int) -> list[int]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a flat JSON array")
    if len(value) != depth:
        raise ValueError(f"{label} has {len(value)} tokens; depth requires {depth}")
    if not all(_plain_int(token) and token >= 0 for token in value):
        raise ValueError(f"{label} must contain only non-negative integer token IDs")
    return list(value)


def load_fixture(path: Path, depth: int, case_id: str | None = None) -> Fixture:
    raw = path.read_bytes()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"fixture is not valid JSON: {error}") from error
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ValueError(f"fixture schema must be {SCHEMA!r}")
    fixture_id = payload.get("fixture_id")
    if not isinstance(fixture_id, str) or not fixture_id.strip():
        raise ValueError("fixture_id must be a non-empty string")
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict) or not provenance:
        raise ValueError("fixture provenance must be a non-empty object")
    computed_provenance_hash = sha256_bytes(canonical_bytes(provenance))
    declared_provenance_hash = payload.get("provenance_sha256")
    if (
        not isinstance(declared_provenance_hash, str)
        or not SHA256_RE.fullmatch(declared_provenance_hash)
        or declared_provenance_hash != computed_provenance_hash
    ):
        raise ValueError("fixture provenance_sha256 is missing or mismatched")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("fixture cases must be a non-empty array")

    seen_ids: set[str] = set()
    selected: list[FixtureCase] = []
    for index, item in enumerate(cases):
        if not isinstance(item, dict):
            raise ValueError(f"cases[{index}] must be an object")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            raise ValueError(f"cases[{index}].id must be a non-empty string")
        if item_id in seen_ids:
            raise ValueError(f"duplicate fixture case id: {item_id}")
        seen_ids.add(item_id)
        item_depth = item.get("depth")
        if not _plain_int(item_depth) or item_depth not in ALLOWED_FIXTURE_DEPTHS:
            raise ValueError(
                f"case {item_id} depth must be one of "
                + ", ".join(str(value) for value in ALLOWED_FIXTURE_DEPTHS)
            )
        token_ids = _validate_token_ids(
            item.get("prompt_token_ids"),
            label=f"case {item_id} prompt_token_ids",
            depth=item_depth,
        )
        declared_hash = item.get("prompt_token_ids_sha256")
        if not isinstance(declared_hash, str) or not SHA256_RE.fullmatch(declared_hash):
            raise ValueError(
                f"case {item_id} prompt_token_ids_sha256 must be lowercase SHA-256"
            )
        computed_hash = token_ids_sha256(token_ids)
        if declared_hash != computed_hash:
            raise ValueError(f"case {item_id} prompt token hash mismatch")
        if item_depth == depth and (case_id is None or item_id == case_id):
            selected.append(
                FixtureCase(
                    case_id=item_id,
                    depth=item_depth,
                    prompt_token_ids=token_ids,
                    prompt_token_ids_sha256=computed_hash,
                    case_sha256=sha256_bytes(canonical_bytes(item)),
                )
            )
    if case_id is not None and case_id not in seen_ids:
        raise ValueError(f"unknown fixture case id: {case_id}")
    if len(selected) != 1:
        qualifier = f" and case {case_id!r}" if case_id else ""
        raise ValueError(
            f"fixture must select exactly one case at depth {depth}{qualifier}; "
            f"found {len(selected)}"
        )
    return Fixture(
        path=path,
        fixture_id=fixture_id,
        sha256=sha256_bytes(raw),
        provenance=provenance,
        provenance_sha256=computed_provenance_hash,
        selected=selected[0],
        case_count=len(cases),
    )


def validate_base_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base URL must be an absolute http(s) URL")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError("base URL cannot contain credentials, query, or fragment")
    path = parsed.path.rstrip("/")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def request_payload(
    *, model: str, prompt_token_ids: list[int], adapter: str
) -> dict[str, Any]:
    if not model:
        raise ValueError("model must be non-empty")
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt_token_ids,
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
        "top_p": 1,
        "seed": 1,
        "stream": True,
        "stream_options": {"include_usage": True},
        "ignore_eos": True,
        "return_token_ids": True,
        "add_special_tokens": False,
        "truncate_prompt_tokens": None,
    }
    if adapter == "llama-server":
        payload.update(
            {
                "cache_prompt": False,
                "return_tokens": True,
                "verbose": True,
            }
        )
    return payload


def request_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "prompt"} | {
        "prompt_token_count": len(payload["prompt"]),
        "prompt_token_ids_sha256": token_ids_sha256(payload["prompt"]),
        "request_payload_sha256": sha256_bytes(canonical_bytes(payload)),
    }


def _event_adapter(event: dict[str, Any], requested: str) -> str | None:
    if requested != "auto":
        return requested
    if isinstance(event.get("__verbose"), dict):
        return "llama-server"
    choices = event.get("choices")
    if isinstance(choices, list) and any(
        isinstance(choice, dict) and isinstance(choice.get("token_ids"), list)
        for choice in choices
    ):
        return "vllm"
    return None


def _valid_token_delta(value: Any, *, label: str) -> list[int]:
    if not isinstance(value, list):
        return []
    if not all(_plain_int(token) and token >= 0 for token in value):
        raise ValueError(f"{label} contains a malformed token ID")
    return list(value)


def post_stream(
    *,
    base_url: str,
    payload: dict[str, Any],
    timeout: int,
    requested_adapter: str,
    request_id: str,
) -> dict[str, Any]:
    endpoint = f"{base_url.rstrip('/')}/v1/completions"
    request = urllib.request.Request(
        endpoint,
        data=canonical_bytes(payload),
        headers={"Content-Type": "application/json", "X-Request-Id": request_id},
        method="POST",
    )
    started_epoch_s = time.time()
    started = time.perf_counter()
    offsets: list[float] = []
    token_ids: list[int] = []
    text_parts: list[str] = []
    usage: dict[str, Any] = {}
    finish_reasons: list[str] = []
    returned_prompt_ids: list[int] | None = None
    response_ids: list[str] = []
    response_request_id: str | None = None
    done_seen = False
    selected_adapter: str | None = None
    verbose_truncated: bool | None = None
    verbose_context_shift: bool | None = None
    verbose_stop_type: str | None = None
    llama_cache_n: int | None = None
    token_sse_event_count = 0

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_request_id = response.headers.get("X-Request-Id")
            for raw in response:
                line = raw.decode("utf-8", errors="strict").strip()
                if not line.startswith("data:"):
                    continue
                body = line[5:].strip()
                if body == "[DONE]":
                    done_seen = True
                    break
                event = json.loads(body)
                if not isinstance(event, dict):
                    raise ValueError("SSE data event must be a JSON object")
                event_id = event.get("id")
                if isinstance(event_id, str):
                    response_ids.append(event_id)
                if isinstance(event.get("usage"), dict):
                    usage = event["usage"]
                adapter = _event_adapter(event, requested_adapter)
                if adapter is not None:
                    if selected_adapter is not None and adapter != selected_adapter:
                        raise ValueError("response adapter changed during stream")
                    selected_adapter = adapter

                event_tokens: list[int] = []
                verbose = event.get("__verbose")
                if selected_adapter == "llama-server" and isinstance(verbose, dict):
                    event_tokens = _valid_token_delta(
                        verbose.get("tokens"), label="llama-server verbose tokens"
                    )
                    prompt_ids = verbose.get("prompt_token_ids")
                    if isinstance(prompt_ids, list):
                        returned_prompt_ids = _valid_token_delta(
                            prompt_ids, label="llama-server prompt token IDs"
                        )
                    if isinstance(verbose.get("truncated"), bool):
                        verbose_truncated = verbose["truncated"]
                    for key in ("context_shift", "context_shifted"):
                        if isinstance(verbose.get(key), bool):
                            verbose_context_shift = verbose[key]
                    if isinstance(verbose.get("stop_type"), str):
                        verbose_stop_type = verbose["stop_type"]
                    timings = event.get("timings")
                    if isinstance(timings, dict) and _plain_int(timings.get("cache_n")):
                        llama_cache_n = timings["cache_n"]

                choices = event.get("choices")
                if isinstance(choices, list):
                    if len(choices) > 1:
                        raise ValueError("benchmark requires one completion choice")
                    for choice in choices:
                        if not isinstance(choice, dict):
                            raise ValueError("completion choice must be an object")
                        finish = choice.get("finish_reason")
                        if isinstance(finish, str):
                            finish_reasons.append(finish)
                        text = choice.get("text")
                        if isinstance(text, str) and text:
                            text_parts.append(text)
                        if selected_adapter == "vllm":
                            event_tokens = _valid_token_delta(
                                choice.get("token_ids"), label="vLLM token IDs"
                            )
                            prompt_ids = choice.get("prompt_token_ids")
                            if isinstance(prompt_ids, list):
                                returned_prompt_ids = _valid_token_delta(
                                    prompt_ids, label="vLLM prompt token IDs"
                                )
                if event_tokens:
                    now = time.perf_counter() - started
                    token_ids.extend(event_tokens)
                    offsets.extend([now] * len(event_tokens))
                    token_sse_event_count += 1
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code}: {body[:2000]}") from error

    ended = time.perf_counter()
    if selected_adapter is None:
        raise ValueError("could not detect a token-ID response adapter")
    return {
        "request_started_epoch_s": started_epoch_s,
        "elapsed_s": ended - started,
        "request_id": request_id,
        "response_x_request_id": response_request_id,
        "response_ids": response_ids,
        "adapter": selected_adapter,
        "done_seen": done_seen,
        "token_ids": token_ids,
        "token_id_offsets_s": offsets,
        "token_sse_event_count": token_sse_event_count,
        "returned_prompt_token_ids": returned_prompt_ids,
        "usage": usage,
        "finish_reasons": finish_reasons,
        "verbose_truncated": verbose_truncated,
        "verbose_context_shift": verbose_context_shift,
        "verbose_stop_type": verbose_stop_type,
        "llama_cache_n": llama_cache_n,
        "text_sha256": sha256_bytes("".join(text_parts).encode("utf-8")),
        "text_preview": "".join(text_parts)[:320],
    }


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    weight = position - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def metric_window(offsets: list[float]) -> dict[str, Any]:
    if len(offsets) < METRIC_EVENTS:
        return {
            "timestamped_events": len(offsets),
            "inter_token_intervals": max(0, len(offsets) - 1),
            "conventional_99_interval_tok_s": None,
            "historical_100_event_tok_s": None,
            "interval_s": None,
        }
    selected = offsets[:METRIC_EVENTS]
    intervals = [right - left for left, right in zip(selected, selected[1:])]
    span = selected[-1] - selected[0]
    valid = span > 0 and all(value >= 0 for value in intervals)
    return {
        "timestamped_events": METRIC_EVENTS,
        "inter_token_intervals": len(intervals),
        "first_event_offset_s": selected[0],
        "time_to_first_token_s": selected[0],
        "last_event_offset_s": selected[-1],
        "window_span_s": span,
        "conventional_99_interval_tok_s": METRIC_INTERVALS / span if valid else None,
        "historical_100_event_tok_s": METRIC_EVENTS / span if valid else None,
        "interval_s": {
            "p10": percentile(intervals, 0.1),
            "median": statistics.median(intervals),
            "mean": statistics.fmean(intervals),
            "min": min(intervals),
            "max": max(intervals),
        },
    }


def validate_response(
    fixture: Fixture,
    payload: dict[str, Any],
    row: dict[str, Any],
    context_capacity: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
    details = (
        usage.get("prompt_tokens_details")
        if isinstance(usage.get("prompt_tokens_details"), dict)
        else {}
    )
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")
    cached_tokens = details.get("cached_tokens")
    returned = row.get("returned_prompt_token_ids")
    adapter = row["adapter"]
    timing = metric_window(row["token_id_offsets_s"])
    checks = {
        "endpoint_is_v1_completions": True,
        "request_prompt_is_flat_integer_array": all(
            _plain_int(value) and value >= 0 for value in payload["prompt"]
        ),
        "request_prompt_depth_exact": len(payload["prompt"]) == fixture.selected.depth,
        "request_prompt_hash_exact": (
            token_ids_sha256(payload["prompt"])
            == fixture.selected.prompt_token_ids_sha256
        ),
        "context_capacity_covers_prompt_and_output": (
            context_capacity >= fixture.selected.depth + MAX_TOKENS
        ),
        "usage_prompt_tokens_exact": prompt_tokens == fixture.selected.depth,
        "cached_tokens_zero": cached_tokens == 0,
        "completion_tokens_exact": completion_tokens == MAX_TOKENS,
        "usage_total_tokens_exact": (
            total_tokens == fixture.selected.depth + MAX_TOKENS
        ),
        "stream_token_ids_exact": len(row["token_ids"]) == MAX_TOKENS,
        "metric_events_exact": timing["timestamped_events"] == METRIC_EVENTS,
        "metric_intervals_exact": timing["inter_token_intervals"] == METRIC_INTERVALS,
        "metric_span_positive": timing["conventional_99_interval_tok_s"] is not None,
        "finish_reason_length": row["finish_reasons"] == ["length"],
        "done_seen": row["done_seen"] is True,
        "returned_prompt_ids_exact_if_reported": (
            returned is None or returned == fixture.selected.prompt_token_ids
        ),
        "request_disables_special_tokens": payload["add_special_tokens"] is False,
        "request_disables_prompt_truncation": payload["truncate_prompt_tokens"] is None,
        "request_disables_prompt_cache": payload.get("cache_prompt") in {None, False},
        "request_ignores_eos": payload["ignore_eos"] is True,
        "request_returns_token_ids": payload["return_token_ids"] is True,
        "no_context_shift_reported": row["verbose_context_shift"] in {None, False},
        "llama_prompt_not_truncated": (
            adapter != "llama-server" or row["verbose_truncated"] is False
        ),
        "llama_stop_is_limit": (
            adapter != "llama-server" or row["verbose_stop_type"] == "limit"
        ),
        "llama_cache_zero_if_reported": row["llama_cache_n"] in {None, 0},
    }
    return checks, timing


def build_receipt(
    *,
    args: argparse.Namespace,
    fixture: Fixture,
    payload: dict[str, Any],
    row: dict[str, Any],
) -> dict[str, Any]:
    checks, timing = validate_response(fixture, payload, row, args.context_capacity)
    passed = all(checks.values())
    return {
        "schema": RECEIPT_SCHEMA,
        "status": "passed" if passed else "failed",
        "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "run_identity": {
            "base_url": validate_base_url(args.base_url),
            "endpoint": "/v1/completions",
            "model": args.model,
            "requested_response_adapter": args.response_adapter,
            "selected_response_adapter": row["adapter"],
            "depth": fixture.selected.depth,
            "active_context_tokens": fixture.selected.depth,
            "configured_context_capacity": args.context_capacity,
            "minimum_context_capacity": fixture.selected.depth + MAX_TOKENS,
            "case_id": fixture.selected.case_id,
            "max_tokens": MAX_TOKENS,
            "metric_events": METRIC_EVENTS,
            "metric_intervals": METRIC_INTERVALS,
        },
        "fixture": {
            "path": str(fixture.path.resolve()),
            "schema": SCHEMA,
            "fixture_id": fixture.fixture_id,
            "fixture_sha256": fixture.sha256,
            "case_count": fixture.case_count,
            "selected_case_sha256": fixture.selected.case_sha256,
            "prompt_token_ids_sha256": fixture.selected.prompt_token_ids_sha256,
            "provenance": fixture.provenance,
            "provenance_sha256": fixture.provenance_sha256,
        },
        "request": request_summary(payload),
        "gate": {
            "passed": passed,
            "checks": checks,
            "required_policy": (
                "one exact flat-token completion at D>0; usage.prompt_tokens=D; "
                "cached_tokens=0; no prompt truncation/context shift; 128 returned "
                "token IDs; conventional first-100 timing uses 99 intervals"
            ),
        },
        "metric_window": timing,
        "context_semantics": {
            "definition": (
                "exactly D submitted tokens, confirmed by usage.prompt_tokens, "
                "resident before the measured 128-token generation window"
            ),
            "fills_exact_active_context_axis": passed,
            "configured_context_capacity_is_not_active_context": True,
            "generation_window_advances_context_beyond_D": True,
        },
        "response": {
            key: value
            for key, value in row.items()
            if key not in {"token_id_offsets_s", "returned_prompt_token_ids"}
        }
        | {
            "output_token_ids_sha256": token_ids_sha256(row["token_ids"]),
            "returned_prompt_token_ids_sha256": (
                None
                if row["returned_prompt_token_ids"] is None
                else token_ids_sha256(row["returned_prompt_token_ids"])
            ),
        },
    }


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")


def execute(args: argparse.Namespace, fixture: Fixture) -> int:
    base_url = validate_base_url(args.base_url)
    if args.context_capacity is None:
        raise ValueError("--context-capacity is required with --execute")
    if args.context_capacity < fixture.selected.depth + MAX_TOKENS:
        raise ValueError(
            "--context-capacity must cover depth + 128 output tokens "
            f"({fixture.selected.depth + MAX_TOKENS})"
        )
    if args.out is not None and args.out.exists():
        raise ValueError(f"refusing to overwrite existing output: {args.out}")
    payload = request_payload(
        model=args.model,
        prompt_token_ids=fixture.selected.prompt_token_ids,
        adapter=args.response_adapter,
    )
    request_id = re.sub(
        r"[^A-Za-z0-9_.:-]+",
        "-",
        f"depth-{fixture.fixture_id}-{fixture.selected.case_id}",
    )[:180]
    row = post_stream(
        base_url=base_url,
        payload=payload,
        timeout=args.timeout,
        requested_adapter=args.response_adapter,
        request_id=request_id,
    )
    receipt = build_receipt(args=args, fixture=fixture, payload=payload, row=row)
    if args.out is not None:
        write_receipt(args.out, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["gate"]["passed"] else 2


def plan(args: argparse.Namespace, fixture: Fixture) -> dict[str, Any]:
    if (
        args.context_capacity is not None
        and args.context_capacity < fixture.selected.depth + MAX_TOKENS
    ):
        raise ValueError(
            "--context-capacity must cover depth + 128 output tokens "
            f"({fixture.selected.depth + MAX_TOKENS})"
        )
    payload = request_payload(
        model=args.model,
        prompt_token_ids=fixture.selected.prompt_token_ids,
        adapter=args.response_adapter,
    )
    return {
        "action": "plan-only",
        "network_requests": 0,
        "output_writes": 0,
        "fixture_id": fixture.fixture_id,
        "fixture_sha256": fixture.sha256,
        "case_id": fixture.selected.case_id,
        "depth": fixture.selected.depth,
        "configured_context_capacity": args.context_capacity,
        "minimum_context_capacity": fixture.selected.depth + MAX_TOKENS,
        "endpoint_if_executed": f"{validate_base_url(args.base_url)}/v1/completions",
        "request": request_summary(payload),
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    action = root.add_mutually_exclusive_group()
    action.add_argument(
        "--check", action="store_true", help="validate local inputs only"
    )
    action.add_argument("--plan", action="store_true", help="print a no-network plan")
    action.add_argument("--execute", action="store_true", help="perform one request")
    root.add_argument("--fixture", type=Path)
    root.add_argument("--depth", type=int, choices=ALLOWED_DEPTHS)
    root.add_argument("--case-id")
    root.add_argument(
        "--context-capacity",
        type=int,
        help="endpoint token capacity; --execute requires at least depth + 128",
    )
    root.add_argument("--base-url", default="http://127.0.0.1:18080")
    root.add_argument("--model", default="served-model")
    root.add_argument(
        "--response-adapter",
        choices=("auto", "vllm", "llama-server"),
        default="vllm",
    )
    root.add_argument("--timeout", type=int, default=3600)
    root.add_argument("--out", type=Path)
    return root


def main(argv: Iterable[str] | None = None) -> int:
    root = parser()
    args = root.parse_args(argv)
    if not (args.check or args.plan or args.execute):
        root.print_help()
        return 0
    if args.fixture is None or args.depth is None:
        root.error("--fixture and --depth are required for --check/--plan/--execute")
    if args.out is not None and not args.execute:
        root.error("--out is accepted only with --execute")
    if args.timeout <= 0:
        root.error("--timeout must be positive")
    try:
        fixture = load_fixture(args.fixture, args.depth, args.case_id)
        if args.check:
            print(
                f"CHECK passed fixture={fixture.fixture_id} "
                f"case={fixture.selected.case_id} depth={fixture.selected.depth} "
                "network_requests=0 output_writes=0"
            )
            return 0
        if args.plan:
            print(json.dumps(plan(args, fixture), indent=2, sort_keys=True))
            return 0
        return execute(args, fixture)
    except (OSError, ValueError, RuntimeError) as error:
        root.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
