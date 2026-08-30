#!/usr/bin/env python3
"""Bounded exact-depth greedy repeat with API-provided top-token scores."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


SCHEMA = "qwen38-exact-depth-logprob-repeat-v1"
DEPTH_MODULE_SHA256 = "8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067"
FIXTURE_SHA256 = "c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d"
PROMPT_SHA256 = "aedf2eb779bfa4aad8f533c644ca94646977deae1c10221bff592f06785c76d0"
AUTHORITY_SHA256 = "1d833e5f463366223a669aa15495840d1337b173e675a9ea04f00a5ae339d5cc"
TOKEN_PLACEHOLDER = re.compile(r"^token_id:(\d+)$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def token_ids_sha256(values: list[int]) -> str:
    return hashlib.sha256(canonical_bytes(values)).hexdigest()


def load_depth_module(path: Path) -> Any:
    if sha256(path) != DEPTH_MODULE_SHA256:
        raise RuntimeError("exact-depth module hash changed")
    spec = importlib.util.spec_from_file_location("q38_exact_depth_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load exact-depth module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_base_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base URL must be absolute HTTP(S)")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("base URL cannot contain credentials, query, or fragment")
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "")
    )


def parse_token_placeholder(value: str) -> int:
    match = TOKEN_PLACEHOLDER.fullmatch(value)
    if match is None:
        raise ValueError(
            f"logprob token is not an exact token-ID placeholder: {value!r}"
        )
    return int(match.group(1))


def normalize_logprob_step(
    logprobs: dict[str, Any], selected_token_id: int
) -> dict[str, Any]:
    tokens = logprobs.get("tokens")
    selected_scores = logprobs.get("token_logprobs")
    top_rows = logprobs.get("top_logprobs")
    if not (
        isinstance(tokens, list)
        and len(tokens) == 1
        and isinstance(selected_scores, list)
        and len(selected_scores) == 1
        and isinstance(top_rows, list)
        and len(top_rows) == 1
        and isinstance(top_rows[0], dict)
    ):
        raise ValueError("each streamed token must carry one complete logprob row")
    if parse_token_placeholder(tokens[0]) != selected_token_id:
        raise ValueError("selected token and logprob token disagree")
    top = [
        {"token_id": parse_token_placeholder(token), "logprob": float(score)}
        for token, score in top_rows[0].items()
    ]
    top.sort(key=lambda item: (-item["logprob"], item["token_id"]))
    if not top:
        raise ValueError("top-token score list is empty")
    selected = next(
        (item for item in top if item["token_id"] == selected_token_id), None
    )
    if selected is None:
        raise ValueError("selected token is absent from top-token score list")
    margin = None
    if len(top) >= 2:
        margin = top[0]["logprob"] - top[1]["logprob"]
    return {
        "selected_token_id": selected_token_id,
        "selected_logprob": float(selected_scores[0]),
        "top": top,
        "top1_token_id": top[0]["token_id"],
        "top1_top2_logprob_margin": margin,
        "selected_is_top1": selected_token_id == top[0]["token_id"],
    }


def first_diff(left: list[int], right: list[int]) -> int | None:
    for index, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return index
    return None if len(left) == len(right) else min(len(left), len(right))


def post_stream(
    base_url: str,
    payload: dict[str, Any],
    timeout: int,
    request_id: str,
) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{base_url}/v1/completions",
        data=canonical_bytes(payload),
        headers={"Content-Type": "application/json", "X-Request-Id": request_id},
        method="POST",
    )
    started_epoch = time.time()
    started = time.perf_counter()
    token_ids: list[int] = []
    decisions: list[dict[str, Any]] = []
    usage: dict[str, Any] = {}
    finish_reasons: list[str] = []
    done_seen = False
    response_request_id: str | None = None
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
                if isinstance(event.get("usage"), dict):
                    usage = event["usage"]
                choices = event.get("choices")
                if not isinstance(choices, list) or len(choices) > 1:
                    raise ValueError(
                        "stream must contain at most one completion choice"
                    )
                if not choices:
                    continue
                choice = choices[0]
                finish = choice.get("finish_reason")
                if isinstance(finish, str):
                    finish_reasons.append(finish)
                event_ids = choice.get("token_ids")
                if event_ids is None or event_ids == []:
                    continue
                if not (
                    isinstance(event_ids, list)
                    and len(event_ids) == 1
                    and isinstance(event_ids[0], int)
                    and not isinstance(event_ids[0], bool)
                ):
                    raise ValueError(
                        "each token event must expose one integer token ID"
                    )
                decision = normalize_logprob_step(choice.get("logprobs"), event_ids[0])
                decision["index"] = len(token_ids)
                token_ids.append(event_ids[0])
                decisions.append(decision)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code}: {body[:2000]}") from error
    elapsed = time.perf_counter() - started
    details = usage.get("prompt_tokens_details") or {}
    checks = {
        "done_seen": done_seen,
        "finish_reason_length": finish_reasons == ["length"],
        "token_count_128": len(token_ids) == 128,
        "decision_count_128": len(decisions) == 128,
        "usage_exact": (
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
            usage.get("total_tokens"),
        )
        == (4096, 128, 4224),
        "cached_tokens_zero": details.get("cached_tokens") == 0,
        "selected_is_top1_all": all(row["selected_is_top1"] for row in decisions),
    }
    return {
        "request_id": request_id,
        "response_x_request_id": response_request_id,
        "request_started_epoch_s": started_epoch,
        "elapsed_s": elapsed,
        "usage": usage,
        "finish_reasons": finish_reasons,
        "done_seen": done_seen,
        "token_ids": token_ids,
        "output_token_ids_sha256": token_ids_sha256(token_ids),
        "matches_retained_authority": token_ids_sha256(token_ids) == AUTHORITY_SHA256,
        "decisions": decisions,
        "checks": checks,
        "passed": all(checks.values()),
    }


def build_payload(model: str, prompt: list[int], top_logprobs: int) -> dict[str, Any]:
    return {
        "model": model,
        "prompt": prompt,
        "max_tokens": 128,
        "temperature": 0,
        "top_p": 1,
        "seed": 1,
        "stream": True,
        "stream_options": {"include_usage": True},
        "ignore_eos": True,
        "return_token_ids": True,
        "return_tokens_as_token_ids": True,
        "add_special_tokens": False,
        "truncate_prompt_tokens": None,
        "logprobs": top_logprobs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--depth-module", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:19683")
    parser.add_argument("--model", default="qwen38-flash-next-fp8-tp4")
    parser.add_argument("--repeats", type=int, default=4)
    parser.add_argument("--top-logprobs", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--request-id-prefix", default="q38-ple-only-a11-logprob")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not 2 <= args.repeats <= 8:
        parser.error("--repeats must be between 2 and 8")
    if not 2 <= args.top_logprobs <= 20:
        parser.error("--top-logprobs must be between 2 and 20")
    if sha256(args.fixture) != FIXTURE_SHA256:
        raise RuntimeError("exact-depth fixture hash changed")
    module = load_depth_module(args.depth_module)
    fixture = module.load_fixture(args.fixture, 4096)
    if fixture.selected.prompt_token_ids_sha256 != PROMPT_SHA256:
        raise RuntimeError("selected exact-4K prompt hash changed")
    base_url = validate_base_url(args.base_url)
    payload = build_payload(
        args.model, fixture.selected.prompt_token_ids, args.top_logprobs
    )
    request_summary = {
        key: value for key, value in payload.items() if key != "prompt"
    } | {
        "prompt_tokens": len(payload["prompt"]),
        "prompt_token_ids_sha256": token_ids_sha256(payload["prompt"]),
        "diagnostic_request_payload_sha256": hashlib.sha256(
            canonical_bytes(payload)
        ).hexdigest(),
    }
    if args.plan:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "network_requests": 0,
                    "output_writes": 0,
                    "base_url": base_url,
                    "repeats": args.repeats,
                    "request": request_summary,
                    "performance_credit": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.out is None:
        parser.error("--execute requires --out")
    if args.out.exists():
        parser.error(f"refusing to overwrite {args.out}")
    rows = [
        post_stream(
            base_url,
            payload,
            args.timeout,
            f"{args.request_id_prefix}-{index:02d}",
        )
        for index in range(1, args.repeats + 1)
    ]
    authority = next((row for row in rows if row["matches_retained_authority"]), None)
    pairwise = []
    for left_index, left in enumerate(rows):
        for right_index, right in enumerate(rows[left_index + 1 :], left_index + 1):
            pairwise.append(
                {
                    "left_row": left_index + 1,
                    "right_row": right_index + 1,
                    "first_different_token_index": first_diff(
                        left["token_ids"], right["token_ids"]
                    ),
                }
            )
    result = {
        "schema": SCHEMA,
        "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "status": "passed" if all(row["passed"] for row in rows) else "failed",
        "identity": {
            "base_url": base_url,
            "model": args.model,
            "depth_module_sha256": DEPTH_MODULE_SHA256,
            "fixture_sha256": FIXTURE_SHA256,
            "retained_authority_sha256": AUTHORITY_SHA256,
            "repeats": args.repeats,
            "top_logprobs": args.top_logprobs,
        },
        "request": request_summary,
        "rows": rows,
        "analysis": {
            "unique_output_hashes": sorted(
                {row["output_token_ids_sha256"] for row in rows}
            ),
            "authority_match_count": sum(
                row["matches_retained_authority"] for row in rows
            ),
            "captured_authority_and_divergent_output": (
                authority is not None
                and any(not row["matches_retained_authority"] for row in rows)
            ),
            "selected_is_top1_all": all(
                decision["selected_is_top1"]
                for row in rows
                for decision in row["decisions"]
            ),
            "pairwise": pairwise,
        },
        "performance_credit": False,
        "interpretation": (
            "Report-only API top-token evidence. Adding logprobs changes request "
            "instrumentation and makes all timings ineligible for performance credit."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "unique_output_hashes": result["analysis"]["unique_output_hashes"],
                "authority_match_count": result["analysis"]["authority_match_count"],
                "captured_authority_and_divergent_output": result["analysis"][
                    "captured_authority_and_divergent_output"
                ],
            },
            sort_keys=True,
        )
    )
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
