# R293 variant (2026-09-11): the same overlay on the class-consistent FP16 linear image (R293 = R276 + r290-r293 patches to model_executor/layers/utils.py; no file overlap with these overlays). Content pins in run-qwen35-9b-w4a16-dynamic-server.sh are unchanged.
# R276 + dynamic-Mamba-allocation overlay + full decode graphs per scheduled K on the v1 runner.
# Why: vLLM rewrites FULL_DECODE_ONLY to PIECEWISE under num_speculative_tokens_per_batch_size
# (dyn1 ran eager, 77.6 tok/s), and PIECEWISE with the default splitting ops changes arithmetic on
# the eager attention/GDN path so the 1-row oracle and the 4-row verify disagree at a 4K tie site
# (pwdynm1x, structured-docs-4096). This overlay keeps the published FULL_DECODE_ONLY numerics and
# captures one full decode graph per query length the schedule can produce (keys differ in
# num_reqs, so a graph for 8x4 tokens is never replayed for 16x2). Pure Python; no contract-pinned
# file touched; static configurations keep a single query length and are unchanged.
# Patch: r276-dynsd-fullgraph.patch (on top of r276-dynamic-mamba-alloc).
FROM neural-download/vllm-openai-xpu:qwen38-int4-r293-dynamic-mamba-alloc
COPY r276-dynsd-fullgraph-config-vllm.py /opt/venv/lib/python3.12/site-packages/vllm/config/vllm.py
COPY r276-dynsd-fullgraph-cudagraph_dispatcher.py /opt/venv/lib/python3.12/site-packages/vllm/v1/cudagraph_dispatcher.py
COPY r276-dynsd-fullgraph-gpu_model_runner.py /opt/venv/lib/python3.12/site-packages/vllm/v1/worker/gpu_model_runner.py
