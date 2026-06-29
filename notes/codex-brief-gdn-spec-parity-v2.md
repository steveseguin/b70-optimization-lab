# TASK (iteration 2): Make the GDN spec-parity fix FAST and COMPLETE

You are resuming your own work in the vLLM fork (`/home/steve/src/vllm`) and
`/home/steve/src/vllm-xpu-kernels`. Read your prior writeup
`/home/steve/llm-optimizations/notes/codex-gdn-parity-fix.md` first.

## Status of your first fix (commit 11058ba96)
- Synthetic test passes (`state_equal=true, output_equal=true`).
- BUT the real endpoint canary STILL FAILS: json-canary mismatched at repeat
  20/96 (token diverged to "prezi" — a residual correctness gap your
  synthetic didn't cover; likely conv-state or a partial-acceptance edge).
- AND it is ~15x too slow: 6.46 tok/s, decode 160 ms/tok (baseline 10.69).
  The Python per-spec-position loop calling the heavy FLA chunk kernel per
  position per layer is the bottleneck.

## The definitive root cause (you already found it)
Your writeup says it exactly: the `_xpu_C.gdn_attention` SYCL kernel "only
accepts one state index per sequence and writes a final state... it has no
interface for the full `spec_state_indices_tensor` column table, so the
exact spec-column contract has to be handled by the Python caller unless the
C++/SYCL interface is expanded."

That expansion is the fix. The Python per-position loop cannot be both
correct and fast — stop trying to make it work.

## What to do
Expand the native recurrent path so spec rows are exact AND fast in ONE
captured call, not a Python loop. Concretely:
1. In `/home/steve/src/vllm-xpu-kernels`, extend the `_xpu_C.gdn_attention`
   kernel (or add a thin spec-aware variant) to accept the per-request spec
   column table (`spec_state_indices_tensor`, `spec_query_start_loc`,
   `num_accepted_tokens`) and thread the recurrent (SSM) **and** conv state
   sequentially across each request's spec positions internally, writing the
   correct per-position output and the correct per-position state columns.
   This is the single fast captured op.
2. In `vllm/model_executor/layers/mamba/gdn_linear_attn.py`, call that
   kernel for spec rows (passing the column table) and REMOVE your Python
   per-position loop (`_xpu_gdn_exact_spec_recurrent` path). Keep no-spec
   decode unchanged.
3. Rebuild the kernel (`/home/steve/llm-optimizations/scripts/build-vllm-xpu-kernels-xpu-c-only.sh`
   then copy `_xpu_C.abi3.so` and `libgrouped_gemm_xe_2.so` into
   `vllm_xpu_kernels/`).

## If the kernel expansion proves too deep
Fallback that is still acceptable: make the per-position update lightweight
and graph-captured (NOT the heavy FLA chunk kernel per call). A fixed-k loop
inside the captured region, calling a cheap one-token recurrent update, is
capture-compatible and should be near-baseline speed. But the kernel
expansion is strongly preferred.

## Hard validation (you MUST run the endpoint canary this time — synthetic is not enough)
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
bash scripts/run-qwen36-ablation-candidate.sh tp4-mtp-k1-parity-fix-v2
```
Success = json-canary 96/96 AND color-canary 96/96 AND corrected tok/s back
within ~20% of the 93.55 no-spec baseline (i.e. not 6 tok/s). Report the
actual tok/s.

## Hard rules (unchanged)
- Only this bug. No MoE/kernel micro-opts. No changing no-spec decode.
- COMMIT when the endpoint canary passes. Update your writeup with the real
  endpoint numbers (acceptance, tok/s, canary counts).
- If after focused effort the kernel expansion is infeasible and the fast
  fallback also can't pass canary, STOP and write the precise blocker.
