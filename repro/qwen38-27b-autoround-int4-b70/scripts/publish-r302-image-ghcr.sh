#!/usr/bin/env bash
# R302 (2026-09-13): publish the runtime rebased onto stock vLLM XPU v0.29.0 (R301 = ported overlays + kernels 0.1.14.1
# with the lab's oneDNN GEMM patches; R302 adds the vLLM #53059 uniform-decode alias guard). Source build:
# experiments/qwen38-27b-b70/docker/rebase-v0290/Dockerfile.r301-v0290-rebase (kernel libraries from
# build-kernels-0.1.14.1-clean-clone.sh) then Dockerfile.r302-alias-guard. Serve with VLLM_USE_V2_MODEL_RUNNER=0 (the
# launchers pin it). Needs: `gh auth refresh -h github.com -s write:packages` once, then run this script.
set -euo pipefail
local_ref=${LOCAL_IMAGE:-neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r302}
expected_id=${EXPECTED_IMAGE_ID:-sha256:db6f0004d3c0a303f996f6f433fc40940e045e7add5728933bd30f21568a34e9}
owner=${GHCR_OWNER:-steveseguin}
remote=ghcr.io/${owner}/vllm-openai-xpu-qwen38-int4:r302-v0290-rebase-alias-guard-20260913
[[ "$(docker image inspect "${local_ref}" --format '{{.Id}}')" == "${expected_id}" ]] || { echo "local image id mismatch" >&2; exit 1; }
gh auth token | docker login ghcr.io -u "${owner}" --password-stdin
docker tag "${local_ref}" "${remote}"
docker push "${remote}"
digest=$(docker image inspect "${remote}" --format '{{index .RepoDigests 0}}')
echo "pushed: ${digest}"
echo "Guide line to add: docker pull ${digest}  (image id ${expected_id}; verify with repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-image-contract.sh mtp1-serial-fa-split-gdn ${remote})"
