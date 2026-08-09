#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LANE="$ROOT/experiments/qwen36-27b-q8-gguf-b70"
RUNNER="$LANE/scripts/run-validation.sh"

STAMP="$(date -u +%Y%m%dT%H%M%S.%NZ)"
WAVE_DIR="${WAVE_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal1-four-gpu-functional-${STAMP}}"
PORT_BASE="${PORT_BASE:-19460}"
START_STAGGER_S="${START_STAGGER_S:-5}"
MIN_HOST_AVAILABLE_KIB="${MIN_HOST_AVAILABLE_KIB:-100663296}"
MIN_FAST_FREE_KIB="${MIN_FAST_FREE_KIB:-10485760}"
WAVE_TIMEOUT_S="${WAVE_TIMEOUT_S:-21600}"
TERM_GRACE_S="${TERM_GRACE_S:-45}"
KILL_GRACE_S="${KILL_GRACE_S:-10}"
GPU_IDLE_MAX_MIB=256

die() {
  echo "error: $*" >&2
  exit 1
}

for command_name in awk bash date df dirname env flock grep id jq mkdir pgrep ps \
  python3 rg setsid sha256sum sleep ss timeout xpu-smi; do
  command -v "$command_name" >/dev/null 2>&1 || die "missing command: $command_name"
done
[[ -x "$RUNNER" ]] || die "runner is not executable: $RUNNER"
[[ "$PORT_BASE" =~ ^[0-9]+$ ]] || die "PORT_BASE must be an integer"
(( PORT_BASE >= 1024 && PORT_BASE <= 65532 )) || die "PORT_BASE is outside the usable range"
[[ "$START_STAGGER_S" =~ ^[0-9]+$ ]] || die "START_STAGGER_S must be a nonnegative integer"
(( START_STAGGER_S <= 30 )) || die "START_STAGGER_S must be at most 30 seconds"
[[ "$MIN_HOST_AVAILABLE_KIB" =~ ^[0-9]+$ ]] || die "invalid host-memory floor"
[[ "$MIN_FAST_FREE_KIB" =~ ^[0-9]+$ ]] || die "invalid artifact-space floor"
[[ "$WAVE_TIMEOUT_S" =~ ^[0-9]+$ ]] && (( WAVE_TIMEOUT_S > 0 )) || die "invalid wave timeout"
[[ "$TERM_GRACE_S" =~ ^[0-9]+$ ]] && (( TERM_GRACE_S > 0 )) || die "invalid TERM grace"
[[ "$KILL_GRACE_S" =~ ^[0-9]+$ ]] && (( KILL_GRACE_S > 0 )) || die "invalid KILL grace"

parent_dir="$(dirname "$WAVE_DIR")"
mkdir -p "$parent_dir"
mkdir "$WAVE_DIR" || die "wave directory already exists: $WAVE_DIR"

exec 9>"/run/user/$(id -u)/qwen36-goal1-four-gpu-wave.lock"
flock -n 9 || die "another Goal-1 four-GPU wave owns the host lease"

GPU_LEASE_DIR="/run/user/$(id -u)/qwen36-b70-gpu-leases"
PORT_LEASE_DIR="/run/user/$(id -u)/qwen36-b70-port-leases"
mkdir -p "$GPU_LEASE_DIR" "$PORT_LEASE_DIR"
gpu_lease_fds=()
port_lease_fds=()
for gpu in 0 1 2 3; do
  unset lease_fd
  exec {lease_fd}>"$GPU_LEASE_DIR/gpu${gpu}.lock"
  flock -n "$lease_fd" || die "GPU $gpu is leased by another Qwen process"
  gpu_lease_fds[$gpu]="$lease_fd"
  port=$((PORT_BASE + gpu))
  unset port_fd
  exec {port_fd}>"$PORT_LEASE_DIR/port${port}.lock"
  flock -n "$port_fd" || die "port $port is leased by another Qwen process"
  port_lease_fds[$gpu]="$port_fd"
done

available_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
[[ -n "$available_kib" ]] || die "could not read MemAvailable"
(( available_kib >= MIN_HOST_AVAILABLE_KIB )) || \
  die "host memory below wave floor: ${available_kib} KiB"
