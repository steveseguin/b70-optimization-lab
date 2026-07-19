#!/usr/bin/env python3
"""Measure DSpark policy throughput and acceptance on the explicit DEV suite.

This program intentionally knows only the public continuity suite and the
checked-in additional DEV prompts.  It issues one cold, uniquely salted request
at a time and combines streaming token timing with vLLM speculative counters.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import statistics
import time
import urllib.request
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any


COUNTERS = {
    "cycles": "vllm:spec_decode_num_drafts_total",
    "draft_tokens": "vllm:spec_decode_num_draft_tokens_total",
    "accepted": "vllm:spec_decode_num_accepted_tokens_total",
}


def metric_value(text: str, name: str, position: int | None = None) -> float:
    for line in text.splitlines():
        if not line.startswith(name + "{"):
            continue
        if position is not None and f'position="{position}"' not in line:
            continue
        return float(line.rsplit(None, 1)[1])
    raise RuntimeError(f"metric not found: {name}, position={position}")


def snapshot(base_url: str, timeout: int, width: int) -> dict[str, Any]:
    with urllib.request.urlopen(
        f"{base_url.rstrip('/')}/metrics", timeout=timeout
    ) as response:
        text = response.read().decode()
    values = {key: metric_value(text, name) for key, name in COUNTERS.items()}
    values["accepted_positions"] = [
        metric_value(
            text,
            "vllm:spec_decode_num_accepted_tokens_per_pos_total",
            position,
        )
        for position in range(width)
    ]
    values["running"] = metric_value(text, "vllm:num_requests_running")
    values["waiting"] = metric_value(text, "vllm:num_requests_waiting")
    return values


def subtract(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    result = {
        key: int(round(after[key] - before[key]))
        for key in ("cycles", "draft_tokens", "accepted")
    }
    result["accepted_positions"] = [
        int(round(a - b))
        for a, b in zip(
            after["accepted_positions"],
            before["accepted_positions"],
            strict=True,
        )
    ]
    return result


def post_stream(
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
        "stream": True,
        "stream_options": {"include_usage": True},
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
    first_at: float | None = None
    token_offsets: list[float] = []
    token_ids: list[int] = []
    text_parts: list[str] = []
    usage: dict[str, Any] = {}
    finish_reason: str | None = None
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw in response:
            line = raw.decode(errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            event = json.loads(data)
            if event.get("usage"):
                usage = event["usage"]
            for choice in event.get("choices", []):
                now = time.perf_counter()
                ids = choice.get("token_ids")
                if isinstance(ids, list) and ids:
                    if first_at is None:
                        first_at = now
                    token_ids.extend(int(value) for value in ids)
                    token_offsets.extend([now - started] * len(ids))
                delta = choice.get("delta") or {}
                text_parts.append(delta.get("content") or delta.get("reasoning") or "")
                finish_reason = choice.get("finish_reason") or finish_reason
    ended = time.perf_counter()
    text = "".join(text_parts)
    details = usage.get("prompt_tokens_details") or {}
    return {
        "elapsed_s": ended - started,
        "ttft_s": None if first_at is None else first_at - started,
        "token_id_offsets_s": token_offsets,
        "token_ids": token_ids,
        "completion_tokens": usage.get("completion_tokens"),
        "cached_tokens": details.get("cached_tokens"),
        "finish_reason": finish_reason,
        "output_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "cache_salt_sha256": hashlib.sha256(cache_salt.encode()).hexdigest(),
    }


def load_prompts(
    public_path: Path, dev_path: Path
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    public = json.loads(public_path.read_text())
    dev = json.loads(dev_path.read_text())
    mapping = dev["public_category_by_id"]
    prompts = [
        {
            "id": item["id"],
            "prompt": item["prompt"],
            "category": mapping[item["id"]],
            "source": "public-continuity",
        }
        for item in public["prompts"]
    ]
    prompts.extend(
        {
            "id": item["id"],
            "prompt": item["prompt"],
            "category": item["category"],
            "source": "additional-dev",
        }
        for item in dev["additional_prompts"]
    )
    if len({item["id"] for item in prompts}) != len(prompts):
        raise RuntimeError("duplicate DEV prompt ID")
    return {
        "public_suite_id": public.get("suite_id"),
        "dev_suite_id": dev.get("suite_id"),
    }, prompts


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def aggregate(rows: list[dict[str, Any]], width: int) -> dict[str, Any]:
    cycles = sum(row["counter_delta"]["cycles"] for row in rows)
    drafted = sum(row["counter_delta"]["draft_tokens"] for row in rows)
    accepted = sum(row["counter_delta"]["accepted"] for row in rows)
    positions = [
        sum(row["counter_delta"]["accepted_positions"][index] for row in rows)
        for index in range(width)
    ]
    speeds = [
        float(row["tok_s_1_100_after_ttft"])
        for row in rows
        if row["tok_s_1_100_after_ttft"] is not None
    ]
    emitted_per_cycle = 1 + accepted / cycles if cycles else None
    median_speed = statistics.median(speeds) if speeds else None
    return {
        "prompt_count": len(rows),
        "timed_prompt_count": len(speeds),
        "draft_cycles": cycles,
        "draft_tokens": drafted,
        "mean_scheduled_draft_length": drafted / cycles if cycles else None,
        "accepted_draft_tokens": accepted,
        "draft_token_acceptance": accepted / drafted if drafted else None,
        "accepted_at_position_counts": positions,
        "marginal_acceptance_by_position": [
            value / cycles if cycles else None for value in positions
        ],
        "conditional_acceptance_by_position": [
            value / (cycles if index == 0 else positions[index - 1])
            if (cycles if index == 0 else positions[index - 1])
            else None
            for index, value in enumerate(positions)
        ],
        "emitted_tokens_per_cycle": emitted_per_cycle,
        "net_tok_s_1_100_after_ttft_p10": percentile(speeds, 0.10),
        "net_tok_s_1_100_after_ttft_median": median_speed,
        "net_tok_s_1_100_after_ttft_mean": (
            statistics.fmean(speeds) if speeds else None
        ),
        "derived_cycle_ms_at_median_net_rate": (
            1000 * emitted_per_cycle / median_speed
            if emitted_per_cycle and median_speed
            else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--model", default="deepseek-v4-flash-k160")
    parser.add_argument("--public-suite", type=Path, required=True)
    parser.add_argument("--dev-suite", type=Path, required=True)
    parser.add_argument("--configured-width", type=int, required=True)
    parser.add_argument("--policy-label", required=True)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--metric-tokens", type=int, default=100)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    suite_identity, prompts = load_prompts(args.public_suite, args.dev_suite)
    initial = snapshot(args.base_url, args.timeout, args.configured_width)
    if initial["running"] or initial["waiting"]:
        raise RuntimeError(f"endpoint busy before DEV screen: {initial}")

    rows: list[dict[str, Any]] = []
    for index, item in enumerate(prompts):
        before = snapshot(args.base_url, args.timeout, args.configured_width)
        request_id = re.sub(
            r"[^A-Za-z0-9_.:-]+",
            "-",
            f"dspark-dev-{args.policy_label}-{index:02d}-{item['id']}",
        )[:180]
        response = post_stream(
            args.base_url,
            args.model,
            item["prompt"],
            args.max_tokens,
            args.seed,
            args.timeout,
            request_id,
        )
        after = snapshot(args.base_url, args.timeout, args.configured_width)
        delta = subtract(after, before)
        if sum(delta["accepted_positions"]) != delta["accepted"]:
            raise RuntimeError(f"position counter mismatch for {item['id']}: {delta}")
        if response["cached_tokens"] != 0:
            raise RuntimeError(f"nonzero cache for {item['id']}: {response}")
        offsets = response["token_id_offsets_s"]
        if len(offsets) >= args.metric_tokens:
            duration = offsets[args.metric_tokens - 1] - offsets[0]
            speed = args.metric_tokens / duration if duration > 0 else None
        else:
            speed = None
        rows.append(
            {
                "prompt_index": index,
                "prompt_id": item["id"],
                "prompt_sha256": hashlib.sha256(item["prompt"].encode()).hexdigest(),
                "category": item["category"],
                "source": item["source"],
                "request_id": request_id,
                "counter_delta": delta,
                "tok_s_1_100_after_ttft": speed,
                "response": response,
            }
        )
        print(
            f"{index + 1:02d}/{len(prompts):02d} {item['id']}: "
            f"tok/s={speed!s} cycles={delta['cycles']} "
            f"drafted={delta['draft_tokens']} accepted={delta['accepted']}",
            flush=True,
        )

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["category"]].append(row)
    overall = aggregate(rows, args.configured_width)
    result = {
        "run_identity": {
            **suite_identity,
            "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "model": args.model,
            "public_suite_path": str(args.public_suite),
            "dev_suite_path": str(args.dev_suite),
            "configured_width": args.configured_width,
            "policy_label": args.policy_label,
            "max_tokens": args.max_tokens,
            "metric_tokens": args.metric_tokens,
            "classification": "DEV-only diagnostic; not frozen evaluation",
        },
        "validations": {
            "one_request_at_a_time": True,
            "all_cached_tokens_zero": all(
                row["response"]["cached_tokens"] == 0 for row in rows
            ),
            "all_position_sums_match": all(
                sum(row["counter_delta"]["accepted_positions"])
                == row["counter_delta"]["accepted"]
                for row in rows
            ),
            "all_reached_metric_window": all(
                row["tok_s_1_100_after_ttft"] is not None for row in rows
            ),
        },
        "overall": overall,
        "by_category": {
            key: aggregate(value, args.configured_width)
            for key, value in sorted(groups.items())
        },
        "rows": rows,
        "counter_snapshot_before": initial,
        "counter_snapshot_after": snapshot(
            args.base_url, args.timeout, args.configured_width
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(overall, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
