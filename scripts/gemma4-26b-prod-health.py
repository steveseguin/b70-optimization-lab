#!/usr/bin/env python3
"""Health and smoke checks for the Gemma 4 26B llama-server endpoint."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 300,
) -> tuple[int, dict[str, Any] | None, str]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8", errors="replace")
        try:
            return resp.status, json.loads(text), text
        except json.JSONDecodeError:
            return resp.status, None, text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:19350")
    parser.add_argument("--model", default="gemma4-26b-a4b-q8")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    result: dict[str, Any] = {
        "base_url": base_url,
        "model": args.model,
        "ok": False,
        "checks": {},
        "errors": [],
    }

    try:
        started = time.perf_counter()
        status, payload, text = request_json(
            "GET", f"{base_url}/v1/models", timeout=args.timeout
        )
        models = [] if payload is None else payload.get("data", [])
        result["checks"]["models"] = {
            "status": status,
            "elapsed_s": round(time.perf_counter() - started, 3),
            "models": [item.get("id") for item in models],
            "body_preview": text[:160],
        }
        if args.model not in [item.get("id") for item in models]:
            result["errors"].append(f"model {args.model!r} missing from /v1/models")
    except Exception as exc:
        result["errors"].append(f"/v1/models failed: {exc}")

    cases = [
        {
            "name": "json",
            "prompt": (
                "Return exactly this JSON object and nothing else: "
                "{\"answer\":42,\"unit\":\"widgets\"}\nAnswer:"
            ),
            "max_tokens": 32,
            "expected_contains": '"answer"',
        },
        {
            "name": "sort",
            "prompt": (
                "Sort these colors alphabetically. Reply only with the "
                "comma-separated list: orange, blue, red, green\nAnswer:"
            ),
            "max_tokens": 32,
            "expected_contains": "blue, green, orange, red",
        },
    ]

    rows: list[dict[str, Any]] = []
    for case in cases:
        try:
            started = time.perf_counter()
            status, payload, _ = request_json(
                "POST",
                f"{base_url}/v1/chat/completions",
                {
                    "model": args.model,
                    "messages": [{"role": "user", "content": case["prompt"]}],
                    "max_tokens": case["max_tokens"],
                    "temperature": 0,
                    "top_p": 1,
                    "seed": 1,
                },
                timeout=args.timeout,
            )
            content = ""
            usage: dict[str, Any] = {}
            if payload is not None:
                choice = (payload.get("choices") or [{}])[0]
                content = ((choice.get("message") or {}).get("content") or "").strip()
                usage = payload.get("usage") or {}
            ok = case["expected_contains"].lower() in content.lower()
            rows.append(
                {
                    "name": case["name"],
                    "status": status,
                    "elapsed_s": round(time.perf_counter() - started, 3),
                    "ok": ok,
                    "content": content,
                    "usage": usage,
                }
            )
            if not ok:
                result["errors"].append(
                    f"{case['name']} expected substring {case['expected_contains']!r}, got {content!r}"
                )
        except Exception as exc:
            result["errors"].append(f"{case['name']} completion failed: {exc}")

    result["checks"]["smoke_cases"] = rows
    result["ok"] = not result["errors"]
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(text)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
