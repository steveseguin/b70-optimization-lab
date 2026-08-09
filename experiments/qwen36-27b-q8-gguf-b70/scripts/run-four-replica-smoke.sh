#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LANE="$ROOT/experiments/qwen36-27b-q8-gguf-b70"
MODEL_MANIFEST="$LANE/model-manifest.json"
RUNTIME_MANIFEST="$LANE/runtime-manifest.json"

MODEL="${MODEL:-/mnt/usb-models/models/qwen36-27b-q8-gguf/Qwen3.6-27B-Q8_0.gguf}"
LLAMA_SERVER="${LLAMA_SERVER:-/dev/shm/llama.cpp-pr19-15586/build-sycl/bin/llama-server}"
BASE_PORT="${BASE_PORT:-19460}"
CTX_SIZE="${CTX_SIZE:-4096}"
GPU_IDLE_MAX_MIB="${GPU_IDLE_MAX_MIB:-256}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}"
SEALED_ORACLE="${SEALED_ORACLE:-/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/qwen36-27b-q8_0-f16kv-short-dnn0-exact-20260808T232639Z/exact-tokens.json}"
SEALED_ORACLE_SHA256="e4477808823cdf9bb182d5abc4788cee216011a0195cf49bf03a7bda35f5dbcc"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${RUN_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/qwen36-27b-q8_0-four-replica-smoke-${STAMP}}"

if [[ ! "$BASE_PORT" =~ ^[0-9]+$ ]] || (( BASE_PORT < 1024 || BASE_PORT > 65532 )); then
  echo "BASE_PORT must leave four valid consecutive ports" >&2
  exit 2
fi
if [[ "$CTX_SIZE" != "4096" ]]; then
  echo "the four-replica functional smoke is sealed to CTX_SIZE=4096" >&2
  exit 2
fi
if [[ ! "$GPU_IDLE_MAX_MIB" =~ ^[0-9]+$ ]]; then
  echo "GPU_IDLE_MAX_MIB must be a nonnegative integer" >&2
  exit 2
fi
if [[ ! "$READINESS_TIMEOUT_S" =~ ^[0-9]+$ ]] || (( READINESS_TIMEOUT_S <= 0 )); then
  echo "READINESS_TIMEOUT_S must be a positive integer" >&2
  exit 2
fi
if [[ -e "$RUN_DIR" ]]; then
  echo "RUN_DIR already exists: $RUN_DIR" >&2
  exit 2
fi

EXPECTED_MODEL_SHA256="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["sha256"])' "$MODEL_MANIFEST")"
EXPECTED_MODEL_SIZE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["size_bytes"])' "$MODEL_MANIFEST")"
EXPECTED_RUNTIME_SHA256="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["llama_server_sha256"])' "$RUNTIME_MANIFEST")"

if [[ ! -f "$MODEL" ]] || [[ "$(stat -c %s "$MODEL")" != "$EXPECTED_MODEL_SIZE" ]]; then
  echo "model is missing or has the wrong byte size: $MODEL" >&2
  exit 2
fi
if [[ ! -x "$LLAMA_SERVER" ]]; then
  echo "llama-server not executable: $LLAMA_SERVER" >&2
  exit 2
fi
if [[ ! -f "$SEALED_ORACLE" ]]; then
  echo "sealed DNN-off oracle not found: $SEALED_ORACLE" >&2
  exit 2
fi

for required_command in awk curl find grep journalctl jq python3 sha256sum sort ss timeout xargs xpu-smi; do
  command -v "$required_command" >/dev/null 2>&1 || {
    echo "required command not found: $required_command" >&2
    exit 2
  }
done

mkdir -p "$RUN_DIR"
START_EPOCH="$(date +%s)"
declare -a SERVER_PIDS=()
declare -a CAPTURE_PIDS=()
declare -a PRE_GPU_MIB=()
CLEANUP_FORCED=0

check_host_memory() {
  local label="$1"
  local available_kib
  local swap_free_kib

  available_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
  swap_free_kib="$(awk '/^SwapFree:/ {print $2}' /proc/meminfo)"
  {
    echo "MemAvailable_kib=$available_kib"
    echo "SwapFree_kib=$swap_free_kib"
  } > "$RUN_DIR/host-memory-${label}.txt"
  if (( available_kib < 8388608 )) ||
     (( available_kib < 16777216 && swap_free_kib < 4194304 )); then
    echo "host-memory guard failed at $label: MemAvailable=$available_kib KiB SwapFree=$swap_free_kib KiB" >&2
    return 1
  fi
}

