#!/usr/bin/env bash
# Build the (untested) container route from the repository root. The build
# needs network access for the public vLLM clone and the two hosted releases.
set -euo pipefail
repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
tag="${IMAGE_TAG:-neural-download/vllm-openai-xpu:qwen38-flash-next-placement-mtp1-005dc578}"
docker build --network=host -f "$repo/repro/qwen38-flash-next-fp8-tp4-mtp1-placement-b70-32tps-20260906/Dockerfile" -t "$tag" "$repo"
docker image inspect "$tag" --format '{{.Id}}'
