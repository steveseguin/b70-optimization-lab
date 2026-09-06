#!/usr/bin/env bash
# Drop-in stand-in for build/bin/llama-server that runs the pinned record image instead of a host binary.
# The existing record harness (scripts/run-gemma4-26b-llamacpp-replica.sh) execs "$LLAMA_SERVER" with the record
# arguments and a fully-populated environment; this shim forwards the arguments verbatim and only the llama.cpp /
# SYCL / Level Zero variables (never the host's oneAPI PATH/LD_LIBRARY_PATH: the image sources its own setvars.sh),
# mounts the model directories read-only at their host paths so the -m / --spec-draft-model paths stay valid,
# exposes /dev/dri, and runs in the foreground so the harness's kill of this pid stops the container (--init +
# docker's default signal proxying). Point LLAMA_SERVER at <dir>/bin/llama-server where this file is installed as
# bin/llama-server and <dir>/b70-gemma4-record-source.json is the receipt copied out of the image (see
# install-container-build-dir.sh); preflight.sh then validates the receipt exactly as it would for a host build.
set -euo pipefail
image=${GEMMA4_RECORD_IMAGE:-gemma4-26b-q8-record:oneapi-2026.0-b9769}
tool=${LLAMA_TOOL:-llama-server}
name=${GEMMA4_CONTAINER_NAME:-gemma4-record-$$}
mounts=()
for d in ${GEMMA4_MOUNT_DIRS:-/home/steve/llm-models /mnt/fast-ai/llm-models}; do
    [[ -d ${d} ]] && mounts+=(-v "${d}:${d}:ro")
done
env_args=()
while IFS='=' read -r k _; do
    case ${k} in
        GGML_*|LLAMA_*|ONEAPI_DEVICE_SELECTOR|ZE_*|ZES_*|SYCL_*|UR_*|OMP_*|KMP_*|NEOReadDebugKeys|OverrideGpuAddressSpace|IGC_*)
            env_args+=(-e "${k}") ;;
    esac
done < <(env)
cpu_args=()
[[ -n ${CPU_AFFINITY:-} ]] && cpu_args+=(--cpuset-cpus "${CPU_AFFINITY}")
gid_args=()
for g in render video; do
    gid=$(getent group "${g}" | cut -d: -f3 || true)
    [[ -n ${gid} ]] && gid_args+=(--group-add "${gid}")
done
exec docker run --rm --init --name "${name}" --network host --ipc host --device /dev/dri:/dev/dri \
    --ulimit memlock=-1:-1 --shm-size "${GEMMA4_SHM_SIZE:-8g}" --user "$(id -u):$(id -g)" "${gid_args[@]}" "${cpu_args[@]}" \
    "${mounts[@]}" "${env_args[@]}" -e "LLAMA_TOOL=${tool}" "${image}" "$@"
