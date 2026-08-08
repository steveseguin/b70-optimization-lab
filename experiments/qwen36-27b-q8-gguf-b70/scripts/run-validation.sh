#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LANE="$ROOT/experiments/qwen36-27b-q8-gguf-b70"
MANIFEST="$LANE/model-manifest.json"
RUNTIME_MANIFEST="${RUNTIME_MANIFEST:-$LANE/runtime-manifest.json}"

GPU_INDEX="${GPU_INDEX:-0}"
PORT="${PORT:-19460}"
RUN_SCOPE="${RUN_SCOPE:-smoke}"
CACHE_TYPE_K="${CACHE_TYPE_K:-f16}"
CACHE_TYPE_V="${CACHE_TYPE_V:-f16}"
MODEL="${MODEL:-/mnt/usb-models/models/qwen36-27b-q8-gguf/Qwen3.6-27B-Q8_0.gguf}"
MODEL_ALIAS="${MODEL_ALIAS:-qwen36-27b-q8_0-target-only}"
LLAMA_SERVER="${LLAMA_SERVER:-/dev/shm/llama.cpp-pr19-15586/build-sycl/bin/llama-server}"
VERIFY_MODEL_SHA256="${VERIFY_MODEL_SHA256:-1}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}"
GPU_IDLE_MAX_MIB="${GPU_IDLE_MAX_MIB:-256}"
REQUIRE_ALL_GPUS_IDLE="${REQUIRE_ALL_GPUS_IDLE:-1}"
CASE_ID="${CASE_ID:-}"
ORACLE_JSON="${ORACLE_JSON:-}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LABEL="${LABEL:-qwen36-27b-q8_0-${CACHE_TYPE_K}kv-${RUN_SCOPE}}"
RUN_DIR="${RUN_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/${LABEL}-${STAMP}}"

case "$RUN_SCOPE" in
  smoke|short|long|full) ;;
  *)
    echo "invalid RUN_SCOPE=$RUN_SCOPE; expected smoke, short, long, or full" >&2
    exit 2
    ;;
esac
if [[ ! "$GPU_INDEX" =~ ^[0-3]$ ]]; then
  echo "GPU_INDEX must be 0, 1, 2, or 3" >&2
  exit 2
fi
if [[ "$REQUIRE_ALL_GPUS_IDLE" != "0" && "$REQUIRE_ALL_GPUS_IDLE" != "1" ]]; then
  echo "REQUIRE_ALL_GPUS_IDLE must be 0 or 1" >&2
  exit 2
fi
if [[ ! "$GPU_IDLE_MAX_MIB" =~ ^[0-9]+$ ]]; then
  echo "GPU_IDLE_MAX_MIB must be a nonnegative integer" >&2
  exit 2
fi

if [[ -z "${CTX_SIZE:-}" ]]; then
  case "$RUN_SCOPE" in
    smoke|short) CTX_SIZE=4096 ;;
    long|full) CTX_SIZE=32768 ;;
  esac
fi
if [[ ! "$CTX_SIZE" =~ ^[0-9]+$ ]] || (( CTX_SIZE <= 0 )); then
  echo "CTX_SIZE must be a positive integer" >&2
  exit 2
fi
if [[ "$RUN_SCOPE" == "smoke" || "$RUN_SCOPE" == "short" ]] && (( CTX_SIZE > 4096 )); then
  echo "$RUN_SCOPE requires CTX_SIZE<=4096; use long or full for the 32K allocation gate" >&2
  exit 2
fi
if [[ "$RUN_SCOPE" == "long" || "$RUN_SCOPE" == "full" ]] && (( CTX_SIZE != 32768 )); then
  echo "$RUN_SCOPE requires CTX_SIZE=32768" >&2
  exit 2
fi
if [[ "$VERIFY_MODEL_SHA256" != "1" ]]; then
  echo "VERIFY_MODEL_SHA256=1 is required for this validation runner" >&2
  exit 2
fi

EXPECTED_SHA256="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["sha256"])' "$MANIFEST")"
EXPECTED_SIZE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["size_bytes"])' "$MANIFEST")"
EXPECTED_RUNTIME_SHA256="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["llama_server_sha256"])' "$RUNTIME_MANIFEST")"
if [[ ! -f "$MODEL" ]]; then
  echo "model not found: $MODEL" >&2
  exit 2
