#!/usr/bin/env bash
# After R152: host submission-latency probe (one card), then the R153a and R153b
# campaigns with the R152 runner (same gates), sequentially.
set -uo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
out=/mnt/fast-ai/bench-results
docker run --rm --name qwen38-host-probe --device /dev/dri:/dev/dri --group-add render --memory 6g -e ONEAPI_DEVICE_SELECTOR=level_zero:0 -e VLLM_TARGET_DEVICE=xpu \
  -v "${script_dir}/qwen38-fp8-host-submission-latency-probe.py:/tmp/p.py:ro" -v "${out}:/out" --workdir /tmp --entrypoint python3 \
  neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-fixed-k-w8a16-r139 /tmp/p.py /out/qwen38-host-submission-latency-probe-20260902.json >"${out}/host-probe.log" 2>&1
docker run --rm --name qwen38-allreduce-timing --ulimit core=0 --device /dev/dri:/dev/dri --group-add render --cap-add SYS_PTRACE --security-opt label=disable --ipc=host --shm-size=8g --memory 12g \
  -e ZE_AFFINITY_MASK=0,1 -e ONEAPI_DEVICE_SELECTOR=level_zero:0,1 -e VLLM_TARGET_DEVICE=xpu -e CCL_ATL_TRANSPORT=ofi -e FI_PROVIDER=tcp -e FI_TCP_IFACE=lo -e CCL_ZE_IPC_EXCHANGE=pidfd -e CCL_SEND=direct -e CCL_RECV=direct -e CCL_TOPO_P2P_ACCESS=1 \
  -e CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 -e CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 -e CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
  -v "${script_dir}/qwen38-fp8-tp2-allreduce-census.py:/tmp/ar.py:ro" -v "${out}:/out" --workdir /tmp --entrypoint python3 \
  neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-fixed-k-w8a16-r139 -m torch.distributed.run --standalone --nproc_per_node=2 /tmp/ar.py /out/qwen38-fp8-tp2-allreduce-census-timed-20260902.json >"${out}/allreduce-timing.log" 2>&1
ROOT="${out}/qwen38-fp8-triton-rmsnorm-head-20260902-r153ah" IMAGE_OVERRIDE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-triton-rmsnorm-head-chunk-r153ah \
  IMAGE_ID_OVERRIDE=sha256:fe07e43f18b743d8e199c014a9dec0abb7da60db22b08f5f2fa178ba9238bf39 \
  LAYERNORM_SHA256_OVERRIDE=37c65a77cd398e4d560f797c74c236336910683dfed3a2dc8259878d86e456a9 LM_HEAD_CHUNK_ROWS=32 \
  "${script_dir}/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh" >"${out}/r153ah-runner.nohup" 2>&1
ROOT="${out}/qwen38-fp8-triton-rmsnorm-head-20260902-r153bh" IMAGE_OVERRIDE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-triton-rmsnorm-head-chunk-r153bh \
  IMAGE_ID_OVERRIDE=sha256:094e31f39f99a03f6ce7e0a80c1e6d08ec9aafb5276acecbd8082f08e509612e \
  LAYERNORM_SHA256_OVERRIDE=415f115b413e6e2d28f0b3dad4147e59c406e0b0de40264e9ffbc6c4d0829f2b LM_HEAD_CHUNK_ROWS=32 \
  "${script_dir}/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh" >"${out}/r153bh-runner.nohup" 2>&1
