# R293 variant (2026-09-11): the same overlay on the class-consistent FP16 linear image (R293 = R276 + r290-r293 patches to model_executor/layers/utils.py; no file overlap with these overlays). Content pins in run-qwen35-9b-w4a16-dynamic-server.sh are unchanged.
# R276 plus the 27B lane's dynamic-MTP Mamba active-allocation patch
# (experiments/qwen38-27b-b70/patches/vllm-qwen38-dynamic-mtp-mamba-active-allocation-20260826.patch,
# test hunk dropped; applies to R276's vLLM without fuzz). Under a num_speculative_tokens_per_batch_size
# schedule the scheduler reserves Mamba/GDN state for the largest K still possible for the batch instead
# of the static maximum, which is what took the 27B lane's c64 aggregate from -23% to parity with MTP1.
# Pure Python; every pinned kernel digest and every contract-pinned file unchanged. With no schedule
# configured both changes reduce to R276's own behaviour.
FROM neural-download/vllm-openai-xpu:qwen38-int4-fp16-linear-classpad-cheapest-r293
COPY r276-dynamic-mamba-alloc-scheduler.py /opt/venv/lib/python3.12/site-packages/vllm/v1/core/sched/scheduler.py
COPY r276-dynamic-mamba-alloc-single_type_kv_cache_manager.py /opt/venv/lib/python3.12/site-packages/vllm/v1/core/single_type_kv_cache_manager.py
