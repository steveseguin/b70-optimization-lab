#!/usr/bin/env python3
"""Capture a deterministic short logprob corpus for arithmetic-lane A/Bs."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_prompts(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        meta: dict[str, Any] = {"suite_id": path.stem}
        raw_prompts = payload
    else:
        meta = {key: value for key, value in payload.items() if key != "prompts"}
        raw_prompts = payload["prompts"]
    prompts = []
    for index, item in enumerate(raw_prompts):
        if isinstance(item, dict):
            prompts.append(
                {
                    "id": str(item.get("id", f"prompt-{index:02d}")),
                    "prompt": str(item["prompt"]),
                }
            )
        else:
            prompts.append({"id": f"prompt-{index:02d}", "prompt": str(item)})
    return meta, prompts


def post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--model", default="deepseek-v4-flash-k160")
    parser.add_argument(
        "--model-revision",
        help="immutable target revision recorded in new promotion captures",
    )
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-tokens", type=int, default=8)
    parser.add_argument("--top-logprobs", type=int, default=20)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--inter-request-delay", type=float, default=0.0)
    parser.add_argument("--label", required=True)
    parser.add_argument(
        "--ids",
        help="Comma-separated prompt IDs to capture; defaults to the full suite.",
    )
    args = parser.parse_args()

    suite_meta, prompts = load_prompts(args.suite)
    if args.ids:
        selected = {value.strip() for value in args.ids.split(",") if value.strip()}
        prompts = [item for item in prompts if item["id"] in selected]
        missing = selected - {item["id"] for item in prompts}
        if missing:
            raise SystemExit(f"unknown prompt IDs: {sorted(missing)}")
    rows = []
    for index, item in enumerate(prompts):
        if index and args.inter_request_delay > 0:
            time.sleep(args.inter_request_delay)
        started = time.perf_counter()
        request_payload = {
            "model": args.model,
            "messages": [{"role": "user", "content": item["prompt"]}],
            "temperature": 0,
            "max_tokens": args.max_tokens,
            "seed": args.seed,
        }
        if args.top_logprobs > 0:
            request_payload.update(
                {"logprobs": True, "top_logprobs": args.top_logprobs}
            )
        response = post_json(
            f"{args.base_url.rstrip('/')}/v1/chat/completions",
            request_payload,
            args.timeout,
        )
        choice = response["choices"][0]
        usage = response.get("usage") or {}
        details = usage.get("prompt_tokens_details") or {}
        rows.append(
            {
                "id": item["id"],
                "prompt_sha256": hashlib.sha256(
                    item["prompt"].encode("utf-8")
                ).hexdigest(),
                "elapsed_s": time.perf_counter() - started,
                "content": choice["message"].get("content"),
                "finish_reason": choice.get("finish_reason"),
                "logprobs": (choice.get("logprobs") or {}).get("content") or [],
                "usage": usage,
                "cached_tokens": details.get("cached_tokens"),
                "system_fingerprint": response.get("system_fingerprint"),
            }
        )

    output = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "model": args.model,
        "model_revision": args.model_revision,
        "suite_path": str(args.suite),
        "suite_sha256": hashlib.sha256(args.suite.read_bytes()).hexdigest(),
        "suite": suite_meta,
        "seed": args.seed,
        "max_tokens": args.max_tokens,
        "top_logprobs": args.top_logprobs,
        "decoding": {
            "seed": args.seed,
            "max_tokens": args.max_tokens,
            "top_logprobs": args.top_logprobs,
        },
        "inter_request_delay": args.inter_request_delay,
        "cached_tokens_all_zero": all(row["cached_tokens"] == 0 for row in rows),
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: output[key] for key in output if key != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
