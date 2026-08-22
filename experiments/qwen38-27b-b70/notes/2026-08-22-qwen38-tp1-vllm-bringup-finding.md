# TP1 vLLM bring-up on the pinned image: blocked by a single-card stack bug

Date: 2026-08-22. Goal (user request from the Reddit B70 report): a TP1
benchmark matrix for our AutoRound INT4 model - MTP off/1/2/3, context <=32K,
KV fp8 vs f16, decode + prefill.

## Finding: our pinned vLLM crashes at TP1 for this hybrid model

The lane's pinned image (`0.20.2rc1.dev13+g9557d9108`, torch 2.11+xpu) runs
Qwen3.8-27B AutoRound INT4 fine at **TP2** (all night's endpoint/chunk work),
but a single-card **TP1** boot fails both graph modes:

- **PIECEWISE cudagraph**: boots, captures graphs, serves the first requests
  (200 OK), then the EngineCore dies mid-inference on a Triton JIT of
  `_zero_kv_blocks_kernel` (a KV-block-zeroing path; the log even warns
  "JIT compilation during inference ... consider extending warmup"). SYCL
  crash in `libsycl.so.9`. -> HTTP 500 EngineDeadError.
- **enforce-eager (PLAIN+inductor)**: EngineCore fails at initialization
  (custom_ops=['all'], rms_norm=['xpu_kernels','native']) before serving.

Both were minimal configs (no marginfree door set). Runs preserved under
`bench-results/.../tp1-bench-20260822/mtp0-f16-{short,eager-short}`.

## Interpretation

This is a TP1-specific stack gap on our pinned image, not a config typo: the
same model+stage serves correctly at TP2. The `_zero_kv_blocks_kernel` and the
eager-init failure are single-card code paths our pinned build does not cover.
Notably the Reddit report that motivated this ran the **newer
`vllm/vllm-openai-xpu:latest` (0.27.1, torch 2.13)** image, which is very
likely why single-card works there. Validating the community's TP1 vLLM claims
on our own hardware therefore needs that newer image (a separate pull +
bring-up), OR a warmup/patch for the `_zero_kv_blocks` path on the pinned one.

This independently corroborates the Reddit poster's theme that TP1 vLLM on
Intel is rough (their D15 prefix-cache and D17 MTP-concurrency bugs); we hit a
different single-card bug on an older image.

## TP1 data we DO have (llama.cpp SYCL lane, quality-accepted)

TP1 is fully working and characterized on the **llama.cpp SYCL** lane:

- Qwen3.8-27B **Q4_K_M target-only, TP1**: 27.81-27.86 tok/s conventional,
  24/24 bit-exact, full quality battery pass (the promoted TP1 lane;
  submission-ready). Low-context.
- Qwen3.8-27B **UD-Q5_K_S** (neural-download flagship package) TP1 depth
  sweep 0->32K exists (decode+prefill vs depth) but at the 256K-KV package
  config, so its absolute rates are package-specific, not a clean 32K-max
  TP1 number.

A clean llama.cpp TP1 context+KV matrix (Q4_K_M/Q8_0, KV f16 vs q8_0,
0->32K decode+prefill) IS runnable now with the neural-download depth-sweep
harness (llama-bench, no vLLM) and is the fast path to fill the TP1 table
while the vLLM TP1 image issue is separate.

## Disposition / next steps

1. vLLM TP1 matrix is BLOCKED on the pinned image. Options: (a) pull the
   newer 0.27.1 XPU image the Reddit used and bring up TP1 there (best match
   to the community claim), or (b) debug the `_zero_kv_blocks` warmup on the
   pinned image. Either is a bring-up session.
2. Fill the TP1 table now from the **llama.cpp** lane (clean Q4_K_M/Q8_0
   context+KV sweeps 0->32K via llama-bench) - fast, quality-accepted,
   no vLLM TP1 dependency.
3. TP3/TP4 (Qwen 27B on 3-4 B70) remains a future combo.

The bench driver `run-20260822-qwen38-tp1-bench.sh` is on record for the
vLLM TP1 attempt once the image question is resolved.