cleanup_servers() {
  local pid
  local deadline
  local any_alive

  set +e
  for pid in "${CAPTURE_PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null
    fi
  done
  deadline=$((SECONDS + 10))
  while (( SECONDS < deadline )); do
    any_alive=0
    for pid in "${CAPTURE_PIDS[@]}"; do
      if kill -0 "$pid" 2>/dev/null; then
        any_alive=1
      fi
    done
    (( any_alive == 0 )) && break
    sleep 1
  done
  for pid in "${CAPTURE_PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill -KILL "$pid" 2>/dev/null
    fi
    wait "$pid" 2>/dev/null
  done
  for pid in "${SERVER_PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null
    fi
  done
  deadline=$((SECONDS + 45))
  while (( SECONDS < deadline )); do
    any_alive=0
    for pid in "${SERVER_PIDS[@]}"; do
      if kill -0 "$pid" 2>/dev/null; then
        any_alive=1
      fi
    done
    (( any_alive == 0 )) && break
    sleep 1
  done
  for pid in "${SERVER_PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      CLEANUP_FORCED=1
      kill -KILL "$pid" 2>/dev/null
    fi
    wait "$pid" 2>/dev/null
  done
  set -e
}

finish() {
  local original_status=$?
  local final_status
  local gpu
  local port
  local final_mib
  local pre_mib

  trap - EXIT INT TERM
  final_status=$original_status
  cleanup_servers
  (( CLEANUP_FORCED == 0 )) || final_status=1

  journalctl -k --since "@$START_EPOCH" --no-pager 2>/dev/null |
    grep -Ei 'xe.*(reset|wedg|fault|hang|timedout|device lost)|GuC.*reset|Fault response|VM.*fault|PCIe.*AER|UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST' \
      > "$RUN_DIR/device-error-scan.txt" || true
  [[ ! -s "$RUN_DIR/device-error-scan.txt" ]] || final_status=1

  grep -EHi 'UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST|out of memory|segmentation fault|core dumped|Aborted' \
    "$RUN_DIR"/gpu*/server.stdout.log > "$RUN_DIR/server-error-scan.txt" 2>/dev/null || true
  [[ ! -s "$RUN_DIR/server-error-scan.txt" ]] || final_status=1
  check_host_memory final || final_status=1

  {
    echo "forced_kill=$CLEANUP_FORCED"
    for gpu in 0 1 2 3; do
      port=$((BASE_PORT + gpu))
      mkdir -p "$RUN_DIR/gpu${gpu}"
      if ss -H -ltn "sport = :$port" | grep -q .; then
        echo "gpu${gpu}_port_closed=0"
        final_status=1
      else
        echo "gpu${gpu}_port_closed=1"
      fi
      timeout 20 xpu-smi stats -d "$gpu" > "$RUN_DIR/gpu${gpu}/xpu-smi-final.txt" 2>&1 || true
      final_mib="$(awk -F '|' '/GPU Memory Used/{gsub(/[^0-9.]/, "", $3); print int($3); exit}' "$RUN_DIR/gpu${gpu}/xpu-smi-final.txt" 2>/dev/null || true)"
      pre_mib="${PRE_GPU_MIB[gpu]:-}"
      if [[ -n "$final_mib" && -n "$pre_mib" ]] && (( final_mib <= pre_mib + GPU_IDLE_MAX_MIB )); then
        echo "gpu${gpu}_vram_returned=1 pre_mib=$pre_mib final_mib=$final_mib"
      else
        echo "gpu${gpu}_vram_returned=0 pre_mib=${pre_mib:-unknown} final_mib=${final_mib:-unknown}"
        final_status=1
      fi
    done
  } > "$RUN_DIR/cleanup-status.txt"

  printf 'original_status=%s\nfinal_status=%s\n' "$original_status" "$final_status" > "$RUN_DIR/exit-status.txt"
  if (( final_status == 0 )); then
    printf 'PASS\n' > "$RUN_DIR/run-status.txt"
  else
    printf 'FAIL\n' > "$RUN_DIR/run-status.txt"
  fi
  find "$RUN_DIR" -type f ! -name artifacts.sha256 -print0 |
    sort -z | xargs -0 -r sha256sum > "$RUN_DIR/artifacts.sha256"
  exit "$final_status"
}
trap finish EXIT
trap 'exit 130' INT TERM

printf '%s  %s\n' "$EXPECTED_MODEL_SHA256" "$MODEL" | sha256sum -c - |
  tee "$RUN_DIR/model-sha256-check.txt"
printf '%s  %s\n' "$EXPECTED_RUNTIME_SHA256" "$LLAMA_SERVER" | sha256sum -c - |
  tee "$RUN_DIR/runtime-sha256-check.txt"
printf '%s  %s\n' "$SEALED_ORACLE_SHA256" "$SEALED_ORACLE" | sha256sum -c - |
  tee "$RUN_DIR/sealed-oracle-sha256-check.txt"

