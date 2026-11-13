# tp105 readiness survey (2026-11-12, read-only)

Base tree: `/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine/src/stage2/packet3`
= tp104 sources (commit 091640933; later commits 05b3b5e69 / 2688cb33e touched notes and data only).
Rule: bit-identical traces or opt-in switch. All apply checks below are dry runs (`git apply --check` /
`patch --dry-run`); nothing was applied, built or run on a GPU.

## Summary

| item | verdict | patch | apply check (current tree) | measured gain | missing |
|---|---|---|---|---|---|
| fl-1 | READY, opt-in `OWN_FL=3` | `fl/fl-1.patch` | clean (offsets 15-91) | bench: FFN -2.4 us + down -0.6..-0.8 us per layer, ~0.13 ms per step predicted (~1.3 %); 0 differ in 4,060 buffers | shipped-form bench (q5) and final syntax check never ran; no engine run |
| xperm-4 B (xorP) | READY if gate traces are identical; compile flag `-DOWN_R2_XORP=1` | `xperm/xperm-4.patch` | clean (no offsets) | bench copies: checks -1.7..-6.5 % per launch, one-token -0.1..-1.8 us; ~-70 us per step, ~-115 us per check; all PASS | the patched production file never compiled or run (x4 queue died at 01:07); trace identity is the proof |
| xperm-4 A | READY, opt-in `OWN_U3_NOPAIR=1` | same | same | -1.0..-2.1 % per launch, ~-20 us per check | gate arm |
| other ~10 butterfly sites | NOT STARTED | probe code only (`xperm/p5/y`, `xperm/x4`) | n/a | none | everything |
| attn sw | READY to compile as opt-in `OWN_MT_SW` (1 checks, 2 one-token, 3 both) | `attn/sw/sw.patch` | clean (no offsets) | bit 2: card-3 bench, 0 differ, ~69 us per step predicted (~0.7 % plain); bit 1: no new data (table from pace-1 / pace-2 benches; 3 shapes empty) | sw benches and ENTRY bitwise builds never ran; no prediction for bit 1 |
| pb256 rux2 | NOT READY | none | n/a | none (CPU floors only) | everything; probe build failed; PF prefetch looks like the closed L1 idea |

## 1. fl (fold launches, fl-1)

**Verdict: READY as an opt-in switch (`OWN_FL=3`, default off), with one caveat: the final patch has never been
compiled or run on a GPU. The tp105 build is its compile check. Gain is ~0.13 ms per one-token step (~1.3 %),
not the 0.5 ms first predicted.**

What it changes (`/home/steve/dsv41-work/fl/design-fl-1.md`): one-token tp steps only (tp_phase cases 3 and 4).
- bit 1: the FFN pre-norm and the stream mix's 25 dot rows (`SkNormDotsW<8>`) folded into the router launch
  (`FlNormK<5120,16,25,8,0,NoRows,FlH16Rows<160>>`; every router work-group forms the norm itself). -40 launches.
- bit 2: `MoeCombineA` folded into the shared expert's down rows (`FlDownComb<GemvQ8P<72>|GemvQ5KP<9>,6>`). -40 launches.
- Rejected after bench (all slower): the "K4" attention folds A1 / A1b / A2 (pre-norm into q_a+kv, q_a/kv norms into
  q_b) +0.8 to +13.6 us per layer; every L1/L2/L3 prefetch and register-preload variant. So the "~0.5 ms" idea is
  mostly dead; only the two FFN-side folds ship.
- Not active in: checks (2-6 tokens), prompt blocks, `OWN_XTAIL=1` (bit 2 off), `OWN_K7` FFN site (fl steps aside),
  `OWN_SMALLK_DOTS != 8`, `OWN_NORM_DOTS=0`.

Files (patch paths are relative to `experiments/own-xpu-runtime/engine`):
- `planning/dsv41-fixtures/own_run_v41.cpp` (parses `OWN_FL`, 0..3)
- `src/stage2/packet3/backend/backend_sycl_v41.hpp` (option, `fl_f1` / `fl_d1_ok` / `fl_d1`, two call sites)
- `src/stage2/packet3/kernels/sycl_v41_fl.hpp` (new file)
With `OWN_FL` unset, `fl_f1` and `fl_d1_ok` return false and the old launches run unchanged.

