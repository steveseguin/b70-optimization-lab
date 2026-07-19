#!/usr/bin/env python3
"""Profile DSpark M=7 acceptance on public and explicitly DEV prompts.

The script runs one request at a time and snapshots vLLM's existing speculative
decode counters around every request. It intentionally has no knowledge of the
frozen speculation-evaluation packs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import statistics
import time
import urllib.request
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any


COUNTER_NAMES = {
    "drafts": "vllm:spec_decode_num_drafts_total",
    "draft_tokens": "vllm:spec_decode_num_draft_tokens_total",
    "accepted": "vllm:spec_decode_num_accepted_tokens_total",
}


def fetch_text(url: str, timeout: int) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8")


def metric_value(text: str, name: str, position: int | None = None) -> float:
    for line in text.splitlines():
        if not line.startswith(name + "{"):
            continue
        if position is not None and f'position="{position}"' not in line:
            continue
        return float(line.rsplit(None, 1)[1])
    raise RuntimeError(f"metric not found: {name}, position={position}")


def snapshot(base_url: str, timeout: int) -> dict[str, Any]:
    text = fetch_text(f"{base_url.rstrip('/')}/metrics", timeout)
    values = {key: metric_value(text, name) for key, name in COUNTER_NAMES.items()}
    values["positions"] = [
        metric_value(
            text, "vllm:spec_decode_num_accepted_tokens_per_pos_total", position
        )
        for position in range(7)
    ]
    values["running"] = metric_value(text, "vllm:num_requests_running")
    values["waiting"] = metric_value(text, "vllm:num_requests_waiting")
    return values


def subtract(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    return {
        key: int(round(after[key] - before[key]))
        for key in ("drafts", "draft_tokens", "accepted")
    } | {
        "positions": [
            int(round(a - b))
            for a, b in zip(after["positions"], before["positions"], strict=True)
        ]
    }


def post_request(
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    seed: int,
    timeout: int,
    request_id: str,
) -> dict[str, Any]:
    cache_salt = str(uuid.uuid4())
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "top_p": 1,
        "seed": seed,
        "stream": False,
        "return_token_ids": True,
        "cache_salt": cache_salt,
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Request-Id": request_id},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.load(response)
    elapsed_s = time.perf_counter() - started
    choice = result["choices"][0]
    text = (choice.get("message") or {}).get("content") or ""
    usage = result.get("usage") or {}
    return {
        "elapsed_s": elapsed_s,
        "finish_reason": choice.get("finish_reason"),
        "usage": usage,
        "cached_tokens": (usage.get("prompt_tokens_details") or {}).get(
            "cached_tokens"
        ),
        "output_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "output_text": text,
        "cache_salt_sha256": hashlib.sha256(cache_salt.encode()).hexdigest(),
    }


def load_prompts(public_path: Path, dev_path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    public = json.loads(public_path.read_text())
    dev = json.loads(dev_path.read_text())
    mapping = dev["public_category_by_id"]
    prompts: list[dict[str, str]] = []
    for item in public["prompts"]:
        prompt_id = item["id"]
        if prompt_id not in mapping:
            raise RuntimeError(f"missing category for public prompt {prompt_id}")
        prompts.append(
            {
                "id": prompt_id,
                "prompt": item["prompt"],
                "category": mapping[prompt_id],
                "source": "public-continuity",
            }
        )
    for item in dev["additional_prompts"]:
        prompts.append(
            {
                "id": item["id"],
                "prompt": item["prompt"],
                "category": item["category"],
                "source": "additional-dev",
            }
        )
    if len({item["id"] for item in prompts}) != len(prompts):
        raise RuntimeError("duplicate prompt id")
    return {
        "public_suite_id": public.get("suite_id"),
        "dev_suite_id": dev.get("suite_id"),
    }, prompts


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    drafts = sum(row["counter_delta"]["drafts"] for row in rows)
    draft_tokens = sum(row["counter_delta"]["draft_tokens"] for row in rows)
    accepted = sum(row["counter_delta"]["accepted"] for row in rows)
    positions = [
        sum(row["counter_delta"]["positions"][position] for row in rows)
        for position in range(7)
    ]
    marginal = [value / drafts if drafts else None for value in positions]
    conditional = []
    for position, value in enumerate(positions):
        denominator = drafts if position == 0 else positions[position - 1]
        conditional.append(value / denominator if denominator else None)
    run_length_counts = [drafts - positions[0]]
    run_length_counts.extend(
        positions[position] - positions[position + 1] for position in range(6)
    )
    run_length_counts.append(positions[6])
    completion_tokens = sum(
        int(row["response"]["usage"].get("completion_tokens") or 0) for row in rows
    )
    elapsed = [float(row["response"]["elapsed_s"]) for row in rows]
    return {
        "prompt_count": len(rows),
        "draft_cycles": drafts,
        "draft_tokens": draft_tokens,
        "accepted_draft_tokens": accepted,
        "draft_token_acceptance": accepted / draft_tokens if draft_tokens else None,
        "accepted_at_position_counts": positions,
        "marginal_acceptance_by_position": marginal,
        "conditional_acceptance_by_position": conditional,
        "accepted_run_length_counts": run_length_counts,
        "accepted_run_length_probabilities": [
            count / drafts if drafts else None for count in run_length_counts
        ],
        "emitted_tokens_per_cycle": 1 + accepted / drafts if drafts else None,
        "observed_completion_tokens_per_cycle": (
            completion_tokens / drafts if drafts else None
        ),
        "completion_tokens": completion_tokens,
        "request_elapsed_s_median": statistics.median(elapsed) if elapsed else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--model", default="deepseek-v4-flash-k160")
    parser.add_argument("--public-suite", type=Path, required=True)
    parser.add_argument("--dev-suite", type=Path, required=True)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    suite_identity, prompts = load_prompts(args.public_suite, args.dev_suite)
    initial = snapshot(args.base_url, args.timeout)
    if initial["running"] != 0 or initial["waiting"] != 0:
        raise RuntimeError(
            f"endpoint busy before run: running={initial['running']}, waiting={initial['waiting']}"
        )

    rows: list[dict[str, Any]] = []
    for index, item in enumerate(prompts):
        before = snapshot(args.base_url, args.timeout)
        if before["running"] != 0 or before["waiting"] != 0:
            raise RuntimeError(f"endpoint busy before prompt {item['id']}")
        request_id = re.sub(
            r"[^A-Za-z0-9_.:-]+", "-", f"dspark7-dev-{index:02d}-{item['id']}"
        )
        response = post_request(
            args.base_url,
            args.model,
            item["prompt"],
            args.max_tokens,
            args.seed,
            args.timeout,
            request_id,
        )
        after = snapshot(args.base_url, args.timeout)
        delta = subtract(after, before)
        if delta["draft_tokens"] != 7 * delta["drafts"]:
            raise RuntimeError(
                f"M=7 invariant failed for {item['id']}: {delta}"
            )
        if sum(delta["positions"]) != delta["accepted"]:
            raise RuntimeError(
                f"per-position sum failed for {item['id']}: {delta}"
            )
        if response["cached_tokens"] != 0:
            raise RuntimeError(
                f"cached_tokens was not zero for {item['id']}: {response['cached_tokens']}"
            )
        rows.append(
            {
                "prompt_index": index,
                "prompt_id": item["id"],
                "prompt_sha256": hashlib.sha256(item["prompt"].encode()).hexdigest(),
                "category": item["category"],
                "source": item["source"],
                "request_id": request_id,
                "counter_delta": delta,
                "response": response,
            }
        )
        print(
            f"{index + 1:02d}/{len(prompts):02d} {item['id']}: "
            f"cycles={delta['drafts']} accepted={delta['accepted']}"
        )

    categories: dict[str, list[dict[str, Any]]] = defaultdict(list)
    sources: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        categories[row["category"]].append(row)
        sources[row["source"]].append(row)
    overall = aggregate(rows)
    validations = {
        "one_request_at_a_time": True,
        "all_cached_tokens_zero": all(
            row["response"]["cached_tokens"] == 0 for row in rows
        ),
        "all_completion_tokens_equal_max": all(
            row["response"]["usage"].get("completion_tokens") == args.max_tokens
            for row in rows
        ),
        "all_m7_counter_invariants": all(
            row["counter_delta"]["draft_tokens"]
            == 7 * row["counter_delta"]["drafts"]
            for row in rows
        ),
        "all_position_sums_match": all(
            sum(row["counter_delta"]["positions"])
            == row["counter_delta"]["accepted"]
            for row in rows
        ),
        "finite_nonnegative_counts": all(
            math.isfinite(float(value)) and value >= 0
            for row in rows
            for value in (
                row["counter_delta"]["drafts"],
                row["counter_delta"]["draft_tokens"],
                row["counter_delta"]["accepted"],
                *row["counter_delta"]["positions"],
            )
        ),
    }
    result = {
        "run_identity": {
            **suite_identity,
            "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "base_url": args.base_url,
            "model": args.model,
            "public_suite_path": str(args.public_suite),
            "dev_suite_path": str(args.dev_suite),
            "max_tokens": args.max_tokens,
            "seed": args.seed,
            "speculative_width": 7,
            "classification": "DEV-only diagnostic; not frozen evaluation",
        },
        "validations": validations,
        "overall": overall,
        "by_category": {
            key: aggregate(value) for key, value in sorted(categories.items())
        },
        "by_source": {
            key: aggregate(value) for key, value in sorted(sources.items())
        },
        "rows": rows,
        "counter_snapshot_before": initial,
        "counter_snapshot_after": snapshot(args.base_url, args.timeout),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"overall": overall, "by_category": result["by_category"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
