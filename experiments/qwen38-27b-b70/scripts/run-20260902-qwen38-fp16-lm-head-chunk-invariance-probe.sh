#!/usr/bin/env bash
# One-card operator probe in the R139 image; no server, no second GPU.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
out=${OUT_DIR:-/mnt/fast-ai/bench-results/qwen38-fp16-lm-head-chunk-invariance-20260902}
image=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-fixed-k-w8a16-r139
[[ ! -e "${out}" ]] || { echo "exists: ${out}" >&2; exit 1; }
mkdir -p "${out}"
docker run --rm --name qwen38-lmhead-chunk-probe --device /dev/dri:/dev/dri --group-add render \
  --memory 8g --ulimit core=0 -e ONEAPI_DEVICE_SELECTOR="${DEVICE_SELECTOR:-level_zero:0}" \
  -v "${script_dir}/probe-qwen38-fp16-lm-head-chunk-invariance.py:/tmp/probe.py:ro" -v "${out}:/out" \
  --workdir /tmp --entrypoint python3 "${image}" /tmp/probe.py --out /out/result.json | tee "${out}/run.log"