Patch: `/home/steve/dsv41-work/fl/fl-1.patch` (23:58 on 11-11; made against src102 = 40f9b9549). The new kernel file in the
patch is byte-identical to `fl/tree/src/stage2/packet3/kernels/sycl_v41_fl.hpp`.

Apply check against the current tree (dry runs only):
- `git -C /home/steve/b70-optimization-lab apply --check -v --directory=experiments/own-xpu-runtime/engine fl-1.patch`:
  clean. Every hunk applies; offsets are 15 to 91 lines. No fuzz.
- `patch --dry-run -p1` from `experiments/own-xpu-runtime/engine`: clean, same offsets.
- The call-site context did not change between tp102 and tp104 (tp103/104 touched pace, px and the prompt path).

Measured (card 1, one-card bench `fl/bench_fl.cpp` + exploratory header `fl/bench/sycl_v41_fl_x.hpp`, real rows of
layers 2 and 30 in card 2's slices, 6 weight copies so reads are cold; logs `fl/logs/out-r1.txt`, `out-t1.txt`,
`out-t2.txt`, `out-t2b.txt`, `out-t3.txt`):
- FFN chain F1 (bit 1): 24.6 -> 22.2 us per layer (layer 2, Q8_0), 25.3 -> 22.8 (layer 30); t3: 24.9 -> 22.5.
- shared down D1 (bit 2): 5.0 -> 4.2 us (layer 2), 5.6 -> 5.0 (layer 30).
- Prediction for card 2: bit 1 ~96 us + bit 2 ~30 us = ~0.13 ms per one-token step (~1.3 % of ~9.9 ms). The design note
  itself says this is under the 0.15 ms bar; it is offered because it is small and opt-in.
- Exactness: every output word of every stage compared, including forced chain fallbacks (norm scale ~1e-15 from a
  float midpoint). r1 800 buffers, t1 600, t2 2,336, t2b 1,460, t3 4,060: 0 differ, PASS in all. No fault lines.
- Register mode (ISA dumps `fl/isa/b3`): the F1 form (`FlDense<2,160,0>`) and both `FlDownComb` forms are 128-register
  kernels, so no extra ~1.7 us mode switch. Only the rejected preload forms went to 256.

Missing:
1. The shipped forms were never run. Queue q5 (`fl/chain5.sh`: build bs1 + `bench_fl_ship.cpp` run ts1, which includes
   the real `sycl_v41_fl.hpp` and `FlH16Rows<160>`) logged "go start 00:39:16" and nothing after. There is no bin/bs1.
   The numbers above come from the exploratory equivalents (same row bodies by design, but a different source file).
2. The final engine patch was never syntax-checked. `syn-s1` (23:25, exit 0) ran before the last backend/kernel edit
   (23:57). `syn-s2` (`chain6.sh`) never ran.
3. No engine run at all: no traces, no speed.
Before or at the six-card gate, the design note's arms (`design-fl-1.md`, "Gate arms"):
- h1 traces with `OWN_FL=3`, `=1` and `=2`: TRACE_IDENTICAL + IDS40_SAME
- h5 / h64 / h256 with `OWN_FL=3`: IDS40_SAME
- 3K trace b256 with `OWN_FL=3`
- h1 with `OWN_K7=3 OWN_FL=3`
- one guessing run with `OWN_FL=3`
- plain x2 with and without the switch (alternated)
- one card-2 profile showing `SkNormDotsW` 77 -> 37 per step and `MoeCombineA` 40 -> 0
Optional if a card is free before the build: run q5 (`fl/chain5.sh`, ~3 min on one card).

## 2. xperm (xorP butterfly, xperm-4)

**Verdict, two parts in one patch:**
- **(B) xorP, `-DOWN_R2_XORP=1`: READY to compile into tp105 on the condition that the gate's traces come out
  byte-identical.** It is a compile-time switch (default 0 = the code exactly as today). Compiled in, it changes the
  default code path, so the gate is its exactness check, the same way xperm-3 went in for tp103. The patched
  production file itself has never been compiled or run (see "Missing").
