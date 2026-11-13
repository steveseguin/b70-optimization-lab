# rux4: software-pipelined prompt routed-expert kernels (2026-11-12, card 2)

Status: done 2026-11-13 01:45 (started 2026-11-12 21:55; restarted after the 00:22 host reset). Patch: `rux4-1.patch`. Work tree `b/` (engine dcf06e199 + `kernels/sycl_v41_routed_rux4.hpp` + the
`OWN_RUX4` plumbing), bench `b/tools/bench/bench_rux4.cpp`, diagnostics `b/tools/bench/rux4_diag.hpp`, machine code
in `isa/<build>/`, runs in `out/`, tools in `tools/` (`isa4.py`: register mode, spills, load-to-use distances;
`gain4.py`: per-format and per-3K-read prediction).

## Budget: where today's kernel spends its time (machine code first)

Today's prompt routed kernels (`RoutedIQ*SUX<NB, 6>`, groups of at most 6 slots) at blocks of 256 tokens, card 2,
per 3K read (13 blocks of 256 x the layers of each format; rux3's ascending-order bench): IQ2_S gate+up 533 ms,
IQ2_XXS gate+up 506, IQ1_S gate+up 338, IQ3_XXS down 316, IQ2_S down 313, IQ2_XS down 117, IQ2_XXS down 59:
**2,183 ms**.

Machine code of the IQ2_S gate + up form (RoutedUT R = 2, E = 8, 128 registers; `isa/` of rux3 x1, checked with
`tools/isa4.py`): its unit loop (8 blocks x 2 rows x 6 slots) holds 1,848 float instructions (1,536 of them the
multiply-adds), 801 integer, 128 SLM gathers (grid table), 202 global reads (x blocks: 4 transposed block reads of
256 B per slot and block). Per (row-block, slot) at the real 4.3 slots per group that is ~37 float-pipe clocks
(32 for the multiply-adds, which the exact order fixes), ~23 integer-pipe clocks, ~36 instructions to issue. The
kernel runs at ~94 clocks per (row-block, slot) (rux3: 2.0 us per slot at real 256). So no pipe is near full: the
time is waiting. The code shows where:

- **The grid gathers run one after another.** Every gather of a block's 16 values (2 rows x 8) is followed at once
  by the instruction that needs it (`isa4.py`: load-to-use distance 1 for 122 of 192 gathers; one register, r4,
  carries every address and result). A thread pays 16 SLM round trips in a row per block. The 256-register down
  forms (R = 4) and the one-row RoutedU3 batch their gathers (distance ~17-25), so this is register pressure in the
  128-register two-row form, not the code. Same in today's IQ2_XXS gate + up (RoutedU3 pairs: 60 of 64 gathers at
  distance <= 2).
- **Each slot waits for its x block.** The 4 block reads of a slot are issued right before its 32 multiply-adds,
  which wait on the first of them.
- With 8 threads per vector engine, the other threads cannot cover ~16 SLM round trips + 4-6 L1/L2 trips per block.

rux3's diagnostics (same loop with parts removed): multiply-adds only ~44 clocks, + x reads ~58, + decode ~72,
both ~94: the two waits add up more than their parts (they serialize on the same thread).

Prediction: issuing a block's gathers back to back (one round trip per block instead of 16), the next block's gathers
and the next slot's x read ahead of the multiply-adds, leaves the float pipe (~37 clocks) and the issue rate as the
bound; even half of the waiting removed is -25 to -30 % per launch.

## Forms (RoutedUP, `kernels/sycl_v41_routed_rux4.hpp`)

RoutedUT's schedule and per-row state with the decode cut in two phases: phase A = every gather of the sub-block
(R rows x E values) issued back to back (LV = 1: volatile inline SLM loads, so none waits for another), phase B =
the same scale multiply and sign xor as `F::wv`. XA = when x is read (0: right before the slot's products; 1/2: one
slot ahead; 3: all slots of the sub-block up front). PF = 1: phase A of the next sub-block before this sub-block's
products. Bit-identity argument in the header: each accumulator gets the same mul and add on the same values in the
same order; only updates of different accumulators interleave.

## Results

### Summary (2026-11-13, card 2, every run bit-identical)

