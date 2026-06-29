# TASK: Get the ReplaySSM spec-decode path SERVING end-to-end (not layer-by-layer)

Work in `/home/steve/src/vllm` + `/home/steve/src/vllm-xpu-kernels`. Resume your
ReplaySSM spec-decode work (committed through 9557d9108).

## Where we are (your work, all committed)
- ReplaySSM GDN spec-verify algorithm: ported + math validated + drafts accept
  at 100%. Parity bug CRACKED.
- Fused GDN kernels (recurrent + conv staging): fast (~0.03 ms/layer each).
- PIECEWISE graph capture: COMPLETES (the overlarge-descriptor bug is fixed).
- VLLM_XPU_GDN_REPLAYSSM_SPEC=1 gates the path.

## The current blocker (end-to-end serving dies)
Run `tp4-mtp-k1-replayssm-capture-validate` (MTP k=1, TP4, PIECEWISE+cg128):
capture completes, "Application startup complete", but the FIRST real request
crashes the engine:
- `EngineDeadError: EngineCore encountered an issue`
- root cause in the log: `RuntimeError: cancelled` during the first request's
  model execution (prefill 498 tokens -> first spec decode). HTTP 500.
- No SpecDecodingMetrics emitted (it dies before completing a spec step).

## Task: make the spec path actually SERVE (canary-runnable), not just capture
Do NOT fix one isolated layer and stop. Get the endpoint canary to RUN
end-to-end. The likely culprits (investigate in order):
1. ReplaySSM spec ring/state not allocated/initialized correctly for the first
   real request (capture uses dummy shapes; first real request's prefill or
   first spec step hits uninitialized/wrong-shape state).
2. A captured graph that's invalid at replay (shape/state mismatch between
   capture-time dummy and real-decode).
3. The spec state lifecycle (alloc on prefill, reset on COW) not firing on the
   real serving path.

Fix whatever it takes so the server survives real traffic and completes a
canary. If fixing the crash reveals the NEXT issue (e.g. wrong output, or slow),
keep going within reason — but if you hit a 3rd distinct layer, STOP and report
the FULL remaining issue set (so it can be re-scoped, not nibbled).

## HARD SAFETY RULES (the last run wedged the GPU)
- NO max-batch / synthetic-load probes. Realistic single-request shapes only.
- ABORT immediately on any `UR_RESULT_ERROR_OUT_OF_RESOURCES`,
  `UR_RESULT_ERROR_DEVICE_LOST`, or D-state kworker. Do not retry-push.
- Don't change validated ReplaySSM math. Don't touch no-spec decode/prefill.

Build kernels if touched: scripts/build-vllm-xpu-kernels-xpu-c-only.sh + copy
.so into vllm_xpu_kernels/.

## Validate with the endpoint canary (the gate)
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
bash scripts/run-qwen36-ablation-candidate.sh tp4-mtp-k1-replayssm-serve
```
Success = server survives traffic + json-canary **96/96** + color-canary **96/96**
+ corrected tok/s within ~30% of 93.55. Report acceptance + tok/s + canary counts.

## COMMIT when canary passes; update notes/codex-gdn-parity-fix.md. If you hit a
3rd distinct layer or a wedge risk, STOP and write the full remaining issue set.
