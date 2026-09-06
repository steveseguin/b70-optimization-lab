#!/usr/bin/env bash
# Materialise a host-side "build dir" for the container path so preflight.sh/run.sh work unchanged:
#   <dir>/bin/llama-server             -> the docker shim (LLAMA_SERVER for run.sh)
#   <dir>/bin/llama-quantize           -> the same shim with LLAMA_TOOL=llama-quantize (LLAMA_QUANTIZE for prepare-draft.sh)
#   <dir>/b70-gemma4-record-source.json -> the build receipt copied out of the image (base commit, patch hash, binary digests)
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
image=${GEMMA4_RECORD_IMAGE:-gemma4-26b-q8-record:oneapi-2026.0-b9769}
dir=${1:?usage: install-container-build-dir.sh <new-dir>}
[[ ! -e ${dir} ]] || { printf 'Refusing to overwrite existing path: %s\n' "${dir}" >&2; exit 2; }
mkdir -p "${dir}/bin"
cp "${here}/llama-server-docker-shim.sh" "${dir}/bin/llama-server"
printf '#!/usr/bin/env bash\nexport LLAMA_TOOL=llama-quantize\nexec "%s/bin/llama-server" "$@"\n' "${dir}" > "${dir}/bin/llama-quantize"
chmod +x "${dir}/bin/llama-server" "${dir}/bin/llama-quantize"
cid=$(docker create "${image}")
trap 'docker rm -f "${cid}" >/dev/null' EXIT
docker cp "${cid}:/src/llama.cpp/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/b70-gemma4-record-source.json" "${dir}/b70-gemma4-record-source.json"
docker image inspect "${image}" --format '{{.Id}}' > "${dir}/image-id.txt"
printf 'GEMMA4_RECORD_IMAGE=%s\nLLAMA_SERVER=%s/bin/llama-server\nLLAMA_QUANTIZE=%s/bin/llama-quantize\n' "${image}" "${dir}" "${dir}"
cat "${dir}/b70-gemma4-record-source.json"
