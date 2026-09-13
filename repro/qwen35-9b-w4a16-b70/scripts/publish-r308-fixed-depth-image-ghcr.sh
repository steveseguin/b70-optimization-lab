#!/usr/bin/env bash
# Publish the qualified R308 boundary repair for Qwen3.5 4B/9B fixed-depth TP1.
# This does not change the 27B or dynamic scheduled-draft R306 profile.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)
local_ref=${LOCAL_IMAGE:-rebase/r308-state-resume}
expected_id=${EXPECTED_IMAGE_ID:?set EXPECTED_IMAGE_ID to the qualified immutable R308 image ID}
[[ "${expected_id}" =~ ^sha256:[0-9a-f]{64}$ ]] || { echo "invalid immutable image ID" >&2; exit 1; }
owner=${GHCR_OWNER:-steveseguin}
remote=ghcr.io/${owner}/vllm-openai-xpu-qwen38-int4:r308-v0290-fixed-depth-state-resume-20260913
[[ "$(docker image inspect "${local_ref}" --format '{{.Id}}')" == "${expected_id}" ]] || { echo "local image id mismatch" >&2; exit 1; }
SKIP_IMAGE_CONTRACT=0 bash "${repo_root}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-image-contract.sh" mtp1-serial-fa-split-gdn "${local_ref}"
gh auth token | docker login ghcr.io -u "${owner}" --password-stdin
docker tag "${local_ref}" "${remote}"
docker push "${remote}"
remote_repo=${remote%:*}
digest=$(docker image inspect "${remote}" --format '{{range .RepoDigests}}{{println .}}{{end}}' | awk -v prefix="${remote_repo}@sha256:" 'index($0, prefix) == 1 {print; exit}')
[[ -n "${digest}" ]] || { echo "pushed image lacks a digest for ${remote_repo}" >&2; exit 1; }
echo "pushed: ${digest}"
echo "Verify anonymous registry access and pull by this digest before recording publication."
