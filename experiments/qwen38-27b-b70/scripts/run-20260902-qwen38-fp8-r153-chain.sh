#!/usr/bin/env bash
# After R152: host submission-latency probe (one card), then the R153a and R153b
# campaigns with the R152 runner (same gates), sequentially.
set -uo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
out=/mnt/fast-ai/bench-results
docker run --rm --name qwen38-host-probe --device /dev/dri:/dev/dri --group-add render --memory 6g -e ONEAPI_DEVICE_SELECTOR=level_zero:0 -e VLLM_TARGET_DEVICE=xpu \
  -v "${script_dir}/qwen38-fp8-host-submission-latency-probe.py:/tmp/p.py:ro" -v "${out}:/out" --workdir /tmp --entrypoint python3 \
  neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-fixed-k-w8a16-r139 /tmp/p.py /out/qwen38-host-submission-latency-probe-20260902.json >"${out}/host-probe.log" 2>&1
ROOT="${out}/qwen38-fp8-triton-rmsnorm-fast-20260902-r153a" IMAGE_OVERRIDE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-triton-rmsnorm-r153a \
  IMAGE_ID_OVERRIDE=sha256:e168f4705e935a6771310bc7e8d579fb79c2190c22f1110b570aa08ad91a9c5f \
  LAYERNORM_SHA256_OVERRIDE=37c65a77cd398e4d560f797c74c236336910683dfed3a2dc8259878d86e456a9 \
  "${script_dir}/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh" >"${out}/r153a-runner.nohup" 2>&1
ROOT="${out}/qwen38-fp8-triton-rmsnorm-fast-20260902-r153b" IMAGE_OVERRIDE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-triton-rmsnorm-r153b \
  IMAGE_ID_OVERRIDE=sha256:9104dfd23ae89af1abaeaba1d91c505459dc457c0419d39825ff740a4f748efc \
  LAYERNORM_SHA256_OVERRIDE=415f115b413e6e2d28f0b3dad4147e59c406e0b0de40264e9ffbc6c4d0829f2b \
  "${script_dir}/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh" >"${out}/r153b-runner.nohup" 2>&1
