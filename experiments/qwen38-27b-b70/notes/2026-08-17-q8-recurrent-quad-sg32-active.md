# Qwen3.8 27B Q8 TP2 recurrent-quad SG32 workgroup

Date: 2026-08-17

Status: active; claimed on the reference ASRock host

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

Other hosts should not duplicate this exact SG32 recurrent-quad arm while the
note remains active.
