#!/usr/bin/env bash
set -euo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "$here/../../.." && pwd)
acceptance_mode=${1:-standard}
case "$acceptance_mode" in
  target-only|standard|zero|no-graph-replay|skip-compiled|no-replayssm|replayssm-eager|replayssm-torch-eager|native-fast-eager|native-fast-piecewise|native-fast-piecewise-scratch|native-serial) ;;
  *)
    printf 'usage: %s target-only|standard|zero|no-graph-replay|skip-compiled|no-replayssm|replayssm-eager|replayssm-torch-eager|native-fast-eager|native-fast-piecewise|native-fast-piecewise-scratch|native-serial\n' "$0" >&2
    exit 2
    ;;
esac
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
verify_tree "$source_root/vllm" 8c27a1e68ac619e198b0c08c2d6f62b80ddb3456 \
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 vllm
verify_tree "$source_root/vllm-xpu-kernels" 534bd9ccca74e0b076067a212271f896bb137d2a \
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 kernels
expected_xpu_c_sha=e9715e02bc7a475f2f8922caa288fa542df6acf24736662aecd37fd6a21cb8a7
xpu_c="$source_root/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so"
if [[ ! -f "$xpu_c" \
  || "$(sha256sum "$xpu_c" | awk '{print $1}')" != "$expected_xpu_c_sha" ]]; then
  printf 'XPU extension mismatch: expected %s at %s\n' \
    "$expected_xpu_c_sha" "$xpu_c" >&2
  exit 3
fi

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
if [[ "$acceptance_mode" == "target-only" ]]; then
  export QWEN36_27B_ENABLE_MTP=0
  export NUM_SPECULATIVE_TOKENS=0
  export STAGE="$source_root/vllm-xpu-kernels"
  export VLLM_XPU_KERNELS_SRC="$source_root/vllm-xpu-kernels"
  export COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'
  export VLLM_XPU_DRAFT_DISABLE_CUDAGRAPHS=1
  unset QWEN36_27B_SPECULATIVE_CONFIG
  unset VLLM_XPU_DDTREE_FULL_GRAPH
  unset VLLM_XPU_DDTREE_CAPTURE_GDN_CORE
  unset VLLM_XPU_GDN_REPLAYSSM_FUSE_PENDING_METADATA
  unset VLLM_XPU_GDN_REPLAYSSM_DIRECT_CORE_OUT
  unset VLLM_XPU_COMPILE_ALLGATHER_CUSTOM_OP
fi
if [[ "$acceptance_mode" == "zero" ]]; then
  # This existing sampler mode rejects every proposal by construction and
  # emits the first target verifier token. The target still runs at width 4.
  export QWEN36_27B_SPECULATIVE_CONFIG='{"method":"qwen3_next_mtp","num_speculative_tokens":3,"rejection_sample_method":"synthetic","synthetic_acceptance_rates":[0.0,0.0,0.0]}'
fi
if [[ "$acceptance_mode" == "no-graph-replay" ]]; then
  # Keep the compiled verifier but bypass its PIECEWISE XPU graph replay.
  export VLLM_XPU_DISABLE_SPEC_DECODE_CUDAGRAPH_REPLAY=1
fi
if [[ "$acceptance_mode" == "skip-compiled" ]]; then
  # Route packed verifier rows through the raw model forward. Ordinary
  # one-token decode remains compiled; this is the known quality oracle.
  export VLLM_XPU_SKIP_COMPILED_SPEC_DECODE=1
fi
if [[ "$acceptance_mode" == "no-replayssm" ]]; then
  # Retain MTP3 but use the ordinary packed GDN state path instead of the
  # experimental ReplaySSM transaction and fused kernels.
  export VLLM_XPU_GDN_REPLAYSSM_SPEC=0