fi
ACTUAL_SIZE="$(stat -c %s "$MODEL")"
if [[ "$ACTUAL_SIZE" != "$EXPECTED_SIZE" ]]; then
  echo "model size mismatch: expected $EXPECTED_SIZE, got $ACTUAL_SIZE" >&2
  exit 2
fi

if [[ -e "$RUN_DIR" ]]; then
  echo "RUN_DIR already exists: $RUN_DIR" >&2
  exit 2
fi
mkdir -p "$RUN_DIR"
START_EPOCH="$(date +%s)"
SERVER_PID=""
CLEANUP_FORCED=0
PRE_GPU_USED_MIB=""

cleanup() {
  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    for _ in $(seq 1 30); do
      kill -0 "$SERVER_PID" 2>/dev/null || break
      sleep 1
    done
    if kill -0 "$SERVER_PID" 2>/dev/null; then
      CLEANUP_FORCED=1
      kill -KILL "$SERVER_PID" 2>/dev/null || true
    fi
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}

on_exit() {
  original_status=$?
  trap - EXIT
  cleanup
  final_status=$original_status
  if command -v xpu-smi >/dev/null 2>&1; then
    timeout 20 xpu-smi stats -d "$GPU_INDEX" > "$RUN_DIR/xpu-smi-final.txt" 2>&1 || true
  fi
  journalctl -k --since "@$START_EPOCH" --no-pager 2>/dev/null |
    grep -Ei 'xe.*(reset|wedg|fault|hang|timedout|device lost)|GuC.*reset|Fault response|VM.*fault|PCIe.*AER|UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST' \
      > "$RUN_DIR/device-error-scan.txt" || true
  grep -Ei 'UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST|out of memory|segmentation fault|core dumped|Aborted' \
    "$RUN_DIR/server.stdout.log" > "$RUN_DIR/server-error-scan.txt" 2>/dev/null || true
  if (( CLEANUP_FORCED != 0 )); then
    echo "forced_kill=1" > "$RUN_DIR/cleanup-status.txt"
    final_status=1
  else
    echo "forced_kill=0" > "$RUN_DIR/cleanup-status.txt"
  fi
  if ss -H -ltn "sport = :$PORT" | grep -q .; then
    echo "port_closed=0" >> "$RUN_DIR/cleanup-status.txt"
    final_status=1
  else
    echo "port_closed=1" >> "$RUN_DIR/cleanup-status.txt"
  fi
  if [[ -s "$RUN_DIR/device-error-scan.txt" ]]; then
    final_status=1
  fi
  if [[ -s "$RUN_DIR/server-error-scan.txt" ]]; then
    final_status=1
  fi
  final_used="$(awk -F '|' '/GPU Memory Used/{gsub(/[^0-9.]/, "", $3); print int($3); exit}' "$RUN_DIR/xpu-smi-final.txt" 2>/dev/null || true)"
  vram_returned=0
  if [[ -n "$final_used" && -n "$PRE_GPU_USED_MIB" ]]; then
    if (( final_used <= PRE_GPU_USED_MIB + GPU_IDLE_MAX_MIB )); then
      vram_returned=1
    fi
  fi
  if (( vram_returned == 0 )); then
    echo "vram_returned=0 pre_mib=${PRE_GPU_USED_MIB:-unknown} final_mib=${final_used:-unknown}" >> "$RUN_DIR/cleanup-status.txt"
    final_status=1
  else
    echo "vram_returned=1 pre_mib=$PRE_GPU_USED_MIB final_mib=$final_used" >> "$RUN_DIR/cleanup-status.txt"
  fi
  printf 'original_status=%s\nfinal_status=%s\n' "$original_status" "$final_status" > "$RUN_DIR/exit-status.txt"
  if (( final_status == 0 )); then
    printf 'PASS\n' > "$RUN_DIR/run-status.txt"
  else
    printf 'FAIL\n' > "$RUN_DIR/run-status.txt"
  fi
  exit "$final_status"
}
trap on_exit EXIT

printf '%s  %s\n' "$EXPECTED_SHA256" "$MODEL" | sha256sum -c - |
  tee "$RUN_DIR/model-sha256-check.txt"

