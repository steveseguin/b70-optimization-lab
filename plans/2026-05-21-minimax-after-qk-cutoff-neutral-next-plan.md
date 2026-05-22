# MiniMax M2.7 After Q/K Cutoff Neutral - Next Plan

Date: 2026-05-21

## Current Position

- Public strict result to beat: `89.314195` output tok/s at p512/n1536, TP4, 4x B70.
- Warm in-process promoted-path control: about `92.3-92.9` output tok/s depending on cache/run method.
- Latest quality-clean candidate: `VLLM_MINIMAX_QK_RMS_DIRECT_INPLACE_MAX_NUMEL=4`.
- Latest decision: not promoted. It passed full strict quality, but paired throughput improved only `0.049%`, inside normal noise.
- Quality policy remains unchanged: exact raw145 n64/n256 hashes, semantic suite, arithmetic repeat, and extended sixpack before any promotion.

## What This Rules Out

Threshold tuning around the already-promoted Q/K direct in-place FP32 all-reduce is not enough. The `numel<=4` path is safe, but it does not remove a measurable backend cost.

Full/default graph capture is also not currently clean with XPU FlashAttention on this stack. A run without explicit PIECEWISE failed before generation because SYCL Graph does not yet support the scratch-memory feature used by FlashAttention. Keep PIECEWISE as the reproducible baseline unless the XPU/FlashAttention graph path changes.

## Next Work

1. Profile only the promoted path plus labels needed for the next source change.
   - Goal: avoid broad instrumentation overhead.
   - Focus: Q/K variance all-reduce, attention `o_proj` FP16 all-reduce, MoE output FP16 all-reduce, and any CPU-visible sync around graph replay.

2. Build a lower-level Q/K fusion instead of another Python wrapper.
   - Preserve exact operation order: variance, TP all-reduce, TP scale, clean-weight guard, apply.
   - Target: reduce at least one backend launch or Python/framework boundary.
   - Guardrail: must match raw145 n64/n256 and arithmetic repeat before any performance claim.

3. Revisit attention `o_proj` only if timing proves it is now larger than Q/K variance.
   - Previous Python-level wrappers were quality-clean but slower.
   - A useful candidate needs to move the collective/projection boundary lower than Python.

4. Keep MoE-output epilogue/all-reduce fusion on the queue.
   - Current Python-level replacement was slower.
   - A real win likely needs to happen inside the llm-scaler/custom kernel boundary, not as an outer wrapper.

5. Do not submit neutral screens to LocalMaxxing.
   - Submit only if strict quality passes and the result beats the public `89.314195` tok/s result by more than run noise.
   - Continue recording negative and neutral screens in GitHub for reproducibility.

## Immediate Candidate

The next candidate should be a narrow source-level Q/K variance plus apply fusion or a timing run that proves attention `o_proj` has become the larger bottleneck. More env-var threshold tuning is unlikely to produce the next meaningful jump toward the >100 tok/s warm target.
