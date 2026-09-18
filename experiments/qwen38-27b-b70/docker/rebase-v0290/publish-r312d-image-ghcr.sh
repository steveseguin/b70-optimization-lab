#!/usr/bin/env bash
# Publish the locally built R312d-c image (R311b + the multi-position verifier attention op paged_decode_multiq in
# _xpu_C, its device library built with DPC++ 2026.0 and the sycl-tla revision the kernel CMake pins; existing ops
# unchanged) to GitHub Container Registry as the prebuilt route for the one-card FP8 package. The source build
# (experiments/qwen38-27b-b70/docker/rebase-v0290/build-kernels-0.1.14.1-r312c-multiq.sh + Dockerfile.r312c-multiq on
# the R311b image, then build-kernels-0.1.14.1-r312d-multiq-toolchain.sh VARIANT=c + Dockerfile.r312d-multiq) stays the
# authoritative recipe. Run by the user: pushing to the registry creates a public artifact, which the agent's safety
# layer refuses to do on its own (2026-09-18).
set -euo pipefail
local_ref=${LOCAL_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r312d-c-multiq}
expected_id=${EXPECTED_IMAGE_ID:-sha256:ea61e69834d02b4abfe435eaaf56b2eda7b7b7c5ac78fffa3740779d8f27353a}
owner=${GHCR_OWNER:-steveseguin}
remote=ghcr.io/${owner}/vllm-openai-xpu-qwen38-int4:r312d-fp8-tp1-20260918
[[ "$(docker image inspect "${local_ref}" --format '{{.Id}}')" == "${expected_id}" ]] || { echo "local image id mismatch" >&2; exit 1; }
gh auth token | docker login ghcr.io -u "${owner}" --password-stdin
docker tag "${local_ref}" "${remote}"
docker push "${remote}"
digest=$(docker image inspect "${remote}" --format '{{range .RepoDigests}}{{println .}}{{end}}' | grep '^ghcr.io/' | head -1)
echo "pushed: ${digest}"
