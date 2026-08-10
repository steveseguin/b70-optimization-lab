#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LANE="$ROOT/experiments/qwen36-27b-q8-gguf-b70"
UNITRACE="/home/steve/src/pti-gpu/build-unitrace/unitrace"
UNITRACE_SHA256="5aaca1f418a212a1d298cac27afb6c471bf1fcf47a1622e0c20d1a2cf43fc85a"
LAUNCHER="$LANE/scripts/serve-target-only.sh"
LAUNCHER_SHA256="fa9475956c9de8dc225e23c13b25e5851bc545ae24ec1ede92939f3ae7f08010"
CAPTURE="$LANE/scripts/capture-exact-tokens.py"
CAPTURE_SHA256="94595b6962e64981723a063b6ec23b80c3701a22d0e256e85b596e6bf75f5b05"
TRACE_SUMMARIZER="$LANE/scripts/summarize-vdr2-unitrace.py"
TRACE_SUMMARIZER_SHA256="6bb552e74e83f719ff842bf20102e5a0942a43fe165be872ddf32cdd2dd852ad"
RUNTIME_MANIFEST="$LANE/runtime-manifest-q8-vdr2-candidate.json"
RUNTIME_MANIFEST_SHA256="4119790a79c55d158e7257d4fa0d95be0ca34639807c1a71ce87b60d6fdc1b49"
MODEL_MANIFEST="$LANE/model-manifest.json"
MODEL="/mnt/usb-models/models/qwen36-27b-q8-gguf/Qwen3.6-27B-Q8_0.gguf"
MODEL_SHA256="f93f517f38e696d35a1a7df2c0e3155a64f4c4dcd662107a146ae263f7fb14ce"
MODEL_BYTES="28595763424"
LLAMA_SERVER="/mnt/fast-ai/runtime/llama.cpp-15586e2d-qwen27-vdr2-hybrid/llama-server"
LLAMA_SERVER_SHA256="1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7"
SUITE="$LANE/c2-long-context-suite-v1.json"
PROMPT_BUILDER="$ROOT/scripts/bench-openai-long-context-suite.py"
ORACLE="/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal2-prefill-ub1024-isolated-gpu0-short-prefill-ub1024-ub1024-20260810T043918.549062817Z/oracle-snapshots/comparison-oracle.json"
ORACLE_SHA256="ef2929dc76c63d52c195efb36465c4b7736c4556fb9d08d87cff9716263ef529"
CANARY_SUITE="$ROOT/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json"
CANARY_ORACLE="/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/qwen36-27b-q8_0-f16kv-short-dnn0-exact-20260808T232639Z/exact-tokens.json"
CANARY_SHA256="e4477808823cdf9bb182d5abc4788cee216011a0195cf49bf03a7bda35f5dbcc"
KERNEL="reorder_mul_mat_vec_q8_0_q8_1_sycl"
TRACE_CAP_BYTES=$((100 * 1024 * 1024))
CONTROL_TIMEOUT_S=900
BASELINE_TOKEN_NS=60281000
RESUME_DECODE_MIN=100
TRACE_CYCLES_MIN=45
TRACE_CYCLES_MAX=55
PORT="${PORT:-19940}"
STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%S.%NZ)}"
RUN_DIR="${RUN_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/profile-vdr2-short-${STAMP}}"
TRACE_DIR="${TRACE_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/traces/profile-vdr2-short-${STAMP}}"
SESSION="${SESSION:-QwenVDR2$(printf '%s' "$STAMP-$$" | sha256sum | cut -c1-48)}"
MODE="${1:-}"

