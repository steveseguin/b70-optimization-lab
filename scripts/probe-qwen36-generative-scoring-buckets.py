#!/usr/bin/env python3
"""Measure /generative_scoring latency versus candidate item length.

This is a low-risk proxy for verifier-bucket shape sensitivity. It does not
measure true KV-resident speculative decode verification: the endpoint builds a
fresh prompt from query + item and scores next-token labels. The result is still
useful for stability and rough forward-shape cost before building a lower-level
KV verifier harness.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_TOKENIZER = (
    "/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8"
    "/snapshots/cced56592e8c8935f8220836b4baa04dfd389118"
)


def post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return {
            "status": resp.status,
            "json": json.loads(resp.read().decode("utf-8")),
        }


def repeated_ids(tokenizer: Any, target_tokens: int, seed_text: str) -> list[int]:
    seed_ids = tokenizer.encode(seed_text, add_special_tokens=False)
    if not seed_ids:
        raise ValueError("seed text produced no token ids")
    return (seed_ids * ((target_tokens + len(seed_ids) - 1) // len(seed_ids)))[:target_tokens]


def summarize(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    if not ordered:
        return {}
    return {
        "mean": statistics.fmean(ordered),
        "median": statistics.median(ordered),
        "min": ordered[0],
        "max": ordered[-1],
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


def score_once(
    *,
    base_url: str,
    model: str,
    query_ids: list[int],
    item_ids: list[int],
    label_ids: list[int],
    timeout: int,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "query": query_ids,
        "items": [item_ids],
        "label_token_ids": label_ids,
        "apply_softmax": True,
        "add_special_tokens": False,
    }
    started = time.perf_counter()
    response = post_json(f"{base_url.rstrip('/')}/generative_scoring", payload, timeout)
    elapsed = time.perf_counter() - started
    data = response["json"]
    return {
        "status": response["status"],
        "elapsed_s": elapsed,
        "elapsed_ms": elapsed * 1000.0,
        "score": data["data"][0]["score"],
        "usage": data.get("usage"),
        "response_id": data.get("id"),
    }


def parse_item_lengths(raw: str) -> list[int]:
    out = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        value = int(part)
        if value < 0:
            raise ValueError("item lengths must be non-negative")
        out.append(value)
    if not out:
        raise ValueError("no item lengths provided")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default="qwen36-35b-a3b-fp8")
    parser.add_argument("--tokenizer", default=DEFAULT_TOKENIZER)
    parser.add_argument("--prompt-tokens", type=int, default=512)
    parser.add_argument("--item-lengths", default="0,1,2,3,4,5,6,8,12,16,24,32")
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, trust_remote_code=True)
    item_lengths = parse_item_lengths(args.item_lengths)
    max_item_tokens = max(item_lengths)
    query_ids = repeated_ids(
        tokenizer,
        args.prompt_tokens,
        (
            "Intel XPU verifier bucket timing prompt. Preserve exact output quality "
            "while comparing speculative verification shapes and route stability. "
        ),
    )
    draft_ids = repeated_ids(
        tokenizer,
        max(1, max_item_tokens),
        " The next verified continuation should remain semantically stable and deterministic.",
    )
    label_ids = [
        tokenizer.encode(" yes", add_special_tokens=False)[0],
        tokenizer.encode(" no", add_special_tokens=False)[0],
    ]

    records = []
    for item_len in item_lengths:
        item_ids = draft_ids[:item_len]
        for phase, count in (("warmup", args.warmups), ("measure", args.repeats)):
            for index in range(count):
                result = score_once(
                    base_url=args.base_url,
                    model=args.model,
                    query_ids=query_ids,
                    item_ids=item_ids,
                    label_ids=label_ids,
                    timeout=args.timeout,
                )
                result.update({
                    "phase": phase,
                    "repeat_index": index,
                    "query_tokens": len(query_ids),
                    "item_tokens": item_len,
                    "total_prompt_tokens_expected": len(query_ids) + item_len,
                })
                records.append(result)

    measured = [row for row in records if row["phase"] == "measure"]
    by_len = []
    baseline_mean = None
    for item_len in item_lengths:
        rows = [row for row in measured if row["item_tokens"] == item_len]
        elapsed = [float(row["elapsed_ms"]) for row in rows]
        usage_prompt_tokens = [
            int(row.get("usage", {}).get("prompt_tokens", 0))
            for row in rows
            if row.get("usage")
        ]
        row_summary = {
            "item_tokens": item_len,
            "request_count": len(rows),
            "elapsed_ms": summarize(elapsed),
            "p90_elapsed_ms": percentile(elapsed, 0.90),
            "p99_elapsed_ms": percentile(elapsed, 0.99),
            "usage_prompt_tokens": summarize([float(v) for v in usage_prompt_tokens]),
        }
        if item_len == 0 and elapsed:
            baseline_mean = statistics.fmean(elapsed)
        if baseline_mean is not None and elapsed:
            row_summary["mean_delta_vs_item0_ms"] = statistics.fmean(elapsed) - baseline_mean
        by_len.append(row_summary)

    output = {
        "base_url": args.base_url.rstrip("/"),
        "model": args.model,
        "tokenizer": args.tokenizer,
        "prompt_tokens": len(query_ids),
        "item_lengths": item_lengths,
        "label_token_ids": label_ids,
        "method_caveat": (
            "This measures /generative_scoring prompt+item scoring. It is not a "
            "true KV-resident speculative decode verifier bucket benchmark."
        ),
        "summary_by_item_tokens": by_len,
        "records": records,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "output_json": str(args.output_json),
        "prompt_tokens": len(query_ids),
        "item_lengths": item_lengths,
        "summary_by_item_tokens": by_len,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
