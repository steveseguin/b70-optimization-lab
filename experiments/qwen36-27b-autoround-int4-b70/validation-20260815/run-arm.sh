#!/usr/bin/env bash
set -euo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "$here/../../.." && pwd)
mode=${1:-}
gpu_pair=${2:-}
arm_root=${3:-}
quality_baseline=${4:-}

if [[ "$mode" != "spec" && "$mode" != "nospec" \
  && "$mode" != "spec-native-scratch" && "$mode" != "nospec-current" \
  && "$mode" != "spec-native-partition" \
  && "$mode" != "spec-native-partition-exact" \
  && "$mode" != "spec-native-partition-exact-native" \
  && "$mode" != "spec-native-partition-exact-native-zero" \
  && "$mode" != "spec-native-partition-exact-native-raw" \
  && "$mode" != "nospec-latest" \
  && "$mode" != "nospec-latest-exact" \
  && "$mode" != "nospec-latest-exact-native" ]]; then
  printf 'usage: %s spec|nospec|spec-native-scratch|nospec-current|spec-native-partition|spec-native-partition-exact|spec-native-partition-exact-native|spec-native-partition-exact-native-zero|spec-native-partition-exact-native-raw|nospec-latest|nospec-latest-exact|nospec-latest-exact-native GPU0,GPU1 ARM_ROOT [QUALITY_BASELINE]\n' "$0" >&2
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
base_stage=${BASE_STAGE:-$source_root/vllm-xpu-kernels}
graph_stage=${STAGE:-$repo/experiments/qwen27_graphsafe_flash_attention/staged-package}
oneccl=${ONECCL_INSTALL_DIR:-/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public}
port=${PORT:-19622}
stamp=${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}
label=${LABEL:-$(basename "$arm_root")}
suite="$arm_root/validation-suite.json"

mkdir -p -- "$arm_root"
if [[ -n "${VALIDATION_SUITE_OVERRIDE:-}" ]]; then
  if [[ ! -f "$VALIDATION_SUITE_OVERRIDE" ]]; then
    printf 'validation suite override is missing: %s\n' \
      "$VALIDATION_SUITE_OVERRIDE" >&2
    exit 3
  fi
  cp -- "$VALIDATION_SUITE_OVERRIDE" "$suite"
  jq -e '.prompts | type == "array" and length > 0' "$suite" \
    > "$arm_root/suite-build.log"
else
  "$here/build-validation-suite.py" --repo "$repo" --out "$suite" \
    > "$arm_root/suite-build.log"
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
current_identity=0
latest_identity=0
exact_identity=0
if [[ "$mode" == "spec-native-scratch" || "$mode" == "nospec-current" ]]; then
  current_identity=1
  verify_tree "$source_root/vllm" 8c27a1e68ac619e198b0c08c2d6f62b80ddb3456 \
    e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 vllm
  verify_tree "$source_root/vllm-xpu-kernels" 534bd9ccca74e0b076067a212271f896bb137d2a \
    e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 kernels
elif [[ "$mode" == "spec-native-partition-exact" \
  || "$mode" == "spec-native-partition-exact-native" \
  || "$mode" == "spec-native-partition-exact-native-zero" \
  || "$mode" == "spec-native-partition-exact-native-raw" \
  || "$mode" == "nospec-latest-exact" \
  || "$mode" == "nospec-latest-exact-native" ]]; then
  latest_identity=1
  exact_identity=1
  verify_tree "$source_root/vllm" b54527eb505409017d43122bc5669eafd601910d \
    e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 vllm
  verify_tree "$source_root/vllm-xpu-kernels" 6a40e2baf3f8710b89e48d18bf214708ba2dbf9a \
    e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 kernels
elif [[ "$mode" == "spec-native-partition" || "$mode" == "nospec-latest" ]]; then
  latest_identity=1
  verify_tree "$source_root/vllm" b54527eb505409017d43122bc5669eafd601910d \
    e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 vllm
  verify_tree "$source_root/vllm-xpu-kernels" 6a40e2baf3f8710b89e48d18bf214708ba2dbf9a \
    e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 kernels