[[ "$PORT" =~ ^[0-9]+$ ]] && (( PORT >= 1024 && PORT <= 65535 )) || {
  echo "PORT must be 1024..65535" >&2; exit 2;
}
[[ "$SESSION" =~ ^[[:alnum:]]{40,64}$ ]] || {
  echo "SESSION must contain 40..64 alphanumeric characters" >&2; exit 2;
}
for path in "$RUN_DIR" "$TRACE_DIR"; do
  [[ "$path" == /* && "$path" != / && "$path" != *$'\n'* ]] || {
    echo "unsafe output path: $path" >&2; exit 2;
  }
done
[[ "$(readlink -m "$RUN_DIR")" != "$(readlink -m "$TRACE_DIR")" ]] || {
  echo "RUN_DIR and TRACE_DIR must be separate" >&2; exit 2;
}
case "$(readlink -m "$RUN_DIR")/" in "$(readlink -m "$TRACE_DIR")/"*)
  echo "RUN_DIR and TRACE_DIR must not contain one another" >&2; exit 2;;
esac
case "$(readlink -m "$TRACE_DIR")/" in "$(readlink -m "$RUN_DIR")/"*)
  echo "RUN_DIR and TRACE_DIR must not contain one another" >&2; exit 2;;
esac

server_cmd=(
  "$LLAMA_SERVER" -m /proc/self/fd/10
  --alias qwen36-27b-q8_0-target-only --host 127.0.0.1 --port "$PORT"
  -dev SYCL0 -ngl 99 -c 32768 -np 1 -b 1024 -ub 1024 -t 8
  --threads-http 6 --poll 50 -lv 4 -ctk f16 -ctv f16 -fa on
  --spec-type none --reasoning off --ctx-checkpoints 0 --cache-ram 0
  --no-cache-idle-slots --no-context-shift --slots --metrics --jinja
  --no-kv-unified --cont-batching
)
unitrace_cmd=(
  "$UNITRACE" --device-timing --kernel-submission --verbose --pid
  --devices-to-sample 0 --follow-child-process 0 --start-paused
  --session "$SESSION" --include-kernels "$KERNEL" --result-dir "$TRACE_DIR"
  "${server_cmd[@]}"
)
capture_cmd=(
  python3 "$CAPTURE" --base-url "http://127.0.0.1:$PORT" --suite "$SUITE"
  --prompt-builder "$PROMPT_BUILDER" --band short --max-tokens 512
  --model-sha256 "$MODEL_SHA256" --runtime-sha256 "$LLAMA_SERVER_SHA256"
  --cache-type-k f16 --cache-type-v f16 --ctx-size 32768
  --sycl-dnn-enabled 0 --sycl-opt-enabled 1 --out "$RUN_DIR/exact-tokens.json"
  --ignore-eos --slot-id 0 --require-exact-token-count --require-full-512-metric
  --require-post-512-canary --post-512-canary-suite "$CANARY_SUITE"
  --post-512-canary-oracle "$RUN_DIR/sealed-128-oracle.json"
  --post-512-canary-oracle-sha256 "$CANARY_SHA256"
  --post-512-canary-prompt-id incident-retrospective
  --oracle-json "$RUN_DIR/comparison-oracle.json"
)

print_plan() {
  printf 'classification=profiler-only\nperformance_promotable=false\n'
  printf 'run_dir=%s\ntrace_dir=%s\nsession=%s\n' "$RUN_DIR" "$TRACE_DIR" "$SESSION"
  printf 'control_timeout_s=%s\ntrace_cap_bytes=%s\n' "$CONTROL_TIMEOUT_S" "$TRACE_CAP_BYTES"
  printf 'baseline_token_ns=%s\n' "$BASELINE_TOKEN_NS"
  printf 'capture_window_target_decode_cycles=50\n'
  printf 'resume_decode_min=%s\ntrace_cycles_min=%s\ntrace_cycles_max=%s\n' \
    "$RESUME_DECODE_MIN" "$TRACE_CYCLES_MIN" "$TRACE_CYCLES_MAX"
  printf 'runtime_verify='; printf '%q ' env -u LD_PRELOAD \
    RUNTIME_MANIFEST="$RUNTIME_MANIFEST" LLAMA_SERVER="$LLAMA_SERVER" \
    "$LAUNCHER" --verify-runtime-bundle \
    "$RUN_DIR/llama-server-ldd.txt" "$RUN_DIR/runtime-resolved-files.sha256" \
    "$RUN_DIR/runtime-bundle-verification.json"; printf '\n'
  printf 'server_environment='; printf '%q ' \
    LD_LIBRARY_PATH="$(dirname "$LLAMA_SERVER"):<oneapi-LD_LIBRARY_PATH>" \
    ONEAPI_DEVICE_SELECTOR='level_zero:*' ZE_AFFINITY_MASK=0 ZES_ENABLE_SYSMAN=1 \
    UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1 GGML_SYCL_ENABLE_VMM=1 \
    GGML_SYCL_ENABLE_GRAPH=0 GGML_SYCL_GRAPH_CACHE_SIZE=0 \
    GGML_SYCL_ENABLE_DNN=0 GGML_SYCL_ENABLE_OPT=1 GGML_SYCL_FA_ONEDNN=1 \
    GGML_SYCL_FA_ONEDNN_MAX_KV=0 GGML_SYCL_ENABLE_MKL_FA=1 \
    GGML_SYCL_ENABLE_FLASH_ATTN=1; printf '\n'
  printf 'unitrace='; printf '%q ' "${unitrace_cmd[@]}"; printf '\n'
  printf 'capture='; printf '%q ' "${capture_cmd[@]}"; printf '\n'
}

if [[ "$MODE" == "--print-plan" ]]; then
  print_plan
  exit 0
elif [[ -n "$MODE" ]]; then
  echo "usage: $0 [--print-plan]" >&2
  exit 2
fi

# Deliberately no retry mode: one preflight, one server, one capture, one control window.
for frozen in \
  "$UNITRACE:$UNITRACE_SHA256" "$LAUNCHER:$LAUNCHER_SHA256" \
  "$CAPTURE:$CAPTURE_SHA256" "$RUNTIME_MANIFEST:$RUNTIME_MANIFEST_SHA256" \
  "$TRACE_SUMMARIZER:$TRACE_SUMMARIZER_SHA256" \
  "$LLAMA_SERVER:$LLAMA_SERVER_SHA256" "$ORACLE:$ORACLE_SHA256" \
  "$CANARY_ORACLE:$CANARY_SHA256"; do
  frozen_path="${frozen%:*}"; frozen_sha="${frozen##*:}"
  [[ "$(sha256sum "$frozen_path" | awk '{print $1}')" == "$frozen_sha" ]] || {
    echo "frozen input mismatch: $frozen_path" >&2; exit 2;
  }
done
[[ "$(stat -c %s "$MODEL")" == "$MODEL_BYTES" ]] || { echo "model size mismatch" >&2; exit 2; }
[[ "$(sha256sum "$MODEL" | awk '{print $1}')" == "$MODEL_SHA256" ]] || { echo "model hash mismatch" >&2; exit 2; }
[[ ! -e "$RUN_DIR" && ! -e "$TRACE_DIR" ]] || { echo "output directory already exists" >&2; exit 2; }
mkdir -p "$RUN_DIR" "$(dirname "$TRACE_DIR")"
print_plan > "$RUN_DIR/profile-plan.env"
cp -- "$ORACLE" "$RUN_DIR/comparison-oracle.json"
cp -- "$CANARY_ORACLE" "$RUN_DIR/sealed-128-oracle.json"

sanitize_runtime_env() {
  local name
  while IFS='=' read -r name _; do
    case "$name" in
      GGML_*|SYCL_*|ZE_*|ZES_*|UR_*|ONEAPI_DEVICE_SELECTOR|LD_PRELOAD) unset "$name" ;;
      LLAMA_*) [[ "$name" == LLAMA_SERVER ]] || unset "$name" ;;
    esac
  done < <(env)
}
sanitize_runtime_env

RUNTIME_MANIFEST="$RUNTIME_MANIFEST" LLAMA_SERVER="$LLAMA_SERVER" \
  "$LAUNCHER" --verify-runtime-bundle \
  "$RUN_DIR/llama-server-ldd.txt" "$RUN_DIR/runtime-resolved-files.sha256" \
  "$RUN_DIR/runtime-bundle-verification.json"

mkdir -p "/run/user/$(id -u)/qwen36-b70-gpu-leases" \
  "/run/user/$(id -u)/qwen36-b70-port-leases"
exec 11>"/run/user/$(id -u)/qwen36-b70-gpu-leases/gpu0.lock"
exec 13>"/run/user/$(id -u)/qwen36-b70-gpu-leases/gpu1.lock"
exec 14>"/run/user/$(id -u)/qwen36-b70-gpu-leases/gpu2.lock"
exec 15>"/run/user/$(id -u)/qwen36-b70-gpu-leases/gpu3.lock"
for lease_fd in 11 13 14 15; do
  flock -n "$lease_fd" || { echo "one or more GPUs are leased" >&2; exit 2; }
done
exec 12>"/run/user/$(id -u)/qwen36-b70-port-leases/port${PORT}.lock"
flock -n 12 || { echo "port $PORT is leased" >&2; exit 2; }

for gpu in 0 1 2 3; do
  timeout 20 xpu-smi stats -d "$gpu" > "$RUN_DIR/xpu-smi-before-gpu${gpu}.txt"
  used="$(awk -F '|' '/GPU Memory Used/{gsub(/[^0-9.]/, "", $3); print int($3); exit}' "$RUN_DIR/xpu-smi-before-gpu${gpu}.txt")"
  [[ -n "$used" ]] && (( used <= 256 )) || { echo "GPU $gpu is not idle" >&2; exit 2; }
done
ss -H -ltn "sport = :$PORT" | grep -q . && { echo "port already in use: $PORT" >&2; exit 2; }

exec 10<"$MODEL"
flock -s -n 10 || { echo "could not lock model" >&2; exit 2; }
set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null
set -u
export LD_LIBRARY_PATH="$(dirname "$LLAMA_SERVER")${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export ONEAPI_DEVICE_SELECTOR='level_zero:*' ZE_AFFINITY_MASK=0 ZES_ENABLE_SYSMAN=1
export UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1 GGML_SYCL_ENABLE_VMM=1
export GGML_SYCL_ENABLE_GRAPH=0 GGML_SYCL_GRAPH_CACHE_SIZE=0 GGML_SYCL_ENABLE_DNN=0
export GGML_SYCL_ENABLE_OPT=1 GGML_SYCL_FA_ONEDNN=1 GGML_SYCL_FA_ONEDNN_MAX_KV=0
export GGML_SYCL_ENABLE_MKL_FA=1 GGML_SYCL_ENABLE_FLASH_ATTN=1

{
  echo 'evidence_class=profiler-only'
  echo 'performance_promotable=false'
  echo 'runtime_profile=q8-vdr2-candidate'
  echo 'full512_band=short'
  echo 'promotion_profile=prefill-ub1024'
  echo 'require_all_gpus_idle=1'
  echo "unitrace_sha256=$UNITRACE_SHA256"
  echo "launcher_sha256=$LAUNCHER_SHA256"
  echo "capture_sha256=$CAPTURE_SHA256"
  echo "runtime_manifest_sha256=$RUNTIME_MANIFEST_SHA256"
  echo "model_sha256=$MODEL_SHA256"
  echo "llama_server_sha256=$LLAMA_SERVER_SHA256"
  echo "session=$SESSION"
  echo "kernel=$KERNEL"
} > "$RUN_DIR/profile-identity.env"

unitrace_pid=''
capture_pid=''
cleanup() {
  if [[ -n "$capture_pid" ]] && kill -0 "$capture_pid" 2>/dev/null; then kill -TERM "$capture_pid" 2>/dev/null || true; fi
  if [[ -n "$unitrace_pid" ]] && kill -0 "$unitrace_pid" 2>/dev/null; then kill -TERM -- "-$unitrace_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

live_deadline=$((SECONDS + CONTROL_TIMEOUT_S))
setsid timeout --signal=TERM --kill-after=15s "$CONTROL_TIMEOUT_S" \
  "${unitrace_cmd[@]}" > "$RUN_DIR/server.stdout.log" 2>&1 &
unitrace_pid=$!
deadline=$live_deadline
until curl -fsS "http://127.0.0.1:$PORT/v1/models" > "$RUN_DIR/models.json" 2> "$RUN_DIR/models.err"; do
  kill -0 "$unitrace_pid" 2>/dev/null || { echo "unitrace/server exited before readiness" >&2; exit 1; }
  (( SECONDS < deadline )) || { echo "server readiness timeout" >&2; exit 1; }
  sleep 2
done
grep -Eq 'offloaded[[:space:]]+65/65 layers to GPU' "$RUN_DIR/server.stdout.log" || {
  echo "full 65/65 GPU offload was not observed" >&2; exit 1;
}

capture_budget=$((live_deadline - SECONDS))
(( capture_budget > 0 )) || { echo "live deadline expired before capture" >&2; exit 1; }
timeout --signal=TERM --kill-after=15s "$capture_budget" \
  "${capture_cmd[@]}" > "$RUN_DIR/exact-tokens.stdout.log" 2>&1 &
capture_pid=$!
resume_count=0 pause_count=0 stop_count=0 control_failed=0
resume_decoded=0 pause_decoded=0
resume_attempted=0 pause_attempted=0 stop_attempted=0
control_deadline=$((SECONDS + CONTROL_TIMEOUT_S))
: > "$RUN_DIR/profile-control.log"
control_once() {
  local action="$1" status
  case "$action" in
    resume) (( resume_attempted == 0 )) || return 1; resume_attempted=1 ;;
    pause) (( pause_attempted == 0 )) || return 1; pause_attempted=1 ;;
    stop) (( stop_attempted == 0 )) || return 1; stop_attempted=1 ;;
    *) return 2 ;;
  esac
  set +e
  "$UNITRACE" "--$action" "$SESSION" >> "$RUN_DIR/profile-control.log" 2>&1
  status=$?
  set -e
  printf '%s action=%s status=%s\n' "$(date -u +%FT%TZ)" "$action" "$status" >> "$RUN_DIR/profile-control.log"
  if (( status == 0 )); then
    case "$action" in
      resume) resume_count=1 ;;
      pause) pause_count=1 ;;
      stop) stop_count=1 ;;
    esac
  fi
  return "$status"
}
while (( stop_count == 0 )); do
  latest_task0_decoded="$(
    sed -nE 's/.*task 0 \| n_decoded = +([0-9]+),.*/\1/p' \
      "$RUN_DIR/server.stdout.log" | tail -n 1
  )"
  latest_task0_decoded="${latest_task0_decoded:-0}"
  trace_bytes="$(du -sb "$TRACE_DIR" 2>/dev/null | awk '{print $1}')"; trace_bytes="${trace_bytes:-0}"
  if (( trace_bytes > TRACE_CAP_BYTES )); then
    printf '%s cap_exceeded bytes=%s\n' "$(date -u +%FT%TZ)" "$trace_bytes" >> "$RUN_DIR/profile-control.log"
    control_failed=1
    (( resume_count == 0 )) || control_once pause || true
    control_once stop || true
    break
  fi
  if (( resume_count == 0 && latest_task0_decoded >= RESUME_DECODE_MIN )); then
    if control_once resume; then
      resume_decoded=$latest_task0_decoded
      printf '%s resumed observed_n_decoded=%s\n' \
        "$(date -u +%FT%TZ)" "$resume_decoded" >> "$RUN_DIR/profile-control.log"
    else
      control_failed=1
      break
    fi
  fi
  if (( resume_count == 1 && pause_count == 0 && latest_task0_decoded >= resume_decoded + TRACE_CYCLES_MIN )); then
    pause_decoded=$latest_task0_decoded
    control_once pause || control_failed=1
    control_once stop || control_failed=1
    (( control_failed == 1 )) || printf '%s paused_stopped observed_n_decoded=%s\n' \
      "$(date -u +%FT%TZ)" "$pause_decoded" >> "$RUN_DIR/profile-control.log"
    break
  fi
  if ! kill -0 "$capture_pid" 2>/dev/null; then control_failed=1; break; fi
  if (( SECONDS >= control_deadline )); then control_failed=1; break; fi
  sleep 0.1
done
if (( stop_count == 0 )); then
  (( resume_count == 0 )) || control_once pause || true
  control_once stop || true
fi

set +e
wait "$capture_pid"; capture_status=$?
capture_pid=''
set -e
kill -TERM -- "-$unitrace_pid" 2>/dev/null || true
set +e
wait "$unitrace_pid"; unitrace_status=$?
set -e
unitrace_pid=''
for _ in $(seq 1 30); do
  ss -H -ltn "sport = :$PORT" | grep -q . || break
  sleep 1
done
ss -H -ltn "sport = :$PORT" | grep -q . && { echo "server port remained open" >&2; exit 1; }

for gpu in 0 1 2 3; do
  timeout 20 xpu-smi stats -d "$gpu" > "$RUN_DIR/xpu-smi-after-gpu${gpu}.txt"
  used="$(awk -F '|' '/GPU Memory Used/{gsub(/[^0-9.]/, "", $3); print int($3); exit}' "$RUN_DIR/xpu-smi-after-gpu${gpu}.txt")"
  [[ -n "$used" ]] && (( used <= 256 )) || { echo "GPU $gpu did not return idle" >&2; exit 1; }
done

observed_decode_cycles=$((pause_decoded - resume_decoded))
(( observed_decode_cycles >= TRACE_CYCLES_MIN && observed_decode_cycles <= TRACE_CYCLES_MAX )) || {
  echo "observed trace window was not ${TRACE_CYCLES_MIN}..${TRACE_CYCLES_MAX} decode cycles: $observed_decode_cycles" >&2
  exit 1
}
python3 "$TRACE_SUMMARIZER" --trace-dir "$TRACE_DIR" --kernel "$KERNEL" \
  --expected-decode-cycles "$observed_decode_cycles" --baseline-token-ns "$BASELINE_TOKEN_NS" \
  --out "$RUN_DIR/unitrace-summary.json"

python3 - "$RUN_DIR/exact-tokens.json" "$RUN_DIR/exact-result-gate.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
rows = d.get("rows") or []
checks = {
    "two_short_rows": len(rows) == 2,
    "all_rows_512": all(r.get("token_count") == 512 for r in rows),
    "all_rows_d511": all((r.get("full_512_metric") or {}).get("interval_count") == 511 for r in rows),
    "intrinsic_passed": (d.get("intrinsic_gate") or {}).get("passed") is True,
    "oracle_exact": (d.get("oracle_comparison") or {}).get("status") == "PASS_ORACLE_EXACT",
    "canary_passed": (d.get("post_512_canary") or {}).get("passed") is True,
}
out = {"evidence_class": "profiler-only", "performance_promotable": False,
       "checks": checks, "passed": all(checks.values())}
open(sys.argv[2], "w").write(json.dumps(out, indent=2, sort_keys=True) + "\n")
raise SystemExit(0 if out["passed"] else 1)
PY

final_trace_bytes="$(du -sb "$TRACE_DIR" | awk '{print $1}')"
find "$TRACE_DIR" -type f -print0 | sort -z | xargs -0 sha256sum > "$RUN_DIR/trace-files.sha256"
[[ -s "$RUN_DIR/trace-files.sha256" ]] || { echo "trace file manifest is empty" >&2; exit 1; }
sha256sum -c "$RUN_DIR/trace-files.sha256" >/dev/null
{
  echo "resume_count=$resume_count"
  echo "pause_count=$pause_count"
  echo "stop_count=$stop_count"
  echo "resume_attempted=$resume_attempted"
  echo "pause_attempted=$pause_attempted"
  echo "stop_attempted=$stop_attempted"
  echo "resume_decoded=$resume_decoded"
  echo "pause_decoded=$pause_decoded"
  echo "observed_decode_cycles=$observed_decode_cycles"
  echo "control_failed=$control_failed"
  echo "capture_status=$capture_status"
  echo "unitrace_status=$unitrace_status"
  echo "unitrace_status_note=group_TERM_after_explicit_profiler_stop_may_be_nonzero"
  echo "trace_bytes=$final_trace_bytes"
  echo "trace_cap_bytes=$TRACE_CAP_BYTES"
  echo "trace_files_manifest_sha256=$(sha256sum "$RUN_DIR/trace-files.sha256" | awk '{print $1}')"
} > "$RUN_DIR/profile-control-summary.env"
(( resume_count == 1 && pause_count == 1 && stop_count == 1 && control_failed == 0 )) || exit 1
(( capture_status == 0 && final_trace_bytes <= TRACE_CAP_BYTES )) || exit 1

find "$RUN_DIR" -maxdepth 1 -type f ! -name artifacts.sha256 -print0 | sort -z | xargs -0 sha256sum > "$RUN_DIR/artifacts.sha256"
echo "$RUN_DIR"
