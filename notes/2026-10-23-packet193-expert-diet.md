# 2026-10-23: packet193, exact instruction-diet micro of the record expert kernels (CPU preparation only)

Packet: `experiments/own-xpu-runtime/stage2/packet193-expert-diet/`. No device work has run. Nothing is queued.
Micro only; never an engine speed result.

## Why

packet192 (lane B, 2026-10-23) measured both record expert kernels as instruction-issue bound: gate/up cold 73.75 /
warm 46.35 / no-load 44.69 us, down 45.94 / 33.75 / 33.33 us. Coordinator ruling (quoted):

> packet192 measured both record expert kernels as instruction-issue bound (no-load within 4 % of L2-warm). Build
> packet193 as the exact instruction-diet micro: candidates `exp-diet` (gate/up), `down-diet` (down) and
> `exp-act-epilogue` (gate/up with the routed-activation epilogue in SLM), each bit-identical to the production kernel
> on all 384 real routes and the NaN/invalid-route fixtures on GNU and Intel host twins before any timing; a candidate
> counts only at <= 0.85x production cold AND warm in both launch orders; one lane-B micro window under 10 minutes.

## What was built

* `p193_diet.hpp`: three candidate kernels beside the pinned production sources (packet192's closure copied, never
  edited). exp-diet hoists the per-tile `exceptional` test to one uniform test per 256-weight step (proved
  `exceptional <=> d non-finite`), applies the sign to the decoded weight after the scale multiply (exact because every
  IQ2_S grid magnitude is in {8, 25, 43} and IEEE RN multiplication is sign-symmetric), and computes the four effective
  scales of a step once. down-diet decodes the half scale once per block instead of once per chain. exp-act-epilogue adds
  the routed activation (the record's separate `silu_product` launch, reproduced as a twin kernel) as an SLM gate<->up
  exchange inside the WG64, gated exactly as the separate launch is.
* `micro.cpp` (from packet192's harness): device byte identity of every candidate on all 384 real routes, warm,
  packet162b's real rows, packet162b's NaN/invalid fixtures f0/f1/f2 x valid/invalid, a non-finite-scale bank and the
  epilogue's inactive / error-preset gating BEFORE timing; cold (384 routes + 512 MiB scrub, 20 repeats) and warm (200)
  strata with production and candidate interleaved in both orders (pass 0 A/B, pass 1 B/A).
* `isa_count.py`: packet81's offline ocloc pipeline on this TU; single-lane walk of the K-loop body.

## Numbers (CPU)

* ISA (dynamic normal-path instructions per weight, offline BMG-G31): production gate/up 15.28 -> exp-diet **11.81**
  (0.773), exp-act-epilogue **11.84** (0.775); production down 20.81 -> down-diet **18.50** (0.889); no spills.
  Rejected forms: `std::bit_cast` byte-array extraction (20.5/weight + 4.9 KB spills: IGC materialises the array;
  production's shift/mask already becomes `:ub` regions) and the hoisted down products (a0 indirect moves + 512 B spills).
* Exactness: GNU twin 3,146 / 3,146 claimed rows byte-equal (incl. NaN fixtures and the non-finite-scale banks); random
  stress 100,000 IQ2 / 200,000 IQ4 blocks bit-exact in the finite profile on both twins, value-exact in the mixed profile
  (23,270 / 47,628 exception tiles). Intel twin: 3,134 / 3,146 equal; the 12 others (NaN-producing strata) differ in NaN
  payload order only (every differing word NaN on both sides; Intel's production differs from GNU's the same way).
  Nothing canonicalised; the device gate stays strict and names a payload-order-only kill verbatim.
* Device peak 1,119,693,652 B (< 1.2 GB), host admission 10 GiB, expected ~137 s (60-411), watchdog 1,800 s, 96 MiB writes.
* Builds: 0 warnings; device closure 48 files inside the packet; build tree 55 MB; root free 29 GB throughout.

## Row (PROPOSAL ONLY)

`ops/lane-queue/proposed-p193-micro-B.txt`, job `packet193-expert-diet-micro-B`, lane B, card 2 (`0000:43:00.0`),
output `evidence/diet-B1/`. Never queued by preparation.

## Report and projection

`s193_report.py`: per candidate/stratum medians (p10/p90) and ratios in both orders, <= 0.85 verdicts, us per
layer-equivalent saved, projected gains (two cards +1.32 % per 0.01 ms per GDN layer; one card 11.4 us/layer = +2 %),
combined pick. Kill rules: device byte difference (per candidate; value vs payload-order named), control disagreement
with packet192 > 10 %, p90/median > 1.5. If the ISA ratios transferred 1:1 to the cold stratum, exp-diet would save
~17 us/layer (two cards ~+2.2 %, one card ~+2.9 %) and down-diet ~5 us (+0.7 % / +0.9 %); the window decides.

## Deviations from the brief

* Item (ii) (byte-regioned extraction) is satisfied by the compiler, not by source: the explicit form was rejected by the
  ISA gate and is retained as evidence.
* down-diet ships without the hoisted products (rejected for spills); it still reduces the count by 11 % through the
  once-per-block half decode.
* The Intel host twin is byte-identical except for NaN payload order on the NaN-producing strata (reported, not loosened;
  README 2.7); the epilogue's non-finite-scale stratum is the one diagnostic row (`exactness_claim: false`).
* `units_idle` would tolerate the owner's endpoint-restore window (`window-p192-driver`, `-restore18`) per the brief; it
  had finished before the first compile, so every compile saw no active unit.
