# Ornith 1.5 35B-A3B: four-row reuse regresses the large Q/K projections

Date: 2026-08-23 EDT

Status: **CLOSED PERFORMANCE NEGATIVE — do not ship**

The broad four-row reordered-ESIMD candidate regressed, while its output-head
restriction was neutral. This follow-up isolated the other high-work shape:
reordered Q4_K/Q6_K DMMV with a 2048-value input and 8192 output rows. That
scope covers 30 recurrent QKV and 10 full-attention Q projections per token,
without touching the smaller dense projections implicated in the broad result.

The candidate was valid and exact. A same-frozen-binary forced 128-token run
produced the canonical transcript SHA-256
`d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`
with the door off and on. The candidate reported 5,080 calls, exactly 40 per
decode evaluation across 127 evaluations.

The mirrored engine screen was negative:

| Arm | Runs (tok/s) | Mean |
| --- | --- | ---: |
| control | `120.052828`, `119.358832` | **119.705830** |
| four-row candidate | `118.654766`, `118.874610` | **118.764688** |

That is **-0.786%**. Sharing one 8 KiB activation across four rows does not
repay the extra ESIMD accumulator pressure at this shape. No server or canary
screen was justified, and the accepted stack remains unchanged.

The complete candidate source is preserved at
`../patches/llamacpp-ornith15-dmmv-esimd-quad-large-projections-negative-20260823.patch`.
Raw mirrored engine records and the structured result are under
`../data/2026-08-23-ornith35b-dmmv-esimd-quad-large-*`.