command -v xpu-smi >/dev/null 2>&1 || { echo "xpu-smi is required" >&2; exit 2; }
xpu-smi discovery -j > "$RUN_DIR/xpu-smi-discovery.json"
xpu-smi -v > "$RUN_DIR/xpu-smi-version.txt" 2>&1 || true
uname -a > "$RUN_DIR/uname.txt"
ldd "$LLAMA_SERVER" > "$RUN_DIR/llama-server-ldd.txt"
dpkg-query -W 2>/dev/null |
  grep -Ei 'intel.*(level-zero|oneapi|compute-runtime|igc)|xpu-smi|libze' \
    > "$RUN_DIR/accelerator-packages.txt" || true
jq -e --argjson device "$GPU_INDEX" '
  [.device_list[] | select(.device_id == $device and .device_function_type == "physical" and (.device_name | contains("Arc(TM) Pro B70")))] | length == 1
' "$RUN_DIR/xpu-smi-discovery.json" >/dev/null
jq --argjson device "$GPU_INDEX" -r '
  .device_list[] | select(.device_id == $device) | "gpu_bdf=" + .pci_bdf_address + "\ngpu_uuid=" + .uuid + "\ngpu_name=" + .device_name
' "$RUN_DIR/xpu-smi-discovery.json" > "$RUN_DIR/gpu-identity.env"
GPU_BDF="$(awk -F= '$1 == "gpu_bdf" {print $2}' "$RUN_DIR/gpu-identity.env")"
if [[ -z "$GPU_BDF" || ! -e "/sys/bus/pci/devices/$GPU_BDF" ]]; then
  echo "selected GPU sysfs identity is missing: ${GPU_BDF:-unknown}" >&2
  exit 2
fi
readlink -f "/sys/bus/pci/devices/$GPU_BDF/driver" \
  > "$RUN_DIR/gpu-driver-sysfs-path.txt"
modinfo xe > "$RUN_DIR/xe-modinfo.txt" 2>&1 || true

for device in 0 1 2 3; do
  timeout 20 xpu-smi stats -d "$device" > "$RUN_DIR/xpu-smi-before-gpu${device}.txt"
  used="$(awk -F '|' '/GPU Memory Used/{gsub(/[^0-9.]/, "", $3); print int($3); exit}' "$RUN_DIR/xpu-smi-before-gpu${device}.txt")"
  if [[ -z "$used" ]]; then
    echo "could not parse GPU memory for device $device" >&2
    exit 2
  fi
  if [[ "$device" == "$GPU_INDEX" ]]; then
    PRE_GPU_USED_MIB="$used"
  fi
  if [[ "$device" == "$GPU_INDEX" || "$REQUIRE_ALL_GPUS_IDLE" == "1" ]]; then
    if (( used > GPU_IDLE_MAX_MIB )); then
      echo "GPU $device is not idle: ${used} MiB used" >&2
      exit 2
    fi
  fi
done

{
  echo "date_utc=$STAMP"
  echo "run_scope=$RUN_SCOPE"
  echo "gpu_index=$GPU_INDEX"
  echo "port=$PORT"
  echo "model=$MODEL"
  echo "model_bytes=$ACTUAL_SIZE"
  echo "expected_model_sha256=$EXPECTED_SHA256"
  echo "model_sha256_verified=$VERIFY_MODEL_SHA256"
  echo "model_alias=$MODEL_ALIAS"
  echo "llama_server=$LLAMA_SERVER"
  echo "llama_server_sha256=$EXPECTED_RUNTIME_SHA256"
  echo "runtime_manifest=$RUNTIME_MANIFEST"
  echo "ctx_size=$CTX_SIZE"
  echo "cache_type_k=$CACHE_TYPE_K"
  echo "cache_type_v=$CACHE_TYPE_V"
  echo "speculation=none"
  echo "vision_projector=none"
  echo "case_id=${CASE_ID:-<scope-default>}"
  echo "oracle_json=${ORACLE_JSON:-<baseline-capture>}"
  echo "require_all_gpus_idle=$REQUIRE_ALL_GPUS_IDLE"
  cat "$RUN_DIR/gpu-identity.env"
} > "$RUN_DIR/run-identity.env"

