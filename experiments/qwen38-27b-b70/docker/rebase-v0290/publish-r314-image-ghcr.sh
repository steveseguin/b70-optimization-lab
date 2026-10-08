#!/usr/bin/env bash
# Publish the locally built R314 image (R310 with only _xpu_C.abi3.so replaced: vllm-xpu-kernels patches r313, the
# speculative GDN kernel carries the SSM state between verify rows through the slot's float16 rounding exactly as
# one-token decode does, and r314, the state table may be handed in with a wide row stride; Python and every other
# file are R310's byte for byte) to GitHub Container Registry as the prebuilt route for the two-card FP8 package's
# drafting-under-load work. The source build (build-kernels-0.1.14.1-r314-state-stride.sh, then
# Dockerfile.r314-state-stride on the R310 image) stays the authoritative recipe; the local image ID is recorded in
# experiments/qwen38-27b-b70/data/2026-10-04-r314/image-id.txt. Run by the user: pushing to the registry creates a
# public artifact, which the agent's safety layer refuses to do on its own (2026-09-18).
set -euo pipefail
local_ref=${LOCAL_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride}
expected_id=${EXPECTED_IMAGE_ID:-sha256:8b78916004ca6581822b6e1f06791f94586a6c1d265c3f63b81b49c09bee1525}
owner=${GHCR_OWNER:-steveseguin}
remote=ghcr.io/${owner}/vllm-openai-xpu-qwen38-int4:r314-fp8-tp2-20261007
[[ "$(docker image inspect "${local_ref}" --format '{{.Id}}')" == "${expected_id}" ]] || { echo "local image id mismatch" >&2; exit 1; }
gh auth token | docker login ghcr.io -u "${owner}" --password-stdin
docker tag "${local_ref}" "${remote}"
docker push "${remote}"
digest=$(docker image inspect "${remote}" --format '{{range .RepoDigests}}{{println .}}{{end}}' | grep '^ghcr.io/' | head -1)
echo "pushed: ${digest}"