xpu-smi discovery -j > "$RUN_DIR/xpu-smi-discovery.json"
jq -e '
  [.device_list[] |
    select(.device_function_type == "physical" and (.device_name | contains("Arc(TM) Pro B70"))) |
    {device_id, pci_bdf_address, uuid, device_name}]
  | length == 4
    and ([.[].device_id] | sort) == [0, 1, 2, 3]
    and ([.[].pci_bdf_address] | unique | length) == 4
    and ([.[].uuid] | unique | length) == 4
' "$RUN_DIR/xpu-smi-discovery.json" >/dev/null
jq '[.device_list[] |
  select(.device_function_type == "physical" and (.device_name | contains("Arc(TM) Pro B70"))) |
  {device_id, pci_bdf_address, uuid, device_name}]
  | sort_by(.device_id)' "$RUN_DIR/xpu-smi-discovery.json" > "$RUN_DIR/gpu-identities.json"
uname -a > "$RUN_DIR/uname.txt"
check_host_memory preflight

for gpu in 0 1 2 3; do
  port=$((BASE_PORT + gpu))
  if ss -H -ltn "sport = :$port" | grep -q .; then
    echo "port already in use: $port" >&2
    exit 2
  fi
  mkdir -p "$RUN_DIR/gpu${gpu}"
  timeout 20 xpu-smi stats -d "$gpu" > "$RUN_DIR/gpu${gpu}/xpu-smi-before.txt"
  PRE_GPU_MIB[gpu]="$(awk -F '|' '/GPU Memory Used/{gsub(/[^0-9.]/, "", $3); print int($3); exit}' "$RUN_DIR/gpu${gpu}/xpu-smi-before.txt")"
  if [[ -z "${PRE_GPU_MIB[gpu]}" ]] || (( PRE_GPU_MIB[gpu] > GPU_IDLE_MAX_MIB )); then
    echo "GPU $gpu is not idle: ${PRE_GPU_MIB[gpu]:-unknown} MiB" >&2
    exit 2
  fi
done

{
  echo "date_utc=$STAMP"
  echo "scope=four simultaneous one-GPU process functional smoke"
  echo "model=$MODEL"
  echo "model_sha256=$EXPECTED_MODEL_SHA256"
  echo "llama_server=$LLAMA_SERVER"
  echo "llama_server_sha256=$EXPECTED_RUNTIME_SHA256"
  echo "ctx_size=$CTX_SIZE"
  echo "parallel_slots_per_process=1"
  echo "cache_type_k=f16"
  echo "cache_type_v=f16"
  echo "sycl_dnn_enabled=0"
  echo "sycl_opt_enabled=1"
  echo "base_port=$BASE_PORT"
  echo "timing_use=diagnostic_only"
} > "$RUN_DIR/run-identity.env"

for gpu in 0 1 2 3; do
  port=$((BASE_PORT + gpu))
  GPU_INDEX="$gpu" \
  PORT="$port" \
  MODEL="$MODEL" \
  LLAMA_SERVER="$LLAMA_SERVER" \
  CTX_SIZE="$CTX_SIZE" \
  CACHE_TYPE_K=f16 \
  CACHE_TYPE_V=f16 \
  LANE_DNN_ENABLED=0 \
  LANE_OPT_ENABLED=1 \
  LOG="$RUN_DIR/gpu${gpu}/server.identity.log" \
  SERVER_OUTPUT_LOG="$RUN_DIR/gpu${gpu}/server.stdout.log" \
  OUT_DIR="$RUN_DIR/gpu${gpu}" \
    "$LANE/scripts/serve-target-only.sh" > "$RUN_DIR/gpu${gpu}/server.stdout.log" 2>&1 &
  SERVER_PIDS[gpu]=$!
  printf '%s\n' "${SERVER_PIDS[gpu]}" > "$RUN_DIR/gpu${gpu}/server.pid"

  deadline=$((SECONDS + READINESS_TIMEOUT_S))
  until curl -fsS "http://127.0.0.1:${port}/v1/models" > "$RUN_DIR/gpu${gpu}/models.json" 2> "$RUN_DIR/gpu${gpu}/models.err"; do
    if ! kill -0 "${SERVER_PIDS[gpu]}" 2>/dev/null; then
      echo "GPU $gpu server exited before readiness" >&2
      exit 1
    fi
    if (( SECONDS >= deadline )); then
      echo "timed out waiting for GPU $gpu on port $port" >&2
      exit 1
    fi
    sleep 2
  done
  if ! grep -Fq 'offloaded 65/65 layers to GPU' "$RUN_DIR/gpu${gpu}/server.stdout.log"; then
    echo "GPU $gpu did not retain full-offload evidence" >&2
    exit 1
  fi
  check_host_memory "gpu${gpu}-loaded"
