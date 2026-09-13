#!/usr/bin/env bash
set -euo pipefail

# Experiments on images that are not yet under contract (e.g. the 2026-09-12 v0.29.0 rebase candidates) may set
# SKIP_IMAGE_CONTRACT=1. The launcher then runs with NO file/kernel identity guarantee; never for published results.
if [[ "${SKIP_IMAGE_CONTRACT:-0}" == 1 ]]; then printf 'IMAGE CONTRACT SKIPPED (SKIP_IMAGE_CONTRACT=1): %s is NOT a qualified image\n' "${2:-?}" >&2; exit 0; fi
profile=${1:?usage: verify-image-contract.sh mtp0|mtp1|mtp1-serial-gdn|mtp1-serial-fp8|mtp1-serial-fa|mtp1-serial-fa-split-gdn IMAGE}
image=${2:?usage: verify-image-contract.sh mtp0|mtp1|mtp1-serial-gdn|mtp1-serial-fp8|mtp1-serial-fa|mtp1-serial-fa-split-gdn IMAGE}

fail() {
  printf 'IMAGE CONTRACT FAIL: %s\n' "$*" >&2
  exit 1
}

command -v docker >/dev/null || fail 'docker is required'
docker image inspect "${image}" >/dev/null 2>&1 || fail "image is not local: ${image}"

actual_kernel_head=$(docker image inspect "${image}" --format '{{ index .Config.Labels "neural.download.kernel.head" }}')
if [[ "${actual_kernel_head}" == 6d92b1bfbf32767ecda8e819613eb151e70030ad ]]; then
  # R303 (2026-09-13): the runtime rebased onto stock vLLM XPU v0.29.0 (kernels 0.1.14.1 = this head) with the lab's
  # ten ported Python files, rebuilt _xpu_C/GDN libraries, the #53059 alias guard and the #51565 GDN first-chunk fix.
  # One closed digest set covers every profile: the seventeen files below are the complete surface the lineage's overlays touch, so a candidate that changes
  # any of them is a different image. Digests: experiments/qwen38-27b-b70/docker/rebase-v0290/r303-contract-digests.sha256.
  v0290_paths=(
    /opt/venv/lib/python3.12/site-packages/vllm/model_executor/kernels/linear/scaled_mm/xpu.py
    /opt/venv/lib/python3.12/site-packages/vllm/_xpu_ops.py
    /opt/venv/lib/python3.12/site-packages/vllm/config/compilation.py
    /opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/mamba/gdn/qwen_gdn_linear_attn.py
    /opt/venv/lib/python3.12/site-packages/vllm/distributed/device_communicators/xpu_communicator.py
    /opt/venv/lib/python3.12/site-packages/vllm_xpu_kernels/_xpu_C.abi3.so
    /opt/venv/lib/python3.12/site-packages/vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so
    /opt/venv/lib/python3.12/site-packages/vllm/ir/ops/layernorm.py
    /opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/logits_processor.py
    /opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/layernorm.py
    /opt/venv/lib/python3.12/site-packages/vllm/v1/attention/backends/flash_attn.py
    /opt/venv/lib/python3.12/site-packages/vllm/v1/worker/gpu_model_runner.py
    /opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/utils.py
    /opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/vocab_parallel_embedding.py
    /opt/venv/lib/python3.12/site-packages/vllm/v1/spec_decode/llm_base_proposer.py
    /opt/venv/lib/python3.12/site-packages/vllm/model_executor/kernels/linear/mixed_precision/xpu.py
    /opt/venv/lib/python3.12/site-packages/vllm/v1/attention/backends/gdn_attn.py
  )
  v0290_expected=(
    7c36e4a8dab4bfc06b1d5be2d8466e8cdc94099dd5409424fecc6dd8ffc2c208
    6ee6b8db18759873246aca28e85ca6d2ba177eb08bfd3b9b0f0feea168cee9b3
    3a79ea08d48d44879ac8cbfee1c7d88f9bd72927d9bd12eee31743e8da8a4d7e
    7ef91a9e03424571155e7a09d8a506bafdd7ea4e08c292b049ab7317b42996e0
    5ab2ea5d9e049e6b53e2d56d1e3419ce01d1988e8be5295bab1f912a7fdbf74d
    bbce7295fb8a58bad456675cfac7cdf3d1e29fe7a9dd5c0970741b130616c932
    6f0fec189b04bd6a94b1b3ca0983623be7e7f2a4734b58e086fab3b0341213f3
    65d33dcb96404ddde273acf84ef901151a8155a2cffc144bdd0c49fe1d576a22
    6b0603d67b0c756253c2fdc882a3896d2e873a16e9aa2ef877aabca8d36bdb5f
    3f949e537ccc52744d7eba52ed2034b20ee3fbaeaabbfab4e672f1dc9767602c
    e0ae4ae14ffdc0c7db1c480978f94b56f74778665a9c454bab32a89371e342e7
    26c69c2e1d41a5708020b2fc4047b40237eaa13f4828431bd7a10e529ea13776
    34ef265d5a05425bd217b718229428e7b124788fb4586d367bd8053d50a80168
    1e72ed72ed7f495f9b4b5d28f7a0c97b5397e853dabc83acf2ab5ab112e9ffd9
    2d9007211cc62bff8dfde27e58714d95c5225be37905991ba34859390b6c8e96
    7cc7ca2fef07a0747a0892a2e774eebd03c5796948499272309d6260321cb751
    ec3ee059e3952264d4889159200e787c8c8ae2d3f21f679557d022c0ac007145
  )
  mapfile -t v0290_observed < <(docker run --rm --entrypoint sha256sum "${image}" "${v0290_paths[@]}" | awk '{print $1}')
  [[ "${#v0290_observed[@]}" == "${#v0290_expected[@]}" ]] || fail 'image hash inventory is incomplete (v0290 set)'
  for index in "${!v0290_expected[@]}"; do
    [[ "${v0290_observed[index]}" == "${v0290_expected[index]}" ]] || \
      fail "content mismatch for ${v0290_paths[index]}: expected ${v0290_expected[index]}, found ${v0290_observed[index]}"
  done
  printf 'IMAGE CONTRACT PASS: profile=%s(v0290) image=%s files=%s kernel=%s\n' "${profile}" "${image}" "${#v0290_expected[@]}" "${actual_kernel_head}"
  exit 0
