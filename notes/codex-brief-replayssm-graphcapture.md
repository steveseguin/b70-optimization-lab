# TASK: Make the ReplaySSM spec path graph-captured (kill per-step recapture)

Work in `/home/steve/src/vllm` + `/home/steve/src/vllm-xpu-kernels`. Resume your
ReplaySSM port (commits through 42fc07e18 / 3b4effe).

## Status (your work + your profile)
- GDN spec-verify kernels (recurrent + conv staging) are fused + fast
  (~0.03 ms/layer each). Drafts accepted. Parity functionally fixed. GOOD.
- BUT endpoint is 0.36-0.65 tok/s. Your all-rank profile said:
  - steady p64/o4: forward_total ~18.7 ms, draft_total ~5.2 ms
  - "First spec decode is dominated by ReplaySSM cache/graph warmup/recapture,
    especially ensure_state and first native launches, with large rank skew."
- The huge gap between steady ~24 ms/step and the endpoint 0.36 tok/s means the
  spec path is NOT running captured in steady state — it's re-warming /
  re-capturing / desyncing across ranks every step.

## Task
Make the entire ReplaySSM spec-decode path **CUDA-graph-safe and captured** so
steady-state replay has zero per-step warmup:
- All ring cursors / `write_pos` / state buffers are **static buffers captured
  by the graph**, advanced in-place **outside capture** (post-verify), exactly as
  the SGLang PR sgl-project/sglang#28695 does (its notes: "cursors are static
  buffers advanced post-verify outside capture; the flush is device-side inside
  the kernel").
- No per-step `ensure_state` / re-alloc / re-compile / re-capture on the warm
  path. Pre-allocate rings at startup; reset only on prefill/COW.
- Kill the **rank skew**: all TP ranks must take the same captured path; profile
  must show balanced per-rank timing.
- If `forward_total ~18.7 ms` itself is too high for spec k=1 (2 tokens vs
  ~5.5 ms no-spec), check what in the spec forward is un-amortized (the MoE
  should amortize; the GDN is now fused). Report the forward breakdown.

Build: `/home/steve/llm-optimizations/scripts/build-vllm-xpu-kernels-xpu-c-only.sh`
then copy `_xpu_C.abi3.so` + `libgrouped_gemm_xe_2.so` into `vllm_xpu_kernels/`.

## MUST validate with the endpoint canary (speed is now the gate)
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
bash scripts/run-qwen36-ablation-candidate.sh tp4-mtp-k1-replayssm-graphcaptured
```
Success = json-canary **96/96** AND color-canary **96/96** AND corrected tok/s
within ~30% of the 93.55 baseline (i.e. steady captured replay, NOT 0.36 tok/s).

## Hard rules
- Don't change the validated ReplaySSM math. Only make it graph-safe/captured +
  kill rank skew.
- COMMIT when canary passes at speed; update notes/codex-gdn-parity-fix.md with
  real numbers.
- If speed still won't come up, STOP and give a precise per-region profile
  (which op dominates the steady step, per-rank) so the next step is targeted.
