#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LANE="$ROOT/experiments/qwen36-27b-q8-gguf-b70"
MODEL_MANIFEST="$LANE/model-manifest.json"
RUNTIME_MANIFEST="${RUNTIME_MANIFEST:-$LANE/runtime-manifest.json}"
SUITE="$LANE/c2-long-context-suite-v1.json"
CAPTURE="$LANE/scripts/capture-simultaneous-c2.py"
COMMON_CAPTURE="$LANE/scripts/capture-exact-tokens.py"
SUITE_VALIDATOR="$LANE/scripts/validate-c2-suite.py"
PROMPT_BUILDER="$ROOT/scripts/bench-openai-long-context-suite.py"
SERVER_LAUNCHER="$LANE/scripts/serve-target-only.sh"
SEALED_128_ORACLE="/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/qwen36-27b-q8_0-f16kv-short-dnn0-exact-20260808T232639Z/exact-tokens.json"
SEALED_128_ORACLE_SHA256="e4477808823cdf9bb182d5abc4788cee216011a0195cf49bf03a7bda35f5dbcc"
SEALED_128_SUITE="$ROOT/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json"
SEALED_128_SUITE_SHA256="df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac"
SEALED_128_CANARY_PROMPT_ID="incident-retrospective"

GPU_INDEX="${GPU_INDEX:-0}"
PORT="${PORT:-19460}"
BAND="${BAND:-near32k}"
MODEL="${MODEL:-/mnt/usb-models/models/qwen36-27b-q8-gguf/Qwen3.6-27B-Q8_0.gguf}"
MODEL_ALIAS="${MODEL_ALIAS:-qwen36-27b-q8_0-target-only}"
LLAMA_SERVER="${LLAMA_SERVER:-/dev/shm/llama.cpp-pr19-15586/build-sycl/bin/llama-server}"
TOKENIZER="${TOKENIZER:-/mnt/fast-ai/llm-cache/hf/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9}"
VALIDATOR_PYTHON="${VALIDATOR_PYTHON:-/home/steve/.venvs/deepseek-v4-xpu/bin/python}"
CONCURRENT_CASE_ORDER="${CONCURRENT_CASE_ORDER:-forward}"

# This is the sealed Goal-1 c2 identity. Runtime/source candidates must supply a
# matching runtime manifest instead of weakening these model and serving gates.
CTX_SIZE=65536
CTX_SIZE_PER_SLOT=32768
PARALLEL_SLOTS=2
KV_UNIFIED=0
CONT_BATCHING=1
CACHE_TYPE_K=f16
CACHE_TYPE_V=f16
BATCH_SIZE=1024
UBATCH_SIZE=128
N_GPU_LAYERS=99
THREADS=8
HTTP_THREADS=6
POLL=50
LOG_VERBOSITY=4
LANE_DNN_ENABLED=0
LANE_OPT_ENABLED=1
LANE_FA_ONEDNN=1
LANE_FA_ONEDNN_MAX_KV=0
LANE_MKL_FA=1
LANE_SYCL_FLASH_ATTN=1
FLASH_ATTN=on

VERIFY_MODEL_SHA256="${VERIFY_MODEL_SHA256:-1}"
REQUIRE_ALL_GPUS_IDLE="${REQUIRE_ALL_GPUS_IDLE:-1}"
GPU_IDLE_MAX_MIB="${GPU_IDLE_MAX_MIB:-256}"
MIN_POST_LOAD_FREE_MIB="${MIN_POST_LOAD_FREE_MIB:-1024}"
MIN_LOADED_DELTA_MIB="${MIN_LOADED_DELTA_MIB:-25000}"
HOST_MEM_MIN_KIB="${HOST_MEM_MIN_KIB:-33554432}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}"
REQUEST_TIMEOUT_S="${REQUEST_TIMEOUT_S:-1800}"
CLIENT_TIMEOUT_S="${CLIENT_TIMEOUT_S:-14400}"
SERVER_STOP_TIMEOUT_S="${SERVER_STOP_TIMEOUT_S:-45}"
CLIENT_STOP_TIMEOUT_S="${CLIENT_STOP_TIMEOUT_S:-10}"
STAMP="$(date -u +%Y%m%dT%H%M%S.%NZ)"
LABEL="${LABEL:-qwen36-27b-q8_0-f16kv-c2-${BAND}-gpu${GPU_INDEX}}"
RUN_DIR="${RUN_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/${LABEL}-${STAMP}}"

die() {
  echo "ERROR: $*" >&2
  exit 2
}

require_uint() {
  local name="$1"
  local value="$2"
  [[ "$value" =~ ^[0-9]+$ ]] || die "$name must be a nonnegative integer"
}

parse_gpu_used_mib() {
  local stats_path="$1"
  awk -F '|' '
    /GPU Memory Used/ {
      value = $3
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      if (value ~ /^[0-9]+([.][0-9]+)?$/) {
        print int(value)
        found = 1
      }
      exit
    }
    END { if (!found) exit 1 }
  ' "$stats_path"
}

case "$BAND" in
  short|middle|near32k) ;;
  *) die "BAND must be short, middle, or near32k" ;;
esac
case "$CONCURRENT_CASE_ORDER" in
  forward|reverse) ;;
  *) die "CONCURRENT_CASE_ORDER must be forward or reverse" ;;
