#!/usr/bin/env bash
set -euo pipefail

# Two four-card waves for the canonical-Q8 forced-512 c2 causal control.
# --print-wave-plan is read-only.  Live execution remains fail-closed until an
# independent review explicitly changes PHASE2_LIVE_GATE and all frozen hashes
# match.  This runner never reloads xe and never reboots the host.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LANE="$ROOT/experiments/qwen36-27b-q8-gguf-b70"
SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
ANALYZER="$LANE/scripts/canonical-q8-c2-crossover-study.py"
LAUNCHER="$LANE/scripts/serve-target-only.sh"
SERVER_ATTESTER="$LANE/scripts/attest-c2-server.py"
MATRIX_CLIENT="$LANE/scripts/capture-c2-token-matrix.py"
CAPTURE_HELPER="$LANE/scripts/capture-simultaneous-c2.py"
COMMON_CAPTURE="$LANE/scripts/capture-exact-tokens.py"
PROMPT_BUILDER="$ROOT/scripts/bench-openai-long-context-suite.py"
RUNTIME_MANIFEST="$LANE/runtime-manifest-canonical-q8-c2.json"
MODEL_MANIFEST="$LANE/model-manifest.json"
SUITE="$LANE/c2-long-context-suite-v1.json"
LLAMA_SERVER="/mnt/fast-ai/runtime/llama.cpp-15586e2d-q8-c2-canonical-109eee6f-hybrid/llama-server"
MODEL="/mnt/usb-models/models/qwen36-27b-q8-gguf/Qwen3.6-27B-Q8_0.gguf"

