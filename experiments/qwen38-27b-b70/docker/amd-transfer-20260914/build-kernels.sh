#!/usr/bin/env bash
# AMD transfer latest-base candidate, 2026-09-14. Rebuilds accepted kernel overlay from public sources:
#   vllm-xpu-kernels 6d92b1bfbf32767ecda8e819613eb151e70030ad (tag 0.1.14.1) unpatched,
#   oneDNN 0e2a5bfeef1bfbffc3137464606540233086ce9b (the tag's own pin) + patches r137a, r137b, r221 (r221 supersedes r220),
#   sycl-tla cd763790ad2f74d7294435ecf77682bac0062c3a,
# built by scripts/build-vllm-xpu-kernels-xpu-c-only.sh inside the public v0.29.0 image's venv with host oneAPI 2026.1
# (libsycl.so.9 matches the image's torch 2.13.0+xpu). ~13 min at JOBS=10 on the lab host. AOT bmg-g21-a0; MoE kernels off
# (as every lab kernel image since R139). Set MIRRORS to local bare mirrors to avoid the WAN (git url.insteadOf).
set -euo pipefail
lab=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty directory}
[[ ! -e "${build_root}" ]] || { echo "BUILD_ROOT exists: ${build_root}" >&2; exit 1; }
base=${BASE_IMAGE:-vllm/vllm-openai-xpu@sha256:28915aadfe9665dd70f1cf36e6f7362e25df24e9035785dedd00559652bbef41}
if [[ -n "${MIRRORS:-}" ]]; then
  export GIT_CONFIG_COUNT=3
  export GIT_CONFIG_KEY_0=url.file://${MIRRORS}/vllm-xpu-kernels.git.insteadOf GIT_CONFIG_VALUE_0=https://github.com/vllm-project/vllm-xpu-kernels.git
  export GIT_CONFIG_KEY_1=url.file://${MIRRORS}/onednn.git.insteadOf GIT_CONFIG_VALUE_1=https://github.com/uxlfoundation/oneDNN.git
  export GIT_CONFIG_KEY_2=url.file://${MIRRORS}/sycl-tla.git.insteadOf GIT_CONFIG_VALUE_2=https://github.com/intel/sycl-tla.git
fi
P=${lab}/experiments/qwen38-27b-b70/patches
mkdir -p "${build_root}/compile"
git clone --no-checkout https://github.com/vllm-project/vllm-xpu-kernels.git "${build_root}/vllm-xpu-kernels"
git -C "${build_root}/vllm-xpu-kernels" checkout --detach 6d92b1bfbf32767ecda8e819613eb151e70030ad
git clone --no-checkout https://github.com/uxlfoundation/oneDNN.git "${build_root}/onednn"
git -C "${build_root}/onednn" checkout --detach 0e2a5bfeef1bfbffc3137464606540233086ce9b
for p in onednn-qwen38-w8a16-fixed-k-align16-r137a-20260902.patch onednn-qwen38-w8a16-c-default-align-r137b-20260902.patch onednn-qwen38-w4a16-fixed-k-two-tier-r221-20260905.patch; do
  git -C "${build_root}/onednn" apply "${P}/${p}"
done
git -C "${build_root}/onednn" diff --check
git clone --no-checkout https://github.com/intel/sycl-tla.git "${build_root}/sycl-tla"
git -C "${build_root}/sycl-tla" checkout --detach cd763790ad2f74d7294435ecf77682bac0062c3a
t0=$(date +%s)
docker run --rm --network none --memory "${BUILD_MEMORY:-14g}" --memory-swap "${BUILD_MEMORY_SWAP:-14g}" --entrypoint /bin/bash \
  --volume /opt/intel/oneapi:/opt/intel/oneapi:ro --volume "${build_root}/vllm-xpu-kernels:/src:ro" --volume "${build_root}/compile:/run" \
  --volume "${build_root}/onednn:/deps/onednn:ro" --volume "${build_root}/sycl-tla:/deps/cutlass:ro" --volume "${lab}:/lab:ro" \
  --env KERNELS_DIR=/src --env VENV_DIR=/opt/venv --env ONEAPI_VARS=/opt/intel/oneapi/compiler/2026.1/env/vars.sh \
  --env BUILD_DIR=/run/build --env INSTALL_PREFIX=/run/install --env FETCHCONTENT_DIR=/run/fetchcontent \
  --env ONEDNN_SOURCE=/deps/onednn --env CUTLASS_SOURCE=/deps/cutlass --env AOT_DEVICES=bmg-g21-a0 --env JOBS="${JOBS:-10}" \
  --env GDN_KERNELS=ON --env MOE_KERNELS=OFF "${base}" /lab/scripts/build-vllm-xpu-kernels-xpu-c-only.sh
echo "kernel build took $(( $(date +%s) - t0 )) s"
out=${build_root}/compile/install/vllm_xpu_kernels
readelf -d "${out}/_xpu_C.abi3.so" | grep -Fq 'Library runpath: [$ORIGIN]' || { echo "non-portable RUNPATH on _xpu_C" >&2; exit 1; }
sha256sum "${out}/_xpu_C.abi3.so" "${out}/libgdn_attn_kernels_xe_2.so"
echo "New-base candidate artifacts: do not require historical binary hashes; record and qualify this build."
