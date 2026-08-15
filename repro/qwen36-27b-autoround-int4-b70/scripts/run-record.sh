#!/usr/bin/env bash
set -euo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "$here/../../.." && pwd)
config="$repo/repro/qwen36-27b-autoround-int4-b70/configs/record.env"
source_root=${SOURCE_ROOT:-}
model_dir=${MODEL_DIR:-}
venv=${VENV:-}
stage=${STAGE:-$repo/experiments/qwen27_graphsafe_flash_attention/work/source}
oneccl=${ONECCL_INSTALL_DIR:-}
gpu_index=${GPU_INDEX:-0,1}
port=${PORT:-19622}
stamp=${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}
run_root=${RUN_ROOT:-$PWD/qwen-int4-repro-runs}
run_dir=${RUN_DIR:-$run_root/qwen27-int4-tp2-record-repro-$stamp}
lock_file=${LOCK_FILE:-/tmp/b70-benchmark.lock}

if [[ -z "$source_root" || -z "$model_dir" || -z "$venv" || -z "$oneccl" ]]; then
  printf 'required: SOURCE_ROOT MODEL_DIR VENV ONECCL_INSTALL_DIR\n' >&2
  exit 2
fi
if [[ -e "$run_dir" ]]; then
  printf 'refusing to overwrite existing run directory: %s\n' "$run_dir" >&2
  exit 2
fi
if [[ ! "$gpu_index" =~ ^[0-9]+,[0-9]+$ ]]; then
  printf 'GPU_INDEX must contain exactly two physical indices, for example 0,1\n' >&2
  exit 2
fi

vllm="$source_root/vllm"
kernels="$source_root/vllm-xpu-kernels"
test -x "$venv/bin/python"
test -d "$model_dir"
test -f "$stage/vllm_xpu_kernels/_vllm_fa2_C.abi3.so"
test -f "$stage/vllm_xpu_kernels/libattn_kernels_xe_2.so"

PYTHON="$venv/bin/python" MODEL_DIR="$model_dir" \
  "$here/download-model.sh" >/dev/null
"$venv/bin/python" - "$vllm" <<'PY'
import sys
from pathlib import Path

import torch
import vllm

expected = Path(sys.argv[1]).resolve()
actual = Path(vllm.__file__).resolve()
if not actual.is_relative_to(expected):
    raise SystemExit(f"venv imports vLLM from {actual}, expected {expected}")
if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"record requires Python 3.12, got {sys.version}")
if torch.__version__ != "2.11.0+xpu":
    raise SystemExit(f"record requires torch 2.11.0+xpu, got {torch.__version__}")
PY

verify_tree() {
  local tree=$1
  local expected_head=$2
  local expected_diff=$3
  local name=$4
  local actual_head actual_diff
  actual_head=$(git -C "$tree" rev-parse HEAD)
  actual_diff=$(git -C "$tree" diff --binary | sha256sum | awk '{print $1}')
  if [[ "$actual_head" != "$expected_head" || "$actual_diff" != "$expected_diff" ]]; then
    printf '%s source mismatch: head=%s diff=%s\n' \
      "$name" "$actual_head" "$actual_diff" >&2
    exit 3
  fi
}
verify_tree "$vllm" e7213ba8e13b74d7bfa3cbc05435a45df90eb76a \
  dcf84454f64bdeca546aa1697f4cd6af89fa95bb56f80ed314ad4d364e134b24 vllm
verify_tree "$kernels" 3b4effeeffd83f6ef4696bbe7e76d924a0e9d171 \
  edcb9314b43d6990474dfb5d64e3716e8d4c33618ec0e3fbd11ae671e47c8c1f kernels

lib="$oneccl/lib/libccl.so.1.0"
spv="$oneccl/lib/ccl/kernels/kernels.spv"
[[ $(sha256sum "$lib" | awk '{print $1}') == \
  43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700 ]]
[[ $(sha256sum "$spv" | awk '{print $1}') == \
  0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9 ]]

# Remove inherited experiment switches. The record config below repopulates
# the complete positive identity instead of inheriting a caller's sweep state.
while IFS= read -r name; do
  case "$name" in
    VLLM_*|QWEN36_27B_*|XPU_GRAPH|COMPILATION_CONFIG|CCL_*|ONECCL_*|SERVER_*|ZE_AFFINITY_MASK|ONEAPI_DEVICE_SELECTOR|QUALITY_*|BENCH_*|RUN_SMOKE|RUN_BENCH|RUN_QUALITY|REQUEST_EXTRA_JSON|CANDIDATE_ENTRYPOINT)
      unset "$name"
      ;;
  esac
done < <(compgen -e)
unset PYTHONPATH LD_PRELOAD LD_LIBRARY_PATH TORCHINDUCTOR_CACHE_DIR

# shellcheck source=../configs/record.env
source "$config"
export SOURCE_ROOT="$source_root"
export VLLM_SOURCE_TREE="$vllm"
export VLLM_XPU_KERNELS_SOURCE_TREE="$kernels"
export MODEL_DIR="$model_dir"
export QWEN36_27B_AR_VENV="$venv"
export STAGE
export VLLM_XPU_KERNELS_SRC="$stage"
export ONECCL_INSTALL_DIR="$oneccl"
export GPU_INDEX="$gpu_index"
export ZE_AFFINITY_MASK="$gpu_index"
export ONEAPI_DEVICE_SELECTOR=level_zero:0,1
export PORT="$port"
export STAMP="$stamp"
export RUN_ROOT="$run_root"
export RUN_DIR="$run_dir/run"
export OUT_DIR="$run_dir/data"
export VLLM_CACHE_ROOT="$run_dir/vllm-cache"
export LABEL=qwen27-tp2-fp16-fullgraph-transaction-repro
export SERVED_MODEL_NAME=qwen27-tp2-targetgraph-drafteager
export QUALITY_BASELINE_JSON="$repo/data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-replayssm-draftint4-current-confirm-20260706T140317Z-repeat64-ctx1024-20260706T140317Z.json"

mkdir -p -- "$run_root"
exec 9>"$lock_file"
if ! flock -n 9; then
  printf 'GPU benchmark lock is held: %s\n' "$lock_file" >&2
  exit 4
fi

exec "$repo/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-fullgraph-transaction-candidate.sh"