else
  verify_tree "$source_root/vllm" e7213ba8e13b74d7bfa3cbc05435a45df90eb76a \
    dcf84454f64bdeca546aa1697f4cd6af89fa95bb56f80ed314ad4d364e134b24 vllm
  verify_tree "$source_root/vllm-xpu-kernels" 3b4effeeffd83f6ef4696bbe7e76d924a0e9d171 \
    edcb9314b43d6990474dfb5d64e3716e8d4c33618ec0e3fbd11ae671e47c8c1f kernels
fi

verify_sha() {
  local path=$1 expected=$2 label=$3 actual
  if [[ ! -f "$path" ]]; then
    printf '%s is missing: %s\n' "$label" "$path" >&2
    exit 3
  fi
  actual=$(sha256sum "$path" | awk '{print $1}')
  if [[ "$actual" != "$expected" ]]; then
    printf '%s SHA256 mismatch: expected=%s actual=%s path=%s\n' \
      "$label" "$expected" "$actual" "$path" >&2
    exit 3
  fi
}

while read -r expected recorded_path; do
  [[ -n "$expected" && -n "$recorded_path" ]] || continue
  binary=$(basename "$recorded_path")
  if [[ "$current_identity" == "1" && "$binary" == "_xpu_C.abi3.so" ]]; then
    expected=e9715e02bc7a475f2f8922caa288fa542df6acf24736662aecd37fd6a21cb8a7
  fi
  if [[ "$latest_identity" == "1" && "$binary" == "_xpu_C.abi3.so" ]]; then
    expected=871188fc4729f6387db10ad4f76fdfe91b96e0502acff9c23b444cadf6ea993e
  fi
  if [[ "$exact_identity" == "1" && "$binary" == "_xpu_C.abi3.so" ]]; then
    expected=871188fc4729f6387db10ad4f76fdfe91b96e0502acff9c23b444cadf6ea993e
  fi
  if [[ "$latest_identity" == "1" && "$binary" == "libgdn_attn_kernels_xe_2.so" ]]; then
    expected=fd326287972c808490e4dfd34362558c132c7939a6adb5f55a7c8e83567f63bb
  fi
  verify_sha "$base_stage/vllm_xpu_kernels/$binary" "$expected" "XPU runtime $binary"
done < "$repo/repro/qwen36-27b-autoround-int4-b70/evidence/xpu-runtime-binaries.sha256"
verify_sha "$oneccl/lib/libccl.so.1.0" \
  43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700 oneCCL
verify_sha "$oneccl/lib/ccl/kernels/kernels.spv" \
  0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9 oneCCL-kernels

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

SOURCE_ROOT="$source_root" "$venv/bin/python" - <<'PY' \
  > "$arm_root/python-runtime-verify.log"
import json
import os
import pathlib
import sys

import torch
import vllm

expected = {
    "python_major_minor": "3.12",
    "torch": "2.11.0+xpu",
    "vllm": "0.20.2rc1.dev13+g9557d9108.d20260620",
}
actual = {
    "python_major_minor": ".".join(map(str, sys.version_info[:2])),
    "torch": torch.__version__,
    "vllm": vllm.__version__,
    "vllm_path": str(pathlib.Path(vllm.__file__).resolve()),
    "xpu_available": torch.xpu.is_available(),
    "xpu_count": torch.xpu.device_count(),
}
expected_vllm_root = pathlib.Path(os.environ["SOURCE_ROOT"], "vllm").resolve()
vllm_path = pathlib.Path(actual["vllm_path"])
valid = (
    all(actual[key] == value for key, value in expected.items())
    and actual["xpu_available"] is True
    and actual["xpu_count"] == 4
    and vllm_path.is_relative_to(expected_vllm_root)
)
print(json.dumps({"expected": expected, "actual": actual, "valid": valid}, indent=2))
if not valid:
    raise SystemExit("Python/XPU runtime identity mismatch")
