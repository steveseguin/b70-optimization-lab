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
  expected_vllm_diff=${VALIDATION_EXPECT_VLLM_DIFF_SHA256:-e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855}
  expected_kernels_diff=${VALIDATION_EXPECT_KERNELS_DIFF_SHA256:-e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855}
  verify_tree "$source_root/vllm" 44fc8fde09fc311d3099dab10366b672d9142ea4 \
    "$expected_vllm_diff" vllm
  verify_tree "$source_root/vllm-xpu-kernels" 2dd55f380df753a10a88fcd9e96192561066e713 \
    "$expected_kernels_diff" kernels
elif [[ "$mode" == "spec-native-partition" || "$mode" == "nospec-latest" ]]; then
  latest_identity=1
  verify_tree "$source_root/vllm" a63ff886e1c9c90f919e8b46a63f34027dfae823 \
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

verify_relative_manifest() {
  local root=$1 manifest=$2 label=$3
  local expected relative_path
  local entries=0
  if [[ ! -f "$manifest" ]]; then
    printf '%s manifest is missing: %s\n' "$label" "$manifest" >&2
    exit 3
  fi
  while read -r expected relative_path _; do
    [[ -n "$expected" ]] || continue
    [[ "$expected" == \#* ]] && continue
    if [[ ! "$expected" =~ ^[0-9a-f]{64}$ || -z "$relative_path" \
      || "$relative_path" == /* || "$relative_path" == *..* ]]; then
      printf '%s manifest has an unsafe or malformed entry: %s %s\n' \
        "$label" "$expected" "$relative_path" >&2
      exit 3
    fi
    verify_sha "$root/$relative_path" "$expected" "$label $relative_path"
    entries=$((entries + 1))
  done < "$manifest"
  if (( entries == 0 )); then
    printf '%s manifest contains no file identities: %s\n' \
      "$label" "$manifest" >&2
    exit 3
  fi
}

if [[ -n "${VALIDATION_XPU_RUNTIME_MANIFEST:-}" ]]; then
  verify_relative_manifest "$base_stage/vllm_xpu_kernels" \
    "$VALIDATION_XPU_RUNTIME_MANIFEST" XPU-runtime
else
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
      expected=8f11e716910289c9e53b770fab14231c040ac5b08ea7830947390ac0fb674496
    fi
    if [[ "$latest_identity" == "1" && "$binary" == "libgdn_attn_kernels_xe_2.so" ]]; then
      expected=e7b9757a317157bb4a63159cc38ad3fc302135ca72954807d189420bbcf1595e
    fi
    verify_sha "$base_stage/vllm_xpu_kernels/$binary" "$expected" "XPU runtime $binary"
  done < "$repo/repro/qwen36-27b-autoround-int4-b70/evidence/xpu-runtime-binaries.sha256"
fi
if [[ -n "${VALIDATION_ONECCL_MANIFEST:-}" ]]; then
  verify_relative_manifest "$oneccl" "$VALIDATION_ONECCL_MANIFEST" oneCCL
  oneccl_validated_lib_sha=$(awk \
    '$2 == "lib/libccl.so.1.0" {print $1}' \
    "$VALIDATION_ONECCL_MANIFEST")
  oneccl_validated_kernels_sha=$(awk \
    '$2 == "lib/ccl/kernels/kernels.spv" {print $1}' \
    "$VALIDATION_ONECCL_MANIFEST")
  if [[ ! "$oneccl_validated_lib_sha" =~ ^[0-9a-f]{64}$ \
    || ! "$oneccl_validated_kernels_sha" =~ ^[0-9a-f]{64}$ ]]; then
    printf 'oneCCL manifest must identify libccl.so.1.0 and kernels.spv exactly once\n' >&2
    exit 3
  fi
else
  verify_sha "$oneccl/lib/libccl.so.1.0" \
    43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700 oneCCL
  verify_sha "$oneccl/lib/ccl/kernels/kernels.spv" \
    0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9 oneCCL-kernels
fi

verify_graph_stage() {
  if [[ -n "${VALIDATION_GRAPH_STAGE_MANIFEST:-}" ]]; then
    verify_relative_manifest "$graph_stage" "$VALIDATION_GRAPH_STAGE_MANIFEST" \
      graph-safe-FlashAttention
    return
  fi
  verify_sha "$graph_stage/vllm_xpu_kernels/_vllm_fa2_C.abi3.so" \
    33938cdd2436684dcb76108a4db43e4ab0314406ad537fcd3732a005f7d23739 \
    graph-safe-FlashAttention-extension
  verify_sha "$graph_stage/vllm_xpu_kernels/libattn_kernels_xe_2.so" \
    "${VALIDATION_FA_DEVICE_LIBRARY_SHA256:-604f1b328870f2c41ef1d05c4d6016c34d222033d905877b0f9a2ff0c66b2a0c}" \
    graph-safe-FlashAttention-device-library
  verify_sha "$graph_stage/vllm_xpu_kernels/libattn_stock.so" \
    3cbd3ed2ff51a477e6746b3e5860c070d093fd2d29b0b7a58e6dd081e9ad1289 \
    graph-safe-FlashAttention-stock-dependency
  verify_sha "$graph_stage/vllm_xpu_kernels/flash_attn_interface.py" \
    869c79f5f678252c341cfb8fb5cf9ee34f95c3d2debf4d169b759510da432480 \
    graph-safe-FlashAttention-Python-interface
}

PYTHON="$venv/bin/python" MODEL_DIR="$model_dir" \
  MODEL_MANIFEST="${VALIDATION_MODEL_MANIFEST:-$repo/repro/qwen36-27b-autoround-int4-b70/manifests/model.json}" \
  "$repo/repro/qwen36-27b-autoround-int4-b70/scripts/download-model.sh" \
  > "$arm_root/model-verify.log"

# Clear inherited experiment state before installing the exact recorded
# identity. Host/runtime paths are explicitly repopulated below.
while IFS= read -r name; do
  case "$name" in
    VLLM_*|QWEN36_27B_*|XPU_GRAPH|COMPILATION_CONFIG|CCL_*|ONECCL_*|SERVER_*|ZE_AFFINITY_MASK|ONEAPI_DEVICE_SELECTOR|PYTHONHASHSEED|QUALITY_*|BENCH_*|RUN_SMOKE|RUN_BENCH|RUN_QUALITY|REQUEST_EXTRA_JSON|CANDIDATE_ENTRYPOINT)
      unset "$name"
      ;;
  esac
done < <(compgen -e)
unset PYTHONPATH LD_PRELOAD LD_LIBRARY_PATH TORCHINDUCTOR_CACHE_DIR

if [[ -n "${VALIDATION_ONECCL_MANIFEST:-}" ]]; then
  export ONECCL_VALIDATED_LIB_SHA256="$oneccl_validated_lib_sha"
  export ONECCL_VALIDATED_KERNELS_SHA256="$oneccl_validated_kernels_sha"
fi

SOURCE_ROOT="$source_root" \
EXPECTED_XPU_COUNT="${VALIDATION_EXPECT_XPU_COUNT:-4}" \
EXPECTED_VLLM_VERSION="${VALIDATION_EXPECT_VLLM_VERSION:-0.20.2rc1.dev13+g9557d9108.d20260620}" \
  "$venv/bin/python" - <<'PY' \
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
    "vllm": os.environ["EXPECTED_VLLM_VERSION"],
    "xpu_count": int(os.environ["EXPECTED_XPU_COUNT"]),
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
export HF_HOME=${VALIDATION_HF_HOME:-/mnt/usb-models/llm-cache/hf}
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
compile_cache_root="$VLLM_CACHE_ROOT/torch_compile_cache"
if [[ -n "${VALIDATION_COMPILE_CACHE_MANIFEST:-}" ]]; then
  "$repo/scripts/canonical-tree-manifest.py" verify \
    --root "$compile_cache_root" \
    --manifest "$VALIDATION_COMPILE_CACHE_MANIFEST" \
    > "$arm_root/compile-cache-preflight.json"
  cp -- "$VALIDATION_COMPILE_CACHE_MANIFEST" \
    "$arm_root/compile-cache-input-manifest.json"
fi
export BENCH_MAX_TOKENS=${VALIDATION_BENCH_MAX_TOKENS:-512}
export BENCH_METRIC_TOKENS=${VALIDATION_BENCH_METRIC_TOKENS:-100}
export QUALITY_REPEAT_RUNS=32
export QUALITY_LONG_CONTEXT_TOKENS=1024
export RUN_SMOKE=${VALIDATION_RUN_SMOKE:-1}
export RUN_BENCH=${VALIDATION_RUN_BENCH:-1}
export RUN_QUALITY=${VALIDATION_RUN_QUALITY:-1}
if [[ -n "${VALIDATION_REQUEST_EXTRA_JSON:-}" ]]; then
  export REQUEST_EXTRA_JSON="${VALIDATION_REQUEST_EXTRA_JSON}"
else
  export REQUEST_EXTRA_JSON='{"chat_template_kwargs":{"enable_thinking":false}}'
fi
export QUALITY_BASELINE_JSON="$quality_baseline"
if [[ "${VALIDATION_ENABLE_PACKET_TRACE:-0}" == "1" ]]; then
  # Bounded correctness trace. These files distinguish a wrong target row
  # from a correct target row that is mis-selected or mis-emitted.
  export VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_FILE="$arm_root/verify-trace.jsonl"
  export VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_MAX_LINES="${VALIDATION_SPEC_VERIFY_TRACE_MAX_LINES:-32}"
  export VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_TOPK="${VALIDATION_SPEC_VERIFY_TRACE_TOPK:-1}"
  export VLLM_XPU_SPEC_DECODE_BONUS_LOGIT_TRACE_FILE="$arm_root/bonus-trace.jsonl"
  export VLLM_XPU_SPEC_DECODE_BONUS_LOGIT_TRACE_MAX_LINES="${VALIDATION_SPEC_BONUS_TRACE_MAX_LINES:-32}"
  export VLLM_XPU_GDN_METADATA_TRACE_FILE="$arm_root/gdn-metadata.jsonl"
  export VLLM_XPU_GDN_METADATA_TRACE_MAX_LINES="${VALIDATION_GDN_METADATA_TRACE_MAX_LINES:-48}"
  export VLLM_XPU_GDN_METADATA_TRACE_RANK=0
  export VLLM_XPU_MODEL_INPUT_TRACE_FILE="$arm_root/model-input-trace.jsonl"
  export VLLM_XPU_MODEL_INPUT_TRACE_MAX_LINES="${VALIDATION_MODEL_INPUT_TRACE_MAX_LINES:-32}"
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
  if [[ -n "${VALIDATION_GDN_ROW_TRACE_EXEC_INDICES:-}" ]]; then
    export VLLM_XPU_GDN_ROW_TRACE_EXEC_INDICES="$VALIDATION_GDN_ROW_TRACE_EXEC_INDICES"
  fi

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
if [[ "${VALIDATION_FA_BATCH_INVARIANT:-0}" == "1" ]]; then
  export VLLM_XPU_FA_BATCH_INVARIANT=1
fi
if [[ "${VALIDATION_RMSNORM_BATCH_INVARIANT:-0}" == "1" ]]; then
  export VLLM_XPU_RMSNORM_BATCH_INVARIANT=1
fi
if [[ "${VALIDATION_LINEAR_BATCH_INVARIANT:-0}" == "1" ]]; then
  export VLLM_XPU_LINEAR_BATCH_INVARIANT=1
fi
if [[ "${VALIDATION_FA_SYNC_AFTER_PACKED:-0}" == "1" ]]; then
  export VLLM_XPU_FA_SYNC_AFTER_PACKED=1
fi
if [[ "${VALIDATION_QWEN_SYNC_AFTER_FULL_ATTN_O_PROJ:-0}" == "1" ]]; then
  export VLLM_XPU_QWEN_SYNC_AFTER_FULL_ATTN_O_PROJ=1
  if [[ -n "${VALIDATION_QWEN_SYNC_AFTER_FULL_ATTN_O_PROJ_LAYERS:-}" ]]; then
    export VLLM_XPU_QWEN_SYNC_AFTER_FULL_ATTN_O_PROJ_LAYERS="$VALIDATION_QWEN_SYNC_AFTER_FULL_ATTN_O_PROJ_LAYERS"
  fi
fi
if [[ -n "${VALIDATION_SYNC_ROW_PARALLEL_AFTER_GEMM_PREFIX:-}" ]]; then
  export VLLM_XPU_SYNC_ROW_PARALLEL_AFTER_GEMM_PREFIX="$VALIDATION_SYNC_ROW_PARALLEL_AFTER_GEMM_PREFIX"
fi
if [[ "${VALIDATION_COMPILE_ALLREDUCE_STATIC_INPLACE:-0}" == "1" ]]; then
  # Correctness lane: publish compiled row-parallel reductions through the
  # stable mutating custom-op handoff instead of embedding dist.all_reduce in
  # the surrounding graph piece.
  export VLLM_XPU_COMPILE_ALLREDUCE_STATIC_INPLACE=1
fi
if [[ "${VALIDATION_ONEDNN_INT4_COMPLETION_BARRIER:-0}" == "1" ]]; then
  export VLLM_XPU_ONEDNN_INT4_COMPLETION_BARRIER=1
fi
if [[ "${VALIDATION_ONEDNN_INT4_INPUT_DEPENDENCY:-0}" == "1" ]]; then
  export VLLM_XPU_ONEDNN_INT4_INPUT_DEPENDENCY=1
  export VLLM_XPU_ONEDNN_INT4_INPUT_DEPENDENCY_SCOPE="${VALIDATION_ONEDNN_INT4_INPUT_DEPENDENCY_SCOPE:-layer0_gdn_in}"
fi
if [[ -n "${VALIDATION_M4_M1_ORACLE_FILE:-}" ]]; then
  export VLLM_XPU_M4_M1_ORACLE_FILE="$VALIDATION_M4_M1_ORACLE_FILE"
  export VLLM_XPU_M4_M1_ORACLE_FORWARD="${VALIDATION_M4_M1_ORACLE_FORWARD:-all}"
  export VLLM_XPU_M4_M1_ORACLE_COMPONENTS="${VALIDATION_M4_M1_ORACLE_COMPONENTS:-int4}"
fi
if [[ "${VALIDATION_ONEDNN_INT8_COMPLETION_BARRIER:-0}" == "1" ]]; then
  export VLLM_XPU_ONEDNN_INT8_COMPLETION_BARRIER=1
fi
if [[ "${VALIDATION_ONEDNN_INT8_INPUT_DEPENDENCY:-0}" == "1" ]]; then
  export VLLM_XPU_ONEDNN_INT8_INPUT_DEPENDENCY=1
fi
if [[ -n "${VALIDATION_LM_HEAD_INT8:-}" ]]; then
  # Exactness control: allow the harness to disable the experimental target
  # W8A8 vocabulary projection without inheriting ambient process state.
  export VLLM_XPU_LM_HEAD_INT8="${VALIDATION_LM_HEAD_INT8}"
fi
if [[ -n "${VALIDATION_DRAFT_LM_HEAD_INT4_RERANK_TOPK:-}" ]]; then
  # Candidate-only acceptance lever: the INT4 draft head proposes a small
  # local-vocabulary set and its retained original weights rerank that set.
  # Target verification remains unchanged.
  export VLLM_XPU_DRAFT_LM_HEAD_INT4_RERANK_TOPK="${VALIDATION_DRAFT_LM_HEAD_INT4_RERANK_TOPK}"
fi
if [[ -n "${VALIDATION_INDUCTOR_MAX_AUTOTUNE:-}" ]]; then
  # Fresh-compile determinism arm. vLLM defaults single-size graphs to max
  # autotune; expose the control explicitly instead of inheriting host state.
  export VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE="${VALIDATION_INDUCTOR_MAX_AUTOTUNE}"
fi
if [[ -n "${VALIDATION_INDUCTOR_COORDINATE_DESCENT_TUNING:-}" ]]; then
  export VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING="${VALIDATION_INDUCTOR_COORDINATE_DESCENT_TUNING}"
fi
if [[ -n "${VALIDATION_PYTHONHASHSEED:-}" ]]; then
  # Python reads this only when each TP/server process starts. Scrubbing it
  # above prevents an ambient shell seed from silently changing graph/codegen
  # traversal order between supposedly identical fresh compilations.
  export PYTHONHASHSEED="${VALIDATION_PYTHONHASHSEED}"
fi
if [[ "${VALIDATION_ALLREDUCE_ASYNC_WAIT:-0}" == "1" ]]; then
  # Eager-only ordering control: retain the collective work handle and wait
  # explicitly instead of relying on the default synchronous wrapper.
  export VLLM_XPU_ALLREDUCE_ASYNC_WAIT=1
fi
if [[ -n "${VALIDATION_DETERMINISTIC_GREEDY_MARGIN:-}" ]]; then
  # Shared target/verifier greedy policy for FP16-ULP near ties. The lower
  # token id wins only when the top-two gap is within this recorded margin.
  export VLLM_XPU_DETERMINISTIC_GREEDY_MARGIN="${VALIDATION_DETERMINISTIC_GREEDY_MARGIN}"
fi
if [[ "${VALIDATION_INT4_GEMM_FIXED_M4:-0}" == "1" ]]; then
  # Diagnostic only: make one-row target projections use the verifier's M=4
  # W4A16 descriptor and retain row zero.  Do not promote its timing.
  export VLLM_XPU_INT4_GEMM_FIXED_M4=1
fi
if [[ "${VALIDATION_INT8_LM_HEAD_FIXED_M4:-0}" == "1" ]]; then
  # Diagnostic only: make a one-row target lm_head use the verifier's M=4
  # W8A8 descriptor and retain row zero.  Do not promote its timing.
  export VLLM_XPU_INT8_LM_HEAD_FIXED_M4=1
fi
if [[ "${VALIDATION_INT8_LM_HEAD_SERIAL_M1:-0}" == "1" ]]; then
  # Exactness lane: preserve packed model execution but evaluate the target
  # INT8 vocabulary projection as independent M=1 rows.
  export VLLM_XPU_LM_HEAD_INT8_SERIAL_M1=1
fi
if [[ "${VALIDATION_GDN_BA_SERIAL_M1:-0}" == "1" ]]; then
  # Exactness lane: evaluate each packed GDN b/a projection row with the
  # target's M=1 projection shape.
  export VLLM_XPU_GDN_BA_SERIAL_M1=1
fi
if [[ "${VALIDATION_GDN_RMSNORM_GATED_SERIAL_M4:-0}" == "1" ]]; then
  # Exactness lane: evaluate the four packed GDN gated-RMSNorm rows using the
  # ordinary one-row reduction geometry. This is diagnostic until it passes
  # the full parity and performance gates.
  export VLLM_XPU_GDN_RMSNORM_GATED_SERIAL_M4=1
fi
if [[ "${VALIDATION_SYNC_AFTER_CUDAGRAPH_WARMUP:-0}" == "1" ]]; then
  export VLLM_XPU_SYNC_AFTER_CUDAGRAPH_WARMUP=1
fi
if [[ "${VALIDATION_SYNC_AFTER_MODEL_FORWARD:-0}" == "1" ]]; then
  # Diagnostic only: distinguish an unfinished model forward from later
  # logits/all-gather or sampler visibility.  This is a host synchronization
  # and must never be used for a promoted throughput result.
  export VLLM_XPU_SYNC_AFTER_MODEL_FORWARD=1
fi
if [[ "${VALIDATION_SKIP_COMPILED_SPEC_DECODE:-0}" == "1" ]]; then
  # Diagnostic only: execute speculative verifier forwards outside the
  # compiled wrapper while leaving the ordinary target/draft identities and
  # PIECEWISE process unchanged. This is needed for tensor traces, which are
  # intentionally suppressed while Dynamo is compiling.
  export VLLM_XPU_SKIP_COMPILED_SPEC_DECODE=1
fi
if [[ "${VALIDATION_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT:-0}" == "1" ]]; then
  export VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT=1
fi
if [[ "${VALIDATION_BATCH_INVARIANT:-0}" == "1" ]]; then
  # Diagnostic use of vLLM's complete batch-invariance contract. This is the
  # broad reference for deciding whether residual M4/M1 drift is arithmetic;
  # it is not a performance recipe unless it passes the normal gate.
  export VLLM_BATCH_INVARIANT=1
fi
if [[ "${VALIDATION_QWEN_GEMMA_RMSNORM_SERIAL_M4:-0}" == "1" ]]; then
  export VLLM_XPU_QWEN_GEMMA_RMSNORM_SERIAL_M4=1
fi
if [[ "${VALIDATION_QWEN_GEMMA_RMSNORM_SYCL:-0}" == "1" ]]; then
  export VLLM_XPU_QWEN_GEMMA_RMSNORM_SYCL=1
fi
if [[ "${VALIDATION_QWEN_DEVICE_BARRIER_AFTER_INPUT_NORM:-0}" == "1" ]]; then
  export VLLM_XPU_QWEN_DEVICE_BARRIER_AFTER_INPUT_NORM=1
  export VLLM_XPU_QWEN_DEVICE_BARRIER_AFTER_INPUT_NORM_LAYERS="${VALIDATION_QWEN_DEVICE_BARRIER_AFTER_INPUT_NORM_LAYERS:-0}"
fi
if [[ "${VALIDATION_SPLIT_QWEN_GEMMA_RMSNORM_SYCL:-0}" == "1" ]]; then
  export VLLM_XPU_SPLIT_QWEN_GEMMA_RMSNORM_SYCL=1
fi
if [[ "${VALIDATION_GDN_NATIVE_SPEC_METADATA_SNAPSHOT:-0}" == "1" ]]; then
  export VLLM_XPU_GDN_NATIVE_SPEC_METADATA_SNAPSHOT=1
fi
if [[ "${VALIDATION_GDN_NATIVE_SPEC_COMPLETION_BARRIER:-0}" == "1" ]]; then
  export VLLM_XPU_GDN_NATIVE_SPEC_COMPLETION_BARRIER=1
fi
if [[ "${VALIDATION_SPEC_DECODE_DRAFT_ONLY:-0}" == "1" ]]; then
  # Correctness scaffold: the target verifies drafts but never trusts a
  # packed target-owned replacement or bonus row.  This is intentionally not
  # a performance recipe until it passes the complete target-token oracle.
  export VLLM_XPU_SPEC_DECODE_DRAFT_ONLY=1
fi
if [[ -n "${VALIDATION_SPEC_DECODE_DRAFT_ONLY_ACCEPT_MIN_MARGIN:-}" ]]; then
  export VLLM_XPU_SPEC_DECODE_DRAFT_ONLY_ACCEPT_MIN_MARGIN="${VALIDATION_SPEC_DECODE_DRAFT_ONLY_ACCEPT_MIN_MARGIN}"
fi
if [[ -n "${VALIDATION_SPEC_DECODE_ACCEPT_MIN_MARGIN:-}" ]]; then
  export VLLM_XPU_SPEC_DECODE_ACCEPT_MIN_MARGIN="${VALIDATION_SPEC_DECODE_ACCEPT_MIN_MARGIN}"
fi
if [[ -n "${VALIDATION_SPEC_DECODE_REPLACEMENT_MIN_MARGIN:-}" ]]; then
  export VLLM_XPU_SPEC_DECODE_REPLACEMENT_MIN_MARGIN="${VALIDATION_SPEC_DECODE_REPLACEMENT_MIN_MARGIN}"
fi
if [[ -n "${VALIDATION_SPEC_DECODE_BONUS_MIN_MARGIN:-}" ]]; then
  export VLLM_XPU_SPEC_DECODE_BONUS_MIN_MARGIN="${VALIDATION_SPEC_DECODE_BONUS_MIN_MARGIN}"
fi
if [[ "${VALIDATION_SPEC_DECODE_RECOVER_SUPPRESSED_REPLACEMENT:-0}" == "1" ]]; then
  export VLLM_XPU_SPEC_DECODE_RECOVER_SUPPRESSED_REPLACEMENT=1
fi
if [[ "${VALIDATION_SPEC_DECODE_KEEP_PLACEHOLDER_REPLACEMENT_SUPPRESSION:-0}" == "1" ]]; then
  # DFlash publishes concrete draft IDs inside the verifier even when the
  # scheduler-facing speculative slots are placeholders.  Keep a low-margin
  # suppression mask in that case so the ordinary one-token recovery path can
  # replace the packed verifier row instead of exposing it.
  export VLLM_XPU_SPEC_DECODE_KEEP_PLACEHOLDER_REPLACEMENT_SUPPRESSION=1
fi
if [[ "${VALIDATION_SPEC_DECODE_NO_PREEMPT_SUPPRESSED_REPLACEMENT:-0}" == "1" ]]; then
  # Preserve the exact accepted prefix and roll back only the packed target
  # tail.  The following forced M1 step recomputes the suppressed token without
  # rebuilding the request from its prompt.
  export VLLM_XPU_SPEC_DECODE_NO_PREEMPT_SUPPRESSED_REPLACEMENT=1
fi
if [[ "${VALIDATION_SPEC_DECODE_REPLAY_SUPPRESSED_REPLACEMENT_ACCEPTED:-0}" == "1" ]]; then
  export VLLM_XPU_SPEC_DECODE_REPLAY_SUPPRESSED_REPLACEMENT_ACCEPTED=1
fi
if [[ "${VALIDATION_SPEC_DECODE_RESTORE_REPLAYED_GDN_STATE:-0}" == "1" ]]; then
  export VLLM_XPU_SPEC_DECODE_RESTORE_REPLAYED_GDN_STATE=1
fi
if [[ "${VALIDATION_SPEC_DECODE_SKIP_REPLAYED_MAMBA_POSTPROCESS:-0}" == "1" ]]; then
  export VLLM_XPU_SPEC_DECODE_SKIP_REPLAYED_MAMBA_POSTPROCESS=1
fi
if [[ "${VALIDATION_GDN_SERIAL_SPEC_IDENTITY:-0}" == "1" ]]; then
  # Reproduce the established serial GDN transaction as one bounded step
  # toward a whole-model one-token verifier.  Keep every flag explicit in the
  # run identity; none is inherited from the caller.
  export VLLM_XPU_GDN_NATIVE_SPEC_DECODE=0
  export VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1
  export VLLM_XPU_GDN_SERIAL_SPEC_PACKED_DECODE=1
  export VLLM_XPU_GDN_SERIAL_SPEC_CONV=1
  export VLLM_XPU_GDN_SPEC_PROMOTE_RUNNING_AFTER_SPEC=1
  export VLLM_XPU_GDN_SPEC_PROMOTE_CONV_STATE=1
fi
if [[ "${VALIDATION_GDN_CAPTURE_NATIVE_SPEC:-0}" == "1" ]]; then
  # Diagnostic opt-in: capture the persistent-scratch native GDN op inside
  # PIECEWISE instead of crossing 48 eager producer/consumer boundaries.
  export VLLM_XPU_GDN_CAPTURE_NATIVE_SPEC=1
fi
if [[ -n "${VALIDATION_GDN_SYNC_AFTER_NATIVE_SPEC_DECODE_LAYERS:-}" ]]; then
  export VLLM_XPU_GDN_SYNC_AFTER_NATIVE_SPEC_DECODE_LAYERS="$VALIDATION_GDN_SYNC_AFTER_NATIVE_SPEC_DECODE_LAYERS"
fi
if [[ "${VALIDATION_GDN_TRACE_CONV_PUBLISH_ONCE:-0}" == "1" ]]; then
  export VLLM_XPU_GDN_TRACE_CONV_PUBLISH_ONCE=1
fi
if [[ "${VALIDATION_DISABLE_SPEC_STATIC_GRAPH_METADATA:-0}" == "1" ]]; then
  export VLLM_XPU_GDN_DISABLE_SPEC_STATIC_GRAPH_METADATA=1
fi
if [[ "$mode" == "spec" || "$mode" == "spec-native-scratch" \
  || "$mode" == "spec-native-partition" \
  || "$mode" == "spec-native-partition-exact" \
  || "$mode" == "spec-native-partition-exact-native" \
  || "$mode" == "spec-native-partition-exact-native-zero" \
  || "$mode" == "spec-native-partition-exact-native-raw" ]]; then
  if [[ "${VALIDATION_USE_BASE_XPU_KERNELS_FOR_SPEC:-0}" == "1" ]]; then
    # Exactness diagnostic: remove the historical staged-FlashAttention
    # identity difference and use the same fail-closed current XPU package as
    # the matched target.  The base runtime hashes were verified above.
    export STAGE="$base_stage"
    export VLLM_XPU_KERNELS_SRC="$base_stage"
  else
    # FULL graph capture historically required the isolated graph-safe
    # FlashAttention build. Pin both the Python extension and its device
    # library so existing reproductions cannot silently change identity.
    verify_graph_stage
    export STAGE="$graph_stage"
    export VLLM_XPU_KERNELS_SRC="$graph_stage"
  fi
  if [[ -n "${VALIDATION_FA_CHUNK_COMPLETION_OVERLAY:-}" ]]; then
    if [[ -z "${VALIDATION_FA_CHUNK_COMPLETION_OVERLAY_SHA256:-}" ]]; then
      printf 'VALIDATION_FA_CHUNK_COMPLETION_OVERLAY_SHA256 is required\n' >&2
      exit 3
    fi
    verify_sha "$VALIDATION_FA_CHUNK_COMPLETION_OVERLAY" \
      "$VALIDATION_FA_CHUNK_COMPLETION_OVERLAY_SHA256" \
      FlashAttention-completion-overlay
    export SERVER_LD_PRELOAD="$VALIDATION_FA_CHUNK_COMPLETION_OVERLAY${SERVER_LD_PRELOAD:+:$SERVER_LD_PRELOAD}"
  fi
  export QWEN36_27B_ENABLE_MTP=1
  export NUM_SPECULATIVE_TOKENS="${VALIDATION_NUM_SPECULATIVE_TOKENS:-3}"
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
    if [[ "${VALIDATION_GDN_SERIAL_SPEC_IDENTITY:-0}" == "1" ]]; then
      export VLLM_XPU_GDN_NATIVE_SPEC_DECODE=0
    fi
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
      if [[ "${VALIDATION_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT:-1}" == "1" ]]; then
        export VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1
      else
        unset VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT
      fi
      if [[ "${VALIDATION_GDN_NATIVE_SPEC_PREFIX_BASE_STATE:-0}" == "1" ]]; then
        # Preserve the canonical pre-verifier recurrent state in column zero;
        # exact verifier rows publish their successive states to columns 1-4.
        export VLLM_XPU_GDN_NATIVE_SPEC_PREFIX_BASE_STATE=1
      else
        unset VLLM_XPU_GDN_NATIVE_SPEC_PREFIX_BASE_STATE
      fi
      if [[ "${VALIDATION_GDN_NATIVE_SPEC_REPLACEMENT_PREFIX_STATE_COUNTS:-0}" == "1" ]]; then
        # A suppressed target-owned replacement is replayed from the canonical
        # prefix column, before any accepted verifier rows are recommitted.
        export VLLM_XPU_GDN_NATIVE_SPEC_REPLACEMENT_PREFIX_STATE_COUNTS=1
      else
        unset VLLM_XPU_GDN_NATIVE_SPEC_REPLACEMENT_PREFIX_STATE_COUNTS
      fi
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
  if [[ "${VALIDATION_USE_STAGED_XPU_KERNELS_FOR_TARGET:-0}" == "1" ]]; then
    # Identity-matched target control for staged-FlashAttention speculative
    # runs.  The staged tree is an FA-only Python/device-library overlay; the
    # remaining XPU extension modules continue to resolve from the verified
    # current source package.
    verify_graph_stage
    export STAGE="$graph_stage"
    export VLLM_XPU_KERNELS_SRC="$graph_stage"
  else
    export STAGE="$base_stage"
    export VLLM_XPU_KERNELS_SRC="$base_stage"
  fi
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
if [[ "$mode" == "nospec-latest-exact-native" \
  && "${VALIDATION_BATCH_INVARIANT:-0}" == "1" \
  && "${VALIDATION_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT:-0}" == "1" ]]; then
  # The GDN backend keeps broad batch-invariance support fail-closed behind
  # the production-shaped exact-native proof flag.  A one-row target does not
  # execute the speculative recurrence, but it must carry the same proof
  # contract so the ordinary GDN backend can participate in an identity-
  # matched global-invariant control.
  export VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1
fi
if [[ -n "${VALIDATION_COMPILATION_CONFIG_OVERRIDE:-}" ]]; then
  export COMPILATION_CONFIG="$VALIDATION_COMPILATION_CONFIG_OVERRIDE"
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
  && "${VALIDATION_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT:-1}" == "1" \
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
if [[ "$runner_rc" == "0" && "$RUN_SMOKE" == "1" && ! -s "$SMOKE_OUT" ]]; then
  printf 'runner reported success but smoke output is missing: %s\n' \
    "$SMOKE_OUT" >&2
  runner_rc=7
fi
if [[ "$runner_rc" == "0" && "$RUN_BENCH" == "1" && ! -s "$BENCH_OUT" ]]; then
  printf 'runner reported success but benchmark output is missing: %s\n' \
    "$BENCH_OUT" >&2
  runner_rc=8
fi
if [[ "$runner_rc" == "0" && "$RUN_QUALITY" == "1" && ! -s "$QUALITY_OUT" ]]; then
  printf 'runner reported success but quality output is missing: %s\n' \
    "$QUALITY_OUT" >&2
  runner_rc=9
fi
printf '%s\n' "$runner_rc" > "$arm_root/runner.exit-code"

if [[ -d "$compile_cache_root" ]]; then
  "$repo/scripts/canonical-tree-manifest.py" create \
    --root "$compile_cache_root" \
    --output "$arm_root/compile-cache-output-manifest.json" \
    > "$arm_root/compile-cache-manifest-create.json"
fi

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