fi
if [[ "$acceptance_mode" == "replayssm-eager" || "$acceptance_mode" == "replayssm-torch-eager" ]]; then
  # Keep the complete ReplaySSM transaction, fused stage/recurrent kernels,
  # pending metadata, and direct core output, but remove every graph layer.
  # This separates ReplaySSM state semantics from captured execution.
  export QWEN36_27B_ENABLE_XPU_GRAPH=0
  export VLLM_XPU_ENABLE_XPU_GRAPH=0
  export VLLM_XPU_FORCE_GRAPH_WITH_COMM=0
  export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=0
  export VLLM_XPU_DDTREE_FULL_GRAPH=0
  export VLLM_XPU_DDTREE_CAPTURE_GDN_CORE=0
  export VLLM_XPU_DRAFT_DISABLE_CUDAGRAPHS=1
  export COMPILATION_CONFIG='{"cudagraph_mode":"NONE"}'
fi
if [[ "$acceptance_mode" == "replayssm-torch-eager" ]]; then
  # Replace only the ReplaySSM recurrent kernel with its PyTorch reference.
  # Eight emitted tokens cross the known token-6 failure while keeping this
  # deliberately slow oracle bounded.
  export VLLM_XPU_GDN_REPLAYSSM_TORCH_FALLBACK=1
  export BENCH_MAX_TOKENS=16
  export BENCH_METRIC_TOKENS=8
fi
if [[ "$acceptance_mode" == "native-fast-eager" ]]; then
  # Use the native packed GDN kernel without command-graph capture. This
  # separates kernel/state correctness from the device-lost full-graph arm.
  export VLLM_XPU_GDN_REPLAYSSM_SPEC=0
  export VLLM_XPU_GDN_NATIVE_SPEC_DECODE=1
  export VLLM_XPU_GDN_NATIVE_SPEC_DECODE_SERIAL=0
  export QWEN36_27B_ENABLE_XPU_GRAPH=0
  export VLLM_XPU_ENABLE_XPU_GRAPH=0
  export VLLM_XPU_FORCE_GRAPH_WITH_COMM=0
  export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=0
  export VLLM_XPU_DDTREE_FULL_GRAPH=0
  export VLLM_XPU_DDTREE_CAPTURE_GDN_CORE=0
  export VLLM_XPU_GDN_REPLAYSSM_FUSE_PENDING_METADATA=0
  export VLLM_XPU_GDN_REPLAYSSM_DIRECT_CORE_OUT=0
  export COMPILATION_CONFIG='{"cudagraph_mode":"NONE"}'
fi
if [[ "$acceptance_mode" == "native-fast-piecewise" || "$acceptance_mode" == "native-fast-piecewise-scratch" ]]; then
  # Keep the exact native packed GDN transaction and restore only ordinary
  # PIECEWISE XPU graph capture. Exclude the device-lost DDTree/full-graph
  # configuration used by the first no-ReplaySSM graph attempt.
  export VLLM_XPU_GDN_REPLAYSSM_SPEC=0
  export VLLM_XPU_GDN_NATIVE_SPEC_DECODE=1
  export VLLM_XPU_GDN_NATIVE_SPEC_DECODE_SERIAL=0
  export QWEN36_27B_ENABLE_XPU_GRAPH=1
  export VLLM_XPU_ENABLE_XPU_GRAPH=1
  export VLLM_XPU_FORCE_GRAPH_WITH_COMM=1
  export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1
  export VLLM_XPU_DDTREE_FULL_GRAPH=0
  export VLLM_XPU_DDTREE_CAPTURE_GDN_CORE=0
  export VLLM_XPU_GDN_REPLAYSSM_FUSE_PENDING_METADATA=0
  export VLLM_XPU_GDN_REPLAYSSM_DIRECT_CORE_OUT=0
  export COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[4],"max_cudagraph_capture_size":4}'
fi
if [[ "$acceptance_mode" == "native-fast-piecewise-scratch" ]]; then
  # Keep every native GDN temporary at a stable process-lifetime address so
  # captured Level Zero command graphs cannot replay allocator-reused storage.
  export VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1
