#!/usr/bin/env python3
"""Capture llama.cpp native completion token IDs for a fixed prompt suite."""

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
                if not all(isinstance(token, int) for token in tokens):
                    raise RuntimeError("non-integer native completion token ID")
                now = time.perf_counter() - started
                token_ids.extend(tokens)
                token_offsets_s.extend([now] * len(tokens))
            content = event.get("content")
            if isinstance(content, str) and content:
                content_parts.append(content)
            if event.get("stop") is True:
                final = event
    if final is None:
        raise RuntimeError("native completion stream did not return a final event")
    return {
        "token_ids": token_ids,
        "token_offsets_s": token_offsets_s,
        "content": "".join(content_parts),
        "final": final,
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


def load_prompts(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    raw = json.loads(path.read_text())
    if isinstance(raw, list):
        meta = {"suite_id": path.stem, "version": None}
        entries = raw
    else:
        meta = {key: value for key, value in raw.items() if key != "prompts"}
        entries = raw["prompts"]
    prompts: list[dict[str, str]] = []
    for index, entry in enumerate(entries):
        if isinstance(entry, dict):
            prompt = str(entry["prompt"])
            prompt_id = str(entry.get("id", f"prompt-{index:02d}"))
        else:
            prompt = str(entry)
            prompt_id = f"prompt-{index:02d}"
        prompts.append({"id": prompt_id, "prompt": prompt})
    return meta, prompts


def load_oracle(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise SystemExit(f"oracle is not a JSON object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:19460")
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--oracle-json", type=Path)
    parser.add_argument("--max-prompts", type=int)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--runtime-sha256", required=True)
    parser.add_argument("--cache-type-k", required=True)
    parser.add_argument("--cache-type-v", required=True)
    parser.add_argument("--ctx-size", type=int, required=True)
    args = parser.parse_args()

    suite_meta, prompts = load_prompts(args.suite)
    if args.max_prompts is not None:
        if args.max_prompts <= 0:
            raise SystemExit("--max-prompts must be positive")
        prompts = prompts[: args.max_prompts]
    if not prompts:
        raise SystemExit("no prompts selected")

    base_url = args.base_url.rstrip("/")
    rows: list[dict[str, Any]] = []
    for entry in prompts:
        prompt = entry["prompt"]
        rendered = post_json(
            f"{base_url}/apply-template",
            {"messages": [{"role": "user", "content": prompt}]},
            args.timeout,
        ).get("prompt")
        if not isinstance(rendered, str) or not rendered:
            raise RuntimeError(f"empty rendered prompt for {entry['id']}")
        response = stream_completion(
            f"{base_url}/completion",
            {
                "prompt": rendered,
                "n_predict": args.max_tokens,
                "temperature": 0,
                "top_p": 1,
                "seed": args.seed,
                "cache_prompt": False,
                "return_tokens": True,
                "stream": True,
            },
            args.timeout,
        )
        tokens = response["token_ids"]
        if not isinstance(tokens, list) or not tokens or not all(
            isinstance(token, int) for token in tokens
        ):
            raise RuntimeError(f"missing raw token IDs for {entry['id']}")
        content = response["content"]
        if not isinstance(content, str):
            raise RuntimeError(f"missing completion content for {entry['id']}")
        final = response["final"]
        timings = final.get("timings")
        cache_n = timings.get("cache_n") if isinstance(timings, dict) else None
        predicted_n = (
            timings.get("predicted_n") if isinstance(timings, dict) else None
        )
        offsets = response["token_offsets_s"]
        interval_count = min(99, max(0, len(offsets) - 1))
        tok_s_1_100 = None
        if len(offsets) >= 100:
            duration = offsets[99] - offsets[0]
            if duration > 0:
                tok_s_1_100 = 99 / duration
        rows.append(
            {
                "prompt_id": entry["id"],
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "rendered_prompt_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
                "token_ids": tokens,
                "token_ids_sha256": hashlib.sha256(
                    json.dumps(tokens, separators=(",", ":")).encode()
                ).hexdigest(),
                "token_count": len(tokens),
                "final_predicted_n": predicted_n,
                "stream_token_ids_complete": predicted_n == len(tokens),
                "token_event_offsets_s": offsets,
                "primary_metric": {
                    "name": "tok_s_1_100_intervals_after_ttft",
                    "event_count": min(100, len(offsets)),
                    "interval_count": interval_count,
                    "numerator": 99 if len(offsets) >= 100 else interval_count,
                    "start_event_index": 0,
                    "end_event_index": 99 if len(offsets) >= 100 else len(offsets) - 1,
                    "start_generated_token_number": 1,
                    "end_generated_token_number": 100 if len(offsets) >= 100 else len(offsets),
                    "duration_s": (
                        offsets[99] - offsets[0]
                        if len(offsets) >= 100
                        else None
                    ),
                    "tok_s": tok_s_1_100,
                },
                "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
                "content": content,
                "cache_n": cache_n,
                "tokens_cached_native_semantics": final.get("tokens_cached"),
                "tokens_evaluated": final.get("tokens_evaluated"),
                "truncated": final.get("truncated"),
                "stop_type": final.get("stop_type"),
                "timings": timings if isinstance(timings, dict) else None,
            }
        )

    suite_sha256 = hashlib.sha256(args.suite.read_bytes()).hexdigest()
    intrinsic_pass = (
        len(rows) == len(prompts)
        and len({row["prompt_sha256"] for row in rows}) == len(rows)
        and len({row["prompt_id"] for row in rows}) == len(rows)
        and all(row["cache_n"] == 0 for row in rows)
        and all(row["truncated"] is False for row in rows)
        and all(row["token_count"] >= 100 for row in rows)
        and all(row["stream_token_ids_complete"] is True for row in rows)
        and all(row["primary_metric"]["interval_count"] == 99 for row in rows)
        and all(
            isinstance(row["primary_metric"]["tok_s"], (int, float))
            and row["primary_metric"]["tok_s"] > 0
            for row in rows
        )
    )
    oracle = load_oracle(args.oracle_json)
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
            "cache_prompt": False,
            "return_tokens": True,
            "stream": True,
        }
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
            "oracle_json": str(args.oracle_json),
            "oracle_sha256": hashlib.sha256(args.oracle_json.read_bytes()).hexdigest(),
            "suite_identity_match": identity_match,
            "identity_fields": identity_results,
            "prompt_ids_match": prompt_ids_match,
            "rows": row_results,
        }
        exit_code = 0 if passed else 1

    result = {
        "run_identity": {
            "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
            "base_url": base_url,
            "suite_path": str(args.suite),
            "suite_id": suite_meta.get("suite_id"),
            "suite_sha256": suite_sha256,
            "prompt_ids": [row["prompt_id"] for row in rows],
            "max_tokens": args.max_tokens,
            "seed": args.seed,
            "model_sha256": args.model_sha256,
            "runtime_sha256": args.runtime_sha256,
            "cache_type_k": args.cache_type_k,
            "cache_type_v": args.cache_type_v,
            "ctx_size": args.ctx_size,
            "api": "llama.cpp /apply-template then streaming /completion",
            "cache_prompt": False,
            "return_tokens": True,
            "stream": True,
        },
        "oracle_comparison": comparison,
        "intrinsic_gate": {
            "passed": intrinsic_pass,
            "rows_complete": len(rows) == len(prompts),
            "prompts_unique": len({row["prompt_sha256"] for row in rows}) == len(rows),
            "prompt_ids_unique": len({row["prompt_id"] for row in rows}) == len(rows),
            "native_cache_n_all_zero": all(row["cache_n"] == 0 for row in rows),
            "native_tokens_cached_note": "tokens_cached is current retained prompt state in this llama.cpp API; cache_n is the cache-reuse count",
            "not_truncated_all": all(row["truncated"] is False for row in rows),
            "raw_token_ids_at_least_100_all": all(row["token_count"] >= 100 for row in rows),
            "stream_token_ids_match_final_predicted_n_all": all(
                row["stream_token_ids_complete"] is True for row in rows
            ),
            "primary_interval_count_99_all": all(
                row["primary_metric"]["interval_count"] == 99 for row in rows
            ),
            "primary_rate_positive_all": all(
                isinstance(row["primary_metric"]["tok_s"], (int, float))
                and row["primary_metric"]["tok_s"] > 0
                for row in rows
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
        },
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
