# DeepSeek V4 K160 MTP1 M=2 fusion record

Date: 2026-07-16

## Outcome

Two exact, existing XPU kernels were extended through the M=2 target-verifier
path and produced a new four-B70 single-session record:

- headline strict suite: **57.412142 tok/s**, p10 **53.790798**;
- independent support: **56.952065 tok/s**, p10 **53.640486**;
- previous record: 55.703731 tok/s;
- headline improvement: **3.07%**;
- 70/70 ordered exact capture suites pass, including captures 28 and 58 after
  both strict suites;
- every realistic and exact request reports `cached_tokens=0`;
- LocalMaxxing: `cmrmrgce51nojmj01bbxoruuu` (`APPROVED`).

Evidence is under
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mtp1-m2-fusion-candidate-20260716T000928Z`.

## What was actually wrong

The shared expert already had a row-general clamped-SwiGLU plus dynamic FP8
quantization kernel. The model wrapper nevertheless hard-coded the fused path
to `gate_up.shape[0] == 1`, so the M=2 target verifier materialized a BF16
activation and launched a separate quantizer in every layer.

The generic routed MoE correctly retained expert grouping and cross-row weight
reuse at M=2, but performed gate clamp, up clamp, and SiLU/multiply as three
separate operations. The exact row-general `silu_and_mul_clamp` kernel used by
the qualified direct-M1 path was not selected for M=2.

The repair is deliberately narrow and default-off:

- vLLM `068d6beb25dcd571579f8efb06a3ca08aa29e164` adds
  `VLLM_XPU_V4_SHARED_EXPERT_FUSED_ACT_QUANT_MAX_M`, default `1`; the candidate
  sets it to `2` while retaining the existing fusion flag;
- XPU kernels `84c10f4f1b987c3ace43683299ce9c8d1bf9b94a` add
  `VLLM_XPU_V4_M2_ROUTED_CLAMP_SILU=1`, guarded to the exact K160 MXFP4,
  top-k-6, EP4, intermediate-2048, clamp-at-10 contract and runtime M=2;
- the record's wide-epoch oneCCL runtime remains
  `48fda4f0e074db005596d6899d5227d3f0316c12`.

No weight layout, routing result, target model, draft model, acceptance policy,
or collective protocol changed.

## Why the result matters

The successful change attacks the 43-layer target verifier rather than only
the single attached draft layer. It demonstrates that small exact fusions can
compose into a measurable whole-model win even when each boundary is below the
standalone integration threshold.

It also corrects the earlier strategy of copying the M=1 direct routed-MoE
design into M=2. M=2 already benefits from grouping rows by expert and reusing
weight tiles across verifier rows. Preserving that batching was essential.

## Gates and rejected designs

All timing gates used changing inputs and fixed-address XPU graph replay.

- Shared M=2 activation/quantization was bitwise exact on all four cards. Its
  reliable isolated saving was 0.428-0.453 ms per 43-layer cycle, below the
  standalone 0.50 ms bar.
- Two direct-M1 routed chains were bitwise equal to generic M=2, but regressed
  same-expert routes by 3.14-3.22 ms/cycle, overlap routes by 2.12-2.20 ms,
  duplicates by 1.42-1.44 ms, and mixed EP routes by 1.87-2.01 ms. Disjoint
  routes gained only 0.06-0.13 ms. This design is closed.
- Making M=2 route staging free bounded the removable zero/count/remap/copy
  work at only about 0.33-0.39 ms/cycle. Route staging alone is closed.
- Fusing generic M=2 clamp plus SiLU/multiply was bitwise exact and saved
  0.086-0.093 ms/cycle on the four-card gate. It is not worthwhile alone.
- The conservative minimum of shared M=2 fusion plus routed activation fusion
  was approximately 0.514 ms/cycle, just clearing the combined implementation
  bar. End-to-end qualification then showed the larger repeatable gain above.

Raw gates:

- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m2-shared-act-quant-microgate-20260715T235834Z`;
- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m2-direct-routed-upper-bound-20260716T000153Z`;
- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m2-routed-clamp-silu-fusion-20260716T000531Z`.

## Qualification and interpretation

Both fixed realistic suites ran 12 unique prompts exactly once, generated 128
tokens, retained streamed token IDs, and passed the cold/cached-zero gate. The
ordered exact suite ran 70 times after graph capture and crossed the historical
oneCCL rollover positions without a mismatch or stale response.

This remains target-verified MTP1 and one active generation. It is not
aggregate throughput. The fixed 12-prompt suite is a continuity benchmark and
has now been used heavily for development; it must not be the sole evidence
for a future deeper-speculation policy. New speculation work is governed by
`../quality/spec-eval-contract-v1.json`, which requires freeze-before-reveal
temporal holdouts, actual token-ID parity, request-scoped acceptance economics,
and separate nonrepetitive short- and long-context packs.

## Next action

Keep this service as the target-verified speed floor. Reject additional
single-launch M=2 tweaks below 0.50 ms/cycle. The next kernel work must remove a
larger materialized boundary while preserving grouped expert reuse, such as a
grouped GEMM epilogue/consumer fusion. Any deeper speculation must first clear
the held-out contract rather than merely improve the public 12 prompts.