`OWN_RUX4=1` (default 0) runs the OWN_MT_RUX blocks' cap-6 routed launches on the RoutedUP picks below. Final numbers =
queue12 (`out/run-h*.txt`): only today's kernel and the engine's own OWN_RUX4=1 type (`VarPick` = `RoutedIQ*SUP<NB, 6>`,
with its 64-work-group cap) in the rounds, 6 rounds per run; us per launch on the 3K prompt's real picks (4 sets).
Percent = against today's kernel timed in the same rounds (today's kernel timed twice in the same rounds: within +-0.4 %).

| format (layers on a card) | today's kernel | rux4 pick | 256 tokens: today -> pick | change | 512 tokens |
|---|---|---|---|---|---|
| IQ2_XXS gate+up (15) | RoutedU3 pairs (128 regs) | R4 E8 x1 LV0, 256 regs, 64 WGs | 2885 -> 2355 us | -18.4 % | -19.8 % |
| IQ1_S gate+up (10) | RoutedUT R2 E8 (128) | R2 E8 x0 LV0, 128 regs | 2913 -> 2553 us | -12.4 % | -11.5 % |
| IQ2_S gate+up (15) | RoutedUT R2 E8 (128) | R2 E8 x0 LV0, 128 regs | 3057 -> 2819 us | -7.8 % | -6.3 % |
| IQ3_XXS down (15) | RoutedUT R4 E8 XA2 (256) | R4 E8 x1 LV0, 256 regs, 64 WGs | 1712 -> 1549 us | -9.5 % | -9.5 % |
| IQ2_S down (15) | RoutedUT R2 E8 (128) | R2 E8 x0 LV0, 128 regs | 1738 -> 1594 us | -8.3 % | -8.3 % |
| IQ2_XS down (6) | RoutedU3 pairs (128) | R2 E8 x0 LV0, 128 regs | 1624 -> 1543 us | -5.0 % | -4.9 % |
| IQ2_XXS down (3) | RoutedUT R4 E8 XA2 (256) | R4 E8 x1 LV0, 256 regs, 64 WGs | 1578 -> 1415 us | -10.4 % | -10.2 % |

(means of the three runs h1-h3, 01:37-01:42; run-to-run range of each ratio <= 0.3 points at 256 tokens:
`out/conf-h.txt`; prediction: `out/gain-h.txt`.)

Bitwise: PASS on every format in every run of queues 7-12 (today's kernel against production's RoutedIQ*SU and every
candidate against today's kernel, all output floats compared, real GGUF weights of all 384 experts; real 256 / 512-token
blocks x 2 sets + tpe 4 / 8, and from queue8 on also real 16 / 64-token blocks; the final runs: 21 of 21 format checks).
Kernel journal clean after every run; no fault lines.

Predicted 3K read (tools/gain4.py, launches per read = 13 blocks of 256 x the layers of each format; the px-512 halves
launch 256-token kernels): card 2's routed kernels 2,398 -> 2,129 ms per 3K read (-269 ms, -11.2 %). If those launches
stay on the critical path as in the bench, the 3K read goes from 5.05 s to about 4.8 s (-5 %); the bench runs each
launch alone on a warm card, so the gate's number is the real one.

### What made the difference (machine code + runs)

- Plain loads (LV = 0) with the gathers of a sub-block written first beat the volatile inline loads (LV = 1) on the
  128-register forms of IQ2_S / IQ1_S / IQ2_XS and on IQ2_XXS down; at R4 on IQ2_XXS gate+up / IQ3_XXS down both are
  equal. Same ISA story as rux3: the decode's grid gathers no longer wait one after another; the multiply-adds
  (exact order) are untouched.
- R = 4 tiles at 256 registers with slot i + 1's x read before slot i's products (x1 / x2) win where the decode is
  cheap per value (IQ2_XXS, IQ3_XXS); for IQ2_S / IQ1_S / IQ2_XS the 2-row form at 128 registers wins.
- 64 work-groups for the 256-register forms (4 threads per vector engine: one wave of 16 sub-groups x 64 instead of
  two waves of 128): +1 .. +4 points on top (IQ2_XXS gate+up -12.0 % at 128 work-groups -> -16.6 % at 64, IQ1_S R4
  -6.9 -> -9.9 %, IQ3_XXS -7.5 -> -8.7 %, IQ2_XXS down -9.0 -> -10.1 %; queue9 `out/run-c*.txt`, `out/conf-c.txt`).
