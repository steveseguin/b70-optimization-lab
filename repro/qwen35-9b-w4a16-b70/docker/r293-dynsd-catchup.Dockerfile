# R293 variant (2026-09-11): the same overlay on the class-consistent FP16 linear image (R293 = R276 + r290-r293 patches to model_executor/layers/utils.py; no file overlap with these overlays). Content pins in run-qwen35-9b-w4a16-dynamic-server.sh are unchanged.
# dynsd-fullgraph + draft-state catch-up (preregistration
# notes/2026-09-10-prereg-draft-state-catch-up-at-schedule-transitions.md): a pure-decode step that
# schedules no drafts skips the draft layer's forward; the skipped positions' target hidden states
# and next tokens are kept in a per-request ring and replayed through the draft layer as a
# prefill-shaped pass the next time the request is asked for drafts. Steps with prefill tokens are
# never skipped. Pure Python; nothing the target computes changes, so outputs cannot.
FROM neural-download/vllm-openai-xpu:qwen38-int4-r293-dynsd-fullgraph
COPY r276-dynsd-catchup-gpu_model_runner.py /opt/venv/lib/python3.12/site-packages/vllm/v1/worker/gpu_model_runner.py
COPY r276-dynsd-catchup-llm_base_proposer.py /opt/venv/lib/python3.12/site-packages/vllm/v1/spec_decode/llm_base_proposer.py
