#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
lane="${repo}/experiments/qwen38-flash-next-fp8-b70"
supervisor="${lane}/tools/supervise-tp4-mtp0-16512-fresh-a4.sh"
harness="${repo}/scripts/bench-openai-long-context-suite.py"
suite="${lane}/fixtures/long-context-semantic-16k-v1.json"
reference="${lane}/data/20260828-tp4-mtp0-16k-semantic-a3-same-server-corruption.json"
python=/home/steve/.venvs/vllm-xpu/bin/python
campaign=qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-16512-r1
attempt=5
port=19677
state=/tmp/q38-mtp0-16512-fresh-a4
stop_file="${state}.stop"
run_dir="/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/${campaign}-attempt${attempt}"
base_url="http://127.0.0.1:${port}"
model=qwen38-flash-next-fp8-tp4
expected_supervisor=a968f6647e3e8148602e417dce309b2ba1b8e9b4d849da42e51ef8cb16ee780c
expected_harness=f3bbf3369152a55aa0c9acc8bbad7ff15db2d4d694f03cb5ed275efde7f99459
expected_suite=61d94377bcb5a8252d4796d27ab0a16714c4c603bb20e8f5533641cb9e982e6a
expected_reference=60898a11ab90238e11bc90b73038de5d00c2e72b1b185cc3851989371c429ef0
success=0

write_atomic() {
  local path=$1 value=$2 tmp
  tmp="${path}.tmp.$$"
  printf '%s\n' "$value" >"$tmp"
  mv "$tmp" "$path"
}

write_url() {
  local url=$1 path=$2 tmp
  tmp="${path}.tmp.$$"
  curl --connect-timeout 5 --max-time 20 -fsS "$url" >"$tmp"
  mv "$tmp" "$path"
}