PY

# shellcheck source=../../../repro/qwen36-27b-autoround-int4-b70/configs/record.env
source "$repo/repro/qwen36-27b-autoround-int4-b70/configs/record.env"

export SOURCE_ROOT="$source_root"
export VLLM_SOURCE_TREE="$source_root/vllm"
export VLLM_XPU_KERNELS_SOURCE_TREE="$source_root/vllm-xpu-kernels"
export MODEL_DIR="$model_dir"
export QWEN36_27B_AR_VENV="$venv"
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
export BENCH_MAX_TOKENS=${VALIDATION_BENCH_MAX_TOKENS:-512}
export BENCH_METRIC_TOKENS=${VALIDATION_BENCH_METRIC_TOKENS:-100}
export QUALITY_REPEAT_RUNS=32
export QUALITY_LONG_CONTEXT_TOKENS=1024
export RUN_SMOKE=${VALIDATION_RUN_SMOKE:-1}
export RUN_BENCH=${VALIDATION_RUN_BENCH:-1}
export RUN_QUALITY=${VALIDATION_RUN_QUALITY:-1}
export REQUEST_EXTRA_JSON='{"chat_template_kwargs":{"enable_thinking":false}}'
export QUALITY_BASELINE_JSON="$quality_baseline"
if [[ "${VALIDATION_ENABLE_PACKET_TRACE:-0}" == "1" ]]; then
  # Bounded correctness trace. These files distinguish a wrong target row
  # from a correct target row that is mis-selected or mis-emitted.
  export VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_FILE="$arm_root/verify-trace.jsonl"
  export VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_MAX_LINES=32
  export VLLM_XPU_SPEC_DECODE_BONUS_LOGIT_TRACE_FILE="$arm_root/bonus-trace.jsonl"
  export VLLM_XPU_SPEC_DECODE_BONUS_LOGIT_TRACE_MAX_LINES=32
  export VLLM_XPU_GDN_METADATA_TRACE_FILE="$arm_root/gdn-metadata.jsonl"
  export VLLM_XPU_GDN_METADATA_TRACE_MAX_LINES=48
  export VLLM_XPU_GDN_METADATA_TRACE_RANK=0
  export VLLM_XPU_MODEL_INPUT_TRACE_FILE="$arm_root/model-input-trace.jsonl"
  export VLLM_XPU_MODEL_INPUT_TRACE_MAX_LINES=32
  export VLLM_XPU_MODEL_INPUT_TRACE_RANK=0
