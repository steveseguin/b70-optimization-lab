#!/usr/bin/env bash
set -euo pipefail

# Default-off live wrapper for the four-independent-service MTP scaling gate.
# Activating this file requires a separate review after the helper hashes below
# are frozen.  With no arguments, PENDING is checked before ROOT resolution or
# any external command.
LIVE_ENABLE_STATE="PENDING"
LIVE_ENABLE_REQUIRED="REVIEWED_AND_PINNED"
LIVE_ACK_REQUIRED="I_ACCEPT_FOUR_B70_EMBEDDED_MTP_REALISTIC_SCALING_GATE"
EXPECTED_CAPTURE_SHA256="d51ad8957cf46a703fb12e8de493dafd767d49d32ef07306a995e299496d2547"
EXPECTED_SCALE_GATES_SHA256="088f223e256247d4ef7b5c3531309764fc24bf1eddd4c863eb01e627d11d3d46"
EXPECTED_ONCE_CAPTURE_SHA256="20f082206de7deafdc679fbd638f8361d69dfd647943919732270709e232cd33"
EXPECTED_SERVER_GATES_SHA256="7af3cf19eee537a8381b4583b09649e6a616b375b72685b569c96f7094363a2b"

if [[ $# == 0 ]]; then
  if [[ "$LIVE_ENABLE_STATE" != "$LIVE_ENABLE_REQUIRED" ]]; then
    echo "live four-service embedded-MTP realistic gate is PENDING independent review" >&2
    exit 2
  fi
  if [[ "$EXPECTED_CAPTURE_SHA256" == "PENDING" || "$EXPECTED_SCALE_GATES_SHA256" == "PENDING" ]]; then
    echo "live four-service embedded-MTP realistic gate has PENDING helper hashes" >&2
    exit 2
  fi
  if [[ "${QWEN36_EMBEDDED_MTP_FOUR_SERVICE_LIVE_ACK:-}" != "$LIVE_ACK_REQUIRED" ]]; then
    echo "live four-service embedded-MTP realistic gate requires the exact acknowledgement" >&2
    exit 2
  fi
fi
if (( $# > 0 )) && [[ -z "$1" ]]; then
  echo "explicit empty arguments are invalid; live mode requires no arguments" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LANE="$ROOT/experiments/qwen36-27b-q8-gguf-b70"
CAPTURE="$LANE/scripts/capture-embedded-mtp-four-service-realistic.py"
SCALE_GATES="$LANE/scripts/embedded_mtp_four_service_realistic_gates.py"
ONCE_CAPTURE="$LANE/scripts/capture-openai-completions-once.py"
SERVER_GATES="$LANE/scripts/embedded_mtp_vdr2_gates.py"
RUNTIME_VERIFY_LAUNCHER="$LANE/scripts/serve-target-only.sh"
OPTIONAL_MANIFEST="$LANE/optional-artifacts-manifest.json"
RUNTIME_MANIFEST="$LANE/runtime-manifest-q8-vdr2-candidate.json"
SUITE="$ROOT/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json"

EXPECTED_SUITE_SHA256="df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac"
EXPECTED_OPTIONAL_MANIFEST_SHA256="3f59254c2f01a96f22c2a2bbe83eec09a6d62d6daf1ff6c638fcf5750f687053"
EXPECTED_RUNTIME_MANIFEST_SHA256="4119790a79c55d158e7257d4fa0d95be0ca34639807c1a71ce87b60d6fdc1b49"
EXPECTED_RUNTIME_VERIFY_SHA256="fa9475956c9de8dc225e23c13b25e5851bc545ae24ec1ede92939f3ae7f08010"

MODEL="/mnt/usb-models/models/qwen36-27b-mtp-q8-gguf/Qwen3.6-27B-Q8_0.gguf"
PARTIAL_MODEL="${MODEL}.partial"
EXPECTED_MODEL_SIZE=29047084160
EXPECTED_MODEL_SHA256="9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8"
EXPECTED_REPOSITORY="unsloth/Qwen3.6-27B-MTP-GGUF"
EXPECTED_REVISION="5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace"
EXPECTED_RUNTIME_SHA256="1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7"
EXPECTED_RUNTIME_VERSION="version: 10298 (15586e2d7)"
LLAMA_SERVER="/mnt/fast-ai/runtime/llama.cpp-15586e2d-qwen27-vdr2-hybrid/llama-server"

SOURCE_RUN="/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/embedded-mtp-vdr2-realistic-gpu0-20260810T101337.129519194Z"
SUPPLEMENT_ROOT="/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/offline-supplemental/embedded-mtp-realistic-stale-oracle-final-20260810T101337.KjteSJ"
ISOLATED_CANDIDATE="$SOURCE_RUN/scored-mtp3/scored.json"
MATCHED_CONTROL_FORENSIC="$SOURCE_RUN/forensic-control/forensic.json"
SEALED_MTP3_GATE="$SUPPLEMENT_ROOT/mtp3-capture-gate.json"
SUPPLEMENT_COMPARISON="$SUPPLEMENT_ROOT/comparison.json"
SUPPLEMENT_COMPLETION="$SUPPLEMENT_ROOT/completion-status.json"
SUPPLEMENT_IDENTITY="$SUPPLEMENT_ROOT/supplemental-identity.json"
EXPECTED_ISOLATED_CANDIDATE_SHA256="0ce2399561568c4d80d112f42457fc31acedbddac576f1900e64ba88ee1352e7"
EXPECTED_MATCHED_CONTROL_FORENSIC_SHA256="8af30d579a30aedf3cadaa8f0728d883acc7d0da188bd2b30125b472f37a2ad2"
EXPECTED_SEALED_MTP3_GATE_SHA256="95dad265e308c2a1787d81c7a874eb2a2a2cab7ce513a7d6e9ec02fa448987d6"
EXPECTED_SUPPLEMENT_COMPARISON_SHA256="41d754812311ad657f7f59b7f51794e7b394a82096587123280fdf76dc510ae3"
EXPECTED_SUPPLEMENT_COMPLETION_SHA256="3eaf8d2c72bc64e2440e42486ca69b3605d357cc6e782aae79fd21c059e03c7f"
EXPECTED_SUPPLEMENT_IDENTITY_SHA256="d966b5d2996cee86faba0ef95b68afdabfcd95fb25d97078319680b8b922ae49"

usage() {
  cat <<'EOF'
Usage:
  run-embedded-mtp-four-service-realistic.sh --offline-preflight
  QWEN36_EMBEDDED_MTP_FOUR_SERVICE_LIVE_ACK=I_ACCEPT_FOUR_B70_EMBEDDED_MTP_REALISTIC_SCALING_GATE \
    run-embedded-mtp-four-service-realistic.sh

The live path remains disabled while LIVE_ENABLE_STATE=PENDING.  Once separately
reviewed and activated, it leases all four B70s and starts one pinned c32768/np1
integrated-Q8 MTP3 service per card.  The fixed 12 prompts are generated exactly
once as three synchronized four-request waves.  Streamed timing plus the sealed
retained-isolated token-position binding, content equality, cache zero,
counters, 66/66 offload, fit, overlap, residency, cleanup,
and preregistered 95/90/80 percent scaling floors all fail closed.

Only PORT_BASE and RUN_DIR are accepted live overrides.
EOF
}

check_sha() {
  local expected="$1"
  local path="$2"
  [[ "$expected" =~ ^[0-9a-f]{64}$ ]] || return 1
  printf '%s  %s\n' "$expected" "$path" | sha256sum -c - >/dev/null
}

offline_preflight() {
  for required in awk jq python3 sha256sum; do
    command -v "$required" >/dev/null 2>&1 || {
      echo "offline preflight: missing command: $required" >&2
      return 2
    }
  done
  check_sha "$EXPECTED_CAPTURE_SHA256" "$CAPTURE" || {
    echo "offline preflight: capture helper hash is PENDING or mismatched" >&2
    return 2
  }
  check_sha "$EXPECTED_SCALE_GATES_SHA256" "$SCALE_GATES" || {
    echo "offline preflight: scale gate helper hash is PENDING or mismatched" >&2
    return 2
  }
  check_sha "$EXPECTED_ONCE_CAPTURE_SHA256" "$ONCE_CAPTURE"
  check_sha "$EXPECTED_SERVER_GATES_SHA256" "$SERVER_GATES"
  check_sha "$EXPECTED_RUNTIME_VERIFY_SHA256" "$RUNTIME_VERIFY_LAUNCHER"
  check_sha "$EXPECTED_OPTIONAL_MANIFEST_SHA256" "$OPTIONAL_MANIFEST"
  check_sha "$EXPECTED_RUNTIME_MANIFEST_SHA256" "$RUNTIME_MANIFEST"
  check_sha "$EXPECTED_SUITE_SHA256" "$SUITE"
  check_sha "$EXPECTED_ISOLATED_CANDIDATE_SHA256" "$ISOLATED_CANDIDATE"
  check_sha "$EXPECTED_MATCHED_CONTROL_FORENSIC_SHA256" "$MATCHED_CONTROL_FORENSIC"
  check_sha "$EXPECTED_SEALED_MTP3_GATE_SHA256" "$SEALED_MTP3_GATE"
  check_sha "$EXPECTED_SUPPLEMENT_COMPARISON_SHA256" "$SUPPLEMENT_COMPARISON"
  check_sha "$EXPECTED_SUPPLEMENT_COMPLETION_SHA256" "$SUPPLEMENT_COMPLETION"
  check_sha "$EXPECTED_SUPPLEMENT_IDENTITY_SHA256" "$SUPPLEMENT_IDENTITY"
  jq -e \
    --arg repository "$EXPECTED_REPOSITORY" \
    --arg revision "$EXPECTED_REVISION" \
    --arg sha "$EXPECTED_MODEL_SHA256" \
    --argjson size "$EXPECTED_MODEL_SIZE" '
      .mtp.repository == $repository
      and .mtp.repository_revision == $revision
      and .mtp.size_bytes == $size
      and .mtp.sha256 == $sha
    ' "$OPTIONAL_MANIFEST" >/dev/null
  jq -e \
    --arg runtime "$LLAMA_SERVER" \
    --arg sha "$EXPECTED_RUNTIME_SHA256" '
      .llama_cpp_commit == "15586e2d7165570fb3aa7c26e0d442e289ef69de"
      and .compile_time_controls.GGML_SYCL_REORDER_Q8_0_VDR_MMVQ == 2
      and .llama_server_path == $runtime
      and .llama_server_sha256 == $sha
      and .validated_lane_defaults.GGML_SYCL_ENABLE_GRAPH == 0
      and .validated_lane_defaults.GGML_SYCL_ENABLE_DNN == 0
      and .validated_lane_defaults.GGML_SYCL_ENABLE_OPT == 1
    ' "$RUNTIME_MANIFEST" >/dev/null
  jq -e '
    .status == "PASS_REALISTIC_MTP_WIN"
    and .evidence_valid == true
    and .quality_reference == "matched_fresh_control_v1"
    and .source_run_unchanged == true
  ' "$SUPPLEMENT_COMPLETION" >/dev/null
  echo "offline four-service embedded-MTP realistic preflight: PASS"
}

case "${1:-}" in
  -h|--help)
    usage
    exit 0
    ;;
  --offline-preflight)
    [[ $# == 1 ]] || { usage >&2; exit 2; }
    offline_preflight
    exit 0
    ;;
  "")
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

PORT_BASE="${PORT_BASE:-20020}"
[[ "$PORT_BASE" =~ ^[0-9]{1,5}$ ]] || {
  echo "PORT_BASE must be a decimal port number" >&2
  exit 2
}
PORT_BASE_DECIMAL=$((10#$PORT_BASE))
(( PORT_BASE_DECIMAL >= 1024 && PORT_BASE_DECIMAL <= 65532 )) || {
  echo "PORT_BASE must leave four valid consecutive unprivileged ports" >&2
  exit 2
}
STAMP="$(date -u +%Y%m%dT%H%M%S.%NZ)"
RUN_DIR="${RUN_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/embedded-mtp-four-service-realistic-${STAMP}}"
[[ "$RUN_DIR" == /* && "$RUN_DIR" != "/" && "$RUN_DIR" != *$'\n'* ]] || {
  echo "RUN_DIR must be a non-root absolute path without newlines" >&2
  exit 2
}

GPU_IDLE_MAX_MIB=256
MIN_LOADED_DELTA_MIB=29000
MAX_LOADED_MIB=31500
MIN_HOST_AVAILABLE_KIB=33554432
READINESS_TIMEOUT_S=900
CAPTURE_TIMEOUT_S=900
TERM_GRACE_S=90
CAPTURE_TERM_GRACE_S=10
CURL_CONNECT_TIMEOUT_S=5
CURL_REQUEST_TIMEOUT_S=30

unexpected_env=()
while IFS='=' read -r name _; do
  case "$name" in
    GGML_*|SYCL_*|ZE_*|ZES_*|UR_*|ONEAPI_DEVICE_SELECTOR|LD_PRELOAD|LLAMA_ARG_*)
      unexpected_env+=("$name")
      ;;
  esac
done < <(env)
if (( ${#unexpected_env[@]} > 0 )); then
  printf 'unexpected inherited runtime environment: %s\n' "${unexpected_env[*]}" >&2
  exit 2
fi
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
export NO_PROXY="127.0.0.1,localhost"
export no_proxy="$NO_PROXY"

for required in awk bash chmod cmp cp curl date dirname env find flock grep id \
  journalctl jq kill mkdir mktemp mv ps python3 readlink rm sha256sum sleep sort \
  ss stat setsid timeout xargs xpu-smi; do
  command -v "$required" >/dev/null 2>&1 || {
    echo "required command not found: $required" >&2
    exit 2
  }
done
# xpu-smi is unreliable when multiple experiment processes query stats at the
# same time on this stack.  Share this pathname with the other Qwen36 harnesses
# and serialize every stats invocation without serializing model execution.
XPU_SMI_LOCK="/run/user/$(id -u)/qwen36-b70-xpu-smi-stats.lock"
offline_preflight >/dev/null
[[ -f "$MODEL" && ! -L "$MODEL" ]] || {
  echo "pinned integrated model is missing or is a symlink" >&2
  exit 2
}
[[ ! -e "$PARTIAL_MODEL" ]] || {
  echo "refusing launch while partial model artifact exists" >&2
  exit 2
}
[[ "$(stat -c %s "$MODEL")" == "$EXPECTED_MODEL_SIZE" ]] || {
  echo "integrated model byte size mismatch" >&2
  exit 2
}
[[ -x "$LLAMA_SERVER" ]] || {
  echo "llama-server is not executable: $LLAMA_SERVER" >&2
  exit 2
}

mkdir -p "$(dirname "$RUN_DIR")"
mkdir "$RUN_DIR" || {
  echo "RUN_DIR already exists or could not be created: $RUN_DIR" >&2
  exit 2
}
START_EPOCH="$(date +%s)"
SERVER_PIDS=("" "" "" "")
PRE_GPU_MIB=("" "" "" "")
CAPTURE_PID=""
CAPTURE_PGID=""
SERVICES_STOPPED=0
CLEANUP_FAILED=0
BODY_COMPLETED=0
HARNESS_BASELINE_READY=0
MODEL_BASELINE_READY=0
ERROR_SCAN_COMPLETED=0
ERROR_SCAN_PASSED=0
FINALIZING=0

capture_model_stat() {
  local output="$1"
  python3 - "$MODEL" "$MODEL_FD_PATH" "$output" <<'PY'
import json
import os
import stat
import sys

requested, descriptor, output = sys.argv[1:]
info = os.stat(descriptor)
value = {
    "requested_path": requested,
    "requested_resolved": os.path.realpath(requested),
    "descriptor": descriptor,
    "descriptor_resolved": os.path.realpath(descriptor),
    "device": info.st_dev,
    "inode": info.st_ino,
    "size_bytes": info.st_size,
    "mtime_ns": info.st_mtime_ns,
    "ctime_ns": info.st_ctime_ns,
    "mode": stat.S_IMODE(info.st_mode),
}
with open(output, "x") as stream:
    json.dump(value, stream, indent=2, sort_keys=True)
    stream.write("\n")
PY
}

verify_model_integrity() {
  local unchanged=false
  local sha_verified=false
  (( MODEL_BASELINE_READY == 1 )) || return 1
  capture_model_stat "$RUN_DIR/model-stat-final.json"
  if cmp -s "$RUN_DIR/model-stat-baseline.json" "$RUN_DIR/model-stat-final.json"; then
    unchanged=true
  fi
  if printf '%s  %s\n' "$EXPECTED_MODEL_SHA256" "$MODEL_FD_PATH" |
    sha256sum -c - > "$RUN_DIR/model-sha256-final.check.txt" 2>&1; then
    sha_verified=true
  fi
  jq -n \
    --argjson stat_unchanged "$unchanged" \
    --argjson sha_verified "$sha_verified" \
    --arg expected_sha256 "$EXPECTED_MODEL_SHA256" \
    '{schema:"qwen36-four-service-model-integrity-v1",stat_unchanged:$stat_unchanged,sha256_verified:$sha_verified,expected_sha256:$expected_sha256,passed:($stat_unchanged and $sha_verified)}' \
    > "$RUN_DIR/model-integrity.json"
  [[ "$unchanged" == true && "$sha_verified" == true ]]
}

gpu_used_mib() {
  local gpu="$1"
  local output="$2"
  flock -w 45 "$XPU_SMI_LOCK" timeout 20 \
    env -u ZE_AFFINITY_MASK -u ONEAPI_DEVICE_SELECTOR -u SYCL_DEVICE_FILTER \
    -u UR_DEVICE_AFFINITY_MASK ZES_ENABLE_SYSMAN=1 xpu-smi stats -d "$gpu" \
    > "$output" 2>&1 || return 1
  awk -F '|' '/GPU Memory Used/{gsub(/[^0-9.]/, "", $3); print int($3); exit}' "$output"
}

port_is_listening() {
  local port="$1"
  local text
  text="$(ss -H -ltn "sport = :$port")" || return 2
  [[ -z "$text" ]] && return 1
  return 0
}

pid_running() {
  local pid="$1"
  local state
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  state="$(ps -o stat= -p "$pid" 2>/dev/null | awk '{print $1}')"
  [[ -n "$state" && "$state" != Z* ]]
}

check_host_memory() {
  local label="$1"
  local available
  available="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
  [[ "$available" =~ ^[0-9]+$ ]] || return 1
  printf 'MemAvailable_kib=%s\nrequired_kib=%s\n' "$available" "$MIN_HOST_AVAILABLE_KIB" \
    > "$RUN_DIR/host-memory-${label}.env"
  (( available >= MIN_HOST_AVAILABLE_KIB ))
}

verify_harness_inputs() {
  local label="$1"
  (( HARNESS_BASELINE_READY == 1 )) || return 0
  sha256sum -c "$RUN_DIR/harness-inputs.sha256" \
    > "$RUN_DIR/harness-inputs-${label}.check.txt" 2>&1
}

stop_services() {
  local gpu pid deadline capture_deadline alive forced survivor port post pre
  (( SERVICES_STOPPED == 0 )) || return "$CLEANUP_FAILED"
  SERVICES_STOPPED=1
  if [[ -n "$CAPTURE_PID" ]]; then
    kill -TERM -- "-${CAPTURE_PGID:-$CAPTURE_PID}" 2>/dev/null || \
      kill -TERM "$CAPTURE_PID" 2>/dev/null || true
    capture_deadline=$((SECONDS + CAPTURE_TERM_GRACE_S))
    while pid_running "$CAPTURE_PID" && (( SECONDS < capture_deadline )); do
      sleep 0.2
    done
    if pid_running "$CAPTURE_PID"; then
      CLEANUP_FAILED=1
      kill -KILL -- "-${CAPTURE_PGID:-$CAPTURE_PID}" 2>/dev/null || \
        kill -KILL "$CAPTURE_PID" 2>/dev/null || true
    fi
    wait "$CAPTURE_PID" 2>/dev/null || true
  fi
  CAPTURE_PID=""
  CAPTURE_PGID=""
  for gpu in 0 1 2 3; do
    pid="${SERVER_PIDS[$gpu]}"
    if pid_running "$pid"; then
      kill -TERM "$pid" 2>/dev/null || true
    fi
  done
  deadline=$((SECONDS + TERM_GRACE_S))
  while (( SECONDS < deadline )); do
    alive=0
    for pid in "${SERVER_PIDS[@]}"; do
      pid_running "$pid" && alive=1
    done
    (( alive == 0 )) && break
    sleep 1
  done
  for gpu in 0 1 2 3; do
    mkdir -p "$RUN_DIR/gpu${gpu}"
    pid="${SERVER_PIDS[$gpu]}"
    forced=false
    survivor=false
    if pid_running "$pid"; then
      forced=true
      CLEANUP_FAILED=1
      kill -KILL "$pid" 2>/dev/null || true
    fi
    [[ -z "$pid" ]] || wait "$pid" 2>/dev/null || true
    pid_running "$pid" && survivor=true
    [[ "$survivor" == false ]] || CLEANUP_FAILED=1
    port=$((PORT_BASE_DECIMAL + gpu))
    if port_is_listening "$port"; then
      port_closed=false
      CLEANUP_FAILED=1
    else
      port_status=$?
      if (( port_status == 1 )); then port_closed=true; else port_closed=false; CLEANUP_FAILED=1; fi
    fi
    # One bounded post-stop query only.  Do not turn xpu-smi into a probe loop
    # if a runtime/device failure has occurred; an unclear return fails closed.
    post="$(gpu_used_mib "$gpu" "$RUN_DIR/gpu${gpu}/xpu-smi-cleanup.txt" || true)"
    pre="${PRE_GPU_MIB[$gpu]}"
    if [[ ! "$post" =~ ^[0-9]+$ ]] || (( post > GPU_IDLE_MAX_MIB )); then
      CLEANUP_FAILED=1
      post=-1
    fi
    if [[ ! "$pre" =~ ^[0-9]+$ ]]; then pre=-1; fi
    jq -n \
      --argjson gpu "$gpu" \
      --argjson pid "${pid:--1}" \
      --argjson pre "$pre" \
      --argjson post "$post" \
      --argjson forced "$forced" \
      --argjson survivor "$survivor" \
      --argjson port_closed "$port_closed" \
      '{schema:"qwen36-four-service-cleanup-v1",gpu_index:$gpu,pid:$pid,pre_mib:$pre,post_mib:$post,forced_kill:$forced,survivor:$survivor,pid_dead:($survivor|not),port_closed:$port_closed}' \
      > "$RUN_DIR/gpu${gpu}/cleanup.json"
  done
  return "$CLEANUP_FAILED"
}

scan_errors() {
  local journal_rc device_grep_rc find_rc server_grep_rc server_log
  local journal_stderr_empty=false device_grep_stderr_empty=false
  local find_stderr_empty=false server_grep_stderr_empty=false scan_passed=false
  local -a server_logs=()

  if journalctl -k --since "@$START_EPOCH" --no-pager \
    > "$RUN_DIR/kernel-journal.txt" \
    2> "$RUN_DIR/kernel-journal.stderr.txt"; then
    journal_rc=0
  else
    journal_rc=$?
  fi
  if grep -Ei 'xe.*(reset|wedg|fault|hang|timedout|device lost)|GuC.*reset|Fault response|VM.*fault|PCIe.*AER|UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST' \
    "$RUN_DIR/kernel-journal.txt" \
    > "$RUN_DIR/device-error-scan.txt" \
    2> "$RUN_DIR/device-error-scan.stderr.txt"; then
    device_grep_rc=0
  else
    device_grep_rc=$?
  fi
  if find "$RUN_DIR" -path '*/server.stdout.log' -type f -print0 \
    > "$RUN_DIR/server-log-paths.nul" \
    2> "$RUN_DIR/server-log-find.stderr.txt"; then
    find_rc=0
  else
    find_rc=$?
  fi
  if (( find_rc == 0 )); then
    while IFS= read -r -d '' server_log; do
      server_logs+=("$server_log")
    done < "$RUN_DIR/server-log-paths.nul"
  fi
  if (( ${#server_logs[@]} == 4 )); then
    if grep -EHi 'UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST|out of memory|segmentation fault|core dumped|Aborted|failed to create MTP context' \
      "${server_logs[@]}" \
      > "$RUN_DIR/server-error-scan.txt" \
      2> "$RUN_DIR/server-error-scan.stderr.txt"; then
      server_grep_rc=0
    else
      server_grep_rc=$?
    fi
  else
    server_grep_rc=2
    : > "$RUN_DIR/server-error-scan.txt"
    printf 'expected 4 server logs, found %s\n' "${#server_logs[@]}" \
      > "$RUN_DIR/server-error-scan.stderr.txt"
  fi

  [[ ! -s "$RUN_DIR/kernel-journal.stderr.txt" ]] && journal_stderr_empty=true
  [[ ! -s "$RUN_DIR/device-error-scan.stderr.txt" ]] && device_grep_stderr_empty=true
  [[ ! -s "$RUN_DIR/server-log-find.stderr.txt" ]] && find_stderr_empty=true
  [[ ! -s "$RUN_DIR/server-error-scan.stderr.txt" ]] && server_grep_stderr_empty=true
  if (( journal_rc == 0 && device_grep_rc == 1 && find_rc == 0 && server_grep_rc == 1 )) &&
    (( ${#server_logs[@]} == 4 )) &&
    [[ "$journal_stderr_empty" == true && "$device_grep_stderr_empty" == true &&
       "$find_stderr_empty" == true && "$server_grep_stderr_empty" == true &&
       ! -s "$RUN_DIR/device-error-scan.txt" &&
       ! -s "$RUN_DIR/server-error-scan.txt" ]]; then
    scan_passed=true
  fi
  if ! jq -n \
    --argjson journal_rc "$journal_rc" \
    --argjson device_grep_rc "$device_grep_rc" \
    --argjson find_rc "$find_rc" \
    --argjson server_grep_rc "$server_grep_rc" \
    --argjson server_log_count "${#server_logs[@]}" \
    --argjson journal_stderr_empty "$journal_stderr_empty" \
    --argjson device_grep_stderr_empty "$device_grep_stderr_empty" \
    --argjson find_stderr_empty "$find_stderr_empty" \
    --argjson server_grep_stderr_empty "$server_grep_stderr_empty" \
    --argjson passed "$scan_passed" \
    '{schema:"qwen36-four-service-error-scan-v1",journal_rc:$journal_rc,device_grep_rc:$device_grep_rc,find_rc:$find_rc,server_grep_rc:$server_grep_rc,server_log_count:$server_log_count,journal_stderr_empty:$journal_stderr_empty,device_grep_stderr_empty:$device_grep_stderr_empty,find_stderr_empty:$find_stderr_empty,server_grep_stderr_empty:$server_grep_stderr_empty,passed:$passed}' \
    > "$RUN_DIR/error-scan-status.json"; then
    ERROR_SCAN_COMPLETED=1
    return 1
  fi
  ERROR_SCAN_COMPLETED=1
  if [[ "$scan_passed" == true ]]; then
    ERROR_SCAN_PASSED=1
    return 0
  fi
  return 1
}

seal_artifacts() {
  local temporary
  temporary="$(mktemp "${RUN_DIR}.artifacts.XXXXXX")" || return 1
  (
    cd "$RUN_DIR"
    find . -type f ! -name artifacts.sha256 ! -name completion-status.json -print0 |
      sort -z | xargs -0 -r sha256sum
  ) > "$temporary" || { rm -f "$temporary"; return 1; }
  [[ -s "$temporary" ]] && (cd "$RUN_DIR" && sha256sum -c "$temporary" >/dev/null) || {
    rm -f "$temporary"
    return 1
  }
  mv "$temporary" "$RUN_DIR/artifacts.sha256"
}

finalize() {
  local original_status=$?
  local final_status manifest_sha gate_sha status_sha completion_tmp
  local classification performance_passed scaling_passed
  (( FINALIZING == 0 )) || exit "$original_status"
  FINALIZING=1
  trap - EXIT INT TERM
  final_status=$original_status
  stop_services || final_status=1
  (( ERROR_SCAN_COMPLETED == 1 )) || scan_errors || final_status=1
  (( ERROR_SCAN_PASSED == 1 )) || final_status=1
  verify_harness_inputs final || final_status=1
  check_host_memory final || final_status=1
  (( BODY_COMPLETED == 1 && CLEANUP_FAILED == 0 )) || final_status=1
  if (( final_status == 0 )); then
    printf 'PRE_SEAL_PASS_PENDING_COMPLETION\n' > "$RUN_DIR/run-status.txt"
  else
    printf 'FAIL\n' > "$RUN_DIR/run-status.txt"
  fi
  rm -f -- "$RUN_DIR/artifacts.sha256" "$RUN_DIR/completion-status.json"
  seal_artifacts || final_status=1
  if (( final_status == 0 )); then
    manifest_sha="$(sha256sum "$RUN_DIR/artifacts.sha256" | awk '{print $1}')"
    gate_sha="$(sha256sum "$RUN_DIR/four-service-gate.json" | awk '{print $1}')"
    status_sha="$(sha256sum "$RUN_DIR/run-status.txt" | awk '{print $1}')"
    classification="$(jq -er '.classification' "$RUN_DIR/four-service-gate.json")" || final_status=1
    performance_passed="$(jq -r '.performance_passed' "$RUN_DIR/four-service-gate.json")" || final_status=1
    scaling_passed="$(jq -r '.passed' "$RUN_DIR/four-service-gate.json")" || final_status=1
    [[ "$performance_passed" =~ ^(true|false)$ && "$scaling_passed" =~ ^(true|false)$ ]] || final_status=1
    completion_tmp="$(mktemp "${RUN_DIR}.completion.XXXXXX")"
    jq -n \
      --arg manifest "$manifest_sha" \
      --arg gate "$gate_sha" \
      --arg status "$status_sha" \
      --arg classification "$classification" \
      --argjson performance_passed "$performance_passed" \
      --argjson scaling_passed "$scaling_passed" \
      '{schema:"qwen36-embedded-mtp-four-service-realistic-completion-v1",status:$classification,evidence_valid:true,performance_passed:$performance_passed,scaling_passed:$scaling_passed,evidence_class:"official-four-service-realistic-scaling-gate",performance_promotable:false,localmaxxing_submission_ready:false,artifacts_manifest_sha256:$manifest,four_service_gate_sha256:$gate,pre_seal_status_sha256:$status}' \
      > "$completion_tmp" || final_status=1
    if (( final_status == 0 )); then mv "$completion_tmp" "$RUN_DIR/completion-status.json"; else rm -f "$completion_tmp"; fi
  fi
  if (( final_status != 0 )); then
    rm -f -- "$RUN_DIR/completion-status.json"
    printf 'FAIL\n' > "$RUN_DIR/run-status.txt"
    rm -f -- "$RUN_DIR/artifacts.sha256"
    seal_artifacts || true
  fi
  find "$RUN_DIR" -type f -exec chmod 0444 {} + 2>/dev/null || true
  find "$RUN_DIR" -type d -exec chmod 0555 {} + 2>/dev/null || true
  printf '%s\n' "$RUN_DIR"
  exit "$final_status"
}
trap finalize EXIT
trap 'exit 130' INT TERM

check_host_memory preflight || {
  echo "host MemAvailable is below the 32 GiB floor" >&2
  exit 2
}

GPU_LEASE_DIR="/run/user/$(id -u)/qwen36-b70-gpu-leases"
PORT_LEASE_DIR="/run/user/$(id -u)/qwen36-b70-port-leases"
mkdir -p "$GPU_LEASE_DIR" "$PORT_LEASE_DIR"
LEASE_FDS=()
for gpu in 0 1 2 3; do
  exec {lease_fd}>"$GPU_LEASE_DIR/gpu${gpu}.lock"
  flock -n "$lease_fd" || { echo "GPU $gpu is leased" >&2; exit 2; }
  LEASE_FDS+=("$lease_fd")
  port=$((PORT_BASE_DECIMAL + gpu))
  exec {lease_fd}>"$PORT_LEASE_DIR/port${port}.lock"
  flock -n "$lease_fd" || { echo "port $port is leased" >&2; exit 2; }
  LEASE_FDS+=("$lease_fd")
  if port_is_listening "$port"; then
    echo "port already in use: $port" >&2
    exit 2
  else
    port_status=$?
    (( port_status == 1 )) || { echo "could not prove port $port is closed" >&2; exit 2; }
  fi
done

flock -w 45 "$XPU_SMI_LOCK" timeout 30 \
  env -u ZE_AFFINITY_MASK -u ONEAPI_DEVICE_SELECTOR -u SYCL_DEVICE_FILTER \
  -u UR_DEVICE_AFFINITY_MASK ZES_ENABLE_SYSMAN=1 xpu-smi discovery -j \
  > "$RUN_DIR/xpu-smi-discovery.json"
jq -e '
  [.device_list[] |
    select(.device_function_type == "physical" and (.device_name | contains("Arc(TM) Pro B70"))) |
    {device_id,pci_bdf_address,uuid}]
  | length == 4
    and ([.[].device_id] | sort) == [0,1,2,3]
    and ([.[].pci_bdf_address] | unique | length) == 4
    and ([.[].uuid] | unique | length) == 4
' "$RUN_DIR/xpu-smi-discovery.json" >/dev/null || {
  echo "four distinct physical B70s were not discovered" >&2
  exit 2
}
for gpu in 0 1 2 3; do
  mkdir "$RUN_DIR/gpu${gpu}"
  used="$(gpu_used_mib "$gpu" "$RUN_DIR/gpu${gpu}/xpu-smi-before.txt")"
  [[ "$used" =~ ^[0-9]+$ ]] || { echo "cannot parse GPU $gpu memory" >&2; exit 2; }
  (( used <= GPU_IDLE_MAX_MIB )) || { echo "GPU $gpu is not idle: $used MiB" >&2; exit 2; }
  PRE_GPU_MIB[$gpu]="$used"
done

exec {QWEN36_MODEL_FD}<"$MODEL"
flock -s -n "$QWEN36_MODEL_FD" || { echo "could not lock integrated model" >&2; exit 2; }
MODEL_FD_PATH="/proc/$$/fd/$QWEN36_MODEL_FD"
MODEL_LOAD_PATH="/proc/self/fd/$QWEN36_MODEL_FD"
[[ "$MODEL" -ef "$MODEL_FD_PATH" ]] || { echo "model descriptor mismatch" >&2; exit 2; }
export QWEN36_MODEL_FD
capture_model_stat "$RUN_DIR/model-stat-before-hash.json"
printf '%s  %s\n' "$EXPECTED_MODEL_SHA256" "$MODEL_FD_PATH" |
  sha256sum -c - > "$RUN_DIR/model-sha256.check.txt"
capture_model_stat "$RUN_DIR/model-stat-after-hash.json"
cmp -s "$RUN_DIR/model-stat-before-hash.json" "$RUN_DIR/model-stat-after-hash.json" || {
  echo "model identity changed during initial SHA-256 verification" >&2
  exit 2
}
cp "$RUN_DIR/model-stat-after-hash.json" "$RUN_DIR/model-stat-baseline.json"
MODEL_BASELINE_READY=1

LLAMA_SERVER="$LLAMA_SERVER" RUNTIME_MANIFEST="$RUNTIME_MANIFEST" \
  "$RUNTIME_VERIFY_LAUNCHER" --verify-runtime-bundle \
  "$RUN_DIR/llama-server-ldd.txt" \
  "$RUN_DIR/runtime-resolved-files.sha256" \
  "$RUN_DIR/runtime-bundle.json"

set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null
set -u
RUNTIME_ORIGIN="$(dirname "$LLAMA_SERVER")"
export LD_LIBRARY_PATH="$RUNTIME_ORIGIN${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export ONEAPI_DEVICE_SELECTOR="level_zero:*"
export ZES_ENABLE_SYSMAN=1
export UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1
export GGML_SYCL_ENABLE_VMM=1
export GGML_SYCL_ENABLE_GRAPH=0
export GGML_SYCL_GRAPH_CACHE_SIZE=0
export GGML_SYCL_ENABLE_DNN=0
export GGML_SYCL_ENABLE_OPT=1
export GGML_SYCL_FA_ONEDNN=1
export GGML_SYCL_FA_ONEDNN_MAX_KV=0
export GGML_SYCL_ENABLE_MKL_FA=1
export GGML_SYCL_ENABLE_FLASH_ATTN=1
RUNTIME_VERSION="$($LLAMA_SERVER --version 2>&1)"
grep -Fqx "$EXPECTED_RUNTIME_VERSION" <<< "$RUNTIME_VERSION" || {
  echo "runtime version mismatch" >&2
  exit 2
}

mkdir "$RUN_DIR/input-snapshots"
cp "$SUITE" "$RUN_DIR/input-snapshots/realistic-suite-v1.json"
cp "$ISOLATED_CANDIDATE" "$RUN_DIR/input-snapshots/isolated-candidate-scored.json"
cp "$MATCHED_CONTROL_FORENSIC" "$RUN_DIR/input-snapshots/matched-control-forensic.json"
cp "$SEALED_MTP3_GATE" "$RUN_DIR/input-snapshots/sealed-mtp3-capture-gate.json"
cp "$SUPPLEMENT_COMPARISON" "$RUN_DIR/input-snapshots/supplement-comparison.json"
cp "$SUPPLEMENT_COMPLETION" "$RUN_DIR/input-snapshots/supplement-completion.json"
cp "$SUPPLEMENT_IDENTITY" "$RUN_DIR/input-snapshots/supplement-identity.json"
SUITE_SNAPSHOT="$RUN_DIR/input-snapshots/realistic-suite-v1.json"
ISOLATED_SNAPSHOT="$RUN_DIR/input-snapshots/isolated-candidate-scored.json"
CONTROL_SNAPSHOT="$RUN_DIR/input-snapshots/matched-control-forensic.json"
SEALED_GATE_SNAPSHOT="$RUN_DIR/input-snapshots/sealed-mtp3-capture-gate.json"
COMPARISON_SNAPSHOT="$RUN_DIR/input-snapshots/supplement-comparison.json"
COMPLETION_SNAPSHOT="$RUN_DIR/input-snapshots/supplement-completion.json"
IDENTITY_SNAPSHOT="$RUN_DIR/input-snapshots/supplement-identity.json"

python3 - "$RUN_DIR/service-config.json" "$PORT_BASE_DECIMAL" <<'PY'
import json
import sys

path, base = sys.argv[1], int(sys.argv[2])
value = {
    "schema": "qwen36-embedded-mtp-four-service-config-v1",
    "services": [
        {
            "service_index": gpu,
            "gpu_index": gpu,
            "base_url": f"http://127.0.0.1:{base + gpu}",
            "model": f"qwen36-27b-mtp-q8-vdr2-realistic-scale-gpu{gpu}",
        }
        for gpu in range(4)
    ],
}
with open(path, "x") as stream:
    json.dump(value, stream, indent=2, sort_keys=True)
    stream.write("\n")
PY

cat > "$RUN_DIR/run-identity.env" <<EOF
date_utc=$STAMP
evidence_class=official-four-service-realistic-scaling-gate
performance_promotable=0
localmaxxing_submission_ready=0
gpu_count=4
independent_services=4
slots_per_service=1
port_base=$PORT_BASE_DECIMAL
model=$MODEL
model_size=$EXPECTED_MODEL_SIZE
model_sha256=$EXPECTED_MODEL_SHA256
model_repository=$EXPECTED_REPOSITORY
model_revision=$EXPECTED_REVISION
runtime_manifest_sha256=$EXPECTED_RUNTIME_MANIFEST_SHA256
llama_server=$LLAMA_SERVER
llama_server_sha256=$EXPECTED_RUNTIME_SHA256
llama_cpp_commit=15586e2d7165570fb3aa7c26e0d442e289ef69de
q8_reorder_vdr_mmvq=2
ctx_size=32768
batch_size=1024
ubatch_size=1024
cache_type_k=f16
cache_type_v=f16
spec_type=draft-mtp
spec_n_max=3
spec_n_min=0
spec_p_split=0.10
spec_p_min=0.00
suite_sha256=$EXPECTED_SUITE_SHA256
aggregate_retention_floor=0.95
service_retention_floor=0.90
service_fairness_floor=0.90
prompt_d99_retention_floor=0.80
EOF

harness_inputs=(
  "${BASH_SOURCE[0]}" "$CAPTURE" "$SCALE_GATES" "$ONCE_CAPTURE"
  "$SERVER_GATES" "$RUNTIME_VERIFY_LAUNCHER" "$OPTIONAL_MANIFEST"
  "$RUNTIME_MANIFEST" "$SUITE" "$SUITE_SNAPSHOT" "$ISOLATED_SNAPSHOT"
  "$CONTROL_SNAPSHOT" "$SEALED_GATE_SNAPSHOT" "$COMPARISON_SNAPSHOT"
  "$COMPLETION_SNAPSHOT" "$IDENTITY_SNAPSHOT"
)
printf '%s\n' "${harness_inputs[@]}" | sort -u > "$RUN_DIR/harness-input-paths.txt"
while IFS= read -r path; do sha256sum "$path"; done \
  < "$RUN_DIR/harness-input-paths.txt" > "$RUN_DIR/harness-inputs.sha256"
HARNESS_BASELINE_READY=1
verify_harness_inputs initial

for gpu in 0 1 2 3; do
  port=$((PORT_BASE_DECIMAL + gpu))
  alias="qwen36-27b-mtp-q8-vdr2-realistic-scale-gpu${gpu}"
  server_cmd=(
    "$LLAMA_SERVER"
    -m "$MODEL_LOAD_PATH"
    --alias "$alias"
    --host 127.0.0.1
    --port "$port"
    -dev SYCL0
    -ngl all
    -c 32768
    -np 1
    -b 1024
    -ub 1024
    -t 8
    --threads-http 6
    --poll 50
    -lv 4
    -ctk f16
    -ctv f16
    -fa on
    -fit on
    -fitt 1024
    --spec-type draft-mtp
    --spec-draft-n-max 3
    --spec-draft-n-min 0
    --spec-draft-p-split 0.10
    --spec-draft-p-min 0.00
    --spec-draft-backend-sampling
    --spec-draft-device SYCL0
    --spec-draft-ngl all
    --spec-draft-type-k f16
    --spec-draft-type-v f16
    --reasoning off
    --ctx-checkpoints 0
    --cache-ram 0
    --no-cache-idle-slots
    --no-context-shift
    --slots
    --metrics
    --jinja
    --no-kv-unified
    --cont-batching
  )
  python3 - "$RUN_DIR/gpu${gpu}/server-identity.json" "$gpu" "$MODEL" \
    "$MODEL_LOAD_PATH" "$EXPECTED_MODEL_SHA256" "$EXPECTED_RUNTIME_SHA256" \
    "${server_cmd[@]}" <<'PY'
import json
import sys

output, gpu, model, load_path, model_sha, runtime_sha, *argv = sys.argv[1:]
with open(output, "x") as stream:
    json.dump(
        {
            "mode": "mtp3",
            "lifetime": "four-service-realistic-scale",
            "gpu_index": int(gpu),
            "ze_affinity_mask": gpu,
            "model": model,
            "model_load_path": load_path,
            "model_sha256": model_sha,
            "runtime_sha256": runtime_sha,
            "argv": argv,
        },
        stream,
        indent=2,
        sort_keys=True,
    )
    stream.write("\n")
PY
  env ZE_AFFINITY_MASK="$gpu" "${server_cmd[@]}" \
    > "$RUN_DIR/gpu${gpu}/server.stdout.log" 2>&1 &
  SERVER_PIDS[$gpu]=$!
  printf '%s\n' "${SERVER_PIDS[$gpu]}" > "$RUN_DIR/gpu${gpu}/server.pid"
  # Integrated-MTP model/IGC initialization is serialized across cards.  Once
  # every service is ready, the capture helper still releases four requests at
  # once in each wave and the overlap gate proves simultaneous execution.
  SERVICE_READINESS_DEADLINE=$((SECONDS + READINESS_TIMEOUT_S))
  until curl --noproxy '*' --connect-timeout "$CURL_CONNECT_TIMEOUT_S" \
    --max-time "$CURL_REQUEST_TIMEOUT_S" -fsS "http://127.0.0.1:${port}/v1/models" \
    > "$RUN_DIR/gpu${gpu}/models.json" 2> "$RUN_DIR/gpu${gpu}/models.err"; do
    pid_running "${SERVER_PIDS[$gpu]}" || {
      echo "GPU $gpu service exited before readiness" >&2
      exit 1
    }
    (( SECONDS < SERVICE_READINESS_DEADLINE )) || {
      echo "GPU $gpu service readiness timeout" >&2
      exit 1
    }
    sleep 2
  done
done

for gpu in 0 1 2 3; do
  python3 "$SERVER_GATES" gate-server \
    --mode mtp3 \
    --log "$RUN_DIR/gpu${gpu}/server.stdout.log" \
    --identity "$RUN_DIR/gpu${gpu}/server-identity.json" \
    --output "$RUN_DIR/gpu${gpu}/server-gate-pre.json"
  loaded="$(gpu_used_mib "$gpu" "$RUN_DIR/gpu${gpu}/xpu-smi-loaded.txt")"
  [[ "$loaded" =~ ^[0-9]+$ ]] || { echo "cannot parse GPU $gpu loaded residency" >&2; exit 1; }
  delta=$((loaded - PRE_GPU_MIB[gpu]))
  (( delta >= MIN_LOADED_DELTA_MIB && loaded <= MAX_LOADED_MIB )) || {
    echo "GPU $gpu loaded residency violates 29000-delta/31500-used bounds" >&2
    exit 1
  }
  jq -n \
    --argjson gpu "$gpu" \
    --argjson pre "${PRE_GPU_MIB[$gpu]}" \
    --argjson loaded "$loaded" \
    --argjson delta "$delta" \
    '{schema:"qwen36-four-service-residency-v1",gpu_index:$gpu,pre_mib:$pre,loaded_mib:$loaded,loaded_delta_mib:$delta,minimum_loaded_delta_mib:29000,maximum_loaded_mib:31500}' \
    > "$RUN_DIR/gpu${gpu}/residency.json"
done
check_host_memory all-loaded

python3 "$CAPTURE" prepare \
  --config "$RUN_DIR/service-config.json" \
  --suite "$SUITE_SNAPSHOT" \
  --output "$RUN_DIR/prepared.json" \
  > "$RUN_DIR/prepare.stdout.log" 2>&1
for gpu in 0 1 2 3; do
  port=$((PORT_BASE_DECIMAL + gpu))
  curl --noproxy '*' --connect-timeout "$CURL_CONNECT_TIMEOUT_S" \
    --max-time "$CURL_REQUEST_TIMEOUT_S" -fsS "http://127.0.0.1:${port}/metrics" \
    > "$RUN_DIR/gpu${gpu}/metrics-before.prom"
done

setsid python3 "$CAPTURE" run \
  --config "$RUN_DIR/service-config.json" \
  --prepared "$RUN_DIR/prepared.json" \
  --journal "$RUN_DIR/capture-journal.jsonl" \
  --output "$RUN_DIR/capture.json" \
  --timeout "$CAPTURE_TIMEOUT_S" \
  > "$RUN_DIR/capture.stdout.log" 2> "$RUN_DIR/capture.stderr.log" &
CAPTURE_PID=$!
CAPTURE_PGID="$CAPTURE_PID"
CAPTURE_DEADLINE=$((SECONDS + CAPTURE_TIMEOUT_S))
for wave in 0 1 2; do
  while :; do
    started=0
    if [[ -f "$RUN_DIR/capture-journal.jsonl" ]]; then
      started="$(grep -c "\"event\":\"request_started\".*\"wave_index\":${wave}" "$RUN_DIR/capture-journal.jsonl" || true)"
    fi
    (( started == 4 )) && break
    pid_running "$CAPTURE_PID" || { echo "capture exited before wave $wave started" >&2; wait "$CAPTURE_PID" || true; exit 1; }
    (( SECONDS < CAPTURE_DEADLINE )) || { echo "capture wave $wave start timeout" >&2; exit 1; }
    sleep 0.2
  done
  ss -H -ltnp > "$RUN_DIR/listeners-wave${wave}.txt"
done
while pid_running "$CAPTURE_PID"; do
  (( SECONDS < CAPTURE_DEADLINE )) || {
    echo "capture exceeded the ${CAPTURE_TIMEOUT_S}s whole-process deadline" >&2
    exit 1
  }
  sleep 0.2
done
wait "$CAPTURE_PID"
CAPTURE_PID=""
CAPTURE_PGID=""

for gpu in 0 1 2 3; do
  port=$((PORT_BASE_DECIMAL + gpu))
  curl --noproxy '*' --connect-timeout "$CURL_CONNECT_TIMEOUT_S" \
    --max-time "$CURL_REQUEST_TIMEOUT_S" -fsS "http://127.0.0.1:${port}/metrics" \
    > "$RUN_DIR/gpu${gpu}/metrics-after.prom"
  python3 "$SERVER_GATES" gate-metrics \
    --mode mtp3 \
    --before "$RUN_DIR/gpu${gpu}/metrics-before.prom" \
    --after "$RUN_DIR/gpu${gpu}/metrics-after.prom" \
    --output "$RUN_DIR/gpu${gpu}/metrics-gate.json"
  python3 "$SERVER_GATES" gate-server \
    --mode mtp3 \
    --log "$RUN_DIR/gpu${gpu}/server.stdout.log" \
    --identity "$RUN_DIR/gpu${gpu}/server-identity.json" \
    --output "$RUN_DIR/gpu${gpu}/server-gate-post.json"
done
verify_harness_inputs postcapture
stop_services
verify_model_integrity
LLAMA_SERVER="$LLAMA_SERVER" RUNTIME_MANIFEST="$RUNTIME_MANIFEST" \
  "$RUNTIME_VERIFY_LAUNCHER" --verify-runtime-bundle \
  "$RUN_DIR/llama-server-ldd-final.txt" \
  "$RUN_DIR/runtime-resolved-files-final.sha256" \
  "$RUN_DIR/runtime-bundle-final.json" \
  "$RUN_DIR/runtime-bundle.json"
scan_errors
check_host_memory postcleanup

python3 "$SCALE_GATES" \
  --run-dir "$RUN_DIR" \
  --suite "$SUITE_SNAPSHOT" \
  --isolated-candidate "$ISOLATED_SNAPSHOT" \
  --matched-control-forensic "$CONTROL_SNAPSHOT" \
  --sealed-mtp3-gate "$SEALED_GATE_SNAPSHOT" \
  --supplement-comparison "$COMPARISON_SNAPSHOT" \
  --supplement-completion "$COMPLETION_SNAPSHOT" \
  --supplement-identity "$IDENTITY_SNAPSHOT" \
  --port-base "$PORT_BASE_DECIMAL" \
  --output "$RUN_DIR/four-service-gate.json"
jq -e '
  .evidence_valid == true
  and (.classification == "PASS_REALISTIC_MTP_FOUR_SERVICE_SCALE"
       or .classification == "VALID_REALISTIC_MTP_FOUR_SERVICE_SCALE_RETENTION_FAIL")
  and .performance_promotable == false
  and .localmaxxing_submission_ready == false
' "$RUN_DIR/four-service-gate.json" >/dev/null
BODY_COMPLETED=1
