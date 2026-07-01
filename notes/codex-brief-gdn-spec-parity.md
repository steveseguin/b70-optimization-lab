# TASK: Fix the GDN speculative-decode verifier parity bug (XPU)

You are working in a vLLM fork at `/home/steve/src/vllm` on an Intel XPU
machine (4× Arc Pro B70). This brief is self-contained. Read it fully before
touching anything.

## The goal this serves
>150 tok/s single-session decode on `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
with **no quality loss**. Speculative decoding is the only path to that speed.
Every spec method (EAGLE-1, MTP, DFlash) is blocked by ONE bug. Your job is
that bug.

## The bug (already localized — do NOT re-derive)
Spec-decode verification produces tokens that diverge from the no-spec
greedy baseline. First natural divergence is at output position 17 (no-spec
emits token 11436, spec emits 321). It is **not** sampler randomness and
**not** draft quality (it reproduces with a perfect "oracle" draft). It is
the verifier (target model) producing wrong outputs for the packed spec
rows.

Root cause (confirmed by code reading): the **GDN (Gated Delta Network)
recurrent state for packed spec rows is wrong**. The Qwen3.5/GDN hybrid
attention has a recurrent (SSM) state + conv state that must thread
sequentially across the spec rows of a request
[target, draft_1, ..., draft_k, bonus]. The XPU path does NOT compute this
sequentially. Instead it runs a packed forward through a custom
`gdn_attention_core_xpu` op and then **copies state slots** approximately
in `_xpu_gdn_promote_running_state`
(`vllm/model_executor/layers/mamba/gdn_linear_attn.py` ~lines 526-560).
That function's own comment admits: *"copying from the source row corrupts
the next ordinary decode."* Slot-copy can NEVER be exact.

Two prior agents each spent days tweaking the copy offsets (attempts
m18-m26). Every variant still drifted. **Do not tweak the copy.** Replace
the abstraction.

## What to do
1. Find the real implementation of `torch.ops.vllm.gdn_attention_core_xpu`
   (registered via CustomOp; trace it down — likely in `vllm/_custom_ops.py`
   or a compiled extension or `vllm/model_executor/layers/fla/`). Understand
   how it reads/writes `ssm_state`/`conv_state` and whether it threads state
   across a per-request spec sequence (it has `spec_query_start_loc`/
   `spec_state_indices_tensor` available in attn_metadata).
2. Make the recurrent state for spec rows **exact** — bit-identical to
   processing the sequence one token at a time. Preferred routes (pick the
   cleanest):
   (a) Fix `gdn_attention_core_xpu` (or its caller) to thread SSM state
       sequentially across each request's spec rows using
       `spec_query_start_loc`, so no external slot-copy is needed; OR
   (b) For spec rows only, run the recurrent update sequentially (correct
       by construction) even if slower — correctness first, optimize later.
3. Remove/replace the approximate `_xpu_gdn_promote_running_state` and
   `_xpu_gdn_mirror_prefill_spec_state` slot-copy calls for the spec path
   once the core update is exact.

## Hard rules (these are the failure modes of the prior agents — do not repeat)
- Work ONLY on this GDN spec-parity bug. Do NOT touch MoE kernels, the
  routed-GEMM code, oneDNN, or any "exact but small" speed knob. Those are
  proven exhausted.
- Do NOT re-tread slot-copy offset tweaks (m18-m26, SERIAL_SPEC_DECODE state
  copies). The copy approach is fundamentally approximate.
- Do NOT change no-spec decode behavior. No-spec must remain bit-identical
  (it's the 93.55 tok/s reference lane).
- COMMIT your work with a clear message when you have a candidate fix.
- Do NOT run the full vLLM server canary loop yourself (it is slow and
  needs the GPU runtime). Instead do focused unit-level validation: build a
  tiny synthetic spec sequence and prove the GDN recurrent state after your
  change matches a sequential (one-token-at-a-time) reference. Write that
  test under `/home/steve/llm-optimizations/scripts/` and leave the full
  endpoint validation to the operator.

## Deliverable
- A committed patch in `/home/steve/src/vllm` (and any kernel-side change in
  `/home/steve/src/vllm-xpu-kernels`) that makes spec-row GDN state exact.
- A short writeup at `/home/steve/llm-optimizations/notes/codex-gdn-parity-fix.md`
  explaining: the true root cause, the fix, the synthetic test + its result,
  and the exact endpoint command the operator should run to validate.
- If after focused effort you determine the bug is NOT fixable at this
  layer (e.g. it requires a SYCL kernel change you can't make), STOP and
  write that up precisely in the writeup with the exact remaining blocker.
  Do not spin.

## Validation command the operator will run (for your writeup)
```
cd /home/steve/llm-optimizations
MODEL_PATH=/mnt/fast-ai/qwen36-quark-int8-fp8-mtp-hybrid \
SERVER_LAUNCHER=scripts/launch-qwen36-quark-int8-accepted.sh \
VLLM_QWEN35_MTP_FORCE_FP8_BLOCK=1 \
VLLM_EXTRA_ARGS='--speculative-config {"method":"mtp","num_speculative_tokens":1}' \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":128}' \
XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 VLLM_XPU_FORCE_GRAPH_WITH_COMM=1 \
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1 VLLM_XPU_GDN_NATIVE_FALLBACK=prefill \
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1 VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1 \
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1 VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1 \
GPU_MEMORY_UTILIZATION=0.95 ABLATION_FAST_GRAPH_AUTOCONFIG=0 \
bash scripts/run-qwen36-ablation-candidate.sh tp4-mtp-k1-parity-validate
```
Success = json-canary 96/96 AND color-canary 96/96 (token-identical to the
no-spec baseline).
