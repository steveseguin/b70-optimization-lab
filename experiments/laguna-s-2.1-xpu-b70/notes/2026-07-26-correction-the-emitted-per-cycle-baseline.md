# Laguna — correction: the emitted-per-cycle baseline was an assumption, not a measurement

Date: 2026-07-26 America/Toronto

Status: **correction to prior notes.** No new hardware measurement; the record
throughput itself is unchanged at **94.920039** tok/s. What changes is the
per-cycle decomposition used to project every candidate, and therefore the
conclusion about which candidates can reach 102.

## What was wrong

`3.703` emitted tokens per cycle has been carried as the record baseline through
several notes. Its origin is the Phase 0 **preregistration**, which assumed an
acceptance rate and derived `2.703` accepted `+ 1` bonus. It was never measured.

It is also internally inconsistent. `3.703 / 94.920039` implies a **39.01 ms**
cycle, but Phase 0 separately measured **~32.8 ms**. Both cannot hold.

## What the measurements actually say

Phase 0 ran 13 prompts at 512 tokens, 6,656 generated tokens over **2,132 draft
cycles**, with roughly 70 s of decode inside a 145.4 s wall:

| quantity | value | consistent? |
| --- | ---: | --- |
| emitted per cycle | 6656 / 2132 = **3.122** | — |
| implied cycle | 70000 / 2132 = **32.83 ms** | matches Phase 0's ~32.8 ms |
| implied throughput | 6656 / 70 = **95.1 tok/s** | matches the 94.920 record |

The independent per-prompt table in
`2026-07-25-acceptance-is-the-only-lever.md` agrees: the median prompt runs
94.0 tok/s at **2.941** emitted per cycle.

So the record decomposition is **3.122 emitted per cycle over a 32.8 ms cycle**,
and the three quantities close on each other. The 3.703 figure does not.

## A second check that favours 3.122

Fitting a flat-acceptance geometric model to depth 7:

- `3.122` emitted implies conditional acceptance **p ≈ 0.6977**
- `3.703` emitted implies **p ≈ 0.756**

Measured top-1 coverage is **72.2%**. The fit from the measured baseline lands
next to it; the fit from the assumed baseline does not. That is independent
support for 3.122.

## Corrected projections

Using p₁ = 0.6977 fitted to the measured baseline, and p₂ = 0.116 by scaling the
measured top-1 → top-2 increment (72.2% → 84.2%) by the same factor:

| shape | emitted/cycle | vs record | projected tok/s |
| --- | ---: | ---: | ---: |
| chain depth 7 (record) | 3.122 | — | 94.9 |
| chain depth 11 (M=12) | 3.264 | +4.5% | 99.2 |
| chain depth 15 (M=16) | 3.297 | +5.6% | **100.2** |
| greedy tree, 11 nodes | 3.456 | +10.7% | **105.1** |
| greedy tree, 15 nodes | 3.665 | +17.4% | 111.4 |

## What this changes

**Depth alone can no longer reach 102 at any width up to the 16 bound.** The
previous note projected depth 15 at 102.4 and called it thin; on the corrected
baseline it is **100.2**, and it misses. The geometric tail is simply shallower
than the assumed baseline implied.

That promotes the tree from "the lever with margin" to **required** on the
acceptance axis, and it raises the value of the cycle-time axis, which is
untouched by this correction: the drafter is still ~8.7 ms of a 32.8 ms cycle
and still runs eager.

Combining the two independent axes — a 30% draft-time reduction (×1.086) with
an 11-node tree (×1.107) — projects roughly **114 tok/s**. Neither axis alone is
comfortable; together they have real margin.

## Also affected

The M=12 result reported as "+6.9% emitted per cycle, 3.958 vs 3.703" compares a
measured number against the assumed one. The measured 3.958 came from a
different run whose token budget does not match Phase 0's, so it is not directly
comparable to 3.122 either. The honest statement is that **M=12's emitted-per-
cycle gain has not been established against a matched baseline**, and the
corrected model predicts +4.5% rather than +6.9%. Settling it needs a width-8
and a width-12 leg over the same suite and token budget.

## Standing

Every number in this note except 94.920039 tok/s and the Phase 0 counts is a
model projection. The correction is about internal consistency of the
decomposition, not about a new measurement.
