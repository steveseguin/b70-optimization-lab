#!/usr/bin/env python3
"""Warm Gemma frontdoor prompt cache for stable agent/session IDs."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 7200,
) -> dict[str, Any]:
    body = None
    req_headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req_headers.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = response.read()
    return json.loads(data.decode("utf-8"))


def read_optional(path: str | None) -> str | None:
    if not path:
        return None
    return Path(path).read_text(encoding="utf-8")


def discover_model(base_url: str, requested_model: str | None) -> str:
    if requested_model:
        return requested_model
    root = base_url.removesuffix("/v1")
    try:
        status = request_json("GET", f"{root}/v1/frontdoor/status", timeout=30)
        model = status.get("client_hints", {}).get("api", {}).get("model")
        if isinstance(model, str) and model:
            return model
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        pass
    return "gemma4-26b-a4b-q8"


def build_messages(args: argparse.Namespace) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    system_text = read_optional(args.system_file)
    user_text = read_optional(args.user_file) or args.prompt or "Cache warmup."
    if system_text:
        messages.append({"role": "system", "content": system_text})
    messages.append({"role": "user", "content": user_text})
    return messages


def agent_ids(args: argparse.Namespace) -> list[str]:
    if args.agents:
        return [item.strip() for item in args.agents.split(",") if item.strip()]
    return [f"{args.agent_prefix}-{index}" for index in range(args.agent_count)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model")
    parser.add_argument("--agents", help="Comma-separated sticky agent IDs.")
    parser.add_argument("--agent-prefix", default="bug-agent")
    parser.add_argument("--agent-count", type=int, default=8)
    parser.add_argument(
        "--tiers",
        default="auto",
        help="Comma-separated context tiers to warm: short,long,auto.",
    )
    parser.add_argument("--system-file")
    parser.add_argument("--user-file")
    parser.add_argument("--prompt")
    parser.add_argument("--max-tokens", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=7200)
    parser.add_argument("--out")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    model = discover_model(base_url, args.model)
    messages = build_messages(args)
    tiers = [item.strip() for item in args.tiers.split(",") if item.strip()]
    rows: list[dict[str, Any]] = []

    for tier in tiers:
        for agent_id in agent_ids(args):
            started = time.perf_counter()
            headers = {
                "X-Agent-Id": agent_id,
                "X-Sticky-Mode": "strict",
                "X-Context-Tier": tier,
            }
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": args.max_tokens,
                "temperature": args.temperature,
            }
            row: dict[str, Any] = {
                "agent_id": agent_id,
                "tier": tier,
                "ok": False,
            }
            try:
                response = request_json(
                    "POST",
                    f"{base_url}/chat/completions",
                    payload=payload,
                    headers=headers,
                    timeout=args.timeout,
                )
                usage = response.get("usage", {})
                row.update(
                    {
                        "ok": True,
                        "elapsed_s": time.perf_counter() - started,
                        "prompt_tokens": usage.get("prompt_tokens"),
                        "completion_tokens": usage.get("completion_tokens"),
                        "cached_tokens": (
                            usage.get("prompt_tokens_details", {}).get(
                                "cached_tokens"
                            )
                            if isinstance(usage.get("prompt_tokens_details"), dict)
                            else None
                        ),
                    }
                )
            except Exception as exc:  # noqa: BLE001 - command-line probe summary
                row.update(
                    {
                        "elapsed_s": time.perf_counter() - started,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            rows.append(row)
            print(json.dumps(row, sort_keys=True), flush=True)

    summary = {
        "base_url": base_url,
        "model": model,
        "tiers": tiers,
        "agent_ids": agent_ids(args),
        "rows": rows,
        "ok": all(row["ok"] for row in rows),
    }
    if args.out:
        Path(args.out).write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