fast_free_kib="$(df -Pk /mnt/fast-ai | awk 'NR == 2 {print $4}')"
[[ -n "$fast_free_kib" ]] || die "could not read artifact filesystem space"
(( fast_free_kib >= MIN_FAST_FREE_KIB )) || \
  die "artifact filesystem below free-space floor: ${fast_free_kib} KiB"

if pgrep -af 'llama-server|capture-exact-tokens.py|run-validation.sh' \
  > "$WAVE_DIR/preflight-processes.txt"; then
  die "an existing Qwen/llama validation process is active"
fi

xpu-smi discovery -j > "$WAVE_DIR/xpu-smi-discovery.json"
jq -e '
  ([.device_list[] |
    select(.device_function_type == "physical" and (.device_name | contains("Arc(TM) Pro B70")))] | length) == 4
  and ([.device_list[] |
    select(.device_function_type == "physical" and (.device_name | contains("Arc(TM) Pro B70"))) |
    .device_id] | sort) == [0, 1, 2, 3]
  and ([.device_list[] |
    select(.device_function_type == "physical" and (.device_name | contains("Arc(TM) Pro B70"))) |
    .pci_bdf_address] | unique | length) == 4
  and ([.device_list[] |
    select(.device_function_type == "physical" and (.device_name | contains("Arc(TM) Pro B70"))) |
    .uuid] | unique | length) == 4
' "$WAVE_DIR/xpu-smi-discovery.json" >/dev/null || die "four distinct B70s were not discovered"

for gpu in 0 1 2 3; do
  timeout 20 xpu-smi stats -d "$gpu" > "$WAVE_DIR/xpu-smi-preflight-gpu${gpu}.txt"
  used="$(awk -F '|' '/GPU Memory Used/{gsub(/[^0-9.]/, "", $3); print int($3); exit}' "$WAVE_DIR/xpu-smi-preflight-gpu${gpu}.txt")"
  [[ -n "$used" ]] || die "could not parse GPU $gpu memory"
  (( used <= GPU_IDLE_MAX_MIB )) || die "GPU $gpu is not idle: ${used} MiB"
done

for offset in 0 1 2 3; do
  port=$((PORT_BASE + offset))
  if ss -H -ltn "sport = :$port" | grep -q .; then
    die "port already in use: $port"
  fi
done

sha256sum \
  "${BASH_SOURCE[0]}" \
  "$RUNNER" \
  "$LANE/scripts/serve-target-only.sh" \
  "$LANE/scripts/capture-exact-tokens.py" \
  "$LANE/c2-long-context-suite-v1.json" \
  "$LANE/model-manifest.json" \
  "$LANE/runtime-manifest.json" \
  "$ROOT/scripts/bench-openai-long-context-suite.py" \
  "$ROOT/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json" \
  > "$WAVE_DIR/wave-harness-inputs.sha256"

bands=(short middle near32k realistic)
pids=()
run_dirs=()
runner_statuses=(99 99 99 99)
cleanup_started=0
wave_forced_kill=0
wave_cleanup_survivor=0

group_alive() {
  local pgid="$1"
  ps -eo pgid=,stat= | awk -v target="$pgid" '
    $1 == target && $2 !~ /^Z/ { found = 1 }
    END { exit(found ? 0 : 1) }
  '
}

leader_running() {
  local pid="$1"
  local state
  kill -0 "$pid" 2>/dev/null || return 1
  state="$(ps -o stat= -p "$pid" 2>/dev/null | awk '{print $1}')"
  [[ "$state" != Z* ]]
}

terminate_groups() {
  local deadline
  local any_alive
  local pid

  for pid in "${pids[@]:-}"; do
    if [[ -n "$pid" ]] && group_alive "$pid"; then
      kill -TERM -- "-$pid" 2>/dev/null || true
    fi
  done
  deadline=$((SECONDS + TERM_GRACE_S))
  while (( SECONDS < deadline )); do
    any_alive=0
    for pid in "${pids[@]:-}"; do
      [[ -n "$pid" ]] && group_alive "$pid" && any_alive=1
    done
    (( any_alive == 0 )) && break
    sleep 1
  done
  for pid in "${pids[@]:-}"; do
    if [[ -n "$pid" ]] && group_alive "$pid"; then
      wave_forced_kill=1
      kill -KILL -- "-$pid" 2>/dev/null || true
    fi
  done
  deadline=$((SECONDS + KILL_GRACE_S))
  while (( SECONDS < deadline )); do
    any_alive=0
    for pid in "${pids[@]:-}"; do
      [[ -n "$pid" ]] && group_alive "$pid" && any_alive=1
    done
    (( any_alive == 0 )) && break
    sleep 1
  done
  for pid in "${pids[@]:-}"; do
    if [[ -n "$pid" ]] && group_alive "$pid"; then
      wave_cleanup_survivor=1
    elif [[ -n "$pid" ]]; then
      wait "$pid" 2>/dev/null || true
    fi
  done
  (( wave_cleanup_survivor == 0 ))
}

