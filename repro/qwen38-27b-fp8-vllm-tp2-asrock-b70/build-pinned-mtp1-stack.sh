#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new dedicated writable directory}
kernel_image=${KERNEL_IMAGE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-r13}
mtp0_image=${MTP0_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-collective-work-wait-r15}
mtp1_image=${MTP1_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-rms-serial-r31}
serial_attention_image=${SERIAL_ATTENTION_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-attention-r49}
final_image=${FINAL_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-fa-split-gdn-r50}

[[ ! -e "${build_root}" ]] || {
  printf 'refusing existing BUILD_ROOT: %s\n' "${build_root}" >&2
  exit 1
}
mkdir -p "${build_root}"

BUILD_ROOT="${build_root}/kernel" IMAGE="${kernel_image}" \
  "${script_dir}/build-mtp1-kernel-image.sh"

BUILD_ROOT="${build_root}/mtp0" BASE_IMAGE="${kernel_image}" IMAGE="${mtp0_image}" \
  "${script_dir}/build-deterministic-compiled-image.sh"

BUILD_ROOT="${build_root}/mtp1" BASE_IMAGE="${mtp0_image}" IMAGE="${mtp1_image}" \
  "${script_dir}/build-mtp1-rmsnorm-serial-image.sh"

BUILD_ROOT="${build_root}/serial-attention" BASE_IMAGE="${mtp1_image}" \
  IMAGE="${serial_attention_image}" \
  "${script_dir}/build-mtp1-serial-attention-image.sh"

BUILD_ROOT="${build_root}/final-gdn" BASE_IMAGE="${serial_attention_image}" \
  IMAGE="${final_image}" \
  "${script_dir}/build-mtp1-rebuilt-gdn-image.sh"

"${script_dir}/verify-image-contract.sh" mtp0 "${mtp0_image}"
"${script_dir}/verify-image-contract.sh" mtp1 "${mtp1_image}"
"${script_dir}/verify-image-contract.sh" mtp1-serial-fa "${serial_attention_image}"
"${script_dir}/verify-image-contract.sh" mtp1-serial-fa-split-gdn "${final_image}"

printf 'PINNED STACK BUILD COMPLETE\nkernel_image=%s\nmtp0_image=%s\nmtp1_image=%s\nserial_attention_image=%s\nfinal_image=%s\n' \
  "${kernel_image}" "${mtp0_image}" "${mtp1_image}" \
  "${serial_attention_image}" "${final_image}"