- **(A) "no pair code below 16 tokens", `OWN_U3_NOPAIR=1`: READY as a runtime opt-in (default off).** It is a separate
  arm, worth ~-20 us per check.
- **The ~10 other butterfly sites: NOT STARTED beyond probe code.** Nothing was built or run. Not for tp105.

What it changes (`/home/steve/dsv41-work/xperm/README-ledger.txt`, sections 11 and 12):
- B: the three lane-sum butterflies in the routed expert kernels become five `permute_group_by_xor` adds (xor 16, 8, 4,
  2, 1) instead of `select_from_group(lane ^ w)`. The sites are `R2_ROWS_END`, `R2_PAIR_SCHED`'s `red`, and
  `RoutedU3`'s sum. IGC recognises the chain as a sub-group reduction and lowers it to halving adds. That is the
  butterfly's own tree at lane 0, operand order included (ISA `xperm/isa/l34-p5` entry_0011).
  - Caveat in the patch comment: the bits rest on that IGC lowering. Another compiler order would change them, and
    trace identity would catch it.
- A: the IQ2_XXS (NB 20, 9) and IQ2_XS (NB 20, 9) expert-major check kernels with nsl < `PAIR_NSL` (16 tokens) are
  instantiated as `RoutedU3<..., PAIRS=false>`. The pair branch never runs below 16 tokens, so the sums are the same.

Patch: `/home/steve/dsv41-work/xperm/xperm-4.patch` (00:52 on 11-12; repo-root paths; made against tp104 = 091640933;
the tree is `xperm/p5/x`, and its `routed_r2.hpp` matches the patch line for line). Files:
- `src/stage2/packet3/kernels/sycl_v41_routed_r2.hpp` (`R2_XSUM` macro + 3 sites)
- `src/stage2/packet3/backend/backend_sycl_v41_mt.inc` (`u3_nopair` + the `XN` selection)
- `planning/dsv41-fixtures/own_run_v41.cpp` (`OWN_U3_NOPAIR` parsing)

Apply check against the current tree (dry runs only):
- `git -C /home/steve/b70-optimization-lab apply --check -v xperm-4.patch` (no `--directory` needed): clean, no offsets.
- `patch --dry-run -p1` from the repo root: clean.
- Build note: tp104's flags are `-DOWN_R2_TAB_COPY=1 -DOWN_R2_TAB_COPY_XXS=1` (`dsv41-work/build104.sh`). tp105 must add
  `-DOWN_R2_XORP=1` to get B.

Measured (card 5, one-card benches, all "no fault lines"). Outputs are in `xperm/out/`.
- Checks, `RoutedU3` copy forms in `src/l34_probe.hpp` (`run-p4-*`, `run-p5-*`, `run-p6-*`; every run PASS, 0 differ,
  over random ids M 1-6 and 15, real 3K picks M 2-6, wide-exponent x and real GGUF rows). Per-launch change at
  M2 .. M6:

  | kernel | change, M2 .. M6 |
  |---|---|
  | IQ2_S g+u | -1.7 .. -2.7 % |
  | IQ2_XXS g+u (A+B) | -2.9 .. -4.9 % (e.g. M3 62.04 -> 59.38 us) |
  | IQ1_S g+u | -0.9 .. -2.8 % |
  | IQ2_S down | -3.3 .. -4.3 % |
  | IQ3_XXS down | -2.7 .. -4.0 % |
  | IQ2_XS down (A+B) | -5.8 .. -6.5 % |
  | IQ2_XXS down (A+B) | -4.9 .. -5.9 % |

  A alone: IQ2_XXS g+u -1.4 .. -2.1 %, IQ2_XS down -1.5 .. -2.1 %, IQ2_XXS down -1.0 .. -1.6 %.
- One-token step: `xdq.hpp` copy forms built with `XD_XORP=0` and `=1` (`bin/bench_xdq_xdq8a` / `xdq8b`; outputs
  `out/run-xdq8a-x1/x2.txt` and `run-xdq8b-x1/x2.txt`). 8 PASS / 0 FAIL in every run. Per launch, warm: -0.15 to
  -1.80 us; cold: -1.74 to +0.47 us.
