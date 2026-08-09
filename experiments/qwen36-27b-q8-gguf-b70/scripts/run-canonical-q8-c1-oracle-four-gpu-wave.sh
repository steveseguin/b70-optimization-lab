#!/usr/bin/env bash
set -euo pipefail

# Phase-1 only: four fresh c2-topology servers, sequential M=1 oracle capture.
# Live execution is an explicit --run-phase1 action and remains disabled by the
# pending analyzer hash until the frozen offline test/reviewer gates pass.
# --print-wave-plan is always read-only and cannot touch XPU.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LANE="$ROOT/experiments/qwen36-27b-q8-gguf-b70"
SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
ANALYZER="$LANE/scripts/canonical-q8-c1-oracle-study.py"
LAUNCHER="$LANE/scripts/serve-target-only.sh"
SERVER_ATTESTER="$LANE/scripts/attest-c2-server.py"
MATRIX_CLIENT="$LANE/scripts/capture-c2-token-matrix.py"
CAPTURE_CLIENT="$LANE/scripts/capture-simultaneous-c2.py"
CANONICAL_ATTESTER="$LANE/scripts/attest-canonical-q8-dispatch.py"
RUNTIME_MANIFEST="$LANE/runtime-manifest-canonical-q8-c2.json"
SUITE="$LANE/c2-long-context-suite-v1.json"
COMMON_CAPTURE="$LANE/scripts/capture-exact-tokens.py"
PROMPT_BUILDER="$ROOT/scripts/bench-openai-long-context-suite.py"
MODEL_MANIFEST="$LANE/model-manifest.json"
LLAMA_SERVER="/mnt/fast-ai/runtime/llama.cpp-15586e2d-q8-c2-canonical-109eee6f-hybrid/llama-server"

MODEL="/mnt/usb-models/models/qwen36-27b-q8-gguf/Qwen3.6-27B-Q8_0.gguf"
OLD_ORACLE="${OLD_ORACLE:-/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal1-formal-c2-gpu0-short-diag-20260809T171516.435188879Z/sequential-oracle/oracle.json}"
BASELINE_CANARY="${BASELINE_CANARY:-/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/qwen36-27b-q8_0-f16kv-short-dnn0-exact-20260808T232639Z/exact-tokens.json}"
BASELINE_CANARY_SUITE="${BASELINE_CANARY_SUITE:-$ROOT/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json}"
OFFICIAL_C1_DIR="${OFFICIAL_C1_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal1-isolated-baseline-gpu0-short-20260809T163733.326112517Z}"

EXPECTED_MODEL_SHA256="f93f517f38e696d35a1a7df2c0e3155a64f4c4dcd662107a146ae263f7fb14ce"
EXPECTED_MODEL_SIZE=28595763424
EXPECTED_RUNTIME_SHA256="1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7"
EXPECTED_MANIFEST_SHA256="1b6c305b7e3fad027e7397168bda23526b72b8a4b59e8c6b2b3788fc7347b4d9"
EXPECTED_MATRIX_SHA256="aac9348d09340bfdc2b21725512ff4784f1fe42be533f69f7cf8a96277a872a7"
EXPECTED_CANONICAL_ATTESTER_SHA256="73ce1562ae5cee236f5761f36e9250409c90460593c1aa08bcd4c963d1de45da"
EXPECTED_OLD_ORACLE_SHA256="7a884c14ecd1705981aea63c22e8fd96b9b6646aeca98a53850d5cc54836e534"
EXPECTED_SUITE_SHA256="053523440e4a23d7f772dec5025fe4831ba33c0a8eaba76795e4ee76718860af"
EXPECTED_CANARY_SHA256="e4477808823cdf9bb182d5abc4788cee216011a0195cf49bf03a7bda35f5dbcc"
EXPECTED_CANARY_SUITE_SHA256="df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac"
EXPECTED_LAUNCHER_SHA256="96ee485eadc69949ad2035a1cc33a8f1433b6ce826399c4294e60e43b263ca74"
EXPECTED_SERVER_ATTESTER_SHA256="9a3fab9c74728a12bdba0401c89154564dd0b5115ea2731dbc8035eae8109f00"
EXPECTED_CAPTURE_CLIENT_SHA256="7d89e99ee8f69dea24f27a6a0b83b7c9faf8285273159c2b771149126d2d0f00"
EXPECTED_COMMON_CAPTURE_SHA256="94595b6962e64981723a063b6ec23b80c3701a22d0e256e85b596e6bf75f5b05"
EXPECTED_PROMPT_BUILDER_SHA256="2286c9fd1ef59136a92a857be2992b31e0ff3bc844c7489239ab8f76f515cf72"
EXPECTED_MODEL_MANIFEST_SHA256="858a15c80b51fdedf7bed24f32906369d1c0b7b8534a04b3822bc1b80f6829b9"
# Patched to the final analyzer hash after the offline suite is frozen.
EXPECTED_ANALYZER_SHA256="43c707c0b8040d694efa89e13638820fff5eed4cc95fa9129bcd0110452d65d6"
EXPECTED_OFFICIAL_C1_RESULT_SHA256="fe03bfdd5adb826a3c9b5a68f9922c543b3767f3afce7ca388139dd6613356c4"
EXPECTED_OFFICIAL_C1_MANIFEST_SHA256="d1203c993a50c1d1ced03f20e85f96c61ee23c6c349b27326310fe8b6c4ce65c"
EXPECTED_OFFICIAL_C1_MARKER_SHA256="5cbb5809398fa6edb6ea08d96edb54e7f166328d23a4dbe0412016858c796a56"

PORT_BASE="${PORT_BASE:-19620}"
SELECTORS=(0 0 1 1)
START_STAGGER_S="${START_STAGGER_S:-5}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-1200}"
REQUEST_TIMEOUT_S="${REQUEST_TIMEOUT_S:-1800}"
WAVE_TIMEOUT_S="${WAVE_TIMEOUT_S:-7200}"
TERM_GRACE_S="${TERM_GRACE_S:-90}"
KILL_GRACE_S="${KILL_GRACE_S:-10}"
PASSIVE_DRAIN_S="${PASSIVE_DRAIN_S:-60}"
GPU_IDLE_MAX_MIB=256
MIN_LOADED_DELTA_MIB=25000
MIN_FIT_FREE_MIB=1024
MIN_HOST_AVAILABLE_KIB="${MIN_HOST_AVAILABLE_KIB:-100663296}"
MIN_FAST_FREE_KIB="${MIN_FAST_FREE_KIB:-10485760}"
STAMP="$(date -u +%Y%m%dT%H%M%S.%NZ)"
WAVE_DIR="${WAVE_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/canonical-q8-c1-oracle-four-gpu-${STAMP}}"

die() {
  echo "ERROR: $*" >&2
  exit 2
}

require_uint() {
  [[ "$2" =~ ^[0-9]+$ ]] || die "$1 must be a nonnegative integer"
}

file_sha256() {
  local value
  [[ -f "$1" ]] || return 1
  value="$(sha256sum "$1" | awk '{print $1}')" || return 1
  [[ "$value" =~ ^[0-9a-f]{64}$ ]] || return 1
  printf '%s\n' "$value"
}

assert_sha() {
  [[ "$(file_sha256 "$1")" == "$2" ]] || die "SHA-256 mismatch: $1"
}

pid_running() {
  local state
  kill -0 "$1" 2>/dev/null || return 1
  state="$(ps -o stat= -p "$1" 2>/dev/null | awk '{print $1}')"
  [[ -n "$state" && "$state" != Z* ]]
}

process_start_ticks() {
  python3 - "$1" <<'PY'
from pathlib import Path
import sys
raw = Path(f"/proc/{int(sys.argv[1])}/stat").read_text()
close = raw.rfind(")")
if close < 0:
    raise SystemExit(1)
parts = raw[close + 2:].split()
if len(parts) < 20 or not parts[19].isdigit() or int(parts[19]) <= 0:
    raise SystemExit(1)
print(parts[19])
PY
}

group_alive() {
  ps -eo pgid=,stat= | awk -v target="$1" '$1==target && $2 !~ /^Z/ {found=1} END{exit(found?0:1)}'
}

sample_gpu() {
  timeout 20 xpu-smi stats -d "$1" > "$2" 2>&1
}

parse_gpu_used_mib() {
  local expected_gpu="$2"
  [[ "$expected_gpu" =~ ^[0-3]$ ]] || return 1
  awk -F '|' -v expected_gpu="$expected_gpu" '
    function trim(value) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      return value
    }
    {
      label=trim($2)
      value=trim($3)
    }
    label == "Device ID" {
      device_count++
      if (value !~ /^[0-9]+$/) malformed=1
      else device_id=value + 0
    }
    label == "GPU Memory Used (MiB)" {
      memory_count++
      if (value !~ /^[0-9]+([.][0-9]+)?$/) malformed=1
      else {
        memory_mib=int(value)
        if ((value + 0) != memory_mib) malformed=1
      }
    }
    END {
      if (malformed || device_count != 1 || memory_count != 1 || device_id != expected_gpu) exit 1
      print memory_mib
    }
  ' "$1"
}

