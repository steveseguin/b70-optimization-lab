# TASK: Pre-warm the spec-decode draft + rejection sampler (kill the multi-second first step)

Work in `/home/steve/src/vllm` + `/home/steve/src/vllm-xpu-kernels`. Resume your
ReplaySSM port (commits through 7afdb06ad).

## The exact blocker (your profile)
The FIRST post-prefill spec-decode step takes **seconds per rank**:
- rank0: `draft_total 5678 ms`, `rejection_sampler 3102 ms` (rank1-3 similar).
Steady state is already fast (~24 ms/step). So the endpoint (0.36 tok/s) is
being crushed by this first-step warmup firing per request.

## Task
Eliminate the first-spec-step warmup so steady-state speed holds from the first
real request:
1. **Pre-warm the draft model (MTP) forward** during engine startup / the
   existing cudagraph capture phase (run a dummy draft forward + capture it),
   so the first real spec step doesn't compile/autotune/recapture.
2. **Pre-warm the rejection sampler** the same way (it's taking ~3 s on first
   use — likely first-call compile/capture). Ensure the rejection-sampler kernel
   is captured/warmed before serving.
3. Make sure the warmup runs once at startup, NOT per request.
4. Re-confirm the ReplaySSM spec path is fully captured (static cursors advanced
   outside capture) so no per-step recapture remains.

Build kernels if touched: `/home/steve/llm-optimizations/scripts/build-vllm-xpu-kernels-xpu-c-only.sh`
then copy `_xpu_C.abi3.so` + `libgrouped_gemm_xe_2.so` into `vllm_xpu_kernels/`.

## MUST validate with the endpoint canary (now the real gate)
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
bash scripts/run-qwen36-ablation-candidate.sh tp4-mtp-k1-replayssm-prewarmed
```
Success = json-canary **96/96** AND color-canary **96/96** AND corrected tok/s
within ~30% of the 93.55 baseline. Report acceptance + tok/s + canary counts.

## Hard rules
- Don't change validated ReplaySSM math. Only add pre-warming + ensure capture.
- COMMIT when canary passes at speed; update notes/codex-gdn-parity-fix.md.
- If speed still won't come, STOP and give a precise per-region profile of the
  steady step + what the first step still pays.