- Prediction (card 5 launch counts from tg101 timelines):
  - ~-70 us per one-token step (~0.7 %; warm -83, cold -60)
  - ~-115 us per check (~0.7 % of a 16.2 ms check cycle; -78 at M2, -247 at M5)
  - A adds ~-20 us per check

Missing:
1. The patched production file has never been compiled or run. Every timing and bitwise result above comes from bench
   copies (`l34_probe.hpp`, `xdq.hpp`) that use the same expression. Queue `x4/chain_builds.sh` would have closed the
   gap: xv1 = `bench_xdq.cpp` built on `p5/x` with `-DOWN_R2_XORP=1`, comparing the patched production kernels against
   the copies, plus host syntax checks `syn def` / `syn xorp`. `out/x4-builds.log` stops at "01:07:12 start x4a"
   (host reset at 01:14), and `out/x4-runs.log` is empty. So the risk is that the same reduction is lowered
   differently in the production instantiation.
2. Gate arms:
   - The full trace set with `-DOWN_R2_XORP=1` against tp104 (prompt-1 traces with checks, 3K traces, guessing logs):
     every one must be byte-identical. If any differs, rebuild without the flag; no other fix in tp105.
   - `OWN_U3_NOPAIR=1` on the guessing traces and runs (checks are its only shapes).
   - Speed: plain and guessing, alternated x2.
3. Other sites (not for tp105):
   - The ledger's list of unmeasured sites: `sycl_v41.hpp` 1543, 1884, 3924, 3970, 4006, 5602, 5904, 6174, 8583 and
     `sycl_v41_routed_rux.hpp` 206.
   - Probe code exists in `xperm/p5/y` (bench-only mask `OWN_XORP_SITES`, bits 1 / 8 / 16 / 32 / 64 / 512, plus 2048 =
     a bit-reversed form for the dense rows' `sg_tree32`) and in `xperm/x4/bench_x4.cpp` (Q2_K `RoutedQ2KF` + dense
     `GemvQ8P` tree32). None of it was built or run.
   - The tree32 form uses a different pairing (bit 0 first) and needs its own bitwise proof.

## 3. attn (check-form re-pick + M=1 128-register forms, `OWN_MT_SW`)

**Verdict: READY as an opt-in switch (`OWN_MT_SW`, default 0) in the sense that it is safe to compile in: with the
switch unset the default path is logically unchanged (checked below). But neither bit has its own GPU check yet, and
bit 1 has no gain estimate at all. Treat bit 2 as a real arm (~0.7 % plain predicted) and bit 1 as speculative.**

What it changes (`/home/steve/dsv41-work/attn/sw/README.txt`; picks in `attn/sw/patch/picks_sw.py`):
- bit 1, checks of 2-6 tokens: one form table for q_b, output-a, output-b, shared down, q_a + kv, and shared gate + up.
  Forms are picked by bench time + 1.68 us for every 256-register launch, the engine's own form included. This is the
  tg103 lesson: each 256-register launch among 128-register ones costs two register-mode switches of ~0.84-0.94 us.
  It replaces the `OWN_MT_PACE` tables (pace-1 / pace-2) at 2-6 tokens. Shapes with no pick fall back to ws_rows or the
  engine's forms.
- bit 2, one token: the 16-head cards' (2 and 5) q_b Q8_0 and output-a Q8_0 / Q6_K rows in 128-register `PaceKN` forms
  through `pace1_rows`. This supersedes `attn/pace1t/pace1t.patch` (`OWN_PACE1`).
- 3 = both.

Patch: `/home/steve/dsv41-work/attn/sw/sw.patch` (00:58 on 11-12; made against tp104 = 091640933; apply it in the engine
directory). Files:
- `src/stage2/packet3/kernels/sycl_v41_pace.hpp`
- `src/stage2/packet3/backend/backend_sycl_v41.hpp`
- `src/stage2/packet3/backend/backend_sycl_v41_mt.inc`
- `planning/dsv41-fixtures/own_run_v41.cpp` (parses `OWN_MT_SW`, masked to 0..3)