esac
[[ "$GPU_INDEX" =~ ^[0-3]$ ]] || die "GPU_INDEX must be 0, 1, 2, or 3"
require_uint PORT "$PORT"
(( PORT >= 1024 && PORT <= 65535 )) || die "PORT must be from 1024 through 65535"
[[ "$MODEL_ALIAS" == "qwen36-27b-q8_0-target-only" ]] || die "MODEL_ALIAS is locked for the c2 validation lane"
[[ "$VERIFY_MODEL_SHA256" == "1" ]] || die "VERIFY_MODEL_SHA256=1 is mandatory"
[[ "$REQUIRE_ALL_GPUS_IDLE" == "1" ]] || die "formal c2 validation requires all four GPUs idle"
require_uint GPU_IDLE_MAX_MIB "$GPU_IDLE_MAX_MIB"
(( GPU_IDLE_MAX_MIB <= 256 )) || die "GPU_IDLE_MAX_MIB cannot exceed 256"
require_uint MIN_POST_LOAD_FREE_MIB "$MIN_POST_LOAD_FREE_MIB"
(( MIN_POST_LOAD_FREE_MIB >= 1024 )) || die "MIN_POST_LOAD_FREE_MIB cannot be below 1024"
require_uint MIN_LOADED_DELTA_MIB "$MIN_LOADED_DELTA_MIB"
(( MIN_LOADED_DELTA_MIB >= 25000 )) || die "MIN_LOADED_DELTA_MIB cannot be below 25000"
require_uint HOST_MEM_MIN_KIB "$HOST_MEM_MIN_KIB"
(( HOST_MEM_MIN_KIB >= 33554432 )) || die "HOST_MEM_MIN_KIB cannot be below 32 GiB"
require_uint READINESS_TIMEOUT_S "$READINESS_TIMEOUT_S"
require_uint REQUEST_TIMEOUT_S "$REQUEST_TIMEOUT_S"
require_uint CLIENT_TIMEOUT_S "$CLIENT_TIMEOUT_S"
require_uint SERVER_STOP_TIMEOUT_S "$SERVER_STOP_TIMEOUT_S"
require_uint CLIENT_STOP_TIMEOUT_S "$CLIENT_STOP_TIMEOUT_S"
(( READINESS_TIMEOUT_S > 0 && REQUEST_TIMEOUT_S > 0 && CLIENT_TIMEOUT_S > 0 )) || die "timeouts must be positive"
(( SERVER_STOP_TIMEOUT_S > 0 && CLIENT_STOP_TIMEOUT_S > 0 )) || die "stop timeouts must be positive"
[[ "$RUN_DIR" == /* && "$RUN_DIR" != "/" ]] || die "RUN_DIR must be a non-root absolute path"
[[ ! -e "$RUN_DIR" ]] || die "RUN_DIR already exists: $RUN_DIR"

for required_path in \
  "$MODEL_MANIFEST" "$RUNTIME_MANIFEST" "$SUITE" "$CAPTURE" \
  "$COMMON_CAPTURE" "$SUITE_VALIDATOR" "$PROMPT_BUILDER" "$SERVER_LAUNCHER" \
  "$SEALED_128_ORACLE" "$SEALED_128_SUITE"; do
  [[ -f "$required_path" ]] || die "required file not found: $required_path"
done
[[ -d "$TOKENIZER" ]] || die "pinned tokenizer snapshot not found: $TOKENIZER"
[[ "$(basename "$(readlink -f "$TOKENIZER")")" == "6a9e13bd6fc8f0983b9b99948120bc37f49c13e9" ]] || \
  die "TOKENIZER does not resolve to the pinned revision"
[[ "$VALIDATOR_PYTHON" == "/home/steve/.venvs/deepseek-v4-xpu/bin/python" ]] || \
  die "VALIDATOR_PYTHON is locked to the validated tokenizer environment"
[[ -x "$VALIDATOR_PYTHON" ]] || die "validator Python is not executable: $VALIDATOR_PYTHON"
[[ -f /opt/intel/oneapi/setvars.sh ]] || die "oneAPI environment script is missing"

for required_command in \
  awk basename chmod cmp cp curl dirname dpkg-query find flock git grep id journalctl jq ldd mkdir mktemp \
  modinfo python3 readlink sha256sum sort ss stat tee timeout uname xargs xpu-smi; do
  command -v "$required_command" >/dev/null 2>&1 || die "required command not found: $required_command"
done

EXPECTED_MODEL_SHA256="$(jq -er '.sha256' "$MODEL_MANIFEST")"
EXPECTED_MODEL_SIZE="$(jq -er '.size_bytes' "$MODEL_MANIFEST")"
EXPECTED_RUNTIME_SHA256="$(jq -er '.llama_server_sha256' "$RUNTIME_MANIFEST")"
EXPECTED_RUNTIME_VERSION="$(jq -er '.runtime_version_line' "$RUNTIME_MANIFEST")"
EXPECTED_TOKENIZER_REVISION="$(jq -er '.tokenizer_identity.revision' "$SUITE")"
[[ "$EXPECTED_TOKENIZER_REVISION" == "6a9e13bd6fc8f0983b9b99948120bc37f49c13e9" ]] || \
  die "c2 suite tokenizer revision is not the pinned revision"
[[ -f "$MODEL" ]] || die "model not found: $MODEL"
[[ "$(stat -c %s "$MODEL")" == "$EXPECTED_MODEL_SIZE" ]] || die "model byte size does not match its manifest"
[[ -x "$LLAMA_SERVER" ]] || die "llama-server not executable: $LLAMA_SERVER"
[[ "$(sha256sum "$SEALED_128_ORACLE" | awk '{print $1}')" == "$SEALED_128_ORACLE_SHA256" ]] || \
  die "sealed external canary oracle SHA-256 mismatch"
[[ "$(sha256sum "$SEALED_128_SUITE" | awk '{print $1}')" == "$SEALED_128_SUITE_SHA256" ]] || \
  die "sealed external canary suite SHA-256 mismatch"

unexpected_env=()
while IFS='=' read -r name _; do
  case "$name" in
    GGML_*|SYCL_*|ZE_*|ZES_*|UR_*|ONEAPI_DEVICE_SELECTOR|LD_PRELOAD)
      unexpected_env+=("$name")
      ;;
    LLAMA_*)
      [[ "$name" == "LLAMA_SERVER" ]] || unexpected_env+=("$name")
      ;;
  esac
done < <(env)
(( ${#unexpected_env[@]} == 0 )) || die "unexpected inherited runtime environment: ${unexpected_env[*]}"

mkdir -p "$(dirname "$RUN_DIR")"
mkdir "$RUN_DIR" || die "RUN_DIR already exists or could not be created: $RUN_DIR"
mkdir "$RUN_DIR/oracle-snapshots"
SEALED_128_ORACLE_SNAPSHOT="$RUN_DIR/oracle-snapshots/sealed-128-oracle.json"
cp -- "$SEALED_128_ORACLE" "$SEALED_128_ORACLE_SNAPSHOT"
chmod 0444 "$SEALED_128_ORACLE_SNAPSHOT"
printf '%s  %s\n' "$SEALED_128_ORACLE_SHA256" "$SEALED_128_ORACLE_SNAPSHOT" |
  sha256sum -c - > "$RUN_DIR/oracle-snapshots/sealed-128-oracle.check.txt"
exec {QWEN36_MODEL_FD}<"$MODEL"
flock -s -n "$QWEN36_MODEL_FD" || die "could not acquire the shared model-file lock"
MODEL_FD_PATH="/proc/$$/fd/$QWEN36_MODEL_FD"
[[ "$MODEL" -ef "$MODEL_FD_PATH" ]] || die "model pathname does not match the pinned descriptor"
[[ "$(stat -Lc %s "$MODEL_FD_PATH")" == "$EXPECTED_MODEL_SIZE" ]] || \
  die "pinned model descriptor size does not match the manifest"
export QWEN36_MODEL_FD
GPU_LEASE_DIR="/run/user/$(id -u)/qwen36-b70-gpu-leases"
PORT_LEASE_DIR="/run/user/$(id -u)/qwen36-b70-port-leases"
mkdir -p "$GPU_LEASE_DIR" "$PORT_LEASE_DIR"
PORT_LEASE_PATH="$PORT_LEASE_DIR/port${PORT}.lock"
declare -a GPU_LEASE_PATHS=()
declare -a GPU_LEASE_FDS=()
INHERITED_SELECTED_GPU_LEASE_FD="${QWEN36_GPU_LEASE_FD:-}"
for lease_gpu in 0 1 2 3; do
  lease_path="$GPU_LEASE_DIR/gpu${lease_gpu}.lock"
  lease_fd=""
  if [[ "$lease_gpu" == "$GPU_INDEX" && -n "$INHERITED_SELECTED_GPU_LEASE_FD" ]]; then
    [[ "$INHERITED_SELECTED_GPU_LEASE_FD" =~ ^[0-9]+$ ]] || \
      die "QWEN36_GPU_LEASE_FD must be numeric"
    [[ "$(readlink -f "/proc/$$/fd/$INHERITED_SELECTED_GPU_LEASE_FD" 2>/dev/null || true)" == "$(readlink -f "$lease_path")" ]] || \
      die "inherited GPU lease does not match GPU $GPU_INDEX"
    flock -n "$INHERITED_SELECTED_GPU_LEASE_FD" || \
      die "inherited GPU lease is not held"
    lease_fd="$INHERITED_SELECTED_GPU_LEASE_FD"
  else
    exec {lease_fd}>"$lease_path"
    flock -n "$lease_fd" || \
      die "GPU $lease_gpu is leased by another Qwen validation process"
  fi
  GPU_LEASE_PATHS[$lease_gpu]="$lease_path"
  GPU_LEASE_FDS[$lease_gpu]="$lease_fd"
done
QWEN36_GPU_LEASE_FD="${GPU_LEASE_FDS[$GPU_INDEX]}"
GPU_LEASE_PATH="${GPU_LEASE_PATHS[$GPU_INDEX]}"
export QWEN36_GPU_LEASE_FD
if [[ -n "${QWEN36_PORT_LEASE_FD:-}" ]]; then
  [[ "$QWEN36_PORT_LEASE_FD" =~ ^[0-9]+$ ]] || die "QWEN36_PORT_LEASE_FD must be numeric"
  [[ "$(readlink -f "/proc/$$/fd/$QWEN36_PORT_LEASE_FD" 2>/dev/null || true)" == "$(readlink -f "$PORT_LEASE_PATH")" ]] || \
    die "inherited port lease does not match port $PORT"
  flock -n "$QWEN36_PORT_LEASE_FD" || die "inherited port lease is not held"
else
  exec {QWEN36_PORT_LEASE_FD}>"$PORT_LEASE_PATH"
  flock -n "$QWEN36_PORT_LEASE_FD" || die "port $PORT is leased by another Qwen validation process"
  export QWEN36_PORT_LEASE_FD
fi
{
  echo "selected_gpu_index=$GPU_INDEX"
  for lease_gpu in 0 1 2 3; do
    echo "gpu${lease_gpu}_lease_path=${GPU_LEASE_PATHS[$lease_gpu]}"
    echo "gpu${lease_gpu}_lease_fd=${GPU_LEASE_FDS[$lease_gpu]}"
  done
  echo "port=$PORT"
  echo "port_lease_path=$PORT_LEASE_PATH"
  echo "port_lease_fd=$QWEN36_PORT_LEASE_FD"
  echo "model_pinned_fd=$QWEN36_MODEL_FD"
  echo "model_pinned_path=$(readlink -f "$MODEL_FD_PATH")"
} > "$RUN_DIR/resource-leases.env"
START_EPOCH="$(date +%s)"
SERVER_PID=""
CLIENT_PID=""
ACTIVE_PHASE=""
ACTIVE_PHASE_DIR=""
ACTIVE_PRE_MIB=""
ACTIVE_EXPECTED_RUNNING=0
SERVER_LAUNCH_COUNT=0
BODY_COMPLETED=0
CLEANUP_FORCED=0
CLEANUP_SURVIVOR=0
INITIAL_SELECTED_MIB=""
HARNESS_MANIFEST_READY=0
HARNESS_MANIFEST_SHA256=""
RUNTIME_BUNDLE_READY=0
RUNTIME_BUNDLE_REPORT_SHA256=""
RUNTIME_RESOLVED_MANIFEST_SHA256=""
MODEL_STAT_BASELINE_READY=0
declare -A PHASE_CLEANUP_PASSED=()

check_host_memory() {
  local label="$1"
  local available_kib
  local swap_free_kib

  available_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
  swap_free_kib="$(awk '/^SwapFree:/ {print $2}' /proc/meminfo)"
  {
    echo "MemAvailable_kib=$available_kib"
    echo "SwapFree_kib=$swap_free_kib"
    echo "minimum_MemAvailable_kib=$HOST_MEM_MIN_KIB"
  } > "$RUN_DIR/host-memory-${label}.env"
  [[ -n "$available_kib" && -n "$swap_free_kib" ]] || return 1
  (( available_kib >= HOST_MEM_MIN_KIB ))
}

capture_model_stat() {
  local output="$1"
  python3 - "$MODEL" "$MODEL_FD_PATH" "$output" <<'PY'
import json
import os
import stat
import sys

model_path, model_fd_path, output_path = sys.argv[1:]
info = os.stat(model_fd_path, follow_symlinks=True)
payload = {
    "requested_path": model_path,
    "requested_path_resolved": os.path.realpath(model_path),
    "pinned_fd_path": model_fd_path,
    "pinned_path_resolved": os.path.realpath(model_fd_path),
    "device": info.st_dev,
    "inode": info.st_ino,
    "size_bytes": info.st_size,
    "mtime_ns": info.st_mtime_ns,
    "ctime_ns": info.st_ctime_ns,
    "mode": stat.S_IMODE(info.st_mode),
}
with open(output_path, "w") as output:
    json.dump(payload, output, indent=2, sort_keys=True)
    output.write("\n")
PY
}

verify_model_stat() {
  local label="$1"
  local observed="$RUN_DIR/model-stat-${label}.json"
  local check_log="$RUN_DIR/model-stat-${label}.check.log"

  (( MODEL_STAT_BASELINE_READY == 1 )) || {
    printf 'model stat baseline was not initialized\n' > "$check_log"
    return 1
  }
  [[ "$MODEL" -ef "$MODEL_FD_PATH" ]] || {
    printf 'model pathname no longer matches pinned descriptor\n' > "$check_log"
    return 1
  }
  capture_model_stat "$observed" || return 1
  if cmp -s "$RUN_DIR/model-stat-baseline.json" "$observed"; then
    printf 'model stat identity unchanged\n' > "$check_log"
    return 0
  fi
  printf 'model stat identity changed\n' > "$check_log"
  return 1
}

sample_gpu() {
  local device="$1"
  local output="$2"
  timeout 20 xpu-smi stats -d "$device" > "$output" 2>&1
}

verify_harness_inputs() {
  local label="$1"
  local observed_manifest_sha256
  local check_log="$RUN_DIR/harness-inputs-${label}.check.log"

  if (( HARNESS_MANIFEST_READY != 1 )); then
    printf 'harness manifest was not initialized\n' > "$check_log"
    return 1
  fi
  if ! observed_manifest_sha256="$(sha256sum "$RUN_DIR/harness-inputs.sha256" | awk '{print $1}')"; then
    printf 'harness manifest could not be hashed\n' > "$check_log"
    return 1
  fi
  if [[ "$observed_manifest_sha256" != "$HARNESS_MANIFEST_SHA256" ]]; then
    printf 'harness manifest changed: expected %s, got %s\n' \
      "$HARNESS_MANIFEST_SHA256" "$observed_manifest_sha256" > "$check_log"
    return 1
  fi
  sha256sum -c "$RUN_DIR/harness-inputs.sha256" > "$check_log" 2>&1
}

verify_runtime_bundle_snapshot() {
  local label="$1"
  local check_log="$RUN_DIR/runtime-resolved-files-${label}.check.log"
  local ldd_output="$RUN_DIR/llama-server-ldd-${label}-post-oneapi.txt"
  local hashes_output="$RUN_DIR/runtime-resolved-files-${label}.sha256"
  local report_output="$RUN_DIR/runtime-bundle-${label}.json"
  local observed_report_sha256
  local observed_resolved_manifest_sha256

  if (( RUNTIME_BUNDLE_READY != 1 )); then
    printf 'runtime bundle baseline was not initialized\n' > "$check_log"
    return 1
  fi
  observed_report_sha256="$(sha256sum "$RUN_DIR/runtime-bundle-initial.json" | awk '{print $1}')" || return 1
  observed_resolved_manifest_sha256="$(sha256sum "$RUN_DIR/runtime-resolved-files.sha256" | awk '{print $1}')" || return 1
  if [[ "$observed_report_sha256" != "$RUNTIME_BUNDLE_REPORT_SHA256" ]] || \
     [[ "$observed_resolved_manifest_sha256" != "$RUNTIME_RESOLVED_MANIFEST_SHA256" ]]; then
    printf 'runtime bundle evidence manifest drifted\n' > "$check_log"
    return 1
  fi
  if ! sha256sum -c "$RUN_DIR/runtime-resolved-files.sha256" \
    > "$check_log" 2>&1; then
    return 1
  fi
  LLAMA_SERVER="$LLAMA_SERVER" \
  RUNTIME_MANIFEST="$RUNTIME_MANIFEST" \
    "$SERVER_LAUNCHER" --verify-runtime-bundle \
      "$ldd_output" "$hashes_output" "$report_output" \
      "$RUN_DIR/runtime-bundle-initial.json" \
      >> "$check_log" 2>&1
}

wait_for_pid_exit() {
  local pid="$1"
  local timeout_s="$2"
  local deadline=$((SECONDS + timeout_s))

  while kill -0 "$pid" 2>/dev/null; do
    (( SECONDS < deadline )) || return 1
    sleep 1
  done
}

stop_active_phase() {
  local phase="$ACTIVE_PHASE"
  local phase_dir="$ACTIVE_PHASE_DIR"
  local cleanup_ok=1
  local client_forced=0
  local server_forced=0
  local server_alive_before_stop=0
  local client_still_alive=0
  local server_still_alive=0
  local port_closed=0
  local vram_returned=0
  local all_gpus_idle_after=1
  local final_mib=""
  local device
  local used

  [[ -n "$phase" ]] || return 0
  set +e
  if [[ -n "$CLIENT_PID" ]] && kill -0 "$CLIENT_PID" 2>/dev/null; then
    kill "$CLIENT_PID" 2>/dev/null
    if ! wait_for_pid_exit "$CLIENT_PID" "$CLIENT_STOP_TIMEOUT_S"; then
      client_forced=1
      CLEANUP_FORCED=1
      kill -KILL "$CLIENT_PID" 2>/dev/null
      if ! wait_for_pid_exit "$CLIENT_PID" 5; then
        client_still_alive=1
        CLEANUP_SURVIVOR=1
      fi
    fi
    if (( client_still_alive == 0 )); then
      wait "$CLIENT_PID" 2>/dev/null
    fi
  fi
  CLIENT_PID=""

  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    server_alive_before_stop=1
    kill "$SERVER_PID" 2>/dev/null
    if ! wait_for_pid_exit "$SERVER_PID" "$SERVER_STOP_TIMEOUT_S"; then
      server_forced=1
      CLEANUP_FORCED=1
      kill -KILL "$SERVER_PID" 2>/dev/null
      if ! wait_for_pid_exit "$SERVER_PID" 5; then
        server_still_alive=1
        CLEANUP_SURVIVOR=1
      fi
    fi
    if (( server_still_alive == 0 )); then
      wait "$SERVER_PID" 2>/dev/null
    fi
  fi
  if (( ACTIVE_EXPECTED_RUNNING == 1 && server_alive_before_stop == 0 )); then
    cleanup_ok=0
  fi
  if (( client_forced != 0 || server_forced != 0 || client_still_alive != 0 || server_still_alive != 0 )); then
    cleanup_ok=0
  fi
  if ss -H -ltn "sport = :$PORT" | grep -q .; then
    port_closed=0
    cleanup_ok=0
  else
    port_closed=1
  fi
  for device in 0 1 2 3; do
    if ! sample_gpu "$device" "$phase_dir/xpu-smi-after-gpu${device}.txt"; then
      all_gpus_idle_after=0
      continue
    fi
    used="$(parse_gpu_used_mib "$phase_dir/xpu-smi-after-gpu${device}.txt")"
    if [[ -z "$used" ]] || (( used > GPU_IDLE_MAX_MIB )); then
      all_gpus_idle_after=0
    fi
    if [[ "$device" == "$GPU_INDEX" ]]; then
      final_mib="$used"
    fi
  done
  if [[ -n "$final_mib" && -n "$ACTIVE_PRE_MIB" ]] && \
     (( final_mib <= ACTIVE_PRE_MIB + GPU_IDLE_MAX_MIB )); then
    vram_returned=1
  else
    cleanup_ok=0
  fi
  if (( all_gpus_idle_after == 0 )); then
    cleanup_ok=0
  fi
  {
    echo "phase=$phase"
    echo "client_forced_kill=$client_forced"
    echo "server_forced_kill=$server_forced"
    echo "client_still_alive=$client_still_alive"
    echo "server_still_alive=$server_still_alive"
    echo "server_alive_before_stop=$server_alive_before_stop"
    echo "port_closed=$port_closed"
    echo "vram_returned=$vram_returned"
    echo "all_four_gpus_idle_after=$all_gpus_idle_after"
    echo "pre_mib=${ACTIVE_PRE_MIB:-unknown}"
    echo "final_mib=${final_mib:-unknown}"
    echo "cleanup_passed=$cleanup_ok"
  } > "$phase_dir/cleanup-status.env"
  PHASE_CLEANUP_PASSED["$phase"]="$cleanup_ok"
  SERVER_PID=""
  ACTIVE_PHASE=""
  ACTIVE_PHASE_DIR=""
  ACTIVE_PRE_MIB=""
  ACTIVE_EXPECTED_RUNNING=0
  set -e
  (( cleanup_ok == 1 ))
}

seal_artifacts() {
  local seal_tmp
  (( CLEANUP_SURVIVOR == 0 )) || return 1
  seal_tmp="$(mktemp "${RUN_DIR}.artifacts.XXXXXX")" || return 1
  if ! (
    cd "$RUN_DIR"
    find . -type f \
      ! -name artifacts.sha256 \
      ! -name completion-status.json \
      -print0 |
      sort -z | xargs -0 -r sha256sum
  ) > "$seal_tmp"; then
    rm -f "$seal_tmp"
    return 1
  fi
  if [[ ! -s "$seal_tmp" ]] || ! (
    cd "$RUN_DIR"
    sha256sum -c "$seal_tmp" >/dev/null
  ); then
    rm -f "$seal_tmp"
    return 1
  fi
  mv "$seal_tmp" "$RUN_DIR/artifacts.sha256" || return 1
  (
    cd "$RUN_DIR"
    sha256sum -c artifacts.sha256 >/dev/null
  )
}

write_completion_status() {
  local marker_tmp
  local artifacts_sha256
  local summary_sha256
  local external_quality_passed
  local semantic_quality_passed

  [[ -s "$RUN_DIR/artifacts.sha256" ]] || return 1
  (
    cd "$RUN_DIR"
    sha256sum -c artifacts.sha256 >/dev/null
  ) || return 1
  artifacts_sha256="$(sha256sum "$RUN_DIR/artifacts.sha256" | awk '{print $1}')" || return 1
  summary_sha256="$(sha256sum "$RUN_DIR/validation-summary.json" | awk '{print $1}')" || return 1
  external_quality_passed="$(jq -er '
    .mandatory_gates.external_baseline_canary_both_phases == true
    and .mandatory_gates.external_baseline_canary_identity_both_phases == true
  ' "$RUN_DIR/validation-summary.json")" || return 1
  semantic_quality_passed="$(jq -er '
    .mandatory_gates.semantic_retrieval_both_phases == true
    and .mandatory_gates.semantic_cross_phase_exact == true
  ' "$RUN_DIR/validation-summary.json")" || return 1
  [[ "$external_quality_passed" == "true" && "$semantic_quality_passed" == "true" ]] || return 1
  marker_tmp="$(mktemp "${RUN_DIR}.completion-status.XXXXXX")" || return 1
  if ! python3 - \
    "$artifacts_sha256" "$summary_sha256" "$HARNESS_MANIFEST_SHA256" \
    "$SEALED_128_ORACLE_SHA256" "$SEALED_128_SUITE_SHA256" \
    "$SEALED_128_CANARY_PROMPT_ID" \
    > "$marker_tmp" <<'PY'
import datetime
import json
import sys

(
    artifacts_sha256,
    summary_sha256,
    harness_sha256,
    external_oracle_sha256,
    external_suite_sha256,
    external_prompt_id,
) = sys.argv[1:]
print(json.dumps({
    "artifact_manifest": "artifacts.sha256",
    "artifact_manifest_sha256": artifacts_sha256,
    "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "evidence_valid": True,
    "external_baseline_canary_passed": True,
    "external_baseline_oracle_sha256": external_oracle_sha256,
    "external_baseline_prompt_id": external_prompt_id,
    "external_baseline_suite_sha256": external_suite_sha256,
    "exit_status": 0,
    "harness_manifest_sha256": harness_sha256,
    "pre_seal_summary": "validation-summary.json",
    "pre_seal_summary_sha256": summary_sha256,
    "run_status": "PASS",
    "semantic_retrieval_and_cross_phase_exact": True,
}, indent=2, sort_keys=True))
PY
  then
    rm -f "$marker_tmp"
    return 1
  fi
  if ! jq -e \
    --arg artifacts "$artifacts_sha256" \
    --arg summary "$summary_sha256" \
    --arg harness "$HARNESS_MANIFEST_SHA256" \
    --arg oracle "$SEALED_128_ORACLE_SHA256" \
    --arg suite "$SEALED_128_SUITE_SHA256" \
    --arg prompt "$SEALED_128_CANARY_PROMPT_ID" '
      .evidence_valid == true
      and .exit_status == 0
      and .run_status == "PASS"
      and .artifact_manifest_sha256 == $artifacts
      and .pre_seal_summary_sha256 == $summary
      and .harness_manifest_sha256 == $harness
      and .external_baseline_canary_passed == true
      and .external_baseline_oracle_sha256 == $oracle
      and .external_baseline_suite_sha256 == $suite
      and .external_baseline_prompt_id == $prompt
      and .semantic_retrieval_and_cross_phase_exact == true
    ' "$marker_tmp" >/dev/null; then
    rm -f "$marker_tmp"
    return 1
  fi
  mv "$marker_tmp" "$RUN_DIR/completion-status.json"
}

write_validation_summary() {
  local fault_scans_clear="$1"
  local final_port_closed="$2"
  local final_vram_returned="$3"
  local no_forced_kill="$4"
  local final_host_memory_ok="$5"
  local no_cleanup_survivor="$6"
  local harness_inputs_unchanged="$7"
  local runtime_bundle_unchanged="$8"
  local final_all_gpus_idle="$9"
  local model_stat_unchanged="${10}"
  local model_sha256_final_verified="${11}"
  python3 - \
    "$RUN_DIR" "$BODY_COMPLETED" "$SERVER_LAUNCH_COUNT" "$fault_scans_clear" \
    "$BAND" "$final_port_closed" "$final_vram_returned" "$no_forced_kill" \
    "$final_host_memory_ok" "$no_cleanup_survivor" "$harness_inputs_unchanged" \
    "$runtime_bundle_unchanged" "$final_all_gpus_idle" \
    "$model_stat_unchanged" "$model_sha256_final_verified" \
    "$SEALED_128_ORACLE_SHA256" "$SEALED_128_SUITE_SHA256" \
    "$SEALED_128_CANARY_PROMPT_ID" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
body_completed = int(sys.argv[2]) == 1
launch_count = int(sys.argv[3])
fault_scans_clear = int(sys.argv[4]) == 1
band = sys.argv[5]
final_port_closed = int(sys.argv[6]) == 1
final_vram_returned = int(sys.argv[7]) == 1
no_forced_kill = int(sys.argv[8]) == 1
final_host_memory_ok = int(sys.argv[9]) == 1
no_cleanup_survivor = int(sys.argv[10]) == 1
harness_inputs_unchanged = int(sys.argv[11]) == 1
runtime_bundle_unchanged = int(sys.argv[12]) == 1
final_all_gpus_idle = int(sys.argv[13]) == 1
model_stat_unchanged = int(sys.argv[14]) == 1
model_sha256_final_verified = int(sys.argv[15]) == 1
external_oracle_sha256 = sys.argv[16]
external_suite_sha256 = sys.argv[17]
external_prompt_id = sys.argv[18]

def load_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def cleanup_passed(path: Path) -> bool:
    try:
        fields = dict(
            line.split("=", 1)
            for line in path.read_text().splitlines()
            if "=" in line
        )
    except FileNotFoundError:
        return False
    return fields.get("cleanup_passed") == "1"

sequential = load_json(root / "sequential-oracle" / "oracle.json") or {}
concurrent = load_json(root / "concurrent" / "result.json") or {}
phase_names = ("sequential-oracle", "concurrent")
phase_attestation = {
    name: bool((load_json(root / name / "server-attestation.json") or {}).get("passed"))
    for name in phase_names
}
phase_vram = {
    name: bool((load_json(root / name / "vram-fit-check.json") or {}).get("passed"))
    for name in phase_names
}
phase_cleanup = {
    name: cleanup_passed(root / name / "cleanup-status.env")
    for name in phase_names
}

def phase_quality(packet: dict) -> dict[str, bool]:
    identity = packet.get("run_identity") or {}
    external = packet.get("external_baseline_canaries") or []
    semantic = packet.get("semantic_retrieval") or []
    external_identity = (
        identity.get("baseline_canary_oracle_sha256") == external_oracle_sha256
        and identity.get("baseline_canary_suite_sha256") == external_suite_sha256
        and identity.get("baseline_canary_prompt_id") == external_prompt_id
        and len(external) == 2
        and all(
            isinstance(row, dict)
            and row.get("passed") is True
            and type(row.get("slot_id_requested")) is int
            and row.get("slot_id_requested") == slot_id
            and row.get("oracle_sha256") == external_oracle_sha256
            and row.get("suite_sha256") == external_suite_sha256
            and row.get("prompt_id") == external_prompt_id
            for slot_id, row in enumerate(external)
        )
    )
    semantic_natural_stop = len(semantic) == 2 and all(
        isinstance(row, dict)
        and row.get("passed") is True
        and row.get("stop_type") == "eos"
        for row in semantic
    )
    semantic_cache_zero = len(semantic) == 2 and all(
        isinstance(row, dict)
        and type(row.get("cache_n")) is int
        and row.get("cache_n") == 0
        for row in semantic
    )
    semantic_forced_link = len(semantic) == 2 and all(
        isinstance(row, dict)
        and row.get("forced_512_pre_eos_token_prefix_exact") is True
        and row.get("forced_512_content_prefix_exact") is True
        for row in semantic
    )
    return {
        "external_canary_identity": external_identity,
        "external_canary_passed": external_identity
        and all(row.get("passed") is True for row in external),
        "semantic_natural_stop_all": semantic_natural_stop,
        "semantic_cache_zero_all": semantic_cache_zero,
        "semantic_forced512_link_all": semantic_forced_link,
        "semantic_selected_cases_exact": semantic_natural_stop
        and semantic_cache_zero
        and semantic_forced_link
        and all((row.get("validation") or {}).get("pass") is True for row in semantic),
    }

phase_quality_gates = {
    "sequential-oracle": phase_quality(sequential),
    "concurrent": phase_quality(concurrent),
}
semantic_cross_phase_exact = (
    (concurrent.get("oracle_comparison") or {}).get("passed") is True
    and len((concurrent.get("oracle_comparison") or {}).get("semantic_retrieval") or [])
    == 2
    and all(
        isinstance(row, dict)
        and row.get("prompt_exact") is True
        and row.get("tokens_exact") is True
        and row.get("content_exact") is True
        for row in (
            (concurrent.get("oracle_comparison") or {}).get("semantic_retrieval")
            or []
        )
    )
)

sequential_passed = (
    sequential.get("intrinsic_gate", {}).get("passed") is True
    and sequential.get("intrinsic_gate", {}).get("semantic_retrieval_passed") is True
    and sequential.get("intrinsic_gate", {}).get("external_baseline_canary_passed") is True
    and len(sequential.get("external_baseline_canaries") or []) == 2
    and all(
        isinstance(row, dict) and row.get("passed") is True
        for row in (sequential.get("external_baseline_canaries") or [])
    )
    and len(sequential.get("semantic_retrieval") or []) == 2
    and all(
        isinstance(row, dict) and row.get("passed") is True
        for row in (sequential.get("semantic_retrieval") or [])
    )
    and sequential.get("oracle_comparison", {}).get("status")
    == "BASELINE_CAPTURE_READY"
)
concurrent_passed = (
    concurrent.get("intrinsic_gate", {}).get("passed") is True
    and concurrent.get("intrinsic_gate", {}).get("semantic_retrieval_passed") is True
    and concurrent.get("intrinsic_gate", {}).get("external_baseline_canary_passed") is True
    and len(concurrent.get("external_baseline_canaries") or []) == 2
    and all(
        isinstance(row, dict) and row.get("passed") is True
        for row in (concurrent.get("external_baseline_canaries") or [])
    )
    and len(concurrent.get("semantic_retrieval") or []) == 2
    and all(
        isinstance(row, dict) and row.get("passed") is True
        for row in (concurrent.get("semantic_retrieval") or [])
    )
    and concurrent.get("oracle_comparison", {}).get("passed") is True
    and concurrent.get("oracle_comparison", {}).get("status")
    == "PASS_ORACLE_EXACT"
)

aggregate = concurrent.get("aggregate") or {}
rows = concurrent.get("rows") or []
sustained_rates = [
    row.get("sustained_metric", {}).get("tok_s")
    for row in rows
    if isinstance(row.get("sustained_metric", {}).get("tok_s"), (int, float))
]
aggregate_rate = aggregate.get("aggregate_tok_s_1_512_intervals")
aggregate_pp_rate = aggregate.get("aggregate_prompt_tok_s_wall")
fairness = aggregate.get("fairness_min_over_max")
primary_thresholds_met = (
    isinstance(aggregate_rate, (int, float))
    and aggregate_rate >= 30.0
    and len(sustained_rates) == 2
    and min(sustained_rates) >= 13.0
    and isinstance(aggregate_pp_rate, (int, float))
    and aggregate_pp_rate >= 400.0
)
stretch_thresholds_met = (
    isinstance(aggregate_rate, (int, float))
    and aggregate_rate >= 35.0
    and len(sustained_rates) == 2
    and min(sustained_rates) >= 16.0
)

mandatory = {
    "body_completed": body_completed,
    "exactly_two_fresh_server_launches": launch_count == 2,
    "sequential_oracle_passed": sequential_passed,
    "concurrent_intrinsic_and_oracle_passed": concurrent_passed,
    "external_baseline_canary_both_phases": all(
        gates["external_canary_passed"]
        for gates in phase_quality_gates.values()
    ),
    "external_baseline_canary_identity_both_phases": all(
        gates["external_canary_identity"]
        for gates in phase_quality_gates.values()
    ),
    "semantic_retrieval_both_phases": all(
        gates["semantic_selected_cases_exact"]
        for gates in phase_quality_gates.values()
    ),
    "semantic_cross_phase_exact": semantic_cross_phase_exact,
    "phase_attestation_passed": all(phase_attestation.values()),
    "phase_vram_fit_passed": all(phase_vram.values()),
    "phase_cleanup_passed": all(phase_cleanup.values()),
    "fault_scans_clear": fault_scans_clear,
    "final_port_closed": final_port_closed,
    "final_vram_returned": final_vram_returned,
    "no_forced_kill": no_forced_kill,
    "final_host_memory_ok": final_host_memory_ok,
    "no_cleanup_survivor": no_cleanup_survivor,
    "harness_inputs_unchanged": harness_inputs_unchanged,
    "runtime_bundle_unchanged": runtime_bundle_unchanged,
    "all_four_gpus_idle_after_run": final_all_gpus_idle,
    "model_stat_unchanged": model_stat_unchanged,
    "model_sha256_final_verified": model_sha256_final_verified,
}
functional_c2_passed = sequential_passed and concurrent_passed
pre_seal_gates_passed = all(mandatory.values())
result = {
    "band": band,
    "concurrent_case_order": concurrent.get("run_identity", {}).get("case_order"),
    "mandatory_gates": mandatory,
    "phase_attestation": phase_attestation,
    "phase_vram_fit": phase_vram,
    "phase_cleanup": phase_cleanup,
    "phase_quality_gates": phase_quality_gates,
    "external_baseline_identity": {
        "oracle_sha256": external_oracle_sha256,
        "suite_sha256": external_suite_sha256,
        "prompt_id": external_prompt_id,
        "slot_ids": [0, 1],
    },
    "semantic_cross_phase_exact": semantic_cross_phase_exact,
    "pre_seal_gates_passed": pre_seal_gates_passed,
    "completion_protocol": {
        "authoritative_completion_marker": "completion-status.json",
        "artifact_manifest": "artifacts.sha256",
        "note": "Evidence becomes valid only when the detached completion marker exists, says evidence_valid=true, and its referenced artifact manifest and digests verify.",
    },
    "functional_c2_passed": functional_c2_passed,
    "strategy_performance_targets": {
        "primary_thresholds_met": primary_thresholds_met,
        "stretch_thresholds_met": stretch_thresholds_met,
        "primary_passed": (
            pre_seal_gates_passed
            and functional_c2_passed
            and primary_thresholds_met
        ),
        "stretch_passed": (
            pre_seal_gates_passed
            and functional_c2_passed
            and stretch_thresholds_met
        ),
        "primary_thresholds": {
            "aggregate_decode_tok_s_min": 30.0,
            "each_request_decode_tok_s_min": 13.0,
            "aggregate_prompt_tok_s_min": 400.0,
        },
        "stretch_thresholds": {
            "aggregate_decode_tok_s_min": 35.0,
            "each_request_decode_tok_s_min": 16.0,
        },
        "observed": {
            "aggregate_tok_s_1_512_intervals": aggregate_rate,
            "per_request_tok_s_1_512_intervals": sustained_rates,
            "aggregate_prompt_tok_s_wall": aggregate_pp_rate,
            "fairness_min_over_max": fairness,
        },
        "note": "Raw threshold attainment is separate; primary/stretch pass also requires all pre-seal and functional c2 gates. An honest slower measurement can remain valid evidence without passing a performance target.",
    },
}
(root / "validation-summary.json").write_text(
    json.dumps(result, indent=2, sort_keys=True) + "\n"
)
PY
}

finish() {
  local original_status=$?
  local final_status="$original_status"
  local fault_scans_clear=1
  local final_mib=""
  local final_vram_returned=0
  local port_closed=0
  local no_forced_kill=1
  local final_host_memory_ok=1
  local no_cleanup_survivor=1
  local journal_scan_ok=1
  local server_scan_ok=1
  local harness_inputs_unchanged=0
  local runtime_bundle_unchanged=0
  local final_all_gpus_idle=1
  local grep_status=0
  local expected_log
  local device
  local used
  local model_stat_unchanged=0
  local model_sha256_final_verified=0

  trap - EXIT INT TERM
  set +e
  if ! stop_active_phase; then
    final_status=1
  fi
  set +e

  if ! journalctl -k --since "@$START_EPOCH" --no-pager \
    > "$RUN_DIR/kernel-journal.txt" 2> "$RUN_DIR/kernel-journal.stderr.log"; then
    journal_scan_ok=0
    : > "$RUN_DIR/device-error-scan.txt"
  else
    grep -Ei 'xe.*(reset|wedg|fault|hang|timedout|device lost)|GuC.*reset|Fault response|VM.*fault|PCIe.*AER|RAS.*error|UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST' \
      "$RUN_DIR/kernel-journal.txt" > "$RUN_DIR/device-error-scan.txt"
    grep_status=$?
    if (( grep_status > 1 )); then
      journal_scan_ok=0
    fi
  fi
  for expected_log in \
    "$RUN_DIR/sequential-oracle/server.stdout.log" \
    "$RUN_DIR/concurrent/server.stdout.log"; do
    if [[ ! -r "$expected_log" ]]; then
      server_scan_ok=0
    fi
  done
  if (( server_scan_ok == 1 )); then
    grep -EHi 'UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST|out of memory|segmentation fault|core dumped|Aborted' \
      "$RUN_DIR/sequential-oracle/server.stdout.log" \
      "$RUN_DIR/concurrent/server.stdout.log" \
        > "$RUN_DIR/server-error-scan.txt"
    grep_status=$?
    if (( grep_status > 1 )); then
      server_scan_ok=0
    fi
  else
    : > "$RUN_DIR/server-error-scan.txt"
  fi
  if (( journal_scan_ok == 0 || server_scan_ok == 0 )) || \
     [[ -s "$RUN_DIR/device-error-scan.txt" || -s "$RUN_DIR/server-error-scan.txt" ]]; then
    fault_scans_clear=0
    final_status=1
  fi
  {
    echo "journal_scan_ok=$journal_scan_ok"
    echo "server_scan_ok=$server_scan_ok"
    echo "device_error_scan_empty=$([[ ! -s "$RUN_DIR/device-error-scan.txt" ]] && echo 1 || echo 0)"
    echo "server_error_scan_empty=$([[ ! -s "$RUN_DIR/server-error-scan.txt" ]] && echo 1 || echo 0)"
    echo "fault_scans_clear=$fault_scans_clear"
  } > "$RUN_DIR/fault-scan-status.env"
  if ! check_host_memory final; then
    final_host_memory_ok=0
    final_status=1
  fi
  if ss -H -ltn "sport = :$PORT" | grep -q .; then
    port_closed=0
    final_status=1
  else
    port_closed=1
  fi
  for device in 0 1 2 3; do
    if ! sample_gpu "$device" "$RUN_DIR/xpu-smi-final-gpu${device}.txt"; then
      final_all_gpus_idle=0
      continue
    fi
    used="$(parse_gpu_used_mib "$RUN_DIR/xpu-smi-final-gpu${device}.txt")"
    if [[ -z "$used" ]] || (( used > GPU_IDLE_MAX_MIB )); then
      final_all_gpus_idle=0
    fi
    if [[ "$device" == "$GPU_INDEX" ]]; then
      final_mib="$used"
    fi
  done
  if [[ -n "$final_mib" && -n "$INITIAL_SELECTED_MIB" ]] && \
     (( final_mib <= INITIAL_SELECTED_MIB + GPU_IDLE_MAX_MIB )); then
    final_vram_returned=1
  else
    final_status=1
  fi
  if (( final_all_gpus_idle == 0 )); then
    final_status=1
  fi
  if (( CLEANUP_FORCED != 0 )); then
    no_forced_kill=0
    final_status=1
  fi
  if (( CLEANUP_SURVIVOR != 0 )); then
    no_cleanup_survivor=0
    final_status=1
  fi
  if verify_harness_inputs final; then
    harness_inputs_unchanged=1
  else
    final_status=1
  fi
  if verify_runtime_bundle_snapshot final; then
    runtime_bundle_unchanged=1
  else
    final_status=1
  fi
  if (( MODEL_STAT_BASELINE_READY == 1 )) && verify_model_stat final; then
    model_stat_unchanged=1
  else
    final_status=1
  fi
  if (( MODEL_STAT_BASELINE_READY == 1 )); then
    if printf '%s  %s\n' "$EXPECTED_MODEL_SHA256" "$MODEL_FD_PATH" |
      sha256sum -c - > "$RUN_DIR/model-sha256-final.check.txt" 2>&1; then
      model_sha256_final_verified=1
    else
      final_status=1
    fi
  else
    printf 'model stat baseline was not initialized\n' \
      > "$RUN_DIR/model-sha256-final.check.txt"
    final_status=1
  fi
  {
    echo "runtime_bundle_baseline_initialized=$RUNTIME_BUNDLE_READY"
    echo "runtime_bundle_unchanged=$runtime_bundle_unchanged"
  } > "$RUN_DIR/runtime-bundle-final-status.env"

  write_validation_summary \
    "$fault_scans_clear" "$port_closed" "$final_vram_returned" \
    "$no_forced_kill" "$final_host_memory_ok" "$no_cleanup_survivor" \
    "$harness_inputs_unchanged" "$runtime_bundle_unchanged" \
    "$final_all_gpus_idle" "$model_stat_unchanged" \
    "$model_sha256_final_verified"
  if ! jq -e '.pre_seal_gates_passed == true' \
    "$RUN_DIR/validation-summary.json" >/dev/null; then
    final_status=1
  fi
  {
    echo "forced_kill=$CLEANUP_FORCED"
    echo "cleanup_survivor=$CLEANUP_SURVIVOR"
    echo "port_closed=$port_closed"
    echo "vram_returned=$final_vram_returned"
    echo "all_four_gpus_idle_after=$final_all_gpus_idle"
    echo "model_stat_unchanged=$model_stat_unchanged"
    echo "model_sha256_final_verified=$model_sha256_final_verified"
    echo "initial_mib=${INITIAL_SELECTED_MIB:-unknown}"
    echo "final_mib=${final_mib:-unknown}"
    echo "sequential_cleanup_passed=${PHASE_CLEANUP_PASSED[sequential-oracle]:-0}"
    echo "concurrent_cleanup_passed=${PHASE_CLEANUP_PASSED[concurrent]:-0}"
  } > "$RUN_DIR/cleanup-status.env"
  if (( final_status == 0 )); then
    printf 'original_status=%s\npre_seal_status=0\ncompletion_marker_required=1\n' \
      "$original_status" > "$RUN_DIR/exit-status.env"
    printf 'PRE_SEAL_PASS_PENDING_COMPLETION\n' > "$RUN_DIR/run-status.txt"
  else
    printf 'original_status=%s\nfinal_status=%s\n' \
      "$original_status" "$final_status" > "$RUN_DIR/exit-status.env"
    printf 'FAIL\n' > "$RUN_DIR/run-status.txt"
  fi

  rm -f "$RUN_DIR/artifacts.sha256" "$RUN_DIR/completion-status.json"
  if (( final_status == 0 )); then
    if ! seal_artifacts || ! write_completion_status; then
      final_status=1
    fi
  fi
  if (( final_status != 0 )); then
    final_status=1
    printf 'original_status=%s\nfinal_status=%s\n' "$original_status" "$final_status" > "$RUN_DIR/exit-status.env"
    printf 'FAIL\n' > "$RUN_DIR/run-status.txt"
    rm -f "$RUN_DIR/artifacts.sha256" "$RUN_DIR/completion-status.json"
    # A sealed failure packet is useful, but only completion-status.json can
    # upgrade a successful pre-seal packet to valid evidence.
    seal_artifacts || true
  fi
  printf '%s\n' "$RUN_DIR"
  exit "$final_status"
}
trap finish EXIT
trap 'exit 130' INT TERM

check_phase_idle() {
  local phase="$1"
  local phase_dir="$2"
  local device
  local used

  for device in 0 1 2 3; do
    if [[ "$device" != "$GPU_INDEX" && "$REQUIRE_ALL_GPUS_IDLE" == "0" ]]; then
      continue
    fi
    sample_gpu "$device" "$phase_dir/xpu-smi-before-gpu${device}.txt" || return 1
    used="$(parse_gpu_used_mib "$phase_dir/xpu-smi-before-gpu${device}.txt")"
    [[ -n "$used" ]] || return 1
    if [[ "$device" == "$GPU_INDEX" ]]; then
      ACTIVE_PRE_MIB="$used"
    fi
    if (( used > GPU_IDLE_MAX_MIB )); then
      echo "$phase preflight: GPU $device is not idle (${used} MiB)" >&2
      return 1
    fi
  done
  [[ -n "$ACTIVE_PRE_MIB" ]]
}

attest_server() {
  local phase_dir="$1"

  python3 - \
    "$phase_dir/server.stdout.log" \
    "$phase_dir/server.identity.log" \
    "$phase_dir/server-attestation.json" \
    "$EXPECTED_MODEL_SIZE" \
    "$EXPECTED_RUNTIME_SHA256" \
    "$MIN_POST_LOAD_FREE_MIB" <<'PY'
import json
import re
import sys

log_path, identity_path, out_path, model_size_raw, runtime_sha, min_free_raw = sys.argv[1:]
text = open(log_path, errors="replace").read()
identity_text = open(identity_path, errors="replace").read()
identity_header = identity_text.split("--- server ---", 1)[0]
identity = {}
for line in identity_header.splitlines():
    if "=" in line:
        key, value = line.split("=", 1)
        identity[key] = value

expected_identity = {
    "model_bytes": model_size_raw,
    "model_alias": "qwen36-27b-q8_0-target-only",
    "llama_server_sha256": runtime_sha,
    "ctx_size": "65536",
    "parallel_slots": "2",
    "ctx_size_per_slot": "32768",
    "kv_unified": "0",
    "cont_batching": "1",
    "batch_size": "1024",
    "ubatch_size": "128",
    "n_gpu_layers": "99",
    "threads": "8",
    "http_threads": "6",
    "log_verbosity": "4",
    "flash_attn": "on",
    "cache_type_k": "f16",
    "cache_type_v": "f16",
    "speculation": "none",
    "vision_projector": "none",
    "reasoning": "off",
    "ONEAPI_DEVICE_SELECTOR": "level_zero:*",
    "GGML_SYCL_ENABLE_VMM": "1",
    "GGML_SYCL_ENABLE_GRAPH": "0",
    "GGML_SYCL_ENABLE_DNN": "0",
    "GGML_SYCL_ENABLE_OPT": "1",
    "GGML_SYCL_FA_ONEDNN": "1",
    "GGML_SYCL_FA_ONEDNN_MAX_KV": "0",
    "GGML_SYCL_ENABLE_MKL_FA": "1",
    "GGML_SYCL_ENABLE_FLASH_ATTN": "1",
}
identity_fields = {
    key: identity.get(key) == value for key, value in expected_identity.items()
}
model_fd = identity.get("model_pinned_fd", "")
identity_fields["pinned_model_fd_contract"] = (
    model_fd.isdigit()
    and identity.get("model_load_path") == f"/proc/self/fd/{model_fd}"
    and str(identity.get("model_pinned_path", "")).startswith("/")
)
argv = identity.get("argv", "")
required_argv = (
    "-ngl 99",
    "-c 65536",
    "-np 2",
    "-b 1024",
    "-ub 128",
    "-ctk f16",
    "-ctv f16",
    "-fa on",
    "--spec-type none",
    "--reasoning off",
    "--ctx-checkpoints 0",
    "--cache-ram 0",
    "--no-cache-idle-slots",
    "--no-context-shift",
    "--no-kv-unified",
    "--cont-batching",
    "--slots",
    "--metrics",
    "--threads-http 6",
    "--jinja",
)
argv_fields = {value: value in argv for value in required_argv}

def context_value(name):
    values = re.findall(rf"llama_context:\s+{re.escape(name)}\s*=\s*([^\s]+)", text)
    return values[-1] if values else None

offload_pairs = [
    (int(left), int(right))
    for left, right in re.findall(r"offloaded\s+(\d+)/(\d+)\s+layers to GPU", text)
]
slot_matches = re.findall(
    r"initializing, n_slots = (\d+), n_ctx_slot = (\d+), kv_unified = '([^']+)'",
    text,
)
kv_matches = re.findall(
    r"llama_kv_cache: size =\s*([0-9.]+) MiB \(\s*(\d+) cells,\s*(\d+) layers,\s*(\d+)/(\d+) seqs\), K \(([^)]+)\):\s*([0-9.]+) MiB, V \(([^)]+)\):\s*([0-9.]+) MiB",
    text,
)
rs_matches = re.findall(
    r"llama_memory_recurrent: size =\s*([0-9.]+) MiB \(\s*(\d+) cells,\s*(\d+) layers,\s*(\d+) seqs",
    text,
)
fit_matches = [
    (int(free), int(required))
    for free, required in re.findall(
        r"will leave\s+(\d+)\s+>=\s+(\d+) MiB of free device memory", text
    )
]
kv = kv_matches[-1] if kv_matches else None
rs = rs_matches[-1] if rs_matches else None
fit_free_mib = fit_matches[-1][0] if fit_matches else None
min_free = int(min_free_raw)
runtime_fields = {
    "full_offload_65_of_65": (65, 65) in offload_pairs,
    "n_seq_max_2": context_value("n_seq_max") == "2",
    "n_ctx_65536": context_value("n_ctx") == "65536",
    "n_ctx_seq_32768": context_value("n_ctx_seq") == "32768",
    "n_batch_1024": context_value("n_batch") == "1024",
    "n_ubatch_128": context_value("n_ubatch") == "128",
    "flash_attn_enabled": context_value("flash_attn") == "enabled",
    "kv_unified_false": context_value("kv_unified") == "false",
    "two_slot_runtime": bool(slot_matches)
    and slot_matches[-1] == ("2", "32768", "false"),
    # With non-unified KV, llama.cpp reports the per-sequence cell capacity
    # followed by n_seq_max/n_stream.  The 4096-MiB total,
    # n_ctx=65536, n_ctx_seq=32768, and 2/2 sequence gates together attest the
    # full two-slot allocation; expecting 65536 in this per-sequence field is
    # incorrect for --no-kv-unified.
    "f16_kv_4096_mib": bool(kv)
    and abs(float(kv[0]) - 4096.0) <= 0.1
    and kv[1:5] == ("32768", "16", "2", "2")
    and kv[5] == "f16"
    and abs(float(kv[6]) - 2048.0) <= 0.1
    and kv[7] == "f16"
    and abs(float(kv[8]) - 2048.0) <= 0.1,
    "two_slot_recurrent_state": bool(rs)
    and 298.0 <= float(rs[0]) <= 301.0
    and rs[1:] == ("2", "64", "2"),
    "post_fit_free_at_least_minimum": isinstance(fit_free_mib, int)
    and fit_free_mib >= min_free,
    "prompt_cache_disabled": "prompt cache is disabled" in text,
    "context_checkpoints_disabled": "context checkpoints disabled" in text,
    "speculation_disabled": "no implementations specified for speculative decoding" in text,
}
result = {
    "expected_identity": expected_identity,
    "identity_fields": identity_fields,
    "argv_fields": argv_fields,
    "runtime_fields": runtime_fields,
    "observed": {
        "offload_pairs": offload_pairs,
        "slot_config": slot_matches[-1] if slot_matches else None,
        "kv_config": kv,
        "recurrent_config": rs,
        "fit_free_mib": fit_free_mib,
        "minimum_fit_free_mib": min_free,
    },
}
result["passed"] = (
    all(identity_fields.values())
    and all(argv_fields.values())
    and all(runtime_fields.values())
)
open(out_path, "w").write(json.dumps(result, indent=2, sort_keys=True) + "\n")
if not result["passed"]:
    raise SystemExit("server identity/fit/offload attestation failed")
PY
}

start_phase() {
  local phase="$1"
  local phase_dir="$RUN_DIR/$phase"
  local deadline
  local loaded_mib

  [[ -z "$ACTIVE_PHASE" && -z "$SERVER_PID" && -z "$CLIENT_PID" ]] || die "cannot start $phase while another phase is active"
  if ss -H -ltn "sport = :$PORT" | grep -q .; then
    die "port already in use before $phase: $PORT"
  fi
  mkdir -p "$phase_dir"
  ACTIVE_PHASE="$phase"
  ACTIVE_PHASE_DIR="$phase_dir"
  ACTIVE_EXPECTED_RUNNING=0
  check_phase_idle "$phase" "$phase_dir" || die "$phase idle preflight failed"
  check_host_memory "$phase-preload" || die "$phase host-memory preflight failed"
  verify_harness_inputs "${phase}-server" || die "$phase harness inputs changed before server launch"
  verify_runtime_bundle_snapshot "${phase}-prelaunch" || die "$phase runtime bundle changed before server launch"
  verify_model_stat "${phase}-prelaunch" || die "$phase model identity changed before server launch"

  GPU_INDEX="$GPU_INDEX" \
  PORT="$PORT" \
  MODEL="$MODEL" \
  MODEL_ALIAS="$MODEL_ALIAS" \
  LLAMA_SERVER="$LLAMA_SERVER" \
  RUNTIME_MANIFEST="$RUNTIME_MANIFEST" \
  CTX_SIZE="$CTX_SIZE" \
  PARALLEL_SLOTS="$PARALLEL_SLOTS" \
  KV_UNIFIED="$KV_UNIFIED" \
  CONT_BATCHING="$CONT_BATCHING" \
  BATCH_SIZE="$BATCH_SIZE" \
  UBATCH_SIZE="$UBATCH_SIZE" \
  N_GPU_LAYERS="$N_GPU_LAYERS" \
  THREADS="$THREADS" \
  HTTP_THREADS="$HTTP_THREADS" \
  POLL="$POLL" \
  LOG_VERBOSITY="$LOG_VERBOSITY" \
  CACHE_TYPE_K="$CACHE_TYPE_K" \
  CACHE_TYPE_V="$CACHE_TYPE_V" \
  FLASH_ATTN="$FLASH_ATTN" \
  LANE_DNN_ENABLED="$LANE_DNN_ENABLED" \
  LANE_OPT_ENABLED="$LANE_OPT_ENABLED" \
  LANE_FA_ONEDNN="$LANE_FA_ONEDNN" \
  LANE_FA_ONEDNN_MAX_KV="$LANE_FA_ONEDNN_MAX_KV" \
  LANE_MKL_FA="$LANE_MKL_FA" \
  LANE_SYCL_FLASH_ATTN="$LANE_SYCL_FLASH_ATTN" \
  LOG="$phase_dir/server.identity.log" \
  SERVER_OUTPUT_LOG="$phase_dir/server.stdout.log" \
  OUT_DIR="$phase_dir" \
    "$SERVER_LAUNCHER" > "$phase_dir/server.stdout.log" 2>&1 &
  SERVER_PID=$!
  SERVER_LAUNCH_COUNT=$((SERVER_LAUNCH_COUNT + 1))
  {
    echo "phase=$phase"
    echo "server_pid=$SERVER_PID"
    echo "server_launch_ordinal=$SERVER_LAUNCH_COUNT"
    echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } > "$phase_dir/server-launch.env"
  printf '%s\n' "$SERVER_PID" > "$phase_dir/server.pid"

  deadline=$((SECONDS + READINESS_TIMEOUT_S))
  until curl -fsS "http://127.0.0.1:${PORT}/v1/models" > "$phase_dir/models.json" 2> "$phase_dir/models.err"; do
    kill -0 "$SERVER_PID" 2>/dev/null || die "$phase server exited before readiness"
    (( SECONDS < deadline )) || die "$phase server readiness timeout"
    sleep 2
  done
  ACTIVE_EXPECTED_RUNNING=1
  jq -e --arg alias "$MODEL_ALIAS" '
    (.data | length) == 1
    and .data[0].id == $alias
    and .data[0].meta.n_ctx == 32768
    and .data[0].meta.ftype == "Q8_0"
    and .data[0].meta.n_params == 26895998464
  ' "$phase_dir/models.json" >/dev/null || die "$phase model endpoint identity failed"

  attest_server "$phase_dir" || die "$phase server attestation failed"
  sample_gpu "$GPU_INDEX" "$phase_dir/xpu-smi-loaded.txt" || die "$phase loaded VRAM sample failed"
  loaded_mib="$(parse_gpu_used_mib "$phase_dir/xpu-smi-loaded.txt")"
  [[ -n "$loaded_mib" ]] || die "$phase loaded VRAM value is missing"
  python3 - \
    "$phase_dir/server-attestation.json" \
    "$phase_dir/vram-fit-check.json" \
    "$ACTIVE_PRE_MIB" \
    "$loaded_mib" \
    "$MIN_LOADED_DELTA_MIB" \
    "$MIN_POST_LOAD_FREE_MIB" <<'PY'
import json
import sys

attestation_path, out_path, pre_raw, loaded_raw, delta_raw, free_raw = sys.argv[1:]
attestation = json.load(open(attestation_path))
pre = int(pre_raw)
loaded = int(loaded_raw)
minimum_delta = int(delta_raw)
minimum_free = int(free_raw)
fit_free = attestation.get("observed", {}).get("fit_free_mib")
result = {
    "pre_mib": pre,
    "loaded_mib": loaded,
    "loaded_delta_mib": loaded - pre,
    "minimum_loaded_delta_mib": minimum_delta,
    "fit_free_mib": fit_free,
    "minimum_fit_free_mib": minimum_free,
}
result["passed"] = (
    loaded - pre >= minimum_delta
    and isinstance(fit_free, int)
    and fit_free >= minimum_free
)
open(out_path, "w").write(json.dumps(result, indent=2, sort_keys=True) + "\n")
if not result["passed"]:
    raise SystemExit("loaded VRAM or free-reserve gate failed")
PY
  kill -0 "$SERVER_PID" 2>/dev/null || die "$phase server died after readiness"
  verify_model_stat "${phase}-loaded" || die "$phase model identity changed during model load"
}

run_capture_phase() {
  local mode="$1"
  local out_path="$2"
  local oracle_path="${3:-}"
  local phase_dir="$ACTIVE_PHASE_DIR"
  local -a args

  args=(
    timeout --signal=TERM --kill-after=30 "$CLIENT_TIMEOUT_S"
    python3 "$CAPTURE"
    --mode "$mode"
    --base-url "http://127.0.0.1:${PORT}"
    --suite "$SUITE"
    --band "$BAND"
    --prompt-builder "$PROMPT_BUILDER"
    --common-script "$COMMON_CAPTURE"
    --server-attestation "$phase_dir/server-attestation.json"
    --baseline-canary-suite "$SEALED_128_SUITE"
    --baseline-canary-oracle "$SEALED_128_ORACLE_SNAPSHOT"
    --baseline-canary-oracle-sha256 "$SEALED_128_ORACLE_SHA256"
    --baseline-canary-prompt-id "$SEALED_128_CANARY_PROMPT_ID"
    --out "$out_path"
    --timeout "$REQUEST_TIMEOUT_S"
    --model-sha256 "$EXPECTED_MODEL_SHA256"
    --runtime-sha256 "$EXPECTED_RUNTIME_SHA256"
    --cache-type-k "$CACHE_TYPE_K"
    --cache-type-v "$CACHE_TYPE_V"
    --ctx-size-total "$CTX_SIZE"
    --ctx-size-per-slot "$CTX_SIZE_PER_SLOT"
  )
  if [[ -n "$oracle_path" ]]; then
    args+=(--oracle-json "$oracle_path")
  fi
  if [[ "$mode" == "concurrent" ]]; then
    args+=(--case-order "$CONCURRENT_CASE_ORDER")
  fi
  verify_harness_inputs "${mode}-capture" || return 1
  "${args[@]}" > "$phase_dir/capture.stdout.log" 2> "$phase_dir/capture.stderr.log" &
  CLIENT_PID=$!
  printf '%s\n' "$CLIENT_PID" > "$phase_dir/client.pid"
  if ! wait "$CLIENT_PID"; then
    CLIENT_PID=""
    return 1
  fi
  CLIENT_PID=""
}

"$VALIDATOR_PYTHON" - > "$RUN_DIR/validator-python-packages.json" \
  2> "$RUN_DIR/validator-python-packages.stderr.log" <<'PY'
import json
import sys
from importlib.metadata import version

import jinja2
import transformers

print(json.dumps({
    "executable": sys.executable,
    "python": sys.version,
    "packages": {
        "jinja2": version("jinja2"),
        "transformers": version("transformers"),
    },
}, indent=2, sort_keys=True))
PY

capture_model_stat "$RUN_DIR/model-stat-before-initial-hash.json"
printf '%s  %s\n' "$EXPECTED_MODEL_SHA256" "$MODEL_FD_PATH" | sha256sum -c - |
  tee "$RUN_DIR/model-sha256-check.txt"
capture_model_stat "$RUN_DIR/model-stat-after-initial-hash.json"
cmp -s "$RUN_DIR/model-stat-before-initial-hash.json" \
  "$RUN_DIR/model-stat-after-initial-hash.json" || die "model identity changed during initial SHA-256 verification"
cp "$RUN_DIR/model-stat-after-initial-hash.json" "$RUN_DIR/model-stat-baseline.json"
MODEL_STAT_BASELINE_READY=1
printf '%s  %s\n' "$EXPECTED_RUNTIME_SHA256" "$LLAMA_SERVER" | sha256sum -c - |
  tee "$RUN_DIR/runtime-sha256-check.txt"
set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null
set -u
RUNTIME_VERSION="$($LLAMA_SERVER --version 2>&1)"
grep -Fqx "$EXPECTED_RUNTIME_VERSION" <<< "$RUNTIME_VERSION" || die "llama-server version does not match the runtime manifest"
printf '%s\n' "$RUNTIME_VERSION" > "$RUN_DIR/runtime-version.txt"
LLAMA_SERVER="$LLAMA_SERVER" \
RUNTIME_MANIFEST="$RUNTIME_MANIFEST" \
  "$SERVER_LAUNCHER" --verify-runtime-bundle \
    "$RUN_DIR/llama-server-ldd-initial-post-oneapi.txt" \
    "$RUN_DIR/runtime-resolved-files.sha256" \
    "$RUN_DIR/runtime-bundle-initial.json"
RUNTIME_BUNDLE_REPORT_SHA256="$(sha256sum "$RUN_DIR/runtime-bundle-initial.json" | awk '{print $1}')"
RUNTIME_RESOLVED_MANIFEST_SHA256="$(sha256sum "$RUN_DIR/runtime-resolved-files.sha256" | awk '{print $1}')"
RUNTIME_BUNDLE_READY=1

xpu-smi discovery -j > "$RUN_DIR/xpu-smi-discovery.json"
jq -e --argjson selected "$GPU_INDEX" '
  ([.device_list[] |
    select(.device_function_type == "physical" and (.device_name | contains("Arc(TM) Pro B70"))) |
    {device_id, pci_bdf_address, uuid, device_name}] | length) == 4
  and ([.device_list[] |
    select(.device_function_type == "physical" and (.device_name | contains("Arc(TM) Pro B70"))) |
    .device_id] | sort) == [0, 1, 2, 3]
  and ([.device_list[] |
    select(.device_function_type == "physical" and (.device_name | contains("Arc(TM) Pro B70"))) |
    .pci_bdf_address] | unique | length) == 4
  and ([.device_list[] |
    select(.device_function_type == "physical" and (.device_name | contains("Arc(TM) Pro B70"))) |
    .uuid] | unique | length) == 4
  and ([.device_list[] |
    select(.device_id == $selected and .device_function_type == "physical" and (.device_name | contains("Arc(TM) Pro B70")))] | length) == 1
' "$RUN_DIR/xpu-smi-discovery.json" >/dev/null || die "four-card or selected-GPU identity check failed"
jq '[.device_list[] |
  select(.device_function_type == "physical" and (.device_name | contains("Arc(TM) Pro B70"))) |
  {device_id, pci_bdf_address, uuid, device_name}] | sort_by(.device_id)' \
  "$RUN_DIR/xpu-smi-discovery.json" > "$RUN_DIR/gpu-identities.json"

for device in 0 1 2 3; do
  if [[ "$device" != "$GPU_INDEX" && "$REQUIRE_ALL_GPUS_IDLE" == "0" ]]; then
    continue
  fi
  sample_gpu "$device" "$RUN_DIR/xpu-smi-preflight-gpu${device}.txt" || die "GPU $device preflight sample failed"
  used="$(parse_gpu_used_mib "$RUN_DIR/xpu-smi-preflight-gpu${device}.txt")"
  [[ -n "$used" ]] || die "GPU $device preflight VRAM value is missing"
  (( used <= GPU_IDLE_MAX_MIB )) || die "GPU $device is not idle (${used} MiB)"
  if [[ "$device" == "$GPU_INDEX" ]]; then
    INITIAL_SELECTED_MIB="$used"
  fi
done
[[ -n "$INITIAL_SELECTED_MIB" ]] || die "selected-GPU preflight was not retained"
check_host_memory preflight || die "host-memory preflight failed"

uname -a > "$RUN_DIR/uname.txt"
xpu-smi -v > "$RUN_DIR/xpu-smi-version.txt" 2>&1 || true
dpkg-query -W 2>/dev/null |
  grep -Ei 'intel.*(level-zero|oneapi|compute-runtime|igc)|xpu-smi|libze' \
    > "$RUN_DIR/accelerator-packages.txt" || true
modinfo xe > "$RUN_DIR/xe-modinfo.txt" 2>&1 || true
git -C "$ROOT" rev-parse HEAD > "$RUN_DIR/repository-head.txt"
git -C "$ROOT" status --short > "$RUN_DIR/repository-status.txt"
sha256sum \
  "$MODEL_MANIFEST" "$RUNTIME_MANIFEST" "$SUITE" "$CAPTURE" \
  "$COMMON_CAPTURE" "$SUITE_VALIDATOR" "$PROMPT_BUILDER" \
  "$SERVER_LAUNCHER" "$SEALED_128_SUITE" "$SEALED_128_ORACLE" \
  "$SEALED_128_ORACLE_SNAPSHOT" "${BASH_SOURCE[0]}" \
  > "$RUN_DIR/harness-inputs.sha256"
HARNESS_MANIFEST_SHA256="$(sha256sum "$RUN_DIR/harness-inputs.sha256" | awk '{print $1}')"
HARNESS_MANIFEST_READY=1
verify_harness_inputs initial || die "initial harness-input verification failed"

verify_harness_inputs suite-validator || die "harness inputs changed before suite validation"
"$VALIDATOR_PYTHON" "$SUITE_VALIDATOR" \
  --suite "$SUITE" \
  --tokenizer "$TOKENIZER" \
  --prompt-builder "$PROMPT_BUILDER" \
  --ctx-size "$CTX_SIZE_PER_SLOT" \
  --output-tokens 512 \
  --out "$RUN_DIR/suite-validation.json" \
    > "$RUN_DIR/suite-validation.stdout.log" 2> "$RUN_DIR/suite-validation.stderr.log"
jq -e '.passed == true and (.rows | length) == 6' "$RUN_DIR/suite-validation.json" >/dev/null || die "c2 suite calibration failed"

{
  echo "date_utc=$STAMP"
  echo "scope=fresh-server sequential c2 oracle followed by fresh-server concurrent c2 comparison"
  echo "band=$BAND"
  echo "gpu_index=$GPU_INDEX"
  echo "port=$PORT"
  echo "model=$MODEL"
  echo "model_bytes=$EXPECTED_MODEL_SIZE"
  echo "model_sha256=$EXPECTED_MODEL_SHA256"
  echo "model_alias=$MODEL_ALIAS"
  echo "llama_server=$LLAMA_SERVER"
  echo "llama_server_sha256=$EXPECTED_RUNTIME_SHA256"
  echo "runtime_manifest=$RUNTIME_MANIFEST"
  echo "runtime_manifest_sha256=$(sha256sum "$RUNTIME_MANIFEST" | awk '{print $1}')"
  echo "runtime_bundle_report_sha256=$RUNTIME_BUNDLE_REPORT_SHA256"
  echo "runtime_resolved_files_manifest_sha256=$RUNTIME_RESOLVED_MANIFEST_SHA256"
  echo "runtime_bundle_dependency_count=$(jq -r '.dependency_count' "$RUN_DIR/runtime-bundle-initial.json")"
  echo "runtime_bundle_origin_shared_object_count=$(jq -r '.origin_shared_object_count' "$RUN_DIR/runtime-bundle-initial.json")"
  echo "tokenizer=$TOKENIZER"
  echo "tokenizer_revision=$EXPECTED_TOKENIZER_REVISION"
  echo "validator_python=$VALIDATOR_PYTHON"
  echo "concurrent_case_order=$CONCURRENT_CASE_ORDER"
  echo "suite=$SUITE"
  echo "suite_sha256=$(sha256sum "$SUITE" | awk '{print $1}')"
  echo "external_baseline_canary_suite=$SEALED_128_SUITE"
  echo "external_baseline_canary_oracle=$SEALED_128_ORACLE_SNAPSHOT"
  echo "external_baseline_canary_oracle_sha256=$SEALED_128_ORACLE_SHA256"
  echo "external_baseline_canary_prompt_id=$SEALED_128_CANARY_PROMPT_ID"
  echo "ctx_size_total=$CTX_SIZE"
  echo "ctx_size_per_slot=$CTX_SIZE_PER_SLOT"
  echo "parallel_slots=$PARALLEL_SLOTS"
  echo "kv_unified=$KV_UNIFIED"
  echo "cont_batching=$CONT_BATCHING"
  echo "cache_type_k=$CACHE_TYPE_K"
  echo "cache_type_v=$CACHE_TYPE_V"
  echo "batch_size=$BATCH_SIZE"
  echo "ubatch_size=$UBATCH_SIZE"
  echo "n_gpu_layers=$N_GPU_LAYERS"
  echo "threads=$THREADS"
  echo "http_threads=$HTTP_THREADS"
  echo "poll=$POLL"
  echo "log_verbosity=$LOG_VERBOSITY"
  echo "sycl_dnn_enabled=$LANE_DNN_ENABLED"
  echo "sycl_opt_enabled=$LANE_OPT_ENABLED"
  echo "sycl_vmm_enabled=1"
  echo "sycl_graph_enabled=0"
  echo "flash_attn=$FLASH_ATTN"
  echo "min_post_load_free_mib=$MIN_POST_LOAD_FREE_MIB"
  echo "min_loaded_delta_mib=$MIN_LOADED_DELTA_MIB"
  echo "require_all_gpus_idle=$REQUIRE_ALL_GPUS_IDLE"
  echo "model_pinned_fd=$QWEN36_MODEL_FD"
  echo "model_pinned_path=$(readlink -f "$MODEL_FD_PATH")"
  echo "timing_identity=512-token conventional 511-interval window"
  echo "performance_thresholds_are_separate_from_evidence_validity=1"
  echo "primary_aggregate_decode_tok_s_min=30"
  echo "primary_each_request_decode_tok_s_min=13"
  echo "primary_aggregate_prompt_tok_s_min=400"
  echo "stretch_aggregate_decode_tok_s_min=35"
  echo "stretch_each_request_decode_tok_s_min=16"
} > "$RUN_DIR/run-identity.env"

start_phase sequential-oracle
run_capture_phase sequential-oracle "$RUN_DIR/sequential-oracle/oracle.json" || die "sequential c2 oracle capture failed"
jq -e \
  --arg oracle_sha "$SEALED_128_ORACLE_SHA256" \
  --arg suite_sha "$SEALED_128_SUITE_SHA256" \
  --arg prompt_id "$SEALED_128_CANARY_PROMPT_ID" '
  .intrinsic_gate.passed == true
  and .intrinsic_gate.semantic_retrieval_passed == true
  and .intrinsic_gate.external_baseline_canary_passed == true
  and ([.semantic_retrieval[].passed] == [true, true])
  and ([.external_baseline_canaries[].passed] == [true, true])
  and ([.external_baseline_canaries[].slot_id_requested] == [0, 1])
  and .run_identity.baseline_canary_oracle_sha256 == $oracle_sha
  and .run_identity.baseline_canary_suite_sha256 == $suite_sha
  and .run_identity.baseline_canary_prompt_id == $prompt_id
  and all(.external_baseline_canaries[];
    .oracle_sha256 == $oracle_sha
    and .suite_sha256 == $suite_sha
    and .prompt_id == $prompt_id)
  and .decode_occupancy.passed == true
  and .slot_topology.passed == true
  and .oracle_comparison.status == "BASELINE_CAPTURE_READY"
  and .run_identity.mode == "sequential-oracle"
  and .run_identity.case_order == "forward"
  and .run_identity.parallel_slots == 2
  and .run_identity.ctx_size_total == 65536
  and .run_identity.ctx_size_per_slot == 32768
  and .run_identity.cache_type_k == "f16"
  and .run_identity.cache_type_v == "f16"
' "$RUN_DIR/sequential-oracle/oracle.json" >/dev/null || die "sequential oracle gate failed"
stop_active_phase || die "sequential-oracle cleanup failed; concurrent phase was not started"
verify_runtime_bundle_snapshot sequential-poststop || die "runtime bundle changed during sequential-oracle phase"
sha256sum "$RUN_DIR/sequential-oracle/oracle.json" > "$RUN_DIR/sequential-oracle/oracle.sha256"
sha256sum -c "$RUN_DIR/sequential-oracle/oracle.sha256" \
  > "$RUN_DIR/sequential-oracle/oracle-sha256-check.txt" || die "sequential oracle seal check failed"

start_phase concurrent
run_capture_phase concurrent "$RUN_DIR/concurrent/result.json" "$RUN_DIR/sequential-oracle/oracle.json" || die "concurrent c2 capture failed"
jq -e \
  --arg case_order "$CONCURRENT_CASE_ORDER" \
  --arg oracle_sha "$SEALED_128_ORACLE_SHA256" \
  --arg suite_sha "$SEALED_128_SUITE_SHA256" \
  --arg prompt_id "$SEALED_128_CANARY_PROMPT_ID" '
  .intrinsic_gate.passed == true
  and .intrinsic_gate.semantic_retrieval_passed == true
  and .intrinsic_gate.external_baseline_canary_passed == true
  and ([.semantic_retrieval[].passed] == [true, true])
  and ([.external_baseline_canaries[].passed] == [true, true])
  and ([.external_baseline_canaries[].slot_id_requested] == [0, 1])
  and .run_identity.baseline_canary_oracle_sha256 == $oracle_sha
  and .run_identity.baseline_canary_suite_sha256 == $suite_sha
  and .run_identity.baseline_canary_prompt_id == $prompt_id
  and all(.external_baseline_canaries[];
    .oracle_sha256 == $oracle_sha
    and .suite_sha256 == $suite_sha
    and .prompt_id == $prompt_id)
  and .intrinsic_gate.overlap_passed == true
  and .decode_occupancy.passed == true
  and .slot_topology.passed == true
  and .oracle_comparison.passed == true
  and .oracle_comparison.status == "PASS_ORACLE_EXACT"
  and .aggregate.broad_decode_overlap == true
  and .run_identity.mode == "concurrent"
  and .run_identity.case_order == $case_order
  and .run_identity.parallel_slots == 2
  and .run_identity.ctx_size_total == 65536
  and .run_identity.ctx_size_per_slot == 32768
  and .run_identity.cache_type_k == "f16"
  and .run_identity.cache_type_v == "f16"
' "$RUN_DIR/concurrent/result.json" >/dev/null || die "concurrent exactness/overlap gate failed"
stop_active_phase || die "concurrent cleanup failed"
verify_runtime_bundle_snapshot concurrent-poststop || die "runtime bundle changed during concurrent phase"

[[ "$SERVER_LAUNCH_COUNT" == "2" ]] || die "expected exactly two fresh server launches"
[[ "${PHASE_CLEANUP_PASSED[sequential-oracle]:-0}" == "1" ]] || die "sequential phase did not clean up"
[[ "${PHASE_CLEANUP_PASSED[concurrent]:-0}" == "1" ]] || die "concurrent phase did not clean up"
BODY_COMPLETED=1
