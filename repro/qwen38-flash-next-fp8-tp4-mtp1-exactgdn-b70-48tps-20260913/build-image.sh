#!/usr/bin/env bash
# Build the (untested) container route from the repository root. The build
# needs network access for the public vLLM clone and the two hosted releases.
set -euo pipefail
repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
tag="${IMAGE_TAG:-neural-download/vllm-openai-xpu:qwen38-flash-next-hctriton-mtp1-6d872457}"
docker build --network=host -f "$repo/repro/qwen38-flash-next-fp8-tp4-mtp1-qsafused-b70-38tps-20260907/Dockerfile" -t "$tag" "$repo"
docker image inspect "$tag" --format '{{.Id}}'
