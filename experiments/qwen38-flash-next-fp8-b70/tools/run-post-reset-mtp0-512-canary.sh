#!/usr/bin/env bash
set -Eeuo pipefail

run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/post-reset-recovery-qualification-20260828-stage-b/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-512-r1-attempt28
state=/tmp/q38-post-reset-mtp0-512-supervisor
python=/home/steve/.venvs/vllm-xpu/bin/python
base_url=http://127.0.0.1:19666
model=qwen38-flash-next-fp8-tp4
raw_path="${run_dir}/post-reset-canary-raw-response.json"
receipt_path="${run_dir}/post-reset-canary.json"

write_url() {
  local url=$1 path=$2 tmp
  tmp="${path}.tmp.$$"
  curl --connect-timeout 5 --max-time 15 -fsS "$url" >"$tmp"
  mv "$tmp" "$path"
}

[[ $# == 0 ]] || { printf 'FAIL: canary takes no arguments\n' >&2; exit 2; }
[[ -d "$run_dir" ]] || { printf 'FAIL: Stage-B run directory is absent\n' >&2; exit 1; }
for artifact in health-before-canary.json models-before-canary.json \
  metrics-before-canary.prom post-reset-canary-raw-response.json \
  post-reset-canary.json metrics-after-canary.prom health-after-canary.json \
  post-reset-canary-gates-passed.txt; do
  [[ ! -e "${run_dir}/${artifact}" ]] || {
    printf 'FAIL: refusing to overwrite canary artifact %s\n' "$artifact" >&2
    exit 1
  }
done
for pid_file in "${state}.pid" "${state}.child.pid" "${state}.launcher.pid" \
  "${run_dir}/server.pid"; do
  pid=$(cat "$pid_file" 2>/dev/null || true)
  [[ "$pid" =~ ^[1-9][0-9]*$ && -e "/proc/${pid}" ]] || {
    printf 'FAIL: expected live Stage-B owner is absent: %s\n' "$pid_file" >&2
    exit 1
  }
done
server_pid=$(cat "${run_dir}/server.pid")
server_command=$(tr '\0' ' ' <"/proc/${server_pid}/cmdline")
[[ "$server_command" == *"vllm serve /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8"* && \
   "$server_command" == *"--port 19666"* ]] || {
  printf 'FAIL: server PID does not own the frozen Stage-B identity\n' >&2
  exit 1
}

write_url "${base_url}/health" "${run_dir}/health-before-canary.json"
write_url "${base_url}/v1/models" "${run_dir}/models-before-canary.json"
jq -e --arg model "$model" '.data | any(.id == $model)' \
  "${run_dir}/models-before-canary.json" >/dev/null || {
  printf 'FAIL: model endpoint does not expose the frozen served identity\n' >&2
  exit 1
}
write_url "${base_url}/metrics" "${run_dir}/metrics-before-canary.prom"

unset PYTHONOPTIMIZE
"$python" - "$base_url" "$model" "$raw_path" "$receipt_path" <<'PY'
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

base_url, model, raw_path, receipt_path = sys.argv[1:]

def atomic_json(path, value):
    destination = pathlib.Path(path)
    temporary = destination.with_name(f"{destination.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    os.replace(temporary, destination)

def require(condition, detail):
    if not condition:
        raise RuntimeError(detail)

payload = {
    "model": model,
    "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
    "chat_template_kwargs": {"enable_thinking": False},
    "temperature": 0,
    "top_p": 1.0,
    "seed": 20260609,
    "max_tokens": 8,
    "stream": False,
}
request = urllib.request.Request(
    f"{base_url}/v1/chat/completions",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json", "x-request-id": "q38-post-reset-mtp0-512-canary"},
    method="POST",
)
started = time.perf_counter()
try:
    with urllib.request.urlopen(request, timeout=180) as response:
        status = response.status
        raw_body = response.read()
except urllib.error.HTTPError as error:
    status = error.code
    raw_body = error.read()
except Exception as error:
    elapsed = time.perf_counter() - started
    atomic_json(raw_path, {
        "http_status": None,
        "elapsed_s_diagnostic_only": elapsed,
        "transport_error_type": type(error).__name__,
        "transport_error": str(error),
    })
    raise
elapsed = time.perf_counter() - started
decoded = raw_body.decode(errors="replace")
try:
    result = json.loads(decoded)
except json.JSONDecodeError:
    result = None
atomic_json(raw_path, {
    "http_status": status,
    "elapsed_s_diagnostic_only": elapsed,
    "response": result if result is not None else decoded,
})

require(status == 200, f"HTTP status {status}")
require(isinstance(result, dict), "response is not a JSON object")
choices = result.get("choices")
require(isinstance(choices, list) and len(choices) == 1, f"choices={choices!r}")
choice = choices[0]
content = (choice.get("message") or {}).get("content") or ""
normalized = content.strip()
usage = result.get("usage") or {}
prompt_details = usage.get("prompt_tokens_details") or {}
normalized_sha256 = hashlib.sha256(normalized.encode()).hexdigest()
require(result.get("model") == model, f"model={result.get('model')!r}")
require(choice.get("finish_reason") == "stop", f"choice={choice!r}")
require(normalized == "OK", f"normalized={normalized!r}")
require(normalized_sha256 == "565339bc4d33d72817b583024112eb7f5cdf3e5eef0252d6ec1b9c9a94e12bb3", normalized_sha256)
require(usage.get("prompt_tokens") == 17, f"usage={usage!r}")
require(usage.get("completion_tokens") == 2, f"usage={usage!r}")
require(usage.get("total_tokens") == 19, f"usage={usage!r}")
require(prompt_details.get("cached_tokens") == 0, f"prompt_details={prompt_details!r}")
require(prompt_details.get("created_cache_tokens") == 0, f"prompt_details={prompt_details!r}")

atomic_json(receipt_path, {
    "status": "passed",
    "model": result.get("model"),
    "finish_reason": choice.get("finish_reason"),
    "normalized": normalized,
    "normalized_sha256": normalized_sha256,
    "usage": usage,
    "elapsed_s_diagnostic_only": elapsed,
    "speed_credit": False,
    "quality_credit": False,
    "matrix_credit": False,
    "raw_response_path": raw_path,
})
PY

write_url "${base_url}/metrics" "${run_dir}/metrics-after-canary.prom"
write_url "${base_url}/health" "${run_dir}/health-after-canary.json"
tmp="${run_dir}/post-reset-canary-gates-passed.txt.tmp.$$"
printf '%s\n' 'PASS exact OK hash usage cache-zero normal-stop recovery canary' >"$tmp"
mv "$tmp" "${run_dir}/post-reset-canary-gates-passed.txt"