fi
if [[ "${VALIDATION_ENABLE_LAYER_TRACE:-0}" == "1" ]]; then
  # Compare only the first two real verifier packets against ordered native
  # target decode. Python layer traces require either an eager target arm or a
  # speculative arm whose verifier forward alone bypasses compiled execution;
  # compiled functions elide these trace helpers.
  export VLLM_XPU_QWEN_LAYER_TRACE_FILE="$arm_root/qwen-layer-trace.jsonl"
  export VLLM_XPU_QWEN_LAYER_TRACE_LAYERS="${VALIDATION_QWEN_LAYER_TRACE_LAYERS:-0,1,2,3}"
  export VLLM_XPU_QWEN_LAYER_TRACE_STAGES="${VALIDATION_QWEN_LAYER_TRACE_STAGES:-input_norm_after,attention_after,post_attention_norm_after,mlp_after}"
  export VLLM_XPU_QWEN_LAYER_TRACE_ROW_INDICES="${VALIDATION_QWEN_LAYER_TRACE_ROW_INDICES:-0,1,2,3}"
  export VLLM_XPU_QWEN_LAYER_TRACE_POS_MIN="${VALIDATION_QWEN_LAYER_TRACE_POS_MIN:-74}"
  export VLLM_XPU_QWEN_LAYER_TRACE_POS_MAX="${VALIDATION_QWEN_LAYER_TRACE_POS_MAX:-80}"
  export VLLM_XPU_QWEN_LAYER_TRACE_RANK="${VALIDATION_QWEN_LAYER_TRACE_RANK:-0}"
  export VLLM_XPU_QWEN_LAYER_TRACE_RESIDUAL="${VALIDATION_QWEN_LAYER_TRACE_RESIDUAL:-1}"
  export VLLM_XPU_QWEN_LAYER_TRACE_MAX_LINES="${VALIDATION_QWEN_LAYER_TRACE_MAX_LINES:-256}"

  export VLLM_XPU_GDN_ROW_TRACE_FILE="$arm_root/gdn-row-trace.jsonl"
  export VLLM_XPU_GDN_ROW_TRACE_LAYERS="${VALIDATION_GDN_ROW_TRACE_LAYERS:-0,1,2}"
  export VLLM_XPU_GDN_ROW_TRACE_STAGES="${VALIDATION_GDN_ROW_TRACE_STAGES:-forward_post_core,forward_post_norm,forward_post_out_proj}"
  export VLLM_XPU_GDN_ROW_TRACE_ROW_LIMIT="${VALIDATION_GDN_ROW_TRACE_ROW_LIMIT:-4}"
  export VLLM_XPU_GDN_ROW_TRACE_STATE_LIMIT="${VALIDATION_GDN_ROW_TRACE_STATE_LIMIT:-1}"
  export VLLM_XPU_GDN_ROW_TRACE_REQ_REGEX="${VALIDATION_GDN_ROW_TRACE_REQ_REGEX:-holdout--concurrency-review}"
  export VLLM_XPU_GDN_ROW_TRACE_RANK="${VALIDATION_GDN_ROW_TRACE_RANK:-0}"
  export VLLM_XPU_GDN_ROW_TRACE_MAX_LINES="${VALIDATION_GDN_ROW_TRACE_MAX_LINES:-128}"

  # The detailed GDN trace includes the quantized qkvz/ba projection output,
  # which the lighter row trace begins after.
  export VLLM_XPU_GDN_TRACE_FILE="$arm_root/gdn-projection-trace.jsonl"
  export VLLM_XPU_GDN_TRACE_LAYER_REGEX="${VALIDATION_GDN_TRACE_LAYER_REGEX:-layers\\.(0|1|2)\\.linear_attn}"
  export VLLM_XPU_GDN_TRACE_REQ_REGEX="${VALIDATION_GDN_TRACE_REQ_REGEX:-holdout--concurrency-review}"
  export VLLM_XPU_GDN_TRACE_RANK="${VALIDATION_GDN_TRACE_RANK:-0}"
  export VLLM_XPU_GDN_TRACE_MAX_LINES="${VALIDATION_GDN_TRACE_MAX_LINES:-256}"
  export VLLM_XPU_GDN_TRACE_TENSOR_LIMIT="${VALIDATION_GDN_TRACE_TENSOR_LIMIT:-8}"
  export VLLM_XPU_GDN_TRACE_STATE_LIMIT="${VALIDATION_GDN_TRACE_STATE_LIMIT:-1}"
fi
if [[ -n "${VALIDATION_FA_SERIAL_SPEC_MODE:-}" ]]; then
  export VLLM_XPU_FA_SERIAL_SPEC_MODE="$VALIDATION_FA_SERIAL_SPEC_MODE"
fi
if [[ "${VALIDATION_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT:-0}" == "1" ]]; then
  export VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT=1
