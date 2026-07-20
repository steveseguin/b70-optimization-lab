#!/usr/bin/env python3
"""Drive the two exact decode-anchor requests for the Phase-1 oracle packet."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone
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
        return json.loads(response.read())


def prompt_ids(length: int) -> list[int]:
    # Ordinary in-vocabulary IDs, deterministic and non-repeating over the
    # declared anchors. Raw-token completions avoid tokenizer-length ambiguity.
    return [4096 + ((index * 7919 + 17) % 60000) for index in range(length)]


def run_anchor(
    *,
    base_url: str,
    model: str,
    anchor: int,
    timeout: int,
) -> dict[str, Any]:
    ids = prompt_ids(anchor)
    payload = {
        "model": model,
        "prompt": ids,
        "temperature": 0,
        "max_tokens": 2,
        "seed": 20260720,
        "return_token_ids": True,
    }
    started = time.perf_counter()
    response = post_json(
        f"{base_url.rstrip('/')}/v1/completions",
        payload,
        timeout,
    )
    usage = response.get("usage") or {}
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    if prompt_tokens != anchor:
        raise RuntimeError(f"anchor {anchor}: API reported prompt_tokens={prompt_tokens}")
    if not isinstance(completion_tokens, int) or completion_tokens < 2:
        raise RuntimeError(
            f"anchor {anchor}: only {completion_tokens} completion tokens"
        )
    details = usage.get("prompt_tokens_details") or {}
    return {
        "anchor_position": anchor,
        "bucket": (
            "SWA-resident" if anchor == 64 else "compressed+SWA-window-full"
        ),
        "prompt_token_ids_sha256": hashlib.sha256(
            json.dumps(ids, separators=(",", ":")).encode()
        ).hexdigest(),
        "elapsed_s": time.perf_counter() - started,
        "usage": usage,
        "cached_tokens": details.get("cached_tokens"),
        "response_id": response.get("id"),
        "finish_reason": response["choices"][0].get("finish_reason"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--model", default="deepseek-v4-flash-k160")
    parser.add_argument("--arm-file", type=Path, required=True)
    parser.add_argument("--warmup-file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--anchors", default="64,512")
    parser.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()

    anchors = [int(value) for value in args.anchors.split(",")]
    if anchors != [64, 512]:
        raise SystemExit("Phase-1 capture anchors must be exactly 64,512")
    if args.arm_file.exists():
        raise SystemExit(f"capture arm file already exists: {args.arm_file}")
    warmup_file = args.warmup_file or args.arm_file.with_name("warmup.arm")
    if warmup_file.exists():
        raise SystemExit(f"capture warmup file already exists: {warmup_file}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.arm_file.parent.mkdir(parents=True, exist_ok=True)
    # Exercise both exact singleton-decode geometries with capture bookkeeping
    # active but discarded. Awaiting each response fences their in-order XPU
    # work before the real arm marker can exist.
    warmup_file.touch(exist_ok=False)
    warmup_rows: list[dict[str, Any]] = []
    try:
        for anchor in anchors:
            warmup_rows.append(
                run_anchor(
                    base_url=args.base_url,
                    model=args.model,
                    anchor=anchor,
                    timeout=args.timeout,
                )
            )
    finally:
        warmup_file.unlink(missing_ok=True)

    args.arm_file.touch(exist_ok=False)
    rows: list[dict[str, Any]] = []
    try:
        for anchor in anchors:
            rows.append(
                run_anchor(
                    base_url=args.base_url,
                    model=args.model,
                    anchor=anchor,
                    timeout=args.timeout,
                )
            )
    finally:
        args.arm_file.unlink(missing_ok=True)

    # The first unarmed forward flushes all four ranks while the model and
    # immutable weight bindings are still alive.
    flush_response = post_json(
        f"{args.base_url.rstrip('/')}/v1/completions",
        {
            "model": args.model,
            "prompt": prompt_ids(8),
            "temperature": 0,
            "max_tokens": 1,
            "seed": 20260720,
        },
        args.timeout,
    )
    output = {
        "schema": "m1-attention-boundary-v1-capture-requests",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "anchors": anchors,
        "warmup_completed_before_arm": len(warmup_rows) == len(anchors),
        "warmup_rows": warmup_rows,
        "cached_tokens_all_zero": all(row["cached_tokens"] == 0 for row in rows),
        "rows": rows,
        "flush_response_id": flush_response.get("id"),
    }
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