cleanup_wave() {
  local status=$?
  trap - EXIT INT TERM
  if (( cleanup_started == 0 )); then
    cleanup_started=1
    terminate_groups || status=1
  fi
  exit "$status"
}
trap cleanup_wave EXIT
trap 'exit 130' INT TERM

for gpu in 0 1 2 3; do
  band="${bands[$gpu]}"
  port=$((PORT_BASE + gpu))
  run_dir="$WAVE_DIR/gpu${gpu}-${band}"
  run_dirs+=("$run_dir")
  setsid --wait env \
    GPU_INDEX="$gpu" \
    PORT="$port" \
    RUN_SCOPE=promotion512 \
    FULL512_BAND="$band" \
    EVIDENCE_CLASS=parallel-functional-screen \
    QWEN36_GPU_LEASE_FD="${gpu_lease_fds[$gpu]}" \
    QWEN36_PORT_LEASE_FD="${port_lease_fds[$gpu]}" \
    REQUIRE_ALL_GPUS_IDLE=0 \
    GPU_IDLE_MAX_MIB="$GPU_IDLE_MAX_MIB" \
    LOG_VERBOSITY=4 \
    LABEL="goal1-functional-gpu${gpu}-${band}" \
    RUN_DIR="$run_dir" \
    "$RUNNER" > "$WAVE_DIR/gpu${gpu}-${band}.runner.log" 2>&1 &
  pids+=("$!")
  child_pgid="$(ps -o pgid= -p "${pids[-1]}" | awk '{print $1}')"
  [[ "$child_pgid" == "${pids[-1]}" ]] || die "GPU $gpu runner did not create the expected process group"
  printf 'gpu=%s\tband=%s\tport=%s\tpid=%s\trun_dir=%s\n' \
    "$gpu" "$band" "$port" "${pids[-1]}" "$run_dir" \
    >> "$WAVE_DIR/wave-launches.tsv"
  if (( gpu < 3 && START_STAGGER_S > 0 )); then
    sleep "$START_STAGGER_S"
  fi
done

wave_failed=0
wave_deadline=$((SECONDS + WAVE_TIMEOUT_S))
while :; do
  all_leaders_done=1
  for pid in "${pids[@]}"; do
    if leader_running "$pid"; then
      all_leaders_done=0
      break
    fi
  done
  (( all_leaders_done == 1 )) && break
  if (( SECONDS >= wave_deadline )); then
    wave_failed=1
    terminate_groups || true
    break
  fi
  sleep 5
done
for gpu in 0 1 2 3; do
  if leader_running "${pids[$gpu]}"; then
    runner_statuses[$gpu]=124
    wave_failed=1
  elif wait "${pids[$gpu]}"; then
    runner_statuses[$gpu]=0
  else
    runner_statuses[$gpu]=$?
    wave_failed=1
  fi
done
for pid in "${pids[@]}"; do
  if group_alive "$pid"; then
    wave_failed=1
    terminate_groups || true
    break
  fi
done
(( wave_forced_kill == 0 && wave_cleanup_survivor == 0 )) || wave_failed=1

sha256sum -c "$WAVE_DIR/wave-harness-inputs.sha256" \
  > "$WAVE_DIR/wave-harness-final-check.txt" 2>&1 || wave_failed=1

for gpu in 0 1 2 3; do
  band="${bands[$gpu]}"
  run_dir="${run_dirs[$gpu]}"
  if [[ ! -s "$run_dir/completion-status.json" ]] ||
    ! jq -e '
      .status == "PASS"
      and .evidence_valid == true
      and .evidence_class == "parallel-functional-screen"
      and .performance_promotable == false
    ' "$run_dir/completion-status.json" >/dev/null; then
    wave_failed=1
  fi
  if [[ ! -s "$run_dir/artifacts.sha256" ]] || ! (
    cd "$run_dir"
    sha256sum -c artifacts.sha256 >/dev/null
  ); then
    wave_failed=1
  fi
  printf 'gpu=%s\tband=%s\trunner_status=%s\tcompletion_marker=%s\n' \
    "$gpu" "$band" "${runner_statuses[$gpu]}" \
    "$([[ -s "$run_dir/completion-status.json" ]] && echo present || echo missing)" \
    >> "$WAVE_DIR/wave-results.tsv"
