#!/usr/bin/env python3
"""Health check for the production MiniMax OpenAI-compatible endpoint."""

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
    timeout: int = 60,
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
        if not text.strip():
            return resp.status, None, text
        try:
            return resp.status, json.loads(text), text
        except json.JSONDecodeError:
            return resp.status, None, text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--expected-max-model-len", type=int, default=32768)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--skip-completion", action="store_true")
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    result: dict[str, Any] = {
        "base_url": base_url,
        "ok": False,
        "checks": {},
        "errors": [],
    }

    try:
        started = time.perf_counter()
        status, _, text = request_json("GET", f"{base_url}/health", timeout=args.timeout)
        result["checks"]["health"] = {
            "status": status,
            "elapsed_s": round(time.perf_counter() - started, 3),
            "body_preview": text[:120],
        }
    except Exception as exc:
        result["errors"].append(f"/health failed: {exc}")

    model_id = None
    try:
        started = time.perf_counter()
        status, payload, _ = request_json(
            "GET", f"{base_url}/v1/models", timeout=args.timeout
        )
        models = [] if payload is None else payload.get("data", [])
        model = models[0] if models else {}
        model_id = model.get("id")
        max_model_len = model.get("max_model_len")
        result["checks"]["models"] = {
            "status": status,
            "elapsed_s": round(time.perf_counter() - started, 3),
            "model": model_id,
            "max_model_len": max_model_len,
        }
        if max_model_len != args.expected_max_model_len:
            result["errors"].append(
                f"expected max_model_len={args.expected_max_model_len}, got {max_model_len}"
            )
    except Exception as exc:
        result["errors"].append(f"/v1/models failed: {exc}")

    if not args.skip_completion and model_id:
        try:
            started = time.perf_counter()
            status, payload, _ = request_json(
                "POST",
                f"{base_url}/v1/completions",
                {
                    "model": model_id,
                    "prompt": "Reply with OK only.\n\nAnswer:",
                    "max_tokens": 1,
                    "temperature": 0,
                    "top_p": 1.0,
                    "seed": 1,
                },
                timeout=args.timeout,
            )
            usage = {} if payload is None else payload.get("usage", {})
            text = ""
            if payload is not None and payload.get("choices"):
                text = payload["choices"][0].get("text") or ""
            result["checks"]["completion"] = {
                "status": status,
                "elapsed_s": round(time.perf_counter() - started, 3),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "text_preview": text[:120],
            }
            if not usage.get("completion_tokens"):
                result["errors"].append("completion returned no completion tokens")
        except Exception as exc:
            result["errors"].append(f"/v1/completions failed: {exc}")

    result["ok"] = not result["errors"]
    text = json.dumps(result, indent=2) + "\n"
    print(text, end="")
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(text)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
