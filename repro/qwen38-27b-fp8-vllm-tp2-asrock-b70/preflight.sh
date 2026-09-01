#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
image="${IMAGE:-vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f}"
image_contract_profile="${IMAGE_CONTRACT_PROFILE:-}"
model_dir="${MODEL_DIR:?set MODEL_DIR to the downloaded Qwen3.8-27B-FP8 directory}"

fail() {
    printf 'PREFLIGHT FAIL: %s\n' "$*" >&2
    exit 1
}

[[ "$(uname -m)" == "x86_64" ]] || fail "this reproduction was tested only on x86_64"
[[ -r /etc/os-release ]] || fail "cannot identify the host OS"
# shellcheck disable=SC1091
source /etc/os-release
[[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "24.04" ]] || \
    fail "tested host is Ubuntu 24.04; found ${PRETTY_NAME:-unknown}"

command -v docker >/dev/null || fail "Docker is not installed"
docker info >/dev/null 2>&1 || fail "Docker daemon is unavailable to this user"
groups=" $(id -nG) "
[[ "${groups}" == *" docker "* ]] || fail "current user is not in the docker group"
[[ "${groups}" == *" render "* ]] || fail "current user is not in the render group"

mapfile -t render_nodes < <(find /dev/dri -maxdepth 1 -type c -name 'renderD*' 2>/dev/null | LC_ALL=C sort)
(( ${#render_nodes[@]} >= 2 )) || fail "two DRM render devices are required"
for node in "${render_nodes[@]:0:2}"; do
    [[ -r "${node}" && -w "${node}" ]] || fail "render device is not readable/writable: ${node}"
    device_dir="/sys/class/drm/$(basename -- "${node}")/device"
    [[ -r "${device_dir}/vendor" && -r "${device_dir}/device" ]] || \
        fail "cannot identify PCI device behind ${node}"
    vendor=$(<"${device_dir}/vendor")
    device=$(<"${device_dir}/device")
    [[ "${vendor}" == "0x8086" && "${device}" == "0xe223" ]] || \
        fail "${node} is not an Intel Arc Pro B70 (found ${vendor}:${device})"
done

mem_total_kib=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
swap_total_kib=$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)
(( mem_total_kib >= 15 * 1024 * 1024 )) || fail "at least 15 GiB host RAM is required"
(( mem_total_kib + swap_total_kib >= 20 * 1024 * 1024 )) || \
    fail "at least 20 GiB combined RAM and swap is required"

[[ -d "${model_dir}" ]] || fail "model directory does not exist: ${model_dir}"
docker image inspect "${image}" >/dev/null 2>&1 || \
    fail "pinned image is not local; run: docker pull ${image}"
if [[ -n "${image_contract_profile}" ]]; then
    "${script_dir}/verify-image-contract.sh" "${image_contract_profile}" "${image}"
fi

printf 'host_os=%s\nkernel=%s\ndocker=%s\nrender_devices=%s\ngpu_pci_id=8086:e223\nimage=%s\n' \
    "${PRETTY_NAME}" "$(uname -r)" "$(docker version --format '{{.Server.Version}}')" \
    "${render_nodes[*]}" "${image}"
dpkg-query -W -f='package=${binary:Package} version=${Version}\n' \
    intel-opencl-icd libze1 2>/dev/null || \
    fail "required Intel compute packages are not installed"

"${script_dir}/verify-model-direct.sh" "${model_dir}"
printf 'PREFLIGHT PASS: host prerequisites and direct/ordinary model identities match\n'
