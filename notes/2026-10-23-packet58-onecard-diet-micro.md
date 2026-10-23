# 2026-10-23 — packet58-onecard-diet-micro: the one-card gate/up diet as a lane-B micro (CPU preparation)

Packet: `experiments/own-xpu-runtime/stage2/packet58-onecard-diet-micro/`. Proposal only:
`ops/lane-queue/proposed-p58-dietmicro-micro-B.txt`. No GPU ran; nothing queued.

## Why

packet58-onecard-diet stopped: packet193's two-card diet header binds to 840-B FP32-expanded rows and cannot be
registered in the one-card dispatch, whose record gate/up kernel is `p58ag_exp::Kernel<IQ2_S,2560,64,false,true,0,
Cached=true>` on 820-B rows with 16-bit halves decoded through the 65,536-entry halfcache table and rows reached through
`p58::resolve` over expert-cache pointer slots (`indirect=true` on the record line). The coordinator ruled: derive the
one-card diet as a packet193-shaped micro, keeping the table decode and the slot resolution unchanged.

## What was built

* `p58ag_diet::GateUp` beside a pinned byte-for-byte copy of the production header and its 44-file one-card include
  closure (43 verified against packet58-onecard-cache23's own pins). The three transformations (hoisted uniform
  `exceptional`, sign after the scale multiply, hoisted effective scales) were re-proved on this kernel: the weight
  sign is the sign byte of the code pair (the table carries only `d`); `exceptional ⇔ d non-finite` holds because a
  table entry is a finite half value (|d| ≤ 65504, so `scale` is finite), ±Inf or the canonical NaN; the grid
  magnitudes {8,25,43} are static-asserted against this tree's table; the per-chain FP32 sequence is production's.
  Nothing was dropped.
* ISA (offline BMG-G31, packet81 pipeline): production 15.66 instr/weight (the table gather adds ~0.4 over the two-card
  15.28), candidate 12.02, ratio 0.767, 0 spills, 128 GRF.
* CPU proofs: GNU twin bit-exact on 1,250 byte rows at production shape — 384 real routes (indirect identity slots),
  warm indirect and direct, permuted slot tables (reverse, seeded shuffle) × 8 routes cross-checked against direct runs
  on the permuted routes, packet162b's real rows re-laid out into the 820-B layout by `p49bgemv::repack_row`, the
  NaN/invalid-route fixtures, the non-finite-half bank; 100,000-block random stress per profile with the table and
  the computed decode, 0 mismatches. Intel twin: equal on every claimed row; the NaN-only strata and the mixed-profile
  stress differ in NaN payload order only (0 value mismatches), as packet162/193 found for icpx. NaN-only strata are
  compared by is-NaN per word everywhere (`nan_claim`), never by bytes.
* Row: lane B, card 2, ~75 s, device peak 1,106,093,204 B, no model load, watchdog 1,800 s; device byte identity on
  every stratum first, then cold (384 routes + 512 MiB scrub, 20 repeats) and warm strata interleaved in both orders,
  then a fresh production-only control pass (the 10 % control rule, since no prior one-card micro datum exists).
* Report `s58dm_report`: ≤ 0.85× on cold AND warm in both orders; µs/layer saved; one-card projection at 11.4 µs/layer
  = +2 %; kill rules withhold, never ratio-correct. The wrapper releases the lane before the exactness gate and the
  report, so a post-drain failure cannot leave `active-lane-B.json` behind (packet193's failure mode), and it does not
  kill on a NaN-payload-order-only difference.

## Host hygiene

The coordinator put compiles on hold at ~06:40 UTC for the packet195 two-card chain. All three builds and the ISA
pipeline had finished before; the host-twin rebuild for the stress-row classification waited for clearance, and the
CPU proofs ran at 2 OpenMP threads under nice 19 on cores 8-15. Units and other host compilers were polled by exact
`comm` before every compile. Root free stayed ≈ 29 GB (floor 27 GB); build tree ≈ 21 MB.

## Next

The lane-B window driver may admit the one proposal row. PASS (≤ 0.85× cold and warm, byte-identical) → the engine
key `expert_gateup=production|diet` on the one-card record line with K1a/K1b and the one-load max23 bracket
(packet58-onecard-diet recommendation 2). Closed → not repeated in this diet form.
