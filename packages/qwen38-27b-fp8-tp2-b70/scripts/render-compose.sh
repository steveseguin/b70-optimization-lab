#!/usr/bin/env bash
# Regenerate compose.yaml from the package launcher's own `docker run` argv (serve.py render), so the packet cannot
# drift away from the configuration that produced the measured result. Nothing is started and no GPU is touched.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); repo=$(cd -- "${here}/../../.." && pwd)
pkg=packages/qwen38-27b-fp8-tp2-b70
launcher=${LAUNCHER_PATH:-${pkg}/scripts/serve.py}
work=$(mktemp -d); trap 'rm -rf "${work}"' EXIT
python3 "${repo}/${launcher}" render --profile recommended --out "${work}/argv-two.nul" >/dev/null
OVERLAY_VOLUME="./overlays:/overlay:ro" PROFILE_NOTE="with the draft-only INT4 shortlist head and decode-identical verifier rows (XPU graphs off)." \
python3 "${repo}/tools/render-container-compose.py" - "${work}/argv-two.nul" "${repo}/${pkg}/compose.yaml" \
  ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04 \
  "Qwen/Qwen3.8-27B-FP8" "${pkg}/scripts/serve.py" "${pkg}/scripts/render-compose.sh" qwen38-27b-fp8 5