fi
expected_kernel_head=1e90ffa672ba02f17a909da11838a4c55b199783
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
  /opt/venv/lib/python3.12/site-packages/vllm/ir/ops/layernorm.py
  /opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/logits_processor.py
)
expected=(
  7c36e4a8dab4bfc06b1d5be2d8466e8cdc94099dd5409424fecc6dd8ffc2c208
  f3273ccfb41be44c3c02080c26df10e8b200060366b900d940803f4221224c59
  6e57a553093753856baaf7987e37ff24a15b73c95730e397e74d22c539d440ec
  7afb4de8b87d7f180d696f7cadad8b9d48d9ab7b706ae19616425c4f9456fb19
  5ab2ea5d9e049e6b53e2d56d1e3419ce01d1988e8be5295bab1f912a7fdbf74d
  ba911f7e7d0bae668f0039a3e443e1768c2010d239d2970d281a7dd01fcb5289
  05488952d1d98ca68915cabd7e7fe4ce62632662b175c560ae49bb2444187c79
  65d33dcb96404ddde273acf84ef901151a8155a2cffc144bdd0c49fe1d576a22
  46c9e079b5428e8d6a0140042c827206ce4b50050b515ebe8cf8f65c6e96da89
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
# vllm/ir/ops/layernorm.py holds the RMSNorm arithmetic itself; layers/layernorm.py only dispatches to
# it, so pinning the wrapper alone left the model's normalisation unverified. Appended to the arrays
# above rather than inserted: indices 4, 5 and 6 are referenced literally further down this script.
expected_ir_layernorm_sha256=${EXPECTED_IR_LAYERNORM_SHA256:-}
# The logits processor computes the vocabulary projection, the last matmul before the argmax, and was
# likewise unpinned. Candidates that replace it opt in with its exact digest.
expected_logits_processor_sha256=${EXPECTED_LOGITS_PROCESSOR_SHA256:-}

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
if [[ -n "${expected_logits_processor_sha256}" ]]; then
  for index in "${!paths[@]}"; do
    [[ "${paths[index]}" == */vllm/model_executor/layers/logits_processor.py ]] && expected[index]=${expected_logits_processor_sha256}
  done
fi
if [[ -n "${expected_ir_layernorm_sha256}" ]]; then
  for index in "${!paths[@]}"; do
    [[ "${paths[index]}" == */vllm/ir/ops/layernorm.py ]] && expected[index]=${expected_ir_layernorm_sha256}
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
