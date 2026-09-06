# Container route for the lossless MTP1 line. UNTESTED: this image has not
# been built or replayed yet (see CONTAINER-STATUS.md). It pins the same
# identities the native gate verifies: vLLM overlay 1b2a17c1 over public
# 76cfe1cd (from the in-repository bundle), the hosted 2f829747 kernel stage,
# and the hosted public oneCCL 4ceafd1 build. The base image is the same
# vllm-openai-xpu digest the lab's Qwen3.8 27B FP8 images use; its torch/triton
# versions are checked at build time against the record (2.11.0+xpu, 3.7.0).
ARG BASE_IMAGE=vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f
FROM ${BASE_IMAGE}
ARG STAGE_RELEASE=https://github.com/steveseguin/b70-optimization-lab/releases/download/qwen38-flash-next-runtime-2f829747-20260827
ARG ONECCL_RELEASE=https://github.com/steveseguin/b70-optimization-lab/releases/download/qwen38-flash-next-oneccl-4ceafd1-b70-public-20260906
USER root
RUN apt-get update && apt-get install -y --no-install-recommends git zstd curl ca-certificates && rm -rf /var/lib/apt/lists/*
# 1. vLLM overlay source from the bundle (tag q38-lossless-mtp1-1b2a17c1).
COPY patches/qwen38-flash-next-fp8-b70/vllm-lossless-mtp1-1b2a17c1/vllm-q38-lossless-mtp1-1b2a17c1-20260906.bundle /tmp/overlay.bundle
RUN git clone --quiet --filter=blob:none https://github.com/vllm-project/vllm.git /opt/vllm-src \
 && git -C /opt/vllm-src fetch --quiet /tmp/overlay.bundle refs/tags/q38-lossless-mtp1-1b2a17c1:refs/tags/q38-lossless-mtp1-1b2a17c1 \
 && git -C /opt/vllm-src checkout --quiet q38-lossless-mtp1-1b2a17c1 \
 && test "$(git -C /opt/vllm-src rev-parse HEAD^{tree})" = 1cb86e078991895906e75544207733ee7373c55d \
 && rm /tmp/overlay.bundle
# 2. Hosted kernel stage, installed by the mtp3 guide's frozen installer against
#    its download contract (parts, receipt, archive prefix, 18-file manifest).
COPY repro/qwen38-flash-next-fp8-tp4-mtp3-b70/prepare-runtime.py \
     repro/qwen38-flash-next-fp8-tp4-mtp3-b70/runtime-contract.json \
     repro/qwen38-flash-next-fp8-tp4-mtp3-b70/runtime-stage.sha256 /opt/flash-next-stage-installer/
RUN mkdir -p /tmp/parts /tmp/stage-work && cd /tmp/parts \
 && for f in qwen38-flash-next-runtime-stage-2f829747.tar.part-0000 qwen38-flash-next-runtime-stage-2f829747.tar.part-0001 qwen38-flash-next-runtime-stage-2f829747.tar.receipt.json; do curl -fsSL -o "$f" "${STAGE_RELEASE}/$f"; done \
 && python3 /opt/flash-next-stage-installer/prepare-runtime.py --parts-dir /tmp/parts --kernel-stage /opt/kernel-stage --receipt /opt/flash-next-stage-installer/install-receipt.json --work-dir /tmp/stage-work \
 && rm -rf /tmp/parts /tmp/stage-work \
 && cd /opt/kernel-stage/vllm_xpu_kernels && sha256sum --quiet -c /opt/flash-next-stage-installer/runtime-stage.sha256 \
 && test "$(find /opt/kernel-stage/vllm_xpu_kernels -type f \( -name '*.py' -o -name '*.so' \) | wc -l)" = 18
# 3. Hosted public oneCCL 4ceafd1 build.
COPY patches/qwen38-flash-next-fp8-b70/oneccl-4ceafd1-b70-public/lib.sha256 /tmp/oneccl-lib.sha256
RUN mkdir -p /opt/oneccl-4ceafd1-b70-public && cd /opt/oneccl-4ceafd1-b70-public \
 && curl -fsSL -o lib.tar.zst ${ONECCL_RELEASE}/oneccl-4ceafd1-b70-public-lib.tar.zst \
 && test "$(sha256sum lib.tar.zst | cut -d' ' -f1)" = 34dc2cad9603d6d910d677042cd6d992717f79b72e59add71dbdc302e65f8c24 \
 && zstd -dq lib.tar.zst && tar -xf lib.tar && rm lib.tar lib.tar.zst \
 && sha256sum --quiet -c /tmp/oneccl-lib.sha256
# 4. Tuned MoE map and the record's launch configuration.
COPY experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32 /opt/moe-m1-w13-n32
COPY repro/qwen38-flash-next-fp8-tp4-mtp1-lossless-b70-27tps-20260905/container-serve.sh /opt/container-serve.sh
RUN python3 - <<'PY'
import torch, triton
assert torch.__version__ == "2.11.0+xpu", torch.__version__
assert triton.__version__ == "3.7.0", triton.__version__
PY
ENV PYTHONPATH=/opt/kernel-stage:/opt/vllm-src \
    LD_LIBRARY_PATH=/opt/oneccl-4ceafd1-b70-public/lib:/opt/kernel-stage/vllm_xpu_kernels \
    VLLM_XPU_ENABLE_XPU_GRAPH=1 \
    VLLM_TUNED_CONFIG_FOLDER=/opt/moe-m1-w13-n32 \
    CCL_SYCL_ALLREDUCE_LL=twoshots
ENTRYPOINT ["/opt/container-serve.sh"]
