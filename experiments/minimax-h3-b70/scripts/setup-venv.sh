#!/usr/bin/env bash
# Build the GPU venv for the MiniMax-H3 two-B70 lane: /mnt/fast-ai/venvs/minimax-h3
#
# THIS SCRIPT DOWNLOADS (~8-10 GB of wheels). It was written but deliberately NOT run by the
# agent that prepared this lane, because that session was under a no-download rule and none of
# the XPU wheels are cached on this host (~/.cache/pip holds 268 MB; the only torch on disk is
# the CPU build in /mnt/fast-ai/venvs/minimax-h3-cpu and the 2.11.0+xpu build inside
# /home/steve/.venvs/vllm-xpu, which belongs to the FP8 lane and must not be reused or mutated).
#
# Run it deliberately, with the cards idle, and record the resolved versions:
#
#     ./setup-venv.sh --yes
#     /mnt/fast-ai/venvs/minimax-h3/bin/pip freeze > ../data/environment.txt
#
# The runtime is pinned to the LTX 2.5 lane's captured, proven PyTorch-XPU stack
# (experiments/ltx25-b70/data/environment.txt) -- same torch/torchvision/torchaudio/triton and the
# same oneAPI 2026.1 runtime wheels -- so that a MiniMax-H3 fault can be compared against a lane
# that is known to work on these cards. The additions on top are diffusers (git main, editable
# from the checkout already on disk) and PyAV.
#
# It goes on /mnt/fast-ai, not on /: the root filesystem has ~22 GB free and this venv is ~10 GB.
set -euo pipefail

VENV="${VENV:-/mnt/fast-ai/venvs/minimax-h3}"
DIFFUSERS_SRC="${DIFFUSERS_SRC:-/mnt/fast-ai/build/diffusers-src}"
XPU_INDEX="${XPU_INDEX:-https://download.pytorch.org/whl/xpu}"
PYTHON="${PYTHON:-python3.12}"

if [[ "${1:-}" != "--yes" ]]; then
  cat >&2 <<EOF
This downloads roughly 8-10 GB of wheels into ${VENV}.
Re-run with --yes once that is intended.

  torch==2.14.0+xpu torchvision==0.29.0+xpu torchaudio==2.11.0+xpu   from ${XPU_INDEX}
  triton-xpu==3.8.0 and the oneAPI 2026.1 runtime wheels             (pulled as dependencies)
  transformers==5.17.0 safetensors==0.8.0 numpy==2.5.2 av==18.1.0 accelerate huggingface-hub
  diffusers  -e ${DIFFUSERS_SRC}   (git $(git -C "${DIFFUSERS_SRC}" rev-parse --short HEAD 2>/dev/null || echo '?'))
EOF
  exit 1
fi

test -d "${DIFFUSERS_SRC}" || { echo "missing diffusers checkout: ${DIFFUSERS_SRC}" >&2; exit 1; }
DIFFUSERS_COMMIT="$(git -C "${DIFFUSERS_SRC}" rev-parse HEAD)"
echo "diffusers source commit: ${DIFFUSERS_COMMIT}"

"${PYTHON}" -m venv "${VENV}"
"${VENV}/bin/pip" install --upgrade pip wheel

# 1. The XPU torch stack, from the same index the other lanes on this host used.
"${VENV}/bin/pip" install --index-url "${XPU_INDEX}" \
  "torch==2.14.0+xpu" "torchvision==0.29.0+xpu" "torchaudio==2.11.0+xpu"

# 2. Everything else from PyPI, pinned to the LTX lane's captured versions where it has one.
"${VENV}/bin/pip" install \
  "transformers==5.17.0" \
  "safetensors==0.8.0" \
  "numpy==2.5.2" \
  "av==18.1.0" \
  "accelerate" \
  "huggingface-hub" \
  "requests" "regex" "Pillow" "importlib_metadata"

# 3. diffusers from the checkout on disk. The MiniMax-H3 checkpoints declare 0.36.0.dev0, i.e. a
#    git-main build: there is no release that carries MiniMaxH3Transformer3DModel.
"${VENV}/bin/pip" install --no-deps -e "${DIFFUSERS_SRC}"

# 4. The check the lane brief asks for. Importing torch is fine; no XPU tensor is created here.
"${VENV}/bin/python" -c "import torch, diffusers; print(torch.__version__, diffusers.__version__)"

# 5. And the checks that actually matter for this lane.
"${VENV}/bin/python" - <<'PY'
import torch, diffusers, transformers, av, safetensors
print("torch       ", torch.__version__)
print("diffusers   ", diffusers.__version__, "<- must be 0.36.0.dev0 or newer")
print("transformers", transformers.__version__)
print("av          ", av.__version__)
print("safetensors ", safetensors.__version__)
print("xpu visible ", torch.xpu.is_available(), torch.xpu.device_count(), "device(s)")
from diffusers import MiniMaxH3Transformer3DModel, MiniMaxH3Scheduler  # noqa: F401
from diffusers import AutoencoderKLMiniMaxH3, AutoencoderKLMiniMaxH3Audio  # noqa: F401
from diffusers.modular_pipelines.minimax_h3.modular_blocks_minimax_h3 import MiniMaxH3CoreDenoiseStep  # noqa: F401
from transformers import Qwen3VLForConditionalGeneration  # noqa: F401
print("every MiniMax-H3 class this lane needs imported cleanly")
PY

echo
echo "built ${VENV} on diffusers ${DIFFUSERS_COMMIT}"
echo "record it:  ${VENV}/bin/pip freeze > $(dirname "$0")/../data/environment.txt"
