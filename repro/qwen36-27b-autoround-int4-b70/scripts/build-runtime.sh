#!/usr/bin/env bash
set -euo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "$here/../../.." && pwd)
source_root=${SOURCE_ROOT:-}
venv=${VENV:-}
jobs=${MAX_JOBS:-8}
compiler_root=${INTEL_COMPILER_ROOT:-/opt/intel/oneapi/compiler/2025.3}

if [[ -z "$source_root" || -z "$venv" ]]; then
  printf 'usage: SOURCE_ROOT=/path/from/restore VENV=/path/to/venv %s\n' "$0" >&2
  exit 2
fi
vllm="$source_root/vllm"
kernels="$source_root/vllm-xpu-kernels"
test -d "$vllm/.git"
test -d "$kernels/.git"
test -x "$compiler_root/bin/icpx"
command -v python3.12 >/dev/null

[[ $(git -C "$vllm" rev-parse HEAD) == \
  e7213ba8e13b74d7bfa3cbc05435a45df90eb76a ]]
[[ $(git -C "$vllm" diff --binary | sha256sum | awk '{print $1}') == \
  dcf84454f64bdeca546aa1697f4cd6af89fa95bb56f80ed314ad4d364e134b24 ]]
[[ $(git -C "$kernels" rev-parse HEAD) == \
  3b4effeeffd83f6ef4696bbe7e76d924a0e9d171 ]]
[[ $(git -C "$kernels" diff --binary | sha256sum | awk '{print $1}') == \
  edcb9314b43d6990474dfb5d64e3716e8d4c33618ec0e3fbd11ae671e47c8c1f ]]

if [[ -f "$compiler_root/env/vars.sh" ]]; then
  set +u
  source "$compiler_root/env/vars.sh" >/dev/null
  set -u
fi

if [[ ! -x "$venv/bin/python" ]]; then
  python3.12 -m venv "$venv"
fi
python="$venv/bin/python"

"$python" -m pip install --upgrade pip
"$python" -m pip install -r "$vllm/requirements/xpu.txt"
"$python" -m pip uninstall -y triton triton-xpu || true
"$python" -m pip install \
  --extra-index-url https://download.pytorch.org/whl/xpu \
  triton-xpu==3.7.0

MAX_JOBS="$jobs" VLLM_TARGET_DEVICE=xpu \
  "$python" -m pip install --no-build-isolation -e "$kernels" -v
VLLM_TARGET_DEVICE=xpu \
  "$python" -m pip install --no-build-isolation -e "$vllm" -v

# Build the two graph-safe FlashAttention deltas in an isolated source copy.
# This does not modify the restored kernel checkout.
SOURCE_TREE="$kernels" \
PYTHON="$python" \
MAX_JOBS="$jobs" \
INTEL_COMPILER_ROOT="$compiler_root" \
  "$repo/experiments/qwen27_graphsafe_flash_attention/build.sh" --full

stage="$repo/experiments/qwen27_graphsafe_flash_attention/work/source"
test -f "$stage/vllm_xpu_kernels/_vllm_fa2_C.abi3.so"
test -f "$stage/vllm_xpu_kernels/libattn_kernels_xe_2.so"

"$python" - <<'PY'
import torch
import vllm
import vllm_xpu_kernels
print("torch", torch.__version__)
print("vllm", getattr(vllm, "__version__", "unknown"), vllm.__file__)
print("vllm_xpu_kernels", vllm_xpu_kernels.__file__)
PY

printf 'runtime built\nVENV=%s\nSTAGE=%s\n' "$venv" "$stage"
printf 'Build success does not by itself establish speed or quality; run the full gate.\n'
