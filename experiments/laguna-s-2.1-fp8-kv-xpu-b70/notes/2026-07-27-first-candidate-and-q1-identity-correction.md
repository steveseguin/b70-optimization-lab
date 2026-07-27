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

## Corrected reference and reinterpretation

Two independent corrected 128-token q1 runs are bitwise identical for all 13
prompts:

- `teacher-q1-exact128-a-20260727T142000Z`;
- `teacher-q1-exact128-b-20260727T142648Z`.

The original graph candidate matches either corrected reference on 12/13
prompts. The only mismatch is `shell-safety-review`, beginning at generated
token index 1. Therefore the earlier 0/13 result came from the invalid teacher,
but a narrow real difference remains in the width-12 speculative graph path.
The first teacher and `teacher-q1-repeat128-20260727T141339Z` are retained as
superseded diagnostics and must not be used as exactness oracles.

## Eager-isolation harness correction

The first `candidate-eager` launch
(`candidate-eager128-20260727T143353Z`) failed before model load. It carried
`VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA=1` while disabling the
Breakable graph, and vLLM correctly rejected that invalid combination.

The corrected eager arm keeps FP8 KV, width 12, depth 11, deterministic target
arithmetic, and real DFlash speculation, but disables prebuilt graph metadata
along with graph capture. This makes the arm a valid isolation of the graph
execution contract rather than a runnable performance candidate.

Source audit before the replacement run found three more selectors coupled to
that graph contract: the M-wide BF16 router, DFlash context-KV workspace, and
DFlash W8A16 path. The attempted run
`candidate-eager128-20260727T143805Z` was rejected at model construction by
the M-wide router guard, so it produced no performance or exactness result.
The eager isolation now explicitly disables all four graph-coupled selectors.
It retains the base BF16 router, fused W1-route-W2, route interleave, exact
attention, and batched exact MoE selectors, all of which have an explicit
enforce-eager contract.

The resulting run `candidate-eager128-20260727T144116Z` passed 13/13 token-ID
and text-hash exactness against the corrected q1 reference. It used real
depth-11 speculation (5,456 proposed and 1,200 accepted draft tokens), exposed
280,735 FP8 KV tokens, and shut down cleanly. Its preferred 99-interval median
was 29.075578 tok/s; performance is diagnostic only because this arm
intentionally disables the optimized graph stack.

This isolates the remaining 1/13 difference to the graph-coupled stack, not
FP8 KV storage or the generic eager width-12 verifier. The next preregistered
arm keeps the full 146/145 graph, M-wide router, DFlash context workspace, and
DFlash W8A16 path, changing only prebuilt exact attention metadata from on to
off. If it is 13/13, prebuilt metadata is the culprit. If it remains 12/13,
the next arm must remove the rest of the graph-coupled performance selectors
as a group before further bisection.
