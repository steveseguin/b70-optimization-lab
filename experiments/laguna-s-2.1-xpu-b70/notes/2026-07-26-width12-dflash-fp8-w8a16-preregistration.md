# Laguna width-12 DFlash FP8 W8A16 preregistration

Date: 2026-07-26 America/Toronto

Status: preregistered before implementation or endpoint measurement.

## Fixed benchmark and success gate

The benchmark remains the existing honest cold, cache-zero,
one-active-generation Laguna S 2.1 TP4 endpoint gate. A candidate is a success
only if it:

- measures at least 102 tokens/s;
- reproduces all 13 teacher responses bitwise;
- reports `cached_tokens=0`;
- preserves the audited 146/145 topology on all four ranks;
- uses the same scored window, payloads, model revisions, and run identity as
  the width-12 record lane;
- is measured once from a clean cold start, with no favorable retry or result
  selection.

The current best exact leg is 100.5248896052723 tokens/s:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/phase5-w12-b0dabaa3-20260726T144510Z`

The clean width-12 router/context-KV stack candidate measured
99.72015184765868 tokens/s and was 13/13 exact:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-width12-stack-clean-candidate2-1e9887a92-13e211c3b-20260726T205829Z`

## Candidate

Add one default-off selector,
`VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16=1`, with a fail-closed Laguna-specific
contract. It is valid only for the already-audited width-12/depth-11 TP4
DFlash configuration and requires the exact-attention, exact-MoE,
width-12-router, and DFlash context-KV workspace selectors.

With the selector enabled:

1. Convert only the DFlash drafter's 31 dense BF16 projections to
   per-output-channel E4M3FN weights and execute them through
   `_xpu_C.fp8_gemm_w8a16`.
2. Give the drafter a separate FP8 copy of the shared target LM head; never
   mutate the target LM head.
3. Fuse the six exact auxiliary RMSNorm/copy operations into a rowwise
   persistent-workspace combine. The combine must be raw-bit equivalent to
   the incumbent path when its FC remains BF16.

The target model, target logits, target KV state, rejection sampler, sampling
parameters, and correctness oracle remain unchanged. Draft proposals and
acceptance rate may change; no drafted token may be emitted without the same
target verification used by the control.

Quantization happens during model loading, outside the request and scored
window. It must not relocate graph capture, prefill, warmup, or any other
request work.

## Pre-measurement evidence

The file named `dflash-int4/model.safetensors` contains BF16 dense weights and
has no draft quantization configuration. The target's routed experts remain
separately quantized; this candidate does not touch them.

On physical B70 card 0, using the actual TP4-local matrix shapes at M=12,
21/21 ABBA blocks favored the FP8 kernel:

| projection | BF16 ms | FP8 ms | saving ms |
|---|---:|---:|---:|
| auxiliary FC `[3072,18432]` | 0.201659 | 0.101399 | 0.100285 |
| QKV `[2816,3072]`, per layer | 0.037500 | 0.027003 | 0.010529 |
| O `[3072,2304]`, per layer | 0.037173 | 0.026857 | 0.010362 |
| gate `[3072,3072]`, per layer | 0.037603 | 0.026998 | 0.010797 |
| up `[3072,3072]`, per layer | 0.037497 | 0.026554 | 0.010899 |
| down `[3072,3072]`, per layer | 0.041169 | 0.029931 | 0.011034 |
| draft-only LM head `[25088,3072]` | about 0.2654 | about 0.1402 | 0.12525 |

Across six DFlash layers, the projected projection/head saving is about
0.547 ms per draft cycle. The raw-bit-exact auxiliary-combine screen saved
about 0.072 ms per M=12 call, for a preregistered combined estimate of about
0.619 ms per cycle. This is a projection, not a throughput claim.

Per-channel FP8 output screens had relative L2 error around 2.55--2.72% and
cosine similarity around 0.99963--0.99967. That is sufficient to justify one
honest endpoint test, not to predict exact acceptance.

## Stop rules

Before an endpoint leg, the implementation must prove:

- selector default-off behavior is unchanged;
- contract drift fails closed;
- exactly the intended 31 draft projections are transformed;
- the original target LM head is not mutated;
- auxiliary-combine BF16 behavior is raw-bit exact;
- workspace pointers and tensor signatures are stable;
- the relevant unit/contract suite passes.

The first valid cold endpoint result is the result. If it is under 102
tokens/s, inexact, cached, or topologically invalid, record it as a loss and
diagnose from that artifact rather than rerunning for a favorable number.
