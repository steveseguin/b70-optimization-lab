#!/usr/bin/env bash
# R293 (2026-09-11): publish the INT4 image with the class-consistent FP16 linear (R276 + r290-r293 patches: VLLM_XPU_FP16_LINEAR_CLASSPAD=1 keeps every unquantized linear in one verified oneDNN M-class instead of 32-row pieces; off by default).
# Publish the locally built R156 image (the R187 line uses it unchanged; R187 is a launch-time compilation config) to
# GitHub Container Registry as an optional prebuilt route. The source build (build-fixed-k-w8a16-r139-published-image.sh
# + build-gdn-split-mixed-r156-image.sh) stays the authoritative recipe; this only saves the build step.
# Needs: `gh auth refresh -h github.com -s write:packages` once (browser flow), then run this script.
set -euo pipefail
local_ref=${LOCAL_IMAGE:-neural-download/vllm-openai-xpu:qwen38-int4-fp16-linear-classpad-cheapest-r293}
expected_id=${EXPECTED_IMAGE_ID:-sha256:40d46730c9a24f9396cc67c0e5578dd80d11dfae7a4d23a55f97620140a0b3e6}
owner=${GHCR_OWNER:-steveseguin}
remote=ghcr.io/${owner}/vllm-openai-xpu-qwen38-int4:r293-fp16-linear-classpad-20260911
[[ "$(docker image inspect "${local_ref}" --format '{{.Id}}')" == "${expected_id}" ]] || { echo "local image id mismatch" >&2; exit 1; }
gh auth token | docker login ghcr.io -u "${owner}" --password-stdin
docker tag "${local_ref}" "${remote}"
docker push "${remote}"
digest=$(docker image inspect "${remote}" --format '{{index .RepoDigests 0}}')
echo "pushed: ${digest}"
echo "Guide line to add: docker pull ${digest}  (image id ${expected_id}; verify with repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-image-contract.sh mtp1-serial-fa-split-gdn ${remote})"