Default-path check (read): the three condition rewrites in `_mt.inc` and the two in `sycl_v41_pace.hpp` reduce to the
old conditions when `g_pace_sw == 0`. Only the order of side-effect-free tests changes. The new one-token branches in
`backend_sycl_v41.hpp` are guarded by `g_pace_sw & 2u`.

Apply check against the current tree (dry runs only):
- `git -C /home/steve/b70-optimization-lab apply --check -v --directory=experiments/own-xpu-runtime/engine sw.patch`:
  clean, no offsets.
- `patch --dry-run -p1` from `experiments/own-xpu-runtime/engine`: clean.

Measured:
- bit 2 (one token): card 3, `attn/pace1t/bench_pace1t.cpp`, binary `pace1t/bin/p1a`, output
  `attn/pace1t/logs/out-p1.txt` (00:37 on 11-12). Every form 0 differ, riders included. The chosen picks:

  | rows | today, us | pick, us | launches per step |
  |---|---|---|---|
  | q_b Q8_0 (`PaceSQ8N<40,1,1,1,1>`, 128 registers, fit) | 22.40 | 21.98 | 27 |
  | output-a Q8_0 (`PaceSQ8N<128,1,2,1,1>`, 128 registers, spread) | 17.08 | 16.46 | 27 |
  | output-a Q6_K (`PaceSQ6N<16,1,1,1>`, 128 registers, spread) | 18.44 | 15.31 | 13 |

  q_b Q6_K has no 128-register win and is kept. Rough prediction on cards 2 / 5: ~11 + 17 + 41 = ~69 us per one-token
  step (~0.7 % of ~9.9 ms; my arithmetic, since predict.py never ran). The 16-head cards are last at the output-a
  exchange, so most of this should reach the step.
- bit 1 (checks): no new measurement. The table reuses older bench data: pace-1 (`attn/pace/logs`, 635 compares, 0
  differ), pace-2 (`attn/pace2/logs`, 720 compares, 0 differ) and tools/repick2. Each pick is bit-exact in its source
  bench. Three shapes are still empty placeholders waiting for bench_sw round 1, so they take no pick:
  - `('qb', 8, 4096)`
  - `('oa', 6, 2048)`
  - `('oa', 6, 1024)`

Missing:
1. Nothing in `attn/sw` was built or run:
   - `sw/bin/` is empty, and `logs/buildq-sw1.out` is empty (chain1 = bench_sw round 1).
   - chain2's ENTRY builds `sw2e` / `sw1te` never started. Those benches compile the patched header's real selection
     code and memcmp it against today's forms; they are the patch's own bitwise check.
   - `tools/predict.py` (per-check / per-step prediction) never ran.
   - README results are still "@@RESULTS@@".
2. The engine has never compiled this patch. tp105 would be its first compile.
3. Gate arms:
   - prompt-1 traces with `OWN_MT_SW=1`, `=2` and `=3`, including checks at 2-6 tokens and guessing logs. These double
     as the bitwise check that the ENTRY benches never gave.
   - a check timeline with `OWN_MT_SW=1`, to count the mode switches (expect fewer 256-register launches than tg102b's
     54-60 at 2 tokens and 140-163 at 5).
   - a one-token timeline with `OWN_MT_SW=2` (q_b / output-a on cards 2 / 5).
   - speed: plain with `=2` and guessing with `=1` / `=3`, alternated x2.

## 4. pb256 / rux2 (prompt expert kernels, rux-2)

**Verdict: NOT READY. Nothing to ship. Work had barely started: there is no patch file, no measurement, and an empty pick
table.** px-512, px-move and engbench (also in pb256/) are already in tp104, confirmed below.

What it was meant to change (`pb256/rux2/tools/edit_rux2.py`, 01:06 on 11-12):
- An opt-in `OWN_MT_RUX2=1` that re-picks the prompt expert kernels' forms per format (`RuxPick2<type, NB, 6>`: R, E,
  XA, G, PF) from a bench ledger.