GPU_INDEX="$GPU_INDEX" \
PORT="$PORT" \
MODEL="$MODEL" \
MODEL_ALIAS="$MODEL_ALIAS" \
LLAMA_SERVER="$LLAMA_SERVER" \
RUNTIME_MANIFEST="$RUNTIME_MANIFEST" \
CTX_SIZE="$CTX_SIZE" \
CACHE_TYPE_K="$CACHE_TYPE_K" \
CACHE_TYPE_V="$CACHE_TYPE_V" \
LOG="$RUN_DIR/server.identity.log" \
OUT_DIR="$RUN_DIR" \
  "$LANE/scripts/serve-target-only.sh" > "$RUN_DIR/server.stdout.log" 2>&1 &
SERVER_PID=$!
printf '%s\n' "$SERVER_PID" > "$RUN_DIR/server.pid"

deadline=$((SECONDS + READINESS_TIMEOUT_S))
until curl -fsS "http://127.0.0.1:${PORT}/v1/models" > "$RUN_DIR/models.json" 2> "$RUN_DIR/models.err"; do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "server exited before readiness; see $RUN_DIR/server.stdout.log" >&2
    exit 1
  fi
  if (( SECONDS >= deadline )); then
    echo "timed out waiting for port $PORT" >&2
    exit 1
  fi
  sleep 2
done

python3 - "$RUN_DIR/server.stdout.log" "$RUN_DIR/full-offload-check.json" <<'PY'
import json
import re
import sys

log_path, out_path = sys.argv[1:]
text = open(log_path, errors="replace").read()
pairs = [(int(a), int(b)) for a, b in re.findall(r"offloaded (\d+)/(\d+) layers to GPU", text)]
valid = [(a, b) for a, b in pairs if a == b and b >= 65]
result = {"all_pairs": pairs, "full_target_offload_pairs": valid, "passed": bool(valid)}
open(out_path, "w").write(json.dumps(result, indent=2) + "\n")
if not valid:
    raise SystemExit("no full target offload >=65 layers found")
PY

if command -v xpu-smi >/dev/null 2>&1; then
  timeout 20 xpu-smi stats -d "$GPU_INDEX" > "$RUN_DIR/xpu-smi-loaded.txt" 2>&1 || true
fi

if [[ "$RUN_SCOPE" == "smoke" || "$RUN_SCOPE" == "short" || "$RUN_SCOPE" == "full" ]]; then
  exact_args=(
    python3 "$LANE/scripts/capture-exact-tokens.py"
    --base-url "http://127.0.0.1:${PORT}"
    --suite "$ROOT/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json"
    --max-tokens 128
    --model-sha256 "$EXPECTED_SHA256"
    --runtime-sha256 "$EXPECTED_RUNTIME_SHA256"
    --cache-type-k "$CACHE_TYPE_K"
    --cache-type-v "$CACHE_TYPE_V"
    --ctx-size "$CTX_SIZE"
    --out "$RUN_DIR/exact-tokens.json"
  )
  if [[ "$RUN_SCOPE" == "smoke" ]]; then
    exact_args+=(--max-prompts 1)
  fi
  if [[ -n "$ORACLE_JSON" ]]; then
    exact_args+=(--oracle-json "$ORACLE_JSON")
  fi
  "${exact_args[@]}" > "$RUN_DIR/exact-tokens.stdout.log" 2>&1
fi

if [[ "$RUN_SCOPE" == "long" || "$RUN_SCOPE" == "full" ]]; then
  long_args=(
    python3 "$ROOT/scripts/bench-openai-long-context-suite.py"
    --base-url "http://127.0.0.1:${PORT}"
    --model "$MODEL_ALIAS"
    --suite "$LANE/long-context-suite-v1.json"
    --max-tokens 128
    --request-extra-json '{"cache_prompt":false}'
    --out "$RUN_DIR/long-context-suite.json"
  )
  if [[ -n "$CASE_ID" ]]; then
    long_args+=(--case-id "$CASE_ID")
  fi
  "${long_args[@]}" > "$RUN_DIR/long-context-suite.stdout.log" 2>&1
  python3 "$LANE/scripts/validate-long-context-result.py" \
    --suite "$LANE/long-context-suite-v1.json" \
    --result "$RUN_DIR/long-context-suite.json" \
    --ctx-size "$CTX_SIZE" \
    --max-tokens 128 \
    --out "$RUN_DIR/long-context-validation.json"
fi

echo "$RUN_DIR"
