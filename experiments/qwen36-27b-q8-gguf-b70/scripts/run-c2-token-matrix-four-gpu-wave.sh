#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LANE="$ROOT/experiments/qwen36-27b-q8-gguf-b70"
SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
LAUNCHER="$LANE/scripts/serve-target-only.sh"
ATTESTER="$LANE/scripts/attest-c2-server.py"
MATRIX_CLIENT="$LANE/scripts/capture-c2-token-matrix.py"
FORMAL_CAPTURE="$LANE/scripts/capture-simultaneous-c2.py"
COMMON_CAPTURE="$LANE/scripts/capture-exact-tokens.py"
SUITE="$LANE/c2-long-context-suite-v1.json"
PROMPT_BUILDER="$ROOT/scripts/bench-openai-long-context-suite.py"
MODEL_MANIFEST="$LANE/model-manifest.json"
RUNTIME_MANIFEST="$LANE/runtime-manifest.json"

MODEL="/mnt/usb-models/models/qwen36-27b-q8-gguf/Qwen3.6-27B-Q8_0.gguf"
LLAMA_SERVER="/dev/shm/llama.cpp-pr19-15586/build-sycl/bin/llama-server"
MODEL_ALIAS="qwen36-27b-q8_0-target-only"
EXPECTED_MODEL_SHA256="f93f517f38e696d35a1a7df2c0e3155a64f4c4dcd662107a146ae263f7fb14ce"
EXPECTED_MODEL_SIZE=28595763424
EXPECTED_RUNTIME_SHA256="1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7"
ORACLE_SOURCE="/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal1-formal-c2-gpu0-short-diag-20260809T171516.435188879Z/sequential-oracle/oracle.json"
ORACLE_SHA256="7a884c14ecd1705981aea63c22e8fd96b9b6646aeca98a53850d5cc54836e534"
HIST_FORWARD="/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal1-formal-c2-gpu0-short-diag-20260809T171516.435188879Z/concurrent/result.json"
HIST_FORWARD_SHA256="39416de77fb20d88523dc83c15f629dec7d7a9e341e98d8104368dcd02778763"
HIST_REVERSE="/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal1-formal-c2-gpu0-short-reverse-20260809T173515.954289991Z/concurrent/result.json"
HIST_REVERSE_SHA256="55fd86dc97087689d24dcf0e546296a01bfe82f4748b0e1a1b71ebdc80645618"

PORT_BASE="${PORT_BASE:-19520}"
START_STAGGER_S="${START_STAGGER_S:-5}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-1200}"
WAVE_TIMEOUT_S="${WAVE_TIMEOUT_S:-3600}"
TERM_GRACE_S="${TERM_GRACE_S:-45}"
KILL_GRACE_S="${KILL_GRACE_S:-10}"
REQUEST_TIMEOUT_S="${REQUEST_TIMEOUT_S:-1800}"
MIN_HOST_AVAILABLE_KIB="${MIN_HOST_AVAILABLE_KIB:-100663296}"
MIN_FAST_FREE_KIB="${MIN_FAST_FREE_KIB:-10485760}"
GPU_IDLE_MAX_MIB=256
MIN_LOADED_DELTA_MIB=25000
MIN_FIT_FREE_MIB=1024
STAMP="$(date -u +%Y%m%dT%H%M%S.%NZ)"
WAVE_DIR="${WAVE_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal1-c2-token-matrix-four-gpu-${STAMP}}"

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
  local path="$1"
  awk -F '|' '
    /GPU Memory Used/ {
      value=$3
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      if (value ~ /^[0-9]+([.][0-9]+)?$/) { print int(value); found=1 }
      exit
    }
    END { if (!found) exit 1 }
  ' "$path"
}

file_sha256() {
  local path="$1"
  local value
  [[ -f "$path" ]] || return 1
  value="$(sha256sum "$path" | awk '{print $1}')" || return 1
  [[ "$value" =~ ^[0-9a-f]{64}$ ]] || return 1
  printf '%s\n' "$value"
}

sample_gpu() {
  local gpu="$1"
  local out="$2"
  timeout 20 xpu-smi stats -d "$gpu" > "$out" 2>&1
}

pid_running() {
  local pid="$1"
  local state
  kill -0 "$pid" 2>/dev/null || return 1
  state="$(ps -o stat= -p "$pid" 2>/dev/null | awk '{print $1}')"
  [[ -n "$state" && "$state" != Z* ]]
}

capture_model_stat() {
  local fd_path="$1"
  local out="$2"
  python3 - "$fd_path" "$out" <<'PY'
import json
import os
import sys

fd_path, out_path = sys.argv[1:]
value = os.stat(fd_path, follow_symlinks=True)
payload = {
    "device": value.st_dev,
    "inode": value.st_ino,
    "size_bytes": value.st_size,
    "mtime_ns": value.st_mtime_ns,
    "ctime_ns": value.st_ctime_ns,
}
with open(out_path, "w") as stream:
    json.dump(payload, stream, indent=2, sort_keys=True)
    stream.write("\n")
PY
}

seal_directory() {
  local directory="$1"
  local manifest_name="$2"
  local marker_name="$3"
  local temp
  temp="$(mktemp "${directory}/.${manifest_name}.XXXXXX")" || return 1
  if ! (
    cd "$directory"
    find . -type f \
      ! -name "$manifest_name" \
      ! -name "$marker_name" \
      ! -name ".${manifest_name}.*" \
      -print0 |
      sort -z |
      xargs -0 -r sha256sum > "$temp"
  ); then
    rm -f "$temp"
    return 1
  fi
  [[ -s "$temp" ]] || { rm -f "$temp"; return 1; }
  if ! (cd "$directory" && sha256sum -c "$temp" >/dev/null); then
    rm -f "$temp"
    return 1
  fi
  mv "$temp" "$directory/$manifest_name" || return 1
  (cd "$directory" && sha256sum -c "$manifest_name" >/dev/null)
}

validate_lease_fd() {
  local fd="$1"
  local expected_path="$2"
  [[ "$fd" =~ ^[0-9]+$ ]] || return 1
  [[ "$(readlink -f "/proc/$$/fd/$fd" 2>/dev/null || true)" == "$(readlink -f "$expected_path")" ]] || return 1
  flock -n "$fd"
}

