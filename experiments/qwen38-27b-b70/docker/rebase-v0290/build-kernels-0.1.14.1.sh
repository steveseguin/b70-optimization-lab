#!/usr/bin/env bash
# Stage B kernel build (2026-09-12): vllm-xpu-kernels 0.1.14.1 (6d92b1bf, includes #544) + oneDNN 0e2a5bfe with the lab's
# r137a + r137b + r221 GEMM patches (r221 supersedes r220) (no r35/r50: the served config keeps every serial-exact gate at 0 and the width
# contract is now handled on the vLLM side by PR #53542), built inside the stock v0.29.0 image's venv with host oneAPI 2026.1.
set -uo pipefail
B=/home/steve/builds/rebase-v0290-kernels-20260912; lab=/home/steve/b70-optimization-lab
t0=$(date +%s)
docker run --rm --network none --memory 14g --memory-swap 28g --entrypoint /bin/bash \
  --volume /opt/intel/oneapi:/opt/intel/oneapi:ro --volume $B/vllm-xpu-kernels:/src:ro --volume $B/compile:/run \
  --volume $B/onednn:/deps/onednn:ro --volume $B/sycl-tla:/deps/cutlass:ro --volume $lab:/lab:ro \
  --env KERNELS_DIR=/src --env VENV_DIR=/opt/venv --env ONEAPI_VARS=/opt/intel/oneapi/compiler/2026.1/env/vars.sh \
  --env BUILD_DIR=/run/build --env INSTALL_PREFIX=/run/install --env FETCHCONTENT_DIR=/run/fetchcontent \
  --env ONEDNN_SOURCE=/deps/onednn --env CUTLASS_SOURCE=/deps/cutlass --env AOT_DEVICES=bmg-g21-a0 --env JOBS=10 \
  --env GDN_KERNELS=ON --env MOE_KERNELS=OFF vllm/vllm-openai-xpu:latest /lab/scripts/build-vllm-xpu-kernels-xpu-c-only.sh
rc=$?; echo "build rc=$rc in $(( $(date +%s)-t0 )) s"; ls -la $B/compile/install/vllm_xpu_kernels/ 2>/dev/null | head; echo BUILD-DONE-$rc
