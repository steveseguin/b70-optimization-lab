#!/usr/bin/env bash
set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$THIS_DIR/configs/runtime-env.sh"
source "$VENV/bin/activate"
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh >/dev/null 2>&1

python - <<'PY'
import torch
from vllm.platforms import current_platform
import vllm
import vllm_xpu_kernels
import custom_esimd_kernels_vllm.moe_int4_ops as moe

print("platform", current_platform.device_type)
print("torch", torch.__version__, torch.xpu.is_available(), torch.xpu.device_count())
print("vllm", vllm.__version__)
print("vllm_xpu_kernels", getattr(vllm_xpu_kernels, "__version__", "ok"))
print("moe_int4_ops", moe.__name__)
assert current_platform.device_type == "xpu"
assert torch.xpu.is_available()
assert torch.xpu.device_count() == 4
PY

xpu-smi discovery
clinfo -l

