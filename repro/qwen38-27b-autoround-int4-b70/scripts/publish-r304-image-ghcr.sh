#!/usr/bin/env bash
# R304 (2026-09-13): publish the runtime rebased onto stock vLLM XPU v0.29.0 (R301 = ported overlays + kernels 0.1.14.1
# with the lab's oneDNN GEMM patches; R302 adds the vLLM #53059 alias guard; R303 adds the #51565 GDN first-chunk fix; R304 adds the #53542 active-width fix). Source:
# experiments/qwen38-27b-b70/docker/rebase-v0290/Dockerfile.r301-v0290-rebase (kernel libraries from
# build-kernels-0.1.14.1-clean-clone.sh) then Dockerfile.r302-alias-guard , Dockerfile.r303-gdn-phase-fix and Dockerfile.r304-gdn-active-width. Serve with VLLM_USE_V2_MODEL_RUNNER=0 (the
# launchers pin it). Needs: `gh auth refresh -h github.com -s write:packages` once, then run this script.
set -euo pipefail
local_ref=${LOCAL_IMAGE:-neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r304}
expected_id=${EXPECTED_IMAGE_ID:-sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2}
owner=${GHCR_OWNER:-steveseguin}
remote=ghcr.io/${owner}/vllm-openai-xpu-qwen38-int4:r304-v0290-rebase-20260913
[[ "$(docker image inspect "${local_ref}" --format '{{.Id}}')" == "${expected_id}" ]] || { echo "local image id mismatch" >&2; exit 1; }
gh auth token | docker login ghcr.io -u "${owner}" --password-stdin
docker tag "${local_ref}" "${remote}"
docker push "${remote}"
digest=$(docker image inspect "${remote}" --format '{{index .RepoDigests 0}}')
echo "pushed: ${digest}"
echo "Guide line to add: docker pull ${digest}  (image id ${expected_id}; verify with repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-image-contract.sh mtp1-serial-fa-split-gdn ${remote})"
