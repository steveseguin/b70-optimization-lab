# Qwen3.8 Gemma RMSNorm cross-process D3 preregistration

Date: 2026-08-31

Status: **preregistered before D3 operator calls**

## Question

R9 proved eager rank-local nondeterminism and D2 proved the engaged padded B/A
path stable. Are the Gemma-style RMSNorm plain or fused-residual operations
unstable at MTP0 decode/prefill row counts, and do per-row or padded treatments
remove any instability?

## Frozen diagnostic

- exact current image ID
  `sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136`;
- local B70 GPU 0; four fresh containers; fixed FP16 inputs and FP32
  `(weight + 1)`; hidden size 5120; epsilon 1e-6;
- M values `1,48,49,52,53,55,56,57,59,65,71,75,78`;
- both plain RMSNorm and fused add+RMSNorm;
- direct batch, per-row serial, and zero-padded M=128 treatments; two identical
  calls in every process plus cross-process SHA-256 comparison.

Record exactness within and across processes and numerical parity between
treatments. A direct failure with a stable alternative is a candidate causal
repair; all-stable is negative evidence. No operator result promotes model
correctness or speed.