done

if ! python3 - \
  "$WAVE_DIR" "$PORT_BASE" \
  "$LANE/c2-long-context-suite-v1.json" \
  "$ROOT/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json" \
  "$ROOT/scripts/bench-openai-long-context-suite.py" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
port_base = int(sys.argv[2])
paired_suite = str(Path(sys.argv[3]).resolve())
realistic_suite = str(Path(sys.argv[4]).resolve())
prompt_builder = str(Path(sys.argv[5]).resolve())
prompt_builder_sha256 = hashlib.sha256(Path(prompt_builder).read_bytes()).hexdigest()
bands = ["short", "middle", "near32k", "realistic"]


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path):
    with open(path) as stream:
        return json.load(stream)


def load_env(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


lanes = []
all_passed = True
for gpu, band in enumerate(bands):
    lane = root / f"gpu{gpu}-{band}"
    checks = {}
    try:
        marker = load_json(lane / "completion-status.json")
        identity = load_env(lane / "run-identity.env")
        exact = load_json(lane / "exact-tokens.json")
        exact_gate = load_json(lane / "exact-result-gate.json")
        expected_port = port_base + gpu
        expected_suite = realistic_suite if band == "realistic" else paired_suite
        rows = exact.get("rows") or []
        run_identity = exact.get("run_identity") or {}
        intrinsic = exact.get("intrinsic_gate") or {}
        prefix = exact.get("prefix_oracle_comparison")
        checks = {
            "completion_status": marker.get("status") == "PASS",
            "completion_evidence": marker.get("evidence_valid") is True,
            "completion_class": marker.get("evidence_class") == "parallel-functional-screen",
            "completion_not_promotable": marker.get("performance_promotable") is False,
            "completion_scope": marker.get("run_scope") == "promotion512",
            "completion_band": marker.get("full512_band") == band,
            "completion_gpu": marker.get("gpu_index") == gpu,
            "artifact_manifest_digest": marker.get("artifacts_manifest_sha256")
            == sha256(lane / "artifacts.sha256"),
            "preseal_run_status_digest": marker.get("pre_seal_run_status_sha256")
            == sha256(lane / "run-status.txt"),
            "preseal_exit_status_digest": marker.get("pre_seal_exit_status_sha256")
            == sha256(lane / "exit-status.txt"),
            "harness_manifest_digest": marker.get("harness_manifest_sha256")
            == sha256(lane / "harness-inputs.sha256"),
            "runtime_bundle_digest": marker.get("runtime_bundle_report_sha256")
            == sha256(lane / "runtime-bundle-initial.json"),
            "runtime_resolved_manifest_digest": marker.get("runtime_resolved_manifest_sha256")
            == sha256(lane / "runtime-resolved-files.sha256"),
            "result_digest": marker.get("result_sha256")
            == sha256(lane / "exact-tokens.json"),
            "marker_canary": marker.get("post_512_canary_passed") is True,
            "identity_gpu": identity.get("gpu_index") == str(gpu),
            "identity_port": identity.get("port") == str(expected_port),
            "identity_scope": identity.get("run_scope") == "promotion512",
            "identity_class": identity.get("evidence_class") == "parallel-functional-screen",
            "identity_not_promotable": identity.get("performance_promotable") == "0",
            "identity_band": identity.get("full512_band") == band,
            "identity_context": identity.get("ctx_size") == "32768",
            "identity_single_slot": identity.get("parallel_slots") == "1",
            "identity_parallel_idle_policy": identity.get("require_all_gpus_idle") == "0",
            "exact_gate": exact_gate.get("passed") is True,
            "intrinsic": intrinsic.get("passed") is True,
            "pp_gate": intrinsic.get("full_512_prompt_processing_fields_passed_all") is True,
            "canary_gate": intrinsic.get("post_512_canary_passed") is True,
            "canary_object": (exact.get("post_512_canary") or {}).get("passed") is True,
            "oracle_baseline": (exact.get("oracle_comparison") or {}).get("status")
            == "BASELINE_CAPTURE_READY",
            "prefix_gate": (
                isinstance(prefix, dict)
                and prefix.get("passed") is True
                and prefix.get("status") == "PASS_PREFIX_ORACLE_EXACT"
                if band == "realistic"
                else prefix is None
            ),
            "suite": str(Path(run_identity.get("suite_path", "")).resolve())
            == expected_suite,
            "prompt_builder": (
                run_identity.get("prompt_builder_path") is None
                if band == "realistic"
                else str(
                    Path(run_identity.get("prompt_builder_path", "")).resolve()
                )
                == prompt_builder
            ),
            "prompt_builder_digest": (
                run_identity.get("prompt_builder_sha256") is None
                if band == "realistic"
                else run_identity.get("prompt_builder_sha256")
                == prompt_builder_sha256
            ),
            "band": run_identity.get("band") == (None if band == "realistic" else band),
            "base_url": run_identity.get("base_url")
            == f"http://127.0.0.1:{expected_port}",
            "slot_zero": run_identity.get("slot_id") == 0,
            "max_tokens": run_identity.get("max_tokens") == 512,
            "exact_count": run_identity.get("require_exact_token_count") is True,
            "full_512": run_identity.get("require_full_512_metric") is True,
            "row_count": len(rows) == (12 if band == "realistic" else 2),
            "row_lengths": all(row.get("token_count") == 512 for row in rows),
            "row_intervals": all(
                (row.get("full_512_metric") or {}).get("interval_count") == 511
                for row in rows
            ),
        }
    except Exception as exc:  # fail closed and retain why
        checks = {"exception_free": False}
        error = repr(exc)
    else:
        error = None
    passed = bool(checks) and all(checks.values())
    all_passed = all_passed and passed
    lanes.append({
        "band": band,
        "checks": checks,
        "error": error,
        "gpu": gpu,
        "passed": passed,
    })

output = {"lanes": lanes, "passed": all_passed}
(root / "wave-child-validation.json").write_text(
    json.dumps(output, indent=2, sort_keys=True) + "\n"
)
if not all_passed:
    raise SystemExit("one or more child packets failed aggregate identity validation")
PY
then
  wave_failed=1
fi

final_available_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
[[ -n "$final_available_kib" ]] || wave_failed=1
(( final_available_kib >= 33554432 )) || wave_failed=1
for gpu in 0 1 2 3; do
  timeout 20 xpu-smi stats -d "$gpu" > "$WAVE_DIR/xpu-smi-final-gpu${gpu}.txt" || wave_failed=1
  used="$(awk -F '|' '/GPU Memory Used/{gsub(/[^0-9.]/, "", $3); print int($3); exit}' "$WAVE_DIR/xpu-smi-final-gpu${gpu}.txt")"
  [[ -n "$used" ]] || wave_failed=1
  (( used <= GPU_IDLE_MAX_MIB )) || wave_failed=1
  port=$((PORT_BASE + gpu))
  if ss -H -ltn "sport = :$port" | grep -q .; then
    wave_failed=1
  fi
done

python3 - "$WAVE_DIR" "$wave_failed" "$available_kib" "$final_available_kib" \
  "${runner_statuses[@]}" <<'PY'
import datetime
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
failed = int(sys.argv[2]) != 0
initial_memory = int(sys.argv[3])
final_memory = int(sys.argv[4])
statuses = [int(value) for value in sys.argv[5:9]]
bands = ["short", "middle", "near32k", "realistic"]
result = {
    "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "evidence_class": "parallel-functional-screen",
    "performance_promotable": False,
    "passed": not failed,
    "pre_seal_gates_passed": not failed,
    "host_mem_available_kib": {
        "preflight": initial_memory,
        "final": final_memory,
    },
    "lanes": [
        {
            "gpu": gpu,
            "band": band,
            "runner_status": statuses[gpu],
            "run_dir": f"gpu{gpu}-{band}",
        }
        for gpu, band in enumerate(bands)
    ],
    "note": "Rates from this simultaneous four-card wave are diagnostic; isolated packets are required for performance claims.",
}
(root / "wave-summary.json").write_text(
    json.dumps(result, indent=2, sort_keys=True) + "\n"
)
PY

{
  echo "wave_forced_kill=$wave_forced_kill"
  echo "wave_cleanup_survivor=$wave_cleanup_survivor"
  echo "wave_timeout_s=$WAVE_TIMEOUT_S"
  echo "term_grace_s=$TERM_GRACE_S"
  echo "kill_grace_s=$KILL_GRACE_S"
} > "$WAVE_DIR/wave-lifecycle.env"

seal_wave_artifacts() {
  local seal_tmp
  seal_tmp="$(mktemp "${WAVE_DIR}.artifacts.XXXXXX")" || return 1
  if ! (
    cd "$WAVE_DIR"
    find . -type f \
      ! -name wave-artifacts.sha256 \
      ! -name wave-completion-status.json \
      -print0 | sort -z | xargs -0 -r sha256sum
  ) > "$seal_tmp"; then
    rm -f "$seal_tmp"
    return 1
  fi
  if [[ ! -s "$seal_tmp" ]] || ! (
    cd "$WAVE_DIR"
    sha256sum -c "$seal_tmp" >/dev/null
  ); then
    rm -f "$seal_tmp"
    return 1
  fi
  mv "$seal_tmp" "$WAVE_DIR/wave-artifacts.sha256"
  (
    cd "$WAVE_DIR"
    sha256sum -c wave-artifacts.sha256 >/dev/null
  )
}

if (( wave_failed != 0 )); then
  printf 'FAIL\n' > "$WAVE_DIR/wave-status.txt"
  rm -f "$WAVE_DIR/wave-completion-status.json" "$WAVE_DIR/wave-artifacts.sha256"
  seal_wave_artifacts || true
  printf '%s\n' "$WAVE_DIR"
  exit 1
fi

printf 'PRE_SEAL_PASS_PENDING_COMPLETION\n' > "$WAVE_DIR/wave-status.txt"
rm -f "$WAVE_DIR/wave-completion-status.json" "$WAVE_DIR/wave-artifacts.sha256"
if ! seal_wave_artifacts; then
  printf 'FAIL\n' > "$WAVE_DIR/wave-status.txt"
  rm -f "$WAVE_DIR/wave-completion-status.json" "$WAVE_DIR/wave-artifacts.sha256"
  seal_wave_artifacts || true
  exit 1
fi
wave_manifest_sha="$(sha256sum "$WAVE_DIR/wave-artifacts.sha256" | awk '{print $1}')"
wave_summary_sha="$(sha256sum "$WAVE_DIR/wave-summary.json" | awk '{print $1}')"
wave_status_sha="$(sha256sum "$WAVE_DIR/wave-status.txt" | awk '{print $1}')"
wave_completion_tmp="$(mktemp "${WAVE_DIR}.completion.XXXXXX")"
if ! jq -n \
  --arg manifest_sha256 "$wave_manifest_sha" \
  --arg summary_sha256 "$wave_summary_sha" \
  --arg status_sha256 "$wave_status_sha" \
  '{status:"PASS", evidence_valid:true, evidence_class:"parallel-functional-screen", performance_promotable:false, artifact_manifest:"wave-artifacts.sha256", artifact_manifest_sha256:$manifest_sha256, pre_seal_summary:"wave-summary.json", pre_seal_summary_sha256:$summary_sha256, pre_seal_status:"wave-status.txt", pre_seal_status_sha256:$status_sha256}' \
  > "$wave_completion_tmp" ||
  ! jq -e \
    --arg manifest_sha256 "$wave_manifest_sha" \
    --arg summary_sha256 "$wave_summary_sha" \
    --arg status_sha256 "$wave_status_sha" '
      .status == "PASS"
      and .evidence_valid == true
      and .evidence_class == "parallel-functional-screen"
      and .performance_promotable == false
      and .artifact_manifest_sha256 == $manifest_sha256
      and .pre_seal_summary_sha256 == $summary_sha256
      and .pre_seal_status_sha256 == $status_sha256
    ' "$wave_completion_tmp" >/dev/null ||
  ! mv "$wave_completion_tmp" "$WAVE_DIR/wave-completion-status.json"; then
  rm -f "$wave_completion_tmp" "$WAVE_DIR/wave-completion-status.json"
  printf 'FAIL\n' > "$WAVE_DIR/wave-status.txt"
  rm -f "$WAVE_DIR/wave-artifacts.sha256"
  seal_wave_artifacts || true
  exit 1
fi
printf '%s\n' "$WAVE_DIR"
