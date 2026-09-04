#!/usr/bin/env bash
# Publish the locally built R156 image (the R187 line uses it unchanged; R187 is a launch-time compilation config) to
# GitHub Container Registry as an optional prebuilt route. The source build (build-fixed-k-w8a16-r139-published-image.sh
# + build-gdn-split-mixed-r156-image.sh) stays the authoritative recipe; this only saves the build step.
# Needs: `gh auth refresh -h github.com -s write:packages` once (browser flow), then run this script.
set -euo pipefail
local_ref=${LOCAL_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-split-mixed-r156}
expected_id=${EXPECTED_IMAGE_ID:-sha256:173660ec18c6e98a14b9a4f573922abe9d3414999056f07ab5c3c14b55d6ceb0}
owner=${GHCR_OWNER:-steveseguin}
remote=ghcr.io/${owner}/vllm-openai-xpu-qwen38-fp8:r156-whole-graph-r187-20260903
[[ "$(docker image inspect "${local_ref}" --format '{{.Id}}')" == "${expected_id}" ]] || { echo "local image id mismatch" >&2; exit 1; }
gh auth token | docker login ghcr.io -u "${owner}" --password-stdin
docker tag "${local_ref}" "${remote}"
docker push "${remote}"
digest=$(docker image inspect "${remote}" --format '{{index .RepoDigests 0}}')
echo "pushed: ${digest}"
echo "Guide line to add: docker pull ${digest}  (image id ${expected_id}; verify with repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-image-contract.sh mtp1-serial-fa-split-gdn ${remote})"
