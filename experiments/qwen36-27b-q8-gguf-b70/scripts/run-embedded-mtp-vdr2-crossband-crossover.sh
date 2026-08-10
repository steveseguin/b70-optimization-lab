#!/usr/bin/env bash
set -euo pipefail

# Default-off live wrapper for the fixed four-card, two-wave middle/near-32K
# embedded-MTP crossover.  The no-argument path must remain before ROOT
# resolution and every external command until independent review activates it.
LIVE_ENABLE_STATE="REVIEWED_AND_PINNED"
LIVE_ENABLE_REQUIRED="REVIEWED_AND_PINNED"
LIVE_ACK_REQUIRED="I_ACCEPT_FOUR_B70_EMBEDDED_MTP_VDR2_CROSSBAND_CROSSOVER"
CHILD_ACK_REQUIRED="INTERNAL_REVIEWED_CROSSBAND_CHILD_V1"
EXPECTED_CAPTURE_SHA256="94595b6962e64981723a063b6ec23b80c3701a22d0e256e85b596e6bf75f5b05"
EXPECTED_METRIC_GATES_SHA256="7af3cf19eee537a8381b4583b09649e6a616b375b72685b569c96f7094363a2b"
EXPECTED_CROSSBAND_GATES_SHA256="9154afc0ea874d26cc2028bad922921ca54d8a2b70f75341aff97990a3e9695b"
EXPECTED_SUITE_SHA256="053523440e4a23d7f772dec5025fe4831ba33c0a8eaba76795e4ee76718860af"
EXPECTED_PROMPT_BUILDER_SHA256="2286c9fd1ef59136a92a857be2992b31e0ff3bc844c7489239ab8f76f515cf72"

