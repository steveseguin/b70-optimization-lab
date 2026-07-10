#!/usr/bin/env bash
set -euo pipefail

# Diagnostic Level Zero kernel profile for the current strict-valid Qwen27
# recipe. This uses offline LLM mode because unitrace does not flush timing
# summaries from the online server's spawned EngineCore process on this host.
# It is a kernel-attribution tool, never a throughput or quality result.
# STATUS: CLOSED/RETAINED. Device timing made 8 tokens exceed 15 minutes and
# did not complete. Prefer profile-current-recipe-regions.sh.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
UNITRACE="${UNITRACE:-/home/steve/src/pti-gpu/build-unitrace/unitrace}"
PYTHON="${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
GPU_INDEX="${GPU_INDEX:-0}"
MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
RUN_ROOT="${RUN_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/profiles}"
RUN_DIR="${RUN_DIR:-$RUN_ROOT/qwen27-current-recipe-unitrace-offline-$STAMP}"
SESSION="qwen27${STAMP//[^[:alnum:]]/}"
WARMUP_TOKENS="${WARMUP_TOKENS:-128}"
PROFILE_TOKENS="${PROFILE_TOKENS:-8}"

if [[ ! -x "$UNITRACE" ]]; then
  echo "unitrace executable not found: $UNITRACE" >&2
  exit 2
fi
if [[ ! -x "$PYTHON" ]]; then
  echo "Python executable not found: $PYTHON" >&2
  exit 2
fi
if [[ ! -d "$MODEL_DIR" ]]; then
  echo "Model directory not found: $MODEL_DIR" >&2
  exit 2
fi
for value_name in WARMUP_TOKENS PROFILE_TOKENS; do
  value="${!value_name}"
  if [[ ! "$value" =~ ^[1-9][0-9]*$ ]]; then
    echo "$value_name must be a positive integer, got: $value" >&2
    exit 2
  fi
done

mkdir -p "$RUN_DIR/unitrace"
export ZE_AFFINITY_MASK="$GPU_INDEX"
export ONEAPI_DEVICE_SELECTOR=level_zero:0
export PYTHONPATH="/home/steve/src/vllm${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export VLLM_TARGET_DEVICE=xpu
export VLLM_NO_USAGE_STATS=1
export VLLM_ENABLE_V1_MULTIPROCESSING=0
export XPU_GRAPH=1
export VLLM_XPU_ENABLE_XPU_GRAPH=1
export VLLM_XPU_FORCE_GRAPH_WITH_COMM=1
export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1
export VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1
export VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0
export VLLM_XPU_GDN_REPLAYSSM_SPEC=1
export VLLM_XPU_GDN_REPLAYSSM_SPEC_CACHE_LEN=8
export VLLM_XPU_GDN_REPLAYSSM_TORCH_FALLBACK=0
export VLLM_XPU_GDN_REPLAYSSM_STAGE_CONV_TORCH_FALLBACK=0
export VLLM_XPU_GDN_REPLAYSSM_COMMIT_IN_FORWARD=1
export VLLM_XPU_GDN_REPLAYSSM_SLOT_MGMT_TORCH_FALLBACK=1
export VLLM_XPU_LM_HEAD_INT8=1
export VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16
export VLLM_XPU_DRAFT_LM_HEAD_INT4=1
export VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128
export VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16

cat > "$RUN_DIR/identity.env" <<EOF
classification=diagnostic_level_zero_kernel_profile_not_headline
date_utc=$STAMP
model_dir=$MODEL_DIR
gpu_index=$GPU_INDEX
topology=offline_llm_v1_multiprocessing_disabled
warmup_tokens=$WARMUP_TOKENS
profile_tokens=$PROFILE_TOKENS
num_speculative_tokens=3
compilation_config={"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}
unitrace=$UNITRACE
unitrace_version=$($UNITRACE --version | head -n 1)
unitrace_source_commit=a5bab309f4ffdd78bd127035c46f5f75371160f8
session=$SESSION
EOF

cd "$ROOT"
args=(
  "$UNITRACE"
  --device-timing
  --verbose
  --pid
  --follow-child-process 0
  --devices-to-sample 0
  --session "$SESSION"
  --start-paused
  --result-dir "$RUN_DIR/unitrace"
  "$PYTHON"
  experiments/qwen36-27b-autoround-int4-b70/scripts/profile-current-recipe-unitrace-driver.py
  --model "$MODEL_DIR"
  --unitrace "$UNITRACE"
  --session "$SESSION"
  --output "$RUN_DIR/profiled-response.json"
  --warmup-tokens "$WARMUP_TOKENS"
  --profile-tokens "$PROFILE_TOKENS"
)
printf '%q ' "${args[@]}" > "$RUN_DIR/unitrace-command.txt"
printf '\n' >> "$RUN_DIR/unitrace-command.txt"

set +e
"${args[@]}" > "$RUN_DIR/driver.stdout.log" 2>&1
unitrace_rc=$?
set -e
echo "$unitrace_rc" > "$RUN_DIR/unitrace.rc"

mapfile -t timing_files < <(
  find "$RUN_DIR/unitrace" -type f -name device_timing.txt -size +200c | sort
)
if ((${#timing_files[@]} == 0)); then
  echo "unitrace produced no device_timing.txt evidence" >&2
  exit 5
fi
{
  for timing_file in "${timing_files[@]}"; do
    echo "=== $timing_file ==="
    cat "$timing_file"
  done
} > "$RUN_DIR/unitrace-summary.txt"

if ((unitrace_rc != 0)); then
  echo "unitrace/driver exited with $unitrace_rc; evidence retained in $RUN_DIR" >&2
  exit "$unitrace_rc"
fi
echo "$RUN_DIR"
