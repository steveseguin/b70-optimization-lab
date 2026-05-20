#!/usr/bin/env bash
set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$THIS_DIR/configs/promoted-env.sh"
source "$VENV/bin/activate"

python - <<'PY'
import importlib
import inspect
import os
import sys

import torch
import vllm

print("python", sys.version.replace("\n", " "))
print("torch", torch.__version__)
print("torch_xpu_available", torch.xpu.is_available())
print("torch_xpu_device_count", torch.xpu.device_count())
print("vllm", vllm.__version__, inspect.getfile(vllm))

mod = importlib.import_module("custom_esimd_kernels_vllm")
print("llm_scaler_module", inspect.getfile(mod))

ops = importlib.import_module("custom_esimd_kernels_vllm.ops")
for name in [
    "moe_forward_tiny_cutlass_nmajor_int4_u4_minimax_ws",
    "moe_forward_tiny_cutlass_nmajor_int4_u4_minimax",
]:
    print(name, hasattr(ops, name))

print("VLLM_XPU_USE_LLM_SCALER_MOE", os.environ.get("VLLM_XPU_USE_LLM_SCALER_MOE"))
print("VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP", os.environ.get("VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP"))
PY

xpu-smi discovery -j
xpu-smi topology -m || true

