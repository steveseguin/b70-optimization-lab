#!/usr/bin/env bash
set -euo pipefail

profile=${1:?usage: verify-image-contract.sh mtp0|mtp1|mtp1-serial-gdn|mtp1-serial-fp8|mtp1-serial-fa|mtp1-serial-fa-split-gdn IMAGE}
image=${2:?usage: verify-image-contract.sh mtp0|mtp1|mtp1-serial-gdn|mtp1-serial-fp8|mtp1-serial-fa|mtp1-serial-fa-split-gdn IMAGE}

fail() {
  printf 'IMAGE CONTRACT FAIL: %s\n' "$*" >&2
  exit 1
}

command -v docker >/dev/null || fail 'docker is required'
docker image inspect "${image}" >/dev/null 2>&1 || fail "image is not local: ${image}"

expected_kernel_head=1e90ffa672ba02f17a909da11838a4c55b199783
actual_kernel_head=$(docker image inspect "${image}" --format '{{ index .Config.Labels "neural.download.kernel.head" }}')
[[ "${actual_kernel_head}" == "${expected_kernel_head}" ]] || \
  fail "kernel head mismatch: expected ${expected_kernel_head}, found ${actual_kernel_head:-unset}"

paths=(
  /opt/venv/lib/python3.12/site-packages/vllm/model_executor/kernels/linear/scaled_mm/xpu.py
  /opt/venv/lib/python3.12/site-packages/vllm/_xpu_ops.py
  /opt/venv/lib/python3.12/site-packages/vllm/config/compilation.py
  /opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/mamba/gdn/qwen_gdn_linear_attn.py
  /opt/venv/lib/python3.12/site-packages/vllm/distributed/device_communicators/xpu_communicator.py
  /opt/venv/lib/python3.12/site-packages/vllm_xpu_kernels/_xpu_C.abi3.so
  /opt/venv/lib/python3.12/site-packages/vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so
)
expected=(
  7c36e4a8dab4bfc06b1d5be2d8466e8cdc94099dd5409424fecc6dd8ffc2c208
  f3273ccfb41be44c3c02080c26df10e8b200060366b900d940803f4221224c59
  6e57a553093753856baaf7987e37ff24a15b73c95730e397e74d22c539d440ec
  7afb4de8b87d7f180d696f7cadad8b9d48d9ab7b706ae19616425c4f9456fb19
  5ab2ea5d9e049e6b53e2d56d1e3419ce01d1988e8be5295bab1f912a7fdbf74d
  ba911f7e7d0bae668f0039a3e443e1768c2010d239d2970d281a7dd01fcb5289
  05488952d1d98ca68915cabd7e7fe4ce62632662b175c560ae49bb2444187c79
)

# A source-qualified oneDNN selector rebuild intentionally changes the
# monolithic extension while leaving the separately loaded GDN/MHC device
# libraries untouched.  Candidates must opt into that contract with exact
# digests; the ordinary profile remains closed over its frozen extension.
expected_xpu_extension_sha256=${EXPECTED_XPU_EXTENSION_SHA256:-}
expected_mhc_library_sha256=${EXPECTED_MHC_LIBRARY_SHA256:-}
# R152 candidates replace the Gemma/RMSNorm module; they must opt in with its exact digest.
expected_layernorm_sha256=${EXPECTED_LAYERNORM_SHA256:-}
# R156 candidates replace the XPU op wrapper module; opt in with its exact digest.
expected_xpu_ops_sha256=${EXPECTED_XPU_OPS_SHA256:-}
# R207 candidates replace the XPU communicator module; opt in with its exact digest.
expected_xpu_communicator_sha256=${EXPECTED_XPU_COMMUNICATOR_SHA256:-}
# R220/R221 candidates replace the vllm-xpu-kernels extension (_xpu_C.abi3.so, rebuilt with the W4A16 fixed-K
# oneDNN patch); opt in with its exact digest.
expected_xpu_c_sha256=${EXPECTED_XPU_C_SHA256:-}

# Experimental overlays may intentionally replace only the XPU communicator.
# Keep the ordinary package hash immutable and require candidates to provide
# their exact replacement digest explicitly.
if [[ -n "${EXPECTED_XPU_COMMUNICATOR_SHA256:-}" ]]; then
  expected[4]=${EXPECTED_XPU_COMMUNICATOR_SHA256}
fi

