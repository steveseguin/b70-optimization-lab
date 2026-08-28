#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
supervisor="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/supervise-tp4-mtp0-16512.sh"
state=/tmp/q38-mtp0-16512-supervisor
stop_file="${state}.stop"
run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-16512-r1-attempt1
harness="${repo}/scripts/bench-openai-token-depth-suite.py"
fixture="${repo}/data/qwen27-exact-depth/qwen38-flash-next-bcd9f01-exact-depth-v1.json"
python=/home/steve/.venvs/vllm-xpu/bin/python
base_url=http://127.0.0.1:19673
model=qwen38-flash-next-fp8-tp4
output="${run_dir}/exact-depth-16k-o128.json"
expected_harness=8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067
expected_fixture=c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d
expected_prompt=b7acffcd09d9466fd8382a72248f5447c59f4ee18572aff243ef29ee889883e7
expected_payload=b555e47c199a9166f23ba60520e6714a11fd8a31e36053db75c12863ac01c103
expected_supervisor=85181bc89f55c67e70a0eff8b74485d05d9182fa4ab93ff1ef739e317ad79ee5
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

signal_stop() {
  local rc=$?
  if (( success == 0 )) && [[ ! -e "$stop_file" ]]; then
    write_atomic "$stop_file" 'STOP after failed MTP0 active-16K request'
  fi
  exit "$rc"
}
trap signal_stop EXIT

