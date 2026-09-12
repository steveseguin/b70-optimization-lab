#!/usr/bin/env bash
# Assemble the A359 kernel stage: served stage + rebuilt _xpu_C.abi3.so, new loadable manifest.
set -Eeuo pipefail
B=/mnt/usb-models/qwen38-build/xpu-gdn-roundstate-e421889
OLD=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70
NEW=/mnt/usb-models/qwen38-build/runtime-gdn-roundstate-${1:?sha7}-b70
REPO=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70
[[ -f $B/_xpu_C.abi3.so ]] || { echo "no built _xpu_C"; exit 1; }
diff <(readelf -d $OLD/vllm_xpu_kernels/_xpu_C.abi3.so | grep NEEDED | awk '{print $NF}') \
     <(readelf -d $B/_xpu_C.abi3.so | grep NEEDED | awk '{print $NF}') && echo "NEEDED sets identical"
strings $B/_xpu_C.abi3.so | grep -c 'VLLM_XPU_GDN_SPEC_ROUND_STATE'
[[ ! -e $NEW ]] || { echo "stage exists: $NEW"; exit 1; }
mkdir -p $NEW && cp -a $OLD/vllm_xpu_kernels $NEW/ && cp $B/_xpu_C.abi3.so $NEW/vllm_xpu_kernels/_xpu_C.abi3.so
(cd $NEW/vllm_xpu_kernels && find . -type f \( -name '*.py' -o -name '*.so' \) | wc -l)
(cd $NEW/vllm_xpu_kernels && sha256sum $(sed -E 's/^[0-9a-f]{64}  //' $REPO/data/runtime-stage-padding-guard-loadable.sha256)) > $REPO/data/runtime-stage-gdn-roundstate-${2:?manifest-tag}-loadable.sha256
wc -l $REPO/data/runtime-stage-gdn-roundstate-${2:?manifest-tag}-loadable.sha256
diff <(sort -k2 $REPO/data/runtime-stage-padding-guard-loadable.sha256) <(sort -k2 $REPO/data/runtime-stage-gdn-roundstate-${2:?manifest-tag}-loadable.sha256) || true
(cd $NEW/vllm_xpu_kernels && sha256sum -c --quiet $REPO/data/runtime-stage-gdn-roundstate-${2:?manifest-tag}-loadable.sha256) && echo "manifest verifies"
