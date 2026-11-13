# rux3: routed experts with many tokens per weight decode (2026-11-12, card 2)

Status: done (2026-11-12 21:50). **Bigger expert groups do not pay** with any kernel form we have: no OWN_RUX3 patch
is recommended (the opt-in code exists in `b/`, see "Engine design", and is bit-identical, but 4-14 % slower per
format). Side finding: **the engine's group order at blocks of >= 128 tokens (heaviest groups first,
`OWN_MT_EU_HEAVY=1`, the default until tp105) makes today's kernels 3-6 % (gate + up) and 8-15 % (down) slower than
the plain order** (`OWN_MT_EU_HEAVY=0`); six cards: 3K read px-512 5.52 -> 5.43 s, identical traces (tg105h); tp106
makes it the default. Numbers below are one-card bench times on card 2, real expert weights, every form bit-checked.

## In one paragraph

The prompt expert kernels decode each expert row once per *group* of slots (a slot = one token's pick of one expert)
and then run every slot of the group through it. Today a group holds at most 6 slots; at blocks of 256 tokens a
decode serves 4.3 slots on average, although a slot's expert is picked by 38 tokens of the block on average. The idea
was to let groups grow to 8 or 16 slots so the decode is paid less often. Measured: the time per slot hardly moves
with tokens per expert (4 to 64: within about +-15 % for every format and form), and with real routing every
bigger-group form loses. Why: at today's group size the weight fetch + decode is only about a third of the time; the
rest is per-slot work (reading the token's activations from cache and the multiply-adds), which bigger groups do not
reduce. Holding 8-16 slots per sub-group needs twice the registers, which halves the threads per core (or spills),
and the decode's and loads' waiting time then shows: that costs more than the saved decodes.

## Real routing: tokens per expert (3K prompt, u84 dump, 40 layers; `tools/groups_big.py`)

| block | experts used | tokens / used expert (mean, slot-weighted) | slots per group at cap 6 / 8 / 16 / 32 | slots in FULL groups of 8 / 16 / 32 |
|---|---|---|---|---|
| 256 | 185 of 384 | 8.3, 38 | 4.29 / 5.06 / 6.71 / 7.71 | 66.6 % / 48.3 % / 30.6 % |
| 512 | 228 | 13.5, 72 | 4.88 / 6.00 / 8.93 / 11.4 | 78.0 % / 62.9 % / 45.3 % |
| 1024 | 271 | 22.7, 133 | 5.31 / 6.74 / 11.1 / 16.0 | 86.3 % / 75.0 % / 59.8 % |
| 2048 | 312 | 39.4, 250 | 5.60 / 7.26 / 13.0 / 20.9 | 91.8 % / 84.4 % / 72.6 % |

## Measured: time per slot against tokens per expert

Bench `b/tools/bench/bench_rux3.cpp` on card 2 (runs `out/run-g1a..c.txt` gate + up, `out/run-d1a..b.txt` down;
tables by `tools/table3.py`). Real weights: all 384 experts of one layer per format, card 2's rows (gate + up:
768 rows x 5,120 columns as one launch; down: 864 rows x 2,304 columns). Bit-identity: every form below, on all
groups and on the two-list split, against `RoutedIQ*SU<NB, 6>`: PASS, 0 output floats differ (350 M per gate + up
format, 394 M per down format; real picks at 256 / 512, tpe 4 / 16). The engine's grouping kernel `ExpertGroupP2`
against the host lists: PASS, 0 words differ (90 groupings).

Synthetic routing, "tpe T" = every expert picked by exactly T tokens (64 T tokens). us per slot; "best other form" =
the fastest of 12 forms that use groups of 8 or 16 (R = 2 / 3 / 4 rows per tile, 1-8 elements per x load, x asked
one slot ahead or not, 128 / 256 registers), each on every group at its cap:

| format | kernel | 4 | 8 | 16 | 32 | 64 |
|---|---|---:|---:|---:|---:|---:|
| IQ2_S gate+up | today (cap 6) | 2.165 | 2.274 | 2.087 | 2.198 | 2.282 |
| | best other form | 2.428 (+12 %, MT8 ship) | 2.035 (-11 %, MT8 ship) | 2.049 (-2 %, MT8 ship) | 2.129 (-3 %, MT8 ship) | 2.173 (-5 %, MT8 ship) |
| IQ2_XXS gate+up | today (cap 6) | 1.924 | 2.005 | 1.777 | 1.815 | 1.806 |
| | best other form | 2.093 (+9 %, MT8 ship) | 1.794 (-11 %, MT8 ship) | 1.834 (+3 %, MT8 ship) | 1.761 (-3 %, MT8 ship) | 1.837 (+2 %, MT8 ship) |
| IQ1_S gate+up | today (cap 6) | 2.099 | 2.190 | 2.092 | 2.127 | 2.097 |
| | best other form | 2.180 (+4 %, MT8 ship) | 1.856 (-15 %, MT8 ship) | 1.915 (-8 %, MT8 ship) | 1.961 (-8 %, MT8 ship) | 2.206 (+5 %, MT8 ship) |
| IQ3_XXS down | today (cap 6) | 1.354 | 1.321 | 1.206 | 1.196 | 1.166 |
| | best other form | 1.399 (+3 %, MT8 ship) | 1.136 (-14 %, MT8 ship) | 1.123 (-7 %, MT16 ship) | 1.155 (-3 %, MT16 ship) | 1.176 (+1 %, MT8 ship) |
| IQ2_S down | today (cap 6) | 1.194 | 1.225 | 1.129 | 1.206 | 1.194 |
| | best other form | 1.279 (+7 %, MT8 ship) | 1.091 (-11 %, MT8 ship) | 1.102 (-2 %, MT16 ship) | 1.156 (-4 %, MT8 ship) | 1.194 (+0 %, MT8 ship) |
| IQ2_XS down | today (cap 6) | 1.077 | 1.076 | 0.988 | 0.993 | 0.986 |
| | best other form | 1.198 (+11 %, MT8 ship) | 1.021 (-5 %, MT8 ship) | 0.992 (+0 %, MT8 ship) | 1.001 (+1 %, MT8 ship) | 1.009 (+2 %, MT8 ship) |
| IQ2_XXS down | today (cap 6) | 1.260 | 1.224 | 1.136 | 1.125 | 1.103 |
| | best other form | 1.223 (-3 %, MT8 ship) | 1.022 (-16 %, MT8 ship) | 1.032 (-9 %, MT8 ship) | 1.004 (-11 %, MT8 ship) | 1.064 (-4 %, MT8 ship) |

(MT8 / MT16 ship = today's two-row form compiled for 8 / 16 slots, 128 registers. At 8 tokens per expert today's
cap 6 splits each expert 6 + 2, which is why that column is today's worst; any T that is a multiple of 6 would not.
The groups-of-16 forms R3 / R4 at 256 registers: 2.36 / 3.40 us per slot at tpe 16 for IQ2_S, +13 % / +63 %.)

Real picks of the 3K prompt, blocks of M consecutive tokens. Today vs the rux3 two-list split (full groups of C on
the best form, the rest on today's kernel; groups in ascending order in both):

| format | kernel | 256 | 512 | 1024 | 2048 |
|---|---|---:|---:|---:|---:|
| IQ2_S gate+up | today (cap 6) | 1.779 | 1.741 | 1.683 | 1.778 |
| | best two-list split | 1.910 (+7 %, MT16 R3E8G) | 1.871 (+7 %, MT8 ship) | 1.895 (+13 %, MT8 ship) | 1.807 (+2 %, MT8 ship) |
| IQ2_XXS gate+up | today (cap 6) | 1.691 | 1.654 | 1.594 | 1.585 |
| | best two-list split | 1.830 (+8 %, MT16 R3E8G) | 1.782 (+8 %, MT8 ship) | 1.728 (+8 %, MT8 ship) | 1.696 (+7 %, MT8 ship) |
| IQ1_S gate+up | today (cap 6) | 1.695 | 1.663 | 1.631 | 1.591 |
| | best two-list split | 1.782 (+5 %, MT16 R3E8G) | 1.729 (+4 %, MT16 R3E8G) | 1.820 (+12 %, MT8 R4E4PG) | 1.782 (+12 %, MT8 R4E4PG) |
| IQ3_XXS down | today (cap 6) | 1.055 | 1.015 | 0.999 | 1.003 |
| | best two-list split | 1.184 (+12 %, MT16 ship) | 1.154 (+14 %, MT16 ship) | 1.123 (+12 %, MT16 ship) | 1.140 (+14 %, MT8 ship) |
| IQ2_S down | today (cap 6) | 1.046 | 1.029 | 1.030 | 1.065 |
| | best two-list split | 1.111 (+6 %, MT16 R3E8G) | 1.117 (+9 %, MT8 ship) | 1.103 (+7 %, MT8 ship) | 1.146 (+8 %, MT8 ship) |
| IQ2_XS down | today (cap 6) | 0.974 | 0.955 | 0.948 | 0.960 |
| | best two-list split | 1.064 (+9 %, MT16 R3E8G) | 1.064 (+11 %, MT8 ship) | 1.028 (+8 %, MT8 ship) | 1.020 (+6 %, MT8 ship) |
| IQ2_XXS down | today (cap 6) | 0.984 | 0.959 | 0.946 | 0.953 |
| | best two-list split | 1.088 (+11 %, MT16 R3E8G) | 1.084 (+13 %, MT8 ship) | 1.056 (+12 %, MT8 ship) | 1.038 (+9 %, MT8 ship) |

Card 2 per 3K read (13 blocks x the layers of each format, `tools/gain3.py`): today's kernels 2,183 ms at blocks of
256 (ascending group order), the split 2,356 ms (+7.9 %). One expert launch per 512 tokens (the PX halves' routed
launches merged) instead of two of 256: 2,133 ms (-2.3 %), too little to give up the halves' overlap.

## Where the time goes (diagnostic kernels, `b/tools/bench/rux3_diag.hpp`, runs `out/run-x1a/b.txt`)

Timing-only copies of today's loop with parts removed (outputs differ by design; the control copy compiles to the
same machine code as the shipped form: 8,507 instructions, 192 B scratch, and times the same). Per slot, groups in
the heaviest-first order, IQ2_S gate + up / IQ3_XXS down, real 256 and tpe 16:

| form (today's) | full | without the per-slot x reads | without weight fetch + decode | multiply-adds only |
|---|---:|---:|---:|---:|
| IQ2_S gate+up R2, 128 reg, real 256 | 2.007 | 1.540 (-23 %) | 1.243 (-38 %) | 0.946 (-53 %) |
| IQ2_S gate+up R2, 128 reg, tpe 16 | 2.208 | 1.431 (-35 %) | 1.452 (-34 %) | 0.890 (-60 %) |
| IQ3_XXS down R2, 128 reg, real 256 | 1.307 | 0.852 (-35 %) | 0.677 (-48 %) | 0.551 (-58 %) |
| IQ3_XXS down R4, 256 reg, real 256 | 1.424 | 1.027 (-28 %) | 0.604 (-58 %) | 0.608 (-57 %) |
| IQ2_S gate+up R3 x 16 slots, 256 reg, tpe 16 | 2.373 | 1.085 (-54 %) | | |

Reading: the multiply-adds alone run at ~42 XVE clocks per (row-block, slot) against 32 for their instructions, so
they are near their bound; the rest is the x reads (a quarter to a third) and the weight fetch + decode (a third
to a half), overlapping. In 256-register mode (half the threads) the decode's waits and the x reads' waits are not
hidden: the R3 x 16-slot form spends 54 % of its time on x reads although it reads less x per row than today's.
That is why groups of 16 lose: the decode they save (~1/3 of the time at 4.3 slots per group, ~1/12 at 16) is
smaller than what the 256-register mode adds.

The earlier model (`ALU = 32 + 139 / S`, decode-bound) was wrong in its split: the decode instructions mostly fill
issue slots the loads leave idle, so their marginal cost per group is ~50-190 XVE clocks per row-block (fit over
tpe 4-64, `tools/fit3.py`), not 139 on top.

## Group order (side finding; `out/run-ord.txt`, earlier runs `out/run-x1a/b.txt`, `out/run-h1a1.txt`)

The engine groups a block's slots with `ExpertGroupPM`; from 128 tokens (`OWN_MT_EU_BIG_M`) it orders the groups
heaviest first (`k.heavy = big && mt_eu_heavy`, default on), below 128 by ascending first slot. That order was made
for groups of up to 16 slots; with today's cap of 6 (rux-1) it costs time on real picks. Same kernel, same groups,
only their order differs, so the outputs are bit-identical by construction (a slot's sums do not depend on where its
group sits in the list). One card-2 slot, today's cap-6 kernels, each pattern warmed up first, 4 rounds alternated;
the null test (ascending against ascending) stays within +-1.4 %:

| format | layers on card 2 | real 128: heaviest first vs ascending | real 256 | real 512 |
|---|---:|---:|---:|---:|
| IQ2_S gate+up | 15 | +2.8 % | +4.4 % | +1.6 % |
| IQ2_XXS gate+up | 15 | +1.4 % | +3.4 % | +3.5 % |
| IQ1_S gate+up | 10 | +0.2 % | +3.3 % | +5.7 % |
| IQ3_XXS down | 15 | +8.4 % | +13.8 % | +12.7 % |
| IQ2_S down | 15 | +10.5 % | +10.8 % | +8.5 % |
| IQ2_XS down | 6 | +9.9 % | +10.0 % | +7.5 % |
| IQ2_XXS down | 3 | +9.1 % | +15.3 % | +13.6 % |
| card 2 per 3K read | | 2,627 -> 2,514 ms (-4.3 %) | **2,536 -> 2,375 ms (-6.3 %)** | 2,404 -> 2,271 ms (-5.5 %) |

(Synthetic picks where every expert has the same count: 0-1.5 %. Two expert-major orders were also measured:
expert id then first slot, 0-4 % slower than ascending; busiest expert first, -3 to +1 % for gate + up but +3-6 %
for the downs. Ascending stays the best overall.) The bench's heaviest-first total, 2,536 ms per read, matches the
card-2 budget's 192 ms x 13 = 2,496 ms for the routed experts, so the bench reproduces what the engine runs today.
Why the order matters was not pinned down (the downs, with per-slot activations, lose most; ascending order walks the
block's tokens in memory order).

Switch: `OWN_MT_EU_HEAVY=0` (exists today; no patch needed). Six-card check (main thread's gate tg105h,
`runs/tg105h/summary.txt`, tp105 binary): 3K traces and first 40 ids identical at blocks of 256 and px-512; 3K read
px-512 5.52 / 5.52 s -> 5.43 / 5.44 s (-1.5 %), blocks of 256 5.69 -> 5.56 s (-2.3 %); answers (256 tokens) the same.

## What would make bigger groups (or anything per slot) pay

Today's form spends ~94 XVE clocks per (row-block, slot) at real 256 against ~42 for its multiply-adds alone; the
difference is waiting on the x reads and on the weight fetch + decode. Two levers remain, neither a grouping change:
- More rows per x read at 128 registers: R = 3 / 4 with 3-4 slots per group keeps today's accumulator count, but the
  decoder's per-row state does not fit: round g2 (built, `bin/bench_rux3_g2`, gate + up formats, ISA in `isa/g2`)
  spills 64 B - 15 KB per thread in 20 of its 27 new kernels (spill-free: R = 2 at 4 slots, R = 4 at 4 slots in
  256-register mode, IQ2_XXS R3E4 at 4 slots). Not timed (the cards went to tg106); `queue6.sh` runs it (and builds
  the down round d2). A leaner decoder state comes first.
- In 256-register mode, ask for the next block's weights / grid values and the next slot's x before the current
  multiply-adds (software pipelining), so half the threads still keep the core busy. rux-1's x-only version (XA = 2)
  helps the R4 downs at 6 slots and spills at 16.

## Engine design of OWN_RUX3 (written, bench-checked, NOT recommended)

Where the routed launches are issued (backend_sycl_v41_mt.inc, `tpm_layer`): phase 3b groups the block's 6 M slots by
expert (`ExpertGroupPM`, one work-group, into `egrp[c]`), then `routed_m` launches gate + up (one launch over every
group: `RoutedIQ*SUX<NB, cap>`), the SwiGLU, the act pull; phase 4 launches the down rows on the same groups. With
`OWN_PX` (+ `OWN_PX_BIG`: blocks of 512 as two halves of 256) every half runs its own phases 3a / 3b / 4 with its own
groups (`px_egrp[c][h]`), interleaved with the other half's pulls.

rux3 changes only the grouping and the routed launches, not the block sizes, the exchanges or the PX schedule:
- `ExpertGroupP2` (new, `kernels/sycl_v41_routed_rux3.hpp`): ExpertGroupPM's counting sort writing two lists in one
  launch (same work-group size and local memory): list A = every expert's full chunks of C slots (into `egrpA[c]`),
  list B = each expert's remaining slots in chunks of at most the cap (6), ExpertGroupPM's order (into `egrp[c]`).
  Checked word for word against the host lists in the bench (real picks of 16-256 tokens, C = 8 / 12 / 16, both orders).
- `routed_m`: when the layer was grouped in two lists (`rux3_c[c]`), first list A on `RoutedIQ*SU3A<NB, C>`
  (`Rux3Pick`), then list B on today's `RoutedIQ*SUX<NB, 6>`, both writing the same output rows (disjoint slots).
- `tpm_layer`: `rux3_c[c]` = `OWN_RUX3` set, `OWN_MT_RUX` on, block >= `OWN_RUX3_MIN` (64) tokens, cap <= 6.
- PX: list A per half (`px_egrpA[c][h]`, `px_r3[c][h]`), saved / restored with the other per-half values.
- Memory: one more RUGrp list per card (110 KB; a second one for PX half B); no activation buffers change. Free card
  memory after load (~3.1-3.6 GiB per card) is not affected.
- Driver (`own_run_v41.cpp`): `OWN_RUX3=8|16` (0: off, default), `OWN_RUX3_MIN=m`.
- Exactness: no output depends on the grouping (a slot's output rows are (row, slot) sums computed whole by the group
  holding the slot); list A's forms are RoutedUT forms (rux-1's bit-identity argument).

Not turned into a patch for the gate: at the measured +4-14 % per format it would slow the read. The work copy is
in `b/` (`mkpatch.sh` would write `rux3-1.patch`), kept for a future form whose per-slot cost does not grow with the
group size.

## Predicted 3K read

- `OWN_MT_EU_HEAVY=0`: card 2's routed kernels -160 ms per 3K read at blocks of 256 (PX halves), -6.3 % of their time.
  If they stay on the critical path (card 2's kernels are most of its read) the 3K read goes from 5.56 s to about
  5.40 s (-2.9 %); the other cards run the same formats in other mixes and should gain alike. Free: same outputs.
  Measured on six cards (tg105h): px-512 5.52 -> 5.43 s (-1.5 %), blocks of 256 5.69 -> 5.56 s (-2.3 %).
- rux3 as designed (split at 256): routed kernels +173 ms per read on card 2 (+7.9 %): the read gets slower. No gate.
- Bigger expert-only blocks (512): -50 ms of kernel time (-2.3 %) before losing the PX overlap: not worth it.
