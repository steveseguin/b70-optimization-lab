#!/usr/bin/env bash
# Download devan-carlin/Qwen3.8-27B-int4-AutoRound at the pinned revision (manifest model.json), then build the plain-GPTQ
# relabel the recipe serves (R212: identical tensors hard-linked, config relabelled so vLLM routes to the oneDNN W4A16
# kernel). usage: download-model.sh SOURCE_DIR RELABEL_DIR   (RELABEL_DIR is what MODEL_DIR points at)
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); repo=$(cd -- "${here}/../../.." && pwd)
src=${1:?usage: download-model.sh SOURCE_DIR RELABEL_DIR}; dst=${2:?usage: download-model.sh SOURCE_DIR RELABEL_DIR}
MODEL_DIR="${src}" MODEL_MANIFEST=${repo}/repro/qwen38-27b-autoround-int4-b70/manifests/model.json "${repo}/tools/container-packet/download-model.sh"
python3 "${repo}/repro/qwen38-27b-autoround-int4-b70/scripts/make-gptq-relabel.py" "${src}" "${dst}" --manifest "${repo}/repro/qwen38-27b-autoround-int4-b70/manifests/model-gptq-relabel-r212.json"
echo "serve with MODEL_DIR=${dst}"