child_main() {
  : "${GPU_INDEX:?}" "${PORT:?}" "${SCENARIO:?}" "${RUN_DIR:?}" \
    "${MODEL_FD:?}" "${QWEN36_GPU_LEASE_FD:?}" "${QWEN36_PORT_LEASE_FD:?}" \
    "${WAVE_RELEASE_FILE:?}" "${WAVE_ABORT_FILE:?}" "${ORACLE_SNAPSHOT:?}" \
    "${RUNTIME_REFERENCE_REPORT:?}" "${MODEL_STAT_BASELINE:?}"
  [[ "$GPU_INDEX" =~ ^[0-3]$ ]] || die "child GPU_INDEX is invalid"
  case "$SCENARIO" in swap|duplicate-b) ;; *) die "child scenario is invalid" ;; esac
  require_uint PORT "$PORT"
  [[ ! -e "$RUN_DIR" ]] || die "child RUN_DIR already exists: $RUN_DIR"
  mkdir "$RUN_DIR"

  local gpu_lease_path="/run/user/$(id -u)/qwen36-b70-gpu-leases/gpu${GPU_INDEX}.lock"
  local port_lease_path="/run/user/$(id -u)/qwen36-b70-port-leases/port${PORT}.lock"
  validate_lease_fd "$QWEN36_GPU_LEASE_FD" "$gpu_lease_path" || die "child GPU lease is invalid"
  validate_lease_fd "$QWEN36_PORT_LEASE_FD" "$port_lease_path" || die "child port lease is invalid"
  [[ -r "/proc/$$/fd/$MODEL_FD" ]] || die "child model FD is unreadable"
  [[ "$(stat -Lc %s "/proc/$$/fd/$MODEL_FD")" == "$EXPECTED_MODEL_SIZE" ]] || die "child model FD size drifted"
  capture_model_stat "/proc/$$/fd/$MODEL_FD" "$RUN_DIR/model-stat-prelaunch.json"
  cmp -s "$MODEL_STAT_BASELINE" "$RUN_DIR/model-stat-prelaunch.json" || die "child model stat drifted"
  [[ "$(sha256sum "$ORACLE_SNAPSHOT" | awk '{print $1}')" == "$ORACLE_SHA256" ]] || die "child oracle snapshot drifted"

  local server_pid=""
  local server_expected=0
  local body_complete=0
  local result_valid=0
  local cleanup_forced=0
  local cleanup_survivor=0
  local active_probe_failed=0
  local pre_mib=""
  local start_epoch
  start_epoch="$(date +%s)"

  child_finish() {
    local original_status=$?
    local final_status="$original_status"
    local server_alive_before_stop=0
    local port_closed=0
    local vram_returned=0
    local final_mib=""
    local fault_detected="$active_probe_failed"
    local deadline
    trap - EXIT INT TERM
    set +e
    if (( server_expected == 1 )) && [[ -n "$server_pid" ]] && pid_running "$server_pid"; then
      server_alive_before_stop=1
    fi
    if [[ -n "$server_pid" ]] && pid_running "$server_pid"; then
      kill -TERM "$server_pid" 2>/dev/null
      deadline=$((SECONDS + TERM_GRACE_S))
      while (( SECONDS < deadline )) && pid_running "$server_pid"; do sleep 1; done
      if pid_running "$server_pid"; then
        cleanup_forced=1
        kill -KILL "$server_pid" 2>/dev/null
      fi
      deadline=$((SECONDS + KILL_GRACE_S))
      while (( SECONDS < deadline )) && pid_running "$server_pid"; do sleep 1; done
      if pid_running "$server_pid"; then
        cleanup_survivor=1
      else
        wait "$server_pid" 2>/dev/null
      fi
    fi
    if [[ -n "$server_pid" ]] && pid_running "$server_pid"; then cleanup_survivor=1; fi
    if (( cleanup_forced == 1 || cleanup_survivor == 1 )); then fault_detected=1; fi
    if ! ss -H -ltn "sport = :$PORT" | grep -q .; then port_closed=1; fi
    capture_model_stat "/proc/$$/fd/$MODEL_FD" "$RUN_DIR/model-stat-final.json" 2>/dev/null
    cmp -s "$MODEL_STAT_BASELINE" "$RUN_DIR/model-stat-final.json" || final_status=1
    [[ "$MODEL" -ef "/proc/$$/fd/$MODEL_FD" ]] || final_status=1
    if grep -EHi 'UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST|out of memory|segmentation fault|core dumped|Aborted|Timedout job' \
      "$RUN_DIR/server.stdout.log" "$RUN_DIR/server.identity.log" \
      > "$RUN_DIR/server-error-scan.txt" 2> "$RUN_DIR/server-error-scan.stderr"; then
      fault_detected=1
      final_status=1
    elif [[ $? -gt 1 ]]; then
      fault_detected=1
      final_status=1
    fi
    if journalctl -k --since "@$start_epoch" --no-pager \
      > "$RUN_DIR/kernel-journal.txt" 2> "$RUN_DIR/kernel-journal.stderr"; then
      if grep -Ei 'xe.*(reset|wedg|fault|hang|timedout|device lost)|GuC.*reset|Fault response|VM.*fault|PCIe.*AER|UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST' \
        "$RUN_DIR/kernel-journal.txt" > "$RUN_DIR/device-error-scan.txt"; then
        fault_detected=1
        final_status=1
      elif [[ $? -gt 1 ]]; then
        fault_detected=1
        final_status=1
      fi
    else
      fault_detected=1
      final_status=1
    fi
    if (( fault_detected == 0 )); then
      sleep 3
      if sample_gpu "$GPU_INDEX" "$RUN_DIR/xpu-smi-final.txt"; then
        final_mib="$(parse_gpu_used_mib "$RUN_DIR/xpu-smi-final.txt" 2>/dev/null || true)"
        if [[ -n "$pre_mib" && -n "$final_mib" ]] && (( final_mib <= pre_mib + GPU_IDLE_MAX_MIB )); then
          vram_returned=1
        else
          fault_detected=1
          final_status=1
        fi
      else
        fault_detected=1
        final_status=1
      fi
    else
      printf 'skipped: passive fault evidence made active XPU probing unsafe\n' \
        > "$RUN_DIR/xpu-smi-final.skipped.txt"
    fi
    (( body_complete == 1 && result_valid == 1 && server_alive_before_stop == 1 )) || final_status=1
    (( cleanup_forced == 0 && cleanup_survivor == 0 && port_closed == 1 && vram_returned == 1 )) || final_status=1
    {
      echo "original_status=$original_status"
      echo "final_status=$final_status"
      echo "body_complete=$body_complete"
      echo "result_valid=$result_valid"
      echo "server_alive_before_stop=$server_alive_before_stop"
      echo "forced_kill=$cleanup_forced"
      echo "cleanup_survivor=$cleanup_survivor"
      echo "port_closed=$port_closed"
      echo "vram_returned=$vram_returned"
      echo "passive_fault_detected=$fault_detected"
      echo "pre_mib=${pre_mib:-unknown}"
      echo "final_mib=${final_mib:-unknown}"
    } > "$RUN_DIR/cleanup-status.env"
    if (( final_status == 0 )); then
      printf 'PRE_SEAL_EVIDENCE_VALID\n' > "$RUN_DIR/run-status.txt"
    else
      printf 'FAIL\n' > "$RUN_DIR/run-status.txt"
    fi
    rm -f "$RUN_DIR/artifacts.sha256" "$RUN_DIR/diagnostic-completion-status.json"
    if ! seal_directory "$RUN_DIR" artifacts.sha256 diagnostic-completion-status.json; then
      final_status=1
    fi
    if (( final_status == 0 )); then
      local manifest_sha result_sha attestation_sha marker_tmp
      if ! manifest_sha="$(file_sha256 "$RUN_DIR/artifacts.sha256")" || \
         ! result_sha="$(file_sha256 "$RUN_DIR/token-matrix.json")" || \
         ! attestation_sha="$(file_sha256 "$RUN_DIR/server-attestation.json")"; then
        final_status=1
      fi
      if (( final_status == 0 )); then marker_tmp="$(mktemp "$RUN_DIR/.diagnostic-completion-status.XXXXXX")" || final_status=1; fi
      if (( final_status == 0 )); then jq -n \
        --arg status EVIDENCE_VALID \
        --arg scenario "$SCENARIO" \
        --argjson gpu_index "$GPU_INDEX" \
        --arg manifest_sha "$manifest_sha" \
        --arg result_sha "$result_sha" \
        --arg attestation_sha "$attestation_sha" \
        '{status:$status,evidence_valid:true,evidence_class:"diagnostic-only",performance_promotable:false,scenario:$scenario,gpu_index:$gpu_index,artifact_manifest:"artifacts.sha256",artifact_manifest_sha256:$manifest_sha,result:"token-matrix.json",result_sha256:$result_sha,server_attestation_sha256:$attestation_sha}' \
        > "$marker_tmp" || final_status=1; fi
      if (( final_status == 0 )); then
        jq -e --arg scenario "$SCENARIO" --argjson gpu "$GPU_INDEX" \
          --arg manifest_sha "$manifest_sha" --arg result_sha "$result_sha" \
          --arg attestation_sha "$attestation_sha" '
            .status=="EVIDENCE_VALID" and .evidence_valid==true
            and .evidence_class=="diagnostic-only" and .performance_promotable==false
            and .scenario==$scenario and .gpu_index==$gpu
            and .artifact_manifest_sha256==$manifest_sha
            and .result_sha256==$result_sha
            and .server_attestation_sha256==$attestation_sha
          ' "$marker_tmp" >/dev/null || final_status=1
      fi
      if (( final_status == 0 )); then mv "$marker_tmp" "$RUN_DIR/diagnostic-completion-status.json" || final_status=1; fi
      [[ -z "${marker_tmp:-}" ]] || rm -f "$marker_tmp"
    fi
    if (( final_status != 0 )); then
      rm -f "$RUN_DIR/diagnostic-completion-status.json"
      printf 'FAIL\n' > "$RUN_DIR/run-status.txt"
      seal_directory "$RUN_DIR" artifacts.sha256 diagnostic-completion-status.json || true
    fi
    exit "$final_status"
  }
  trap child_finish EXIT
  trap 'exit 130' INT TERM

  if ss -H -ltn "sport = :$PORT" | grep -q .; then die "child port is already in use"; fi
  if ! sample_gpu "$GPU_INDEX" "$RUN_DIR/xpu-smi-before.txt"; then
    active_probe_failed=1
    die "child preflight GPU sample failed"
  fi
  if ! pre_mib="$(parse_gpu_used_mib "$RUN_DIR/xpu-smi-before.txt")"; then
    active_probe_failed=1
    die "child preflight GPU sample was not parseable"
  fi
  (( pre_mib <= GPU_IDLE_MAX_MIB )) || die "child GPU is not idle: $pre_mib MiB"

  LLAMA_SERVER="$LLAMA_SERVER" RUNTIME_MANIFEST="$RUNTIME_MANIFEST" \
    "$LAUNCHER" --verify-runtime-bundle \
      "$RUN_DIR/runtime-ldd-prelaunch.txt" \
      "$RUN_DIR/runtime-resolved-prelaunch.sha256" \
      "$RUN_DIR/runtime-bundle-prelaunch.json" \
      "$RUNTIME_REFERENCE_REPORT"

  QWEN36_MODEL_FD="$MODEL_FD" \
  GPU_INDEX="$GPU_INDEX" PORT="$PORT" MODEL="$MODEL" MODEL_ALIAS="$MODEL_ALIAS" \
  LLAMA_SERVER="$LLAMA_SERVER" RUNTIME_MANIFEST="$RUNTIME_MANIFEST" \
  CTX_SIZE=65536 PARALLEL_SLOTS=2 KV_UNIFIED=0 CONT_BATCHING=1 \
  BATCH_SIZE=1024 UBATCH_SIZE=128 N_GPU_LAYERS=99 THREADS=8 HTTP_THREADS=6 \
  POLL=50 LOG_VERBOSITY=4 CACHE_TYPE_K=f16 CACHE_TYPE_V=f16 FLASH_ATTN=on \
  LANE_DNN_ENABLED=0 LANE_OPT_ENABLED=1 LANE_FA_ONEDNN=1 \
  LANE_FA_ONEDNN_MAX_KV=0 LANE_MKL_FA=1 LANE_SYCL_FLASH_ATTN=1 \
  LOG="$RUN_DIR/server.identity.log" SERVER_OUTPUT_LOG="$RUN_DIR/server.stdout.log" OUT_DIR="$RUN_DIR" \
    "$LAUNCHER" > "$RUN_DIR/launcher.stdout.log" 2> "$RUN_DIR/launcher.stderr.log" &
  server_pid=$!
  printf '%s\n' "$server_pid" > "$RUN_DIR/server.pid"

  local deadline=$((SECONDS + READINESS_TIMEOUT_S))
  until curl -fsS "http://127.0.0.1:${PORT}/v1/models" > "$RUN_DIR/models.json" 2> "$RUN_DIR/models.err"; do
    pid_running "$server_pid" || die "child server exited before readiness"
    (( SECONDS < deadline )) || die "child server readiness timeout"
    sleep 2
  done
  server_expected=1
  jq -e --arg alias "$MODEL_ALIAS" '
    (.data|length)==1 and .data[0].id==$alias and .data[0].meta.n_ctx==32768
    and .data[0].meta.ftype=="Q8_0" and .data[0].meta.n_params==26895998464
  ' "$RUN_DIR/models.json" >/dev/null || die "child model endpoint identity failed"

  python3 "$ATTESTER" \
    --server-log "$RUN_DIR/server.stdout.log" \
    --identity-log "$RUN_DIR/server.identity.log" \
    --out "$RUN_DIR/server-attestation.json" \
    --model-size "$EXPECTED_MODEL_SIZE" \
    --runtime-sha256 "$EXPECTED_RUNTIME_SHA256" \
    --minimum-fit-free-mib "$MIN_FIT_FREE_MIB"
  local attestation_sha
  attestation_sha="$(file_sha256 "$RUN_DIR/server-attestation.json")"
  if ! sample_gpu "$GPU_INDEX" "$RUN_DIR/xpu-smi-loaded.txt"; then
    active_probe_failed=1
    die "child loaded GPU sample failed"
  fi
  local loaded_mib
  if ! loaded_mib="$(parse_gpu_used_mib "$RUN_DIR/xpu-smi-loaded.txt")"; then
    active_probe_failed=1
    die "child loaded GPU sample was not parseable"
  fi
  (( loaded_mib - pre_mib >= MIN_LOADED_DELTA_MIB )) || die "child loaded VRAM delta is too small"
  capture_model_stat "/proc/$$/fd/$MODEL_FD" "$RUN_DIR/model-stat-loaded.json"
  cmp -s "$MODEL_STAT_BASELINE" "$RUN_DIR/model-stat-loaded.json" || die "child model stat changed during load"
  pid_running "$server_pid" || die "child server died after attestation"

  local ready_tmp
  ready_tmp="$(mktemp "$RUN_DIR/.ready.XXXXXX")"
  jq -n --arg scenario "$SCENARIO" --arg attestation_sha "$attestation_sha" \
    --argjson gpu_index "$GPU_INDEX" --argjson port "$PORT" --argjson server_pid "$server_pid" \
    --argjson pre_mib "$pre_mib" --argjson loaded_mib "$loaded_mib" \
    '{ready:true,scenario:$scenario,gpu_index:$gpu_index,port:$port,server_pid:$server_pid,pre_mib:$pre_mib,loaded_mib:$loaded_mib,server_attestation_sha256:$attestation_sha}' \
    > "$ready_tmp"
  mv "$ready_tmp" "$RUN_DIR/ready.json"

  deadline=$((SECONDS + READINESS_TIMEOUT_S))
  while [[ ! -f "$WAVE_RELEASE_FILE" ]]; do
    [[ ! -f "$WAVE_ABORT_FILE" ]] || die "wave aborted before release"
    pid_running "$server_pid" || die "child server died before release"
    (( SECONDS < deadline )) || die "child release timeout"
    sleep 1
  done

  timeout --signal=TERM --kill-after=30 "$REQUEST_TIMEOUT_S" \
    python3 "$MATRIX_CLIENT" \
      --scenario "$SCENARIO" \
      --base-url "http://127.0.0.1:${PORT}" \
      --suite "$SUITE" \
      --prompt-builder "$PROMPT_BUILDER" \
      --common-script "$COMMON_CAPTURE" \
      --capture-script "$FORMAL_CAPTURE" \
      --server-attestation "$RUN_DIR/server-attestation.json" \
      --server-attestation-sha256 "$attestation_sha" \
      --oracle-json "$ORACLE_SNAPSHOT" \
      --oracle-sha256 "$ORACLE_SHA256" \
      --model-sha256 "$EXPECTED_MODEL_SHA256" \
      --runtime-sha256 "$EXPECTED_RUNTIME_SHA256" \
      --server-pid "$server_pid" \
      --out "$RUN_DIR/token-matrix.json" \
      --timeout "$REQUEST_TIMEOUT_S" \
      > "$RUN_DIR/client.stdout.log" 2> "$RUN_DIR/client.stderr.log"
  jq -e --arg scenario "$SCENARIO" --arg base_url "http://127.0.0.1:${PORT}" \
    --arg model_sha "$EXPECTED_MODEL_SHA256" --arg runtime_sha "$EXPECTED_RUNTIME_SHA256" \
    --arg oracle_sha "$ORACLE_SHA256" --arg attestation_sha "$attestation_sha" '
    .evidence_valid==true
    and .diagnostic_identity.diagnostic_only==true
    and .diagnostic_identity.performance_claim_eligible==false
    and .diagnostic_identity.scenario==$scenario
    and .diagnostic_identity.base_url==$base_url
    and .diagnostic_identity.model_sha256==$model_sha
    and .diagnostic_identity.runtime_sha256==$runtime_sha
    and .diagnostic_identity.oracle_sha256==$oracle_sha
    and .diagnostic_identity.server_attestation_sha256==$attestation_sha
    and .identity_gate.passed==true
    and .live_server_binding.passed==true
    and .attestation_process_binding.passed==true
    and .input_integrity.passed==true
    and .scenario.scenario==$scenario and .scenario.evidence_valid==true
    and (.scenario.rows|length)==2
    and ([.scenario.rows[].slot_id]|sort)==[0,1]
    and (all(.scenario.rows[]; (.token_ids|length)==128 and .evidence_valid==true))
    and (
      if $scenario=="duplicate-b" then
        [.scenario.rows[].case_id]==["q27-q8-c2-04k-b","q27-q8-c2-04k-b"]
      else
        [.scenario.rows[].case_id]==["q27-q8-c2-04k-b","q27-q8-lc-04k-middle"]
      end
    )
    and (.classification=="VALID_EXACT_TO_C1" or .classification=="VALID_DIVERGENCE_FROM_C1")
  ' "$RUN_DIR/token-matrix.json" >/dev/null || die "child matrix evidence is invalid"
  result_valid=1
  body_complete=1
  # Run normal teardown while child_main's local lifecycle state is still in
  # scope.  Relying on the outer `exit 0` would fire the EXIT trap only after
  # these locals had been destroyed under `set -u`.
  child_finish
}

