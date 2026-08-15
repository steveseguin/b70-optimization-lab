#!/usr/bin/env bash
set -euo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "$here/../../.." && pwd)
acceptance_mode=${1:-standard}
if [[ "$acceptance_mode" != "standard" && "$acceptance_mode" != "zero" ]]; then
  printf 'usage: %s standard|zero\n' "$0" >&2
  exit 2
fi
source_root=${SOURCE_ROOT:-/home/steve/src}
venv=${VENV:-/home/steve/.venvs/vllm-xpu}
model_dir=${MODEL_DIR:-/mnt/usb-models/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}
graph_stage=${STAGE:-$repo/experiments/qwen27_graphsafe_flash_attention/staged-package}
oneccl=${ONECCL_INSTALL_DIR:-/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public}
stamp=${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}
run_root=${RUN_ROOT:-/mnt/usb-models/bench-results/qwen36-27b-autoround-int4-b70/correctness-recovery-$acceptance_mode-$stamp}
port=${PORT:-19622}
gpu_pair=${GPU_INDEX:-0,1}

if [[ -e "$run_root" ]]; then
  printf 'refusing existing output root: %s\n' "$run_root" >&2
  exit 2
fi
if systemctl is-active --quiet muse-glimmer-bf16-fleet.service \
  || systemctl is-active --quiet muse-glimmer-frontdoor.service; then
  printf 'Muse services must remain stopped\n' >&2
  exit 3
fi

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

mkdir -p -- "$run_root"
cp -- "$here/first-divergence-suite.json" "$run_root/suite.json"

# Remove inherited experiment settings, then install the exact recorded arm.
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
export ONECCL_INSTALL_DIR="$oneccl"
export STAGE="$graph_stage"
export VLLM_XPU_KERNELS_SRC="$graph_stage"
export GPU_INDEX="$gpu_pair"
export ZE_AFFINITY_MASK="$gpu_pair"
export ONEAPI_DEVICE_SELECTOR=level_zero:0,1
export PORT="$port"
export LABEL="qwen27-fixed4-verifier-trace-$acceptance_mode"
export SERVED_MODEL_NAME="qwen27-fixed4-verifier-trace-$acceptance_mode"
export SUITE="$run_root/suite.json"
export RUN_ROOT="$run_root"
export RUN_DIR="$run_root/run"
export OUT_DIR="$run_root/data"
export BENCH_OUT="$run_root/data/bench.json"
export QUALITY_OUT="$run_root/data/quality.json"
export SMOKE_OUT="$run_root/data/smoke.json"
export SUMMARY_OUT="$run_root/data/summary.json"
export BENCH_MAX_TOKENS=128
# The historical candidate wrapper fixes the accounting window at 100 tokens.
# Keep 128 outputs so its generic benchmark gate remains internally valid.
export BENCH_METRIC_TOKENS=100
export RUN_SMOKE=0
export RUN_BENCH=1
export RUN_QUALITY=0
export REQUEST_EXTRA_JSON='{"chat_template_kwargs":{"enable_thinking":false}}'
export VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_FILE="$run_root/verify-trace.jsonl"
export VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_MAX_LINES=512
export VLLM_XPU_SPEC_DECODE_BONUS_LOGIT_TRACE_FILE="$run_root/bonus-trace.jsonl"
export VLLM_XPU_SPEC_DECODE_BONUS_LOGIT_TRACE_MAX_LINES=512
if [[ "$acceptance_mode" == "zero" ]]; then
  # This existing sampler mode rejects every proposal by construction and
  # emits the first target verifier token. The target still runs at width 4.
  export QWEN36_27B_SPECULATIVE_CONFIG='{"method":"qwen3_next_mtp","num_speculative_tokens":3,"rejection_sample_method":"synthetic","synthetic_acceptance_rates":[0.0,0.0,0.0]}'
fi
export VLLM_CACHE_ROOT=${VLLM_CACHE_ROOT:-/mnt/usb-models/llm-runtime/vllm-cache/qwen27-correctness-recovery-20260815}
export CANDIDATE_ENTRYPOINT="$repo/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-fullgraph-transaction-candidate.sh"

reference="$repo/experiments/qwen36-27b-autoround-int4-b70/validation-20260815/evidence/independent-validation-20260815T152141Z/nospec-01a/data/bench.json"
candidate="$repo/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-fullgraph-transaction-candidate.sh"

exec 9>/tmp/b70-benchmark.lock
if ! flock -n 9; then
  printf 'GPU benchmark lock is held\n' >&2
  exit 4
fi

set +e
"$candidate" > "$run_root/runner.stdout.log" 2>&1
runner_rc=$?
set -e
printf '%s\n' "$runner_rc" > "$run_root/runner.exit-code"

if [[ "$runner_rc" -eq 0 && -s "$run_root/verify-trace.jsonl" ]]; then
  "$venv/bin/python" "$here/analyze-verifier-trace.py" \
    --trace "$run_root/verify-trace.jsonl" \
    --candidate "$run_root/data/bench.json" \
    --reference "$reference" \
    --out "$run_root/analysis.json" \
    > "$run_root/analysis.stdout.log"
fi

find "$run_root" -type f ! -name SHA256SUMS -print0 \
  | sort -z | xargs -0 sha256sum > "$run_root/SHA256SUMS"
printf '%s\n' "$run_root"
exit "$runner_rc"
