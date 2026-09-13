#!/usr/bin/env bash
# Publish the qualified R307 boundary repair for Qwen3.5 4B/9B fixed-depth TP1.
# This does not change the 27B or dynamic scheduled-draft R306 profile.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)
local_ref=${LOCAL_IMAGE:-neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r307}
expected_id=${EXPECTED_IMAGE_ID:-sha256:9be49c62baabf4611ecf08419d836a2e2f171adba5d2a28509b6fd796e7d28c3}
owner=${GHCR_OWNER:-steveseguin}
remote=ghcr.io/${owner}/vllm-openai-xpu-qwen38-int4:r307-v0290-fixed-depth-boundary-20260913
[[ "$(docker image inspect "${local_ref}" --format '{{.Id}}')" == "${expected_id}" ]] || { echo "local image id mismatch" >&2; exit 1; }
SKIP_IMAGE_CONTRACT=0 bash "${repo_root}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-image-contract.sh" mtp1-serial-fa-split-gdn "${local_ref}"
gh auth token | docker login ghcr.io -u "${owner}" --password-stdin
docker tag "${local_ref}" "${remote}"
docker push "${remote}"
digest=$(docker image inspect "${remote}" --format '{{index .RepoDigests 0}}')
echo "pushed: ${digest}"
echo "Verify anonymous registry access and pull by this digest before recording publication."