- Slower everywhere (closed): PF = 1 (the next sub-block's gathers early: +7 .. +98 %), XA = 3 (all slots' x up front:
  tens of KB of spills, +1,600 %), R 2 E 2 (+40 .. +90 %), R 4 E 4 (+6 .. +29 %), R 3 E 8 (+4 .. +14 % mostly), tiles of 6
  and 8 rows (E 2 / 4 / 8: +15 .. +148 %), R 2 E 8 with x read ahead at 128 registers (x1 / x2: +48 .. +180 %, LV 0
  and 1).
- Method note: the ratio of a form depends a little on what else runs in the same rounds (g1/g2 with two forms 2-3x
  slower in the rounds: IQ2_S gate+up -5 % where the clean runs give -7.9 %); the final table is from runs with only
  today's kernel and the pick.

### Runs

- queue7 (00:32): `out/run-p1a, p2a, p3xa, p3qa, p3da, g2x` (first forms + diagnostics)
- queue8b (00:56-00:58): `out/run-p4aa/ba/ca` (down formats), `p5sa`, `p5wa`, `p6sa/wa` (R 6 / 8), `*64` (64 WGs)
- queue9 (00:58-01:02): `out/run-c*` (6 rounds, 128 vs 64 WGs, A B B A), summary `out/conf-c.txt` (tools/conf4.py)
- queue10 (01:21-01:26): `out/run-f*` (VarPick of the first picks + alternatives: R2 E8 x0 LV0 won IQ2_S down / IQ2_XS down /
  IQ1_S at 256)
- queue11 (01:29-01:34): `out/run-g*` (R2 E8 x1 / x2 LV0 at 128: +48 .. +180 %, closed)
- queue12 (01:37-01:42): `out/run-h1..h3` (final: today's kernel vs VarPick only), `out/conf-h.txt`, `out/gain-h.txt`

Diagnostics (p1a, IQ2_S gate+up, RoutedUT's loop with parts removed, us per slot at 256): R2 E8 128 regs: whole 1.95,
multiply-adds only 0.93, x reads only 1.19, decode only 0.71; R4 E8 256 regs: whole 2.08, multiply-adds only 1.01,
x reads only 0.77, decode only 1.22. The rux4 picks bring IQ2_S gate+up to 1.83 us per slot: the multiply-adds alone
(0.93) leave room; the x reads (each 1 KB read feeds 2 rows) are the next wall for the 2-row forms.

### Integration (main thread)

- Patch: `/home/steve/dsv41-work/rux4/rux4-1.patch` against lab HEAD 477999804 (no engine change since 83c00d95a):
  `git apply --check` OK (tools/mkpatch2.sh); the engine's syntax check (build108.sh's `icpx -fsyntax-only
  own_run_v41.cpp` with the engine flags) passes on HEAD + patch (tools/syncheck.sh, logs/syncheck.log).
- Files: new `kernels/sycl_v41_routed_rux4.hpp`; `backend_sycl_v41.hpp` (its include); `backend_sycl_v41_mt.inc` (`bool
  rux4 = false`, the XP selector block before the XR block, and in `gu` the form's own work-group cap: `max_wg`
  lowered to `K::WGCAP` when the kernel has one, i.e. only RoutedUP); `own_run_v41.cpp` (`OWN_RUX4`); plus the bench
  `tools/bench/bench_rux4.cpp` and `tools/bench/rux4_diag.hpp` (not built by the engine; drop them if unwanted).
- New env var: `OWN_RUX4=1` (default 0 = today's kernels, no other change). It acts only where OWN_MT_RUX runs (default
  on, blocks of >= OWN_MT_RUX_MIN = 16 tokens) with groups of at most 6 slots (OWN_MT_EU=6, the default); checks of 2-6
  tokens and one-token steps are untouched.
- Compile flags: none new (the engine's -DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1 -DOWN_R2_XORP=1, -fp-model=precise
  -ffp-contract=off, auto large-GRF). The bench builds used exactly those. Register modes are pinned per kernel
  (K::GRF through RowsGrfK): the R 4 picks at 256, the R 2 picks at 128. Seven new kernel instantiations (one per
  format with a pick).
- The bit-identity argument is in the header (each accumulator gets the same mul and add on the same values in the same
  order; only updates of different accumulators interleave; same reduction R2_XSUM with OWN_R2_XORP as the shipped
  forms' xperm-4 lowering).