done

for gpu in 0 1 2 3; do
  loaded_mib=""
  timeout 20 xpu-smi stats -d "$gpu" > "$RUN_DIR/gpu${gpu}/xpu-smi-all-loaded.txt"
  loaded_mib="$(awk -F '|' '/GPU Memory Used/{gsub(/[^0-9.]/, "", $3); print int($3); exit}' "$RUN_DIR/gpu${gpu}/xpu-smi-all-loaded.txt")"
  if [[ -z "$loaded_mib" ]] || (( loaded_mib < 25000 || loaded_mib > 32000 )); then
    echo "GPU $gpu did not show the expected fully loaded memory range: ${loaded_mib:-unknown} MiB" >&2
    exit 1
  fi
done

SUITE="$ROOT/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json"
python3 - "$SEALED_ORACLE" "$RUN_DIR/sealed-one-prompt-oracle.json" "$EXPECTED_MODEL_SHA256" "$EXPECTED_RUNTIME_SHA256" <<'PY'
import copy
import json
import sys

source_path, out_path, model_sha, runtime_sha = sys.argv[1:]
data = json.load(open(source_path))
identity = data["run_identity"]
rows = data["rows"]
assert data["intrinsic_gate"]["passed"] is True
assert identity["model_sha256"] == model_sha
assert identity["runtime_sha256"] == runtime_sha
assert identity["ctx_size"] == 4096
assert identity["cache_type_k"] == identity["cache_type_v"] == "f16"
assert identity["max_tokens"] == 128
assert len(rows) == 12
assert rows[0]["prompt_id"] == "incident-retrospective"
assert rows[0]["token_count"] == 128
assert rows[0]["cache_n"] == rows[0]["stream_cache_n"] == 0
assert rows[0]["truncated"] is rows[0]["stream_truncated"] is False

subset = copy.deepcopy(data)
subset["run_identity"]["prompt_ids"] = [rows[0]["prompt_id"]]
subset["rows"] = [rows[0]]
subset["summary"] = {
    "derived_sealed_oracle_subset": True,
    "source_prompt_count": len(rows),
    "subset_prompt_count": 1,
}
subset["oracle_comparison"] = {
    "status": "SEALED_SUBSET_DERIVED",
    "source_path": source_path,
}
with open(out_path, "w") as handle:
    json.dump(subset, handle, indent=2)
    handle.write("\n")
PY
COMMON_ARGS=(
  --suite "$SUITE"
  --max-prompts 1
  --max-tokens 128
  --model-sha256 "$EXPECTED_MODEL_SHA256"
  --runtime-sha256 "$EXPECTED_RUNTIME_SHA256"
  --cache-type-k f16
  --cache-type-v f16
  --ctx-size "$CTX_SIZE"
  --sycl-dnn-enabled 0
  --sycl-opt-enabled 1
)

python3 "$LANE/scripts/capture-exact-tokens.py" \
  --base-url "http://127.0.0.1:${BASE_PORT}" \
  --out "$RUN_DIR/common-oracle.json" \
  --oracle-json "$RUN_DIR/sealed-one-prompt-oracle.json" \
  "${COMMON_ARGS[@]}"
jq -e '.oracle_comparison.status == "PASS_ORACLE_EXACT" and .oracle_comparison.passed == true and .intrinsic_gate.passed == true' \
  "$RUN_DIR/common-oracle.json" >/dev/null

capture_failed=0
for gpu in 0 1 2 3; do
  port=$((BASE_PORT + gpu))
  python3 "$LANE/scripts/capture-exact-tokens.py" \
    --base-url "http://127.0.0.1:${port}" \
    --out "$RUN_DIR/gpu${gpu}/simultaneous-exact.json" \
    --oracle-json "$RUN_DIR/common-oracle.json" \
    "${COMMON_ARGS[@]}" \
    > "$RUN_DIR/gpu${gpu}/capture.stdout.log" 2> "$RUN_DIR/gpu${gpu}/capture.stderr.log" &
  CAPTURE_PIDS[gpu]=$!
done

set +e
for gpu in 0 1 2 3; do
  wait "${CAPTURE_PIDS[gpu]}" || capture_failed=1
done
set -e
CAPTURE_PIDS=()
if (( capture_failed != 0 )); then
  echo "one or more simultaneous exact captures failed" >&2
  exit 1
fi
for gpu in 0 1 2 3; do
  jq -e '.oracle_comparison.status == "PASS_ORACLE_EXACT" and .oracle_comparison.passed == true and .intrinsic_gate.passed == true' \
    "$RUN_DIR/gpu${gpu}/simultaneous-exact.json" >/dev/null
done

printf 'functional_validation_complete=1\nreplica_count=4\n' > "$RUN_DIR/functional-summary.env"