- A new `PF` template parameter on `RoutedUT` (`pb256/rux2/c/src/stage2/packet3/kernels/sycl_v41_routed_rux.hpp`): before
  each job, prefetch the sub-group's next job's weight rows to L3 (PF 1) or L1 + L3 (PF 2).
- `rux2/b` = HEAD's header, byte-identical to the current tree's `sycl_v41_routed_rux.hpp`.

State:
- `edit_rux2.py`'s `FORMS = {}` is empty ("filled from the ledger (out/ledger-*.txt)"). No ledger file exists, so as
  written it would make `OWN_MT_RUX2=1` run exactly RuxPick's forms (a no-op), plus the unused PF code.
- The only bench build, `logs/build-probe1.log` (23:31 on 11-11: fmt 0x1e7, VarShip + VarSP variants,
  `-DRUX2_MT6 -DRUX2_NOCHECK`), failed: "exit 1 in 6 s", with no error text captured. `rux2/bin/` is empty; no bench ran.
- The only result is a CPU floor analysis, `pb256/rux2/out/floors.txt`. At blocks of 256 the expert launches cost
  ~2.43 s per 3K read in the engine, against an FP-operation floor of 0.86 s and max(FP, weights, port) 1.66 s. That
  leaves room (~0.4 s was the earlier lever estimate in `pb256/README-overlap.txt`), but the floor says nothing about
  which form gets there.
- Warning for whoever resumes: the PF idea is the same mechanism the xperm helper closed for the one-token and check
  expert kernels ("L1 prefetch ... bit-identical in every form, slower in every form", ledger sections 8-9; strategy
  scoreboard). Expect it to lose here too unless the prompt kernels are memory-idle, which the floors do not show.
  `README-overlap.txt` line 420 also asks that the routed gate / up forms stay 128-register or PX's sites 3 / 4 move.

Apply check: no patch exists, so nothing to check.

Already in tp104 (reverse dry runs: `git apply --check -R --directory=experiments/own-xpu-runtime/engine` of
`pb256/pxmove/px512-plus-move.patch` and of `pb256/px512/px-512.patch` both succeed; the tree has 10 / 18 references to
`OWN_PX_BIG` / `OWN_PX_MOVE` / `OWN_PX_WGS` in `own_run_v41.cpp` / `_mt.inc`):
- px-512 (`OWN_PX_BIG=1` + `OWN_PX=1`). tg104c: all traces identical, 3K read 5.56 s vs 5.71 (-2.8 %), w8 / w4 worse.
  It stays opt-in. Blocks of 300 (halves of 150) reset the host 2 / 2 and are banned. Whether PX-style card-to-card
  read traffic is safe and fast after the iommu=pt reboot is what tg105pt measures (strategy notes, 11:10 entry). So I
  would not flip px-512 to default in tp105 before tg105pt reports.
- px-move (`OWN_PX_MOVE`, `OWN_PX_WGS`): ~0 in tg104. Off.
- engbench (`pb256/engbench/engbench.cpp`): a one-card measurement tool (it found that the one-launch overlap was a
  queue-profiling artefact); nothing to ship.

## Combined check of the ready patches

All three patches stacked in one dry run, in three orders (fl / sw / xperm-4, xperm-4 / sw / fl, sw / xperm-4 / fl):
`git apply --check --directory=experiments/own-xpu-runtime/engine fl-1.patch sw.patch <xperm-4 with repo-root paths
stripped>` succeeds every time. The stripped copy is a scratch file; the original patch is unchanged. They share
`own_run_v41.cpp`, `backend_sycl_v41.hpp` and `_mt.inc` but touch different regions.

Suggested tp105 = tp104 + the three patches + `-DOWN_R2_XORP=1` added to the build flags.
- `OWN_FL`, `OWN_U3_NOPAIR` and `OWN_MT_SW` stay off by default.
- xorP is the only default-path change. Its first gate stage is trace identity against tp104; if any trace differs,
  rebuild without the flag (the switches are unaffected).
- None of the three patched sources has been compiled in its final form, so the tp105 syntax check is their first
  compile check.
