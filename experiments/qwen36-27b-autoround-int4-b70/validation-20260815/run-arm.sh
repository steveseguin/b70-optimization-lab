#!/usr/bin/env bash
set -euo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "$here/../../.." && pwd)
mode=${1:-}
gpu_pair=${2:-}
arm_root=${3:-}
quality_baseline=${4:-}

if [[ "$mode" != "spec" && "$mode" != "nospec" \
  && "$mode" != "spec-native-scratch" && "$mode" != "nospec-current" ]]; then
  printf 'usage: %s spec|nospec|spec-native-scratch|nospec-current GPU0,GPU1 ARM_ROOT [QUALITY_BASELINE]\n' "$0" >&2
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
current_identity=0
if [[ "$mode" == "spec-native-scratch" || "$mode" == "nospec-current" ]]; then
  current_identity=1
  verify_tree "$source_root/vllm" 8c27a1e68ac619e198b0c08c2d6f62b80ddb3456 \
    e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 vllm
  verify_tree "$source_root/vllm-xpu-kernels" 534bd9ccca74e0b076067a212271f896bb137d2a \
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
export BENCH_MAX_TOKENS=512
export BENCH_METRIC_TOKENS=100
export QUALITY_REPEAT_RUNS=32
export QUALITY_LONG_CONTEXT_TOKENS=1024
export REQUEST_EXTRA_JSON='{"chat_template_kwargs":{"enable_thinking":false}}'
export QUALITY_BASELINE_JSON="$quality_baseline"
if [[ "$mode" == "spec" || "$mode" == "spec-native-scratch" ]]; then
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
  if [[ "$mode" == "spec-native-scratch" ]]; then
    export VLLM_XPU_GDN_REPLAYSSM_SPEC=0
    export VLLM_XPU_GDN_NATIVE_SPEC_DECODE=1
    export VLLM_XPU_GDN_NATIVE_SPEC_DECODE_SERIAL=0
    export VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1
    export VLLM_XPU_DDTREE_FULL_GRAPH=0
    export VLLM_XPU_DDTREE_CAPTURE_GDN_CORE=0
    export VLLM_XPU_GDN_REPLAYSSM_FUSE_PENDING_METADATA=0
    export VLLM_XPU_GDN_REPLAYSSM_DIRECT_CORE_OUT=0
    export COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[4],"max_cudagraph_capture_size":4}'
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
printf '%s\n' "$runner_rc" > "$arm_root/runner.exit-code"

if [[ -s "$BENCH_OUT" ]]; then
  "$venv/bin/python" "$repo/scripts/qualify_realistic_window_metrics.py" \
    "$BENCH_OUT" --in-place > "$arm_root/qualify.log"
fi
find "$arm_root" -type f ! -name SHA256SUMS.pre-manifest -print0 \
  | sort -z | xargs -0 sha256sum \
  > "$arm_root/SHA256SUMS.pre-manifest"
exit "$runner_rc"