# Activation requires a reviewed literal edit to these exact, hash-pinned bytes.
# The environment cannot override this fail-closed checkpoint.
PHASE2_LIVE_GATE="REVIEWED_AND_FROZEN"
ACTION="${1:-}"
if [[ "$ACTION" == "--print-wave-plan" ]]; then
  [[ $# -eq 1 ]] || { echo "ERROR: --print-wave-plan accepts no other arguments" >&2; exit 2; }
  exec python3 "$ANALYZER" print-plan --port-base "${PORT_BASE:-19720}"
fi
if [[ "$ACTION" != "--run-phase2" && "$ACTION" != "--child" ]]; then
  echo "ERROR: use --print-wave-plan or the explicitly reviewed --run-phase2 action" >&2
  exit 2
fi
[[ "$PHASE2_LIVE_GATE" == "REVIEWED_AND_FROZEN" ]] || {
  echo "ERROR: Phase-2 live gate is pending independent review" >&2
  exit 2
}

EXPECTED_MODEL_SHA256="f93f517f38e696d35a1a7df2c0e3155a64f4c4dcd662107a146ae263f7fb14ce"
EXPECTED_MODEL_SIZE=28595763424
EXPECTED_RUNTIME_SHA256="1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7"
EXPECTED_MANIFEST_SHA256="1b6c305b7e3fad027e7397168bda23526b72b8a4b59e8c6b2b3788fc7347b4d9"
EXPECTED_SYCL_DSO_SHA256="f0a9e736dde321f72fceb14db6fb1410a9ad090380a3cf8ed7c591e949c94305"
EXPECTED_SUITE_SHA256="053523440e4a23d7f772dec5025fe4831ba33c0a8eaba76795e4ee76718860af"
EXPECTED_LAUNCHER_SHA256="fa9475956c9de8dc225e23c13b25e5851bc545ae24ec1ede92939f3ae7f08010"
EXPECTED_SERVER_ATTESTER_SHA256="3ca549cd971fd76b3152c8bb9e0a55689eb398051ee61a2ed2e532b3f8b2ec78"
EXPECTED_MATRIX_SHA256="aac9348d09340bfdc2b21725512ff4784f1fe42be533f69f7cf8a96277a872a7"
EXPECTED_CAPTURE_HELPER_SHA256="7d89e99ee8f69dea24f27a6a0b83b7c9faf8285273159c2b771149126d2d0f00"
EXPECTED_COMMON_CAPTURE_SHA256="94595b6962e64981723a063b6ec23b80c3701a22d0e256e85b596e6bf75f5b05"
EXPECTED_PROMPT_BUILDER_SHA256="2286c9fd1ef59136a92a857be2992b31e0ff3bc844c7489239ab8f76f515cf72"
EXPECTED_MODEL_MANIFEST_SHA256="858a15c80b51fdedf7bed24f32906369d1c0b7b8534a04b3822bc1b80f6829b9"
# Pinned after the analyzer and adversarial suite passed offline checks.
EXPECTED_ANALYZER_SHA256="771b50bd25432af0da9d6e7b9503112a1b148423367d47340454faa7b5b3acfa"

PHASE1_DIR="/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/canonical-q8-c1-oracle-four-gpu-20260810T013725.235133447Z"
EXPECTED_PHASE1_MANIFEST_SHA256="2871f4947a06a99f28ea813dbb1b092f638336ef46be6631d79f7528fe98259c"
EXPECTED_PHASE1_SUMMARY_SHA256="5550e5a60f577d6642d750b1f7035759a286ffcb383e35497e0c546f2d46741b"
EXPECTED_PHASE1_MARKER_SHA256="5335f67a5b5a177ae6bada2cabb45f6c1fc45cc62f285072e2ceefa572d6ce01"
EXPECTED_SELECTOR0_ORACLE_SHA256="62a3e2991f697db2e420a49ddb048539cf94f1fd436f93b3f48b08eb8b38d573"
EXPECTED_SELECTOR1_ORACLE_SHA256="bb179eac0ffa11bffc2d56f77b309ccdf62fcbce193f56a1cb9efbc944e6a2d4"

PORT_BASE=19720
WAVE1_SELECTORS=(0 1 0 1)
WAVE2_SELECTORS=(1 0 1 0)
SCENARIOS=(forward forward reverse reverse)
START_STAGGER_S="${START_STAGGER_S:-5}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-1200}"
REQUEST_TIMEOUT_S="${REQUEST_TIMEOUT_S:-1800}"
WAVE_TIMEOUT_S="${WAVE_TIMEOUT_S:-7200}"
TERM_GRACE_S="${TERM_GRACE_S:-90}"
KILL_GRACE_S="${KILL_GRACE_S:-10}"
PASSIVE_DRAIN_S="${PASSIVE_DRAIN_S:-60}"
FAILURE_HANDOFF_MARGIN_S="${FAILURE_HANDOFF_MARGIN_S:-40}"
PREFIX_STABILITY_TIMEOUT_S=10
UNBOUND_TRANSITION_WAIT_S=35
GPU_IDLE_MAX_MIB=256
MIN_LOADED_DELTA_MIB=25000
MIN_FIT_FREE_MIB=1024
MIN_HOST_AVAILABLE_KIB="${MIN_HOST_AVAILABLE_KIB:-100663296}"
MIN_FAST_FREE_KIB="${MIN_FAST_FREE_KIB:-10485760}"
STAMP="$(date -u +%Y%m%dT%H%M%S.%NZ)"
RUN_ROOT="${RUN_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/canonical-q8-c2-crossover-four-gpu-${STAMP}}"

# Child EXIT runs outside child_main's local frame, so all cleanup state is
# initialized here and reset before every child workload.
CHILD_STATE_ACTIVE=0
CHILD_FAILURE_REASON="child exited without a classified cause"
CHILD_SERVER_PID=""
CHILD_SERVER_PPID=""
CHILD_SERVER_START_TICKS=""
CHILD_SERVER_PGID=""
CHILD_CLEANUP_FORCED=0
CHILD_CLEANUP_SURVIVOR=0
CHILD_NORMAL_COMPLETE=0

die() {
  if [[ "${CHILD_STATE_ACTIVE:-0}" == 1 ]]; then CHILD_FAILURE_REASON="$*"; fi
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

assert_core_dependency_hashes() {
  assert_sha "$ANALYZER" "$EXPECTED_ANALYZER_SHA256"
  assert_sha "$LAUNCHER" "$EXPECTED_LAUNCHER_SHA256"
  assert_sha "$SERVER_ATTESTER" "$EXPECTED_SERVER_ATTESTER_SHA256"
  assert_sha "$MATRIX_CLIENT" "$EXPECTED_MATRIX_SHA256"
  assert_sha "$CAPTURE_HELPER" "$EXPECTED_CAPTURE_HELPER_SHA256"
  assert_sha "$COMMON_CAPTURE" "$EXPECTED_COMMON_CAPTURE_SHA256"
  assert_sha "$PROMPT_BUILDER" "$EXPECTED_PROMPT_BUILDER_SHA256"
  assert_sha "$RUNTIME_MANIFEST" "$EXPECTED_MANIFEST_SHA256"
  assert_sha "$MODEL_MANIFEST" "$EXPECTED_MODEL_MANIFEST_SHA256"
  assert_sha "$SUITE" "$EXPECTED_SUITE_SHA256"
  assert_sha "$LLAMA_SERVER" "$EXPECTED_RUNTIME_SHA256"
}

assert_phase1_packet_hashes() {
  local oracle="$1" oracle_sha="$2"
  assert_sha "$PHASE1_DIR/wave-artifacts.sha256" "$EXPECTED_PHASE1_MANIFEST_SHA256"
  assert_sha "$PHASE1_DIR/phase-summary.json" "$EXPECTED_PHASE1_SUMMARY_SHA256"
  assert_sha "$PHASE1_DIR/wave-diagnostic-completion-status.json" "$EXPECTED_PHASE1_MARKER_SHA256"
  assert_sha "$oracle" "$oracle_sha"
}

assert_outer_fixed_dependencies() {
  assert_core_dependency_hashes
  assert_phase1_packet_hashes "$SELECTOR0_ORACLE" "$EXPECTED_SELECTOR0_ORACLE_SHA256"
  assert_phase1_packet_hashes "$SELECTOR1_ORACLE" "$EXPECTED_SELECTOR1_ORACLE_SHA256"
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
parts = raw[close + 2:].split() if close >= 0 else []
if len(parts) < 20 or not parts[19].isdigit() or int(parts[19]) <= 0:
    raise SystemExit(1)
print(parts[19])
PY
}

process_identity() {
  # Read parent PID and start ticks atomically from one procfs stat snapshot.
  python3 - "$1" <<'PY'
from pathlib import Path
import sys
raw = Path(f"/proc/{int(sys.argv[1])}/stat").read_text()
close = raw.rfind(")")
parts = raw[close + 2:].split() if close >= 0 else []
if (
    len(parts) < 20
    or not parts[1].isdigit()
    or int(parts[1]) <= 0
    or not parts[19].isdigit()
    or int(parts[19]) <= 0
):
    raise SystemExit(1)
print(parts[1], parts[19])
PY
}

bound_pid_running() {
  local pid="$1" expected_ppid="$2" expected_ticks="$3" observed
  [[ "$pid" =~ ^[1-9][0-9]*$ && "$expected_ppid" =~ ^[1-9][0-9]*$ && \
     "$expected_ticks" =~ ^[1-9][0-9]*$ ]] || return 1
  pid_running "$pid" || return 1
  observed="$(process_identity "$pid" 2>/dev/null || true)"
  [[ "$observed" == "$expected_ppid $expected_ticks" ]]
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
    function trim(value) {gsub(/^[[:space:]]+|[[:space:]]+$/, "", value); return value}
    {label=trim($2); value=trim($3)}
    label == "Device ID" {dc++; if (value !~ /^[0-9]+$/) bad=1; else device=value+0}
    label == "GPU Memory Used (MiB)" {
      mc++; if (value !~ /^[0-9]+([.][0-9]+)?$/) bad=1
      else {memory=int(value); if ((value+0) != memory) bad=1}
    }
    END {if (bad || dc != 1 || mc != 1 || device != expected_gpu) exit 1; print memory}
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
  local destination="$1" temporary
  shift
  [[ ! -e "$destination" ]] || return 1
  temporary="$(mktemp "$(dirname "$destination")/.$(basename "$destination").XXXXXX")" || return 1
  if ! jq "$@" > "$temporary"; then rm -f "$temporary"; return 1; fi
  chmod 0444 "$temporary" || { rm -f "$temporary"; return 1; }
  ln "$temporary" "$destination" || { rm -f "$temporary"; return 1; }
  rm -f "$temporary"
}

claim_wave_state() {
  local desired="$1" temporary
  [[ -n "$CURRENT_WAVE_STATE" && ! -e "$CURRENT_WAVE_STATE" ]] || return 1
  temporary="$(mktemp "$(dirname "$CURRENT_WAVE_STATE")/.wave-state.XXXXXX")" || return 1
  printf 'state=%s\n' "$desired" > "$temporary"
  chmod 0444 "$temporary" || { rm -f "$temporary"; return 1; }
  if ln "$temporary" "$CURRENT_WAVE_STATE" 2>/dev/null; then
    rm -f "$temporary"
    return 0
  fi
  rm -f "$temporary"
  return 1
}

wave_failure_present() {
  [[ -e "$CURRENT_WAVE_ABORT" || -e "$CURRENT_WAVE_FAILURE" ]] && return 0
  [[ -f "$CURRENT_WAVE_STATE" ]] && grep -qx 'state=ABORT' "$CURRENT_WAVE_STATE"
}

publish_wave_abort() {
  local wave="$1" gpu="$2" destination temporary state
  destination="$CURRENT_WAVE_ABORT"
  if claim_wave_state ABORT; then
    :
  else
    state="$(awk -F= '$1=="state" {print $2}' "$CURRENT_WAVE_STATE" 2>/dev/null || true)"
    if [[ "$state" == "ABORT" ]]; then return 0; fi
    [[ "$state" == "RELEASE" ]] || return 1
    destination="$CURRENT_WAVE_FAILURE"
  fi
  [[ ! -e "$destination" ]] || return 0
  temporary="$(mktemp "$(dirname "$destination")/.wave-abort.XXXXXX")" || return 1
  printf 'wave=%s\ngpu=%s\n' "$wave" "$gpu" > "$temporary"
  chmod 0444 "$temporary" || { rm -f "$temporary"; return 1; }
  ln "$temporary" "$destination" 2>/dev/null || true
  rm -f "$temporary"
}

publish_wave_release() {
  local wave="$1" temporary
  temporary="$(mktemp "$(dirname "$CURRENT_WAVE_RELEASE")/.wave-release.XXXXXX")" || return 1
  if ! jq -n --argjson wave "$wave" --arg utc "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      '{released:true,phase:"canonical-q8-c2-crossover",wave:$wave,released_utc:$utc}' \
      > "$temporary"; then rm -f "$temporary"; return 1; fi
  chmod 0444 "$temporary" || { rm -f "$temporary"; return 1; }
  if ! claim_wave_state RELEASE; then rm -f "$temporary"; return 1; fi
  if ! ln "$temporary" "$CURRENT_WAVE_RELEASE"; then rm -f "$temporary"; return 1; fi
  rm -f "$temporary"
  wave_failure_present && return 1
  return 0
}

stable_log_size() {
  python3 - "$1" <<'PY'
import os, stat, sys
fd = os.open(sys.argv[1], os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
try:
    value = os.fstat(fd)
    if not stat.S_ISREG(value.st_mode) or value.st_size <= 0:
        raise SystemExit(1)
    os.lseek(fd, value.st_size - 1, os.SEEK_SET)
    if os.read(fd, 1) != b"\n":
        raise SystemExit(1)
    print(value.st_size)
finally:
    os.close(fd)
PY
}

copy_prefix_new() {
  python3 - "$1" "$2" "$3" <<'PY'
import os, stat, sys
from pathlib import Path
source, destination, size = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
value = source.lstat()
if not stat.S_ISREG(value.st_mode) or source.is_symlink() or destination.exists() or size <= 0 or value.st_size < size:
    raise SystemExit(1)
temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
try:
    with source.open("rb") as incoming, os.fdopen(fd, "wb") as outgoing:
        remaining = size
        while remaining:
            block = incoming.read(min(8 * 1024 * 1024, remaining))
            if not block:
                raise SystemExit(1)
            outgoing.write(block)
            remaining -= len(block)
        outgoing.flush()
        os.fsync(outgoing.fileno())
    if temporary.read_bytes()[-1:] != b"\n":
        raise SystemExit(1)
    os.link(temporary, destination)
finally:
    temporary.unlink(missing_ok=True)
PY
}

wait_for_stable_line_boundary() {
  local path="$1" timeout_seconds="$2" deadline first second
  deadline=$((SECONDS + timeout_seconds))
  while (( SECONDS < deadline )); do
    wave_failure_present && return 1
    owned_server_running || return 1
    first="$(stable_log_size "$path" 2>/dev/null || true)"
    if [[ "$first" =~ ^[1-9][0-9]*$ ]]; then
      sleep 0.2
      second="$(stable_log_size "$path" 2>/dev/null || true)"
      if [[ "$second" == "$first" ]]; then printf '%s\n' "$first"; return 0; fi
    fi
    sleep 0.2
  done
  return 1
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

selector_for_wave() {
  local wave="$1" gpu="$2"
  if [[ "$wave" == 1 ]]; then printf '%s\n' "${WAVE1_SELECTORS[$gpu]}"
  else printf '%s\n' "${WAVE2_SELECTORS[$gpu]}"; fi
}

child_main() {
  : "${WAVE:?}" "${GPU_INDEX:?}" "${SCENARIO:?}" "${SELECTOR:?}" "${PORT:?}" \
    "${RUN_DIR:?}" "${MODEL_FD:?}" "${QWEN36_GPU_LEASE_FD:?}" \
    "${QWEN36_PORT_LEASE_FD:?}" "${CURRENT_WAVE_RELEASE:?}" "${CURRENT_WAVE_ABORT:?}" \
    "${CURRENT_WAVE_STATE:?}" "${CURRENT_WAVE_FAILURE:?}" \
    "${CURRENT_WAVE_CHILD_SURVIVOR:?}" "${OUTER_PID:?}" "${OUTER_START_TICKS:?}" \
    "${MODEL_STAT_BASELINE:?}" "${OUTER_RUNTIME_REFERENCE:?}" "${WAVE_INPUT_MANIFEST:?}" \
    "${SESSION_GATE:?}" "${ORACLE:?}" "${ORACLE_SHA256:?}"
  [[ "$PHASE2_LIVE_GATE" == "REVIEWED_AND_FROZEN" ]] || die "child live gate mismatch"
  [[ "$(file_sha256 "$SCRIPT")" == "${EXPECTED_SCRIPT_SHA256:?}" ]] || die "runner changed before child entry"
  local expected_selector self_identity self_ppid self_ticks self_pgid self_sid deadline prefix_size pre_mib loaded_mib
  expected_selector="$(selector_for_wave "$WAVE" "$GPU_INDEX")"
  [[ "$SELECTOR" == "$expected_selector" ]] || die "selector/mapping mismatch"
  [[ "$SCENARIO" == "${SCENARIOS[$GPU_INDEX]}" ]] || die "scenario/mapping mismatch"
  [[ "$PORT" == "$((PORT_BASE + GPU_INDEX))" ]] || die "port/mapping mismatch"
  deadline=$((SECONDS + 30))
  while [[ ! -s "$SESSION_GATE" ]]; do
    (( SECONDS < deadline )) || die "session gate timeout"
    sleep 0.05
  done
  self_identity="$(process_identity $$)"
  read -r self_ppid self_ticks <<< "$self_identity"
  self_pgid="$(ps -o pgid= -p $$ | awk '{print $1}')"
  self_sid="$(ps -o sid= -p $$ | awk '{print $1}')"
  [[ "$self_ppid" == "$OUTER_PID" ]] || die "outer parent PID mismatch"
  [[ "$(process_start_ticks "$self_ppid" 2>/dev/null || true)" == "$OUTER_START_TICKS" ]] \
    || die "outer parent start identity mismatch"
  jq -e --argjson pid "$$" --argjson ppid "$self_ppid" --arg ticks "$self_ticks" \
    --arg parent_ticks "$OUTER_START_TICKS" --argjson pgid "$self_pgid" --argjson sid "$self_sid" \
    '.passed==true and .pid==$pid and .parent_pid==$ppid and .parent_start_ticks==$parent_ticks and .start_ticks==$ticks and .pgid==$pgid and .sid==$sid and .pid==.pgid and .pgid==.sid' \
    "$SESSION_GATE" >/dev/null || die "session identity mismatch"
  # Direct --child entry cannot substitute a freshly baselined dependency set.
  assert_core_dependency_hashes
  assert_phase1_packet_hashes "$ORACLE" "$ORACLE_SHA256"
  [[ ! -e "$RUN_DIR" ]] || die "child output exists"
  mkdir "$RUN_DIR"

  CHILD_STATE_ACTIVE=1
  CHILD_FAILURE_REASON="child exited without a classified cause"
  CHILD_SERVER_PID=""
  CHILD_SERVER_PPID="$$"
  CHILD_SERVER_START_TICKS=""
  CHILD_SERVER_PGID=""
  CHILD_CLEANUP_FORCED=0
  CHILD_CLEANUP_SURVIVOR=0
  CHILD_NORMAL_COMPLETE=0
  owned_server_running() {
    [[ -n "$CHILD_SERVER_PID" && -n "$CHILD_SERVER_PPID" && -n "$CHILD_SERVER_START_TICKS" && -n "$CHILD_SERVER_PGID" ]] || return 1
    bound_pid_running "$CHILD_SERVER_PID" "$CHILD_SERVER_PPID" "$CHILD_SERVER_START_TICKS" || return 1
    [[ "$(ps -o pgid= -p "$CHILD_SERVER_PID" 2>/dev/null | awk '{print $1}')" == "$CHILD_SERVER_PGID" ]]
  }
  publish_abort() {
    publish_wave_abort "$WAVE" "$GPU_INDEX"
  }
  parent_identity_bound() {
    [[ "$self_ppid" == "$OUTER_PID" ]] || return 1
    [[ "$(process_start_ticks "$OUTER_PID" 2>/dev/null || true)" == "$OUTER_START_TICKS" ]]
  }
  publish_child_survivor() {
    local temporary
    [[ ! -e "$CURRENT_WAVE_CHILD_SURVIVOR" ]] || return 0
    temporary="$(mktemp "$(dirname "$CURRENT_WAVE_CHILD_SURVIVOR")/.child-survivor.XXXXXX")" || return 1
    printf 'wave=%s\ngpu=%s\npid=%s\ncleanup_survivor=1\n' \
      "$WAVE" "$GPU_INDEX" "$$" > "$temporary"
    chmod 0444 "$temporary" || { rm -f "$temporary"; return 1; }
    ln "$temporary" "$CURRENT_WAVE_CHILD_SURVIVOR" 2>/dev/null || true
    rm -f "$temporary"
  }
  child_error() {
    local status=$?
    if [[ "$CHILD_FAILURE_REASON" == "child exited without a classified cause" ]]; then
      CHILD_FAILURE_REASON="command failed at line ${BASH_LINENO[0]} with rc=${status}: ${BASH_COMMAND}"
    fi
    return "$status"
  }
  child_failure() {
    local status=$? quiet_deadline stop_deadline
    (( status != 0 )) || status=1
    trap - EXIT ERR INT TERM
    set +e
    rm -f "$RUN_DIR/ready.json"
    publish_abort
    if owned_server_running; then
      { date -u +epoch_s=%s; stat -c 'server_log_size=%s' "$RUN_DIR/server.stdout.log" 2>/dev/null || true; } \
        > "$RUN_DIR/passive-drain-before.env"
      quiet_deadline=$((SECONDS + PASSIVE_DRAIN_S))
      while (( SECONDS < quiet_deadline )) && owned_server_running; do sleep 1; done
      { date -u +epoch_s=%s; stat -c 'server_log_size=%s' "$RUN_DIR/server.stdout.log" 2>/dev/null || true; } \
        > "$RUN_DIR/passive-drain-after.env"
    fi
    if owned_server_running; then
      kill -TERM "$CHILD_SERVER_PID" 2>/dev/null || true
      stop_deadline=$((SECONDS + TERM_GRACE_S))
      while (( SECONDS < stop_deadline )) && owned_server_running; do sleep 1; done
    fi
    if owned_server_running; then
      CHILD_CLEANUP_FORCED=1
      kill -KILL "$CHILD_SERVER_PID" 2>/dev/null || true
      stop_deadline=$((SECONDS + KILL_GRACE_S))
      while (( SECONDS < stop_deadline )) && owned_server_running; do sleep 1; done
    fi
    if owned_server_running; then CHILD_CLEANUP_SURVIVOR=1
    elif [[ -n "$CHILD_SERVER_PID" ]]; then wait "$CHILD_SERVER_PID" 2>/dev/null || true; fi
    if [[ -n "$CHILD_SERVER_PID" ]] && pid_running "$CHILD_SERVER_PID" && ! owned_server_running; then
      # Identity was lost: send no signal and make the lane explicitly invalid.
      CHILD_CLEANUP_SURVIVOR=1
      printf 'pid=%s\nexpected_parent_pid=%s\nexpected_start_ticks=%s\nsignals_sent=0\n' \
        "$CHILD_SERVER_PID" "$CHILD_SERVER_PPID" "$CHILD_SERVER_START_TICKS" \
        > "$RUN_DIR/server-identity-unbound.env"
    fi
    if (( CHILD_CLEANUP_SURVIVOR == 1 )); then
      publish_child_survivor || true
    fi
    {
      echo "status=FAIL"; echo "exit_status=$status"; printf 'failure_reason=%q\n' "$CHILD_FAILURE_REASON"
      echo "wave=$WAVE"; echo "gpu_index=$GPU_INDEX"; echo "scenario=$SCENARIO"; echo "selector=$SELECTOR"
      echo "forced_kill=$CHILD_CLEANUP_FORCED"; echo "cleanup_survivor=$CHILD_CLEANUP_SURVIVOR"
    } > "$RUN_DIR/cleanup-status.env"
    printf 'FAIL\n' > "$RUN_DIR/run-status.txt"
    rm -f "$RUN_DIR/artifacts.sha256" "$RUN_DIR/diagnostic-completion-status.json"
    seal_directory "$RUN_DIR" artifacts.sha256 diagnostic-completion-status.json || true
    exit "$status"
  }
  trap child_failure EXIT
  trap child_error ERR
  trap 'exit 130' INT TERM

  local gpu_lease="/run/user/$(id -u)/qwen36-b70-gpu-leases/gpu${GPU_INDEX}.lock"
  local port_lease="/run/user/$(id -u)/qwen36-b70-port-leases/port${PORT}.lock"
  validate_lease_fd "$QWEN36_GPU_LEASE_FD" "$gpu_lease" || die "invalid inherited GPU lease"
  validate_lease_fd "$QWEN36_PORT_LEASE_FD" "$port_lease" || die "invalid inherited port lease"
  [[ -r "/proc/$$/fd/$MODEL_FD" ]] || die "model FD unreadable"
  capture_model_stat "/proc/$$/fd/$MODEL_FD" "$RUN_DIR/model-stat-prelaunch.json"
  cmp -s "$MODEL_STAT_BASELINE" "$RUN_DIR/model-stat-prelaunch.json" || die "model identity drift"
  sha256sum -c "$WAVE_INPUT_MANIFEST" > "$RUN_DIR/wave-inputs-prelaunch.check.txt"
  parent_identity_bound || die "outer parent identity lost before first probe"
  assert_core_dependency_hashes
  assert_phase1_packet_hashes "$ORACLE" "$ORACLE_SHA256"
  timeout 10 ss -H -ltn "sport = :$PORT" > "$RUN_DIR/port-preflight.txt" 2> "$RUN_DIR/port-preflight.stderr" \
    || die "port preflight failed"
  [[ ! -s "$RUN_DIR/port-preflight.txt" ]] || die "port already has listener"
  wave_failure_present && die "peer aborted before XPU sample"
  sample_gpu "$GPU_INDEX" "$RUN_DIR/xpu-smi-before.txt" || die "preflight XPU sample failed"
  pre_mib="$(parse_gpu_used_mib "$RUN_DIR/xpu-smi-before.txt" "$GPU_INDEX")" || die "preflight XPU parse failed"
  (( pre_mib <= GPU_IDLE_MAX_MIB )) || die "GPU is not idle"
  runtime_report "$RUN_DIR/runtime-reference.json" "$OUTER_RUNTIME_REFERENCE"

  wave_failure_present && die "peer aborted before launch"
  parent_identity_bound || die "outer parent identity lost before server launch"
  assert_core_dependency_hashes
  assert_phase1_packet_hashes "$ORACLE" "$ORACLE_SHA256"
  wave_failure_present && die "peer aborted at server launch boundary"
  QWEN36_MODEL_FD="$MODEL_FD" GPU_INDEX="$GPU_INDEX" PORT="$PORT" MODEL="$MODEL" \
  MODEL_ALIAS="qwen36-27b-q8_0-target-only" LLAMA_SERVER="$LLAMA_SERVER" \
  RUNTIME_MANIFEST="$RUNTIME_MANIFEST" CTX_SIZE=65536 PARALLEL_SLOTS=2 \
  KV_UNIFIED=0 CONT_BATCHING=1 BATCH_SIZE=1024 UBATCH_SIZE=128 \
  N_GPU_LAYERS=99 THREADS=8 HTTP_THREADS=6 POLL=50 LOG_VERBOSITY=4 \
  CACHE_TYPE_K=f16 CACHE_TYPE_V=f16 FLASH_ATTN=on \
  LANE_DNN_ENABLED=0 LANE_OPT_ENABLED=1 LANE_FA_ONEDNN=1 \
  LANE_FA_ONEDNN_MAX_KV=0 LANE_MKL_FA=1 LANE_SYCL_FLASH_ATTN=1 \
  LANE_Q8_0_C2_CANONICAL_MMVQ="$SELECTOR" SLEEP_IDLE_SECONDS=-1 \
  LOG="$RUN_DIR/server.identity.log" SERVER_OUTPUT_LOG="$RUN_DIR/server.stdout.log" OUT_DIR="$RUN_DIR" \
    "$LAUNCHER" > "$RUN_DIR/launcher.stdout.log" 2> "$RUN_DIR/launcher.stderr.log" &
  CHILD_SERVER_PID=$!
  server_identity="$(process_identity "$CHILD_SERVER_PID")"
  read -r server_ppid CHILD_SERVER_START_TICKS <<< "$server_identity"
  [[ "$server_ppid" == "$CHILD_SERVER_PPID" ]] || die "server parent identity mismatch"
  CHILD_SERVER_PGID="$(ps -o pgid= -p "$CHILD_SERVER_PID" | awk '{print $1}')"
  [[ "$CHILD_SERVER_PGID" == "$(ps -o pgid= -p $$ | awk '{print $1}')" ]] || die "server escaped process group"
  printf '%s\n' "$CHILD_SERVER_PID" > "$RUN_DIR/server.pid"

  deadline=$((SECONDS + READINESS_TIMEOUT_S))
  until curl -fsS "http://127.0.0.1:${PORT}/v1/models" > "$RUN_DIR/models.json" 2> "$RUN_DIR/models.err"; do
    wave_failure_present && die "peer aborted during readiness"
    owned_server_running || die "server exited before readiness"
    (( SECONDS < deadline )) || die "server readiness timeout"
    sleep 2
  done
  jq -e '.data|length==1 and .[0].meta.n_ctx==32768 and .[0].meta.ftype=="Q8_0" and .[0].meta.n_params==26895998464' \
    "$RUN_DIR/models.json" >/dev/null || die "model endpoint identity failed"
  python3 "$SERVER_ATTESTER" --server-log "$RUN_DIR/server.stdout.log" \
    --identity-log "$RUN_DIR/server.identity.log" --out "$RUN_DIR/server-attestation.json" \
    --model-size "$EXPECTED_MODEL_SIZE" --runtime-sha256 "$EXPECTED_RUNTIME_SHA256" \
    --minimum-fit-free-mib "$MIN_FIT_FREE_MIB"
  local attestation_sha
  attestation_sha="$(file_sha256 "$RUN_DIR/server-attestation.json")"
  sample_gpu "$GPU_INDEX" "$RUN_DIR/xpu-smi-loaded.txt" || die "loaded XPU sample failed"
  loaded_mib="$(parse_gpu_used_mib "$RUN_DIR/xpu-smi-loaded.txt" "$GPU_INDEX")" || die "loaded XPU parse failed"
  (( loaded_mib - pre_mib >= MIN_LOADED_DELTA_MIB )) || die "loaded VRAM delta too small"
  if [[ "$SELECTOR" == 1 ]]; then
    deadline=$((SECONDS + 30))
    until grep -Eq "$MARKER_PATTERN" "$RUN_DIR/server.stdout.log"; do
      owned_server_running || die "server died awaiting flat first hit"
      (( SECONDS < deadline )) || die "selector-on flat first-hit timeout"
      sleep 1
    done
  fi
  prefix_size="$(wait_for_stable_line_boundary "$RUN_DIR/server.stdout.log" "$PREFIX_STABILITY_TIMEOUT_S")" \
    || die "prerelease log did not stabilize"
  copy_prefix_new "$RUN_DIR/server.stdout.log" "$RUN_DIR/prerelease-prefix.log" "$prefix_size"
  atomic_json "$RUN_DIR/ready.json" -n --argjson wave "$WAVE" --argjson gpu "$GPU_INDEX" \
    --arg scenario "$SCENARIO" --argjson selector "$SELECTOR" --argjson port "$PORT" \
    --argjson pid "$CHILD_SERVER_PID" --arg attestation_sha "$attestation_sha" \
    '{ready:true,wave:$wave,gpu_index:$gpu,scenario:$scenario,selector:$selector,port:$port,server_pid:$pid,server_attestation_sha256:$attestation_sha}'

  deadline=$((SECONDS + READINESS_TIMEOUT_S))
  while [[ ! -f "$CURRENT_WAVE_RELEASE" ]]; do
    wave_failure_present && die "wave aborted before release"
    owned_server_running || die "server died before release"
    (( SECONDS < deadline )) || die "release barrier timeout"
    sleep 1
  done
  jq -e --argjson wave "$WAVE" '.released==true and .phase=="canonical-q8-c2-crossover" and .wave==$wave' \
    "$CURRENT_WAVE_RELEASE" >/dev/null || die "release marker mismatch"
  [[ "$(<"$CURRENT_WAVE_STATE")" == "state=RELEASE" ]] || die "release state mismatch"
  parent_identity_bound || die "outer parent identity lost at capture boundary"
  wave_failure_present && die "wave aborted at capture boundary"

  set +e
  timeout --signal=TERM --kill-after=30 "$REQUEST_TIMEOUT_S" \
    python3 "$ANALYZER" capture --wave "$WAVE" --gpu-index "$GPU_INDEX" \
      --scenario "$SCENARIO" --selector "$SELECTOR" --base-url "http://127.0.0.1:${PORT}" \
      --suite "$SUITE" --suite-sha256 "$EXPECTED_SUITE_SHA256" \
      --prompt-builder "$PROMPT_BUILDER" --common-script "$COMMON_CAPTURE" \
      --capture-helper "$CAPTURE_HELPER" --capture-helper-sha256 "$EXPECTED_CAPTURE_HELPER_SHA256" \
      --matrix-client "$MATRIX_CLIENT" --matrix-client-sha256 "$EXPECTED_MATRIX_SHA256" \
      --server-attestation "$RUN_DIR/server-attestation.json" --server-attestation-sha256 "$attestation_sha" \
      --phase1-dir "$PHASE1_DIR" --phase1-manifest-sha256 "$EXPECTED_PHASE1_MANIFEST_SHA256" \
      --phase1-summary-sha256 "$EXPECTED_PHASE1_SUMMARY_SHA256" \
      --phase1-marker-sha256 "$EXPECTED_PHASE1_MARKER_SHA256" \
      --oracle "$ORACLE" --oracle-sha256 "$ORACLE_SHA256" \
      --model-sha256 "$EXPECTED_MODEL_SHA256" --runtime-sha256 "$EXPECTED_RUNTIME_SHA256" \
      --server-pid "$CHILD_SERVER_PID" --timeout "$REQUEST_TIMEOUT_S" --out "$RUN_DIR/capture.json" \
      > "$RUN_DIR/client.stdout.log" 2> "$RUN_DIR/client.stderr.log"
  local capture_status=$?
  set -e
  if (( capture_status != 0 )); then
    CHILD_FAILURE_REASON="forced-512 crossover capture failed with rc=${capture_status}"
    return "$capture_status"
  fi
  owned_server_running || die "server died during capture"
  prefix_size="$(wait_for_stable_line_boundary "$RUN_DIR/server.stdout.log" "$PREFIX_STABILITY_TIMEOUT_S")" \
    || die "postcapture log did not stabilize"
  copy_prefix_new "$RUN_DIR/server.stdout.log" "$RUN_DIR/postcapture-prefix.log" "$prefix_size"
  cmp -n "$(stat -c %s "$RUN_DIR/prerelease-prefix.log")" "$RUN_DIR/prerelease-prefix.log" \
    "$RUN_DIR/postcapture-prefix.log" || die "prerelease prefix changed"
  sha256sum -c "$WAVE_INPUT_MANIFEST" > "$RUN_DIR/wave-inputs-postcapture.check.txt"

  owned_server_running || die "server identity lost before graceful TERM"
  kill -TERM "$CHILD_SERVER_PID"
  deadline=$((SECONDS + TERM_GRACE_S))
  while (( SECONDS < deadline )) && owned_server_running; do sleep 1; done
  if owned_server_running; then CHILD_CLEANUP_FORCED=1; die "server did not stop gracefully"; fi
  wait "$CHILD_SERVER_PID" 2>/dev/null || true
  timeout 10 ss -H -ltn "sport = :$PORT" > "$RUN_DIR/port-postteardown.txt" 2> "$RUN_DIR/port-postteardown.stderr" \
    || die "post-teardown port query failed"
  [[ ! -s "$RUN_DIR/port-postteardown.txt" ]] || die "port remained open"
  runtime_report "$RUN_DIR/runtime-final.json" "$RUN_DIR/runtime-reference.json"
  python3 "$ANALYZER" attest-lane --wave "$WAVE" --gpu-index "$GPU_INDEX" \
    --scenario "$SCENARIO" --selector "$SELECTOR" --port "$PORT" --server-pid "$CHILD_SERVER_PID" \
    --capture "$RUN_DIR/capture.json" --server-log "$RUN_DIR/server.stdout.log" \
    --identity-log "$RUN_DIR/server.identity.log" --prerelease-prefix "$RUN_DIR/prerelease-prefix.log" \
    --postcapture-prefix "$RUN_DIR/postcapture-prefix.log" --runtime-manifest "$RUNTIME_MANIFEST" \
    --runtime-manifest-sha256 "$EXPECTED_MANIFEST_SHA256" --runtime-reference "$RUN_DIR/runtime-reference.json" \
    --runtime-final "$RUN_DIR/runtime-final.json" --phase1-dir "$PHASE1_DIR" \
    --phase1-manifest-sha256 "$EXPECTED_PHASE1_MANIFEST_SHA256" \
    --phase1-summary-sha256 "$EXPECTED_PHASE1_SUMMARY_SHA256" \
    --phase1-marker-sha256 "$EXPECTED_PHASE1_MARKER_SHA256" \
    --oracle "$ORACLE" --oracle-sha256 "$ORACLE_SHA256" --out "$RUN_DIR/lane-attestation.json"
  jq -e '.passed==true and .performance_promotable==false' "$RUN_DIR/lane-attestation.json" >/dev/null \
    || die "lane attestation failed"
  capture_model_stat "/proc/$$/fd/$MODEL_FD" "$RUN_DIR/model-stat-final.json"
  cmp -s "$MODEL_STAT_BASELINE" "$RUN_DIR/model-stat-final.json" || die "final model stat drift"
  sha256sum -c "$WAVE_INPUT_MANIFEST" > "$RUN_DIR/wave-inputs-postteardown.check.txt"
  printf 'PRE_SEAL_EVIDENCE_VALID\n' > "$RUN_DIR/run-status.txt"
  {
    echo "status=PASS"; echo "wave=$WAVE"; echo "gpu_index=$GPU_INDEX"; echo "scenario=$SCENARIO"
    echo "selector=$SELECTOR"; echo "graceful_server_teardown=1"; echo "forced_kill=0"
    echo "cleanup_survivor=0"; echo "port_closed=1"
  } > "$RUN_DIR/cleanup-status.env"
  seal_directory "$RUN_DIR" artifacts.sha256 diagnostic-completion-status.json || die "lane seal failed"
  CHILD_NORMAL_COMPLETE=1
  CHILD_STATE_ACTIVE=0
  trap - EXIT ERR INT TERM
}

if [[ "$ACTION" == "--child" ]]; then
  [[ $# -eq 1 ]] || die "--child accepts no other arguments"
  child_main
  exit 0
fi
[[ "$ACTION" == "--run-phase2" && $# -eq 1 ]] || die "live execution requires only --run-phase2"

for command_name in awk bash chmod cmp cp curl date df dirname env find flock grep id journalctl jq \
  ln mkdir mktemp pgrep ps python3 readlink setsid sha256sum sort ss stat timeout xargs xpu-smi; do
  command -v "$command_name" >/dev/null 2>&1 || die "required command missing: $command_name"
done
for name in PORT_BASE START_STAGGER_S READINESS_TIMEOUT_S REQUEST_TIMEOUT_S WAVE_TIMEOUT_S \
  TERM_GRACE_S KILL_GRACE_S PASSIVE_DRAIN_S FAILURE_HANDOFF_MARGIN_S \
  MIN_HOST_AVAILABLE_KIB MIN_FAST_FREE_KIB; do require_uint "$name" "${!name}"; done
(( PORT_BASE >= 1024 && PORT_BASE <= 65532 )) || die "PORT_BASE must leave four valid ports"
(( START_STAGGER_S >= 5 && READINESS_TIMEOUT_S >= 600 && REQUEST_TIMEOUT_S >= 900 && WAVE_TIMEOUT_S >= 3600 )) \
  || die "launch/request timeout floor weakened"
(( TERM_GRACE_S >= 60 && KILL_GRACE_S >= 10 && PASSIVE_DRAIN_S >= 60 && FAILURE_HANDOFF_MARGIN_S >= 40 )) \
  || die "cleanup safety floor weakened"
[[ "$RUN_ROOT" == /* && "$RUN_ROOT" != / && ! -e "$RUN_ROOT" ]] || die "RUN_ROOT must be a new non-root absolute path"
[[ -n "$PHASE1_DIR" && "$PHASE1_DIR" == /* && -d "$PHASE1_DIR" ]] || die "PHASE1_DIR must name the fresh sealed Phase-1 packet"
for value in "$EXPECTED_ANALYZER_SHA256" "$EXPECTED_PHASE1_MANIFEST_SHA256" \
  "$EXPECTED_PHASE1_SUMMARY_SHA256" "$EXPECTED_PHASE1_MARKER_SHA256" \
  "$EXPECTED_SELECTOR0_ORACLE_SHA256" "$EXPECTED_SELECTOR1_ORACLE_SHA256"; do
  [[ "$value" =~ ^[0-9a-f]{64}$ ]] || die "live identity remains pending/frozen hash is absent"
done
for path in "$ANALYZER" "$LAUNCHER" "$SERVER_ATTESTER" "$MATRIX_CLIENT" "$CAPTURE_HELPER" \
  "$COMMON_CAPTURE" "$PROMPT_BUILDER" "$RUNTIME_MANIFEST" "$MODEL_MANIFEST" "$SUITE" "$LLAMA_SERVER" "$MODEL" \
  "$PHASE1_DIR/wave-artifacts.sha256" "$PHASE1_DIR/phase-summary.json" \
  "$PHASE1_DIR/wave-diagnostic-completion-status.json"; do
  [[ -f "$path" ]] || die "required file missing: $path"
done
[[ -x "$LLAMA_SERVER" && -f /opt/intel/oneapi/setvars.sh ]] || die "runtime or oneAPI setup unavailable"
assert_sha "$ANALYZER" "$EXPECTED_ANALYZER_SHA256"
assert_sha "$LAUNCHER" "$EXPECTED_LAUNCHER_SHA256"
assert_sha "$SERVER_ATTESTER" "$EXPECTED_SERVER_ATTESTER_SHA256"
assert_sha "$MATRIX_CLIENT" "$EXPECTED_MATRIX_SHA256"
assert_sha "$CAPTURE_HELPER" "$EXPECTED_CAPTURE_HELPER_SHA256"
assert_sha "$COMMON_CAPTURE" "$EXPECTED_COMMON_CAPTURE_SHA256"
assert_sha "$PROMPT_BUILDER" "$EXPECTED_PROMPT_BUILDER_SHA256"
assert_sha "$RUNTIME_MANIFEST" "$EXPECTED_MANIFEST_SHA256"
assert_sha "$MODEL_MANIFEST" "$EXPECTED_MODEL_MANIFEST_SHA256"
assert_sha "$SUITE" "$EXPECTED_SUITE_SHA256"
assert_sha "$LLAMA_SERVER" "$EXPECTED_RUNTIME_SHA256"
assert_sha "$PHASE1_DIR/wave-artifacts.sha256" "$EXPECTED_PHASE1_MANIFEST_SHA256"
assert_sha "$PHASE1_DIR/phase-summary.json" "$EXPECTED_PHASE1_SUMMARY_SHA256"
assert_sha "$PHASE1_DIR/wave-diagnostic-completion-status.json" "$EXPECTED_PHASE1_MARKER_SHA256"
[[ "$(stat -c %s "$MODEL")" == "$EXPECTED_MODEL_SIZE" ]] || die "model size mismatch"
[[ "$(jq -er .sha256 "$MODEL_MANIFEST")" == "$EXPECTED_MODEL_SHA256" ]] || die "model manifest mismatch"
[[ "$(jq -er .llama_server_sha256 "$RUNTIME_MANIFEST")" == "$EXPECTED_RUNTIME_SHA256" ]] || die "runtime manifest mismatch"
[[ "$(jq -er '.origin_shared_objects[]|select(.soname=="libggml-sycl.so.0")|.sha256' "$RUNTIME_MANIFEST")" == "$EXPECTED_SYCL_DSO_SHA256" ]] \
  || die "candidate SYCL DSO mismatch"

SELECTOR0_ORACLE="$(jq -er '.selector_oracles["0"].path' "$PHASE1_DIR/phase-summary.json")"
SELECTOR1_ORACLE="$(jq -er '.selector_oracles["1"].path' "$PHASE1_DIR/phase-summary.json")"
for path in "$SELECTOR0_ORACLE" "$SELECTOR1_ORACLE"; do
  [[ "$path" == /* && -f "$path" && ! -L "$path" ]] || die "Phase-1 oracle path invalid"
  [[ "$(readlink -f "$path")" == "$(readlink -f "$PHASE1_DIR")"/* ]] || die "Phase-1 oracle escapes packet"
done
assert_sha "$SELECTOR0_ORACLE" "$EXPECTED_SELECTOR0_ORACLE_SHA256"
assert_sha "$SELECTOR1_ORACLE" "$EXPECTED_SELECTOR1_ORACLE_SHA256"
assert_outer_fixed_dependencies

unexpected_env=()
while IFS='=' read -r name _; do
  case "$name" in GGML_*|SYCL_*|ZE_*|ZES_*|UR_*|ONEAPI_DEVICE_SELECTOR|LD_PRELOAD|LLAMA_*) unexpected_env+=("$name");; esac
done < <(env)
(( ${#unexpected_env[@]} == 0 )) || die "unexpected accelerator environment: ${unexpected_env[*]}"

mkdir -p "$(dirname "$RUN_ROOT")"
mkdir "$RUN_ROOT"
START_EPOCH="$(date +%s)"
OUTER_COMPLETE=0
OUTER_FORCED_KILL=0
OUTER_SURVIVOR=0
FAILED_TRANSITION_PID=""
CURRENT_WAVE=0
CURRENT_WAVE_DIR=""
CURRENT_WAVE_ABORT=""
CURRENT_WAVE_RELEASE=""
CURRENT_WAVE_STATE=""
CURRENT_WAVE_FAILURE=""
CURRENT_WAVE_CHILD_SURVIVOR=""
OUTER_PID="$$"
OUTER_START_TICKS="$(process_start_ticks "$OUTER_PID")"
printf 'pid=%s\nstart_ticks=%s\n' "$OUTER_PID" "$OUTER_START_TICKS" \
  > "$RUN_ROOT/outer-runner-identity.env"
declare -a CHILD_PIDS=() CHILD_PPIDS=() CHILD_START_TICKS=() CHILD_PGIDS=() CHILD_SIDS=() CHILD_DIRS=()
declare -a GPU_LEASE_FDS=() PORT_LEASE_FDS=()

outer_identity_bound() {
  [[ "$$" == "$OUTER_PID" ]] || return 1
  [[ "$(process_start_ticks "$OUTER_PID" 2>/dev/null || true)" == "$OUTER_START_TICKS" ]]
}

child_survivor_reported() {
  local gpu directory cleanup value
  [[ -n "$CURRENT_WAVE_CHILD_SURVIVOR" && -e "$CURRENT_WAVE_CHILD_SURVIVOR" ]] && return 0
  [[ -n "$CURRENT_WAVE_DIR" && -d "$CURRENT_WAVE_DIR" ]] || return 1
  for gpu in 0 1 2 3; do
    directory="${CHILD_DIRS[$gpu]:-}"
    [[ -n "$directory" && -d "$directory" ]] || continue
    cleanup="$directory/cleanup-status.env"
    [[ -f "$cleanup" && ! -L "$cleanup" ]] || return 0
    value="$(awk -F= '$1=="cleanup_survivor" {count++; value=$2} END {if (count==1) print value}' "$cleanup" 2>/dev/null || true)"
    [[ "$value" == 0 || "$value" == 1 ]] || return 0
    [[ "$value" == 1 ]] && return 0
  done
  return 1
}

recorded_session_alive() {
  local gpu="$1" pid ppid ticks pgid sid table rc
  pid="${CHILD_PIDS[$gpu]:-}"
  ppid="${CHILD_PPIDS[$gpu]:-}"
  ticks="${CHILD_START_TICKS[$gpu]:-}"
  pgid="${CHILD_PGIDS[$gpu]:-}"
  sid="${CHILD_SIDS[$gpu]:-}"
  [[ -n "$pid" && -n "$ppid" && -n "$ticks" && -n "$pgid" && -n "$sid" && "$pid" == "$pgid" && "$pgid" == "$sid" ]] || return 1
  bound_pid_running "$pid" "$ppid" "$ticks" || return 1
  [[ "$(ps -o pgid=,sid= -p "$pid" 2>/dev/null | awk '{print $1, $2}')" == "$pgid $sid" ]] || return 1
  if ! table="$(ps -eo sid=,stat= 2>/dev/null)"; then return 0; fi
  if printf '%s\n' "$table" | awk -v sid="$sid" '$1==sid && $2 !~ /^Z/ {found=1} END{exit(found?0:1)}'; then
    return 0
  else
    rc=$?
  fi
  (( rc == 1 )) && return 1
  return 0
}

session_members_present() {
  local gpu="$1" sid table rc
  sid="${CHILD_SIDS[$gpu]:-}"
  [[ "$sid" =~ ^[1-9][0-9]*$ ]] || return 1
  if ! table="$(ps -eo sid=,stat= 2>/dev/null)"; then return 0; fi
  if printf '%s\n' "$table" | awk -v sid="$sid" '$1==sid && $2 !~ /^Z/ {found=1} END{exit(found?0:1)}'; then
    return 0
  else
    rc=$?
  fi
  (( rc == 1 )) && return 1
  return 0
}

capture_recorded_members() {
  local output="$1" gpu table
  : > "$output"
  table="$(ps -eo pid=,ppid=,pgid=,sid=,stat=,lstart=,args=)" || return 1
  for gpu in 0 1 2 3; do
    [[ -n "${CHILD_SIDS[$gpu]:-}" ]] || continue
    printf '%s\n' "$table" | awk -v gpu="$gpu" -v sid="${CHILD_SIDS[$gpu]}" \
      '$4==sid && $5 !~ /^Z/ {print "gpu=" gpu, $0}' >> "$output"
  done
}

signal_session() {
  local gpu="$1" signal="$2" pid ppid ticks pgid sid
  pid="${CHILD_PIDS[$gpu]:-}"
  ppid="${CHILD_PPIDS[$gpu]:-}"
  ticks="${CHILD_START_TICKS[$gpu]:-}"
  pgid="${CHILD_PGIDS[$gpu]:-}"
  sid="${CHILD_SIDS[$gpu]:-}"
  [[ "$pid" =~ ^[1-9][0-9]*$ && "$pgid" == "$pid" && "$sid" == "$pid" ]] || return 1
  bound_pid_running "$pid" "$ppid" "$ticks" || return 1
  [[ "$(ps -o pgid=,sid= -p "$pid" 2>/dev/null | awk '{print $1, $2}')" == "$pgid $sid" ]] || return 1
  # Signal only the atomically rebound session-leader process group.  Never
  # signal a nonleader PGID copied from a stale session-wide process snapshot.
  bound_pid_running "$pid" "$ppid" "$ticks" || return 1
  kill "-$signal" -- "-$pgid" 2>/dev/null || true
}

capture_transition_lane_processes() {
  local run_dir="$1" output="$2"
  python3 - "$run_dir" > "$output" <<'PY'
import os
from pathlib import Path
import sys

needle = f"RUN_DIR={Path(sys.argv[1]).resolve()}".encode()
rows = []
for proc in Path("/proc").iterdir():
    if not proc.name.isdigit():
        continue
    try:
        environ = (proc / "environ").read_bytes().split(b"\0")
        raw = (proc / "stat").read_text()
        close = raw.rfind(")")
        fields = raw[close + 2 :].split()
        state, ppid, start_ticks = fields[0], int(fields[1]), int(fields[19])
        if needle not in environ or state == "Z":
            continue
        pid = int(proc.name)
        rows.append((pid, ppid, os.getpgid(pid), os.getsid(pid), start_ticks, state))
    except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError, OSError):
        continue
for row in sorted(rows):
    print("pid=%d\tppid=%d\tpgid=%d\tsid=%d\tstart_ticks=%d\tstate=%s" % row)
PY
}

wait_failed_transition_quiet() {
  local pid="$1" run_dir="$2" output="$3" deadline=$((SECONDS + UNBOUND_TRANSITION_WAIT_S))
  while (( SECONDS < deadline )); do
    capture_transition_lane_processes "$run_dir" "$output" || return 1
    if [[ ! -s "$output" ]] && ! pid_running "$pid"; then
      wait "$pid" 2>/dev/null || true
      return 0
    fi
    sleep 1
  done
  capture_transition_lane_processes "$run_dir" "$output" || return 1
  [[ ! -s "$output" ]] && ! pid_running "$pid" || return 1
  wait "$pid" 2>/dev/null || true
  return 0
}

terminate_current_wave() {
  local gpu any deadline quiet_deadline
  [[ -n "$CURRENT_WAVE_DIR" && -d "$CURRENT_WAVE_DIR" ]] || return 0
  publish_wave_abort "$CURRENT_WAVE" outer || true
  capture_recorded_members "$CURRENT_WAVE_DIR/failure-drain-members-before.txt" || true
  quiet_deadline=$((SECONDS + PASSIVE_DRAIN_S + FAILURE_HANDOFF_MARGIN_S))
  while (( SECONDS < quiet_deadline )); do
    any=0
    for gpu in 0 1 2 3; do
      if recorded_session_alive "$gpu" || session_members_present "$gpu"; then any=1; fi
    done
    (( any == 0 )) && break; sleep 1
  done
  capture_recorded_members "$CURRENT_WAVE_DIR/failure-drain-members-after.txt" || true
  for gpu in 0 1 2 3; do recorded_session_alive "$gpu" && signal_session "$gpu" TERM || true; done
  deadline=$((SECONDS + TERM_GRACE_S))
  while (( SECONDS < deadline )); do
    any=0
    for gpu in 0 1 2 3; do
      if recorded_session_alive "$gpu" || session_members_present "$gpu"; then any=1; fi
    done
    (( any == 0 )) && break; sleep 1
  done
  for gpu in 0 1 2 3; do
    if recorded_session_alive "$gpu"; then OUTER_FORCED_KILL=1; signal_session "$gpu" KILL || true; fi
  done
  deadline=$((SECONDS + KILL_GRACE_S))
  while (( SECONDS < deadline )); do
    any=0
    for gpu in 0 1 2 3; do
      if recorded_session_alive "$gpu" || session_members_present "$gpu"; then any=1; fi
    done
    (( any == 0 )) && break; sleep 1
  done
  for gpu in 0 1 2 3; do
    if recorded_session_alive "$gpu"; then OUTER_SURVIVOR=1
    elif session_members_present "$gpu"; then
      OUTER_SURVIVOR=1
      printf 'gpu=%s\nsid=%s\nsignals_sent_after_binding_loss=0\n' \
        "$gpu" "${CHILD_SIDS[$gpu]:-}" >> "$CURRENT_WAVE_DIR/unbound-session-survivors.env"
    elif [[ -n "${CHILD_PIDS[$gpu]:-}" ]]; then wait "${CHILD_PIDS[$gpu]}" 2>/dev/null || true; fi
  done
  if child_survivor_reported; then OUTER_SURVIVOR=1; fi
}

phase_passive_scan() {
  local wave_dir="$1" prefix="$2" fault=0 rc gpu
  capture_recorded_members "$wave_dir/${prefix}-group-members.txt" || fault=1
  [[ ! -s "$wave_dir/${prefix}-group-members.txt" ]] || fault=1
  : > "$wave_dir/${prefix}-lane-listeners.txt"
  for gpu in 0 1 2 3; do
    timeout 10 ss -H -ltn "sport = :$((PORT_BASE + gpu))" >> "$wave_dir/${prefix}-lane-listeners.txt" \
      2>> "$wave_dir/${prefix}-lane-listeners.stderr" || fault=1
  done
  [[ ! -s "$wave_dir/${prefix}-lane-listeners.txt" ]] || fault=1
  if pgrep -af '[l]lama-server|[c]anonical-q8-c2-crossover-study.py|[c]apture-simultaneous-c2.py' \
      > "$wave_dir/${prefix}-processes.txt" 2> "$wave_dir/${prefix}-processes.stderr"; then fault=1
  else rc=$?; (( rc == 1 )) || fault=1; fi
  mapfile -d '' logs < <(find "$wave_dir" -type f \( -name '*.log' -o -name '*.stderr' \) -print0)
  if (( ${#logs[@]} == 0 )); then fault=1; : > "$wave_dir/${prefix}-log-error-scan.txt"
  elif grep -EHi 'UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST|out of memory|segmentation fault|core dumped|Aborted|Timedout job' \
      "${logs[@]}" > "$wave_dir/${prefix}-log-error-scan.txt" 2> "$wave_dir/${prefix}-log-error-scan.stderr"; then fault=1
  else rc=$?; (( rc == 1 )) || fault=1; fi
  journalctl -k --since "@$START_EPOCH" --no-pager > "$wave_dir/${prefix}-kernel-journal.txt" \
    2> "$wave_dir/${prefix}-kernel-journal.stderr" || fault=1
  if grep -Ei 'xe.*(reset|wedg|fault|hang|timedout|device lost)|GuC.*reset|Fault response|VM.*fault|PCIe.*AER|UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST' \
      "$wave_dir/${prefix}-kernel-journal.txt" > "$wave_dir/${prefix}-device-error-scan.txt" \
      2> "$wave_dir/${prefix}-device-error-scan.stderr"; then fault=1
  else rc=$?; (( rc == 1 )) || fault=1; fi
  printf 'passive_fault_detected=%s\n' "$fault" > "$wave_dir/${prefix}-passive-status.env"
  (( fault == 0 ))
}

failure_passive_scan() {
  local root="$1" prefix="$2" require_quiet="$3" query_failed=0 device_fault=0
  local quiet_fault=0 process_present=0 rc gpu log_list
  if ! capture_recorded_members "$root/${prefix}-group-members.txt"; then query_failed=1; fi
  if (( require_quiet == 1 )) && [[ -s "$root/${prefix}-group-members.txt" ]]; then quiet_fault=1; fi
  if (( require_quiet == 1 && OUTER_SURVIVOR != 0 )); then quiet_fault=1; fi
  : > "$root/${prefix}-unbound-transition-child.txt"
  if [[ -n "$FAILED_TRANSITION_PID" ]] && pid_running "$FAILED_TRANSITION_PID"; then
    if ! ps -o pid=,ppid=,pgid=,sid=,stat=,lstart=,args= -p "$FAILED_TRANSITION_PID" \
        > "$root/${prefix}-unbound-transition-child.txt" \
        2> "$root/${prefix}-unbound-transition-child.stderr"; then
      query_failed=1
    fi
    (( require_quiet == 0 )) || quiet_fault=1
  else
    : > "$root/${prefix}-unbound-transition-child.stderr"
  fi
  : > "$root/${prefix}-lane-listeners.txt"
  : > "$root/${prefix}-lane-listeners.stderr"
  for gpu in 0 1 2 3; do
    if ! timeout 10 ss -H -ltn "sport = :$((PORT_BASE + gpu))" \
        >> "$root/${prefix}-lane-listeners.txt" \
        2>> "$root/${prefix}-lane-listeners.stderr"; then
      query_failed=1
    fi
  done
  if (( require_quiet == 1 )) && [[ -s "$root/${prefix}-lane-listeners.txt" ]]; then quiet_fault=1; fi
  if pgrep -af '[l]lama-server|[c]anonical-q8-c2-crossover-study.py|[c]apture-simultaneous-c2.py|[r]un-canonical-q8-c2-crossover-four-gpu-wave.sh' \
      > "$root/${prefix}-process-candidates.txt" 2> "$root/${prefix}-processes.stderr"; then
    if ! awk -v outer="$$" '$1 != outer' "$root/${prefix}-process-candidates.txt" \
        > "$root/${prefix}-processes.txt"; then query_failed=1; fi
    [[ ! -s "$root/${prefix}-processes.txt" ]] || process_present=1
  else
    rc=$?
    : > "$root/${prefix}-processes.txt"
    (( rc == 1 )) || query_failed=1
  fi
  if (( require_quiet == 1 && process_present == 1 )); then quiet_fault=1; fi
  log_list="$root/${prefix}-log-files.nul"
  if ! find "$root" -type f \( -name '*.log' -o -name '*.stderr' \) -print0 \
      > "$log_list" 2> "$root/${prefix}-log-files.stderr"; then
    query_failed=1
  fi
  mapfile -d '' logs < "$log_list"
  : > "$root/${prefix}-device-log-scan.txt"
  : > "$root/${prefix}-device-log-scan.stderr"
  if (( ${#logs[@]} > 0 )); then
    if grep -EHi 'UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST|xe.*(reset|wedg|fault|hang|timedout|device lost)|GuC.*reset|Fault response|VM.*fault|PCIe.*AER' \
        "${logs[@]}" > "$root/${prefix}-device-log-scan.txt" \
        2> "$root/${prefix}-device-log-scan.stderr"; then
      device_fault=1
    else
      rc=$?
      (( rc == 1 )) || query_failed=1
    fi
  fi
  if ! journalctl -k --since "@$START_EPOCH" --no-pager \
      > "$root/${prefix}-kernel-journal.txt" \
      2> "$root/${prefix}-kernel-journal.stderr"; then
    query_failed=1
  fi
  : > "$root/${prefix}-device-journal-scan.txt"
  : > "$root/${prefix}-device-journal-scan.stderr"
  if grep -Ei 'xe.*(reset|wedg|fault|hang|timedout|device lost)|GuC.*reset|Fault response|VM.*fault|PCIe.*AER|UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST' \
      "$root/${prefix}-kernel-journal.txt" > "$root/${prefix}-device-journal-scan.txt" \
      2> "$root/${prefix}-device-journal-scan.stderr"; then
    device_fault=1
  else
    rc=$?
    (( rc == 1 )) || query_failed=1
  fi
  {
    echo "query_failed=$query_failed"
    echo "device_fault_detected=$device_fault"
    echo "quiet_state_required=$require_quiet"
    echo "quiet_state_failed=$quiet_fault"
    echo "expected_abort_text_is_device_fault=0"
    echo "active_xpu_probe_performed=0"
  } > "$root/${prefix}-passive-status.env"
  (( query_failed == 0 && device_fault == 0 && quiet_fault == 0 ))
}

outer_failure() {
  local status=$? failure_manifest_sha predrain_rc postcleanup_rc
  local pre_query pre_device post_query post_device post_quiet
  trap - EXIT INT TERM
  set +e
  if failure_passive_scan "$RUN_ROOT" failure-predrain 0; then predrain_rc=0; else predrain_rc=1; fi
  terminate_current_wave
  if failure_passive_scan "$RUN_ROOT" failure-postcleanup 1; then postcleanup_rc=0; else postcleanup_rc=1; fi
  if child_survivor_reported; then OUTER_SURVIVOR=1; fi
  pre_query="$(awk -F= '$1=="query_failed" {print $2}' "$RUN_ROOT/failure-predrain-passive-status.env")"
  pre_device="$(awk -F= '$1=="device_fault_detected" {print $2}' "$RUN_ROOT/failure-predrain-passive-status.env")"
  post_query="$(awk -F= '$1=="query_failed" {print $2}' "$RUN_ROOT/failure-postcleanup-passive-status.env")"
  post_device="$(awk -F= '$1=="device_fault_detected" {print $2}' "$RUN_ROOT/failure-postcleanup-passive-status.env")"
  post_quiet="$(awk -F= '$1=="quiet_state_failed" {print $2}' "$RUN_ROOT/failure-postcleanup-passive-status.env")"
  pre_query="${pre_query:-1}"; pre_device="${pre_device:-1}"
  post_query="${post_query:-1}"; post_device="${post_device:-1}"; post_quiet="${post_quiet:-1}"
  {
    echo "status=FAIL"; echo "exit_status=$status"; echo "current_wave=$CURRENT_WAVE"
    echo "forced_kill=$OUTER_FORCED_KILL"; echo "cleanup_survivor=$OUTER_SURVIVOR"
    echo "body_complete=$OUTER_COMPLETE"; echo "failure_predrain_passive_rc=$predrain_rc"
    echo "failure_postcleanup_passive_rc=$postcleanup_rc"
    echo "failure_predrain_query_failed=$pre_query"; echo "failure_predrain_device_fault=$pre_device"
    echo "failure_postcleanup_query_failed=$post_query"; echo "failure_postcleanup_device_fault=$post_device"
    echo "failure_postcleanup_quiet_state_failed=$post_quiet"; echo "active_xpu_probe_after_failure=0"
  } > "$RUN_ROOT/run-root-cleanup-status.env"
  printf 'FAIL\n' > "$RUN_ROOT/run-root-status.txt"
  rm -f "$RUN_ROOT/run-root-artifacts.sha256" "$RUN_ROOT/run-root-diagnostic-completion-status.json"
  if (( OUTER_SURVIVOR == 0 && post_query == 0 && post_quiet == 0 )) && \
      seal_directory "$RUN_ROOT" run-root-artifacts.sha256 run-root-diagnostic-completion-status.json; then
    failure_manifest_sha="$(file_sha256 "$RUN_ROOT/run-root-artifacts.sha256")"
    atomic_json "$RUN_ROOT/run-root-diagnostic-completion-status.json" -n \
      --arg manifest_sha "$failure_manifest_sha" --argjson status "$status" \
      --argjson predrain_rc "$predrain_rc" --argjson postcleanup_rc "$postcleanup_rc" \
      --argjson pre_query "$pre_query" --argjson pre_device "$pre_device" \
      --argjson post_query "$post_query" --argjson post_device "$post_device" --argjson post_quiet "$post_quiet" \
      '{schema_version:1,phase:"canonical-q8-c2-two-wave-selector-crossover",status:"FAIL",evidence_valid:false,evidence_class:"diagnostic-only-failure",performance_promotable:false,active_xpu_probe_after_failure:false,original_status:$status,failure_passive:{predrain_rc:$predrain_rc,postcleanup_rc:$postcleanup_rc,predrain_query_failed:($pre_query==1),predrain_device_fault:($pre_device==1),postcleanup_query_failed:($post_query==1),postcleanup_device_fault:($post_device==1),postcleanup_quiet_state_failed:($post_quiet==1),expected_abort_text_is_device_fault:false},artifact_manifest:"run-root-artifacts.sha256",artifact_manifest_sha256:$manifest_sha}' || true
  else
    printf 'detached_seal_withheld=1\ncleanup_survivor=%s\npostcleanup_query_failed=%s\npostcleanup_quiet_state_failed=%s\n' \
      "$OUTER_SURVIVOR" "$post_query" "$post_quiet" \
      > "$RUN_ROOT/run-root-detached-seal-withheld.env"
  fi
  printf '%s\n' "$RUN_ROOT"
  (( status != 0 )) || status=1
  exit "$status"
}
trap outer_failure EXIT
trap 'exit 130' INT TERM

exec 9>"/run/user/$(id -u)/qwen36-canonical-q8-c2-crossover-four-gpu.lock"
flock -n 9 || die "another canonical c2 crossover owns the host lock"
GPU_LEASE_DIR="/run/user/$(id -u)/qwen36-b70-gpu-leases"
PORT_LEASE_DIR="/run/user/$(id -u)/qwen36-b70-port-leases"
mkdir -p "$GPU_LEASE_DIR" "$PORT_LEASE_DIR"
for gpu in 0 1 2 3; do
  exec {lease_fd}>"$GPU_LEASE_DIR/gpu${gpu}.lock"; flock -n "$lease_fd" || die "GPU $gpu is leased"; GPU_LEASE_FDS[$gpu]="$lease_fd"
  port=$((PORT_BASE + gpu)); exec {port_fd}>"$PORT_LEASE_DIR/port${port}.lock"; flock -n "$port_fd" || die "port $port is leased"; PORT_LEASE_FDS[$gpu]="$port_fd"
done
exec {MODEL_FD}<"$MODEL"
flock -s -n "$MODEL_FD" || die "model lock unavailable"
[[ "$MODEL" -ef "/proc/$$/fd/$MODEL_FD" ]] || die "model FD/path mismatch"
capture_model_stat "/proc/$$/fd/$MODEL_FD" "$RUN_ROOT/model-stat-before-hash.json"
printf '%s  %s\n' "$EXPECTED_MODEL_SHA256" "/proc/$$/fd/$MODEL_FD" | sha256sum -c - > "$RUN_ROOT/model-sha256-initial.check.txt"
capture_model_stat "/proc/$$/fd/$MODEL_FD" "$RUN_ROOT/model-stat-after-hash.json"
cmp -s "$RUN_ROOT/model-stat-before-hash.json" "$RUN_ROOT/model-stat-after-hash.json" || die "model changed during hash"
cp --no-clobber "$RUN_ROOT/model-stat-after-hash.json" "$RUN_ROOT/model-stat-baseline.json"

set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null
set -u
runtime_report "$RUN_ROOT/runtime-initial.json"

available_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
fast_free_kib="$(df -Pk /mnt/fast-ai | awk 'NR==2 {print $4}')"
(( available_kib >= MIN_HOST_AVAILABLE_KIB )) || die "host memory below four-server floor"
(( fast_free_kib >= MIN_FAST_FREE_KIB )) || die "artifact storage below floor"
if pgrep -af '[l]lama-server|[c]anonical-q8-c2-crossover-study.py|[c]apture-simultaneous-c2.py|[r]un-c2-validation.sh' \
    > "$RUN_ROOT/preflight-processes.txt" 2> "$RUN_ROOT/preflight-processes.stderr"; then die "inference or validation already active"
else rc=$?; (( rc == 1 )) || die "preflight process query failed"; fi
timeout 20 xpu-smi discovery -j > "$RUN_ROOT/xpu-smi-discovery.json"
jq -e '[.device_list[]|select(.device_function_type=="physical" and (.device_name|contains("Arc(TM) Pro B70")))] as $d | ($d|length)==4 and ([$d[].device_id]|sort)==[0,1,2,3] and ([$d[].pci_bdf_address]|unique|length)==4 and ([$d[].uuid]|unique|length)==4' \
  "$RUN_ROOT/xpu-smi-discovery.json" >/dev/null || die "four distinct B70 devices not found"
for gpu in 0 1 2 3; do
  sample_gpu "$gpu" "$RUN_ROOT/xpu-smi-preflight-gpu${gpu}.txt"
  used="$(parse_gpu_used_mib "$RUN_ROOT/xpu-smi-preflight-gpu${gpu}.txt" "$gpu")" || die "preflight XPU parse failed"
  (( used <= GPU_IDLE_MAX_MIB )) || die "GPU $gpu is not idle"
  timeout 10 ss -H -ltn "sport = :$((PORT_BASE + gpu))" > "$RUN_ROOT/port-preflight-gpu${gpu}.txt" \
    2> "$RUN_ROOT/port-preflight-gpu${gpu}.stderr" || die "port preflight query failed"
  [[ ! -s "$RUN_ROOT/port-preflight-gpu${gpu}.txt" ]] || die "lane port already in use"
done

mkdir "$RUN_ROOT/phase1-handoff"
for name in wave-artifacts.sha256 phase-summary.json wave-diagnostic-completion-status.json; do
  cp --no-clobber "$PHASE1_DIR/$name" "$RUN_ROOT/phase1-handoff/$name"
  chmod 0444 "$RUN_ROOT/phase1-handoff/$name"
done
cp --no-clobber "$SELECTOR0_ORACLE" "$RUN_ROOT/phase1-handoff/selector0-oracle.json"
cp --no-clobber "$SELECTOR1_ORACLE" "$RUN_ROOT/phase1-handoff/selector1-oracle.json"
chmod 0444 "$RUN_ROOT/phase1-handoff/selector0-oracle.json" "$RUN_ROOT/phase1-handoff/selector1-oracle.json"
python3 "$ANALYZER" attest-phase1 --phase1-dir "$PHASE1_DIR" \
  --phase1-manifest-sha256 "$EXPECTED_PHASE1_MANIFEST_SHA256" \
  --phase1-summary-sha256 "$EXPECTED_PHASE1_SUMMARY_SHA256" --phase1-marker-sha256 "$EXPECTED_PHASE1_MARKER_SHA256" \
  --selector0-oracle "$SELECTOR0_ORACLE" --selector0-oracle-sha256 "$EXPECTED_SELECTOR0_ORACLE_SHA256" \
  --selector1-oracle "$SELECTOR1_ORACLE" --selector1-oracle-sha256 "$EXPECTED_SELECTOR1_ORACLE_SHA256" \
  --out "$RUN_ROOT/phase1-handoff/attestation.json"

assert_outer_fixed_dependencies
SCRIPT_SHA256="$(file_sha256 "$SCRIPT")"
sha256sum "$SCRIPT" "$ANALYZER" "$LAUNCHER" "$SERVER_ATTESTER" "$MATRIX_CLIENT" \
  "$CAPTURE_HELPER" "$COMMON_CAPTURE" "$PROMPT_BUILDER" "$RUNTIME_MANIFEST" "$MODEL_MANIFEST" "$SUITE" \
  "$PHASE1_DIR/wave-artifacts.sha256" "$PHASE1_DIR/phase-summary.json" \
  "$PHASE1_DIR/wave-diagnostic-completion-status.json" "$SELECTOR0_ORACLE" "$SELECTOR1_ORACLE" \
  > "$RUN_ROOT/wave-inputs.sha256"
WAVE_INPUT_MANIFEST="$RUN_ROOT/wave-inputs.sha256"
assert_outer_fixed_dependencies
sha256sum -c "$WAVE_INPUT_MANIFEST" > "$RUN_ROOT/wave-inputs-initial.check.txt"
MARKER_PATTERN='SYCL_Q8_0_C2_CANONICAL_MMVQ first-hit: layout=flat '

run_wave() {
  local wave="$1" wave_dir gpu selector scenario port run_dir session_gate
  local launch_pid launch_identity launch_ppid launch_ticks launch_pgid launch_sid transition_deadline
  local transition_signals_sent transition_process_evidence
  local deadline all_ready any available_loaded_kib prior oracle oracle_sha
  local all_cards_idle used manifest_sha capture_sha attestation_sha cleanup_sha server_pid health_sha cleanup_global_sha
  wave_dir="$RUN_ROOT/wave${wave}"
  outer_identity_bound || die "outer runner identity lost before wave $wave"
  CURRENT_WAVE="$wave"
  CURRENT_WAVE_DIR="$wave_dir"
  CURRENT_WAVE_ABORT="$wave_dir/abort"
  CURRENT_WAVE_RELEASE="$wave_dir/release.json"
  CURRENT_WAVE_STATE="$wave_dir/wave-state.env"
  CURRENT_WAVE_FAILURE="$wave_dir/postrelease-failure.env"
  CURRENT_WAVE_CHILD_SURVIVOR="$wave_dir/child-survivor.env"
  FAILED_TRANSITION_PID=""
  CHILD_PIDS=(); CHILD_PPIDS=(); CHILD_START_TICKS=(); CHILD_PGIDS=(); CHILD_SIDS=(); CHILD_DIRS=()
  mkdir "$wave_dir"
  for gpu in 0 1 2 3; do
    wave_failure_present && die "prior lane aborted"
    outer_identity_bound || die "outer runner identity lost during launch stagger"
    for ((prior=0; prior<gpu; prior++)); do
      recorded_session_alive "$prior" || die "prior child $prior lost its atomic session binding during stagger"
    done
    selector="$(selector_for_wave "$wave" "$gpu")"; scenario="${SCENARIOS[$gpu]}"; port=$((PORT_BASE + gpu))
    run_dir="$wave_dir/gpu${gpu}-${scenario}-selector${selector}"; session_gate="$wave_dir/gpu${gpu}-session-gate.json"
    CHILD_DIRS[$gpu]="$run_dir"
    oracle="$SELECTOR0_ORACLE"; oracle_sha="$EXPECTED_SELECTOR0_ORACLE_SHA256"
    if [[ "$selector" == 1 ]]; then oracle="$SELECTOR1_ORACLE"; oracle_sha="$EXPECTED_SELECTOR1_ORACLE_SHA256"; fi
    setsid --wait /usr/bin/env -i HOME=/home/steve USER=steve LOGNAME=steve \
      PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin LANG=C.utf8 LC_ALL=C.utf8 \
      XDG_RUNTIME_DIR="/run/user/$(id -u)" PHASE2_LIVE_GATE=REVIEWED_AND_FROZEN \
      PORT_BASE="$PORT_BASE" WAVE="$wave" GPU_INDEX="$gpu" SCENARIO="$scenario" SELECTOR="$selector" \
      PORT="$port" RUN_DIR="$run_dir" MODEL_FD="$MODEL_FD" QWEN36_MODEL_FD="$MODEL_FD" \
      QWEN36_GPU_LEASE_FD="${GPU_LEASE_FDS[$gpu]}" QWEN36_PORT_LEASE_FD="${PORT_LEASE_FDS[$gpu]}" \
      CURRENT_WAVE_RELEASE="$CURRENT_WAVE_RELEASE" CURRENT_WAVE_ABORT="$CURRENT_WAVE_ABORT" \
      CURRENT_WAVE_STATE="$CURRENT_WAVE_STATE" CURRENT_WAVE_FAILURE="$CURRENT_WAVE_FAILURE" \
      CURRENT_WAVE_CHILD_SURVIVOR="$CURRENT_WAVE_CHILD_SURVIVOR" \
      OUTER_PID="$OUTER_PID" OUTER_START_TICKS="$OUTER_START_TICKS" SESSION_GATE="$session_gate" \
      MODEL_STAT_BASELINE="$RUN_ROOT/model-stat-baseline.json" OUTER_RUNTIME_REFERENCE="$RUN_ROOT/runtime-initial.json" \
      WAVE_INPUT_MANIFEST="$WAVE_INPUT_MANIFEST" EXPECTED_SCRIPT_SHA256="$SCRIPT_SHA256" \
      PHASE1_DIR="$PHASE1_DIR" EXPECTED_PHASE1_MANIFEST_SHA256="$EXPECTED_PHASE1_MANIFEST_SHA256" \
      EXPECTED_PHASE1_SUMMARY_SHA256="$EXPECTED_PHASE1_SUMMARY_SHA256" \
      EXPECTED_PHASE1_MARKER_SHA256="$EXPECTED_PHASE1_MARKER_SHA256" \
      EXPECTED_SELECTOR0_ORACLE_SHA256="$EXPECTED_SELECTOR0_ORACLE_SHA256" \
      EXPECTED_SELECTOR1_ORACLE_SHA256="$EXPECTED_SELECTOR1_ORACLE_SHA256" \
      ORACLE="$oracle" ORACLE_SHA256="$oracle_sha" READINESS_TIMEOUT_S="$READINESS_TIMEOUT_S" \
      REQUEST_TIMEOUT_S="$REQUEST_TIMEOUT_S" TERM_GRACE_S="$TERM_GRACE_S" KILL_GRACE_S="$KILL_GRACE_S" \
      PASSIVE_DRAIN_S="$PASSIVE_DRAIN_S" MARKER_PATTERN="$MARKER_PATTERN" \
      /usr/bin/bash "$SCRIPT" --child > "$wave_dir/gpu${gpu}-runner.log" 2>&1 &
    launch_pid=$!
    transition_deadline=$((SECONDS + 10))
    launch_identity=""; launch_ppid=""; launch_ticks=""; launch_pgid=""; launch_sid=""
    while (( SECONDS < transition_deadline )); do
      pid_running "$launch_pid" || break
      launch_identity="$(process_identity "$launch_pid" 2>/dev/null || true)"
      read -r launch_ppid launch_ticks <<< "$launch_identity"
      [[ "$launch_ppid" == "$$" && "$launch_ticks" =~ ^[1-9][0-9]*$ ]] && break
      launch_ppid=""; launch_ticks=""
      sleep 0.05
    done
    while bound_pid_running "$launch_pid" "$launch_ppid" "$launch_ticks" && (( SECONDS < transition_deadline )); do
      launch_pgid="$(ps -o pgid= -p "$launch_pid" 2>/dev/null | awk '{print $1}')"
      launch_sid="$(ps -o sid= -p "$launch_pid" 2>/dev/null | awk '{print $1}')"
      [[ "$launch_pgid" == "$launch_pid" && "$launch_sid" == "$launch_pid" ]] && break
      sleep 0.05
    done
    if [[ "$launch_ppid" != "$$" || ! "$launch_ticks" =~ ^[1-9][0-9]*$ || \
          "$launch_pgid" != "$launch_pid" || "$launch_sid" != "$launch_pid" ]] || \
       ! bound_pid_running "$launch_pid" "$launch_ppid" "$launch_ticks"; then
      publish_wave_abort "$wave" "$gpu" || true
      FAILED_TRANSITION_PID="$launch_pid"
      transition_signals_sent=0
      if bound_pid_running "$launch_pid" "$launch_ppid" "$launch_ticks"; then
        kill -TERM "$launch_pid" 2>/dev/null || true
        transition_signals_sent=1
        transition_deadline=$((SECONDS + 10))
        while (( SECONDS < transition_deadline )) && bound_pid_running "$launch_pid" "$launch_ppid" "$launch_ticks"; do sleep 1; done
        if bound_pid_running "$launch_pid" "$launch_ppid" "$launch_ticks"; then
          kill -KILL "$launch_pid" 2>/dev/null || true
          transition_signals_sent=2
        fi
        transition_deadline=$((SECONDS + KILL_GRACE_S))
        while (( SECONDS < transition_deadline )) && bound_pid_running "$launch_pid" "$launch_ppid" "$launch_ticks"; do sleep 1; done
      fi
      transition_process_evidence="$wave_dir/session-transition-failed-gpu${gpu}-processes.txt"
      if wait_failed_transition_quiet "$launch_pid" "$run_dir" "$transition_process_evidence"; then
        printf 'wave=%s\ngpu=%s\npid=%s\nparent_pid=%s\nstart_ticks=%s\nsignals_sent=%s\nwaited_through_gate_timeout=1\nmatching_processes_remaining=0\nreaped=1\ncleanup_survivor=0\n' \
          "$wave" "$gpu" "$launch_pid" "$launch_ppid" "$launch_ticks" "$transition_signals_sent" \
          > "$wave_dir/session-transition-failed-gpu${gpu}.env"
        FAILED_TRANSITION_PID=""
      else
        OUTER_SURVIVOR=1
        printf 'wave=%s\ngpu=%s\npid=%s\nparent_pid=%s\nstart_ticks=%s\nsignals_sent=%s\nwaited_through_gate_timeout=1\nmatching_processes_remaining=1\nreaped=0\ncleanup_survivor=1\n' \
          "$wave" "$gpu" "$launch_pid" "$launch_ppid" "$launch_ticks" "$transition_signals_sent" \
          > "$wave_dir/session-transition-failed-gpu${gpu}.env"
      fi
      die "child $gpu did not enter its atomically bound isolated session"
    fi
    CHILD_PIDS[$gpu]="$launch_pid"; CHILD_PPIDS[$gpu]="$launch_ppid"; CHILD_START_TICKS[$gpu]="$launch_ticks"
    CHILD_PGIDS[$gpu]="$launch_pgid"; CHILD_SIDS[$gpu]="$launch_sid"
    outer_identity_bound || die "outer runner identity lost at session gate"
    atomic_json "$session_gate" -n --argjson pid "$launch_pid" --argjson ppid "$launch_ppid" \
      --arg parent_ticks "$OUTER_START_TICKS" --arg ticks "$launch_ticks" \
      --argjson pgid "$launch_pgid" --argjson sid "$launch_sid" \
      '{passed:true,pid:$pid,parent_pid:$ppid,parent_start_ticks:$parent_ticks,start_ticks:$ticks,pgid:$pgid,sid:$sid}'
    printf 'wave=%s\tgpu=%s\tscenario=%s\tselector=%s\tport=%s\tpid=%s\tparent_pid=%s\tparent_start_ticks=%s\tstart_ticks=%s\tpgid=%s\tsid=%s\n' \
      "$wave" "$gpu" "$scenario" "$selector" "$port" "$launch_pid" "$launch_ppid" "$OUTER_START_TICKS" "$launch_ticks" "$launch_pgid" "$launch_sid" \
      >> "$wave_dir/wave-launches.tsv"
    if (( gpu != 3 )); then sleep "$START_STAGGER_S"; wave_failure_present && die "lane aborted during stagger"; fi
  done

  deadline=$((SECONDS + READINESS_TIMEOUT_S))
  while :; do
    wave_failure_present && die "lane aborted before release"
    all_ready=1
    for gpu in 0 1 2 3; do
      [[ -s "${CHILD_DIRS[$gpu]}/ready.json" ]] || all_ready=0
      recorded_session_alive "$gpu" || die "child $gpu lost binding before readiness"
    done
    (( all_ready == 1 )) && break
    (( SECONDS < deadline )) || die "wave readiness timeout"
    sleep 2
  done
  for gpu in 0 1 2 3; do
    recorded_session_alive "$gpu" || die "child $gpu not atomically bound at release"
    selector="$(selector_for_wave "$wave" "$gpu")"; scenario="${SCENARIOS[$gpu]}"
    jq -e --argjson wave "$wave" --argjson gpu "$gpu" --arg scenario "$scenario" --argjson selector "$selector" \
      '.ready==true and .wave==$wave and .gpu_index==$gpu and .scenario==$scenario and .selector==$selector' \
      "${CHILD_DIRS[$gpu]}/ready.json" >/dev/null || die "ready marker mismatch"
  done
  available_loaded_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
  (( available_loaded_kib >= 33554432 )) || die "host memory below 32 GiB with all servers loaded"
  sha256sum -c "$WAVE_INPUT_MANIFEST" > "$wave_dir/wave-inputs-prerelease.check.txt"
  for gpu in 0 1 2 3; do recorded_session_alive "$gpu" || die "child $gpu lost binding before release publication"; done
  outer_identity_bound || die "outer runner identity lost before release publication"
  publish_wave_release "$wave" || die "atomic wave release lost abort race"

  deadline=$((SECONDS + WAVE_TIMEOUT_S))
  while :; do
    wave_failure_present && die "lane aborted after release"
    any=0
    for gpu in 0 1 2 3; do
      if recorded_session_alive "$gpu"; then any=1
      elif [[ ! -s "${CHILD_DIRS[$gpu]}/artifacts.sha256" ]]; then die "child vanished without seal"; fi
    done
    (( any == 0 )) && break
    (( SECONDS < deadline )) || die "wave timeout"
    sleep 2
  done
  capture_recorded_members "$wave_dir/postwave-group-members-before-reap.txt"
  [[ ! -s "$wave_dir/postwave-group-members-before-reap.txt" ]] || die "live members remain"
  for gpu in 0 1 2 3; do
    wait "${CHILD_PIDS[$gpu]}" || die "child $gpu failed"
    (cd "${CHILD_DIRS[$gpu]}" && sha256sum -c artifacts.sha256 >/dev/null) || die "child seal invalid"
  done
  [[ ! -e "$CURRENT_WAVE_CHILD_SURVIVOR" ]] || die "child cleanup survivor reported"
  child_survivor_reported && die "lane cleanup reports a survivor"
  phase_passive_scan "$wave_dir" preprobe || die "passive fault evidence detected"
  sleep 3
  all_cards_idle=1; : > "$wave_dir/xpu-final-used.tsv"
  for gpu in 0 1 2 3; do
    sample_gpu "$gpu" "$wave_dir/xpu-smi-final-gpu${gpu}.txt" || { all_cards_idle=0; break; }
    used="$(parse_gpu_used_mib "$wave_dir/xpu-smi-final-gpu${gpu}.txt" "$gpu")" || { all_cards_idle=0; break; }
    printf 'gpu=%s\tused_mib=%s\n' "$gpu" "$used" >> "$wave_dir/xpu-final-used.tsv"
    (( used <= GPU_IDLE_MAX_MIB )) || { all_cards_idle=0; break; }
  done
  (( all_cards_idle == 1 )) || die "cards did not return to preflight idle envelope"
  phase_passive_scan "$wave_dir" postprobe || die "postprobe passive fault evidence detected"
  printf 'status=PASS\nall_groups_stopped=1\nall_listeners_closed=1\npassive_fault_detected=0\nfinal_xpu_probes_performed=1\nall_cards_idle=1\nforced_kill=0\ncleanup_survivor=0\n' \
    > "$wave_dir/global-cleanup-status.env"
  (
    cd "$wave_dir"
    find . -maxdepth 1 -type f \( -name 'preprobe-*' -o -name 'postprobe-*' \
      -o -name 'postwave-group-members-before-reap.txt' -o -name 'xpu-smi-final-gpu*.txt' \
      -o -name 'xpu-final-used.tsv' -o -name 'global-cleanup-status.env' \) \
      -print0 | sort -z | xargs -0 sha256sum > global-health-evidence.sha256
    sha256sum -c global-health-evidence.sha256 >/dev/null
  )
  atomic_json "$wave_dir/global-health.json" -n --argjson wave "$wave" \
    --arg evidence_sha "$(file_sha256 "$wave_dir/global-health-evidence.sha256")" \
    '{schema_version:1,phase:"canonical-q8-c2-crossover-wave",wave:$wave,passed:true,all_groups_stopped:true,all_listeners_closed:true,passive_fault_detected:false,final_xpu_probes_performed:true,all_cards_idle:true,forced_kill:false,cleanup_survivor:false,evidence_manifest:"global-health-evidence.sha256",evidence_manifest_sha256:$evidence_sha}'
  health_sha="$(file_sha256 "$wave_dir/global-health.json")"; cleanup_global_sha="$(file_sha256 "$wave_dir/global-cleanup-status.env")"
  for gpu in 0 1 2 3; do
    selector="$(selector_for_wave "$wave" "$gpu")"; scenario="${SCENARIOS[$gpu]}"; run_dir="${CHILD_DIRS[$gpu]}"
    manifest_sha="$(file_sha256 "$run_dir/artifacts.sha256")"; capture_sha="$(file_sha256 "$run_dir/capture.json")"
    attestation_sha="$(file_sha256 "$run_dir/lane-attestation.json")"; cleanup_sha="$(file_sha256 "$run_dir/cleanup-status.env")"
    server_pid="$(<"$run_dir/server.pid")"
    atomic_json "$run_dir/diagnostic-completion-status.json" -n --argjson wave "$wave" --argjson gpu "$gpu" \
      --arg scenario "$scenario" --argjson selector "$selector" --arg server_pid "$server_pid" \
      --arg manifest_sha "$manifest_sha" --arg capture_sha "$capture_sha" --arg attestation_sha "$attestation_sha" \
      --arg cleanup_sha "$cleanup_sha" --arg health_sha "$health_sha" --arg global_cleanup_sha "$cleanup_global_sha" \
      '{schema_version:1,phase:"canonical-q8-c2-crossover-lane",status:"EVIDENCE_VALID",evidence_valid:true,evidence_class:"diagnostic-only",performance_promotable:false,wave:$wave,gpu_index:$gpu,scenario:$scenario,selector:$selector,server_pid:$server_pid,artifact_manifest:"artifacts.sha256",artifact_manifest_sha256:$manifest_sha,capture_sha256:$capture_sha,attestation_sha256:$attestation_sha,cleanup_status_sha256:$cleanup_sha,global_health_sha256:$health_sha,global_cleanup_sha256:$global_cleanup_sha,lifecycle:{graceful_server_teardown:true,forced_kill:false,cleanup_survivor:false,port_closed:true,wave_global_health_passed:true}}'
  done
  printf 'PRE_SEAL_EVIDENCE_VALID\n' > "$wave_dir/wave-status.txt"
  seal_directory "$wave_dir" wave-artifacts.sha256 wave-diagnostic-completion-status.json || die "wave seal failed"
  manifest_sha="$(file_sha256 "$wave_dir/wave-artifacts.sha256")"
  atomic_json "$wave_dir/wave-diagnostic-completion-status.json" -n --argjson wave "$wave" --arg manifest_sha "$manifest_sha" \
    '{schema_version:1,phase:"canonical-q8-c2-crossover-wave",wave:$wave,status:"EVIDENCE_VALID",evidence_valid:true,evidence_class:"diagnostic-only",performance_promotable:false,artifact_manifest:"wave-artifacts.sha256",artifact_manifest_sha256:$manifest_sha}'
}

run_wave 1
jq -e '.status=="EVIDENCE_VALID" and .evidence_valid==true and .wave==1' \
  "$RUN_ROOT/wave1/wave-diagnostic-completion-status.json" >/dev/null || die "wave 1 did not close cleanly"
outer_identity_bound || die "outer runner identity lost between waves"
run_wave 2

aggregate_args=()
for wave in 1 2; do
  for gpu in 0 1 2 3; do
    selector="$(selector_for_wave "$wave" "$gpu")"; scenario="${SCENARIOS[$gpu]}"
    aggregate_args+=(--lane "$RUN_ROOT/wave${wave}/gpu${gpu}-${scenario}-selector${selector}")
  done
done
python3 "$ANALYZER" aggregate "${aggregate_args[@]}" --run-root "$RUN_ROOT" --wave1-dir "$RUN_ROOT/wave1" --wave2-dir "$RUN_ROOT/wave2" \
  --phase1-dir "$PHASE1_DIR" --phase1-manifest-sha256 "$EXPECTED_PHASE1_MANIFEST_SHA256" \
  --phase1-summary-sha256 "$EXPECTED_PHASE1_SUMMARY_SHA256" --phase1-marker-sha256 "$EXPECTED_PHASE1_MARKER_SHA256" \
  --selector0-oracle "$SELECTOR0_ORACLE" --selector0-oracle-sha256 "$EXPECTED_SELECTOR0_ORACLE_SHA256" \
  --selector1-oracle "$SELECTOR1_ORACLE" --selector1-oracle-sha256 "$EXPECTED_SELECTOR1_ORACLE_SHA256" \
  --out "$RUN_ROOT/crossover-summary.json"
jq -e '.evidence_valid==true and .status=="EVIDENCE_VALID" and .performance_promotable==false' \
  "$RUN_ROOT/crossover-summary.json" >/dev/null || die "crossover evidence invalid"
outer_identity_bound || die "outer runner identity lost before final evidence sealing"
capture_model_stat "/proc/$$/fd/$MODEL_FD" "$RUN_ROOT/model-stat-final.json"
cmp -s "$RUN_ROOT/model-stat-baseline.json" "$RUN_ROOT/model-stat-final.json" || die "outer model stat drift"
printf '%s  %s\n' "$EXPECTED_MODEL_SHA256" "/proc/$$/fd/$MODEL_FD" | sha256sum -c - > "$RUN_ROOT/model-sha256-final.check.txt"
runtime_report "$RUN_ROOT/runtime-final.json" "$RUN_ROOT/runtime-initial.json"
sha256sum -c "$WAVE_INPUT_MANIFEST" > "$RUN_ROOT/wave-inputs-final.check.txt"
printf 'EVIDENCE_VALID\n' > "$RUN_ROOT/run-root-status.txt"
printf 'status=PASS\nforced_kill=0\ncleanup_survivor=0\nbody_complete=1\n' > "$RUN_ROOT/run-root-cleanup-status.env"
outer_identity_bound || die "outer runner identity lost at final seal boundary"
seal_directory "$RUN_ROOT" run-root-artifacts.sha256 run-root-diagnostic-completion-status.json || die "run-root seal failed"
root_manifest_sha="$(file_sha256 "$RUN_ROOT/run-root-artifacts.sha256")"; summary_sha="$(file_sha256 "$RUN_ROOT/crossover-summary.json")"
classification="$(jq -er .scientific_outcome.classification "$RUN_ROOT/crossover-summary.json")"
atomic_json "$RUN_ROOT/run-root-diagnostic-completion-status.json" -n --arg manifest_sha "$root_manifest_sha" \
  --arg summary_sha "$summary_sha" --arg classification "$classification" \
  '{schema_version:1,phase:"canonical-q8-c2-two-wave-selector-crossover",status:"EVIDENCE_VALID",evidence_valid:true,evidence_class:"diagnostic-only",performance_promotable:false,scientific_outcome:$classification,artifact_manifest:"run-root-artifacts.sha256",artifact_manifest_sha256:$manifest_sha,summary:"crossover-summary.json",summary_sha256:$summary_sha}'
OUTER_COMPLETE=1
trap - EXIT INT TERM
printf '%s\n' "$RUN_ROOT"