capture_model_stat() {
  python3 - "$1" "$2" <<'PY'
import json, os, sys
value = os.stat(sys.argv[1], follow_symlinks=True)
payload = {name: getattr(value, name) for name in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")}
with open(sys.argv[2], "x", encoding="utf-8") as stream:
    json.dump(payload, stream, indent=2, sort_keys=True)
    stream.write("\n")
    stream.flush()
    os.fsync(stream.fileno())
PY
}

atomic_json() {
  local destination="$1"
  shift
  local temporary
  [[ ! -e "$destination" ]] || return 1
  temporary="$(mktemp "$(dirname "$destination")/.$(basename "$destination").XXXXXX")" || return 1
  if ! jq "$@" > "$temporary"; then rm -f "$temporary"; return 1; fi
  chmod 0444 "$temporary" || { rm -f "$temporary"; return 1; }
  ln "$temporary" "$destination" || { rm -f "$temporary"; return 1; }
  rm -f "$temporary"
}

seal_directory() {
  local directory="$1" manifest_name="$2" marker_name="$3" temporary
  temporary="$(mktemp "$directory/.${manifest_name}.XXXXXX")" || return 1
  if ! (cd "$directory" && find . -type f \
      ! -path "./$manifest_name" ! -path "./$marker_name" ! -path "./.${manifest_name}.*" \
      -print0 | sort -z | xargs -0 -r sha256sum > "$temporary"); then
    rm -f "$temporary"; return 1
  fi
  [[ -s "$temporary" ]] || { rm -f "$temporary"; return 1; }
  (cd "$directory" && sha256sum -c "$temporary" >/dev/null) || { rm -f "$temporary"; return 1; }
  ln "$temporary" "$directory/$manifest_name" || { rm -f "$temporary"; return 1; }
  rm -f "$temporary"
  (cd "$directory" && sha256sum -c "$manifest_name" >/dev/null)
}

validate_lease_fd() {
  [[ "$1" =~ ^[0-9]+$ ]] || return 1
  [[ "$(readlink -f "/proc/$$/fd/$1" 2>/dev/null || true)" == "$(readlink -f "$2")" ]] || return 1
  flock -n "$1"
}

runtime_report() {
  local report="$1" reference="${2:-}"
  if [[ -n "$reference" ]]; then
    LLAMA_SERVER="$LLAMA_SERVER" RUNTIME_MANIFEST="$RUNTIME_MANIFEST" \
      "$LAUNCHER" --verify-runtime-bundle "${report%.json}.ldd.txt" \
      "${report%.json}.resolved.sha256" "$report" "$reference"
  else
    LLAMA_SERVER="$LLAMA_SERVER" RUNTIME_MANIFEST="$RUNTIME_MANIFEST" \
      "$LAUNCHER" --verify-runtime-bundle "${report%.json}.ldd.txt" \
      "${report%.json}.resolved.sha256" "$report"
  fi
}

child_main() {
  : "${GPU_INDEX:?}" "${SELECTOR:?}" "${PORT:?}" "${RUN_DIR:?}" \
    "${MODEL_FD:?}" "${QWEN36_GPU_LEASE_FD:?}" "${QWEN36_PORT_LEASE_FD:?}" \
    "${WAVE_RELEASE_FILE:?}" "${WAVE_ABORT_FILE:?}" "${MODEL_STAT_BASELINE:?}" \
    "${OUTER_RUNTIME_REFERENCE:?}" "${WAVE_INPUT_MANIFEST:?}" "${SESSION_GATE:?}"
  : "${EXPECTED_SCRIPT_SHA256:?}"
  [[ "$(file_sha256 "$SCRIPT")" == "$EXPECTED_SCRIPT_SHA256" ]] || die "runner changed before child entry"
  local session_deadline=$((SECONDS + 30)) self_ticks self_pgid self_sid
  while [[ ! -s "$SESSION_GATE" ]]; do
    (( SECONDS < session_deadline )) || die "session identity gate timeout"
    sleep 0.05
  done
  self_ticks="$(process_start_ticks $$)"
  self_pgid="$(ps -o pgid= -p $$ | awk '{print $1}')"
  self_sid="$(ps -o sid= -p $$ | awk '{print $1}')"
  jq -e --argjson pid "$$" --arg ticks "$self_ticks" --argjson pgid "$self_pgid" --argjson sid "$self_sid" \
    '.passed==true and .pid==$pid and .start_ticks==$ticks and .pgid==$pgid and .sid==$sid and .pid==.pgid and .pgid==.sid' \
    "$SESSION_GATE" >/dev/null || die "session identity gate mismatch"
  [[ "$GPU_INDEX" =~ ^[0-3]$ ]] || die "invalid child GPU"
  [[ "$SELECTOR" == "${SELECTORS[$GPU_INDEX]}" ]] || die "selector/mapping mismatch"
  [[ "$PORT" == "$((PORT_BASE + GPU_INDEX))" ]] || die "port/mapping mismatch"
  [[ ! -e "$RUN_DIR" ]] || die "child output exists: $RUN_DIR"
  mkdir "$RUN_DIR"

  local gpu_lease="/run/user/$(id -u)/qwen36-b70-gpu-leases/gpu${GPU_INDEX}.lock"
  local port_lease="/run/user/$(id -u)/qwen36-b70-port-leases/port${PORT}.lock"
  local server_pid="" server_start_ticks="" server_pgid="" pre_mib="" loaded_mib="" start_epoch cleanup_forced=0
  local normal_complete=0 cleanup_survivor=0 capture_started=0 capture_complete=0
  start_epoch="$(date +%s)"
  owned_server_running() {
    [[ -n "$server_pid" && -n "$server_start_ticks" && -n "$server_pgid" ]] || return 1
    pid_running "$server_pid" || return 1
    [[ "$(process_start_ticks "$server_pid" 2>/dev/null || true)" == "$server_start_ticks" ]] || return 1
    [[ "$(ps -o pgid= -p "$server_pid" 2>/dev/null | awk '{print $1}')" == "$server_pgid" ]]
  }
  publish_abort() {
    local temporary
    [[ -e "$WAVE_ABORT_FILE" ]] && return 0
    temporary="$(mktemp "$(dirname "$WAVE_ABORT_FILE")/.abort.XXXXXX")" || return 1
    printf 'gpu=%s\nselector=%s\n' "$GPU_INDEX" "$SELECTOR" > "$temporary"
    ln "$temporary" "$WAVE_ABORT_FILE" || { rm -f "$temporary"; return 1; }
    rm -f "$temporary"
  }
  child_failure() {
    local status=$? deadline quiet_deadline still_owned=0
    trap - EXIT INT TERM
    set +e
    rm -f "$RUN_DIR/ready.json"
    publish_abort
    if owned_server_running; then
      {
        date -u +epoch_s=%s
        echo "server_pid=$server_pid"
        echo "server_start_ticks=$server_start_ticks"
        echo "server_pgid=$server_pgid"
        stat -c 'server_log_size=%s' "$RUN_DIR/server.stdout.log" 2>/dev/null || true
      } > "$RUN_DIR/passive-drain-before.env"
      quiet_deadline=$((SECONDS + PASSIVE_DRAIN_S))
      while (( SECONDS < quiet_deadline )) && owned_server_running; do sleep 1; done
      owned_server_running && still_owned=1
      {
        date -u +epoch_s=%s
        echo "server_still_owned=$still_owned"
        stat -c 'server_log_size=%s' "$RUN_DIR/server.stdout.log" 2>/dev/null || true
      } > "$RUN_DIR/passive-drain-after.env"
    fi
    if owned_server_running; then
      kill -TERM "$server_pid" 2>/dev/null
      deadline=$((SECONDS + TERM_GRACE_S))
      while (( SECONDS < deadline )) && owned_server_running; do sleep 1; done
      if owned_server_running; then
        cleanup_forced=1
        kill -KILL "$server_pid" 2>/dev/null
        deadline=$((SECONDS + KILL_GRACE_S))
        while (( SECONDS < deadline )) && owned_server_running; do sleep 1; done
      fi
      if owned_server_running; then cleanup_survivor=1; else wait "$server_pid" 2>/dev/null || true; fi
    fi
    {
      echo "status=FAIL"
      echo "exit_status=$status"
      echo "gpu_index=$GPU_INDEX"
      echo "selector=$SELECTOR"
      echo "forced_kill=$cleanup_forced"
      echo "cleanup_survivor=$cleanup_survivor"
      echo "normal_complete=$normal_complete"
    } > "$RUN_DIR/cleanup-status.env"
    printf 'FAIL\n' > "$RUN_DIR/run-status.txt"
    rm -f "$RUN_DIR/artifacts.sha256" "$RUN_DIR/diagnostic-completion-status.json"
    seal_directory "$RUN_DIR" artifacts.sha256 diagnostic-completion-status.json || true
    exit "$status"
  }
  trap child_failure EXIT
  trap 'exit 130' INT TERM

  validate_lease_fd "$QWEN36_GPU_LEASE_FD" "$gpu_lease" || die "invalid inherited GPU lease"
  validate_lease_fd "$QWEN36_PORT_LEASE_FD" "$port_lease" || die "invalid inherited port lease"
  [[ -r "/proc/$$/fd/$MODEL_FD" ]] || die "model FD is unreadable"
  [[ "$(stat -Lc %s "/proc/$$/fd/$MODEL_FD")" == "$EXPECTED_MODEL_SIZE" ]] || die "model FD size drift"
  capture_model_stat "/proc/$$/fd/$MODEL_FD" "$RUN_DIR/model-stat-prelaunch.json"
  cmp -s "$MODEL_STAT_BASELINE" "$RUN_DIR/model-stat-prelaunch.json" || die "model identity drift"
  sha256sum -c "$WAVE_INPUT_MANIFEST" > "$RUN_DIR/wave-inputs-prelaunch.check.txt"

  timeout 10 ss -H -ltn "sport = :$PORT" > "$RUN_DIR/port-preflight.txt" \
    2> "$RUN_DIR/port-preflight.stderr" || die "child port query failed"
  [[ ! -s "$RUN_DIR/port-preflight.txt" ]] || die "port already has a listener"
  [[ ! -e "$WAVE_ABORT_FILE" ]] || die "peer aborted before preflight XPU sample"
  sample_gpu "$GPU_INDEX" "$RUN_DIR/xpu-smi-before.txt" || die "preflight XPU sample failed"
  pre_mib="$(parse_gpu_used_mib "$RUN_DIR/xpu-smi-before.txt" "$GPU_INDEX")" || die "preflight XPU sample unparseable or wrong device"
  (( pre_mib <= GPU_IDLE_MAX_MIB )) || die "GPU is not idle"

  runtime_report "$RUN_DIR/runtime-reference.json" "$OUTER_RUNTIME_REFERENCE"
  local runtime_reference_sha
  runtime_reference_sha="$(file_sha256 "$RUN_DIR/runtime-reference.json")" || die "reference report hash failed"

  [[ ! -e "$WAVE_ABORT_FILE" ]] || die "peer aborted before server launch"
  QWEN36_MODEL_FD="$MODEL_FD" GPU_INDEX="$GPU_INDEX" PORT="$PORT" MODEL="$MODEL" \
  MODEL_ALIAS="qwen36-27b-q8_0-target-only" LLAMA_SERVER="$LLAMA_SERVER" \
  RUNTIME_MANIFEST="$RUNTIME_MANIFEST" CTX_SIZE=65536 PARALLEL_SLOTS=2 \
  KV_UNIFIED=0 CONT_BATCHING=1 BATCH_SIZE=1024 UBATCH_SIZE=128 \
  N_GPU_LAYERS=99 THREADS=8 HTTP_THREADS=6 POLL=50 LOG_VERBOSITY=4 \
  CACHE_TYPE_K=f16 CACHE_TYPE_V=f16 FLASH_ATTN=on \
  LANE_DNN_ENABLED=0 LANE_OPT_ENABLED=1 \
  LANE_FA_ONEDNN=1 LANE_FA_ONEDNN_MAX_KV=0 LANE_MKL_FA=1 \
  LANE_SYCL_FLASH_ATTN=1 LANE_Q8_0_C2_CANONICAL_MMVQ="$SELECTOR" \
  LOG="$RUN_DIR/server.identity.log" SERVER_OUTPUT_LOG="$RUN_DIR/server.stdout.log" \
  OUT_DIR="$RUN_DIR" \
    "$LAUNCHER" > "$RUN_DIR/launcher.stdout.log" 2> "$RUN_DIR/launcher.stderr.log" &
  server_pid=$!
  server_start_ticks="$(process_start_ticks "$server_pid")"
  server_pgid="$(ps -o pgid= -p "$server_pid" | awk '{print $1}')"
  [[ "$server_start_ticks" =~ ^[1-9][0-9]*$ ]] || die "server start-tick capture failed"
  [[ "$server_pgid" == "$(ps -o pgid= -p $$ | awk '{print $1}')" ]] || die "server escaped child process group"
  printf '%s\n' "$server_pid" > "$RUN_DIR/server.pid"

  local deadline=$((SECONDS + READINESS_TIMEOUT_S))
  until curl -fsS "http://127.0.0.1:${PORT}/v1/models" > "$RUN_DIR/models.json" 2> "$RUN_DIR/models.err"; do
    [[ ! -e "$WAVE_ABORT_FILE" ]] || die "peer aborted during server readiness"
    owned_server_running || die "server exited before readiness"
    (( SECONDS < deadline )) || die "server readiness timeout"
    sleep 2
  done
  jq -e --arg alias "qwen36-27b-q8_0-target-only" '
    (.data|length)==1 and .data[0].id==$alias and .data[0].meta.n_ctx==32768
    and .data[0].meta.ftype=="Q8_0" and .data[0].meta.n_params==26895998464
  ' "$RUN_DIR/models.json" >/dev/null || die "model endpoint identity failed"
  python3 "$SERVER_ATTESTER" --server-log "$RUN_DIR/server.stdout.log" \
    --identity-log "$RUN_DIR/server.identity.log" --out "$RUN_DIR/server-attestation.json" \
    --model-size "$EXPECTED_MODEL_SIZE" --runtime-sha256 "$EXPECTED_RUNTIME_SHA256" \
    --minimum-fit-free-mib "$MIN_FIT_FREE_MIB"
  local server_attestation_sha
  server_attestation_sha="$(file_sha256 "$RUN_DIR/server-attestation.json")" || die "server attestation hash failed"
  [[ ! -e "$WAVE_ABORT_FILE" ]] || die "peer aborted before loaded XPU sample"
  sample_gpu "$GPU_INDEX" "$RUN_DIR/xpu-smi-loaded.txt" || die "loaded XPU sample failed"
  loaded_mib="$(parse_gpu_used_mib "$RUN_DIR/xpu-smi-loaded.txt" "$GPU_INDEX")" || die "loaded XPU sample unparseable or wrong device"
  (( loaded_mib - pre_mib >= MIN_LOADED_DELTA_MIB )) || die "loaded VRAM delta too small"
  capture_model_stat "/proc/$$/fd/$MODEL_FD" "$RUN_DIR/model-stat-loaded.json"
  cmp -s "$MODEL_STAT_BASELINE" "$RUN_DIR/model-stat-loaded.json" || die "model changed during load"
  owned_server_running || die "server died after live attestation"

  deadline=$((SECONDS + 30))
  if [[ "$SELECTOR" == 1 ]]; then
    until grep -Eq 'SYCL_Q8_0_C2_CANONICAL_MMVQ first-hit: layout=flat ' "$RUN_DIR/server.stdout.log"; do
      owned_server_running || die "server died awaiting warmup marker"
      (( SECONDS < deadline )) || die "selector-on warmup flat marker timeout"
      sleep 1
    done
  fi
  sleep 1
  cp --no-clobber "$RUN_DIR/server.stdout.log" "$RUN_DIR/prerelease-prefix.log"
  [[ -s "$RUN_DIR/prerelease-prefix.log" ]] || die "empty prerelease log prefix"
  cmp -n "$(stat -c %s "$RUN_DIR/prerelease-prefix.log")" \
    "$RUN_DIR/prerelease-prefix.log" "$RUN_DIR/server.stdout.log" || die "prefix snapshot is not a byte prefix"

  atomic_json "$RUN_DIR/ready.json" -n --argjson gpu "$GPU_INDEX" \
    --argjson selector "$SELECTOR" --argjson port "$PORT" --argjson pid "$server_pid" \
    --arg attestation_sha "$server_attestation_sha" \
    --arg prefix_sha "$(file_sha256 "$RUN_DIR/prerelease-prefix.log")" \
    '{ready:true,gpu_index:$gpu,selector:$selector,port:$port,server_pid:$pid,server_attestation_sha256:$attestation_sha,prerelease_prefix_sha256:$prefix_sha}'

  deadline=$((SECONDS + READINESS_TIMEOUT_S))
  while [[ ! -f "$WAVE_RELEASE_FILE" ]]; do
    [[ ! -f "$WAVE_ABORT_FILE" ]] || die "wave aborted before release"
    owned_server_running || die "server died before release"
    (( SECONDS < deadline )) || die "release barrier timeout"
    sleep 1
  done
  jq -e '.released==true and .phase=="canonical-q8-c1-oracle"' "$WAVE_RELEASE_FILE" >/dev/null || die "invalid release marker"

  python3 "$ANALYZER" capture-live-binding --matrix-client "$MATRIX_CLIENT" \
    --matrix-client-sha256 "$EXPECTED_MATRIX_SHA256" --server-pid "$server_pid" \
    --port "$PORT" --runtime-sha256 "$EXPECTED_RUNTIME_SHA256" \
    --out "$RUN_DIR/live-binding-before.json"
  capture_started=1
  timeout --signal=TERM --kill-after=30 "$REQUEST_TIMEOUT_S" \
    python3 "$CAPTURE_CLIENT" --mode sequential-oracle \
      --base-url "http://127.0.0.1:${PORT}" --suite "$SUITE" --band short \
      --case-order forward --prompt-builder "$PROMPT_BUILDER" --common-script "$COMMON_CAPTURE" \
      --server-attestation "$RUN_DIR/server-attestation.json" \
      --baseline-canary-suite "$BASELINE_CANARY_SUITE" \
      --baseline-canary-oracle "$BASELINE_CANARY" \
      --baseline-canary-oracle-sha256 "$EXPECTED_CANARY_SHA256" \
      --baseline-canary-prompt-id incident-retrospective --out "$RUN_DIR/oracle.json" \
      --timeout "$REQUEST_TIMEOUT_S" --model-sha256 "$EXPECTED_MODEL_SHA256" \
      --runtime-sha256 "$EXPECTED_RUNTIME_SHA256" --cache-type-k f16 --cache-type-v f16 \
      --ctx-size-total 65536 --ctx-size-per-slot 32768 \
      > "$RUN_DIR/client.stdout.log" 2> "$RUN_DIR/client.stderr.log"
  capture_complete=1
  python3 "$ANALYZER" capture-live-binding --matrix-client "$MATRIX_CLIENT" \
    --matrix-client-sha256 "$EXPECTED_MATRIX_SHA256" --server-pid "$server_pid" \
    --port "$PORT" --runtime-sha256 "$EXPECTED_RUNTIME_SHA256" \
    --out "$RUN_DIR/live-binding-after.json"
  owned_server_running || die "server died during oracle capture"
  sha256sum -c "$WAVE_INPUT_MANIFEST" > "$RUN_DIR/wave-inputs-postcapture.check.txt"

  kill -TERM "$server_pid"
  deadline=$((SECONDS + TERM_GRACE_S))
  while (( SECONDS < deadline )) && owned_server_running; do sleep 1; done
  if owned_server_running; then cleanup_forced=1; die "server did not stop gracefully"; fi
  wait "$server_pid" 2>/dev/null || true
  timeout 10 ss -H -ltn "sport = :$PORT" > "$RUN_DIR/port-postteardown.txt" \
    2> "$RUN_DIR/port-postteardown.stderr" || die "post-teardown port query failed"
  [[ ! -s "$RUN_DIR/port-postteardown.txt" ]] || die "port remained open"

  runtime_report "$RUN_DIR/runtime-final.json" "$RUN_DIR/runtime-reference.json"
  local runtime_final_sha
  runtime_final_sha="$(file_sha256 "$RUN_DIR/runtime-final.json")" || die "final runtime report hash failed"
  python3 "$ANALYZER" attest-lane --oracle "$RUN_DIR/oracle.json" \
    --server-log "$RUN_DIR/server.stdout.log" --identity-log "$RUN_DIR/server.identity.log" \
    --prerelease-prefix "$RUN_DIR/prerelease-prefix.log" \
    --runtime-manifest "$RUNTIME_MANIFEST" --runtime-manifest-sha256 "$EXPECTED_MANIFEST_SHA256" \
    --runtime-reference-report "$RUN_DIR/runtime-reference.json" \
    --runtime-reference-report-sha256 "$runtime_reference_sha" \
    --runtime-final-report "$RUN_DIR/runtime-final.json" --runtime-final-report-sha256 "$runtime_final_sha" \
    --canonical-attester "$CANONICAL_ATTESTER" \
    --canonical-attester-sha256 "$EXPECTED_CANONICAL_ATTESTER_SHA256" \
    --server-attestation "$RUN_DIR/server-attestation.json" \
    --server-attestation-sha256 "$server_attestation_sha" \
    --binding-before "$RUN_DIR/live-binding-before.json" \
    --binding-after "$RUN_DIR/live-binding-after.json" --matrix-client "$MATRIX_CLIENT" \
    --matrix-client-sha256 "$EXPECTED_MATRIX_SHA256" --model-sha256 "$EXPECTED_MODEL_SHA256" \
    --runtime-sha256 "$EXPECTED_RUNTIME_SHA256" --suite-sha256 "$EXPECTED_SUITE_SHA256" \
    --gpu-index "$GPU_INDEX" --selector "$SELECTOR" --server-pid "$server_pid" \
    --port "$PORT" --out "$RUN_DIR/lane-attestation.json"
  jq -e '.passed==true and .evidence_class=="diagnostic-only" and .performance_promotable==false' \
    "$RUN_DIR/lane-attestation.json" >/dev/null || die "lane attestation failed"

  capture_model_stat "/proc/$$/fd/$MODEL_FD" "$RUN_DIR/model-stat-final.json"
  cmp -s "$MODEL_STAT_BASELINE" "$RUN_DIR/model-stat-final.json" || die "final model stat drift"
  sha256sum -c "$WAVE_INPUT_MANIFEST" > "$RUN_DIR/wave-inputs-postteardown.check.txt"
  printf 'PRE_SEAL_EVIDENCE_VALID\n' > "$RUN_DIR/run-status.txt"
  {
    echo "status=PASS"
    echo "gpu_index=$GPU_INDEX"
    echo "selector=$SELECTOR"
    echo "graceful_server_teardown=1"
    echo "forced_kill=0"
    echo "cleanup_survivor=0"
    echo "port_closed=1"
  } > "$RUN_DIR/cleanup-status.env"
  seal_directory "$RUN_DIR" artifacts.sha256 diagnostic-completion-status.json || die "lane seal failed"
  normal_complete=1
  trap - EXIT INT TERM
}

print_wave_plan() {
  python3 "$ANALYZER" print-plan --port-base "$PORT_BASE"
}

if [[ "${1:-}" == "--print-wave-plan" ]]; then
  [[ $# -eq 1 ]] || die "--print-wave-plan accepts no other arguments"
  print_wave_plan
  exit 0
fi

if [[ "${1:-}" == "--child" ]]; then
  [[ $# -eq 1 ]] || die "--child accepts no other arguments"
  child_main
  exit 0
fi
if [[ "${1:-}" != "--run-phase1" || $# -ne 1 ]]; then
  die "live execution requires the single explicit argument --run-phase1"
fi
shift

for command_name in awk bash chmod cmp cp curl date df dirname env find flock grep id \
  journalctl jq mkdir mktemp pgrep ps python3 readlink setsid sha256sum sort ss stat \
  timeout xargs xpu-smi; do
  command -v "$command_name" >/dev/null 2>&1 || die "required command missing: $command_name"
done
for path in "$ANALYZER" "$LAUNCHER" "$SERVER_ATTESTER" "$MATRIX_CLIENT" \
  "$CAPTURE_CLIENT" "$CANONICAL_ATTESTER" "$COMMON_CAPTURE" "$PROMPT_BUILDER" \
  "$MODEL_MANIFEST" "$RUNTIME_MANIFEST" "$SUITE" "$MODEL" "$LLAMA_SERVER" \
  "$OLD_ORACLE" "$BASELINE_CANARY" "$BASELINE_CANARY_SUITE" \
  "$OFFICIAL_C1_DIR/exact-tokens.json" "$OFFICIAL_C1_DIR/artifacts.sha256" \
  "$OFFICIAL_C1_DIR/completion-status.json"; do
  [[ -f "$path" ]] || die "required file missing: $path"
done
[[ -x "$LLAMA_SERVER" ]] || die "candidate llama-server is not executable"
[[ -f /opt/intel/oneapi/setvars.sh ]] || die "oneAPI setup is missing"

for value_name in PORT_BASE START_STAGGER_S READINESS_TIMEOUT_S REQUEST_TIMEOUT_S \
  WAVE_TIMEOUT_S TERM_GRACE_S KILL_GRACE_S PASSIVE_DRAIN_S MIN_HOST_AVAILABLE_KIB \
  MIN_FAST_FREE_KIB; do require_uint "$value_name" "${!value_name}"; done
(( PORT_BASE >= 1024 && PORT_BASE <= 65532 )) || die "PORT_BASE must leave four valid ports"
(( START_STAGGER_S >= 5 )) || die "START_STAGGER_S may not weaken the 5s floor"
(( READINESS_TIMEOUT_S >= 600 && REQUEST_TIMEOUT_S >= 900 && WAVE_TIMEOUT_S >= 3600 )) || die "timeout safety floor violated"
(( TERM_GRACE_S >= 60 && KILL_GRACE_S >= 10 && PASSIVE_DRAIN_S >= 60 )) || die "cleanup safety floor violated"
(( MIN_HOST_AVAILABLE_KIB >= 100663296 && MIN_FAST_FREE_KIB >= 10485760 )) || die "resource floor weakened"
[[ "$WAVE_DIR" == /* && "$WAVE_DIR" != / && ! -e "$WAVE_DIR" ]] || die "WAVE_DIR must be a new non-root absolute path"

assert_sha "$LAUNCHER" "$EXPECTED_LAUNCHER_SHA256"
assert_sha "$SERVER_ATTESTER" "$EXPECTED_SERVER_ATTESTER_SHA256"
assert_sha "$MATRIX_CLIENT" "$EXPECTED_MATRIX_SHA256"
assert_sha "$CAPTURE_CLIENT" "$EXPECTED_CAPTURE_CLIENT_SHA256"
assert_sha "$COMMON_CAPTURE" "$EXPECTED_COMMON_CAPTURE_SHA256"
assert_sha "$PROMPT_BUILDER" "$EXPECTED_PROMPT_BUILDER_SHA256"
assert_sha "$MODEL_MANIFEST" "$EXPECTED_MODEL_MANIFEST_SHA256"
assert_sha "$RUNTIME_MANIFEST" "$EXPECTED_MANIFEST_SHA256"
assert_sha "$CANONICAL_ATTESTER" "$EXPECTED_CANONICAL_ATTESTER_SHA256"
[[ "$EXPECTED_ANALYZER_SHA256" =~ ^[0-9a-f]{64}$ ]] || die "analyzer is not frozen; live execution remains disabled"
assert_sha "$ANALYZER" "$EXPECTED_ANALYZER_SHA256"
SCRIPT_SHA256="$(file_sha256 "$SCRIPT")" || die "could not freeze runner hash"
assert_sha "$SUITE" "$EXPECTED_SUITE_SHA256"
assert_sha "$OLD_ORACLE" "$EXPECTED_OLD_ORACLE_SHA256"
assert_sha "$BASELINE_CANARY" "$EXPECTED_CANARY_SHA256"
assert_sha "$BASELINE_CANARY_SUITE" "$EXPECTED_CANARY_SUITE_SHA256"
assert_sha "$OFFICIAL_C1_DIR/exact-tokens.json" "$EXPECTED_OFFICIAL_C1_RESULT_SHA256"
assert_sha "$OFFICIAL_C1_DIR/artifacts.sha256" "$EXPECTED_OFFICIAL_C1_MANIFEST_SHA256"
assert_sha "$OFFICIAL_C1_DIR/completion-status.json" "$EXPECTED_OFFICIAL_C1_MARKER_SHA256"
assert_sha "$LLAMA_SERVER" "$EXPECTED_RUNTIME_SHA256"
[[ "$(stat -c %s "$MODEL")" == "$EXPECTED_MODEL_SIZE" ]] || die "model size mismatch"
[[ "$(jq -er .sha256 "$MODEL_MANIFEST")" == "$EXPECTED_MODEL_SHA256" ]] || die "model manifest mismatch"
[[ "$(jq -er .llama_server_path "$RUNTIME_MANIFEST")" == "$LLAMA_SERVER" ]] || die "candidate runtime path mismatch"
[[ "$(jq -er .llama_server_sha256 "$RUNTIME_MANIFEST")" == "$EXPECTED_RUNTIME_SHA256" ]] || die "candidate runtime manifest mismatch"

unexpected_env=()
while IFS='=' read -r name _; do
  case "$name" in GGML_*|SYCL_*|ZE_*|ZES_*|UR_*|ONEAPI_DEVICE_SELECTOR|LD_PRELOAD|LLAMA_*) unexpected_env+=("$name");; esac
done < <(env)
(( ${#unexpected_env[@]} == 0 )) || die "unexpected accelerator environment: ${unexpected_env[*]}"

mkdir -p "$(dirname "$WAVE_DIR")"
mkdir "$WAVE_DIR"
START_EPOCH="$(date +%s)"
WAVE_ABORT_FILE="$WAVE_DIR/abort"
WAVE_RELEASE_FILE="$WAVE_DIR/release.json"
OUTER_COMPLETE=0
OUTER_FORCED_KILL=0
OUTER_SURVIVOR=0
declare -a CHILD_PIDS=() CHILD_START_TICKS=() CHILD_PGIDS=() CHILD_SIDS=() CHILD_DIRS=()
declare -a GPU_LEASE_FDS=() PORT_LEASE_FDS=()

owned_child_group() {
  local gpu="$1" pid="${CHILD_PIDS[$gpu]:-}" ticks="${CHILD_START_TICKS[$gpu]:-}" pgid="${CHILD_PGIDS[$gpu]:-}" sid="${CHILD_SIDS[$gpu]:-}"
  [[ -n "$pid" && -n "$ticks" && -n "$pgid" && -n "$sid" ]] || return 1
  pid_running "$pid" || return 1
  [[ "$(process_start_ticks "$pid" 2>/dev/null || true)" == "$ticks" ]] || return 1
  [[ "$(ps -o pgid= -p "$pid" 2>/dev/null | awk '{print $1}')" == "$pgid" ]] || return 1
  [[ "$(ps -o sid= -p "$pid" 2>/dev/null | awk '{print $1}')" == "$sid" && "$sid" == "$pgid" ]] || return 1
  group_alive "$pgid"
}

recorded_session_alive() {
  local gpu="$1" pgid="${CHILD_PGIDS[$gpu]:-}" sid="${CHILD_SIDS[$gpu]:-}"
  [[ -n "$pgid" && -n "$sid" && "$pgid" == "$sid" ]] || return 1
  local table rc
  if ! table="$(ps -eo pgid=,sid=,stat= 2>/dev/null)"; then return 0; fi
  if printf '%s\n' "$table" | awk -v sid="$sid" \
      '$2==sid && $3 !~ /^Z/ {found=1} END{exit(found?0:1)}'; then
    return 0
  fi
  rc=$?
  (( rc == 1 )) && return 1
  return 0
}

signal_recorded_session() {
  local gpu="$1" signal="$2" sid="${CHILD_SIDS[$gpu]:-}" table group
  [[ "$sid" =~ ^[1-9][0-9]*$ ]] || return 1
  table="$(ps -eo pgid=,sid=,stat= 2>/dev/null)" || return 1
  while read -r group; do
    [[ "$group" =~ ^[1-9][0-9]*$ ]] || return 1
    kill "-$signal" -- "-$group" 2>/dev/null || true
  done < <(printf '%s\n' "$table" | awk -v sid="$sid" '$2==sid && $3 !~ /^Z/ {print $1}' | sort -n -u)
}

capture_recorded_group_members() {
  local output="$1" gpu table
  : > "$output"
  if ! table="$(ps -eo pid=,ppid=,pgid=,sid=,stat=,lstart=,args= 2>/dev/null)"; then
    printf 'PS_QUERY_ERROR\n' > "$output"
    return 2
  fi
  for gpu in 0 1 2 3; do
    [[ -n "${CHILD_PGIDS[$gpu]:-}" ]] || continue
    printf '%s\n' "$table" | \
      awk -v gpu="$gpu" -v sid="${CHILD_SIDS[$gpu]}" \
      '$4==sid && $5 !~ /^Z/ {print "gpu=" gpu, $0}' >> "$output"
  done
}

terminate_child_groups() {
  local gpu deadline any quiet_deadline abort_tmp
  if [[ ! -e "$WAVE_ABORT_FILE" ]]; then
    abort_tmp="$(mktemp "$WAVE_DIR/.outer-abort.XXXXXX")" || true
    if [[ -n "${abort_tmp:-}" ]]; then
      printf 'outer_abort=1\n' > "$abort_tmp"
      ln "$abort_tmp" "$WAVE_ABORT_FILE" 2>/dev/null || true
      rm -f "$abort_tmp"
    fi
  fi
  capture_recorded_group_members "$WAVE_DIR/failure-drain-members-before.txt" || true
  quiet_deadline=$((SECONDS + PASSIVE_DRAIN_S))
  while (( SECONDS < quiet_deadline )); do
    any=0; for gpu in 0 1 2 3; do recorded_session_alive "$gpu" && any=1; done
    (( any == 0 )) && break
    sleep 1
  done
  capture_recorded_group_members "$WAVE_DIR/failure-drain-members-after.txt" || true
  for gpu in 0 1 2 3; do
    recorded_session_alive "$gpu" && signal_recorded_session "$gpu" TERM || true
  done
  deadline=$((SECONDS + TERM_GRACE_S))
  while (( SECONDS < deadline )); do
    any=0; for gpu in 0 1 2 3; do recorded_session_alive "$gpu" && any=1; done
    (( any == 0 )) && break; sleep 1
  done
  for gpu in 0 1 2 3; do
    if recorded_session_alive "$gpu"; then
      OUTER_FORCED_KILL=1
      signal_recorded_session "$gpu" KILL || true
    fi
  done
  deadline=$((SECONDS + KILL_GRACE_S))
  while (( SECONDS < deadline )); do
    any=0; for gpu in 0 1 2 3; do recorded_session_alive "$gpu" && any=1; done
    (( any == 0 )) && break; sleep 1
  done
  for gpu in 0 1 2 3; do
    if recorded_session_alive "$gpu"; then OUTER_SURVIVOR=1
    elif [[ -n "${CHILD_PIDS[$gpu]:-}" ]]; then wait "${CHILD_PIDS[$gpu]}" 2>/dev/null || true
    fi
  done
}

phase_passive_scan() {
  local prefix="$1" fault=0 rc gpu
  if ! capture_recorded_group_members "$WAVE_DIR/${prefix}-group-members.txt"; then fault=1; fi
  [[ ! -s "$WAVE_DIR/${prefix}-group-members.txt" ]] || fault=1
  : > "$WAVE_DIR/${prefix}-lane-listeners.txt"
  for gpu in 0 1 2 3; do
    if timeout 10 ss -H -ltn "sport = :$((PORT_BASE + gpu))" \
        >> "$WAVE_DIR/${prefix}-lane-listeners.txt" 2>> "$WAVE_DIR/${prefix}-lane-listeners.stderr"; then
      :
    else
      fault=1
    fi
  done
  [[ ! -s "$WAVE_DIR/${prefix}-lane-listeners.txt" ]] || fault=1
  if pgrep -af '[l]lama-server|[c]apture-simultaneous-c2.py|[c]apture-c2-token-matrix.py' \
      > "$WAVE_DIR/${prefix}-processes.txt" 2> "$WAVE_DIR/${prefix}-processes.stderr"; then
    fault=1
  else
    rc=$?; (( rc == 1 )) || fault=1
  fi
  mapfile -d '' scan_logs < <(find "$WAVE_DIR" -type f \( \
    -name '*runner.log' -o -name 'launcher.stdout.log' -o -name 'launcher.stderr.log' \
    -o -name 'client.stdout.log' -o -name 'client.stderr.log' -o \
    -name 'server.stdout.log' -o -name 'server.identity.log' \) -print0)
  if (( ${#scan_logs[@]} == 0 )); then
    : > "$WAVE_DIR/${prefix}-log-error-scan.txt"
    printf 'no lane logs found\n' > "$WAVE_DIR/${prefix}-log-error-scan.stderr"
    fault=1
  else
    if grep -EHi 'UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST|out of memory|segmentation fault|core dumped|Aborted|Timedout job' \
        "${scan_logs[@]}" > "$WAVE_DIR/${prefix}-log-error-scan.txt" 2> "$WAVE_DIR/${prefix}-log-error-scan.stderr"; then
      fault=1
    else
      rc=$?; (( rc == 1 )) || fault=1
    fi
  fi
  if ! journalctl -k --since "@$START_EPOCH" --no-pager \
      > "$WAVE_DIR/${prefix}-kernel-journal.txt" 2> "$WAVE_DIR/${prefix}-kernel-journal.stderr"; then
    fault=1
  fi
  if grep -Ei 'xe.*(reset|wedg|fault|hang|timedout|device lost)|GuC.*reset|Fault response|VM.*fault|PCIe.*AER|UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST' \
      "$WAVE_DIR/${prefix}-kernel-journal.txt" > "$WAVE_DIR/${prefix}-device-error-scan.txt" \
      2> "$WAVE_DIR/${prefix}-device-error-scan.stderr"; then
    fault=1
  else
    rc=$?; (( rc == 1 )) || fault=1
  fi
  printf 'passive_fault_detected=%s\n' "$fault" > "$WAVE_DIR/${prefix}-passive-status.env"
  (( fault == 0 ))
}

capture_failure_predrain() {
  local gpu
  date -u +epoch_s=%s > "$WAVE_DIR/failure-predrain-time.env"
  capture_recorded_group_members "$WAVE_DIR/failure-predrain-group-members.txt" || true
  : > "$WAVE_DIR/failure-predrain-lane-listeners.txt"
  for gpu in 0 1 2 3; do
    timeout 10 ss -H -ltn "sport = :$((PORT_BASE + gpu))" \
      >> "$WAVE_DIR/failure-predrain-lane-listeners.txt" \
      2>> "$WAVE_DIR/failure-predrain-lane-listeners.stderr" || true
  done
  pgrep -af '[l]lama-server|[c]apture-simultaneous-c2.py|[c]apture-c2-token-matrix.py' \
    > "$WAVE_DIR/failure-predrain-processes.txt" \
    2> "$WAVE_DIR/failure-predrain-processes.stderr" || true
  find "$WAVE_DIR" -type f \( -name '*.log' -o -name '*.stderr' \) -printf '%s\t%p\n' \
    > "$WAVE_DIR/failure-predrain-log-sizes.tsv" 2> "$WAVE_DIR/failure-predrain-log-sizes.stderr" || true
  journalctl -k --since "@$START_EPOCH" --no-pager \
    > "$WAVE_DIR/failure-predrain-kernel-journal.txt" \
    2> "$WAVE_DIR/failure-predrain-kernel-journal.stderr" || true
}

outer_failure() {
  local status=$?
  trap - EXIT INT TERM
  set +e
  capture_failure_predrain
  terminate_child_groups
  if phase_passive_scan failure-postcleanup; then passive_rc=0; else passive_rc=1; fi
  set +e
  {
    echo "status=FAIL"; echo "exit_status=$status"; echo "forced_kill=$OUTER_FORCED_KILL"
    echo "cleanup_survivor=$OUTER_SURVIVOR"; echo "body_complete=$OUTER_COMPLETE"
    echo "failure_passive_scan_rc=$passive_rc"; echo "active_xpu_probe_after_failure=0"
  } > "$WAVE_DIR/wave-cleanup-status.env"
  printf 'FAIL\n' > "$WAVE_DIR/wave-status.txt"
  rm -f "$WAVE_DIR/wave-artifacts.sha256" "$WAVE_DIR/wave-diagnostic-completion-status.json"
  if seal_directory "$WAVE_DIR" wave-artifacts.sha256 wave-diagnostic-completion-status.json; then
    failure_manifest_sha="$(file_sha256 "$WAVE_DIR/wave-artifacts.sha256")"
    atomic_json "$WAVE_DIR/wave-diagnostic-completion-status.json" -n \
      --arg manifest_sha "$failure_manifest_sha" --argjson original_status "$status" \
      '{schema_version:1,phase:"four-gpu-sequential-c1-oracle-on-c2-topology",status:"FAIL",evidence_valid:false,evidence_class:"diagnostic-only-failure",performance_promotable:false,active_xpu_probe_after_failure:false,original_status:$original_status,artifact_manifest:"wave-artifacts.sha256",artifact_manifest_sha256:$manifest_sha}' || true
  fi
  printf '%s\n' "$WAVE_DIR"
  (( status != 0 )) || status=1
  exit "$status"
}
trap outer_failure EXIT
trap 'exit 130' INT TERM

exec 9>"/run/user/$(id -u)/qwen36-canonical-q8-c1-oracle-four-gpu.lock"
flock -n 9 || die "another canonical c1-oracle wave owns the host lock"
GPU_LEASE_DIR="/run/user/$(id -u)/qwen36-b70-gpu-leases"
PORT_LEASE_DIR="/run/user/$(id -u)/qwen36-b70-port-leases"
mkdir -p "$GPU_LEASE_DIR" "$PORT_LEASE_DIR"
for gpu in 0 1 2 3; do
  exec {lease_fd}>"$GPU_LEASE_DIR/gpu${gpu}.lock"
  flock -n "$lease_fd" || die "GPU $gpu is leased"
  GPU_LEASE_FDS[$gpu]="$lease_fd"
  port=$((PORT_BASE + gpu))
  exec {port_fd}>"$PORT_LEASE_DIR/port${port}.lock"
  flock -n "$port_fd" || die "port $port is leased"
  PORT_LEASE_FDS[$gpu]="$port_fd"
done

exec {MODEL_FD}<"$MODEL"
flock -s -n "$MODEL_FD" || die "model lock unavailable"
[[ "$MODEL" -ef "/proc/$$/fd/$MODEL_FD" ]] || die "model FD/path mismatch"
capture_model_stat "/proc/$$/fd/$MODEL_FD" "$WAVE_DIR/model-stat-before-hash.json"
printf '%s  %s\n' "$EXPECTED_MODEL_SHA256" "/proc/$$/fd/$MODEL_FD" | sha256sum -c - > "$WAVE_DIR/model-sha256-initial.check.txt"
capture_model_stat "/proc/$$/fd/$MODEL_FD" "$WAVE_DIR/model-stat-after-hash.json"
cmp -s "$WAVE_DIR/model-stat-before-hash.json" "$WAVE_DIR/model-stat-after-hash.json" || die "model changed during hash"
cp "$WAVE_DIR/model-stat-after-hash.json" "$WAVE_DIR/model-stat-baseline.json"

set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null
set -u
runtime_report "$WAVE_DIR/runtime-initial.json"

available_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
fast_free_kib="$(df -Pk /mnt/fast-ai | awk 'NR==2 {print $4}')"
(( available_kib >= MIN_HOST_AVAILABLE_KIB )) || die "host memory below four-server floor"
(( fast_free_kib >= MIN_FAST_FREE_KIB )) || die "artifact storage below floor"
printf 'available_kib=%s\nminimum_kib=%s\n' "$available_kib" "$MIN_HOST_AVAILABLE_KIB" > "$WAVE_DIR/host-memory-preflight.env"
printf 'available_kib=%s\nminimum_kib=%s\n' "$fast_free_kib" "$MIN_FAST_FREE_KIB" > "$WAVE_DIR/artifact-space-preflight.env"
if pgrep -af '[l]lama-server|[c]apture-simultaneous-c2.py|[c]apture-c2-token-matrix.py|[r]un-c2-validation.sh' \
    > "$WAVE_DIR/preflight-processes.txt" 2> "$WAVE_DIR/preflight-processes.stderr"; then
  die "an inference or validation process is already active"
else
  preflight_pgrep_rc=$?
  (( preflight_pgrep_rc == 1 )) || die "preflight process query failed with rc=$preflight_pgrep_rc"
fi
timeout 20 xpu-smi discovery -j > "$WAVE_DIR/xpu-smi-discovery.json"
jq -e '[.device_list[]|select(.device_function_type=="physical" and (.device_name|contains("Arc(TM) Pro B70")))] as $d | ($d|length)==4 and ([$d[].device_id]|sort)==[0,1,2,3] and ([$d[].pci_bdf_address]|unique|length)==4 and ([$d[].uuid]|unique|length)==4' "$WAVE_DIR/xpu-smi-discovery.json" >/dev/null || die "four distinct B70 devices not found"
for gpu in 0 1 2 3; do
  sample_gpu "$gpu" "$WAVE_DIR/xpu-smi-preflight-gpu${gpu}.txt"
  used="$(parse_gpu_used_mib "$WAVE_DIR/xpu-smi-preflight-gpu${gpu}.txt" "$gpu")" || die "preflight XPU sample unparseable or wrong device"
  (( used <= GPU_IDLE_MAX_MIB )) || die "GPU $gpu is not idle"
  timeout 10 ss -H -ltn "sport = :$((PORT_BASE + gpu))" \
    > "$WAVE_DIR/port-preflight-gpu${gpu}.txt" \
    2> "$WAVE_DIR/port-preflight-gpu${gpu}.stderr" || die "port query failed"
  [[ ! -s "$WAVE_DIR/port-preflight-gpu${gpu}.txt" ]] || die "lane port already in use"
done

OLD_ORACLE_SNAPSHOT="$WAVE_DIR/sequential-schema-adapter-oracle.json"
cp --no-clobber "$OLD_ORACLE" "$OLD_ORACLE_SNAPSHOT"
chmod 0444 "$OLD_ORACLE_SNAPSHOT"
assert_sha "$OLD_ORACLE_SNAPSHOT" "$EXPECTED_OLD_ORACLE_SHA256"
BASELINE_CANARY_SNAPSHOT="$WAVE_DIR/sealed-128-canary-oracle.json"
BASELINE_CANARY_SUITE_SNAPSHOT="$WAVE_DIR/sealed-128-canary-suite.json"
cp --no-clobber "$BASELINE_CANARY" "$BASELINE_CANARY_SNAPSHOT"
cp --no-clobber "$BASELINE_CANARY_SUITE" "$BASELINE_CANARY_SUITE_SNAPSHOT"
chmod 0444 "$BASELINE_CANARY_SNAPSHOT" "$BASELINE_CANARY_SUITE_SNAPSHOT"
assert_sha "$BASELINE_CANARY_SNAPSHOT" "$EXPECTED_CANARY_SHA256"
assert_sha "$BASELINE_CANARY_SUITE_SNAPSHOT" "$EXPECTED_CANARY_SUITE_SHA256"
OFFICIAL_C1_SNAPSHOT="$WAVE_DIR/official-c1-pass-packet"
cp -a "$OFFICIAL_C1_DIR" "$OFFICIAL_C1_SNAPSHOT"
assert_sha "$OFFICIAL_C1_SNAPSHOT/exact-tokens.json" "$EXPECTED_OFFICIAL_C1_RESULT_SHA256"
assert_sha "$OFFICIAL_C1_SNAPSHOT/artifacts.sha256" "$EXPECTED_OFFICIAL_C1_MANIFEST_SHA256"
assert_sha "$OFFICIAL_C1_SNAPSHOT/completion-status.json" "$EXPECTED_OFFICIAL_C1_MARKER_SHA256"
(cd "$OFFICIAL_C1_SNAPSHOT" && sha256sum -c artifacts.sha256 > "$WAVE_DIR/official-c1-snapshot.check.txt")
OLD_ORACLE="$OLD_ORACLE_SNAPSHOT"
BASELINE_CANARY="$BASELINE_CANARY_SNAPSHOT"
BASELINE_CANARY_SUITE="$BASELINE_CANARY_SUITE_SNAPSHOT"
OFFICIAL_C1_DIR="$OFFICIAL_C1_SNAPSHOT"
sha256sum "$SCRIPT" "$ANALYZER" "$LAUNCHER" "$SERVER_ATTESTER" "$MATRIX_CLIENT" \
  "$CAPTURE_CLIENT" "$COMMON_CAPTURE" "$PROMPT_BUILDER" "$CANONICAL_ATTESTER" \
  "$MODEL_MANIFEST" "$RUNTIME_MANIFEST" "$SUITE" "$OLD_ORACLE" \
  "$BASELINE_CANARY" "$BASELINE_CANARY_SUITE" "$OFFICIAL_C1_DIR/exact-tokens.json" \
  "$OFFICIAL_C1_DIR/artifacts.sha256" "$OFFICIAL_C1_DIR/completion-status.json" \
  > "$WAVE_DIR/wave-inputs.sha256"
WAVE_INPUT_MANIFEST="$WAVE_DIR/wave-inputs.sha256"
sha256sum -c "$WAVE_INPUT_MANIFEST" > "$WAVE_DIR/wave-inputs-initial.check.txt"

TASK_USER_HOME="/home/steve"
for gpu in 0 1 2 3; do
  [[ ! -e "$WAVE_ABORT_FILE" ]] || die "a prior lane aborted; refusing another launch"
  for ((prior=0; prior<gpu; prior++)); do
    owned_child_group "$prior" || die "prior child $prior vanished during stagger"
  done
  port=$((PORT_BASE + gpu)); selector="${SELECTORS[$gpu]}"; run_dir="$WAVE_DIR/gpu${gpu}-selector${selector}"
  session_gate="$WAVE_DIR/gpu${gpu}-session-gate.json"
  CHILD_DIRS[$gpu]="$run_dir"
  setsid --wait /usr/bin/env -i HOME="$TASK_USER_HOME" USER=steve LOGNAME=steve \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    LANG=C.utf8 LC_ALL=C.utf8 XDG_RUNTIME_DIR="/run/user/$(id -u)" \
    PORT_BASE="$PORT_BASE" GPU_INDEX="$gpu" SELECTOR="$selector" PORT="$port" RUN_DIR="$run_dir" \
    MODEL_FD="$MODEL_FD" QWEN36_MODEL_FD="$MODEL_FD" \
    QWEN36_GPU_LEASE_FD="${GPU_LEASE_FDS[$gpu]}" QWEN36_PORT_LEASE_FD="${PORT_LEASE_FDS[$gpu]}" \
    WAVE_RELEASE_FILE="$WAVE_RELEASE_FILE" WAVE_ABORT_FILE="$WAVE_ABORT_FILE" \
    SESSION_GATE="$session_gate" \
    WAVE_INPUT_MANIFEST="$WAVE_INPUT_MANIFEST" MODEL_STAT_BASELINE="$WAVE_DIR/model-stat-baseline.json" \
    OUTER_RUNTIME_REFERENCE="$WAVE_DIR/runtime-initial.json" READINESS_TIMEOUT_S="$READINESS_TIMEOUT_S" \
    REQUEST_TIMEOUT_S="$REQUEST_TIMEOUT_S" TERM_GRACE_S="$TERM_GRACE_S" \
    KILL_GRACE_S="$KILL_GRACE_S" PASSIVE_DRAIN_S="$PASSIVE_DRAIN_S" \
    EXPECTED_SCRIPT_SHA256="$SCRIPT_SHA256" \
    OLD_ORACLE="$OLD_ORACLE" BASELINE_CANARY="$BASELINE_CANARY" \
    BASELINE_CANARY_SUITE="$BASELINE_CANARY_SUITE" OFFICIAL_C1_DIR="$OFFICIAL_C1_DIR" \
    /usr/bin/bash "$SCRIPT" --child > "$WAVE_DIR/gpu${gpu}-runner.log" 2>&1 &
  launch_pid=$!
  launch_ticks="$(process_start_ticks "$launch_pid" 2>/dev/null || true)"
  transition_deadline=$((SECONDS + 10))
  launch_pgid=""; launch_sid=""
  while [[ "$launch_ticks" =~ ^[1-9][0-9]*$ ]] && (( SECONDS < transition_deadline )); do
    [[ "$(process_start_ticks "$launch_pid" 2>/dev/null || true)" == "$launch_ticks" ]] || break
    launch_pgid="$(ps -o pgid= -p "$launch_pid" 2>/dev/null | awk '{print $1}')"
    launch_sid="$(ps -o sid= -p "$launch_pid" 2>/dev/null | awk '{print $1}')"
    [[ "$launch_pgid" == "$launch_pid" && "$launch_sid" == "$launch_pid" ]] && break
    sleep 0.05
  done
  if [[ ! "$launch_ticks" =~ ^[1-9][0-9]*$ || "$launch_pgid" != "$launch_pid" || "$launch_sid" != "$launch_pid" || \
        "$(process_start_ticks "$launch_pid" 2>/dev/null || true)" != "$launch_ticks" ]]; then
    transition_abort="$(mktemp "$WAVE_DIR/.session-transition-abort.XXXXXX" 2>/dev/null || true)"
    if [[ -n "$transition_abort" ]]; then
      printf 'session_transition_failure_gpu=%s\n' "$gpu" > "$transition_abort"
      ln "$transition_abort" "$WAVE_ABORT_FILE" 2>/dev/null || true
      rm -f "$transition_abort"
    fi
    if [[ -z "$launch_ticks" || "$(process_start_ticks "$launch_pid" 2>/dev/null || true)" == "$launch_ticks" ]]; then
      kill -TERM "$launch_pid" 2>/dev/null || true
      transition_deadline=$((SECONDS + 10))
      while (( SECONDS < transition_deadline )) && pid_running "$launch_pid"; do sleep 1; done
      if pid_running "$launch_pid"; then kill -KILL "$launch_pid" 2>/dev/null || true; fi
      transition_deadline=$((SECONDS + KILL_GRACE_S))
      while (( SECONDS < transition_deadline )) && pid_running "$launch_pid"; do sleep 1; done
      if pid_running "$launch_pid"; then OUTER_SURVIVOR=1; else wait "$launch_pid" 2>/dev/null || true; fi
    fi
    die "child $gpu did not enter its isolated session"
  fi
  CHILD_PIDS[$gpu]="$launch_pid"
  CHILD_START_TICKS[$gpu]="$launch_ticks"
  CHILD_PGIDS[$gpu]="$launch_pgid"
  CHILD_SIDS[$gpu]="$launch_sid"
  [[ "${CHILD_PGIDS[$gpu]}" == "${CHILD_PIDS[$gpu]}" ]] || die "child $gpu is not its process-group leader"
  [[ "${CHILD_SIDS[$gpu]}" == "${CHILD_PGIDS[$gpu]}" ]] || die "child $gpu is not its session leader"
  atomic_json "$session_gate" -n --argjson pid "$launch_pid" --arg ticks "$launch_ticks" \
    --argjson pgid "$launch_pgid" --argjson sid "$launch_sid" \
    '{passed:true,pid:$pid,start_ticks:$ticks,pgid:$pgid,sid:$sid}'
  printf 'gpu=%s\tselector=%s\tport=%s\tpid=%s\tstart_ticks=%s\tpgid=%s\tsid=%s\n' "$gpu" "$selector" "$port" "${CHILD_PIDS[$gpu]}" "${CHILD_START_TICKS[$gpu]}" "${CHILD_PGIDS[$gpu]}" "${CHILD_SIDS[$gpu]}" >> "$WAVE_DIR/wave-launches.tsv"
  if (( gpu != 3 )); then
    sleep "$START_STAGGER_S"
    [[ ! -e "$WAVE_ABORT_FILE" ]] || die "a lane aborted during stagger"
  fi
done

deadline=$((SECONDS + READINESS_TIMEOUT_S))
while :; do
  [[ ! -e "$WAVE_ABORT_FILE" ]] || die "a lane aborted before the barrier"
  all_ready=1
  for gpu in 0 1 2 3; do
    [[ -s "${CHILD_DIRS[$gpu]}/ready.json" ]] || all_ready=0
    owned_child_group "$gpu" || { [[ -s "${CHILD_DIRS[$gpu]}/ready.json" ]] || die "child $gpu exited before readiness"; }
  done
  (( all_ready == 1 )) && break
  (( SECONDS < deadline )) || die "four-card readiness timeout"
  sleep 2
done
for gpu in 0 1 2 3; do
  owned_child_group "$gpu" || die "child $gpu not live at release"
  jq -e --argjson gpu "$gpu" --argjson selector "${SELECTORS[$gpu]}" --argjson port "$((PORT_BASE + gpu))" '.ready==true and .gpu_index==$gpu and .selector==$selector and .port==$port and (.server_pid|type)=="number" and (.server_attestation_sha256|test("^[0-9a-f]{64}$")) and (.prerelease_prefix_sha256|test("^[0-9a-f]{64}$"))' "${CHILD_DIRS[$gpu]}/ready.json" >/dev/null || die "invalid lane readiness marker"
done
available_loaded_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
printf 'available_kib=%s\nminimum_kib=33554432\n' "$available_loaded_kib" > "$WAVE_DIR/host-memory-all-loaded.env"
(( available_loaded_kib >= 33554432 )) || die "host memory below 32 GiB with all four servers loaded"
sha256sum -c "$WAVE_INPUT_MANIFEST" > "$WAVE_DIR/wave-inputs-prerelease.check.txt"
atomic_json "$WAVE_RELEASE_FILE" -n --arg released_utc "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '{released:true,phase:"canonical-q8-c1-oracle",released_utc:$released_utc}'

deadline=$((SECONDS + WAVE_TIMEOUT_S))
while :; do
  [[ ! -e "$WAVE_ABORT_FILE" ]] || die "a lane aborted after release"
  any=0
  for gpu in 0 1 2 3; do
    if recorded_session_alive "$gpu"; then
      any=1
    elif [[ ! -s "${CHILD_DIRS[$gpu]}/artifacts.sha256" ]]; then
      die "child $gpu vanished without a preliminary seal"
    fi
  done
  (( any == 0 )) && break
  (( SECONDS < deadline )) || die "four-card wave timeout"
  sleep 2
done
capture_recorded_group_members "$WAVE_DIR/postwave-group-members-before-reap.txt"
[[ ! -s "$WAVE_DIR/postwave-group-members-before-reap.txt" ]] || die "recorded session retained live members"
for gpu in 0 1 2 3; do
  if ! wait "${CHILD_PIDS[$gpu]}"; then die "child $gpu failed"; fi
  [[ -s "${CHILD_DIRS[$gpu]}/artifacts.sha256" ]] || die "child $gpu did not seal preliminary evidence"
  (cd "${CHILD_DIRS[$gpu]}" && sha256sum -c artifacts.sha256 >/dev/null) || die "child $gpu preliminary seal invalid"
  [[ ! -e "${CHILD_DIRS[$gpu]}/diagnostic-completion-status.json" ]] || die "lane marker appeared before global health verdict"
done

phase_passive_scan preprobe || die "phase-global passive fault evidence detected"

sleep 3
all_cards_idle=1
: > "$WAVE_DIR/xpu-final-used.tsv"
for gpu in 0 1 2 3; do
  if ! sample_gpu "$gpu" "$WAVE_DIR/xpu-smi-final-gpu${gpu}.txt"; then
    all_cards_idle=0
    for ((remaining=gpu+1; remaining<4; remaining++)); do
      printf 'skipped: prior final XPU probe failed\n' > "$WAVE_DIR/xpu-smi-final-gpu${remaining}.skipped.txt"
    done
    break
  fi
  if ! used="$(parse_gpu_used_mib "$WAVE_DIR/xpu-smi-final-gpu${gpu}.txt" "$gpu")"; then
    all_cards_idle=0
    for ((remaining=gpu+1; remaining<4; remaining++)); do
      printf 'skipped: prior final XPU parse failed\n' > "$WAVE_DIR/xpu-smi-final-gpu${remaining}.skipped.txt"
    done
    break
  fi
  printf 'gpu=%s\tused_mib=%s\n' "$gpu" "$used" >> "$WAVE_DIR/xpu-final-used.tsv"
  if (( used > GPU_IDLE_MAX_MIB )); then
    all_cards_idle=0
    for ((remaining=gpu+1; remaining<4; remaining++)); do
      printf 'skipped: prior final XPU use exceeded idle threshold\n' > "$WAVE_DIR/xpu-smi-final-gpu${remaining}.skipped.txt"
    done
    break
  fi
done
postprobe_clean=1
phase_passive_scan postprobe || postprobe_clean=0
(( all_cards_idle == 1 )) || die "one or more cards did not return to idle"
(( postprobe_clean == 1 )) || die "post-XPU passive fault evidence detected"
printf 'status=PASS\nall_groups_stopped=1\nall_listeners_closed=1\npassive_fault_detected=0\nfinal_xpu_probes_performed=1\nall_cards_idle=1\nforced_kill=0\ncleanup_survivor=0\n' > "$WAVE_DIR/global-cleanup-status.env"
(
  cd "$WAVE_DIR"
  find . -maxdepth 1 -type f \( -name 'preprobe-*' -o -name 'postprobe-*' \
    -o -name 'postwave-group-members-before-reap.txt' -o -name 'xpu-smi-final-gpu*.txt' \
    -o -name 'xpu-final-used.tsv' -o -name 'global-cleanup-status.env' \) \
    -print0 | sort -z | xargs -0 sha256sum > global-health-evidence.sha256
  sha256sum -c global-health-evidence.sha256 >/dev/null
)
global_evidence_sha="$(file_sha256 "$WAVE_DIR/global-health-evidence.sha256")"
atomic_json "$WAVE_DIR/global-health.json" -n \
  --arg evidence_path "$WAVE_DIR/global-health-evidence.sha256" --arg evidence_sha "$global_evidence_sha" \
  '{schema_version:1,phase:"four-gpu-sequential-c1-oracle-on-c2-topology",passed:true,all_groups_stopped:true,all_listeners_closed:true,passive_fault_detected:false,final_xpu_probes_performed:true,all_cards_idle:true,forced_kill:false,cleanup_survivor:false,evidence_manifest_path:$evidence_path,evidence_manifest_sha256:$evidence_sha}'
global_health_sha="$(file_sha256 "$WAVE_DIR/global-health.json")"
global_cleanup_sha="$(file_sha256 "$WAVE_DIR/global-cleanup-status.env")"

for gpu in 0 1 2 3; do
  lane_dir="${CHILD_DIRS[$gpu]}"; selector="${SELECTORS[$gpu]}"
  cmp -s <(printf 'status=PASS\ngpu_index=%s\nselector=%s\ngraceful_server_teardown=1\nforced_kill=0\ncleanup_survivor=0\nport_closed=1\n' "$gpu" "$selector") \
    "$lane_dir/cleanup-status.env" || die "lane $gpu cleanup status is not exact"
  manifest_sha="$(file_sha256 "$lane_dir/artifacts.sha256")"
  oracle_sha="$(file_sha256 "$lane_dir/oracle.json")"
  attestation_sha="$(file_sha256 "$lane_dir/lane-attestation.json")"
  cleanup_sha="$(file_sha256 "$lane_dir/cleanup-status.env")"
  server_pid="$(<"$lane_dir/server.pid")"
  atomic_json "$lane_dir/diagnostic-completion-status.json" -n \
    --argjson gpu "$gpu" --argjson selector "$selector" --arg server_pid "$server_pid" \
    --arg manifest_sha "$manifest_sha" --arg oracle_sha "$oracle_sha" --arg attestation_sha "$attestation_sha" \
    --arg cleanup_sha "$cleanup_sha" --arg health_path "$WAVE_DIR/global-health.json" --arg health_sha "$global_health_sha" \
    --arg global_cleanup_path "$WAVE_DIR/global-cleanup-status.env" --arg global_cleanup_sha "$global_cleanup_sha" \
    '{schema_version:1,phase:"four-gpu-sequential-c1-oracle-on-c2-topology",status:"EVIDENCE_VALID",evidence_valid:true,evidence_class:"diagnostic-only",performance_promotable:false,gpu_index:$gpu,selector:$selector,server_pid:$server_pid,artifact_manifest:"artifacts.sha256",artifact_manifest_sha256:$manifest_sha,oracle:"oracle.json",oracle_sha256:$oracle_sha,attestation:"lane-attestation.json",attestation_sha256:$attestation_sha,cleanup_status_sha256:$cleanup_sha,lifecycle:{graceful_server_teardown:true,forced_kill:false,cleanup_survivor:false,port_closed:true,global_passive_health_passed:true,global_health_path:$health_path,global_health_sha256:$health_sha,global_cleanup_path:$global_cleanup_path,global_cleanup_sha256:$global_cleanup_sha}}'
done

python3 "$ANALYZER" aggregate \
  --lane "${CHILD_DIRS[0]}" --lane "${CHILD_DIRS[1]}" --lane "${CHILD_DIRS[2]}" --lane "${CHILD_DIRS[3]}" \
  --old-baseline-oracle "$OLD_ORACLE" --old-baseline-oracle-sha256 "$EXPECTED_OLD_ORACLE_SHA256" \
  --official-c1-dir "$OFFICIAL_C1_DIR" --official-c1-result-sha256 "$EXPECTED_OFFICIAL_C1_RESULT_SHA256" \
  --official-c1-manifest-sha256 "$EXPECTED_OFFICIAL_C1_MANIFEST_SHA256" \
  --official-c1-marker-sha256 "$EXPECTED_OFFICIAL_C1_MARKER_SHA256" \
  --model-sha256 "$EXPECTED_MODEL_SHA256" --runtime-sha256 "$EXPECTED_RUNTIME_SHA256" \
  --suite-sha256 "$EXPECTED_SUITE_SHA256" --selector0-oracle "$WAVE_DIR/selector0-oracle.json" \
  --selector1-oracle "$WAVE_DIR/selector1-oracle.json" --out "$WAVE_DIR/phase-summary.json"
jq -e '.passed==true and .evidence_class=="diagnostic-only" and .performance_promotable==false' "$WAVE_DIR/phase-summary.json" >/dev/null || die "phase aggregate failed"

capture_model_stat "/proc/$$/fd/$MODEL_FD" "$WAVE_DIR/model-stat-final.json"
cmp -s "$WAVE_DIR/model-stat-baseline.json" "$WAVE_DIR/model-stat-final.json" || die "outer model stat drift"
printf '%s  %s\n' "$EXPECTED_MODEL_SHA256" "/proc/$$/fd/$MODEL_FD" | sha256sum -c - > "$WAVE_DIR/model-sha256-final.check.txt"
runtime_report "$WAVE_DIR/runtime-final.json" "$WAVE_DIR/runtime-initial.json"
sha256sum -c "$WAVE_INPUT_MANIFEST" > "$WAVE_DIR/wave-inputs-final.check.txt"
printf 'PRE_SEAL_EVIDENCE_VALID\n' > "$WAVE_DIR/wave-status.txt"
printf 'status=PASS\nforced_kill=0\ncleanup_survivor=0\nbody_complete=1\n' > "$WAVE_DIR/wave-cleanup-status.env"
seal_directory "$WAVE_DIR" wave-artifacts.sha256 wave-diagnostic-completion-status.json || die "outer seal failed"
wave_manifest_sha="$(file_sha256 "$WAVE_DIR/wave-artifacts.sha256")"
summary_sha="$(file_sha256 "$WAVE_DIR/phase-summary.json")"
atomic_json "$WAVE_DIR/wave-diagnostic-completion-status.json" -n --arg manifest_sha "$wave_manifest_sha" --arg summary_sha "$summary_sha" \
  '{schema_version:1,phase:"four-gpu-sequential-c1-oracle-on-c2-topology",status:"EVIDENCE_VALID",evidence_valid:true,evidence_class:"diagnostic-only",performance_promotable:false,artifact_manifest:"wave-artifacts.sha256",artifact_manifest_sha256:$manifest_sha,summary:"phase-summary.json",summary_sha256:$summary_sha}'
OUTER_COMPLETE=1
trap - EXIT INT TERM
printf '%s\n' "$WAVE_DIR"