fi
if [[ "$mode" == "spec" || "$mode" == "spec-native-scratch" \
  || "$mode" == "spec-native-partition" \
  || "$mode" == "spec-native-partition-exact" \
  || "$mode" == "spec-native-partition-exact-native" \
  || "$mode" == "spec-native-partition-exact-native-zero" \
  || "$mode" == "spec-native-partition-exact-native-raw" ]]; then
  # FULL graph capture requires the isolated graph-safe FlashAttention build.
  # The ordinary XPU extension uses work-group scratch memory, which SYCL graph
  # capture rejects.  Pin both the Python extension and its device library so
  # this cannot silently regress to the ordinary package.
  verify_sha "$graph_stage/vllm_xpu_kernels/_vllm_fa2_C.abi3.so" \
    33938cdd2436684dcb76108a4db43e4ab0314406ad537fcd3732a005f7d23739 \
    graph-safe-FlashAttention-extension
  verify_sha "$graph_stage/vllm_xpu_kernels/libattn_kernels_xe_2.so" \
    604f1b328870f2c41ef1d05c4d6016c34d222033d905877b0f9a2ff0c66b2a0c \
    graph-safe-FlashAttention-device-library
  export STAGE="$graph_stage"
  export VLLM_XPU_KERNELS_SRC="$graph_stage"
  export QWEN36_27B_ENABLE_MTP=1
  export NUM_SPECULATIVE_TOKENS=3
  if [[ "$mode" == "spec-native-scratch" \
    || "$mode" == "spec-native-partition" \
    || "$mode" == "spec-native-partition-exact" \
    || "$mode" == "spec-native-partition-exact-native" \
    || "$mode" == "spec-native-partition-exact-native-zero" \
    || "$mode" == "spec-native-partition-exact-native-raw" ]]; then
    export VLLM_XPU_GDN_REPLAYSSM_SPEC=0
    export VLLM_XPU_GDN_NATIVE_SPEC_DECODE=1
    export VLLM_XPU_GDN_NATIVE_SPEC_DECODE_SERIAL=0
    export VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1
    export VLLM_XPU_DDTREE_FULL_GRAPH=0
    export VLLM_XPU_DDTREE_CAPTURE_GDN_CORE=0
    export VLLM_XPU_GDN_REPLAYSSM_FUSE_PENDING_METADATA=0
    export VLLM_XPU_GDN_REPLAYSSM_DIRECT_CORE_OUT=0
    if [[ "$mode" == "spec-native-partition" \
      || "$mode" == "spec-native-partition-exact" \
      || "$mode" == "spec-native-partition-exact-native" \
      || "$mode" == "spec-native-partition-exact-native-zero" \
      || "$mode" == "spec-native-partition-exact-native-raw" ]]; then
      export COMPILATION_CONFIG='{"use_inductor_graph_partition":true,"pass_config":{"fuse_rope_kvcache_cat_mla":false},"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[4],"max_cudagraph_capture_size":4}'
    else
      export COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[4],"max_cudagraph_capture_size":4}'
    fi
    if [[ "$mode" == "spec-native-partition-exact" \
      || "$mode" == "spec-native-partition-exact-native" \
      || "$mode" == "spec-native-partition-exact-native-zero" \
      || "$mode" == "spec-native-partition-exact-native-raw" ]]; then
      export VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1
    fi
    if [[ "$mode" == "spec-native-partition-exact-native-zero" ]]; then
      # Coherent fixed-width-four target control: execute all verifier rows,
      # but synthetically reject every proposal so only target row zero emits.
      export QWEN36_27B_SPECULATIVE_CONFIG='{"method":"qwen3_next_mtp","num_speculative_tokens":3,"rejection_sample_method":"synthetic","synthetic_acceptance_rates":[0.0,0.0,0.0]}'
    fi
    if [[ "$mode" == "spec-native-partition-exact-native-raw" ]]; then
      export VLLM_XPU_SKIP_COMPILED_SPEC_DECODE=1
    fi
  fi
  candidate="$repo/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-fullgraph-transaction-candidate.sh"
