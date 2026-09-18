#!/usr/bin/env bash
# Publish the locally built R311b image (R310 + rebuilt vllm-xpu-kernels r311: the single-checkpoint speculative GDN
# state op gdn_attention_ckpt; existing ops unchanged) to GitHub Container Registry as the prebuilt route for the
# one-card FP8 package. The source build (experiments/qwen38-27b-b70/docker/rebase-v0290/
# build-kernels-0.1.14.1-r311-gdn-checkpoint.sh + Dockerfile.r311-gdn-checkpoint on the public R310 image) stays the
# authoritative recipe. Run by the user (pushing to the registry creates a public artifact).
set -euo pipefail
local_ref=${LOCAL_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r311b-gdn-checkpoint}
expected_id=${EXPECTED_IMAGE_ID:-sha256:7baa32bd3a4623e93ace18b369e366951fb4b618b17927450bbd9cce15cc4dc7}
owner=${GHCR_OWNER:-steveseguin}
remote=ghcr.io/${owner}/vllm-openai-xpu-qwen38-int4:r311b-fp8-tp1-20260917
[[ "$(docker image inspect "${local_ref}" --format '{{.Id}}')" == "${expected_id}" ]] || { echo "local image id mismatch" >&2; exit 1; }
gh auth token | docker login ghcr.io -u "${owner}" --password-stdin
docker tag "${local_ref}" "${remote}"
docker push "${remote}"
digest=$(docker image inspect "${remote}" --format '{{range .RepoDigests}}{{println .}}{{end}}' | grep '^ghcr.io/' | head -1)
echo "pushed: ${digest}"