if [[ "${1:-}" == "--child" ]]; then
  shift
  [[ $# -eq 0 ]] || die "--child takes no positional arguments"
  child_main
  exit 0
fi

[[ $# -eq 0 ]] || die "unexpected positional arguments"

for command_name in awk bash chmod cmp cp curl date df dirname env find flock grep id \
  journalctl jq mkdir mktemp pgrep ps python3 readlink setsid sha256sum sort ss stat \
  timeout uname xargs xpu-smi; do
  command -v "$command_name" >/dev/null 2>&1 || die "required command not found: $command_name"
done
for path in "$SCRIPT" "$LAUNCHER" "$ATTESTER" "$MATRIX_CLIENT" "$FORMAL_CAPTURE" \
  "$COMMON_CAPTURE" "$SUITE" "$PROMPT_BUILDER" "$MODEL_MANIFEST" "$RUNTIME_MANIFEST" \
  "$MODEL" "$LLAMA_SERVER" "$ORACLE_SOURCE" "$HIST_FORWARD" "$HIST_REVERSE"; do
  [[ -f "$path" ]] || die "required file not found: $path"
done
[[ -x "$LLAMA_SERVER" ]] || die "llama-server is not executable"
[[ -f /opt/intel/oneapi/setvars.sh ]] || die "oneAPI setvars is missing"
[[ "$(stat -c %s "$MODEL")" == "$EXPECTED_MODEL_SIZE" ]] || die "model size mismatch"
[[ "$(jq -er .sha256 "$MODEL_MANIFEST")" == "$EXPECTED_MODEL_SHA256" ]] || die "model manifest SHA mismatch"
[[ "$(jq -er .llama_server_sha256 "$RUNTIME_MANIFEST")" == "$EXPECTED_RUNTIME_SHA256" ]] || die "runtime manifest SHA mismatch"
[[ "$(sha256sum "$LLAMA_SERVER" | awk '{print $1}')" == "$EXPECTED_RUNTIME_SHA256" ]] || die "runtime binary SHA mismatch"
[[ "$(sha256sum "$ORACLE_SOURCE" | awk '{print $1}')" == "$ORACLE_SHA256" ]] || die "sequential oracle SHA mismatch"
[[ "$(sha256sum "$HIST_FORWARD" | awk '{print $1}')" == "$HIST_FORWARD_SHA256" ]] || die "historical forward result SHA mismatch"
[[ "$(sha256sum "$HIST_REVERSE" | awk '{print $1}')" == "$HIST_REVERSE_SHA256" ]] || die "historical reverse result SHA mismatch"

for value_name in PORT_BASE START_STAGGER_S READINESS_TIMEOUT_S WAVE_TIMEOUT_S TERM_GRACE_S KILL_GRACE_S REQUEST_TIMEOUT_S MIN_HOST_AVAILABLE_KIB MIN_FAST_FREE_KIB; do
  require_uint "$value_name" "${!value_name}"
done
(( PORT_BASE >= 1024 && PORT_BASE <= 65532 )) || die "PORT_BASE must leave four usable ports"
(( READINESS_TIMEOUT_S > 0 && WAVE_TIMEOUT_S > 0 && TERM_GRACE_S > 0 && KILL_GRACE_S > 0 && REQUEST_TIMEOUT_S > 0 )) || die "timeouts must be positive"
[[ "$WAVE_DIR" == /* && "$WAVE_DIR" != "/" && ! -e "$WAVE_DIR" ]] || die "WAVE_DIR must be a new non-root absolute path"

unexpected_env=()
while IFS='=' read -r name _; do
  case "$name" in
    GGML_*|SYCL_*|ZE_*|ZES_*|UR_*|ONEAPI_DEVICE_SELECTOR|LD_PRELOAD) unexpected_env+=("$name") ;;
    LLAMA_*) unexpected_env+=("$name") ;;
  esac
done < <(env)
(( ${#unexpected_env[@]} == 0 )) || die "unexpected inherited accelerator environment: ${unexpected_env[*]}"

mkdir -p "$(dirname "$WAVE_DIR")"
mkdir "$WAVE_DIR"
START_EPOCH="$(date +%s)"
OUTER_BODY_COMPLETE=0
OUTER_FORCED_KILL=0
OUTER_CLEANUP_SURVIVOR=0
MODEL_READY=0
RUNTIME_READY=0
INPUTS_READY=0
declare -a CHILD_PIDS=()
declare -a CHILD_DIRS=()
declare -a GPU_LEASE_FDS=()
declare -a PORT_LEASE_FDS=()

group_alive() {
  local pgid="$1"
  ps -eo pgid=,stat= | awk -v target="$pgid" '$1==target && $2 !~ /^Z/ {found=1} END{exit(found?0:1)}'
}

leader_running() {
  pid_running "$1"
}

verify_wave_inputs() {
  local label="$1"
  (( INPUTS_READY == 1 )) || return 1
  sha256sum -c "$WAVE_DIR/wave-inputs.sha256" \
    > "$WAVE_DIR/wave-inputs-${label}.check.txt" 2>&1
}

verify_child_packet() {
  local gpu="$1"
  local directory="${CHILD_DIRS[$gpu]}"
  local expected_scenario="${scenarios[$gpu]}"
  local marker="$directory/diagnostic-completion-status.json"
  local actual_manifest_sha actual_result_sha actual_attestation_sha
  [[ -s "$marker" && -s "$directory/artifacts.sha256" ]] || return 1
  (cd "$directory" && sha256sum -c artifacts.sha256 >/dev/null) || return 1
  actual_manifest_sha="$(file_sha256 "$directory/artifacts.sha256")" || return 1
  actual_result_sha="$(file_sha256 "$directory/token-matrix.json")" || return 1
  actual_attestation_sha="$(file_sha256 "$directory/server-attestation.json")" || return 1
  jq -e --arg scenario "$expected_scenario" --argjson gpu "$gpu" \
    --arg manifest_sha "$actual_manifest_sha" --arg result_sha "$actual_result_sha" \
    --arg attestation_sha "$actual_attestation_sha" '
      .status=="EVIDENCE_VALID" and .evidence_valid==true
      and .evidence_class=="diagnostic-only" and .performance_promotable==false
      and .scenario==$scenario and .gpu_index==$gpu
      and .artifact_manifest=="artifacts.sha256"
      and .artifact_manifest_sha256==$manifest_sha
      and .result=="token-matrix.json" and .result_sha256==$result_sha
      and .server_attestation_sha256==$attestation_sha
    ' "$marker" >/dev/null
}

terminate_groups() {
  local pid deadline alive
  : > "$WAVE_DIR/abort"
  for pid in "${CHILD_PIDS[@]:-}"; do
    [[ -n "$pid" ]] && group_alive "$pid" && kill -TERM -- "-$pid" 2>/dev/null || true
  done
  deadline=$((SECONDS + TERM_GRACE_S))
  while (( SECONDS < deadline )); do
    alive=0
    for pid in "${CHILD_PIDS[@]:-}"; do [[ -n "$pid" ]] && group_alive "$pid" && alive=1; done
    (( alive == 0 )) && break
    sleep 1
  done
  for pid in "${CHILD_PIDS[@]:-}"; do
    if [[ -n "$pid" ]] && group_alive "$pid"; then
      OUTER_FORCED_KILL=1
      kill -KILL -- "-$pid" 2>/dev/null || true
    fi
  done
  deadline=$((SECONDS + KILL_GRACE_S))
  while (( SECONDS < deadline )); do
    alive=0
    for pid in "${CHILD_PIDS[@]:-}"; do [[ -n "$pid" ]] && group_alive "$pid" && alive=1; done
    (( alive == 0 )) && break
    sleep 1
  done
  for pid in "${CHILD_PIDS[@]:-}"; do
    [[ -n "$pid" ]] && group_alive "$pid" && OUTER_CLEANUP_SURVIVOR=1
  done
  for pid in "${CHILD_PIDS[@]:-}"; do
    if [[ -n "$pid" ]] && ! group_alive "$pid"; then wait "$pid" 2>/dev/null || true; fi
  done
}

outer_finish() {
  local original_status=$?
  local final_status="$original_status"
  local gpu port used manifest_sha summary_sha marker_tmp
  local fault_detected=0
  trap - EXIT INT TERM
  set +e
  terminate_groups
  (( OUTER_FORCED_KILL == 0 && OUTER_CLEANUP_SURVIVOR == 0 )) || final_status=1
  if (( OUTER_FORCED_KILL == 1 || OUTER_CLEANUP_SURVIVOR == 1 )); then fault_detected=1; fi
  for gpu in 0 1 2 3; do
    if [[ -f "${CHILD_DIRS[$gpu]:-}/cleanup-status.env" ]] && \
       grep -Eq '^(passive_fault_detected|forced_kill|cleanup_survivor)=1$' \
         "${CHILD_DIRS[$gpu]}/cleanup-status.env"; then
      fault_detected=1
    fi
  done
  if journalctl -k --since "@$START_EPOCH" --no-pager > "$WAVE_DIR/kernel-journal.txt" 2> "$WAVE_DIR/kernel-journal.stderr"; then
    if grep -Ei 'xe.*(reset|wedg|fault|hang|timedout|device lost)|GuC.*reset|Fault response|VM.*fault|PCIe.*AER|UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST' \
      "$WAVE_DIR/kernel-journal.txt" > "$WAVE_DIR/device-error-scan.txt"; then
      fault_detected=1
      final_status=1
    elif [[ $? -gt 1 ]]; then
      fault_detected=1
      final_status=1
    fi
  else
    fault_detected=1
    final_status=1
  fi
  if grep -EHi 'UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST|out of memory|segmentation fault|core dumped|Aborted|Timedout job' \
    "$WAVE_DIR"/gpu*/server.stdout.log "$WAVE_DIR"/gpu*/server.identity.log \
    > "$WAVE_DIR/server-error-scan.txt" 2> "$WAVE_DIR/server-error-scan.stderr"; then
    fault_detected=1
    final_status=1
  elif [[ $? -gt 1 ]]; then
    fault_detected=1
    final_status=1
  fi
  for gpu in 0 1 2 3; do
    port=$((PORT_BASE + gpu))
    if ss -H -ltn "sport = :$port" | grep -q .; then
      fault_detected=1
      final_status=1
    fi
    if (( fault_detected == 0 )); then
      if sample_gpu "$gpu" "$WAVE_DIR/xpu-smi-final-gpu${gpu}.txt"; then
        used="$(parse_gpu_used_mib "$WAVE_DIR/xpu-smi-final-gpu${gpu}.txt" 2>/dev/null || true)"
        if [[ -z "$used" ]] || (( used > GPU_IDLE_MAX_MIB )); then
          fault_detected=1
          final_status=1
        fi
      else
        fault_detected=1
        final_status=1
      fi
    else
      printf 'skipped: passive fault evidence made active XPU probing unsafe\n' \
        > "$WAVE_DIR/xpu-smi-final-gpu${gpu}.skipped.txt"
    fi
  done
  if (( MODEL_READY == 1 )); then
    [[ "$MODEL" -ef "/proc/$$/fd/$MODEL_FD" ]] || final_status=1
    capture_model_stat "/proc/$$/fd/$MODEL_FD" "$WAVE_DIR/model-stat-final.json" || final_status=1
    cmp -s "$WAVE_DIR/model-stat-baseline.json" "$WAVE_DIR/model-stat-final.json" || final_status=1
    printf '%s  %s\n' "$EXPECTED_MODEL_SHA256" "/proc/$$/fd/$MODEL_FD" | sha256sum -c - \
      > "$WAVE_DIR/model-sha256-final.check.txt" 2>&1 || final_status=1
  fi
  if (( RUNTIME_READY == 1 )); then
    LLAMA_SERVER="$LLAMA_SERVER" RUNTIME_MANIFEST="$RUNTIME_MANIFEST" \
      "$LAUNCHER" --verify-runtime-bundle \
        "$WAVE_DIR/runtime-ldd-final.txt" \
        "$WAVE_DIR/runtime-resolved-final.sha256" \
        "$WAVE_DIR/runtime-bundle-final.json" \
        "$WAVE_DIR/runtime-bundle-initial.json" || final_status=1
  fi
  if (( INPUTS_READY == 1 )); then verify_wave_inputs final || final_status=1; fi
  if (( OUTER_BODY_COMPLETE == 1 )); then
    for gpu in 0 1 2 3; do verify_child_packet "$gpu" || final_status=1; done
  fi
  (( OUTER_BODY_COMPLETE == 1 )) || final_status=1
  {
    echo "original_status=$original_status"
    echo "final_status=$final_status"
    echo "body_complete=$OUTER_BODY_COMPLETE"
    echo "forced_kill=$OUTER_FORCED_KILL"
    echo "cleanup_survivor=$OUTER_CLEANUP_SURVIVOR"
    echo "passive_fault_detected=$fault_detected"
  } > "$WAVE_DIR/wave-cleanup-status.env"
  if (( final_status == 0 )); then printf 'PRE_SEAL_EVIDENCE_VALID\n' > "$WAVE_DIR/wave-status.txt"; else printf 'FAIL\n' > "$WAVE_DIR/wave-status.txt"; fi
  rm -f "$WAVE_DIR/wave-artifacts.sha256" "$WAVE_DIR/wave-diagnostic-completion-status.json"
  seal_directory "$WAVE_DIR" wave-artifacts.sha256 wave-diagnostic-completion-status.json || final_status=1
  if (( final_status == 0 )); then
    if ! manifest_sha="$(file_sha256 "$WAVE_DIR/wave-artifacts.sha256")" || \
       ! summary_sha="$(file_sha256 "$WAVE_DIR/wave-summary.json")"; then
      final_status=1
    fi
    if (( final_status == 0 )); then marker_tmp="$(mktemp "$WAVE_DIR/.wave-diagnostic-completion-status.XXXXXX")" || final_status=1; fi
    if (( final_status == 0 )); then jq -n --arg manifest_sha "$manifest_sha" --arg summary_sha "$summary_sha" \
      '{status:"EVIDENCE_VALID",evidence_valid:true,evidence_class:"diagnostic-only",performance_promotable:false,artifact_manifest:"wave-artifacts.sha256",artifact_manifest_sha256:$manifest_sha,summary:"wave-summary.json",summary_sha256:$summary_sha}' \
      > "$marker_tmp" || final_status=1; fi
    if (( final_status == 0 )); then
      jq -e --arg manifest_sha "$manifest_sha" --arg summary_sha "$summary_sha" '
        .status=="EVIDENCE_VALID" and .evidence_valid==true
        and .evidence_class=="diagnostic-only" and .performance_promotable==false
        and .artifact_manifest=="wave-artifacts.sha256"
        and .artifact_manifest_sha256==$manifest_sha
        and .summary=="wave-summary.json" and .summary_sha256==$summary_sha
      ' "$marker_tmp" >/dev/null || final_status=1
    fi
    if (( final_status == 0 )); then mv "$marker_tmp" "$WAVE_DIR/wave-diagnostic-completion-status.json" || final_status=1; fi
    [[ -z "${marker_tmp:-}" ]] || rm -f "$marker_tmp"
  fi
  if (( final_status != 0 )); then
    rm -f "$WAVE_DIR/wave-diagnostic-completion-status.json"
    printf 'FAIL\n' > "$WAVE_DIR/wave-status.txt"
    seal_directory "$WAVE_DIR" wave-artifacts.sha256 wave-diagnostic-completion-status.json || true
  fi
  printf '%s\n' "$WAVE_DIR"
  exit "$final_status"
}
trap outer_finish EXIT
trap 'exit 130' INT TERM

exec 9>"/run/user/$(id -u)/qwen36-c2-token-matrix-four-gpu-wave.lock"
flock -n 9 || die "another c2 token-matrix wave owns the host lock"
GPU_LEASE_DIR="/run/user/$(id -u)/qwen36-b70-gpu-leases"
PORT_LEASE_DIR="/run/user/$(id -u)/qwen36-b70-port-leases"
mkdir -p "$GPU_LEASE_DIR" "$PORT_LEASE_DIR"
for gpu in 0 1 2 3; do
  unset lease_fd port_fd
  exec {lease_fd}>"$GPU_LEASE_DIR/gpu${gpu}.lock"
  flock -n "$lease_fd" || die "GPU $gpu is leased"
  GPU_LEASE_FDS[$gpu]="$lease_fd"
  port=$((PORT_BASE + gpu))
  exec {port_fd}>"$PORT_LEASE_DIR/port${port}.lock"
  flock -n "$port_fd" || die "port $port is leased"
  PORT_LEASE_FDS[$gpu]="$port_fd"
done

exec {MODEL_FD}<"$MODEL"
flock -s -n "$MODEL_FD" || die "could not acquire shared model lock"
[[ "$MODEL" -ef "/proc/$$/fd/$MODEL_FD" ]] || die "model FD does not match path"
capture_model_stat "/proc/$$/fd/$MODEL_FD" "$WAVE_DIR/model-stat-before-hash.json"
printf '%s  %s\n' "$EXPECTED_MODEL_SHA256" "/proc/$$/fd/$MODEL_FD" | sha256sum -c - \
  > "$WAVE_DIR/model-sha256-initial.check.txt"
capture_model_stat "/proc/$$/fd/$MODEL_FD" "$WAVE_DIR/model-stat-after-hash.json"
cmp -s "$WAVE_DIR/model-stat-before-hash.json" "$WAVE_DIR/model-stat-after-hash.json" || die "model changed during initial hash"
cp "$WAVE_DIR/model-stat-after-hash.json" "$WAVE_DIR/model-stat-baseline.json"
MODEL_READY=1

set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null
set -u
LLAMA_SERVER="$LLAMA_SERVER" RUNTIME_MANIFEST="$RUNTIME_MANIFEST" \
  "$LAUNCHER" --verify-runtime-bundle \
    "$WAVE_DIR/runtime-ldd-initial.txt" \
    "$WAVE_DIR/runtime-resolved-initial.sha256" \
    "$WAVE_DIR/runtime-bundle-initial.json"
RUNTIME_READY=1

available_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
fast_free_kib="$(df -Pk /mnt/fast-ai | awk 'NR==2 {print $4}')"
(( available_kib >= MIN_HOST_AVAILABLE_KIB )) || die "host memory below four-process floor"
(( fast_free_kib >= MIN_FAST_FREE_KIB )) || die "artifact filesystem below free-space floor"
printf 'MemAvailable_kib=%s\nminimum_kib=%s\n' "$available_kib" "$MIN_HOST_AVAILABLE_KIB" > "$WAVE_DIR/host-memory-preflight.env"
printf 'available_kib=%s\nminimum_kib=%s\n' "$fast_free_kib" "$MIN_FAST_FREE_KIB" > "$WAVE_DIR/artifact-space-preflight.env"

if pgrep -af '[l]lama-server|[c]apture-c2-token-matrix.py|[r]un-c2-validation.sh|[r]un-validation.sh' > "$WAVE_DIR/preflight-processes.txt"; then
  die "an inference or validation process is already active"
fi
timeout 20 xpu-smi discovery -j > "$WAVE_DIR/xpu-smi-discovery.json"
jq -e '
  [.device_list[]|select(.device_function_type=="physical" and (.device_name|contains("Arc(TM) Pro B70")))] as $d
  | ($d|length)==4 and ([$d[].device_id]|sort)==[0,1,2,3]
    and ([$d[].pci_bdf_address]|unique|length)==4 and ([$d[].uuid]|unique|length)==4
    and ([$d[]|{device_id,pci_bdf_address}]|sort_by(.device_id)) == [
      {"device_id":0,"pci_bdf_address":"0000:23:00.0"},
      {"device_id":1,"pci_bdf_address":"0000:27:00.0"},
      {"device_id":2,"pci_bdf_address":"0000:43:00.0"},
      {"device_id":3,"pci_bdf_address":"0000:47:00.0"}
    ]
' "$WAVE_DIR/xpu-smi-discovery.json" >/dev/null || die "four distinct B70s were not discovered"
for gpu in 0 1 2 3; do
  sample_gpu "$gpu" "$WAVE_DIR/xpu-smi-preflight-gpu${gpu}.txt"
  used="$(parse_gpu_used_mib "$WAVE_DIR/xpu-smi-preflight-gpu${gpu}.txt")"
  (( used <= GPU_IDLE_MAX_MIB )) || die "GPU $gpu is not idle"
  port=$((PORT_BASE + gpu))
  ! ss -H -ltn "sport = :$port" | grep -q . || die "port $port is already in use"
done

ORACLE_SNAPSHOT="$WAVE_DIR/sequential-c2-oracle.json"
cp "$ORACLE_SOURCE" "$ORACLE_SNAPSHOT"
chmod 0444 "$ORACLE_SNAPSHOT"
printf '%s  %s\n' "$ORACLE_SHA256" "$ORACLE_SNAPSHOT" | sha256sum -c - > "$WAVE_DIR/oracle-snapshot.check.txt"
sha256sum "$SCRIPT" "$LAUNCHER" "$ATTESTER" "$MATRIX_CLIENT" "$FORMAL_CAPTURE" \
  "$COMMON_CAPTURE" "$SUITE" "$PROMPT_BUILDER" "$MODEL_MANIFEST" "$RUNTIME_MANIFEST" \
  "$ORACLE_SNAPSHOT" "$HIST_FORWARD" "$HIST_REVERSE" > "$WAVE_DIR/wave-inputs.sha256"
INPUTS_READY=1
verify_wave_inputs initial || die "wave inputs failed their initial digest check"

scenarios=(duplicate-b swap duplicate-b swap)
WAVE_RELEASE_FILE="$WAVE_DIR/release.json"
WAVE_ABORT_FILE="$WAVE_DIR/abort"
for gpu in 0 1 2 3; do
  port=$((PORT_BASE + gpu))
  scenario="${scenarios[$gpu]}"
  run_dir="$WAVE_DIR/gpu${gpu}-${scenario}"
  CHILD_DIRS[$gpu]="$run_dir"
  setsid --wait /usr/bin/env -i \
    HOME="/home/steve" USER="steve" LOGNAME="steve" SHELL="/bin/bash" \
    PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    LANG="C.utf8" LC_ALL="C.utf8" XDG_RUNTIME_DIR="/run/user/$(id -u)" \
    GPU_INDEX="$gpu" PORT="$port" SCENARIO="$scenario" RUN_DIR="$run_dir" \
    MODEL_FD="$MODEL_FD" QWEN36_MODEL_FD="$MODEL_FD" \
    QWEN36_GPU_LEASE_FD="${GPU_LEASE_FDS[$gpu]}" \
    QWEN36_PORT_LEASE_FD="${PORT_LEASE_FDS[$gpu]}" \
    WAVE_RELEASE_FILE="$WAVE_RELEASE_FILE" WAVE_ABORT_FILE="$WAVE_ABORT_FILE" \
    ORACLE_SNAPSHOT="$ORACLE_SNAPSHOT" \
    RUNTIME_REFERENCE_REPORT="$WAVE_DIR/runtime-bundle-initial.json" \
    MODEL_STAT_BASELINE="$WAVE_DIR/model-stat-baseline.json" \
    READINESS_TIMEOUT_S="$READINESS_TIMEOUT_S" REQUEST_TIMEOUT_S="$REQUEST_TIMEOUT_S" \
    TERM_GRACE_S="$TERM_GRACE_S" KILL_GRACE_S="$KILL_GRACE_S" \
    /usr/bin/bash "$SCRIPT" --child > "$WAVE_DIR/gpu${gpu}-${scenario}.runner.log" 2>&1 &
  CHILD_PIDS[$gpu]=$!
  child_pgid="$(ps -o pgid= -p "${CHILD_PIDS[$gpu]}" | awk '{print $1}')"
  [[ "$child_pgid" == "${CHILD_PIDS[$gpu]}" ]] || die "child $gpu did not become its process-group leader"
  printf 'gpu=%s\tscenario=%s\tport=%s\tpid=%s\trun_dir=%s\n' \
    "$gpu" "$scenario" "$port" "${CHILD_PIDS[$gpu]}" "$run_dir" >> "$WAVE_DIR/wave-launches.tsv"
  (( gpu == 3 || START_STAGGER_S == 0 )) || sleep "$START_STAGGER_S"
done

ready_deadline=$((SECONDS + READINESS_TIMEOUT_S))
while :; do
  all_ready=1
  for gpu in 0 1 2 3; do
    [[ -s "${CHILD_DIRS[$gpu]}/ready.json" ]] || all_ready=0
    if ! leader_running "${CHILD_PIDS[$gpu]}" && [[ ! -s "${CHILD_DIRS[$gpu]}/ready.json" ]]; then
      die "child $gpu exited before readiness"
    fi
  done
  (( all_ready == 1 )) && break
  (( SECONDS < ready_deadline )) || die "four-server readiness timeout"
  sleep 2
done
for gpu in 0 1 2 3; do
  leader_running "${CHILD_PIDS[$gpu]}" || die "child $gpu is not live at the release barrier"
  jq -e --arg scenario "${scenarios[$gpu]}" --argjson gpu "$gpu" --argjson port "$((PORT_BASE + gpu))" '
    .ready==true and .scenario==$scenario and .gpu_index==$gpu and .port==$port
    and (.server_attestation_sha256|test("^[0-9a-f]{64}$"))
  ' "${CHILD_DIRS[$gpu]}/ready.json" >/dev/null || die "child $gpu readiness marker is invalid"
done
verify_wave_inputs prerelease || die "wave inputs changed before diagnostic release"
available_loaded_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
printf 'MemAvailable_kib=%s\n' "$available_loaded_kib" > "$WAVE_DIR/host-memory-all-loaded.env"
(( available_loaded_kib >= 33554432 )) || die "host memory fell below 32 GiB with all services loaded"
release_tmp="$(mktemp "$WAVE_DIR/.release.XXXXXX")"
jq -n --arg released_utc "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '{released:true,released_utc:$released_utc}' > "$release_tmp"
mv "$release_tmp" "$WAVE_RELEASE_FILE"

wave_deadline=$((SECONDS + WAVE_TIMEOUT_S))
while :; do
  any_alive=0
  for pid in "${CHILD_PIDS[@]}"; do leader_running "$pid" && any_alive=1; done
  (( any_alive == 0 )) && break
  (( SECONDS < wave_deadline )) || die "four-child diagnostic timeout"
  sleep 5
done
for gpu in 0 1 2 3; do
  child_pid="${CHILD_PIDS[$gpu]}"
  if wait "$child_pid"; then
    printf 'gpu%s_status=0\n' "$gpu" >> "$WAVE_DIR/child-exit-status.env"
  else
    status=$?
    printf 'gpu%s_status=%s\n' "$gpu" "$status" >> "$WAVE_DIR/child-exit-status.env"
    die "child $gpu failed with status $status"
  fi
  CHILD_PIDS[$gpu]=""
  marker="${CHILD_DIRS[$gpu]}/diagnostic-completion-status.json"
  jq -e --arg scenario "${scenarios[$gpu]}" --argjson gpu "$gpu" '
    .status=="EVIDENCE_VALID" and .evidence_valid==true
    and .evidence_class=="diagnostic-only" and .performance_promotable==false
    and .scenario==$scenario and .gpu_index==$gpu
    and .artifact_manifest=="artifacts.sha256" and .result=="token-matrix.json"
  ' "$marker" >/dev/null || die "child $gpu completion marker is invalid"
  (cd "${CHILD_DIRS[$gpu]}" && sha256sum -c artifacts.sha256 >/dev/null) || die "child $gpu artifact manifest failed"
  [[ "$(sha256sum "${CHILD_DIRS[$gpu]}/artifacts.sha256" | awk '{print $1}')" == "$(jq -r .artifact_manifest_sha256 "$marker")" ]] || die "child $gpu manifest digest mismatch"
  [[ "$(sha256sum "${CHILD_DIRS[$gpu]}/token-matrix.json" | awk '{print $1}')" == "$(jq -r .result_sha256 "$marker")" ]] || die "child $gpu result digest mismatch"
  [[ "$(sha256sum "${CHILD_DIRS[$gpu]}/server-attestation.json" | awk '{print $1}')" == "$(jq -r .server_attestation_sha256 "$marker")" ]] || die "child $gpu attestation digest mismatch"
done

python3 - "$WAVE_DIR" "$HIST_FORWARD" "$HIST_REVERSE" "${CHILD_DIRS[@]}" <<'PY'
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

wave = Path(sys.argv[1])
historical_paths = [Path(sys.argv[2]), Path(sys.argv[3])]
lane_paths = [Path(value) for value in sys.argv[4:]]

def digest_tokens(tokens):
    return hashlib.sha256(json.dumps(tokens, separators=(",", ":")).encode()).hexdigest()

def compare(left, right):
    valid = isinstance(left, list) and isinstance(right, list)
    if not valid:
        return {"comparable": False, "lcp_tokens": None, "exact": False, "first_mismatch": None}
    limit = min(len(left), len(right))
    lcp = 0
    while lcp < limit and left[lcp] == right[lcp]:
        lcp += 1
    mismatch = None
    if lcp < len(left) or lcp < len(right):
        mismatch = {
            "index_zero_based": lcp,
            "ordinal_one_based": lcp + 1,
            "left_token_id": left[lcp] if lcp < len(left) else None,
            "right_token_id": right[lcp] if lcp < len(right) else None,
        }
    return {"comparable": True, "lcp_tokens": lcp, "exact": left == right, "first_mismatch": mismatch}

historical = {}
for path in historical_paths:
    value = json.load(path.open())
    for row in value["rows"]:
        if row["slot_id"] == 1:
            historical[row["case_id"]] = row["stream_token_ids"][:128]
expected_case_ids = {"q27-q8-lc-04k-middle", "q27-q8-c2-04k-b"}
if set(historical) != expected_case_ids:
    raise SystemExit("historical slot-1 fingerprints are incomplete")

discovery = json.load((wave / "xpu-smi-discovery.json").open())
gpu_identities = {
    item["device_id"]: {
        "device_id": item["device_id"],
        "pci_bdf_address": item["pci_bdf_address"],
        "uuid": item["uuid"],
        "device_name": item["device_name"],
    }
    for item in discovery["device_list"]
    if item.get("device_function_type") == "physical"
    and "Arc(TM) Pro B70" in item.get("device_name", "")
}

lanes = []
repeat_groups = defaultdict(list)
for gpu_index, path in enumerate(lane_paths):
    result_path = path / "token-matrix.json"
    value = json.load(result_path.open())
    scenario = value["diagnostic_identity"]["scenario"]
    rows = []
    for row in value["scenario"]["rows"]:
        observed = row["token_ids"]
        expected = row["oracle_prefix_comparison"]["expected_token_ids"]
        case_id = row["case_id"]
        boundary = 95 if case_id == "q27-q8-lc-04k-middle" else 70
        to_c1 = compare(observed, expected)
        retained = {
            "case_id": case_id,
            "slot_id": row["slot_id"],
            "known_natural_answer_tokens": boundary,
            "observed_token_ids": observed,
            "observed_token_ids_sha256": digest_tokens(observed),
            "expected_c1_token_ids": expected,
            "expected_c1_token_ids_sha256": digest_tokens(expected),
            "to_c1": to_c1,
            "observed_prefix_reaches_known_answer_boundary": to_c1["lcp_tokens"] >= boundary,
            "mismatch_after_known_answer_boundary": (
                None if to_c1["exact"] else to_c1["lcp_tokens"] >= boundary
            ),
            "potential_answer_prefix_corruption": to_c1["lcp_tokens"] < boundary,
            "to_historical_slot1_m2": compare(observed, historical.get(case_id)),
        }
        rows.append(retained)
        repeat_groups[(scenario, row["slot_id"], case_id)].append(retained)
    cross_slot = compare(rows[0]["observed_token_ids"], rows[1]["observed_token_ids"])
    lanes.append({
        "gpu_index": gpu_index,
        "gpu_identity": gpu_identities.get(gpu_index),
        "run_dir": str(path),
        "scenario": scenario,
        "classification": value["classification"],
        "evidence_valid": value["evidence_valid"],
        "exact_to_c1": value["exact_to_c1"],
        "rows": rows,
        "cross_slot": {
            "applicable": scenario == "duplicate-b",
            **cross_slot,
        },
    })

repeats = []
for key, rows in sorted(repeat_groups.items()):
    scenario, slot_id, case_id = key
    repeats.append({
        "scenario": scenario,
        "slot_id": slot_id,
        "case_id": case_id,
        "replicate_count": len(rows),
        "comparison": compare(rows[0]["observed_token_ids"], rows[1]["observed_token_ids"]) if len(rows) == 2 else None,
    })

summary = {
    "schema_version": 1,
    "status": "EVIDENCE_VALID",
    "evidence_class": "diagnostic-only",
    "performance_promotable": False,
    "all_lanes_evidence_valid": all(lane["evidence_valid"] for lane in lanes),
    "repeat_structure_complete": len(repeats) == 4
    and all(item["replicate_count"] == 2 for item in repeats),
    "potential_answer_prefix_corruption": any(
        row["potential_answer_prefix_corruption"]
        for lane in lanes
        for row in lane["rows"]
    ),
    "lanes": lanes,
    "cross_repeat_comparisons": repeats,
    "interpretation_guard": {
        "repeat_consensus_required": True,
        "mismatch_before_known_answer_boundary_requires_natural_stop_c2": True,
        "q8_kernel_causality_established": False,
    },
}
if (
    len(lanes) != 4
    or set(gpu_identities) != {0, 1, 2, 3}
    or not summary["all_lanes_evidence_valid"]
    or not summary["repeat_structure_complete"]
):
    raise SystemExit("aggregate lane evidence is incomplete")
with (wave / "wave-summary.json").open("w") as stream:
    json.dump(summary, stream, indent=2, sort_keys=True)
    stream.write("\n")
PY

jq -e '
  .status=="EVIDENCE_VALID" and .evidence_class=="diagnostic-only"
  and .performance_promotable==false and .all_lanes_evidence_valid==true
  and .repeat_structure_complete==true and (.lanes|length)==4
' "$WAVE_DIR/wave-summary.json" >/dev/null || die "wave aggregate summary failed"
OUTER_BODY_COMPLETE=1