else
  export STAGE="$base_stage"
  export VLLM_XPU_KERNELS_SRC="$base_stage"
  export QWEN36_27B_ENABLE_MTP=0
  unset QWEN36_27B_SPECULATIVE_CONFIG
  # The candidate's fixed width-4 full graph is a packed-verifier schedule,
  # not a valid one-row target reference. Use the previously quality-validated
  # ordinary target graph for no-spec controls while retaining the exact FP16
  # target, oneCCL, LM-head, sampling, and model identity.
  export COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'
  export VLLM_XPU_DRAFT_DISABLE_CUDAGRAPHS=1
  unset VLLM_XPU_DDTREE_FULL_GRAPH
  unset VLLM_XPU_DDTREE_CAPTURE_GDN_CORE
  unset VLLM_XPU_GDN_REPLAYSSM_FUSE_PENDING_METADATA
  unset VLLM_XPU_GDN_REPLAYSSM_DIRECT_CORE_OUT
  unset VLLM_XPU_COMPILE_ALLGATHER_CUSTOM_OP
  candidate="$repo/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-oneccl-public4ce-candidate.sh"
fi

if [[ "$mode" == "spec-native-partition-exact-native" \
  || "$mode" == "spec-native-partition-exact-native-zero" \
  || "$mode" == "spec-native-partition-exact-native-raw" \
  || "$mode" == "nospec-latest-exact-native" ]]; then
  # Use one coherent GDN arithmetic identity on both sides.  Value 0 disables
  # the default decode,prefill Triton fallback and routes ordinary target decode
  # through the same native one-token kernel used by the exact verifier proof.
  export VLLM_XPU_GDN_NATIVE_FALLBACK=0
fi
if [[ -n "${VALIDATION_VLLM_EXTRA_ARGS:-}" ]]; then
  export VLLM_EXTRA_ARGS="$VALIDATION_VLLM_EXTRA_ARGS"
fi
if [[ -n "${VALIDATION_ENABLE_XPU_GRAPH:-}" ]]; then
  export QWEN36_27B_ENABLE_XPU_GRAPH="$VALIDATION_ENABLE_XPU_GRAPH"
  if [[ "$VALIDATION_ENABLE_XPU_GRAPH" == "0" ]]; then
    unset XPU_GRAPH VLLM_XPU_ENABLE_XPU_GRAPH
    unset VLLM_XPU_FORCE_GRAPH_WITH_COMM VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE
  fi
fi

printf 'mode=%s\ngpu_pair=%s\narm_root=%s\nquality_baseline=%s\n' \
  "$mode" "$gpu_pair" "$arm_root" "$quality_baseline" > "$arm_root/arm.env"

exec 9>/tmp/b70-benchmark.lock
if ! flock -n 9; then
  printf 'GPU benchmark lock is held\n' >&2
  exit 4
fi

set +e
"$candidate" \
  > "$arm_root/runner.stdout.log" 2>&1
runner_rc=$?
set -e
if [[ "$runner_rc" == "0" \
  && ( "$mode" == "spec-native-partition-exact" \
    || "$mode" == "spec-native-partition-exact-native" \
    || "$mode" == "spec-native-partition-exact-native-zero" \
    || "$mode" == "spec-native-partition-exact-native-raw" ) ]]; then
  if ! grep -Fq \
    'VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT reached' \
    "$RUN_DIR/server.stdout.log"; then
    printf 'exact recurrent branch marker missing from server log\n' >&2
    runner_rc=6
  fi
fi
printf '%s\n' "$runner_rc" > "$arm_root/runner.exit-code"

if [[ -s "$BENCH_OUT" && "$BENCH_METRIC_TOKENS" == "100" ]]; then
  "$venv/bin/python" "$repo/scripts/qualify_realistic_window_metrics.py" \
    "$BENCH_OUT" --in-place > "$arm_root/qualify.log"
elif [[ -s "$BENCH_OUT" ]]; then
  printf 'diagnostic metric window (%s events); strict 100-event qualifier skipped\n' \
    "$BENCH_METRIC_TOKENS" > "$arm_root/qualify.log"
fi
find "$arm_root" -type f ! -name SHA256SUMS.pre-manifest -print0 \
  | sort -z | xargs -0 sha256sum \
  > "$arm_root/SHA256SUMS.pre-manifest"
exit "$runner_rc"
