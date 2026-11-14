# rux6: prompt routed-expert kernels, where the time goes and what takes it off (2026-11-13, card 1)

Status (2026-11-13 11:12): forms chosen and confirmed (section 2); patch `rux6-1.patch` (OWN_RUX6, default off)
against lab HEAD 0fe63f831 (`git apply --check` clean, re-checked 11:09); engine `bin/own_run_v41_rux6` built (try 2,
compile 1545 s) and passed sendcheck v2 (section 3: v1 flagged 3 sends in production kernels, judged false positives);
six-card gate `gate6.sh g1` running since 11:10 (unit rux6-gate-1110). Restart notes at the end.

Work tree `b/` (engine 71cb3cc08 copy + `kernels/sycl_v41_routed_rux6.hpp`; the kernel headers it shares with the lab are
identical to lab HEAD's), bench `b/tools/bench/bench_rux6.cpp` (bench_rux4's harness: real GGUF rows of all 384 experts,
the 3K prompt's real expert picks, real 256 / 512-token blocks, every output float compared against ship6 and prod6),
diagnostics `b/tools/bench/rux6_diag.hpp`, port / latency bench `b/tools/bench/bench_port6.cpp`, machine code in
`isa/<build>/`, runs in `out/`, tools in `tools/` (`ledger6.py`, `gain6.py`, `tab6.py`, `clk6.py`, `mix6.py`,
`conf6.py`, `sendcheck6.py`, `plumb6.py`, `mkpatch6.sh`), scripts `bld6.sh` / `r6.sh` / `q6.sh` / `runq.sh` (bench
builds and card-1 runs, card-share rules built in), `build_engine6.sh` (engine), `six.sh` / `one.sh` / `drive.sh`
(six-card engine runs, copied from qkv/).

## 1. Ledger: today's (rux4 pick) clocks per (row-block, slot)

Unit: vector-engine clocks per (row of 256 columns, slot) = us x 2.6 GHz x 256 engines / (rows x blocks), measured on
card 1 (port bench: 10.69 T float ops/s = 256 engines x 16 lanes x 2.6 GHz; a SIMD32 float instruction = 2 clocks).
The float floor: 256 multiplies + 256 adds per (row-block, slot) = 32 clocks; the machine code of the picks
(`tools/mix6.py`, hot loop) holds ~38-41 float-pipe clocks and ~12-19 integer-pipe clocks per (row-block, slot) at
4.28 slots per group, and the engine issues float and integer instructions in the same clock (port bench: float +
integer mix 219.7 ns/iter against float alone 196 and integer alone 150). So the issue floor is ~38-41 clocks.

Measured (out/run-d1a.txt, 256 tokens, 3 rounds; "pickD" = rux4's pick with one part removed, same tiles, same
register mode; percent = time saved against the pick):

| format | pick us/slot | clocks | float / int in code | no x reads (slots 1+) | no decode | no gathers | no products |
|---|---|---|---|---|---|---|---|
| IQ2_S gate+up (R2 E8, 128 regs) | 1.788 | 77.5 | 38.4 / 17.9 | -39 % | -28 % | -2 % | -7 % |
| IQ2_XXS gate+up (R4 E8 x1, 256 regs) | 1.478 | 64.0 | 38.3 / 11.5 | -24 % | -36 % | +7 % | -9 % |
| IQ1_S gate+up (R2 E8, 128 regs) | 1.621 | 70.2 | 41.4 / 17.5 | -36 % | -22 % | -4 % | -9 % |
| IQ3_XXS down (R4 E8 x1, 256 regs) | 0.992 | 84.9 | 37.5 / 12.4 | -16 % | -50 % | +2 % | -5 % |
| IQ2_S down (R2 E8, 128 regs) | 1.033 | 88.4 | 38.7 / 19.3 | -42 % | -38 % | +7 % | -6 % |

(512 tokens: the same picture, out/run-d1a.txt.) What this says:

- The kernels run at ~1.7-2.3x their issue floor: they wait, they do not compute.
- The products cost almost nothing (removing every multiply-add saves 5-9 %): the float pipe is not the limit.
- The grid gathers (SLM table reads) are not the limit either (removing them: -4 .. +7 %; conflict-free addresses
  -8 .. +5 %).
- The two waits are the x reads and the weight decode. "No x reads" (every slot uses slot 0's x read) saves 36-42 %
  on the two-row forms; the 4-row forms (IQ2_XXS, IQ3_XXS) share each x read between 4 rows and lose less (16-24 %),
  but there the decode is the bigger wait (36 / 50 %).
- Note on "xSame" (every slot reads slot 0's address): the compiler merged those reads and the slots' multiplies
  (machine code: 96 x reads instead of 576), so it is the same measurement as "no x reads", not an L1-hit test.
  `xHit` (D = 10: distinct reads inside the lines slot 0 just fetched) separates hit cost from miss cost.

Why the x reads wait: the 16 sub-groups of a work-group work on 16 neighbouring row pairs of the same expert group,
so they read the same x blocks at the same time; every slot's 1 KB x read is waited on right after it is issued
(rux4's XA = 0 pick: reading the next slot ahead was slower at 128 registers), and each job's x is new to L1 (the
next job of a work-group is ~5 groups further on).

## 2. What takes the waits off: prefetches of x ahead of use (measured)

Forms: `RoutedUX` (sycl_v41_routed_rux6.hpp) = rux4's pick, the same text (tiles, decode, x reads, products, reduction,
stores), plus prefetches; a prefetch moves no value into a register, so every output float stays the pick's (checked:
every run below compares every output float of every form with ship6, and ship6 with prod6: all PASS). Parameters:
XP = x blocks ahead; XW = who asks (0: every sub-group all of its group's slots; 1: sub-group s only slot s % cnt;
2: sub-group s < cnt only slot s); WP = weight rows (1: next segment's quant bytes, 2: + next job's rows); PK = message
(0: SYCL prefetch extension, which IGC emits L1-uncached / L3-cached, `load.ugm.d8u32.a64.uc.ca (32|M0) null`;
1: IGC's LSC prefetch builtin, L1 + L3, `.ca.ca`; 2: the OpenCL sub-group block prefetch, ONE uniform address and
1 KB per message, `load.ugm.d64x64t.a64 (1|M0) null`). No inline asm (the 04:09 fault, below); every build's machine code
passed tools/sendcheck6.py.

What the runs say (card 1, real picks, % against the pick timed in the same rounds, 256 / 512 tokens;
`python3 -I tools/tab6.py out/run-x4a.txt out/run-x6a.txt ... out/run-x10a.txt`):

- Every sub-group asking for every slot (XW 0) is far slower (+45 .. +130 %, x4a / x6a / x7a): 16 copies of each
  message per work-group. Weight prefetches (WP 1 / 2) are slower everywhere (+6 .. +131 %, x4a / x6a): the weight
  stream needs no help; they only add messages.
- Gate + up pairs (x of a token is shared by its 6 experts' groups, already in L3): only an L1 prefetch helps, and
  only the one-message form: XW 1, PK 2, 4 blocks ahead: IQ2_S -6.9 / -8.0 %, IQ1_S -7.2 / -7.0 % (x9a-c, 3 runs; xp3
  ties at 256 and loses at 512: IQ2_S -7.1 / -6.2, IQ1_S -6.8 / -4.0). L3-only (PK 0) is slower (+9 .. +14 %, x9a-c),
  per-lane L1 (PK 1) too (+2 .. +17 %, x6a / x7a). IQ2_XXS pair (R4, 256 registers): every form slower (+0.1 .. +12 %,
  x4a / x6a / x7a): no rux6 form (it keeps rux4's pick).
- Downs (per-slot x, new from memory): the L3 prefetch (PK 0) wins; L1 forms do not add to it. Two-row forms
  (16 sub-groups on one group): XW 2, 1 block ahead: IQ2_S -18.7 / -23.8 %, IQ2_XS -18.6 / -22.9 % (x8a / x10a);
  four-row forms (work-groups straddle groups): XW 1: IQ3_XXS 2 blocks ahead -11.2 / -16.8 % (x8a / x10a), IQ2_XXS
  1 ahead -13.8 / -19.8 % (x8a / x10a).

Picks (`Rux6Pick` in the header; the engine type `Rux6Q<TY, NB>` = rux4's pick + these), confirmed with the engine's own
type in clean rounds (only the pick and Rux6Q in the rounds, 5 rounds per run, 3 runs: `out/run-x11a.txt`, `x11b`,
`x11c`; bitwise PASS on all 7 formats in x11a, 16 / 64 / 256 / 512 tokens x 2 sets + tpe 4 / 8; journal clean):

| format (layers) | pick + prefetch | 256 tokens: us per launch | % (3 runs) | 512 tokens % | clocks per (row-block, slot), 256 |
|---|---|---|---|---|---|
| IQ2_S gate+up (15) | XP 4, XW 1, block prefetch (L1) | 2891.5 -> 2628.7 | -9.1 (-8.5 .. -9.6) | -9.9 | 81.6 -> 74.2 |
| IQ1_S gate+up (10) | XP 4, XW 1, block prefetch (L1) | 2598.2 -> 2387.7 | -8.1 (-7.5 .. -8.7) | -7.5 | 73.3 -> 67.4 |
| IQ2_XXS gate+up (15) | none (rux4's pick) | 2330.7 -> 2335.8 | +0.2 (same kernel) | +0.0 | 65.8 |
| IQ3_XXS down (15) | XP 2, XW 1, SYCL prefetch (L3) | 1566.7 -> 1377.9 | -12.0 (-11.8 .. -12.2) | -17.8 | 87.3 -> 76.8 |
| IQ2_S down (15) | XP 1, XW 2, SYCL prefetch (L3) | 1624.1 -> 1311.3 | -19.3 (-19.0 .. -19.6) | -22.6 | 90.5 -> 73.1 |
| IQ2_XS down (6) | XP 1, XW 2, SYCL prefetch (L3) | 1577.0 -> 1272.8 | -19.3 (-19.1 .. -19.4) | -23.4 | 87.9 -> 70.9 |
| IQ2_XXS down (3) | XP 1, XW 1, SYCL prefetch (L3) | 1434.1 -> 1241.8 | -13.4 (-13.3 .. -13.6) | -19.5 | 79.9 -> 69.2 |

(us and % from `python3 -I tools/gain6.py out/run-x11[abc].txt` and `tools/tab6.py`; clocks from `tools/clk6.py`,
`out/clk-x11.txt`.) The pairs gain more in clean rounds than with eight forms in the rounds (IQ2_S -9.1 against -6.9 %):
rux4's method note again. Production reads prompts as two halves of 256 inside 512 blocks (round19-tlp109: 158 RoutedUP
launches per 512 piece on card 2 = 79 per 256-token step), so the 256-token column is the one that counts.

Predicted (tools/gain6.py, 13 blocks of 256 x the layers of each format, card 2's rows): card 2's routed kernels per 3K
read 2157.2 -> 1949.6 ms (-207.6 ms, -9.6 %). With experts ~51 % of a 512 piece on card 2 (round19-tlp109) that is about
-4 .. -5 % of the 3K read if the cards stay balanced and the experts stay on the critical path; the six-card A/B
(section 3) is the real number.

Still on the table (the ledger): the picked forms run at 1.6-1.9x the ~38-41 clock issue floor (out/clk-x11.txt), so the
waits are not gone:
- RoutedUX's own code costs IQ2_S something before any prefetch: the XP 0 form (no prefetch: the pick's text) times
  +4.1 / +4.6 % on IQ2_S pairs (x9a-c) and +2.9 / +4.5 % on IQ2_S downs (x4a .. x10a), ~0 on the other formats. The
  machine code has about the same instruction count but more spill messages (`ss[` sends; uniform values spilled in
  the job prologue / epilogue, one fill per segment loop): IQ2_S down 26 against the pick's 3 (isa/x10), IQ2_S pair 44
  against 21, IQ1_S pair 42 against 30 (isa/x9); the shipped forms carry it (IQ2_S down xp1 xw2: 26, isa/x11). The
  source differs from RoutedUP only by the prefetch lambda and `if constexpr` lines that are off at XP 0, so the lambda
  is the suspect. rux6-2 experiment queued (b2/, `tools/bench/rux6_y.hpp`): RoutedUY = RoutedUP's text + the same
  prefetch through a static member function, runs y1pa (pairs) / y1da (downs) against the pick and Rux6Q.
- The x reads cost data-port time even when they hit L1: the port bench's L1 block reads give 14006 B/ns at 128
  registers and 7466 B/ns at 256 (out/run-port2a.txt, L1X) = 21.0 / 11.2 B per engine clock; a two-row form reads
  1 KB of x per (row pair, block, slot) = 512 B per (row-block, slot) = ~24 port clocks, a four-row form at 256
  registers 256 B = ~23 clocks. That is under the ~38-41 clock float floor (the two can overlap), but it is a floor of
  its own that only more rows per x read lower (rux4: R4 loses on IQ2_S / IQ1_S at 256 registers).
- IQ2_XXS gate + up (21 % of the routed time) gets nothing from prefetches; its larger wait is the decode
  (no decode: -36 %, out/run-d1a.txt).
- The same kernel compiles to the same code in different bench builds (isa/x10 against isa/x11: same instruction and
  spill counts, 3-4 lines differ on the 128-register forms; `tools/isacmp6.py`); the engine build's machine code of the
  rux6 forms is compared with the bench's (section 3) before the bench numbers are carried over.
- What remains of the x-read wait after the prefetch was not separated (the PDX diagnostics use XW 0, which is itself
  slow); a PDX form on XW 1 / 2 would split hit cost from miss cost.

Rule slip, 09:43: the first queue after the restart (x11s .. x9c) started ~80 s after the main thread's six.active went
away, not 180 s: q6.sh's six.lastseen was stale from 05:24 (its poller only runs inside q6.sh). No fault (journal clean
after every run). Fixed: runq.sh keeps a poller for its whole life (heartbeat `six.poller`), and q6.sh restarts the
180-s count from its own start when no poller is live.

## 3. Patch, engine build, six-card checks

- `rux6-1.patch` (`bash tools/mkpatch6.sh`: a fresh archive of the lab's HEAD engine in `tree/` (own git repo),
  `tools/plumb6.py`, the header + bench files from `b/`): 8 files (own_run_v41.cpp: OWN_RUX6 read + one stderr line
  "OWN_RUX6: ..." when on; backend_sycl_v41.hpp: the include; backend_sycl_v41_mt.inc: `bool rux6 = false` and the
  X6 dispatch before rux4's, only where `rux6_has`; new kernels/sycl_v41_routed_rux6.hpp; tools/bench/bench_rux6.cpp +
  rux6_cands.inc, rux6_tags.inc, rux6_diag.hpp). Rebased 10:31 on lab HEAD 0fe63f831 (tp110 sources: RUX5 default
  + qkv-1, OWN_QKV_SPLIT default on; first made on d07c2f594); `git apply --check` clean on a fresh archive and in the
  lab checkout (check only); the engine build's snapshot is this tree. OWN_RUX6 unset / 0: no code path
  changes (the X6 block is skipped; every other launch is untouched).
- Engine: `build_engine6.sh` (build109.sh's flags, snapshot `snap-eng/` of `tree/`, IGC machine code dumped to
  `isa/eng/`, tools/sendcheck6.py must PASS or the binary is renamed .UNSAFE; holds locks/build-rux6) ->
  `bin/own_run_v41_rux6`; log `logs/build-eng.log`. Try 1 (09:51:07, syntax ok in 44 s) was stopped at 09:58 by the
  main thread's HOLD_BUILDS (by design; log `logs/build-eng-try1.log`); try 2 queued 09:59 (waits for 180 s without
  HOLD_BUILDS / six.active / compilers); it started 10:40:01 in tg110's 200-s gap and holds locks/build-rux6 for ~25 min,
  so tg110's next section waits for it (qkv's build_engine.sh pattern: six-card gates wait for locks/ to empty; the
  build stops itself only on HOLD_BUILDS).
- Six-card checks: `gate6.sh g1` (systemd unit rux6-gate-...): `drive.sh` -> `six.sh` (one run per call; six.active
  taken only after 195 s absent and >= 210 s since six.active or any engine was last seen, idxsplit's rule) -> `one.sh`
  (trace / t3k / p3k modes). Traces with OWN_RUX6=1: h64, h256 (prompt 1 vs runs/ab1), t3k64, t3k256, t3k512 (3K vs
  runs/gm64/t3k_ref; 512 = production PX mode with tg109's PB); then, only if all five are identical, the 3K read A/B
  OWN_RUX6 = 0 / 1 / 1 / 0 (256 answers, PL + P5, answers vs runs/e52/p3kplain-ids.txt). Results: `runs/g1/summary.txt`.

- Engine build try 2 (`logs/build-eng.log`): compile exit 0 in 1545 s; sendcheck (v1) on its 2729 kernels: 1,001,157
  sends, FAIL 3 -> binary renamed .UNSAFE, exit 4 (10:06 + 1563 s). The 3 sends (`isa/eng/sendcheck-v1.txt`) are all
  IGC-made `load.ugm.d32x32t.a64 (1|M0)` loads in two production kernels, RoutePMRows<RowsPair<TokRows<HcFinishRows>,
  DenseRowsM<GemvQ8P<...>>>> (`isa/eng/OCL_asmfe12982192b51e41_simd32_entry_0099.asm` r124, line 17834; `..._0127.asm`
  r213 line 48398, r212 line 64704): no rux6 code, no inline asm. Each address register's offset 0 is written in an
  earlier block (e.g. `add (1|M0) r124.0<1>:q r8.3 + 1920` at line 14576), and the 64-bit values IGC wrote into the same
  register at .2 / .3 inside the send's block are other uniform pointers that later instructions read. The v1 rule
  (any 64-bit write at another offset in the block = FAIL) cannot tell that from the 04:09 pattern.
- sendcheck v2 (11:10, `tools/sendcheck6.py`; v1 kept as `tools/sendcheck6-v1.py`): such a send is "ERL" (not failed)
  only when BOTH the address bytes were written earlier in the kernel AND the other-offset 64-bit value is read by
  another instruction of the block. The 04:09 pattern (a misplaced address read by nothing but the send) stays FAIL.
  Checked: faulting forms isa/t1 / t2 / t3 FAIL 541 / 817 / 1058 sends, the same as v1; isa/d1, x9, x10, x11 PASS;
  isa/eng: `TOTAL 2729 files: sends 1001157 ok 469573 unk 9147 erl 3 FAIL 0 ... -> PASS` (`isa/eng/sendcheck.txt`); the
  6 rux6 RoutedUX kernels in the engine (entries 0030-0033 / 0030-0031 of two modules) have erl 0, FAIL 0. Binary
  renamed `bin/own_run_v41_rux6` (sha256 in `bin/own_run_v41_rux6.sha256`), logged in `logs/build-eng.log`.
- Gate launched 11:10 (unit rux6-gate-1110, `runs/g1/`; the two earlier "not run" summaries kept as
  `runs/g1/summary-try1.txt`, `summary-try2.txt`).

(results below as they come)

## Restart notes

- Nothing of rux6 keeps running across a host restart. Check `logs/build-eng.log` (last line "rux6 engine build exit N"),
  `isa/eng/sendcheck.txt`, `runs/g1/summary.txt` + `runs/g1/drive.txt`. A finished engine build is reusable; a
  half-done one: rerun `systemd-run --user --unit=rux6-engbuild-$(date +%H%M) --collect build_engine6.sh`.
- Gate: `systemd-run --user --unit=rux6-gate-$(date +%H%M) --collect -p StandardOutput=append:logs/gate.txt
  -p StandardError=append:logs/gate.txt /home/steve/dsv41-work/rux6/gate6.sh g1` (use a new run dir name if g1 holds
  partial results).

## FAULT 2026-11-13 04:09:13, card 1 (0000:23:00.0) -- my kernel, GPU work stopped

Run `x1a` (bin/x1, the first rux6 prefetch / L1-cached-x forms, out/run-x1a.txt, FAULT-x1a.txt): page faults
(Faulted Address 0x0 x55, 0x200010000 x21, 0x100000000000 x3), CAT errors, ccs engine reset, timed-out job, device
coredump (/sys/class/drm/card6/device/devcoredump/data); the bench died with DEVICE_LOST (exit 134).

Cause (found in the machine code, isa/t3): the inline-asm messages with ONE uniform address -- the transposed
prefetch `lsc_load.ugm.ca.ca (M1_NM, 1) %%null:d64x64t flat[%0]:a64` and the L1-cached x read `ld64ca`, both with
an `"rw.u"` address operand -- get their address placed in a sub-register (e.g. `mov r12.2:uq = addr`), but the
send reads its address from the start of the register (`[r12:1]` = r12.0:uq, which holds the group count). So the
messages went to garbage addresses. The per-lane forms (`"rw"`, (M1, 32), e.g. pf16 / pf8) are allocated at register
start (isa/t3: `add (16) r4.0:q`, `add (16|M16) r6.0:q`, `[r4:4]`) and are fine. port bench's ld64ca / ld64uc chase
loads have the same "rw.u" pattern and must not run either (bin/port3 was never built / run).

Health probe passed 04:12 (main thread; /home/steve/dsv41-work/faults/fault-20261113T0409-card1/). Fix and guard:
- No inline asm left anywhere in rux6: the prefetches use the SYCL prefetch extension (each lane names one address,
  IGC builds the message); the L1-cached x read form (XC) is dropped; the port bench's asm modes (SLMT, asm chase
  loads) are removed (its earlier SLMT number is void: same misplaced-address pattern, SLM does not fault) and the
  cache test uses annotated_ptr read hints (plain C++ loads).
- `tools/sendcheck6.py`: for every send of every kernel, the bytes it reads its address from must be written in its
  block, or no 64-bit value may have been written into that register at another offset (the 04:09 pattern). Checked
  on known builds: isa/t1, t2, t3 (the faulting forms): FAIL 541-571 sends per bad kernel; isa/d1 (70 kernels) and
  isa/port2: PASS (0 FAIL). v2 (11:10, section 3) exempts IGC's packed live pointers ("erl"); same FAIL counts on
  t1-t3. `bld6.sh` runs it after every build (dump always on) and renames a failing binary
  bin/TAG.UNSAFE; `r6.sh` / `q6.sh` refuse any binary without isa/TAG/sendcheck.txt = PASS, and a fault writes STOP.
- First run of each new form: one small shape, once (CHECKM=16 CHECK1=1 NOTPE=1 NOTIME=1), then the full queue.