if [[ $# == 0 ]]; then
  if [[ "$LIVE_ENABLE_STATE" != "$LIVE_ENABLE_REQUIRED" ]]; then
    echo "live embedded-MTP cross-band crossover is PENDING independent review" >&2
    exit 2
  fi
  if [[ "$EXPECTED_CROSSBAND_GATES_SHA256" == "PENDING" ]]; then
    echo "live embedded-MTP cross-band crossover has a PENDING gate hash" >&2
    exit 2
  fi
  if [[ "${QWEN36_EMBEDDED_MTP_CROSSBAND_LIVE_ACK:-}" != "$LIVE_ACK_REQUIRED" ]]; then
    echo "live embedded-MTP cross-band crossover requires the exact acknowledgement" >&2
    exit 2
  fi
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LANE="$ROOT/experiments/qwen36-27b-q8-gguf-b70"
SCRIPT="$LANE/scripts/run-embedded-mtp-vdr2-crossband-crossover.sh"
CROSSBAND_GATES="$LANE/scripts/embedded_mtp_crossband_gates.py"
METRIC_GATES="$LANE/scripts/embedded_mtp_vdr2_gates.py"
CAPTURE="$LANE/scripts/capture-exact-tokens.py"
RUNTIME_VERIFY_LAUNCHER="$LANE/scripts/serve-target-only.sh"
OPTIONAL_MANIFEST="$LANE/optional-artifacts-manifest.json"
RUNTIME_MANIFEST="$LANE/runtime-manifest-q8-vdr2-candidate.json"
SUITE="$LANE/c2-long-context-suite-v1.json"
PROMPT_BUILDER="$ROOT/scripts/bench-openai-long-context-suite.py"

MODEL="/mnt/usb-models/models/qwen36-27b-mtp-q8-gguf/Qwen3.6-27B-Q8_0.gguf"
PARTIAL_MODEL="${MODEL}.partial"
EXPECTED_MODEL_SIZE=29047084160
EXPECTED_MODEL_SHA256="9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8"
EXPECTED_REPOSITORY="unsloth/Qwen3.6-27B-MTP-GGUF"
EXPECTED_REVISION="5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace"
EXPECTED_RUNTIME_MANIFEST_SHA256="4119790a79c55d158e7257d4fa0d95be0ca34639807c1a71ce87b60d6fdc1b49"
EXPECTED_RUNTIME_SHA256="1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7"
EXPECTED_RUNTIME_VERSION="version: 10298 (15586e2d7)"
LLAMA_SERVER="/mnt/fast-ai/runtime/llama.cpp-15586e2d-qwen27-vdr2-hybrid/llama-server"

READINESS_TIMEOUT_S=900
BARRIER_TIMEOUT_S=900
GPU_IDLE_MAX_MIB=256
MIN_HOST_AVAILABLE_KIB=33554432
MIN_LOADED_DELTA_MIB=25000
MAX_LOADED_USED_MIB=31632

usage() {
  cat <<'EOF'
Usage:
  run-embedded-mtp-vdr2-crossband-crossover.sh --offline-preflight
  QWEN36_EMBEDDED_MTP_CROSSBAND_LIVE_ACK=I_ACCEPT_FOUR_B70_EMBEDDED_MTP_VDR2_CROSSBAND_CROSSOVER \
    run-embedded-mtp-vdr2-crossband-crossover.sh

Once independently reviewed and deliberately activated, the live form leases
all four B70s and runs a fixed split crossover.  Wave 1 is GPU0 middle control,
GPU1 middle MTP3, GPU2 near32k control, GPU3 near32k MTP3.  Wave 2 reverses the
treatment on every card.  Middle uses -b 1024 -ub 128; near32k uses -b 1024
-ub 1024.  Each arm captures two deterministic prompts at a forced 512 tokens,
then performs the capture helper's same-lifetime exact replay.  Fresh same-card
controls are the quality authority.  This is a parallel functional screen, not
a LocalMaxxing submission run.  PORT_BASE and RUN_DIR are the only live
overrides.
EOF
}

offline_preflight() {
  for required in awk jq python3 sha256sum; do
    command -v "$required" >/dev/null 2>&1 || {
      echo "offline preflight: missing command: $required" >&2
      return 2
    }
  done
  for hash in \
    "$EXPECTED_CAPTURE_SHA256" "$EXPECTED_METRIC_GATES_SHA256" \
    "$EXPECTED_CROSSBAND_GATES_SHA256" "$EXPECTED_SUITE_SHA256" \
    "$EXPECTED_PROMPT_BUILDER_SHA256"; do
    [[ "$hash" =~ ^[0-9a-f]{64}$ ]] || {
      echo "offline preflight: a helper hash is PENDING or malformed" >&2
      return 2
    }
  done
  printf '%s  %s\n' \
    "$EXPECTED_CAPTURE_SHA256" "$CAPTURE" \
    "$EXPECTED_METRIC_GATES_SHA256" "$METRIC_GATES" \
    "$EXPECTED_CROSSBAND_GATES_SHA256" "$CROSSBAND_GATES" \
    "$EXPECTED_SUITE_SHA256" "$SUITE" \
    "$EXPECTED_PROMPT_BUILDER_SHA256" "$PROMPT_BUILDER" |
    sha256sum -c - >/dev/null
  [[ "$(sha256sum "$RUNTIME_MANIFEST" | awk '{print $1}')" == "$EXPECTED_RUNTIME_MANIFEST_SHA256" ]] || {
    echo "offline preflight: runtime manifest SHA-256 mismatch" >&2
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
  echo "offline embedded-MTP cross-band preflight: PASS"
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
  --child)
    ;;
  "")
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

port_is_listening() {
  local port="$1"
  local listeners
  if ! listeners="$(ss -H -ltn "sport = :$port" 2>&1)"; then
    printf 'ss failed while checking port %s: %s\n' "$port" "$listeners" >&2
    return 2
  fi
  [[ -n "$listeners" ]]
}

gpu_used_mib() {
  local device="$1"
  local output="$2"
  timeout 20 xpu-smi stats -d "$device" > "$output" 2>&1 || return 1
  awk -F '|' '/GPU Memory Used/{gsub(/[^0-9.]/, "", $3); print int($3); exit}' "$output"
}

check_host_memory() {
  local output="$1"
  local available
  available="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
  printf 'MemAvailable_kib=%s\nrequired_kib=%s\n' "${available:-unknown}" \
    "$MIN_HOST_AVAILABLE_KIB" > "$output"
  [[ "$available" =~ ^[0-9]+$ ]] && (( available >= MIN_HOST_AVAILABLE_KIB ))
}

capture_model_stat() {
  local requested="$1"
  local descriptor="$2"
  local output="$3"
  python3 - "$requested" "$descriptor" "$output" <<'PY'
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
with open(output, "w", encoding="utf-8") as stream:
    json.dump(payload, stream, indent=2, sort_keys=True)
    stream.write("\n")
PY
}

compare_model_stats() {
  local baseline="$1"
  local observed="$2"
  python3 - "$baseline" "$observed" <<'PY'
import json
import sys

baseline_path, observed_path = sys.argv[1:]
with open(baseline_path, encoding="utf-8") as stream:
    baseline = json.load(stream)
with open(observed_path, encoding="utf-8") as stream:
    observed = json.load(stream)
keys = {
    "requested_path",
    "requested_resolved",
    "descriptor_resolved",
    "device",
    "inode",
    "size_bytes",
    "mtime_ns",
    "ctime_ns",
    "mode",
}
if {key: baseline.get(key) for key in keys} != {
    key: observed.get(key) for key in keys
}:
    raise SystemExit("model stat identity changed")
PY
}

write_arm_identity() {
  local output="$1"
  local mode="$2"
  local band="$3"
  local gpu="$4"
  local wave="$5"
  local ubatch="$6"
  local port="$7"
  local alias="$8"
  local load_path="$9"
  shift 9
  python3 - "$output" "$mode" "$band" "$gpu" "$wave" "$ubatch" "$port" \
    "$alias" "$MODEL" "$load_path" "$EXPECTED_MODEL_SHA256" \
    "$EXPECTED_RUNTIME_SHA256" "$LLAMA_SERVER" "$@" <<'PY'
import json
import sys

(
    output,
    mode,
    band,
    gpu,
    wave,
    ubatch,
    port,
    alias,
    model,
    load_path,
    model_sha,
    runtime_sha,
    runtime_path,
    *argv,
) = sys.argv[1:]
payload = {
    "mode": mode,
    "band": band,
    "gpu_index": int(gpu),
    "wave": int(wave),
    "batch_size": 1024,
    "ubatch_size": int(ubatch),
    "port": int(port),
    "alias": alias,
    "model": model,
    "model_load_path": load_path,
    "model_sha256": model_sha,
    "runtime_sha256": runtime_sha,
    "runtime_path": runtime_path,
    "argv": argv,
}
with open(output, "w", encoding="utf-8") as stream:
    json.dump(payload, stream, indent=2, sort_keys=True)
    stream.write("\n")
PY
}

expected_assignment() {
  case "$1:$2" in
    1:0) printf 'middle control 128\n' ;;
    1:1) printf 'middle mtp3 128\n' ;;
    1:2) printf 'near32k control 1024\n' ;;
    1:3) printf 'near32k mtp3 1024\n' ;;
    2:0) printf 'middle mtp3 128\n' ;;
    2:1) printf 'middle control 128\n' ;;
    2:2) printf 'near32k mtp3 1024\n' ;;
    2:3) printf 'near32k control 1024\n' ;;
    *) return 2 ;;
  esac
}

seal_directory() {
  local directory="$1"
  local temporary
  temporary="$(mktemp "${directory}.artifacts.XXXXXX")"
  (
    cd "$directory"
    find . -type f ! -path ./artifacts.sha256 ! -path ./completion-status.json -print0 |
      sort -z | xargs -0 -r sha256sum
  ) > "$temporary"
  [[ -s "$temporary" ]]
  (
    cd "$directory"
    sha256sum -c "$temporary" >/dev/null
  )
  mv "$temporary" "$directory/artifacts.sha256"
}

