#!/usr/bin/env bash
# Regenerate a container packet's compose.yaml from its recipe launcher, so the packet cannot drift
# away from the configuration that produced the measured result.
#
# It runs the real launcher (image contract check, model manifest verification and all) behind a
# docker shim that captures the final `docker run` argv instead of starting a container, once per
# card-count profile, then renders both into compose.yaml. Nothing is started and no GPU is touched.
#
# Required env:
#   PACKAGE_DIR   packages/<id>            the packet to write into
#   LAUNCHER      repro/<...>/run-....sh   the recipe launcher, relative to the repo root
#   MODEL_DIR     verified model directory
#   SERVED_NAME   served model name
#   MODEL_DESC    human description of the model directory, for the compose error message
# Optional:
#   IMAGE (local tag), DIGEST_REF (registry digest pin), MTP_DEPTH (default 3),
#   MAX_MODEL_LEN / MAX_NUM_SEQS / MAX_NUM_BATCHED_TOKENS
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
pkg_dir=${PACKAGE_DIR:?set PACKAGE_DIR}; launcher=${LAUNCHER:?set LAUNCHER}
model_dir=${MODEL_DIR:?set MODEL_DIR}; served=${SERVED_NAME:?set SERVED_NAME}
model_desc=${MODEL_DESC:?set MODEL_DESC}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-int4-gdn-spec-group-sync-free-r276}
digest_ref=${DIGEST_REF:-ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:521eb277c0733f8c2ce47aea1bb98ed576c6f1ad63bf5baf22d38fc07abf54ad}
depth=${MTP_DEPTH:-3}

work=$(mktemp -d); trap 'rm -rf "${work}"' EXIT
mkdir -p "${work}/shim"
cat > "${work}/shim/docker" <<'SHIM'
#!/usr/bin/env bash
# Capture only the docker run whose --name is CAPTURE_CONTAINER_NAME; everything else (image
# contract checks, inspect, ps) goes to the real binary untouched.
real=/usr/bin/docker
if [[ "${1:-}" == "run" && -n "${CAPTURE_CONTAINER_NAME:-}" ]]; then
  for a in "$@"; do
    if [[ "$a" == "${CAPTURE_CONTAINER_NAME}" ]]; then
      : >"${DOCKER_ARGV_CAPTURE:?}"; for x in "$@"; do printf '%s\0' "$x" >>"${DOCKER_ARGV_CAPTURE}"; done
      exit 0
    fi
  done
fi
exec "$real" "$@"
SHIM
chmod +x "${work}/shim/docker"

# Intercepted before docker sees it; the value is replaced by ${PORT} in the rendered file. Chosen
# not to collide with a running lane in case the shim is ever bypassed.
render_port=18199
# PROFILES (default "one two"): a packet whose result exists only on two cards (the 27B FP8 lane) renders "two" alone.
for prof in ${PROFILES:-one two}; do
  if [[ "${prof}" == one ]]; then tp=1; mask=0; else tp=2; mask=0,1; fi
  name=$(basename "${pkg_dir}")-render-${prof}
  PATH="${work}/shim:${PATH}" DOCKER_ARGV_CAPTURE="${work}/argv-${prof}.nul" CAPTURE_CONTAINER_NAME="${name}" \
    env MODEL_DIR="${model_dir}" IMAGE="${image}" VLLM_CACHE_DIR="${work}/cache-${prof}" \
        CONTAINER_NAME="${name}" SERVED_MODEL_NAME="${served}" \
        TENSOR_PARALLEL_SIZE="${tp}" XPU_DEVICE_MASK="${mask}" PORT="${render_port}" \
        MTP_DEPTH="${depth}" XPU_GRAPH=1 DRAFT_HEAD_INT4=1 \
        MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}" MAX_NUM_SEQS="${MAX_NUM_SEQS:-16}" \
        MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-1024}" \
        bash "${repo}/${launcher}" >"${work}/render-${prof}.log" 2>&1
  [[ -s "${work}/argv-${prof}.nul" ]] || { echo "capture failed for ${prof}:" >&2; tail -5 "${work}/render-${prof}.log" >&2; exit 1; }
done

one_argv="${work}/argv-one.nul"; two_argv="${work}/argv-two.nul"
[[ -s "${one_argv}" ]] || one_argv=-
[[ -s "${two_argv}" ]] || two_argv=-
python3 "${repo}/tools/render-container-compose.py" \
  "${one_argv}" "${two_argv}" "${repo}/${pkg_dir}/compose.yaml" \
  "${digest_ref}" "${model_desc}" "${launcher}" "${pkg_dir}/scripts/render-compose.sh" "${served}" "${depth}"
