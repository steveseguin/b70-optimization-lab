# Qwen3.8 27B Q8 TP2 recurrent-quad SG32 workgroup

Date: 2026-08-17

Status: closed; position artifact and `-0.233%` combined regression

## Hypothesis and contract

The accepted SG16 workgroup packs sixteen independent SG16 output-row
subgroups (256 work items) into each exact-shape recurrent GDN-quad launch and
delivered an order-balanced `+0.257%` realistic primary-median gain over SG8.
This bounded follow-up tests SG32 (512 work items) for the same local shape
`K5120/N5120+3072+24+24`.

Each output row remains one SG16 subgroup with the same Q8 DP4A block walk,
FP32 accumulation order and subgroup reduction. Only independent-row packing
changes. SG16 stays in the same binary as control; the accepted source/repro
is not modified during the screen.

- target-only equal TP2, F16 KV, FlashAttention, `b1024/ub256`;
- mechanism must announce SG32 on both devices and end with
  `VERIFY_MISMATCH=0`;
- eight-process position-balanced screen before endpoint work;
- advance only if both balanced halves and the pooled result support SG32;
- complete-output, semantic, repeat and long-context hashes must remain exact
  before any promotion.

## Result

The SG32 smoke announced `32xSG16` on both B70s for the exact local recurrent
shape and ended with `VERIFY_MISMATCH=0`.

The first eight-process order (`A-B-B-A,B-A-A-B`, `A=SG16`, `B=SG32`)
appeared strongly positive at `37.417536` versus `36.805149 tok/s`
(`+1.664%`). Its halves exposed a severe state/position conflict: `+3.225%`
then only `+0.150%`.

A fully complementary eight-process order swapped every arm position. It
reversed to `36.690102` SG32 versus `37.475763 tok/s` SG16 (`-2.096%`). Across
all 16 processes, each arm occupied the same position patterns and SG32
measured `37.053819` versus `37.140456 tok/s`, a **`-0.233%`** regression.

This is a clean rejection. No endpoint or extended quality suite was run
because the candidate failed the performance gate. Keep accepted SG16 and do
not retry this exact SG32 packing unchanged.

Artifacts:

- incremental patch after accepted SG16:
  [`../patches/q8-recurrent-quad-sg32-negative-20260817.diff`](../patches/q8-recurrent-quad-sg32-negative-20260817.diff)
- patch SHA-256:
  `e7e801d1cbc7ee28e395f1a6ce7ff44d6fc10300dcaed257dba2319a77816655`
- candidate `libggml-sycl.so.0.19.0` SHA-256:
  `12fe19ce55252ea13bcdc09bb1df74eaa04ca0c4b7bae0e0ec002a2bf772a448`
- raw local evidence:
  `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-quad-sg32/`

Both GPUs remained normal after the 16-run screen with no current-boot Xe/GuC
fault, reset, timeout, or hang signature. The initial CLI invocation with
joined option spellings was rejected before model loading and is not a result.
