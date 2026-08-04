# Speculation is what makes this model's decode bandwidth-efficient

Date: 2026-08-04 America/Toronto

Status: **measured, six device configurations. Supersedes the two projections in
`2026-08-03-width12-lock-and-speed-ceilings.md`, both of which were wrong.**

## The measurement that settles it

A width-1 arm was built to isolate graph capture with no drafter at all. It
needed four separate gates relaxed, because speculation is an architectural
assumption in this stack rather than a policy: the breakable-graph contract
refuses capture when `speculative_config is None`, and both the runner and the
launcher derive the token budget as `8182 + (depth - 1)`, which is nonsense at
depth 0.

| config | GB/step | steps/s | achieved bandwidth | % of 2.12 TB/s |
| :--- | ---: | ---: | ---: | ---: |
| q12, M=12, 1K | 30.94 | 41.96 | **1.298 TB/s** | **61.2%** |
| q12, M=12, 32K | 32.50 | 37.70 | **1.225 TB/s** | **57.8%** |
| width-1 graphed, 1K | 9.16 | 12.92 | 0.118 TB/s | 5.6% |
| width-1 graphed, 32K | 10.72 | 13.31 | 0.143 TB/s | 6.7% |
| eager no-spec, 1K | 9.16 | 12.09 | 0.111 TB/s | 5.2% |
| eager no-spec, 32K | 10.72 | 12.12 | 0.130 TB/s | 6.1% |

Graph capture is worth **7--10%**, not the 2x previously attributed to it. The
real variable is **rows per step**: M=12 streams at ~60% of peak, M=1 at ~6%.
A tenfold difference in bandwidth utilisation from batch shape alone.

## Why: single-row MoE cannot saturate memory

At M=1 each layer gathers 10 arbitrary experts out of 256 and multiplies a
one-row activation against them. The GEMMs are too small to hide latency and the
gather is close to worst-case scattered access. At M=12 the same layer touches 97
experts, reads 3.4x more bytes, and streams them an order of magnitude more
efficiently because the work per fetch is large enough to matter.

**Speculation is therefore not overhead on this model. It is the mechanism that
supplies enough rows to use the memory system.** The width-12 verifier is not an
accident of the campaign's history; it is the reason decode works at all.

## Two retractions

Both prior projections in the companion note are withdrawn.

1. *"Disabling speculation is worth ~3x at long context (39.6 -> ~115 tok/s)."*
   **Wrong.** It is worth 0.34x. Measured 13.31 against 39.589 at 32K. The
   roofline assumed M=1 could reach the same fraction of peak as M=12; it
   reaches a tenth of it.

2. *"Target graphs alone give ~11%, so a ported width-1 path lands at 60--80
   tok/s."* **Also wrong**, and wrong for a second reason: the 11% figure came
   from q8, which pays draft passes inside the same step, so it never isolated
   capture. Isolated, capture is worth 7--10% and width-1 tops out near 13 tok/s.

The measurements said so three times before the mechanism was understood --
qdepth 7.25, q8 7.10, eager 12.09 -- all clustered near 10, none near 115.

## Target assessment, final

| target | measured | verdict |
| :--- | ---: | :--- |
| 1000 tok/s prefill | 5,169 @1K · 7,345 @4K · 7,345 @32K | **met** |
| 250 tok/s decode with speculation | 152.3 @1K | needs ~100% of peak bandwidth against 61% measured; bytes ceiling is 246.7 |
| 100 tok/s decode without speculation | 12.92 @1K, 13.31 @32K | needs 0.92--1.07 TB/s at M=1, roughly **8x** the measured small-M utilisation |
| >150 tok/s at 32K with speculation | 39.589 | bytes ceiling 68.5; **impossible** |

## On the premise that 608 GB/s should give more

It should not, and the bandwidth is not being wasted. The serving path already
achieves **1.3 TB/s of the 2.12 TB/s** available across four cards. The constraint
is bytes per token, not utilisation: top-10-of-256 routing at M=12 touches 97
experts per layer, so one decode step reads 31--33 GB. At 2.12 TB/s that caps
long-context decode near 68 tok/s no matter how good the kernels are, and 39.589
is 58% of that cap.

Making this model materially faster means reducing bytes per token, and the
largest reducible term is the **5.59 GB of BF16 attention weights** -- 61% of the
M=1 budget -- which the INT4 scheme never targeted. That is the one lever with
real headroom, and it is closed off by the standing constraint against further
quantisation.

## What remains genuinely open

- Raising M=12 bandwidth utilisation from 61% toward peak would take 32K decode
  from 39.6 toward the 68.5 ceiling. Worth roughly 1.7x and the only decode work
  with headroom that does not touch quality.
- Deeper drafts trade more experts touched against more accepted tokens.
  Acceptance is 23.9% at 1K and 0.47% at 32K, so this helps only at short
  context, and the crossover has not been swept.
- Prefill already exceeds target everywhere measured and needs no work.

## Boundaries

Six configurations, cold cache, `gpu_memory_utilization=0.80`, TP4, no
quantisation change, no caching or speculation setting used to inflate a number.
Every figure is a real request. The protected `125.4619731637751 tok/s`
conventional short-decode record is untouched.
