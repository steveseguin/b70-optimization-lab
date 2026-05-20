#!/usr/bin/env bash
set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${VENV:-$HOME/.venvs/vllm-xpu}"
SRC_ROOT="${SRC_ROOT:-$HOME/src}"
VLLM_SRC="${VLLM_SRC:-$SRC_ROOT/vllm}"
LLM_SCALER_ROOT="${LLM_SCALER_ROOT:-$SRC_ROOT/llm-scaler}"
LLM_SCALER_SRC="$LLM_SCALER_ROOT/vllm/custom-esimd-kernels-vllm"
PATCH_TMP="$(mktemp -d)"
trap 'rm -rf "$PATCH_TMP"' EXIT

decode_patch() {
  local src="$1"
  local dst="$2"
  base64 -d "$src" | gzip -dc > "$dst"
}

VLLM_PATCH="$PATCH_TMP/vllm.patch"
LLM_SCALER_PATCH="$PATCH_TMP/llm-scaler.patch"
decode_patch "$THIS_DIR/patches/vllm-active-promoted-minimax-89tps-20260520.patch.gz.b64" "$VLLM_PATCH"
decode_patch "$THIS_DIR/patches/llm-scaler-active-promoted-minimax-89tps-20260520.patch.gz.b64" "$LLM_SCALER_PATCH"

mkdir -p "$SRC_ROOT"

if [ ! -d "$VLLM_SRC/.git" ]; then
  git clone https://github.com/vllm-project/vllm.git "$VLLM_SRC"
fi
git -C "$VLLM_SRC" fetch origin
git -C "$VLLM_SRC" checkout c51df43005726a09c6eb7348e8c1b00501c70a8e
git -C "$VLLM_SRC" apply --whitespace=fix "$VLLM_PATCH"

if [ ! -d "$LLM_SCALER_ROOT/.git" ]; then
  git clone https://github.com/intel/llm-scaler.git "$LLM_SCALER_ROOT"
fi
git -C "$LLM_SCALER_ROOT" fetch origin
git -C "$LLM_SCALER_ROOT" checkout 4bfc0070090cc54afdb2d46b8e57882359141568
git -C "$LLM_SCALER_SRC" apply --whitespace=fix "$LLM_SCALER_PATCH"

python3.12 -m venv "$VENV"
source "$VENV/bin/activate"
python -m pip install -U pip setuptools wheel packaging ninja cmake pybind11

# This was the working local family on 2026-05-20. If exact wheels disappear,
# use the closest current XPU nightly and record the replacement in your notes.
python -m pip install --pre --upgrade \
  torch==2.11.0+xpu torchvision==0.26.0+xpu torchaudio==2.11.0+xpu \
  --index-url https://download.pytorch.org/whl/nightly/xpu

python -m pip install -U \
  'transformers==5.7.0' 'tokenizers==0.22.2' 'safetensors==0.7.0' \
  'compressed-tensors==0.15.0.1' 'huggingface_hub==1.13.0' 'hf-xet==1.4.3' \
  'oneccl==2021.17.2' 'oneccl-devel==2021.17.2' \
  'triton-xpu==3.7.0' 'vllm-xpu-kernels==0.1.7'

source /opt/intel/oneapi/compiler/2025.3/env/vars.sh
cd "$LLM_SCALER_SRC"
python setup_moe_int4_only.py build_ext --inplace

cd "$VLLM_SRC"
python -m pip install -e . --no-build-isolation

echo "Build complete. Run scripts/03-verify-runtime.sh next."
