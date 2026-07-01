# TASK: Make the spec-decode warmup BOTH fast AND correct

Work in `/home/steve/src/vllm` + `/home/steve/src/vllm-xpu-kernels`. Resume your
ReplaySSM spec-decode work (committed through 7afdb06ad).

## The exact finding (your last run)
- **Full-sampler warmup** at startup recovers speed (within ~30% of 93.55) BUT
  is NOT correctness-safe: json + color canary fail at 1/96 with MALFORMED output
  (e.g. `{"answer":  +`, wrong/empty color lists). So the warmup is corrupting
  something that affects real sampling.
- **Targeted rejection_sample/greedy-verifier warmup** is correctness-safe but
  does NOT recover speed. So the missing cost is in the full sampler path beyond
  the rejection_sample kernel itself (likely the sampling/topk/greedy path or a
  graph captured with wrong shapes/state during warmup).

## Task
Make a warmup that is BOTH fast AND correct:
1. Find exactly WHAT the full-sampler warmup corrupts (most likely: captured
   cudagraph for the sampler built with dummy/warmup shapes that don't match
   real decode, OR stale RNG/sample buffers, OR a topk/greedy fallback flag
   flipped during warmup). The malformed-output symptom (truncated/garbled
   tokens) points at wrong-shape capture or stale buffer reuse.
2. Fix it by ISOLATING the warmup: warm on separate buffers, reset/clear any
   sampler state after warmup, and ensure the captured graph matches real-decode
   shapes. Do NOT warm in a way that leaves captured graphs/buffers in a state
   that diverges from real serving.
3. Keep the speed win (the warmup must still eliminate the multi-second first
   step) while restoring canary correctness.

Build kernels if touched: scripts/build-vllm-xpu-kernels-xpu-c-only.sh + copy
.so into vllm_xpu_kernels/.

## MUST validate with the endpoint canary (both gates now: speed AND correctness)
```
cd /home/steve/llm-optimizations
MODEL_PATH=/mnt/fast-ai/qwen36-quark-int8-fp8-mtp-hybrid \
SERVER_LAUNCHER=scripts/launch-qwen36-quark-int8-accepted.sh \
VLLM_QWEN35_MTP_FORCE_FP8_BLOCK=1 VLLM_XPU_GDN_REPLAYSSM_SPEC=1 \
VLLM_EXTRA_ARGS='--speculative-config {"method":"mtp","num_speculative_tokens":1}' \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":128}' \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 \
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
GPU_MEMORY_UTILIZATION=0.95 ABLATION_FAST_GRAPH_AUTOCONFIG=0 READINESS_TIMEOUT_S=2400 \
bash scripts/run-qwen36-ablation-candidate.sh tp4-mtp-k1-replayssm-warmcorrect
```
Success = json-canary **96/96** AND color-canary **96/96** AND corrected tok/s
within ~30% of 93.55. Report acceptance + tok/s + canary counts.

## Hard rules
- Don't change validated ReplaySSM math. Only fix warmup state isolation.
- COMMIT when BOTH canary 96/96 AND speed gate pass. Update notes/codex-gdn-parity-fix.md.
- If you can't make it both fast and correct, STOP and report precisely what
  state the fast warmup corrupts (so it can be isolated surgically).