case "${profile}" in
  mtp0) ;;
  mtp1)
    paths+=(/opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/layernorm.py)
    expected+=(50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8)
    ;;
  mtp1-serial-gdn)
    paths+=(/opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/layernorm.py)
    expected+=(50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8)
    expected[5]=a190f22ccd9b2b6e638d7e0bc57e8a67946064219768d697a134786e8f6ee12d
    expected[6]=2c343620d689409bfa371a8b4c3db680e4786f23bc092411e7d03140f1b2a355
    ;;
  mtp1-serial-fp8)
    paths+=(
      /opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/layernorm.py
      /opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/quantization/fp8.py
    )
    expected+=(
      50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8
      6af089e6a9e805add109420cddbe04da356ec95c44b605f7fefee6205e83b6fc
    )
    ;;
  mtp1-serial-fa)
    paths+=(
      /opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/layernorm.py
      /opt/venv/lib/python3.12/site-packages/vllm/v1/attention/backends/flash_attn.py
    )
    expected+=(
      50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8
      c90006b0e4e59eab26fce7c1636b99507b8eabf3acf2d88d62b6e569939975d1
    )
    ;;
  mtp1-serial-fa-split-gdn)
    # The lab image and clean rebuild have identical code/data sections. Their
    # whole-file digests differ only in .dynstr: the clean build uses the
    # portable $ORIGIN runpath, while the lab image retained linker padding and
    # a host-specific oneAPI/Torch path. Require one complete known pair.
    expected[5]=f8013aff50f815b290cbec87d7926936c3fae9daacad6e1cf1f4c01ca60180ef
    expected[6]=32a13caab7d56e6b584b7396ff61b3755a60362e6647db26337b98fdbd0bb4ec
    paths+=(
      /opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/layernorm.py
      /opt/venv/lib/python3.12/site-packages/vllm/v1/attention/backends/flash_attn.py
    )
    expected+=(
      50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8
      c90006b0e4e59eab26fce7c1636b99507b8eabf3acf2d88d62b6e569939975d1
    )
    ;;
  *) fail "unsupported profile: ${profile}" ;;
esac

if [[ -n "${expected_xpu_extension_sha256}" ]]; then
  expected[5]=${expected_xpu_extension_sha256}
fi
if [[ -n "${expected_xpu_ops_sha256}" ]]; then
  for index in "${!paths[@]}"; do
    [[ "${paths[index]}" == */vllm/_xpu_ops.py ]] && expected[index]=${expected_xpu_ops_sha256}
  done
fi
if [[ -n "${expected_xpu_communicator_sha256}" ]]; then
  for index in "${!paths[@]}"; do
    [[ "${paths[index]}" == */device_communicators/xpu_communicator.py ]] && expected[index]=${expected_xpu_communicator_sha256}
  done
fi
if [[ -n "${expected_xpu_c_sha256}" ]]; then
  for index in "${!paths[@]}"; do
    [[ "${paths[index]}" == */vllm_xpu_kernels/_xpu_C.abi3.so ]] && expected[index]=${expected_xpu_c_sha256}
  done
fi
if [[ -n "${expected_layernorm_sha256}" ]]; then
  for index in "${!paths[@]}"; do
    [[ "${paths[index]}" == */vllm/model_executor/layers/layernorm.py ]] && expected[index]=${expected_layernorm_sha256}
  done
fi
if [[ -n "${expected_mhc_library_sha256}" ]]; then
  paths+=(/opt/venv/lib/python3.12/site-packages/vllm_xpu_kernels/libmhc_kernels_xe_2.so)
  expected+=("${expected_mhc_library_sha256}")
fi

mapfile -t observed < <(
  docker run --rm --entrypoint sha256sum "${image}" "${paths[@]}" |
    awk '{print $1}'
)
[[ "${#observed[@]}" == "${#expected[@]}" ]] || fail 'image hash inventory is incomplete'
if [[ "${profile}" == mtp1-serial-fa-split-gdn ]]; then
  if [[ -n "${expected_xpu_extension_sha256}" ]]; then
    case "${observed[6]}" in
      32a13caab7d56e6b584b7396ff61b3755a60362e6647db26337b98fdbd0bb4ec|2c343620d689409bfa371a8b4c3db680e4786f23bc092411e7d03140f1b2a355)
        expected[6]=${observed[6]}
        ;;
      *) fail 'fixed-extension candidate does not preserve a validated GDN device library' ;;
    esac
  else
    case "${observed[5]}:${observed[6]}" in
      f8013aff50f815b290cbec87d7926936c3fae9daacad6e1cf1f4c01ca60180ef:32a13caab7d56e6b584b7396ff61b3755a60362e6647db26337b98fdbd0bb4ec) ;;
      1632cafcf2afc0bc039dd49ebbb5eda4e62d626f4c20729aecd9e87874d1dc08:2c343620d689409bfa371a8b4c3db680e4786f23bc092411e7d03140f1b2a355)
        expected[5]=${observed[5]}
        expected[6]=${observed[6]}
        ;;
      *) fail 'final GDN libraries do not match either validated full-file pair' ;;
    esac
  fi
fi
for index in "${!expected[@]}"; do
  [[ "${observed[index]}" == "${expected[index]}" ]] || \
    fail "content mismatch for ${paths[index]}: expected ${expected[index]}, found ${observed[index]}"
done

printf 'IMAGE CONTRACT PASS: profile=%s image=%s files=%s kernel=%s\n' \
  "${profile}" "${image}" "${#expected[@]}" "${expected_kernel_head}"
