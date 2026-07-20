#!/usr/bin/env python3
"""Capture a bounded PTI unitrace window inside one streamed decode request."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
import urllib.request
from pathlib import Path


def control(unitrace: Path, action: str, session: str) -> dict[str, object]:
    started_ns = time.monotonic_ns()
    proc = subprocess.run(
        [str(unitrace), f"--{action}", session],
        check=False,
        capture_output=True,
        text=True,
    )
    ended_ns = time.monotonic_ns()
    if proc.returncode != 0:
        raise RuntimeError(
            f"unitrace --{action} failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return {
        "action": action,
        "started_monotonic_ns": started_ns,
        "ended_monotonic_ns": ended_ns,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--model", default="deepseek-v4-flash-k160")
    parser.add_argument("--unitrace", type=Path, required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--trace-chunks", type=int, default=24)
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    prompt = (
        "Write numbered technical lines until the token limit. Every line must "
        "contain decode, kernel, collective, submission, latency, and validation. "
        "Do not summarize or conclude. Begin at line 001."
    )
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": args.max_tokens,
        "temperature": 0,
        "top_p": 1,
        "seed": 20260720,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    request = urllib.request.Request(
        f"{args.base_url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    request_started_ns = time.monotonic_ns()
    first_text_ns = None
    chunk_times_ns: list[int] = []
    text_parts: list[str] = []
    controls: list[dict[str, object]] = []
    usage: dict[str, object] = {}
    paused = False

    with urllib.request.urlopen(request, timeout=600) as response:
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
                delta = choice.get("delta") or {}
                text = (
                    delta.get("reasoning_content")
                    or delta.get("reasoning")
                    or delta.get("content")
                    or ""
                )
                if not text:
                    continue
                now_ns = time.monotonic_ns()
                if first_text_ns is None:
                    first_text_ns = now_ns
                    controls.append(control(args.unitrace, "resume", args.session))
                chunk_times_ns.append(now_ns)
                text_parts.append(text)
                if len(chunk_times_ns) == args.trace_chunks + 1:
                    controls.append(control(args.unitrace, "pause", args.session))
                    paused = True

    request_ended_ns = time.monotonic_ns()
    if first_text_ns is None:
        raise RuntimeError("request produced no streamed text")
    if not paused:
        controls.append(control(args.unitrace, "pause", args.session))
    controls.append(control(args.unitrace, "stop", args.session))

    text = "".join(text_parts)
    intervals_ms = [
        (right - left) / 1e6
        for left, right in zip(chunk_times_ns, chunk_times_ns[1:], strict=False)
    ]
    trace_intervals_ms = intervals_ms[: args.trace_chunks]
    result = {
        "classification": "diagnostic_profiler_crosscheck",
        "one_active_generation": True,
        "request": {
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "prompt": prompt,
            "max_tokens": args.max_tokens,
            "request_started_monotonic_ns": request_started_ns,
            "first_text_monotonic_ns": first_text_ns,
            "request_ended_monotonic_ns": request_ended_ns,
        },
        "trace_window": {
            "requested_intervals": args.trace_chunks,
            "captured_intervals": len(trace_intervals_ms),
            "interarrival_ms": trace_intervals_ms,
            "mean_interarrival_ms": sum(trace_intervals_ms) / len(trace_intervals_ms),
            "window_ms": sum(trace_intervals_ms),
        },
        "stream": {
            "text_chunks": len(chunk_times_ns),
            "all_interarrival_ms": intervals_ms,
            "usage": usage,
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "text": text,
        },
        "unitrace_controls": controls,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
