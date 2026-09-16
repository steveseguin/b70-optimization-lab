#!/usr/bin/env bash
# Publish the locally built R310 image (R304 + rebuilt vllm-xpu-kernels: oneDNN r309 one-card fixed-K shapes and
# kernels r310 GDN output fences) to GitHub Container Registry as the prebuilt route for the one-card FP8 package.
# The source build (experiments/qwen38-27b-b70/docker/rebase-v0290/build-kernels-0.1.14.1-r310-gdn-barriers.sh +
# Dockerfile.r310-gdn-barriers on the public R304 image) stays the authoritative recipe.
set -euo pipefail
local_ref=${LOCAL_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r310-gdn-barriers}
expected_id=${EXPECTED_IMAGE_ID:-sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04}
owner=${GHCR_OWNER:-steveseguin}
remote=ghcr.io/${owner}/vllm-openai-xpu-qwen38-int4:r310-fp8-tp1-20260915
[[ "$(docker image inspect "${local_ref}" --format '{{.Id}}')" == "${expected_id}" ]] || { echo "local image id mismatch" >&2; exit 1; }
gh auth token | docker login ghcr.io -u "${owner}" --password-stdin
docker tag "${local_ref}" "${remote}"
docker push "${remote}"
digest=$(docker image inspect "${remote}" --format '{{range .RepoDigests}}{{println .}}{{end}}' | grep '^ghcr.io/' | head -1)
echo "pushed: ${digest}"
