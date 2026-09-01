# Qwen3.8 FP8 TP2 MTP1 global batch-invariance R64: incompatible

R64 did not reach the benchmark. The server verified all 66 model files, loaded
the model, and then failed closed during worker initialization:

> `RuntimeError: VLLM batch_invariant mode is not supported for GDN_ATTN.`

The only changed variable from the R63 FP16-draft control was
`VLLM_BATCH_INVARIANT=1`. No request was sent, so this is neither a speed result
nor an output-quality result. It does establish that the broad upstream switch
cannot repair this Qwen3.8 lane without changing the GDN support boundary.

The next screen is deliberately narrower: use the existing deterministic XPU
linear implementation only for `ParallelLMHead`. A real-shape XPU smoke at
`[M,5120] x [5120,124160]` produced a bitwise-identical first output row for
`M=1` and `M=2` with zero maximum difference. R65 will test that path under the
strict sequential-oracle gate while leaving GDN, attention, MoE, and all other
linears untouched.

Evidence and identities are in
[`2026-09-01-qwen38-fp8-mtp1-batch-invariant-r64-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-batch-invariant-r64-result.json).
