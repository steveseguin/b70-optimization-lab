# TASK: Capture the spec-decode path (no synthetic warmup) — fast AND correct, safely

Work in `/home/steve/src/vllm` + `/home/steve/src/vllm-xpu-kernels`. Resume your
ReplaySSM spec-decode work (committed through 7afdb06ad).

## What happened last time (AVOID)
Your "max-batch synthetic proposer warmup" OOR'd the XPU runtime and wedged the
GPU driver (10+ kworkers stuck in D-state; required a reboot). The full-sampler
warmup was fast but broke canary correctness (malformed outputs).

## The right approach (this task)
Don't do synthetic warmup at all. Instead, make the spec-decode path get
**captured during the normal cudagraph capture phase** so the first real spec
step uses pre-captured graphs (no per-step compile/autotune → no multi-second
first step, no synthetic load):
- Ensure the spec forward (draft/MTP + ReplaySSM GDN verify + rejection sampler)
  is included in the existing PIECEWISE capture sweep (the same capture that
  already handles the no-spec decode), at the real spec-decode shapes
  (query_len = 1 + num_speculative_tokens), NOT synthetic max-batch.
- The full-sampler warmup broke correctness because the captured sampler graph
  didn't match real-decode state/shapes. Proper capture at real shapes fixes both
  speed (pre-compiled) and correctness (shapes match).
- If a rejection-sampler/topk path can't be captured, ensure its first-call
  compile happens during startup (one small realistic-dummy call, NOT max-batch)
  and that it leaves no stale state.

## HARD SAFETY RULES (do not break these)
- **NO max-batch / synthetic-load probes.** Any warmup probe uses realistic
  single-request spec-decode shapes only.
- **Abort immediately** if any run shows `UR_RESULT_ERROR_OUT_OF_RESOURCES`,
  `UR_RESULT_ERROR_DEVICE_LOST`, device-lost, or a process entering D-state.
  Do not retry-push the runtime — stop and report.
- Don't change validated ReplaySSM math.

Build kernels if touched: scripts/build-vllm-xpu-kernels-xpu-c-only.sh + copy
.so into vllm_xpu_kernels/.

## Validate with the endpoint canary (both gates)
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
bash scripts/run-qwen36-ablation-candidate.sh tp4-mtp-k1-replayssm-capturedfast
```
Success = json-canary **96/96** AND color-canary **96/96** AND corrected tok/s
within ~30% of 93.55. Report acceptance + tok/s + canary counts.

## If it can't pass both gates
STOP and report: what the steady per-step profile is, whether the spec path is
now captured, and precisely what still makes the first step slow or the output
wrong. Do not push the runtime into a wedge.
