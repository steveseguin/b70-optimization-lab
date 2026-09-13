#!/usr/bin/env bash
# CPU-only reconstruction of the R307 Python overlay from its immutable public parent.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base=ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2
tag=${REBUILD_TAG:-rebase/r307-repro-20260913}
out=${OUT_DIR:?set OUT_DIR to a new build evidence directory}
mkdir -p "${out}"
# Explicitly require the public parent locally; fetch it separately if needed.
docker image inspect "${base}" --format '{{.Id}} {{json .RepoDigests}}' | tee "${out}/parent.txt"
context=$(mktemp -d)
trap 'rm -rf "${context}"' EXIT
for file in Dockerfile.r307-gdn-state-handoff r306-gdn-active-width-contiguous-staging.py r307-gdn-state-handoff.py; do
  cp "${script_dir}/${file}" "${context}/${file}"
done
sha256sum "${context}"/* > "${out}/build-inputs.sha256"
docker build --pull=false --no-cache --build-arg BASE="${base}" -t "${tag}" -f "${context}/Dockerfile.r307-gdn-state-handoff" "${context}" 2>&1 | tee "${out}/build.log"
mapfile -t paths < <(awk '{print $2}' "${script_dir}/r307-contract-digests.sha256")
docker run --rm -w / --entrypoint sha256sum "${tag}" "${paths[@]}" > "${out}/observed.sha256"
diff -u "${script_dir}/r307-contract-digests.sha256" "${out}/observed.sha256"
docker image inspect "${tag}" --format '{{.Id}} {{json .Config.Labels}}' > "${out}/image.txt"
echo "PASS: all ${#paths[@]} R307 runtime files match; evidence: ${out}"