[[ $# == 0 ]] || { printf 'FAIL: client takes no arguments\n' >&2; exit 2; }
[[ -d "$run_dir" ]] || { printf 'FAIL: run directory missing\n' >&2; exit 1; }
[[ "$(sha256sum "$harness" | cut -d' ' -f1)" == "$expected_harness" ]] || { printf 'FAIL: harness hash mismatch\n' >&2; exit 1; }
[[ "$(sha256sum "$fixture" | cut -d' ' -f1)" == "$expected_fixture" ]] || { printf 'FAIL: fixture hash mismatch\n' >&2; exit 1; }
[[ "$(sha256sum "$supervisor" | cut -d' ' -f1)" == "$expected_supervisor" ]] || { printf 'FAIL: supervisor hash mismatch\n' >&2; exit 1; }
supervisor_pid=$(cat "${state}.pid" 2>/dev/null || true)
server_pid=$(cat "${run_dir}/server.pid" 2>/dev/null || true)
recorded_server_pid=$(cat "${state}.server.pid" 2>/dev/null || true)
[[ "$supervisor_pid" =~ ^[1-9][0-9]*$ && -e "/proc/${supervisor_pid}" ]] || { printf 'FAIL: live supervisor is absent\n' >&2; exit 1; }
[[ "$server_pid" =~ ^[1-9][0-9]*$ && "$server_pid" == "$recorded_server_pid" && -e "/proc/${server_pid}" ]] || { printf 'FAIL: owned live server is absent\n' >&2; exit 1; }
supervisor_command=$(tr '\0' ' ' <"/proc/${supervisor_pid}/cmdline")
server_command=$(tr '\0' ' ' <"/proc/${server_pid}/cmdline")
[[ "$supervisor_command" == *"${supervisor}"* ]] || { printf 'FAIL: supervisor command identity mismatch\n' >&2; exit 1; }
[[ "$server_command" == *"vllm serve /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8"* && \
   "$server_command" == *"--port 19673"* ]] || { printf 'FAIL: server command identity mismatch\n' >&2; exit 1; }
for artifact in health-before-request.json models-before-request.json \
  metrics-before-request.prom exact-depth-16k-o128.json client-request.log \
  client-request.rc metrics-after-request.prom request1-adjudication.json \
  request1-classified.txt; do
  [[ ! -e "${run_dir}/${artifact}" ]] || { printf 'FAIL: refusing to overwrite %s\n' "$artifact" >&2; exit 1; }
done
[[ ! -e "$stop_file" ]] || { printf 'FAIL: stop sentinel already exists\n' >&2; exit 1; }

write_url "${base_url}/health" "${run_dir}/health-before-request.json"
write_url "${base_url}/v1/models" "${run_dir}/models-before-request.json"
jq -e --arg model "$model" '.data | any(.id == $model)' \
  "${run_dir}/models-before-request.json" >/dev/null
write_url "${base_url}/metrics" "${run_dir}/metrics-before-request.prom"

"$python" - "${run_dir}/metrics-before-request.prom" "${run_dir}/server.log" <<'PY'
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
capacity = int(labels.get("kv_cache_size_tokens", "0"))
if capacity < 16512:
    raise RuntimeError(f"reported cache capacity {capacity} is below 16512")
if server_log.count("Total CPU offloaded parameters: 12.22") != 4:
    raise RuntimeError("exact four-rank 12.22-GiB offload receipt is absent")
PY

set +e
timeout --signal=TERM --kill-after=10s 1810s \
  "$python" "$harness" --execute --fixture "$fixture" --depth 16384 \
  --context-capacity 16512 --base-url "$base_url" --model "$model" \
  --response-adapter vllm --timeout 1800 --out "$output" \
  >"${run_dir}/client-request.log" 2>&1
rc=$?
set -e
write_atomic "${run_dir}/client-request.rc" "$rc"
(( rc == 0 )) || exit "$rc"

write_url "${base_url}/metrics" "${run_dir}/metrics-after-request.prom"
"$python" - "$output" "${run_dir}/request1-adjudication.json" \
  "$expected_prompt" "$expected_payload" <<'PY'
import json
import os
import pathlib
import sys

candidate_path, output_path, expected_prompt_hash, expected_payload_hash = sys.argv[1:]
candidate = json.loads(pathlib.Path(candidate_path).read_text())
if candidate.get("status") != "passed" or candidate.get("gate", {}).get("passed") is not True:
    raise RuntimeError("generic exact-depth gate did not pass")
checks = candidate.get("gate", {}).get("checks", {})
if len(checks) != 25 or not all(checks.values()):
    raise RuntimeError(f"expected all 25 generic checks to pass: {checks!r}")
if candidate.get("request", {}).get("prompt_token_ids_sha256") != expected_prompt_hash:
    raise RuntimeError("frozen request prompt hash changed")
if candidate.get("request", {}).get("request_payload_sha256") != expected_payload_hash:
    raise RuntimeError("frozen request payload hash changed")
response = candidate["response"]
usage = response["usage"]
if usage.get("prompt_tokens") != 16384 or usage.get("completion_tokens") != 128 or usage.get("total_tokens") != 16512:
    raise RuntimeError(f"unexpected usage: {usage!r}")
if usage.get("prompt_tokens_details", {}).get("cached_tokens") != 0:
    raise RuntimeError("cache reuse is nonzero")
if response.get("finish_reasons") != ["length"] or len(response.get("token_ids", [])) != 128:
    raise RuntimeError("output length/finish gate failed")
adjudication = {
    "status": "quarantined-generic-exact-depth-only",
    "generic_exact_depth_gate": "passed",
    "generic_check_count": 25,
    "prompt_tokens": 16384,
    "completion_tokens": 128,
    "cached_tokens": 0,
    "candidate_output_token_ids_sha256": response["output_token_ids_sha256"],
    "candidate_text_sha256": response["text_sha256"],
    "repeat_gate": "absent",
    "semantic_gate": "absent",
    "diagnostic_rate_tok_s": candidate["metric_window"]["conventional_99_interval_tok_s"],
    "diagnostic_ttft_s": candidate["metric_window"]["time_to_first_token_s"],
    "speed_credit": False,
    "quality_credit": False,
    "deployment_credit": False,
    "matrix_classification": "grade-d-quarantined-capability",
    "interpretation": "One current-source MTP0 exact-16K request completed generic structural gates; no semantic or repeat authority exists at this depth.",
}
destination = pathlib.Path(output_path)
temporary = destination.with_name(f"{destination.name}.tmp.{os.getpid()}")
temporary.write_text(json.dumps(adjudication, indent=2) + "\n")
os.replace(temporary, destination)
PY

write_atomic "${run_dir}/request1-classified.txt" \
  'QUARANTINE generic exact-16K MTP0 cache-zero pass; semantic and repeat gates absent'
success=1
write_atomic "$stop_file" 'STOP after completed MTP0 active-16K classification'
trap - EXIT
