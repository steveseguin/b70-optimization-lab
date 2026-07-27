# First FP8 candidate and q1 identity correction

Date: 2026-07-27 America/Toronto

## Candidate result before correction

Artifact:
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/fp8-kv/candidate-m12d11-20260727T140713Z`

The width-12/depth-11 candidate itself passed:

- explicit FP8 engine identity;
- four target calibrated-scale audits;
- four DFlash unit-scale/un-calibrated audits;
- FlashAttention v2;
- 291,707 KV cache tokens;
- four-rank 146/145 capture and replay;
- cold/cache-zero benchmark policy;
- clean worker teardown.

It measured `98.60760033588245 tok/s` by the conventional 99-interval metric,
but compared 0/13 against the first FP8 teacher. It is not promoted.

## Why that comparison was not yet causal

A fresh 128-token target-only repeat matched only 9/13 prefixes against the
first teacher. The mismatches started at token indices 1, 49, 85, and 90. This
showed that the teacher identity itself was not deterministic.

The runner had incorrectly coupled deterministic target arithmetic to the
candidate-only width selector:

```text
VLLM_XPU_EXACT_SPEC_ATTN=$width12
VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=$width12
```

Teacher mode sets `width12=0`, so it disabled the exact q1 path. Laguna's
original exactness diagnosis explicitly requires the q1 reference to use the
same deterministic target row-serialization and rank-ordered reduction path.
This was a harness identity error, not evidence that calibrated FP8 scales are
intrinsically nondeterministic.

The correction enables exact target attention/MoE and the exact W1/W2 routing
path for both teacher and candidate. Teacher mode still disables speculation,
graph capture, width-12 router/workspace selectors, and the draft model. A new
teacher must be generated after this correction before candidate exactness is
interpreted.