fi
if [[ "$acceptance_mode" == "native-serial" ]]; then
  # Use the sequential native packed-GDN oracle. This retains the four-row
  # verifier and MTP scheduler while removing both ReplaySSM and the parallel
  # native recurrent update from the correctness comparison.
  export VLLM_XPU_GDN_REPLAYSSM_SPEC=0
  export VLLM_XPU_GDN_NATIVE_SPEC_DECODE=1
  export VLLM_XPU_GDN_NATIVE_SPEC_DECODE_SERIAL=1
  export QWEN36_27B_ENABLE_XPU_GRAPH=0
  export VLLM_XPU_ENABLE_XPU_GRAPH=0
  export VLLM_XPU_FORCE_GRAPH_WITH_COMM=0
  export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=0
  export VLLM_XPU_DDTREE_FULL_GRAPH=0
  export VLLM_XPU_DDTREE_CAPTURE_GDN_CORE=0
  export VLLM_XPU_GDN_REPLAYSSM_FUSE_PENDING_METADATA=0
  export VLLM_XPU_GDN_REPLAYSSM_DIRECT_CORE_OUT=0
  export COMPILATION_CONFIG='{"cudagraph_mode":"NONE"}'
  # The metadata builder runs once per forward, so this bounded trace records
  # accepted counts and state-table columns without reading recurrent tensors
  # back to the host. It is diagnostic-only and intentionally rank 0.
  export VLLM_XPU_GDN_METADATA_TRACE_FILE="$run_root/gdn-metadata.jsonl"
  export VLLM_XPU_GDN_METADATA_TRACE_MAX_LINES=160
  export VLLM_XPU_GDN_METADATA_TRACE_RANK=0
fi
if [[ "$acceptance_mode" == "target-only" ]]; then
  export VLLM_CACHE_ROOT=${VLLM_CACHE_ROOT:-/mnt/usb-models/llm-runtime/vllm-cache/qwen27-independent-validation-20260815}
  candidate="$repo/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-oneccl-public4ce-candidate.sh"
else
  if [[ "$acceptance_mode" == "no-replayssm" || "$acceptance_mode" == "replayssm-eager" || "$acceptance_mode" == "replayssm-torch-eager" || "$acceptance_mode" == "native-fast-eager" || "$acceptance_mode" == "native-fast-piecewise" || "$acceptance_mode" == "native-fast-piecewise-scratch" || "$acceptance_mode" == "native-serial" ]]; then
    export VLLM_CACHE_ROOT=${VLLM_CACHE_ROOT:-/mnt/usb-models/llm-runtime/vllm-cache/qwen27-correctness-$acceptance_mode-20260815}
  else
    export VLLM_CACHE_ROOT=${VLLM_CACHE_ROOT:-/mnt/usb-models/llm-runtime/vllm-cache/qwen27-correctness-recovery-20260815}
  fi
  candidate="$repo/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-fullgraph-transaction-candidate.sh"
fi
export CANDIDATE_ENTRYPOINT="$candidate"

reference="$repo/experiments/qwen36-27b-autoround-int4-b70/validation-20260815/evidence/independent-validation-20260815T152141Z/nospec-01a/data/bench.json"

exec 9>/tmp/b70-benchmark.lock
if ! flock -n 9; then
  printf 'GPU benchmark lock is held\n' >&2
  exit 4
fi

set +e
"$candidate" > "$run_root/runner.stdout.log" 2>&1
runner_rc=$?
set -e

# The historical wrapper can return success after an API server startup
# failure because no benchmark request was attempted. Fail closed unless the
# requested cold row and its cache-zero validity record actually exist.
if [[ "$runner_rc" -eq 0 ]]; then
  if [[ ! -s "$run_root/data/bench.json" ]] \
    || ! jq -e '.rows | length == 1' "$run_root/data/bench.json" >/dev/null \
    || ! jq -e '.fresh_response_validity.valid == true' "$run_root/data/bench.json" >/dev/null; then
    printf 'candidate exited zero without one valid cold benchmark row\n' \
      >> "$run_root/runner.stdout.log"
    runner_rc=5
  fi
fi
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
