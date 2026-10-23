# 2026-10-23: packet192, expert-kernel issue-floor decomposition (CPU preparation only)

Packet: `experiments/own-xpu-runtime/stage2/packet192-expert-issue-floor/`.
No device work has run. Nothing is queued. Measurement only; never a speed result.

## Why

The expert kernel-floor study of 2026-10-23
(`stage2/packet190-record-bundle-k3x/analysis/expert-kernel-study-20261023.md`) found the record
gate/up kernel at 48.3 us with its weights in L2 (packet162b) against a 20.1 us copy floor and a
~27 us exact-ALU floor, and ruled NO-GO on a +2 % expert kernel packet. Coordinator ruling (quoted):

> Expert kernel-floor study 2026-10-23: NO-GO on a +2 % expert kernel packet; the single informative
> measurement is an issue-floor decomposition of the two record expert kernels: DRAM-cold on
> packet100b's 384 real routes with the 512 MiB scrub, L2-warm (packet162b harness), and a non-exact
> no-load run with the row pointer aliased to one L1-resident slab. If warm ~ no-load (expected ~48 us),
> only the instruction diet can move the class; if no-load <= 0.75x warm, LSC prefetch is the
> candidate. Build it as packet192, measurement only, one lane-B micro window under 10 minutes.

Without this split the two open candidates (instruction diet, register-free LSC prefetch) are coin
flips below the 15.1 us/layer two-card bar.

## What was built

* `micro.cpp`: one standalone SYCL binary (device mode) and its `OWN_RT_HOST_ONLY` twins (GNU, Intel)
  running exactly the record kernels `p90exp::Kernel<IQ2_S,2560,WG64,Prefetch=false,Wide=true>` and
  `p100::Kernel<2>` from packet189's checked include closure (`native-pinned/`, 46 files, absolute
  includes rewritten; root `p90_expert.hpp` 17c976c4..., `p100_down.hpp` 329ff3d0..., identical to the
  packet103 record bundle; the checked mirror adds only the p35 `prepared_submit` launch form).
* Strata: cold (384 real routes from packet100b, 512 MiB scrub before every launch, 20 x 2 passes);
  L2-warm (one route's experts repeated, 200 x 2 passes; plus packet162b's real layer0/layer24 rows
  for gate/up); no-load (`p192_noload.hpp`: same kernel bodies with every row address aliased into a
  16-row slab; non-exact, diagnostic only, outputs discarded; alias self-test on expert-0 16-row routes
  is byte-identical to production).
* Exactness: host-twin fixtures for all 384 routes + warm + real shapes (GNU writes, Intel verifies,
  byte rows identical); the device must match them before any timing counts.
* `s192_report.py`: medians/p10/p90 per stratum, ratios, decomposition, us per layer-equivalent,
  cross-checks vs the parent datums (packet162b 48.3 us warm; packet100b 46.04 us cold tile16 - the
  down bank is packet100's generator byte for byte), verdict per the ruling, follow-on bars
  (`exp-diet`, `exp-act-epilogue`, `down-diet`: <= 0.85x in both orders and every stratum), kill rules.
  Tested on synthetic streams and on the REAL packet100b/packet162b summaries (refused: different
  schema; datums recomputed) - 8 tests.

## Numbers

* Device peak 1,108,913,492 B (< 1.2 GB; gate/up phase then down phase; scrub 512 MiB resident).
* Host admission 10 GiB (8 GiB reserve + 2 GiB scratch); whole-host admission applies.
* Duration from packet100b's measured 0.92 ms per scrub+launch cycle: ~65 s (expected 30-194 s),
  watchdog 1,800 s, 64 MiB writes.
* Host twins at production shape: GNU 7 s (8 threads), Intel 4 s; 772 exactness rows equal.
* Build: 0 warnings; device closure 48 files inside the packet; build tree 30 MB.

## Row (PROPOSAL ONLY)

`ops/lane-queue/proposed-p192-micro-B.txt`, job `packet192-expert-issue-floor-micro-B`, lane B,
card 2 (`0000:43:00.0`), output `evidence/issue-floor-B1/`. Never queued by preparation.

## Gate receipts

build.json, fixtures.json, cpu-rehearsal.json (7 sandboxed preparation/refusal cases with the real
argv), analysis-tests.log, admission.json, cpu-seal.json, package-rows.json, check-queue-rows.json
(real entry plan, private-copy lanequeue plan, shared rehearse_entry --report, live pin guard),
final-checks.json, final-pin-guard.json, READY-FOR-DEVICE.json (written last).

## Deviations from the brief

* The "L1-resident slab" is bank rows 0..15 (expert 0's first tile) for every expert; the alias
  self-test therefore routes all ten slots to expert 0, where the alias is the identity.
* The analyzer takes the repeat counts from the stream's own summary (the shared report probe caps
  rehearsal files at 1 MiB); the window gate `run_micro.native_summary` enforces the proposed
  384/20/200/2 identity on the device stream and the analysis records `identity_as_proposed`.
* Parent inputs (routes, real rows, parent streams) are read in place and verified by digest; the
  only copy is the 16 KB route JSON derived from `routes.bin` (the sandbox can read JSON, not .bin).

## Device result (2026-10-23, lane B card 2, unit lanequeue-B38, 03:33-03:34 UTC): instruction-issue bound

**Measured 2026-10-23 (lane B, card 2, lanequeue-B38, 03:33-03:34 UTC, 34 s on device): both kernels instruction-issue bound.** gate/up cold 73.75 / warm 46.35 / no-load 44.69 µs (warm/cold 0.629, no-load/warm 0.964); down cold 45.94 / warm 33.75 / no-load 33.33 (0.735, 0.988); layer-equivalent cold 119.69 µs vs the 37.36 µs copy floor; no kill rule fired; cross-checks vs packet100b/162b within tolerance. Follow-on bars (≤ 0.85× production in both strata): exp-diet cold 62.69 / warm 39.40; exp-act-epilogue cold 67.29 / warm 44.01 (kernel + expsact launch); down-diet cold 39.05 / warm 28.69 → packet193. Evidence `evidence/issue-floor-B1/`.

Reading: the no-load stratum (every row pointer aliased to one L1-resident slab) runs within 1-4 % of the L2-warm stratum for both kernels, so the warm kernels are bound by instruction issue, not by load latency; register-free LSC prefetch is therefore not the candidate. The cold strata add a real DRAM term on top (gate/up +27 µs, down +12 µs over warm), larger than the study assumed from the in-model class numbers, which carry partial L2 reuse. Only an exact instruction diet can move the class; packet193 builds `exp-diet`, `down-diet` and `exp-act-epilogue` with byte-identity proofs on CPU before a lane-B micro.

Window receipts: `lineage/window-20261023/`; endpoints restored as `*-20261023-restore18`; PAUSE-A untouched, PAUSE-B re-armed.
