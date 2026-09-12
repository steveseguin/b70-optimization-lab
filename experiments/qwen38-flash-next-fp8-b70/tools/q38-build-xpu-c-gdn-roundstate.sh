#!/usr/bin/env bash
set -Eeuo pipefail
export CMPLR_ROOT=/opt/intel/oneapi/compiler/2025.3
export PATH=$CMPLR_ROOT/bin:$CMPLR_ROOT/bin/compiler:/home/steve/.venvs/vllm-xpu/bin:$PATH
export LD_LIBRARY_PATH=$CMPLR_ROOT/lib:${LD_LIBRARY_PATH:-}
W=/mnt/usb-models/qwen38-build/src-gdn-roundstate-e421889; B=/mnt/usb-models/qwen38-build/xpu-gdn-roundstate-e421889; D=/mnt/usb-models/qwen38-build/deps-gdn-roundstate
echo "=== configure $(date -u +%FT%TZ)"
cmake -S "$W" -B "$B" -G Ninja -DCMAKE_TOOLCHAIN_FILE=cmake/toolchain.cmake -DCMAKE_BUILD_TYPE=Release \
  -DVLLM_TARGET_DEVICE=xpu -DMOE_KERNELS_ENABLED=OFF -DGDN_KERNELS_ENABLED=ON -DVLLM_XPU_ENABLE_XE_DEFAULT=OFF \
  -DVLLM_PYTHON_EXECUTABLE=/home/steve/.venvs/vllm-xpu/bin/python3 \
  -DTorch_DIR=/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/share/cmake/Torch \
  -DSYCL_LIBRARY=$CMPLR_ROOT/lib/libsycl.so -DSYCL_LIBRARY_DIR=$CMPLR_ROOT/lib \
  -DFETCHCONTENT_BASE_DIR=$D -DFETCHCONTENT_SOURCE_DIR_ONEDNN=$D/onednn-src -DVLLM_CUTLASS_SRC_DIR=$D/cutlass-sycl-src \
  -DFETCHCONTENT_FULLY_DISCONNECTED=ON -DCMAKE_MAKE_PROGRAM=/home/steve/.venvs/vllm-xpu/bin/ninja
grep -E 'onednn|cutlass' "$B/CMakeCache.txt" | grep -E 'SOURCE_DIR|BINARY_DIR' | head -4
echo "=== build _xpu_C $(date -u +%FT%TZ)"
nice -n 19 ninja -C "$B" -j 8 _xpu_C
echo "=== done $(date -u +%FT%TZ)"
ls -la "$B"/_xpu_C.abi3.so "$B"/libgdn_attn_kernels_xe_2.so 2>/dev/null || true
