#!/usr/bin/env bash
set -euo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "$here/../../.." && pwd)
mode=${1:-}
gpu_pair=${2:-}
arm_root=${3:-}
quality_baseline=${4:-}

if [[ "$mode" != "spec" && "$mode" != "nospec" ]]; then
  printf 'usage: %s spec|nospec GPU0,GPU1 ARM_ROOT [QUALITY_BASELINE]\n' "$0" >&2
  exit 2
fi
if [[ ! "$gpu_pair" =~ ^[0-9]+,[0-9]+$ || -z "$arm_root" ]]; then
  printf 'invalid GPU pair or arm root\n' >&2
  exit 2
fi
if [[ -e "$arm_root" ]]; then
  printf 'refusing existing arm root: %s\n' "$arm_root" >&2
  exit 2
fi
if systemctl is-active --quiet muse-glimmer-bf16-fleet.service \
  || systemctl is-active --quiet muse-glimmer-frontdoor.service; then
  printf 'Muse services must be stopped before validation\n' >&2
  exit 3
fi

source_root=${SOURCE_ROOT:-/home/steve/src}
venv=${VENV:-/home/steve/.venvs/vllm-xpu}
model_dir=${MODEL_DIR:-/mnt/usb-models/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}
stage=${STAGE:-/home/steve/src/vllm-xpu-kernels}
oneccl=${ONECCL_INSTALL_DIR:-/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public}
port=${PORT:-19622}
stamp=${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}
label=${LABEL:-$(basename "$arm_root")}
suite="$arm_root/validation-suite.json"

mkdir -p -- "$arm_root"
"$here/build-validation-suite.py" --repo "$repo" --out "$suite" \
  > "$arm_root/suite-build.log"

verify_tree() {
  local tree=$1 expected_head=$2 expected_diff=$3 name=$4
  local actual_head actual_diff
  actual_head=$(git -C "$tree" rev-parse HEAD)
  actual_diff=$(git -C "$tree" diff --binary | sha256sum | awk '{print $1}')
  if [[ "$actual_head" != "$expected_head" || "$actual_diff" != "$expected_diff" ]]; then
    printf '%s source mismatch: head=%s diff=%s\n' "$name" "$actual_head" "$actual_diff" >&2
    exit 3
  fi
}
verify_tree "$source_root/vllm" e7213ba8e13b74d7bfa3cbc05435a45df90eb76a \
  dcf84454f64bdeca546aa1697f4cd6af89fa95bb56f80ed314ad4d364e134b24 vllm
verify_tree "$source_root/vllm-xpu-kernels" 3b4effeeffd83f6ef4696bbe7e76d924a0e9d171 \
  edcb9314b43d6990474dfb5d64e3716e8d4c33618ec0e3fbd11ae671e47c8c1f kernels

PYTHON="$venv/bin/python" MODEL_DIR="$model_dir" \
  "$repo/repro/qwen36-27b-autoround-int4-b70/scripts/download-model.sh" \
  > "$arm_root/model-verify.log"

# Clear inherited experiment state before installing the exact recorded
# identity. Host/runtime paths are explicitly repopulated below.
while IFS= read -r name; do
  case "$name" in
    VLLM_*|QWEN36_27B_*|XPU_GRAPH|COMPILATION_CONFIG|CCL_*|ONECCL_*|SERVER_*|ZE_AFFINITY_MASK|ONEAPI_DEVICE_SELECTOR|QUALITY_*|BENCH_*|RUN_SMOKE|RUN_BENCH|RUN_QUALITY|REQUEST_EXTRA_JSON|CANDIDATE_ENTRYPOINT)
      unset "$name"
      ;;
  esac
done < <(compgen -e)
unset PYTHONPATH LD_PRELOAD LD_LIBRARY_PATH TORCHINDUCTOR_CACHE_DIR

# shellcheck source=../../../repro/qwen36-27b-autoround-int4-b70/configs/record.env
source "$repo/repro/qwen36-27b-autoround-int4-b70/configs/record.env"

export SOURCE_ROOT="$source_root"
export VLLM_SOURCE_TREE="$source_root/vllm"
export VLLM_XPU_KERNELS_SOURCE_TREE="$source_root/vllm-xpu-kernels"
export MODEL_DIR="$model_dir"
export QWEN36_27B_AR_VENV="$venv"
export STAGE="$stage"
export VLLM_XPU_KERNELS_SRC="$stage"
export ONECCL_INSTALL_DIR="$oneccl"
export HF_HOME=/mnt/usb-models/llm-cache/hf
export GPU_INDEX="$gpu_pair"
export TENSOR_PARALLEL_SIZE=2
export PORT="$port"
export STAMP="$stamp"
export LABEL="$label"
export SERVED_MODEL_NAME=qwen27-int4-independent-validation
export SUITE="$suite"
export RUN_ROOT="$arm_root"
export RUN_DIR="$arm_root/run"
export OUT_DIR="$arm_root/data"
export BENCH_OUT="$arm_root/data/bench.json"
export QUALITY_OUT="$arm_root/data/quality.json"
export SMOKE_OUT="$arm_root/data/smoke.json"
export SUMMARY_OUT="$arm_root/data/summary-legacy.json"
export VLLM_CACHE_ROOT=${VALIDATION_VLLM_CACHE_ROOT:-/mnt/usb-models/llm-runtime/vllm-cache/qwen27-independent-validation-20260815}
export BENCH_MAX_TOKENS=512
export BENCH_METRIC_TOKENS=100
export QUALITY_REPEAT_RUNS=32
export QUALITY_LONG_CONTEXT_TOKENS=1024
export REQUEST_EXTRA_JSON='{"chat_template_kwargs":{"enable_thinking":false}}'
export QUALITY_BASELINE_JSON="$quality_baseline"
if [[ "$mode" == "spec" ]]; then
  export QWEN36_27B_ENABLE_MTP=1
  export NUM_SPECULATIVE_TOKENS=3
else
  export QWEN36_27B_ENABLE_MTP=0
  unset QWEN36_27B_SPECULATIVE_CONFIG
fi

printf 'mode=%s\ngpu_pair=%s\narm_root=%s\nquality_baseline=%s\n' \
  "$mode" "$gpu_pair" "$arm_root" "$quality_baseline" > "$arm_root/arm.env"

exec 9>/tmp/b70-benchmark.lock
if ! flock -n 9; then
  printf 'GPU benchmark lock is held\n' >&2
  exit 4
fi

set +e
"$repo/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-fullgraph-transaction-candidate.sh" \
  > "$arm_root/runner.stdout.log" 2>&1
runner_rc=$?
set -e
printf '%s\n' "$runner_rc" > "$arm_root/runner.exit-code"

if [[ -s "$BENCH_OUT" ]]; then
  "$venv/bin/python" "$repo/scripts/qualify_realistic_window_metrics.py" \
    "$BENCH_OUT" --in-place > "$arm_root/qualify.log"
fi
find "$arm_root" -type f ! -name SHA256SUMS.pre-manifest -print0 \
  | sort -z | xargs -0 sha256sum \
  > "$arm_root/SHA256SUMS.pre-manifest"
exit "$runner_rc"
