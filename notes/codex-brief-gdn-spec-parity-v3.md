# TASK (iteration 3): Route GDN spec rows through the SEQUENCE (prefill) path

Resume in `/home/steve/src/vllm` + `/home/steve/src/vllm-xpu-kernels`.
Read `notes/codex-gdn-parity-fix.md` (your v1+v2 writeups).

## Why v1 and v2 both failed
- v1 (Python per-position loop): correct-in-principle but ~15x too slow + residual canary mismatch.
- v2 (native spec-state table): faster (42 tok/s probe) but full canary still fails; you noted the path "still launches spec conv plus spec recurrent per GDN layer/spec row."

## The untried lever (the actual fix direction)
**The GDN op already threads recurrent state correctly for a SEQUENCE — that
is exactly why no-spec PREFILL works on XPU.** Every attempt so far forced
spec rows through the *decode/per-row* state semantics (slot-copy, per-position
loop, or a per-spec-row launch table). None of them treated a request's spec
rows as a single short SEQUENCE and let the existing sequence-capable kernel
thread the state the way prefill does.

For one request, the verifier rows `[target, draft_1, ..., draft_k, bonus]`
ARE a contiguous short sequence. The fix: present each request's spec rows
to the GDN recurrent kernel as a **sequence** (via `spec_query_start_loc`,
exactly like prefill uses `query_start_loc`/`cu_seqlens`), in ONE call per
layer — not per-spec-row, not per-position. State then threads correctly and
fast, reusing the path that already works for prefill.

## What to do
1. In `vllm/model_executor/layers/mamba/gdn_linear_attn.py`, for the spec
   rows, call the SAME sequence recurrent path that the prefill branch uses
   (the one that makes no-spec prefill correct), parameterized by
   `spec_query_start_loc` so each request's `[target..bonus]` is one
   sequence. Do NOT launch per spec-row or per spec-position.
2. Make sure partial acceptance still works: after verification, the running
   state for the next decode must be the state at the last ACCEPTED position.
   The sequence kernel writes per-position states (or you read the state at
   the accepted offset) — handle that explicitly. (This is the edge that bit
   v2 — get the partial-acceptance state publication right.)
3. Conv state: same treatment — thread it as a sequence, not a slot-copy.
4. Rebuild the kernel if you touch `vllm-xpu-kernels`
   (`scripts/build-vllm-xpu-kernels-xpu-c-only.sh`, then copy
   `_xpu_C.abi3.so` + `libgrouped_gemm_xe_2.so` into `vllm_xpu_kernels/`).
5. Revert/drop the v2 per-spec-row machinery once the sequence path works.

## MUST run the endpoint canary (synthetic is not sufficient — it lied in v1)
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
GPU_MEMORY_UTILIZATION=0.95 ABLATION_FAST_GRAPH_AUTOCONFIG=0 READINESS_TIMEOUT_S=2400 \
bash scripts/run-qwen36-ablation-candidate.sh tp4-mtp-k1-parity-fix-v3
```
Success = json-canary 96/96 AND color-canary 96/96 AND corrected tok/s
within ~20% of the 93.55 no-spec baseline.

## Hard rules
- Only this. No MoE knobs. No changing no-spec decode or prefill.
- COMMIT when the endpoint canary passes; update the writeup with real
  acceptance / tok/s / canary numbers.
- If the sequence path also can't pass canary, STOP and write the precise
  reason (which state — ssm or conv — diverges first, at which layer/position).