child_main() {
  [[ "$LIVE_ENABLE_STATE" == "$LIVE_ENABLE_REQUIRED" ]] || {
    echo "internal child refused while live wrapper is PENDING" >&2
    return 2
  }
  [[ "$EXPECTED_CROSSBAND_GATES_SHA256" =~ ^[0-9a-f]{64}$ ]] || {
    echo "internal child refused with an unfrozen gate hash" >&2
    return 2
  }
  [[ "${QWEN36_EMBEDDED_MTP_CROSSBAND_CHILD_ACK:-}" == "$CHILD_ACK_REQUIRED" ]] || {
    echo "internal child acknowledgement mismatch" >&2
    return 2
  }
  [[ $# == 8 ]] || { echo "invalid internal child argument count" >&2; return 2; }
  local wave="$2"
  local gpu="$3"
  local band="$4"
  local mode="$5"
  local ubatch="$6"
  local port="$7"
  local pre_gpu_used="$8"
  local expected
  expected="$(expected_assignment "$wave" "$gpu")" || {
    echo "invalid wave/GPU assignment" >&2
    return 2
  }
  [[ "$band $mode $ubatch" == "$expected" ]] || {
    echo "cross-band child assignment does not match the frozen crossover" >&2
    return 2
  }
  [[ "$port" =~ ^[0-9]+$ && "$pre_gpu_used" =~ ^[0-9]+$ ]] || return 2
  [[ "${QWEN36_CROSSBAND_PARENT_RUN_DIR:-}" == /* ]] || return 2
  [[ "${QWEN36_CROSSBAND_PORT_BASE:-}" =~ ^[0-9]+$ ]] || return 2
  (( port == QWEN36_CROSSBAND_PORT_BASE + gpu )) || return 2
  [[ "${QWEN36_MODEL_FD:-}" =~ ^[0-9]+$ ]] || return 2

  local run_dir="$QWEN36_CROSSBAND_PARENT_RUN_DIR"
  local arm_dir="$run_dir/wave${wave}/gpu${gpu}-${band}-${mode}"
  local release="$run_dir/wave${wave}-release.json"
  local model_fd_path="/proc/$$/fd/$QWEN36_MODEL_FD"
  local model_load_path="/proc/self/fd/$QWEN36_MODEL_FD"
  local alias="qwen36-27b-mtp-crossband-w${wave}-g${gpu}-${band}-${mode}"
  local server_pid=""
  local child_finalizing=0

  stop_child_server() {
    local forced=0
    local survivor=0
    local state=""
    local final_used=""
    local port_closed=0
    local port_status=0
    local vram_returned=0
    [[ -n "$server_pid" ]] || return 0
    if kill -0 "$server_pid" 2>/dev/null; then
      kill "$server_pid" 2>/dev/null || true
      for _ in {1..30}; do
        if ! kill -0 "$server_pid" 2>/dev/null; then break; fi
        state="$(ps -o stat= -p "$server_pid" 2>/dev/null | awk '{print $1}' || true)"
        [[ "$state" == Z* ]] && break
        sleep 1
      done
    fi
    state="$(ps -o stat= -p "$server_pid" 2>/dev/null | awk '{print $1}' || true)"
    if kill -0 "$server_pid" 2>/dev/null && [[ "$state" != Z* ]]; then
      forced=1
      kill -KILL "$server_pid" 2>/dev/null || true
      for _ in {1..10}; do
        if ! kill -0 "$server_pid" 2>/dev/null; then break; fi
        state="$(ps -o stat= -p "$server_pid" 2>/dev/null | awk '{print $1}' || true)"
        [[ "$state" == Z* ]] && break
        sleep 1
      done
    fi
    state="$(ps -o stat= -p "$server_pid" 2>/dev/null | awk '{print $1}' || true)"
    if kill -0 "$server_pid" 2>/dev/null && [[ "$state" != Z* ]]; then
      survivor=1
    else
      wait "$server_pid" 2>/dev/null || true
    fi
    for _ in {1..20}; do
      if port_is_listening "$port"; then
        :
      else
        port_status=$?
        if (( port_status == 1 )); then port_closed=1; break; fi
      fi
      sleep 1
    done
    for attempt in {1..30}; do
      final_used="$(gpu_used_mib "$gpu" "$arm_dir/xpu-smi-after-${attempt}.txt" || true)"
      if [[ "$final_used" =~ ^[0-9]+$ ]] && \
        (( final_used <= pre_gpu_used + GPU_IDLE_MAX_MIB )); then
        vram_returned=1
        break
      fi
      sleep 1
    done
    cat > "$arm_dir/cleanup-status.env" <<EOF
forced_kill=$forced
cleanup_survivor=$survivor
port_closed=$port_closed
vram_returned=$vram_returned
pre_gpu_used_mib=$pre_gpu_used
final_gpu_used_mib=${final_used:-unknown}
EOF
    if (( survivor == 0 )); then server_pid=""; fi
    (( forced == 0 && survivor == 0 && port_closed == 1 && vram_returned == 1 ))
  }

  child_finalize() {
    local original_status=$?
    local final_status="$original_status"
    if (( child_finalizing == 1 )); then exit "$original_status"; fi
    child_finalizing=1
    trap - EXIT INT TERM
    set +e
    if [[ -n "$server_pid" ]]; then stop_child_server || final_status=1; fi
    if [[ -d "$arm_dir" && "$final_status" != 0 ]]; then
      chmod u+rwx "$arm_dir" 2>/dev/null || true
      find "$arm_dir" -type f -exec chmod u+rw {} + 2>/dev/null || true
      rm -f -- "$arm_dir/artifacts.sha256" "$arm_dir/completion-status.json" || true
      printf 'FAIL\n' > "$arm_dir/run-status.txt" || true
      seal_directory "$arm_dir" || true
    fi
    exit "$final_status"
  }
  trap child_finalize EXIT
  trap 'exit 130' INT TERM

  mkdir "$arm_dir"
  [[ "$MODEL" -ef "$model_fd_path" ]] || {
    echo "child model path/descriptor mismatch" >&2
    return 2
  }
  sha256sum -c "$run_dir/harness-inputs.sha256" \
    > "$arm_dir/harness-inputs-pre.check.txt" 2>&1
  capture_model_stat "$MODEL" "$model_fd_path" "$arm_dir/model-stat.json"
  compare_model_stats "$run_dir/model-stat-baseline.json" "$arm_dir/model-stat.json"
  check_host_memory "$arm_dir/host-memory-pre.env"

  export ZE_AFFINITY_MASK="$gpu"
  local -a spec_args
  if [[ "$mode" == control ]]; then
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
  local -a server_cmd=(
    "$LLAMA_SERVER"
    -m "$model_load_path"
    --alias "$alias"
    --host 127.0.0.1
    --port "$port"
    -dev SYCL0
    -ngl all
    -c 32768
    -np 1
    -b 1024
    -ub "$ubatch"
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
  write_arm_identity "$arm_dir/server-identity.json" "$mode" "$band" "$gpu" \
    "$wave" "$ubatch" "$port" "$alias" "$model_load_path" "${server_cmd[@]}"
  "${server_cmd[@]}" > "$arm_dir/server.stdout.log" 2>&1 &
  server_pid=$!
  printf '%s\n' "$server_pid" > "$arm_dir/server.pid"
  local deadline=$((SECONDS + READINESS_TIMEOUT_S))
  until curl --noproxy '*' -fsS "http://127.0.0.1:${port}/v1/models" \
    > "$arm_dir/models.json" 2> "$arm_dir/models.err"; do
    kill -0 "$server_pid" 2>/dev/null || {
      echo "server exited before readiness: wave $wave GPU $gpu" >&2
      return 1
    }
    (( SECONDS < deadline )) || {
      echo "server readiness timeout: wave $wave GPU $gpu" >&2
      return 1
    }
    sleep 2
  done
  python3 "$CROSSBAND_GATES" gate-server \
    --mode "$mode" --band "$band" --ubatch-size "$ubatch" \
    --gpu-index "$gpu" --wave "$wave" \
    --log "$arm_dir/server.stdout.log" \
    --identity "$arm_dir/server-identity.json" \
    --output "$arm_dir/server-gate.json"
  local loaded
  loaded="$(gpu_used_mib "$gpu" "$arm_dir/xpu-smi-loaded.txt")"
  [[ "$loaded" =~ ^[0-9]+$ ]] || return 1
  local loaded_delta=$((loaded - pre_gpu_used))
  cat > "$arm_dir/loaded-residency.env" <<EOF
pre_mib=$pre_gpu_used
loaded_mib=$loaded
loaded_delta_mib=$loaded_delta
required_delta_mib=$MIN_LOADED_DELTA_MIB
maximum_loaded_mib=$MAX_LOADED_USED_MIB
minimum_free_headroom_mib=1024
EOF
  (( loaded_delta >= MIN_LOADED_DELTA_MIB && loaded <= MAX_LOADED_USED_MIB )) || {
    echo "loaded residency violates frozen bounds: wave $wave GPU $gpu" >&2
    return 1
  }
  check_host_memory "$arm_dir/host-memory-loaded.env"
  curl --noproxy '*' -fsS "http://127.0.0.1:${port}/metrics" \
    > "$arm_dir/metrics-before.prom"
  python3 - "$arm_dir/ready.json.tmp" "$wave" "$gpu" "$band" "$mode" "$port" <<'PY'
import json
import sys

output, wave, gpu, band, mode, port = sys.argv[1:]
with open(output, "w", encoding="utf-8") as stream:
    json.dump(
        {
            "status": "READY",
            "wave": int(wave),
            "gpu_index": int(gpu),
            "band": band,
            "mode": mode,
            "port": int(port),
        },
        stream,
        indent=2,
        sort_keys=True,
    )
    stream.write("\n")
PY
  mv "$arm_dir/ready.json.tmp" "$arm_dir/ready.json"
  deadline=$((SECONDS + BARRIER_TIMEOUT_S))
  until [[ -f "$release" ]]; do
    kill -0 "$server_pid" 2>/dev/null || return 1
    (( SECONDS < deadline )) || {
      echo "barrier release timeout: wave $wave GPU $gpu" >&2
      return 1
    }
    sleep 1
  done
  jq -e --argjson wave "$wave" \
    '.status == "RELEASED" and .wave == $wave and .ready_count == 4' \
    "$release" >/dev/null

  python3 "$CAPTURE" \
    --base-url "http://127.0.0.1:${port}" \
    --suite "$SUITE" \
    --prompt-builder "$PROMPT_BUILDER" \
    --band "$band" \
    --out "$arm_dir/exact-tokens.json" \
    --max-tokens 512 \
    --ignore-eos \
    --require-exact-token-count \
    --require-full-512-metric \
    --slot-id 0 \
    --seed 1 \
    --model-sha256 "$EXPECTED_MODEL_SHA256" \
    --runtime-sha256 "$EXPECTED_RUNTIME_SHA256" \
    --cache-type-k f16 \
    --cache-type-v f16 \
    --ctx-size 32768 \
    --sycl-dnn-enabled 0 \
    --sycl-opt-enabled 1 \
    > "$arm_dir/exact-tokens.stdout.log" 2>&1
  curl --noproxy '*' -fsS "http://127.0.0.1:${port}/metrics" \
    > "$arm_dir/metrics-after.prom"
  python3 "$METRIC_GATES" gate-metrics \
    --mode "$mode" \
    --before "$arm_dir/metrics-before.prom" \
    --after "$arm_dir/metrics-after.prom" \
    --output "$arm_dir/metrics-gate.json"
  python3 "$CROSSBAND_GATES" gate-server \
    --mode "$mode" --band "$band" --ubatch-size "$ubatch" \
    --gpu-index "$gpu" --wave "$wave" \
    --log "$arm_dir/server.stdout.log" \
    --identity "$arm_dir/server-identity.json" \
    --output "$arm_dir/server-gate-postcapture.json"
  python3 "$CROSSBAND_GATES" gate-arm \
    --mode "$mode" --band "$band" --ubatch-size "$ubatch" \
    --gpu-index "$gpu" --wave "$wave" \
    --capture "$arm_dir/exact-tokens.json" \
    --suite "$SUITE" --prompt-builder "$PROMPT_BUILDER" \
    --server-gate "$arm_dir/server-gate.json" \
    --server-post-gate "$arm_dir/server-gate-postcapture.json" \
    --metrics-before "$arm_dir/metrics-before.prom" \
    --metrics-after "$arm_dir/metrics-after.prom" \
    --metrics-gate "$arm_dir/metrics-gate.json" \
    --output "$arm_dir/arm-gate.json"
  sha256sum -c "$run_dir/harness-inputs.sha256" \
    > "$arm_dir/harness-inputs-post.check.txt" 2>&1
  capture_model_stat "$MODEL" "$model_fd_path" "$arm_dir/model-stat-post.json"
  compare_model_stats "$run_dir/model-stat-baseline.json" "$arm_dir/model-stat-post.json"
  stop_child_server
  printf 'PASS_EVIDENCE_VALID\n' > "$arm_dir/run-status.txt"
  seal_directory "$arm_dir"
  python3 - "$arm_dir" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

arm = Path(sys.argv[1])
gate = json.loads((arm / "arm-gate.json").read_text())
if gate.get("passed") is not True:
    raise SystemExit("arm gate did not pass")
payload = {
    "status": "PASS",
    "evidence_valid": True,
    "performance_promotable": False,
    "localmaxxing_submission_ready": False,
    "arm_gate_sha256": hashlib.sha256((arm / "arm-gate.json").read_bytes()).hexdigest(),
    "artifacts_manifest_sha256": hashlib.sha256((arm / "artifacts.sha256").read_bytes()).hexdigest(),
}
(arm / "completion-status.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY
  find "$arm_dir" -type f -exec chmod 0444 {} +
  chmod 0555 "$arm_dir"
  trap - EXIT INT TERM
}

if [[ "${1:-}" == --child ]]; then
  child_main "$@"
  exit $?
fi

PORT_BASE="${PORT_BASE:-20120}"
[[ "$PORT_BASE" =~ ^[0-9]{1,5}$ ]] || {
  echo "PORT_BASE must be a decimal port number" >&2
  exit 2
}
PORT_BASE_DECIMAL=$((10#$PORT_BASE))
(( PORT_BASE_DECIMAL >= 1024 && PORT_BASE_DECIMAL <= 65532 )) || {
  echo "PORT_BASE must leave four valid consecutive ports" >&2
  exit 2
}
STAMP="$(date -u +%Y%m%dT%H%M%S.%NZ)"
RUN_DIR="${RUN_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/embedded-mtp-vdr2-crossband-crossover-${STAMP}}"
[[ "$RUN_DIR" == /* && "$RUN_DIR" != / && "$RUN_DIR" != *$'\n'* ]] || {
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

unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
export NO_PROXY="127.0.0.1,localhost"
export no_proxy="$NO_PROXY"

for required in awk cat chmod cmp cp curl date dirname env find flock grep id \
  journalctl jq kill mkdir mktemp mv ps python3 readlink rm setsid sha256sum \
  sleep sort ss stat timeout xargs xpu-smi; do
  command -v "$required" >/dev/null 2>&1 || {
    echo "required command not found: $required" >&2
    exit 2
  }
done
offline_preflight >/dev/null
[[ -f "$MODEL" && ! -L "$MODEL" ]] || { echo "pinned model is missing or a symlink" >&2; exit 2; }
[[ ! -e "$PARTIAL_MODEL" ]] || { echo "partial model artifact exists" >&2; exit 2; }
[[ "$(stat -c %s "$MODEL")" == "$EXPECTED_MODEL_SIZE" ]] || { echo "model size mismatch" >&2; exit 2; }
[[ -x "$LLAMA_SERVER" ]] || { echo "pinned runtime is not executable" >&2; exit 2; }

mkdir -p "$(dirname "$RUN_DIR")"
mkdir "$RUN_DIR" || { echo "RUN_DIR already exists or cannot be created" >&2; exit 2; }
START_EPOCH="$(date +%s)"
BODY_COMPLETED=0
FINALIZING=0
MODEL_BASELINE_READY=0
RUNTIME_BASELINE_READY=0
HARNESS_BASELINE_READY=0
ACTIVE_CHILD_PIDS=()
declare -a PRE_GPU_USED=(0 0 0 0)

process_is_live() {
  local pid="$1"
  local state
  kill -0 "$pid" 2>/dev/null || return 1
  state="$(ps -o stat= -p "$pid" 2>/dev/null | awk '{print $1}' || true)"
  [[ -n "$state" && "$state" != Z* ]]
}

kill_active_children() {
  local pid
  for pid in "${ACTIVE_CHILD_PIDS[@]}"; do
    if [[ "$pid" =~ ^[0-9]+$ ]] && process_is_live "$pid"; then
      kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    fi
  done
  for _ in {1..30}; do
    local alive=0
    for pid in "${ACTIVE_CHILD_PIDS[@]}"; do
      process_is_live "$pid" && alive=1
    done
    (( alive == 0 )) && break
    sleep 1
  done
  for pid in "${ACTIVE_CHILD_PIDS[@]}"; do
    if [[ "$pid" =~ ^[0-9]+$ ]] && process_is_live "$pid"; then
      kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
    fi
    wait "$pid" 2>/dev/null || true
  done
  ACTIVE_CHILD_PIDS=()
}

verify_harness_inputs() {
  local label="$1"
  sha256sum -c "$RUN_DIR/harness-inputs.sha256" \
    > "$RUN_DIR/harness-inputs-${label}.check.txt" 2>&1
}

verify_model_stat() {
  local label="$1"
  local observed="$RUN_DIR/model-stat-${label}.json"
  [[ "$MODEL" -ef "$MODEL_FD_PATH" ]]
  capture_model_stat "$MODEL" "$MODEL_FD_PATH" "$observed"
  cmp -s "$RUN_DIR/model-stat-baseline.json" "$observed"
}

finalize() {
  local original_status=$?
  local final_status="$original_status"
  local harness_ok=0
  local model_stat_ok=0
  local model_hash_ok=0
  local runtime_ok=0
  local idle_ok=1
  local port_ok=1
  local device_scan_status=0
  if (( FINALIZING == 1 )); then exit "$original_status"; fi
  FINALIZING=1
  trap - EXIT INT TERM
  set +e
  set +u
  kill_active_children
  if (( HARNESS_BASELINE_READY == 1 )) && verify_harness_inputs final; then harness_ok=1; else final_status=1; fi
  if (( MODEL_BASELINE_READY == 1 )) && verify_model_stat final; then model_stat_ok=1; else final_status=1; fi
  if (( MODEL_BASELINE_READY == 1 )) && \
    printf '%s  %s\n' "$EXPECTED_MODEL_SHA256" "$MODEL_FD_PATH" |
      sha256sum -c - > "$RUN_DIR/model-sha256-final.check.txt" 2>&1; then
    model_hash_ok=1
  else
    final_status=1
  fi
  if (( RUNTIME_BASELINE_READY == 1 )) && \
    LLAMA_SERVER="$LLAMA_SERVER" RUNTIME_MANIFEST="$RUNTIME_MANIFEST" \
      "$RUNTIME_VERIFY_LAUNCHER" --verify-runtime-bundle \
      "$RUN_DIR/llama-server-ldd-final.txt" \
      "$RUN_DIR/runtime-resolved-files-final.sha256" \
      "$RUN_DIR/runtime-bundle-final.json" \
      "$RUN_DIR/runtime-bundle-initial.json"; then
    runtime_ok=1
  else
    final_status=1
  fi
  for gpu in 0 1 2 3; do
    used="$(gpu_used_mib "$gpu" "$RUN_DIR/xpu-smi-final-gpu${gpu}.txt" || true)"
    if [[ ! "$used" =~ ^[0-9]+$ ]] || (( used > PRE_GPU_USED[$gpu] + GPU_IDLE_MAX_MIB )); then
      idle_ok=0
      final_status=1
    fi
    port=$((PORT_BASE_DECIMAL + gpu))
    if port_is_listening "$port"; then
      port_ok=0
      final_status=1
    elif [[ $? != 1 ]]; then
      port_ok=0
      final_status=1
    fi
  done
  journalctl -k --since "@$START_EPOCH" --no-pager \
    > "$RUN_DIR/kernel-journal.txt" 2> "$RUN_DIR/kernel-journal.stderr.txt"
  [[ $? == 0 ]] || final_status=1
  grep -Ei 'xe.*(reset|wedg|fault|hang|timedout|device lost)|GuC.*reset|Fault response|VM.*fault|PCIe.*AER|UR_RESULT_ERROR_DEVICE_LOST|ZE_RESULT_ERROR_DEVICE_LOST' \
    "$RUN_DIR/kernel-journal.txt" > "$RUN_DIR/device-error-scan.txt"
  device_scan_status=$?
  if (( device_scan_status > 1 )) || [[ -s "$RUN_DIR/device-error-scan.txt" ]]; then final_status=1; fi
  (( BODY_COMPLETED == 1 )) || final_status=1
  printf '%s\n' \
    "harness_inputs_unchanged=$harness_ok" \
    "model_stat_unchanged=$model_stat_ok" \
    "model_sha256_final_verified=$model_hash_ok" \
    "runtime_bundle_unchanged=$runtime_ok" \
    "all_gpus_idle=$idle_ok" \
    "all_ports_closed=$port_ok" \
    "body_completed=$BODY_COMPLETED" > "$RUN_DIR/final-integrity.env"
  rm -f -- "$RUN_DIR/artifacts.sha256" "$RUN_DIR/completion-status.json"
  if (( final_status == 0 )); then
    printf 'PASS_EVIDENCE_VALID\n' > "$RUN_DIR/run-status.txt"
  else
    printf 'FAIL\n' > "$RUN_DIR/run-status.txt"
  fi
  seal_directory "$RUN_DIR" || final_status=1
  if (( final_status == 0 )); then
    python3 - "$RUN_DIR" <<'PY' || final_status=1
import hashlib
import json
import sys
from pathlib import Path

run = Path(sys.argv[1])
comparison = json.loads((run / "comparison.json").read_text())
if comparison.get("evidence_passed") is not True:
    raise SystemExit("comparison evidence did not pass")
payload = {
    "status": "PASS",
    "evidence_valid": True,
    "classification": comparison.get("classification"),
    "evidence_class": "parallel-functional-screen",
    "performance_promotable": False,
    "localmaxxing_submission_ready": False,
    "comparison_sha256": hashlib.sha256((run / "comparison.json").read_bytes()).hexdigest(),
    "artifacts_manifest_sha256": hashlib.sha256((run / "artifacts.sha256").read_bytes()).hexdigest(),
}
(run / "completion-status.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY
  fi
  if (( final_status != 0 )); then
    rm -f -- "$RUN_DIR/completion-status.json" "$RUN_DIR/artifacts.sha256"
    printf 'FAIL\n' > "$RUN_DIR/run-status.txt"
    seal_directory "$RUN_DIR" || true
  fi
  exit "$final_status"
}
trap finalize EXIT
trap 'exit 130' INT TERM

GPU_LEASE_DIR="/run/user/$(id -u)/qwen36-b70-gpu-leases"
PORT_LEASE_DIR="/run/user/$(id -u)/qwen36-b70-port-leases"
mkdir -p "$GPU_LEASE_DIR" "$PORT_LEASE_DIR"
LEASE_FDS=()
for gpu in 0 1 2 3; do
  exec {lease_fd}>"$GPU_LEASE_DIR/gpu${gpu}.lock"
  flock -n "$lease_fd" || { echo "GPU $gpu is already leased" >&2; exit 2; }
  LEASE_FDS+=("$lease_fd")
  port=$((PORT_BASE_DECIMAL + gpu))
  exec {lease_fd}>"$PORT_LEASE_DIR/port${port}.lock"
  flock -n "$lease_fd" || { echo "port $port is already leased" >&2; exit 2; }
  LEASE_FDS+=("$lease_fd")
  if port_is_listening "$port"; then
    echo "port $port is already listening" >&2
    exit 2
  elif [[ $? != 1 ]]; then
    exit 2
  fi
done

exec {QWEN36_MODEL_FD}<"$MODEL"
flock -s -n "$QWEN36_MODEL_FD" || { echo "could not lock integrated model" >&2; exit 2; }
export QWEN36_MODEL_FD
MODEL_FD_PATH="/proc/$$/fd/$QWEN36_MODEL_FD"
MODEL_LOAD_PATH="/proc/self/fd/$QWEN36_MODEL_FD"
[[ "$MODEL" -ef "$MODEL_FD_PATH" ]] || { echo "model descriptor mismatch" >&2; exit 2; }
capture_model_stat "$MODEL" "$MODEL_FD_PATH" "$RUN_DIR/model-stat-before-hash.json"
printf '%s  %s\n' "$EXPECTED_MODEL_SHA256" "$MODEL_FD_PATH" |
  sha256sum -c - > "$RUN_DIR/model-sha256-initial.check.txt"
capture_model_stat "$MODEL" "$MODEL_FD_PATH" "$RUN_DIR/model-stat-after-hash.json"
cmp -s "$RUN_DIR/model-stat-before-hash.json" "$RUN_DIR/model-stat-after-hash.json"
cp "$RUN_DIR/model-stat-after-hash.json" "$RUN_DIR/model-stat-baseline.json"
MODEL_BASELINE_READY=1

check_host_memory "$RUN_DIR/host-memory-preflight.env" || {
  echo "host MemAvailable is below the 32 GiB floor" >&2
  exit 2
}
xpu-smi discovery -j > "$RUN_DIR/xpu-smi-discovery.json"
jq -e '
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
' "$RUN_DIR/xpu-smi-discovery.json" >/dev/null
for gpu in 0 1 2 3; do
  PRE_GPU_USED[$gpu]="$(gpu_used_mib "$gpu" "$RUN_DIR/xpu-smi-before-gpu${gpu}.txt")"
  [[ "${PRE_GPU_USED[$gpu]}" =~ ^[0-9]+$ ]] || exit 2
  (( PRE_GPU_USED[$gpu] <= GPU_IDLE_MAX_MIB )) || {
    echo "GPU $gpu is not idle: ${PRE_GPU_USED[$gpu]} MiB" >&2
    exit 2
  }
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
RUNTIME_VERSION="$(ZE_AFFINITY_MASK=0 "$LLAMA_SERVER" --version 2>&1)"
grep -Fqx "$EXPECTED_RUNTIME_VERSION" <<< "$RUNTIME_VERSION"

harness_inputs=(
  "$SCRIPT" "$CROSSBAND_GATES" "$METRIC_GATES" "$CAPTURE"
  "$RUNTIME_VERIFY_LAUNCHER" "$OPTIONAL_MANIFEST" "$RUNTIME_MANIFEST"
  "$SUITE" "$PROMPT_BUILDER"
)
printf '%s\n' "${harness_inputs[@]}" | sort -u > "$RUN_DIR/harness-input-paths.txt"
while IFS= read -r path; do sha256sum "$path"; done \
  < "$RUN_DIR/harness-input-paths.txt" > "$RUN_DIR/harness-inputs.sha256"
HARNESS_BASELINE_READY=1
verify_harness_inputs initial

python3 - "$RUN_DIR/run-identity.json" "$STAMP" "$PORT_BASE_DECIMAL" \
  "$MODEL_LOAD_PATH" <<'PY'
import json
import sys

output, stamp, port_base, model_load_path = sys.argv[1:]
payload = {
    "date_utc": stamp,
    "evidence_class": "parallel-functional-screen",
    "performance_promotable": False,
    "localmaxxing_submission_ready": False,
    "model_load_path": model_load_path,
    "model_size": 29047084160,
    "model_sha256": "9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8",
    "model_repository": "unsloth/Qwen3.6-27B-MTP-GGUF",
    "model_revision": "5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace",
    "runtime_path": "/mnt/fast-ai/runtime/llama.cpp-15586e2d-qwen27-vdr2-hybrid/llama-server",
    "runtime_sha256": "1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7",
    "runtime_manifest_sha256": "4119790a79c55d158e7257d4fa0d95be0ca34639807c1a71ce87b60d6fdc1b49",
    "runtime_commit": "15586e2d7165570fb3aa7c26e0d442e289ef69de",
    "suite_sha256": "053523440e4a23d7f772dec5025fe4831ba33c0a8eaba76795e4ee76718860af",
    "prompt_builder_sha256": "2286c9fd1ef59136a92a857be2992b31e0ff3bc844c7489239ab8f76f515cf72",
    "port_base": int(port_base),
    "ctx_size": 32768,
    "batch_size": 1024,
    "cache_type_k": "f16",
    "cache_type_v": "f16",
    "sycl_dnn_enabled": 0,
    "sycl_opt_enabled": 1,
    "max_tokens": 512,
    "ignore_eos": True,
    "assignments": [
        {"wave": 1, "gpu": 0, "band": "middle", "mode": "control", "ubatch": 128},
        {"wave": 1, "gpu": 1, "band": "middle", "mode": "mtp3", "ubatch": 128},
        {"wave": 1, "gpu": 2, "band": "near32k", "mode": "control", "ubatch": 1024},
        {"wave": 1, "gpu": 3, "band": "near32k", "mode": "mtp3", "ubatch": 1024},
        {"wave": 2, "gpu": 0, "band": "middle", "mode": "mtp3", "ubatch": 128},
        {"wave": 2, "gpu": 1, "band": "middle", "mode": "control", "ubatch": 128},
        {"wave": 2, "gpu": 2, "band": "near32k", "mode": "mtp3", "ubatch": 1024},
        {"wave": 2, "gpu": 3, "band": "near32k", "mode": "control", "ubatch": 1024},
    ],
}
with open(output, "w", encoding="utf-8") as stream:
    json.dump(payload, stream, indent=2, sort_keys=True)
    stream.write("\n")
PY

launch_arm() {
  local wave="$1"
  local gpu="$2"
  local band="$3"
  local mode="$4"
  local ubatch="$5"
  local port=$((PORT_BASE_DECIMAL + gpu))
  QWEN36_EMBEDDED_MTP_CROSSBAND_CHILD_ACK="$CHILD_ACK_REQUIRED" \
    QWEN36_CROSSBAND_PARENT_RUN_DIR="$RUN_DIR" \
    QWEN36_CROSSBAND_PORT_BASE="$PORT_BASE_DECIMAL" \
    setsid --wait env \
      QWEN36_EMBEDDED_MTP_CROSSBAND_CHILD_ACK="$CHILD_ACK_REQUIRED" \
      QWEN36_CROSSBAND_PARENT_RUN_DIR="$RUN_DIR" \
      QWEN36_CROSSBAND_PORT_BASE="$PORT_BASE_DECIMAL" \
      ZE_AFFINITY_MASK="$gpu" \
      "$SCRIPT" --child "$wave" "$gpu" "$band" "$mode" "$ubatch" "$port" \
      "${PRE_GPU_USED[$gpu]}" &
  ACTIVE_CHILD_PIDS+=("$!")
}

run_wave() {
  local wave="$1"
  local deadline
  local all_ready
  local failed=0
  local pid
  local gpu
  local band
  local mode
  local ubatch
  local directory
  ACTIVE_CHILD_PIDS=()
  mkdir "$RUN_DIR/wave${wave}"
  if [[ "$wave" == 1 ]]; then
    launch_arm 1 0 middle control 128
    launch_arm 1 1 middle mtp3 128
    launch_arm 1 2 near32k control 1024
    launch_arm 1 3 near32k mtp3 1024
  else
    launch_arm 2 0 middle mtp3 128
    launch_arm 2 1 middle control 128
    launch_arm 2 2 near32k mtp3 1024
    launch_arm 2 3 near32k control 1024
  fi
  deadline=$((SECONDS + BARRIER_TIMEOUT_S))
  while :; do
    all_ready=1
    for gpu in 0 1 2 3; do
      read -r band mode ubatch <<< "$(expected_assignment "$wave" "$gpu")"
      directory="$RUN_DIR/wave${wave}/gpu${gpu}-${band}-${mode}"
      [[ -f "$directory/ready.json" ]] || all_ready=0
      pid="${ACTIVE_CHILD_PIDS[$gpu]}"
      process_is_live "$pid" || {
        echo "wave $wave GPU $gpu child exited before the barrier" >&2
        return 1
      }
    done
    (( all_ready == 1 )) && break
    (( SECONDS < deadline )) || {
      echo "wave $wave readiness barrier timed out" >&2
      return 1
    }
    sleep 1
  done
  for gpu in 0 1 2 3; do
    read -r band mode ubatch <<< "$(expected_assignment "$wave" "$gpu")"
    directory="$RUN_DIR/wave${wave}/gpu${gpu}-${band}-${mode}"
    jq -e --argjson wave "$wave" --argjson gpu "$gpu" --arg band "$band" --arg mode "$mode" '
      .status == "READY" and .wave == $wave and .gpu_index == $gpu
      and .band == $band and .mode == $mode
    ' "$directory/ready.json" >/dev/null
    port=$((PORT_BASE_DECIMAL + gpu))
    port_is_listening "$port"
  done
  python3 - "$RUN_DIR/wave${wave}-release.json.tmp" "$wave" <<'PY'
import json
import sys

output, wave = sys.argv[1:]
with open(output, "w", encoding="utf-8") as stream:
    json.dump(
        {"status": "RELEASED", "wave": int(wave), "ready_count": 4},
        stream,
        indent=2,
        sort_keys=True,
    )
    stream.write("\n")
PY
  mv "$RUN_DIR/wave${wave}-release.json.tmp" "$RUN_DIR/wave${wave}-release.json"
  for pid in "${ACTIVE_CHILD_PIDS[@]}"; do
    if ! wait "$pid"; then failed=1; fi
  done
  ACTIVE_CHILD_PIDS=()
  (( failed == 0 )) || return 1
  for gpu in 0 1 2 3; do
    read -r band mode ubatch <<< "$(expected_assignment "$wave" "$gpu")"
    directory="$RUN_DIR/wave${wave}/gpu${gpu}-${band}-${mode}"
    jq -e '.status == "PASS" and .evidence_valid == true and .performance_promotable == false' \
      "$directory/completion-status.json" >/dev/null
  done
}

run_wave 1
run_wave 2
python3 "$CROSSBAND_GATES" compare-crossover \
  --root "$RUN_DIR" \
  --suite "$SUITE" \
  --prompt-builder "$PROMPT_BUILDER" \
  --output "$RUN_DIR/comparison.json"
jq -e '
  .evidence_passed == true
  and (.classification == "PASS_CROSSBAND_MTP_RETENTION_WIN"
       or .classification == "VALID_CROSSBAND_NO_MTP_WIN")
  and .performance_promotable == false
  and .localmaxxing_submission_ready == false
' "$RUN_DIR/comparison.json" >/dev/null
BODY_COMPLETED=1
echo "$RUN_DIR"
