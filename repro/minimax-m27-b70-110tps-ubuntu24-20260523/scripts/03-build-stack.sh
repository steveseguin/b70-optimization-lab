#!/usr/bin/env bash
set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$THIS_DIR/../.." && pwd)"
source "$THIS_DIR/configs/runtime-env.sh"

VLLM_XPU_KERNELS_SRC="${VLLM_XPU_KERNELS_SRC:-$SRC_ROOT/vllm-xpu-kernels}"
SWAP_FILE="${SWAP_FILE:-/swap-codex-xpu-build-160g}"
SWAP_SIZE="${SWAP_SIZE:-160G}"
CREATE_BUILD_SWAP="${CREATE_BUILD_SWAP:-1}"

cleanup_swap() {
  if [ "$CREATE_BUILD_SWAP" = "1" ] && [ -f "$SWAP_FILE" ]; then
    echo "Removing temporary build swap $SWAP_FILE"
    sudo swapoff "$SWAP_FILE" 2>/dev/null || true
    sudo rm -f "$SWAP_FILE"
  fi
}
trap cleanup_swap EXIT

if [ "$CREATE_BUILD_SWAP" = "1" ] && [ ! -f "$SWAP_FILE" ]; then
  echo "Creating temporary SSD swap $SWAP_FILE ($SWAP_SIZE)."
  echo "This protects the vllm-xpu-kernels paged_decode_xe2.cpp compile on low-RAM machines."
  sudo fallocate -l "$SWAP_SIZE" "$SWAP_FILE"
  sudo chmod 600 "$SWAP_FILE"
  sudo mkswap "$SWAP_FILE"
  sudo swapon "$SWAP_FILE"
fi

mkdir -p "$SRC_ROOT"

checkout_clean() {
  local repo="$1"
  local commit="$2"
  git -C "$repo" fetch origin
  git -C "$repo" checkout "$commit"
  if [ -n "$(git -C "$repo" status --porcelain)" ]; then
    if [ "${ALLOW_DESTRUCTIVE_RECHECKOUT:-0}" != "1" ]; then
      echo "$repo has local changes after checkout; refusing to reset." >&2
      echo "Use a clean SRC_ROOT or set ALLOW_DESTRUCTIVE_RECHECKOUT=1 for a disposable checkout." >&2
      exit 2
    fi
    git -C "$repo" reset --hard "$commit"
  fi
}

if [ ! -d "$VLLM_SRC/.git" ]; then
  git clone https://github.com/vllm-project/vllm.git "$VLLM_SRC"
fi
checkout_clean "$VLLM_SRC" c51df43005726a09c6eb7348e8c1b00501c70a8e

if [ ! -d "$LLM_SCALER_ROOT/.git" ]; then
  git clone https://github.com/intel/llm-scaler.git "$LLM_SCALER_ROOT"
fi
checkout_clean "$LLM_SCALER_ROOT" 4bfc0070090cc54afdb2d46b8e57882359141568

if [ ! -d "$VLLM_XPU_KERNELS_SRC/.git" ]; then
  git clone https://github.com/intel/vllm-xpu-kernels.git "$VLLM_XPU_KERNELS_SRC"
fi
checkout_clean "$VLLM_XPU_KERNELS_SRC" 28e1f5e74c15744b69cf3b760f6160ceabd15de0
git -C "$VLLM_XPU_KERNELS_SRC" submodule update --init --recursive

patch_tmp="$(mktemp -d)"
trap 'rm -rf "$patch_tmp"; cleanup_swap' EXIT
base64 -d "$REPO_ROOT/repro/minimax-m27-b70-89tps-20260520/patches/vllm-active-promoted-minimax-89tps-20260520.patch.gz.b64" \
  | gzip -dc > "$patch_tmp/vllm.patch"
base64 -d "$REPO_ROOT/repro/minimax-m27-b70-89tps-20260520/patches/llm-scaler-active-promoted-minimax-89tps-20260520.patch.gz.b64" \
  | gzip -dc > "$patch_tmp/llm-scaler.patch"

git -C "$VLLM_SRC" apply --whitespace=fix "$patch_tmp/vllm.patch"
git -C "$LLM_SCALER_ROOT" apply --directory=vllm/custom-esimd-kernels-vllm --whitespace=fix "$patch_tmp/llm-scaler.patch"

python3.12 -m venv "$VENV"
source "$VENV/bin/activate"
python -m pip install -U pip setuptools wheel packaging ninja cmake pybind11

python -m pip install \
  --index-url https://download.pytorch.org/whl/xpu \
  --extra-index-url https://pypi.org/simple \
  'torch==2.11.0+xpu' 'torchvision==0.26.0+xpu' 'torchaudio==2.11.0+xpu'

python -m pip install -U \
  'transformers==5.7.0' 'tokenizers==0.22.2' 'safetensors==0.7.0' \
  'compressed-tensors==0.15.0.1' 'huggingface_hub==1.13.0' 'hf-xet==1.4.3' \
  'oneccl==2021.17.2' 'oneccl-devel==2021.17.2' \
  'triton-xpu==3.7.0'

source /opt/intel/oneapi/compiler/2025.3/env/vars.sh >/dev/null 2>&1
export SYCL_HOME=/opt/intel/oneapi/compiler/2025.3
export TORCH_XPU_ARCH_LIST=bmg

cd "$VLLM_XPU_KERNELS_SRC"
rm -rf build
MAX_JOBS="${VLLM_XPU_KERNELS_MAX_JOBS:-8}" \
  python -m pip install --no-build-isolation --no-deps -e . -v

cd "$LLM_SCALER_ROOT/vllm/custom-esimd-kernels-vllm"
rm -rf build
MAX_JOBS="${LLM_SCALER_MAX_JOBS:-4}" \
  python setup_moe_int4_only.py build_ext --inplace

cd "$VLLM_SRC"
python -m pip install -e . --no-build-isolation

echo "Build complete. Run scripts/04-verify-runtime.sh next."
