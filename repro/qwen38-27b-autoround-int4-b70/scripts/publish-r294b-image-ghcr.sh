#!/usr/bin/env bash
# R294b (2026-09-12): publish the image with the class-consistent FP16 linear (R293) plus the shortlisted draft-only lm_head (R294, VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST; shortlists in /opt/draft-shortlists). Serves the Qwen3.5 4B/9B W4A16 packages.
# Publish the locally built R156 image (the R187 line uses it unchanged; R187 is a launch-time compilation config) to
# GitHub Container Registry as an optional prebuilt route. The source build (build-fixed-k-w8a16-r139-published-image.sh
# + build-gdn-split-mixed-r156-image.sh) stays the authoritative recipe; this only saves the build step.
# Needs: `gh auth refresh -h github.com -s write:packages` once (browser flow), then run this script.
set -euo pipefail
local_ref=${LOCAL_IMAGE:-neural-download/vllm-openai-xpu:qwen38-int4-draft-head-shortlist-r294b}
expected_id=${EXPECTED_IMAGE_ID:-sha256:78bd728d610995d3a05a493c21a0f8a0fdc4062baa570f1c80ade02bf374baf1}
owner=${GHCR_OWNER:-steveseguin}
remote=ghcr.io/${owner}/vllm-openai-xpu-qwen38-int4:r294b-draft-head-shortlist-20260912
[[ "$(docker image inspect "${local_ref}" --format '{{.Id}}')" == "${expected_id}" ]] || { echo "local image id mismatch" >&2; exit 1; }
gh auth token | docker login ghcr.io -u "${owner}" --password-stdin
docker tag "${local_ref}" "${remote}"
docker push "${remote}"
digest=$(docker image inspect "${remote}" --format '{{index .RepoDigests 0}}')
echo "pushed: ${digest}"
echo "Guide line to add: docker pull ${digest}  (image id ${expected_id}; verify with repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-image-contract.sh mtp1-serial-fa-split-gdn ${remote})"
