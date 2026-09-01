# Qwen3.8 FP8 TP2 R62 concurrency screen R63

Date: 2026-09-01

Status: **aggregate floor passed; strict output identity failed**.

R63 tested whether the R62 draft-only INT4 head remained safe when the draft
projection received batched rows. The server provided 67.14× capacity for a
256-token request and admitted all 64 active requests without queueing. The
harness generated 64 sequential complete-token-ID oracles before measuring
c1, c2, c4, c8, c16, c32, and c64. There was no conditioning pass, every
request returned 128 tokens, and cached-token counts remained zero.

The candidate exceeded the user-requested aggregate floor, reaching
`1,080.851 tok/s` at c64. It did not pass the more important output gate:
55/64 c64 outputs matched their sequential oracle, and the first mismatch
appeared at c2. That result is not quality-equivalent and is not promoted.

A matched control used the identical image, scheduler, compile contract,
collective settings, cache policy, and workload, changing only
`VLLM_XPU_DRAFT_LM_HEAD_INT4` from 1 to 0. Its 64 sequential outputs matched
the candidate's 64/64, but it also first diverged at c2 and matched only 54/64
at c64. The candidate therefore inherited the existing MTP1 batch-shape
limitation rather than creating its first failure. At larger batches the exact
mismatch subsets varied between independently started servers, consistent with
slot/admission-order sensitivity. This diagnosis does not relax the gate: R62
may remain a single-user candidate, but it has no output-identity concurrency
claim.

The one-pass aggregate comparison was `1,080.851 tok/s` for R62 versus
`1,061.646 tok/s` for FP16 draft (`+1.809%`). This is diagnostic and too small
and under-repeated to promote. No new GPU/Xe fault appeared in either arm.

R63 also exposed a terminology hazard in the generic concurrency harness. Its
historical `output-isolation-qualified-shape-variant` classification means
requests did not cross-contaminate one another; it deliberately does **not**
mean outputs match their sequential oracle. The harness now emits an explicit
identity-qualification block, warns that isolation is not quality equivalence,
and supports `--require-output-identity`, which exits nonzero on any complete
output mismatch. Historical evidence is not rewritten.

The next optimization target is the underlying deterministic MTP1 batch-shape
path. Only after it is exact should R62 be repeated under aggregate load.

Structured evidence:
[`2026-09-01-qwen38-fp8-mtp1-draft-int4-r63-concurrency-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-draft-int4-r63-concurrency-result.json).