resolve_proc_script() {
  local pid=$1 candidate cwd
  local -a argv
  mapfile -d '' -t argv <"/proc/${pid}/cmdline"
  (( ${#argv[@]} >= 1 )) || return 1
  case "${argv[0]}" in
    bash|*/bash)
      (( ${#argv[@]} >= 2 )) || return 1
      candidate=${argv[1]}
      ;;
    *) candidate=${argv[0]} ;;
  esac
  if [[ "$candidate" != /* ]]; then
    cwd=$(readlink -f "/proc/${pid}/cwd") || return 1
    candidate="${cwd}/${candidate}"
  fi
  realpath -e -- "$candidate"
}

signal_stop() {
  local rc=$?
  if (( success == 0 )) && [[ ! -e "$stop_file" ]]; then
    write_atomic "$stop_file" "STOP after failed MTP0 active-16K fresh-server A4"
  fi
  exit "$rc"
}
trap signal_stop EXIT

[[ $# == 0 ]] || { printf 'FAIL: client takes no arguments\n' >&2; exit 2; }
[[ -d "$run_dir" ]] || { printf 'FAIL: run directory missing\n' >&2; exit 1; }
[[ "$(sha256sum "$supervisor" | cut -d' ' -f1)" == "$expected_supervisor" ]]
[[ "$(sha256sum "$harness" | cut -d' ' -f1)" == "$expected_harness" ]]
[[ "$(sha256sum "$suite" | cut -d' ' -f1)" == "$expected_suite" ]]
[[ "$(sha256sum "$reference" | cut -d' ' -f1)" == "$expected_reference" ]]
supervisor_pid=$(cat "${state}.pid" 2>/dev/null || true)
server_pid=$(cat "${run_dir}/server.pid" 2>/dev/null || true)
recorded_server_pid=$(cat "${state}.server.pid" 2>/dev/null || true)
[[ "$supervisor_pid" =~ ^[1-9][0-9]*$ && -e "/proc/${supervisor_pid}" ]]
[[ "$server_pid" =~ ^[1-9][0-9]*$ && "$server_pid" == "$recorded_server_pid" && -e "/proc/${server_pid}" ]]
supervisor_script=$(resolve_proc_script "$supervisor_pid")
[[ "$supervisor_script" == "$supervisor" ]] || { printf 'FAIL: supervisor identity mismatch\n' >&2; exit 1; }
server_command=$(tr '\0' ' ' <"/proc/${server_pid}/cmdline")
[[ "$server_command" == *"vllm serve /mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8"* && \
   "$server_command" == *"--port ${port}"* ]] || { printf 'FAIL: server identity mismatch\n' >&2; exit 1; }
[[ ! -e "$stop_file" ]] || { printf 'FAIL: stop sentinel already exists\n' >&2; exit 1; }

for artifact in health-before-semantic.json models-before-semantic.json \
  metrics-before-semantic.prom metrics-after-semantic.prom \
  semantic-16k-fresh.json semantic-16k-fresh.log fresh-server-adjudication.json; do
  [[ ! -e "${run_dir}/${artifact}" ]] || {
    printf 'FAIL: refusing to overwrite %s\n' "$artifact" >&2
    exit 1
  }
done

write_url "${base_url}/health" "${run_dir}/health-before-semantic.json"
write_url "${base_url}/v1/models" "${run_dir}/models-before-semantic.json"
jq -e --arg model "$model" '.data | any(.id == $model)' \
  "${run_dir}/models-before-semantic.json" >/dev/null
write_url "${base_url}/metrics" "${run_dir}/metrics-before-semantic.prom"

"$python" - "${run_dir}/metrics-before-semantic.prom" "${run_dir}/server.log" <<'PY'
import pathlib
import re
import sys

metrics = pathlib.Path(sys.argv[1]).read_text()
server_log = pathlib.Path(sys.argv[2]).read_text(errors="replace")
line = next((line for line in metrics.splitlines() if line.startswith("vllm:cache_config_info{")), None)
if line is None:
    raise RuntimeError("cache_config_info is absent")
labels = dict(re.findall(r'(\w+)="([^"]*)"', line))
required = {
    "kv_cache_memory_bytes": "358465536",
    "num_gpu_blocks": "33",
    "enable_prefix_caching": "False",
}
for key, expected in required.items():
    if labels.get(key) != expected:
        raise RuntimeError(f"{key}={labels.get(key)!r}, expected {expected!r}")
if int(labels.get("kv_cache_size_tokens", "0")) < 16512:
    raise RuntimeError("reported cache capacity is below 16512")
if server_log.count("Total CPU offloaded parameters: 12.22") != 4:
    raise RuntimeError("exact four-rank 12.22-GiB offload receipt is absent")
PY

timeout --signal=TERM --kill-after=10s 1810s \
  "$python" "$harness" \
    --base-url "$base_url" --model "$model" --suite "$suite" \
    --case-id q38-fn-16k-middle-v1 --max-tokens 128 --seed 1 \
    --timeout 1800 --return-token-ids \
    --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false}}' \
    --out "${run_dir}/semantic-16k-fresh.json" >"${run_dir}/semantic-16k-fresh.log" 2>&1

write_url "${base_url}/metrics" "${run_dir}/metrics-after-semantic.prom"

"$python" - "$reference" "${run_dir}/semantic-16k-fresh.json" \
  "${run_dir}/fresh-server-adjudication.json" "$server_pid" <<'PY'
import hashlib
import json
import os
import pathlib
import sys

reference_path = pathlib.Path(sys.argv[1])
fresh_path = pathlib.Path(sys.argv[2])
destination = pathlib.Path(sys.argv[3])
server_pid = int(sys.argv[4])
assert server_pid != 23943
reference = json.loads(reference_path.read_text())
fresh = json.loads(fresh_path.read_text())
row = fresh["rows"][0]
baseline = reference["request_1"]
assert fresh["summary"]["long_context_gate"]["passed"] is True
assert row["validation"]["pass"] is True
assert 16000 <= row["prompt_tokens"] <= 16400
assert row["prompt_tokens"] == baseline["prompt_tokens"]
assert row["cached_tokens"] == 0
assert row["token_ids_complete"] is True
assert row["usage"]["prompt_tokens"] + row["usage"]["completion_tokens"] <= 16512
assert row["sha256"] == baseline["text_sha256"]
assert row["token_ids_sha256"] == baseline["token_ids_sha256"]
receipt = {
    "status": "passed",
    "attempt": 5,
    "fresh_server_pid": server_pid,
    "a3_server_pid": 23943,
    "semantic_requests": 1,
    "semantic_passes": 1,
    "cached_tokens_all_zero": True,
    "fresh_server_matches_a3_request_1": True,
    "same_server_repeat": "failed-in-a3-and-not-erased",
    "prompt_tokens": row["prompt_tokens"],
    "completion_tokens": row["completion_tokens"],
    "prompt_sha256": row["prompt_sha256"],
    "text_sha256": row["sha256"],
    "token_ids_sha256": row["token_ids_sha256"],
    "tok_s_after_ttft_diagnostic_only": row["tok_s_after_ttft"],
    "ttft_s": row["ttft_s"],
    "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
    "matrix_classification": "grade-d-quarantined-capability",
    "context_quality_credit": False,
    "speed_credit": False,
    "deployment_credit": False,
}
temporary = destination.with_name(f"{destination.name}.tmp.{os.getpid()}")
temporary.write_text(json.dumps(receipt, indent=2) + "\n")
os.replace(temporary, destination)
PY

success=1
write_atomic "$stop_file" "STOP after passed MTP0 active-16K fresh-server A4"
trap - EXIT
