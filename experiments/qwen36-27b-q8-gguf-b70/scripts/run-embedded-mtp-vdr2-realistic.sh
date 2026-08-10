#!/usr/bin/env bash
set -euo pipefail

# Thin, fail-closed live wrapper for the fixed realistic embedded-MTP gate.
# Keep this source state and the moving helper hashes literal PENDING until an
# independent review freezes all three files. The no-argument live path stops
# before ROOT resolution or any external command while either condition holds.
LIVE_ENABLE_STATE="PENDING"
LIVE_ENABLE_REQUIRED="REVIEWED_AND_PINNED"
LIVE_ACK_REQUIRED="I_ACCEPT_ONE_ISOLATED_B70_EMBEDDED_MTP_VDR2_REALISTIC_GATE"
EXPECTED_CAPTURE_SHA256="20f082206de7deafdc679fbd638f8361d69dfd647943919732270709e232cd33"
EXPECTED_REALISTIC_GATES_SHA256="PENDING"
EXPECTED_SERVER_GATES_SHA256="7af3cf19eee537a8381b4583b09649e6a616b375b72685b569c96f7094363a2b"

# Keep the pending live path ahead of ROOT resolution and every external
# command.  This lets offline tests prove that neither acknowledgement state
# can touch a run directory, model, device, listener, or network endpoint.
if [[ $# == 0 ]]; then
  if [[ "$LIVE_ENABLE_STATE" != "$LIVE_ENABLE_REQUIRED" ]]; then
    echo "live embedded-MTP realistic gate is PENDING independent review and frozen helper hashes" >&2
    exit 2
  fi
  if [[ "$EXPECTED_CAPTURE_SHA256" == "PENDING" || "$EXPECTED_REALISTIC_GATES_SHA256" == "PENDING" ]]; then
    echo "live embedded-MTP realistic gate has PENDING helper hashes" >&2
    exit 2
  fi
  if [[ "${QWEN36_EMBEDDED_MTP_REALISTIC_LIVE_ACK:-}" != "$LIVE_ACK_REQUIRED" ]]; then
    echo "live embedded-MTP realistic gate requires the exact acknowledgement" >&2
    exit 2
  fi
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LANE="$ROOT/experiments/qwen36-27b-q8-gguf-b70"
SERVER_GATES="$LANE/scripts/embedded_mtp_vdr2_gates.py"
REALISTIC_GATES="$LANE/scripts/embedded_mtp_realistic_gates.py"
CAPTURE="$LANE/scripts/capture-openai-completions-once.py"
RUNTIME_VERIFY_LAUNCHER="$LANE/scripts/serve-target-only.sh"
OPTIONAL_MANIFEST="$LANE/optional-artifacts-manifest.json"
RUNTIME_MANIFEST="$LANE/runtime-manifest-q8-vdr2-candidate.json"
SUITE="$ROOT/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json"
EXPECTED_SUITE_SHA256="df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac"
PREFIX_ORACLE="/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/embedded-mtp-vdr2-confirmation-gpu0-20260810T090326.726315114Z/oracle-snapshots/sealed-128-oracle-integrated-q8.json"
EXPECTED_PREFIX_ORACLE_SHA256="e07298632346a62f78af9d532593c15f8622b166104ee157bf383bed25228b9d"

MODEL="/mnt/usb-models/models/qwen36-27b-mtp-q8-gguf/Qwen3.6-27B-Q8_0.gguf"
PARTIAL_MODEL="${MODEL}.partial"
EXPECTED_MODEL_SIZE=29047084160
EXPECTED_MODEL_SHA256="9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8"
TRUNK_MODEL_SHA256="f93f517f38e696d35a1a7df2c0e3155a64f4c4dcd662107a146ae263f7fb14ce"
EXPECTED_REPOSITORY="unsloth/Qwen3.6-27B-MTP-GGUF"
EXPECTED_REVISION="5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace"
EXPECTED_RUNTIME_MANIFEST_SHA256="4119790a79c55d158e7257d4fa0d95be0ca34639807c1a71ce87b60d6fdc1b49"
EXPECTED_RUNTIME_SHA256="1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7"
EXPECTED_RUNTIME_VERSION="version: 10298 (15586e2d7)"
LLAMA_SERVER="/mnt/fast-ai/runtime/llama.cpp-15586e2d-qwen27-vdr2-hybrid/llama-server"

usage() {
  cat <<'EOF'
Usage:
  run-embedded-mtp-vdr2-realistic.sh --offline-preflight
  QWEN36_EMBEDDED_MTP_REALISTIC_LIVE_ACK=I_ACCEPT_ONE_ISOLATED_B70_EMBEDDED_MTP_VDR2_REALISTIC_GATE \
    run-embedded-mtp-vdr2-realistic.sh

After the helper files are frozen, their literal hashes are pinned, and
LIVE_ENABLE_STATE is deliberately reviewed, the live form leases all four idle
B70s and runs only GPU 0 through four fresh sequential server lifetimes:
  1. scored control; 2. scored MTP3;
  3. unscored fresh forensic control; 4. unscored fresh forensic MTP3.

Each lifetime pre-renders the fixed 12 prompts and generates each prompt exactly
once through OpenAI text completions with ordinary EOS and max_tokens=512. The
scored requests alone are bracketed by the headline metrics snapshots. Every
arm is stopped, hashed, and made read-only before the next launch. No sidecar
draft is accepted. PORT_BASE and RUN_DIR are the only live overrides.
EOF
}

offline_preflight() {
  for required in python3 jq sha256sum mktemp rm; do
    command -v "$required" >/dev/null 2>&1 || {
      echo "offline preflight: missing command: $required" >&2
      return 2
    }
  done
  [[ "$EXPECTED_CAPTURE_SHA256" =~ ^[0-9a-f]{64}$ ]] || {
    echo "offline preflight: capture helper SHA-256 is PENDING or malformed" >&2
    return 2
  }
  [[ "$EXPECTED_REALISTIC_GATES_SHA256" =~ ^[0-9a-f]{64}$ ]] || {
    echo "offline preflight: realistic gate SHA-256 is PENDING or malformed" >&2
    return 2
  }
  printf '%s  %s\n' "$EXPECTED_CAPTURE_SHA256" "$CAPTURE" | sha256sum -c - >/dev/null
  printf '%s  %s\n' "$EXPECTED_REALISTIC_GATES_SHA256" "$REALISTIC_GATES" | sha256sum -c - >/dev/null
  printf '%s  %s\n' "$EXPECTED_SERVER_GATES_SHA256" "$SERVER_GATES" | sha256sum -c - >/dev/null
  printf '%s  %s\n' "$EXPECTED_SUITE_SHA256" "$SUITE" | sha256sum -c - >/dev/null
  printf '%s  %s\n' "$EXPECTED_PREFIX_ORACLE_SHA256" "$PREFIX_ORACLE" | sha256sum -c - >/dev/null
  [[ "$(sha256sum "$RUNTIME_MANIFEST" | awk '{print $1}')" == "$EXPECTED_RUNTIME_MANIFEST_SHA256" ]] || {
    echo "offline preflight: VDR2 runtime manifest digest mismatch" >&2
    return 2
  }
  jq -e \
    --arg repository "$EXPECTED_REPOSITORY" \
    --arg revision "$EXPECTED_REVISION" \
    --arg sha "$EXPECTED_MODEL_SHA256" \
    --argjson size "$EXPECTED_MODEL_SIZE" '
      .mtp.repository == $repository
      and .mtp.repository_revision == $revision
      and .mtp.filename == "Qwen3.6-27B-Q8_0.gguf"
      and .mtp.size_bytes == $size
      and .mtp.sha256 == $sha
      and .mtp.baseline_size_delta_bytes == 451320736
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
  echo "offline embedded-MTP realistic preflight: PASS"
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

GPU_INDEX=0
PORT_BASE="${PORT_BASE:-19950}"
[[ "$PORT_BASE" =~ ^[0-9]{1,5}$ ]] || {
  echo "PORT_BASE must be a decimal port number" >&2
  exit 2
}
PORT_BASE_DECIMAL=$((10#$PORT_BASE))
(( PORT_BASE_DECIMAL >= 1024 && PORT_BASE_DECIMAL <= 65532 )) || {
  echo "PORT_BASE must leave four valid consecutive unprivileged ports" >&2
  exit 2
}
PORT_SCORED_CONTROL="$PORT_BASE_DECIMAL"
PORT_SCORED_MTP3=$((PORT_BASE_DECIMAL + 1))
PORT_FORENSIC_CONTROL=$((PORT_BASE_DECIMAL + 2))
PORT_FORENSIC_MTP3=$((PORT_BASE_DECIMAL + 3))
READINESS_TIMEOUT_S=900
GPU_IDLE_MAX_MIB=256
MIN_HOST_AVAILABLE_KIB=33554432
MIN_LOADED_DELTA_MIB=25000
MAX_LOADED_USED_MIB=31632
STAMP="$(date -u +%Y%m%dT%H%M%S.%NZ)"
RUN_DIR="${RUN_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/embedded-mtp-vdr2-realistic-gpu0-${STAMP}}"

[[ "$RUN_DIR" == /* && "$RUN_DIR" != "/" && "$RUN_DIR" != *$'\n'* ]] || {
  echo "RUN_DIR must be a non-root absolute path without newlines" >&2
  exit 2
}

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

# Every HTTP operation in this experiment is loopback-only, including the
# Python capture helper.  Do not permit ambient proxy settings to redirect it.
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
export NO_PROXY="127.0.0.1,localhost"
export no_proxy="$NO_PROXY"

for required in awk cat chmod cmp cp curl date dirname env find flock grep id \
  journalctl jq kill mkdir mktemp mv ps python3 readlink rm sha256sum sleep sort \
  ss stat timeout xargs xpu-smi; do
  command -v "$required" >/dev/null 2>&1 || {
    echo "required command not found: $required" >&2
    exit 2
  }
done

offline_preflight >/dev/null
[[ -f "$MODEL" && ! -L "$MODEL" ]] || {
  echo "final pinned model is missing or is a symlink: $MODEL" >&2
  exit 2
}
[[ ! -e "$PARTIAL_MODEL" ]] || {
  echo "refusing live launch while partial artifact exists: $PARTIAL_MODEL" >&2
  exit 2
}
[[ "$(stat -c %s "$MODEL")" == "$EXPECTED_MODEL_SIZE" ]] || {
  echo "integrated MTP model size mismatch" >&2
  exit 2
}
[[ -x "$LLAMA_SERVER" ]] || { echo "llama-server is not executable: $LLAMA_SERVER" >&2; exit 2; }
[[ "$(sha256sum "$RUNTIME_MANIFEST" | awk '{print $1}')" == "$EXPECTED_RUNTIME_MANIFEST_SHA256" ]] || {
  echo "VDR2 runtime manifest SHA-256 mismatch" >&2
  exit 2
}

mkdir -p "$(dirname "$RUN_DIR")"
if ! mkdir "$RUN_DIR"; then
  echo "RUN_DIR already exists or could not be created: $RUN_DIR" >&2
  exit 2
fi

START_EPOCH="$(date +%s)"
SERVER_PID=""
SERVER_PORT=""
SERVER_ARM_DIR=""
SERVER_EXPECTED=0
MODEL_BASELINE_READY=0
RUNTIME_BASELINE_READY=0
HARNESS_BASELINE_READY=0
BODY_COMPLETED=0
PRE_GPU_USED_MIB=""
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
payload = {
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
with open(output, "w") as stream:
    json.dump(payload, stream, indent=2, sort_keys=True)
    stream.write("\n")
PY
}

check_host_memory() {
  local label="$1"
  local available
  available="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
  printf 'MemAvailable_kib=%s\nrequired_kib=%s\n' "${available:-unknown}" "$MIN_HOST_AVAILABLE_KIB" \
    > "$RUN_DIR/host-memory-${label}.env"
  [[ "$available" =~ ^[0-9]+$ ]] && (( available >= MIN_HOST_AVAILABLE_KIB ))
}

gpu_used_mib() {
  local device="$1"
  local output="$2"
  timeout 20 xpu-smi stats -d "$device" > "$output" 2>&1 || return 1
  awk -F '|' '/GPU Memory Used/{gsub(/[^0-9.]/, "", $3); print int($3); exit}' "$output"
}

port_is_listening() {
  local port="$1"
  local listeners
  if ! listeners="$(ss -H -ltn "sport = :$port" 2>&1)"; then
    printf 'ss failed while checking port %s: %s\n' "$port" "$listeners" >&2
    return 2
  fi
  [[ -n "$listeners" ]]
}

verify_harness_inputs() {
  local label="$1"
  [[ "$HARNESS_BASELINE_READY" == 1 ]] || return 1
  sha256sum -c "$RUN_DIR/harness-inputs.sha256" \
    > "$RUN_DIR/harness-inputs-${label}.check.txt" 2>&1
}

verify_model_stat() {
  local label="$1"
  local observed="$RUN_DIR/model-stat-${label}.json"
  [[ "$MODEL_BASELINE_READY" == 1 && "$MODEL" -ef "$MODEL_FD_PATH" ]] || return 1
  capture_model_stat "$observed"
  cmp -s "$RUN_DIR/model-stat-baseline.json" "$observed"
}

stop_active_server() {
  local forced=0
  local survivor=0
  local state=""
  local final_used=""
  local port_closed=0
  local port_status=0
  local vram_returned=0
  [[ -n "$SERVER_PID" ]] || return 0
  if kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    for _ in {1..30}; do
      if ! kill -0 "$SERVER_PID" 2>/dev/null; then break; fi
      state="$(ps -o stat= -p "$SERVER_PID" 2>/dev/null | awk '{print $1}' || true)"
      [[ "$state" == Z* ]] && break
      sleep 1
    done
  fi
  state="$(ps -o stat= -p "$SERVER_PID" 2>/dev/null | awk '{print $1}' || true)"
  if kill -0 "$SERVER_PID" 2>/dev/null && [[ "$state" != Z* ]]; then
    forced=1
    kill -KILL "$SERVER_PID" 2>/dev/null || true
    for _ in {1..10}; do
      if ! kill -0 "$SERVER_PID" 2>/dev/null; then break; fi
      state="$(ps -o stat= -p "$SERVER_PID" 2>/dev/null | awk '{print $1}' || true)"
      [[ "$state" == Z* ]] && break
      sleep 1
    done
  fi
  state="$(ps -o stat= -p "$SERVER_PID" 2>/dev/null | awk '{print $1}' || true)"
  if kill -0 "$SERVER_PID" 2>/dev/null && [[ "$state" != Z* ]]; then
    survivor=1
  else
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  for _ in {1..20}; do
    if port_is_listening "$SERVER_PORT"; then
      :
    else
      port_status=$?
      if (( port_status == 1 )); then
        port_closed=1
        break
      fi
    fi
    sleep 1
  done
  for attempt in {1..30}; do
    final_used="$(gpu_used_mib "$GPU_INDEX" "$SERVER_ARM_DIR/xpu-smi-after-${attempt}.txt" || true)"
    if [[ "$final_used" =~ ^[0-9]+$ ]] && (( final_used <= PRE_GPU_USED_MIB + GPU_IDLE_MAX_MIB )); then
      vram_returned=1
      break
    fi
    sleep 1
  done
  cat > "$SERVER_ARM_DIR/cleanup-status.env" <<EOF
forced_kill=$forced
cleanup_survivor=$survivor
port_closed=$port_closed
vram_returned=$vram_returned
pre_gpu_used_mib=$PRE_GPU_USED_MIB
final_gpu_used_mib=${final_used:-unknown}
EOF
  if (( survivor == 0 )); then
    SERVER_PID=""
    SERVER_PORT=""
    SERVER_ARM_DIR=""
    SERVER_EXPECTED=0
  fi
  (( forced == 0 && survivor == 0 && port_closed == 1 && vram_returned == 1 ))
}

seal_artifacts() {
  local temporary
  temporary="$(mktemp "${RUN_DIR}.artifacts.XXXXXX")" || return 1
  (
    cd "$RUN_DIR" || exit 1
    find . -type f ! -name artifacts.sha256 ! -name completion-status.json -print0 |
      sort -z | xargs -0 -r sha256sum
  ) > "$temporary" || { rm -f -- "$temporary"; return 1; }
  [[ -s "$temporary" ]] || { rm -f -- "$temporary"; return 1; }
  (
    cd "$RUN_DIR" || exit 1
    sha256sum -c "$temporary" >/dev/null
  ) || { rm -f -- "$temporary"; return 1; }
  mv "$temporary" "$RUN_DIR/artifacts.sha256" || {
    rm -f -- "$temporary"
    return 1
  }
}

finalize() {
  local original_status=$?
  local final_status="$original_status"
  local runtime_ok=0
  local model_stat_ok=0
  local model_hash_ok=0
  local harness_ok=0
  local arm_seals_ok=1
  local device_scan_status=0
  local completion_tmp=""
  if (( FINALIZING == 1 )); then
    exit "$original_status"
  fi
  FINALIZING=1
  trap - EXIT INT TERM
  set +e
  if [[ -n "$SERVER_PID" ]]; then
    stop_active_server || final_status=1
  fi
  if (( HARNESS_BASELINE_READY == 1 )) && verify_harness_inputs final; then harness_ok=1; else final_status=1; fi
  if (( MODEL_BASELINE_READY == 1 )) && verify_model_stat final; then model_stat_ok=1; else final_status=1; fi
  if (( MODEL_BASELINE_READY == 1 )); then
    if printf '%s  %s\n' "$EXPECTED_MODEL_SHA256" "$MODEL_FD_PATH" |
      sha256sum -c - > "$RUN_DIR/model-sha256-final.check.txt" 2>&1; then
      model_hash_ok=1
    else
      final_status=1
    fi
  fi
  if (( RUNTIME_BASELINE_READY == 1 )); then
    if LLAMA_SERVER="$LLAMA_SERVER" RUNTIME_MANIFEST="$RUNTIME_MANIFEST" \
      "$RUNTIME_VERIFY_LAUNCHER" --verify-runtime-bundle \
      "$RUN_DIR/llama-server-ldd-final.txt" \
      "$RUN_DIR/runtime-resolved-files-final.sha256" \
      "$RUN_DIR/runtime-bundle-final.json" \
      "$RUN_DIR/runtime-bundle-initial.json"; then
      runtime_ok=1
    else
      final_status=1
    fi
  fi
  journalctl -k --since "@$START_EPOCH" --no-pager \
    > "$RUN_DIR/kernel-journal.txt" 2> "$RUN_DIR/kernel-journal.stderr.txt"
  if [[ $? != 0 ]]; then final_status=1; fi
  grep -Ei 'xe.*(reset|wedg|fault|hang|timedout|device lost)|GuC.*reset|Fault response|VM.*fault|PCIe.*AER|UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST' \
    "$RUN_DIR/kernel-journal.txt" > "$RUN_DIR/device-error-scan.txt"
  device_scan_status=$?
  if (( device_scan_status > 1 )) || [[ -s "$RUN_DIR/device-error-scan.txt" ]]; then final_status=1; fi
  for arm in scored-control scored-mtp3 forensic-control forensic-mtp3; do
    if [[ ! -f "$RUN_DIR/$arm/arm-artifacts.sha256" ]] || ! (
      cd "$RUN_DIR/$arm" && sha256sum -c arm-artifacts.sha256
    ) > "$RUN_DIR/arm-seal-${arm}.check.txt" 2>&1; then
      arm_seals_ok=0
      final_status=1
    fi
  done
  if (( BODY_COMPLETED != 1 )); then final_status=1; fi
  if ! printf '%s\n' \
    "harness_inputs_unchanged=$harness_ok" \
    "model_stat_unchanged=$model_stat_ok" \
    "model_sha256_final_verified=$model_hash_ok" \
    "runtime_bundle_unchanged=$runtime_ok" \
    "all_four_arm_seals_verified=$arm_seals_ok" \
    "body_completed=$BODY_COMPLETED" \
    > "$RUN_DIR/final-integrity.env"; then
    final_status=1
  fi
  if ! rm -f -- "$RUN_DIR/artifacts.sha256" "$RUN_DIR/completion-status.json"; then
    final_status=1
  fi
  if (( final_status == 0 )); then
    printf 'PASS_EVIDENCE_VALID\n' > "$RUN_DIR/run-status.txt" || final_status=1
  fi
  if (( final_status != 0 )); then
    printf 'FAIL\n' > "$RUN_DIR/run-status.txt" || true
  fi
  if ! seal_artifacts; then
    final_status=1
    printf 'FAIL\n' > "$RUN_DIR/run-status.txt" || true
    rm -f -- "$RUN_DIR/artifacts.sha256" "$RUN_DIR/completion-status.json" || true
    seal_artifacts || true
  fi
  if (( final_status == 0 )); then
    if ! completion_tmp="$(mktemp "${RUN_DIR}.completion.XXXXXX")"; then
      final_status=1
    elif ! python3 - "$RUN_DIR" "$completion_tmp" <<'PY'
import hashlib
import json
import sys
from pathlib import Path
run = Path(sys.argv[1])
output = Path(sys.argv[2])
comparison = json.loads((run / "comparison.json").read_text())
if (
    comparison.get("evidence_passed") is not True
    or comparison.get("realistic_policy_passed") is not True
    or comparison.get("localmaxxing_submission_ready") is not False
    or comparison.get("classification")
    not in {"PASS_REALISTIC_MTP_WIN", "VALID_REALISTIC_NO_MTP_WIN"}
):
    raise SystemExit("comparison evidence gate is not passed")
if (run / "run-status.txt").read_text() != "PASS_EVIDENCE_VALID\n":
    raise SystemExit("run status is not PASS_EVIDENCE_VALID")

def read_env(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text().splitlines():
        key, separator, value = line.partition("=")
        if not separator or not key or key in result:
            raise SystemExit(f"invalid env evidence: {path}")
        result[key] = value
    return result

integrity = read_env(run / "final-integrity.env")
if integrity != {
    "harness_inputs_unchanged": "1",
    "model_stat_unchanged": "1",
    "model_sha256_final_verified": "1",
    "runtime_bundle_unchanged": "1",
    "all_four_arm_seals_verified": "1",
    "body_completed": "1",
}:
    raise SystemExit("final integrity gate is not fully passed")
for arm in ("scored-control", "scored-mtp3", "forensic-control", "forensic-mtp3"):
    cleanup = read_env(run / arm / "cleanup-status.env")
    if any(cleanup.get(key) != value for key, value in {
        "forced_kill": "0",
        "cleanup_survivor": "0",
        "port_closed": "1",
        "vram_returned": "1",
    }.items()):
        raise SystemExit(f"{arm} cleanup gate is not fully passed")
payload = {
    "passed": True,
    "evidence_valid": True,
    "classification": comparison.get("classification"),
    "realistic_policy_passed": True,
    "localmaxxing_submission_ready": False,
    "artifacts_manifest_sha256": hashlib.sha256((run / "artifacts.sha256").read_bytes()).hexdigest(),
    "comparison_sha256": hashlib.sha256((run / "comparison.json").read_bytes()).hexdigest(),
}
output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
PY
    then
      final_status=1
    elif ! mv "$completion_tmp" "$RUN_DIR/completion-status.json"; then
      final_status=1
    fi
  fi
  if (( final_status != 0 )); then
    [[ -z "$completion_tmp" ]] || rm -f -- "$completion_tmp" || true
    rm -f -- "$RUN_DIR/completion-status.json" "$RUN_DIR/artifacts.sha256" || true
    printf 'FAIL\n' > "$RUN_DIR/run-status.txt" || true
    seal_artifacts || true
  fi
  exit "$final_status"
}
trap finalize EXIT
trap 'exit 130' INT TERM

exec {QWEN36_MODEL_FD}<"$MODEL"
flock -s -n "$QWEN36_MODEL_FD" || { echo "could not lock integrated model" >&2; exit 2; }
MODEL_FD_PATH="/proc/$$/fd/$QWEN36_MODEL_FD"
MODEL_LOAD_PATH="/proc/self/fd/$QWEN36_MODEL_FD"
[[ "$MODEL" -ef "$MODEL_FD_PATH" ]] || { echo "model path/descriptor mismatch" >&2; exit 2; }
export QWEN36_MODEL_FD

capture_model_stat "$RUN_DIR/model-stat-before-hash.json"
printf '%s  %s\n' "$EXPECTED_MODEL_SHA256" "$MODEL_FD_PATH" |
  sha256sum -c - > "$RUN_DIR/model-sha256-initial.check.txt"
capture_model_stat "$RUN_DIR/model-stat-after-hash.json"
cmp -s "$RUN_DIR/model-stat-before-hash.json" "$RUN_DIR/model-stat-after-hash.json" || {
  echo "model identity changed during initial hash" >&2
  exit 2
}
cp "$RUN_DIR/model-stat-after-hash.json" "$RUN_DIR/model-stat-baseline.json"
MODEL_BASELINE_READY=1

mkdir "$RUN_DIR/input-snapshots"
cp "$SUITE" "$RUN_DIR/input-snapshots/realistic-suite-v1.json"
cp "$PREFIX_ORACLE" "$RUN_DIR/input-snapshots/prefix-oracle.json"
SUITE_SNAPSHOT="$RUN_DIR/input-snapshots/realistic-suite-v1.json"
PREFIX_ORACLE_SNAPSHOT="$RUN_DIR/input-snapshots/prefix-oracle.json"
printf '%s  %s\n' "$EXPECTED_SUITE_SHA256" "$SUITE_SNAPSHOT" | sha256sum -c - >/dev/null
printf '%s  %s\n' "$EXPECTED_PREFIX_ORACLE_SHA256" "$PREFIX_ORACLE_SNAPSHOT" | sha256sum -c - >/dev/null
chmod 0444 "$SUITE_SNAPSHOT" "$PREFIX_ORACLE_SNAPSHOT"

GPU_LEASE_DIR="/run/user/$(id -u)/qwen36-b70-gpu-leases"
PORT_LEASE_DIR="/run/user/$(id -u)/qwen36-b70-port-leases"
mkdir -p "$GPU_LEASE_DIR" "$PORT_LEASE_DIR"
LEASE_FDS=()
for device in 0 1 2 3; do
  lease_path="$GPU_LEASE_DIR/gpu${device}.lock"
  exec {lease_fd}>"$lease_path"
  flock -n "$lease_fd" || { echo "GPU $device is leased; isolated realistic gate refused" >&2; exit 2; }
  LEASE_FDS+=("$lease_fd")
done
for port in "$PORT_SCORED_CONTROL" "$PORT_SCORED_MTP3" "$PORT_FORENSIC_CONTROL" "$PORT_FORENSIC_MTP3"; do
  lease_path="$PORT_LEASE_DIR/port${port}.lock"
  exec {lease_fd}>"$lease_path"
  flock -n "$lease_fd" || { echo "port $port is leased" >&2; exit 2; }
  LEASE_FDS+=("$lease_fd")
  if port_is_listening "$port"; then
    echo "port already in use: $port" >&2
    exit 2
  else
    port_status=$?
    if (( port_status != 1 )); then
      echo "could not establish that port is closed: $port" >&2
      exit 2
    fi
  fi
done

check_host_memory preflight || { echo "host MemAvailable below 32 GiB floor" >&2; exit 2; }
xpu-smi discovery -j > "$RUN_DIR/xpu-smi-discovery.json"
jq -e --argjson device "$GPU_INDEX" '
  ([.device_list[] |
    select(.device_function_type == "physical" and (.device_name | contains("Arc(TM) Pro B70"))) |
    {device_id, pci_bdf_address, uuid}] | length) == 4
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
    select(.device_id == $device and .device_function_type == "physical" and (.device_name | contains("Arc(TM) Pro B70")))] | length) == 1
' "$RUN_DIR/xpu-smi-discovery.json" >/dev/null
jq --argjson device "$GPU_INDEX" -r '
  .device_list[] | select(.device_id == $device) |
  "gpu_id=" + (.device_id | tostring) + "\ngpu_bdf=" + .pci_bdf_address +
  "\ngpu_uuid=" + .uuid + "\ngpu_name=" + .device_name
' "$RUN_DIR/xpu-smi-discovery.json" > "$RUN_DIR/gpu-identity.env"
for device in 0 1 2 3; do
  used="$(gpu_used_mib "$device" "$RUN_DIR/xpu-smi-before-gpu${device}.txt")"
  [[ "$used" =~ ^[0-9]+$ ]] || { echo "cannot parse GPU $device memory" >&2; exit 2; }
  (( used <= GPU_IDLE_MAX_MIB )) || { echo "GPU $device is not idle: $used MiB" >&2; exit 2; }
  if [[ "$device" == "$GPU_INDEX" ]]; then PRE_GPU_USED_MIB="$used"; fi
done

LLAMA_SERVER="$LLAMA_SERVER" RUNTIME_MANIFEST="$RUNTIME_MANIFEST" \
  "$RUNTIME_VERIFY_LAUNCHER" --verify-runtime-bundle \
  "$RUN_DIR/llama-server-ldd-initial.txt" \
  "$RUN_DIR/runtime-resolved-files.sha256" \
  "$RUN_DIR/runtime-bundle-initial.json"
RUNTIME_BASELINE_READY=1

set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null
set -u
RUNTIME_ORIGIN="$(dirname "$LLAMA_SERVER")"
export LD_LIBRARY_PATH="$RUNTIME_ORIGIN${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export ONEAPI_DEVICE_SELECTOR="level_zero:*"
export ZE_AFFINITY_MASK="$GPU_INDEX"
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

harness_inputs=(
  "$OPTIONAL_MANIFEST" "$RUNTIME_MANIFEST" "$SERVER_GATES" "$REALISTIC_GATES"
  "$CAPTURE" "$RUNTIME_VERIFY_LAUNCHER" "$SUITE" "$PREFIX_ORACLE"
  "$SUITE_SNAPSHOT" "$PREFIX_ORACLE_SNAPSHOT"
  "$LANE/scripts/run-embedded-mtp-vdr2-realistic.sh"
)
printf '%s\n' "${harness_inputs[@]}" | sort -u > "$RUN_DIR/harness-input-paths.txt"
while IFS= read -r path; do sha256sum "$path"; done \
  < "$RUN_DIR/harness-input-paths.txt" > "$RUN_DIR/harness-inputs.sha256"
HARNESS_BASELINE_READY=1
verify_harness_inputs initial || { echo "harness inputs failed initial verification" >&2; exit 2; }

cat > "$RUN_DIR/run-identity.env" <<EOF
date_utc=$STAMP
evidence_class=official-isolated-realistic-gate
performance_promotable=0
gpu_index=$GPU_INDEX
scored_control_port=$PORT_SCORED_CONTROL
scored_mtp3_port=$PORT_SCORED_MTP3
forensic_control_port=$PORT_FORENSIC_CONTROL
forensic_mtp3_port=$PORT_FORENSIC_MTP3
model=$MODEL
model_load_path=$MODEL_LOAD_PATH
model_size=$EXPECTED_MODEL_SIZE
model_sha256=$EXPECTED_MODEL_SHA256
model_repository=$EXPECTED_REPOSITORY
model_revision=$EXPECTED_REVISION
runtime_manifest=$RUNTIME_MANIFEST
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
suite_sha256=$EXPECTED_SUITE_SHA256
prefix_oracle_sha256=$EXPECTED_PREFIX_ORACLE_SHA256
capture_sha256=$EXPECTED_CAPTURE_SHA256
realistic_gates_sha256=$EXPECTED_REALISTIC_GATES_SHA256
EOF

seal_arm() {
  local arm_dir="$1"
  local temporary
  temporary="$(mktemp "${arm_dir}.artifacts.XXXXXX")"
  (
    cd "$arm_dir"
    find . -type f ! -name arm-artifacts.sha256 -print0 |
      sort -z | xargs -0 -r sha256sum
  ) > "$temporary"
  [[ -s "$temporary" ]]
  (
    cd "$arm_dir"
    sha256sum -c "$temporary" >/dev/null
  )
  mv "$temporary" "$arm_dir/arm-artifacts.sha256"
  find "$arm_dir" -type f -exec chmod 0444 {} +
  chmod 0555 "$arm_dir"
}

run_lifetime() {
  local arm="$1"
  local mode="$2"
  local kind="$3"
  local port="$4"
  local alias="qwen36-27b-mtp-q8-vdr2-realistic-${mode}"
  local arm_dir="$RUN_DIR/$arm"
  local loaded=""
  local loaded_delta=""
  local -a server_cmd
  local -a spec_args
  mkdir "$arm_dir"
  if [[ "$mode" == "control" ]]; then
    spec_args=(--spec-type none)
  else
    spec_args=(
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
    )
  fi
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
    "${spec_args[@]}"
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
  python3 - "$arm_dir/server-identity.json" "$mode" "$kind" "$MODEL"     "$MODEL_LOAD_PATH" "$EXPECTED_MODEL_SHA256" "$EXPECTED_RUNTIME_SHA256"     "${server_cmd[@]}" <<'PY'
import json
import sys
output, mode, lifetime, model, load_path, model_sha, runtime_sha, *argv = sys.argv[1:]
with open(output, "w") as stream:
    json.dump(
        {
            "mode": mode,
            "lifetime": lifetime,
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
  verify_harness_inputs "${arm}-prelaunch"
  verify_model_stat "${arm}-prelaunch"
  SERVER_PORT="$port"
  SERVER_ARM_DIR="$arm_dir"
  "${server_cmd[@]}" > "$arm_dir/server.stdout.log" 2>&1 &
  SERVER_PID=$!
  printf '%s\n' "$SERVER_PID" > "$arm_dir/server.pid"
  deadline=$((SECONDS + READINESS_TIMEOUT_S))
  until curl --noproxy '*' -fsS "http://127.0.0.1:${port}/v1/models"     > "$arm_dir/models.json" 2> "$arm_dir/models.err"; do
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
      echo "$arm server exited before readiness" >&2
      return 1
    fi
    if (( SECONDS >= deadline )); then
      echo "$arm server readiness timeout" >&2
      return 1
    fi
    sleep 2
  done
  SERVER_EXPECTED=1
  python3 "$SERVER_GATES" gate-server     --mode "$mode"     --log "$arm_dir/server.stdout.log"     --identity "$arm_dir/server-identity.json"     --output "$arm_dir/server-gate.json"
  loaded="$(gpu_used_mib "$GPU_INDEX" "$arm_dir/xpu-smi-loaded.txt")"
  [[ "$loaded" =~ ^[0-9]+$ ]] || { echo "cannot parse loaded VRAM" >&2; return 1; }
  loaded_delta=$((loaded - PRE_GPU_USED_MIB))
  cat > "$arm_dir/loaded-residency.env" <<EOF
pre_mib=$PRE_GPU_USED_MIB
loaded_mib=$loaded
loaded_delta_mib=$loaded_delta
required_delta_mib=$MIN_LOADED_DELTA_MIB
maximum_loaded_mib=$MAX_LOADED_USED_MIB
minimum_free_headroom_mib=1024
EOF
  (( loaded_delta >= MIN_LOADED_DELTA_MIB && loaded <= MAX_LOADED_USED_MIB )) || {
    echo "$arm loaded residency violates fit bounds" >&2
    return 1
  }
  check_host_memory "${arm}-loaded"
  python3 "$CAPTURE" prepare     --base-url "http://127.0.0.1:${port}"     --suite "$SUITE_SNAPSHOT"     --output "$arm_dir/prepared.json"     > "$arm_dir/prepare.stdout.log" 2>&1
  curl --noproxy '*' -fsS "http://127.0.0.1:${port}/metrics"     > "$arm_dir/metrics-before.prom"
  if [[ "$kind" == "scored" ]]; then
    python3 "$CAPTURE" run       --base-url "http://127.0.0.1:${port}"       --model "$alias"       --prepared "$arm_dir/prepared.json"       --output "$arm_dir/scored.json"       > "$arm_dir/capture.stdout.log" 2>&1
  else
    python3 "$CAPTURE" forensic       --base-url "http://127.0.0.1:${port}"       --model "$alias"       --prepared "$arm_dir/prepared.json"       --output "$arm_dir/forensic.json"       > "$arm_dir/capture.stdout.log" 2>&1
  fi
  curl --noproxy '*' -fsS "http://127.0.0.1:${port}/metrics"     > "$arm_dir/metrics-after.prom"
  python3 "$SERVER_GATES" gate-metrics     --mode "$mode"     --before "$arm_dir/metrics-before.prom"     --after "$arm_dir/metrics-after.prom"     --output "$arm_dir/sealed-metrics-gate.json"
  python3 "$SERVER_GATES" gate-server     --mode "$mode"     --log "$arm_dir/server.stdout.log"     --identity "$arm_dir/server-identity.json"     --output "$arm_dir/server-gate-postcapture.json"
  verify_harness_inputs "${arm}-postcapture"
  verify_model_stat "${arm}-postcapture"
  stop_active_server
  seal_arm "$arm_dir"
}

# Preregistered fresh-lifetime order. Never overlap or reorder these calls.
run_lifetime scored-control control scored "$PORT_SCORED_CONTROL"
run_lifetime scored-mtp3 mtp3 scored "$PORT_SCORED_MTP3"
run_lifetime forensic-control control forensic "$PORT_FORENSIC_CONTROL"
run_lifetime forensic-mtp3 mtp3 forensic "$PORT_FORENSIC_MTP3"

mkdir "$RUN_DIR/gates"
CONTROL_SCORED_SHA256="$(sha256sum "$RUN_DIR/scored-control/scored.json" | awk '{print $1}')"
CONTROL_FORENSIC_SHA256="$(sha256sum "$RUN_DIR/forensic-control/forensic.json" | awk '{print $1}')"

python3 "$REALISTIC_GATES" gate-capture   --mode control   --input "$RUN_DIR/scored-control/scored.json"   --forensic-input "$RUN_DIR/forensic-control/forensic.json"   --suite "$SUITE_SNAPSHOT"   --prefix-oracle "$PREFIX_ORACLE_SNAPSHOT"   --server-identity "$RUN_DIR/scored-control/server-identity.json"   --server-gate "$RUN_DIR/scored-control/server-gate.json"   --server-post-gate "$RUN_DIR/scored-control/server-gate-postcapture.json"   --forensic-server-identity "$RUN_DIR/forensic-control/server-identity.json"   --forensic-server-gate "$RUN_DIR/forensic-control/server-gate.json"   --forensic-server-post-gate "$RUN_DIR/forensic-control/server-gate-postcapture.json"   --output "$RUN_DIR/gates/control-capture-gate.json"

python3 "$REALISTIC_GATES" gate-capture   --mode mtp3   --input "$RUN_DIR/scored-mtp3/scored.json"   --forensic-input "$RUN_DIR/forensic-mtp3/forensic.json"   --suite "$SUITE_SNAPSHOT"   --prefix-oracle "$PREFIX_ORACLE_SNAPSHOT"   --server-identity "$RUN_DIR/scored-mtp3/server-identity.json"   --server-gate "$RUN_DIR/scored-mtp3/server-gate.json"   --server-post-gate "$RUN_DIR/scored-mtp3/server-gate-postcapture.json"   --forensic-server-identity "$RUN_DIR/forensic-mtp3/server-identity.json"   --forensic-server-gate "$RUN_DIR/forensic-mtp3/server-gate.json"   --forensic-server-post-gate "$RUN_DIR/forensic-mtp3/server-gate-postcapture.json"   --control-input "$RUN_DIR/scored-control/scored.json"   --expected-control-sha256 "$CONTROL_SCORED_SHA256"   --control-forensic-input "$RUN_DIR/forensic-control/forensic.json"   --expected-control-forensic-sha256 "$CONTROL_FORENSIC_SHA256"   --output "$RUN_DIR/gates/mtp3-capture-gate.json"

for mode in control mtp3; do
  arm="scored-${mode}"
  python3 "$REALISTIC_GATES" gate-metrics-binding     --mode "$mode"     --before "$RUN_DIR/$arm/metrics-before.prom"     --after "$RUN_DIR/$arm/metrics-after.prom"     --capture "$RUN_DIR/$arm/scored.json"     --sealed-gate "$RUN_DIR/$arm/sealed-metrics-gate.json"     --output "$RUN_DIR/gates/${mode}-metrics-binding-gate.json"
done

python3 "$REALISTIC_GATES" compare-arms   --control-capture-gate "$RUN_DIR/gates/control-capture-gate.json"   --candidate-capture-gate "$RUN_DIR/gates/mtp3-capture-gate.json"   --control-metrics-gate "$RUN_DIR/gates/control-metrics-binding-gate.json"   --candidate-metrics-gate "$RUN_DIR/gates/mtp3-metrics-binding-gate.json"   --control-cleanup "$RUN_DIR/scored-control/cleanup-status.env"   --candidate-cleanup "$RUN_DIR/scored-mtp3/cleanup-status.env"   --control-forensic-cleanup "$RUN_DIR/forensic-control/cleanup-status.env"   --candidate-forensic-cleanup "$RUN_DIR/forensic-mtp3/cleanup-status.env"   --output "$RUN_DIR/comparison.json"
jq -e '
  .evidence_passed == true
  and .realistic_policy_passed == true
  and (.classification == "PASS_REALISTIC_MTP_WIN"
       or .classification == "VALID_REALISTIC_NO_MTP_WIN")
  and .localmaxxing_submission_ready == false
' "$RUN_DIR/comparison.json" >/dev/null
BODY_COMPLETED=1
echo "$RUN_DIR"
