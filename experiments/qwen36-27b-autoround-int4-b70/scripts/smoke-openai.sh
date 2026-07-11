#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
mkdir -p "$repo_dir/data"

BASE_URL="${BASE_URL:-http://127.0.0.1:19410/v1}"
MODEL="${MODEL:-qwen36-27b-int4-autoround}"
ENABLE_THINKING="${ENABLE_THINKING:-0}"
MAX_TOKENS="${MAX_TOKENS:-64}"
OUT="${OUT:-$repo_dir/data/qwen36-27b-autoround-openai-smoke-$(date -u +%Y%m%dT%H%M%SZ).json}"

BASE_URL="$BASE_URL" MODEL="$MODEL" ENABLE_THINKING="$ENABLE_THINKING" MAX_TOKENS="$MAX_TOKENS" OUT="$OUT" python3 - <<'PY'
import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path

base_url = os.environ["BASE_URL"].rstrip("/")
model = os.environ["MODEL"]
enable_thinking = os.environ["ENABLE_THINKING"].strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
max_tokens = int(os.environ["MAX_TOKENS"])
out = Path(os.environ["OUT"])

def request_json(method, path, payload=None, timeout=120):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        base_url + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

models = request_json("GET", "/models", timeout=30)
prompt = "Return exactly this JSON object and no markdown: {\"answer\": 42, \"unit\": \"widgets\"}"
payload = {
    "model": model,
    "messages": [
        {"role": "system", "content": "You are a precise assistant."},
        {"role": "user", "content": prompt},
    ],
    "chat_template_kwargs": {"enable_thinking": enable_thinking},
    "temperature": 0,
    "max_tokens": max_tokens,
}
t0 = time.perf_counter()
completion = request_json("POST", "/chat/completions", payload, timeout=180)
elapsed = time.perf_counter() - t0
choice = completion["choices"][0]
message = choice.get("message", {})
content = message.get("content")
reasoning = message.get("reasoning")
text = content if isinstance(content, str) else ""
reasoning_text = reasoning if isinstance(reasoning, str) else ""
visible_text = text or reasoning_text
usage = completion.get("usage", {})
cached = (
    usage.get("prompt_tokens_details", {}) or {}
).get("cached_tokens")
visible = any(not ch.isspace() for ch in visible_text)
bad_controls = [
    ch for ch in visible_text
    if (ord(ch) < 32 and ch not in "\n\r\t")
]
summary = {
    "base_url": base_url,
    "model": model,
    "models_response": models,
    "enable_thinking": enable_thinking,
    "max_tokens": max_tokens,
    "prompt": prompt,
    "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
    "content": text,
    "reasoning": reasoning_text,
    "finish_reason": choice.get("finish_reason"),
    "output_sha256": hashlib.sha256(text.encode()).hexdigest(),
    "reasoning_sha256": hashlib.sha256(reasoning_text.encode()).hexdigest(),
    "elapsed_s": elapsed,
    "usage": usage,
    "cached_tokens": cached,
    "pass": bool(text and visible and not bad_controls),
    "failure_reasons": [],
}
if not text:
    summary["failure_reasons"].append("empty_content")
if not visible:
    summary["failure_reasons"].append("no_visible_text")
if enable_thinking and reasoning_text and not text:
    summary["failure_reasons"].append("thinking_only_no_content")
if bad_controls:
    summary["failure_reasons"].append("control_chars")
if cached not in (None, 0):
    summary["failure_reasons"].append("cached_tokens_nonzero")
out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(out)
print(json.dumps({
    "pass": summary["pass"],
    "elapsed_s": elapsed,
    "cached_tokens": cached,
    "finish_reason": summary["finish_reason"],
    "content_preview": text[:200],
    "reasoning_preview": reasoning_text[:200],
    "output_preview": text[:200],
}, indent=2, sort_keys=True))
PY
