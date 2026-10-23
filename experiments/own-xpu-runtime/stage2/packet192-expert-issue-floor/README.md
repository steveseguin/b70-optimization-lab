# Packet192: expert-kernel issue-floor decomposition (lane-B micro, measurement only)

CPU preparation is complete; **no GPU ran, nothing is queued, no speed or model-output claim exists.**
One proposed lane-B micro row (`ops/lane-queue/proposed-p192-micro-B.txt`, PROPOSAL ONLY) measures
the two record expert kernels in three strata each and reports which bound binds. It is the
"single most informative measurement" of the expert kernel-floor study
(`../packet190-record-bundle-k3x/analysis/expert-kernel-study-20261023.md`, section C).

## Coordinator ruling (quoted)

> Expert kernel-floor study 2026-10-23: NO-GO on a +2 % expert kernel packet; the single informative
> measurement is an issue-floor decomposition of the two record expert kernels: DRAM-cold on packet100b's
> 384 real routes with the 512 MiB scrub, L2-warm (packet162b harness), and a non-exact no-load run with
> the row pointer aliased to one L1-resident slab. If warm ~ no-load (expected ~48 us), only the
> instruction diet can move the class; if no-load <= 0.75x warm, LSC prefetch is the candidate. Build it
> as packet192, measurement only, one lane-B micro window under 10 minutes.

## What is measured

The record k3x selection `exp-halfcache+down-tile16` (packet189 v5 -> packet190 record 62.345 tok/s;
the one-card record uses the same pair) resolves to exactly these two kernels, compiled here from the
record's own checked include closure (`native-pinned/`, 46 files, provenance in
`native-provenance.json`; `p90_expert.hpp` root digest `17c976c4...`, `p100_down.hpp` `329ff3d0...`,
byte-identical to packet103's record bundle; the checked mirror differs from the root only by the
p35 `prepared_submit`/`packet26::checked` launch form, which is what the record binary compiled):

| kernel | class | shape per launch | bytes read |
|---|---|---|---|
| `p90exp::Kernel<IQ2_S,2560,WG64,Prefetch=false,Wide=true>` | gate/up (both streams, 10 routed experts) | 2 x 6,400 rows x K2560, 840-B E1 rows | 10.75 MB |
| `p100::Kernel<2>` | down (tile16) | 25,600 rows x K640, 360-B rows in 16-row tiles | 9.22 MB |

Strata per kernel (`micro.cpp`):

* **(a) cold** - packet100b's 384 real routes (`lineage-inputs/routes-p100b.json`, derived from
  `packet100b-route-capture/evidence/routes.bin`, fixtures 1/16/32/64 of every layer, both ranks and
  prompts), full 512-expert synthetic banks (the down bank is packet100's generator, seed 100: byte-
  identical to packet100b's micro bank, so its real down-tile16 datum 46.04 us is a cross-check), a
  512 MiB device scrub before **every** launch, 20 launches per route, two passes (15,360 timed events
  per kernel per pass).
* **(b) L2-warm** - the first real route's ten experts repeated without a scrub (10.75 / 9.22 MB
  footprint, inside the 24 MiB L2), 5 untimed warm-ups then 200 timed launches per pass; for gate/up
  additionally packet162b's **real** rows (`packet162-iq2-lookup/build/micro-inputs/layer{0,24}.bin`,
  read in place) with the same 200 x 2 protocol, so the 48.3 us packet162b datum is reproduced by
  the same harness.
* **(c) no-load** - `p192_noload.hpp`: the identical kernel bodies with every row address aliased into
  one 16-row slab (`(expert*rows+row) & 15` -> bank rows 0..15; 13.4 KB per stream for gate/up,
  5.8 KB for down), so every weight load is an L1/L2 hit and the instruction stream is the production
  K loop plus one AND per work-item. **Not exact by construction; `exactness_claim: false`,
  `exact: false`, outputs discarded.** An alias self-test (16-row routes of expert 0, where the alias
  is the identity) must be byte-identical to production on CPU and on the device.

Per-launch device timings come from the profiling queue (`command_start`/`command_end`), as in
packet100 and packet162b. Device memory is phased (gate/up phase, then down) so the peak is
**1,108,913,492 B < 1.2 GB** (scrub 536,870,912 + banks 550,502,400 + real rows 21,504,000 + outputs);
no model load. Host admission 10 GiB (8 GiB reserve + 2 GiB scratch; the binary itself stages 3.4 MB
chunks, 30 MB fixtures, 21 MB real rows); whole-host admission applies because the window driver
stops the owner's endpoints. Duration estimate (from packet100b's measured 0.92 ms per scrub+launch
cycle): cold 2 x 14.2 s, warm/no-load ~2 s, exactness passes ~5 s, bank generation/upload ~20 s,
start-up ~10 s: **~65 s, expected 30-194 s, watchdog 1,800 s**, 64 MiB of writes.

## Exactness gate (before any timing)

The GNU host twin (`-DOWN_RT_HOST_ONLY` build of the same kernels, the engine's CPU oracle form)
computes the expected output/status/error bytes for all 384 cold routes (25,684 B gate/up, 51,244 B
down each), the warm route and the two real shapes: `build/fixtures/` (29.6 MB, digests sealed in
`evidence/fixtures.json`). The Intel host twin verifies every fixture byte (GNU/Intel byte rows
identical). On the device every exactness stratum must be byte-identical to those fixtures
(`native_summary` refuses the window otherwise) and the analyzer withholds the verdict on any
difference. The no-load stratum is excluded from exactness by construction.

## Row

| lane | card | job | proposal | expected | watchdog | device | host | writes |
|---|---|---|---|---|---|---|---|---|
| B | 2 (`0000:43:00.0`) | `packet192-expert-issue-floor-micro-B` | `ops/lane-queue/proposed-p192-micro-B.txt` (mirror `proposals/`) | ~65 s (30-194 s) | 1,800 s | 1,108,913,492 B peak | 10 GiB available | 64 MiB |

The runner is packet162b's `run_micro.py` (frozen v4-lanes reservation, drain permit, fault review,
single-card FD census, supervisor, graceful stop) with this packet's binary, argv, gates and report.
Output `evidence/issue-floor-B1/` must not exist. No retry, no second process, no reseal after a
result exists.

## Report (`s192_report.py`, `evidence/issue-floor-B1/analysis.json` + `s192_report.md`)

Per kernel: cold, warm, no-load medians (and p10/p90, n, per-pass medians), ratios warm/cold and
no-load/warm, the decomposition (DRAM = cold - warm, load latency = warm - no-load, issue = no-load),
us per layer-equivalent (one launch of each kernel per layer; class = gate/up + down vs the packet110
copy floor 37.4 us; the activation launch 5.42 us is separate), cross-checks against the parent
datums (packet162b 48.3 us warm real, packet100b 46.04 us cold tile16), and the verdict per the ruling:

* warm ~ no-load within 10 % -> **"instruction-issue bound: only an instruction diet can move the class"**
* no-load <= 0.75 x warm -> **"load-latency exposed: LSC prefetch is the candidate"**
* otherwise -> **"mixed"**

plus what a follow-on micro packet must beat: `exp-diet` and `exp-act-epilogue` (gate/up; the
epilogue counted against gate/up + the 5.42 us act launch) and `down-diet` (down): candidate
<= 0.85 x production in both A/B orders and every stratum (the packet100 gate), stated as absolute
cold and warm bars in us. Kill rules (verdict withheld, never ratio-corrected): any byte difference in
(a)/(b); cold/warm control disagreement > 10 % between the two passes; any stratum with p90/median
> 1.5 (host disturbance). The analyzer refuses CPU streams and the parent packets' device streams
(different schema) and was tested on them (`test_report.py`, 8 tests).

## Gates (all CPU, in order; `nice -n 19 taskset -c 8-15,24-31 python3 -B <script> </dev/null`)

1. `prepare_native.py` - include closure pinned, record headers verified.
2. `build_micro.py` - three binaries, 0 warnings, closure inside the packet (`evidence/build.json`).
3. `prepare_inputs.py` - routes JSON + parent provenance (`lineage-inputs/`).
4. `rehearse_cpu.py` - host twins at production shape (fixtures), GNU = Intel, alias self-test, the
   real device ELF with the real argv in the shared Landlock preparation sandbox, 7 parser refusal cases
   (`evidence/cpu-rehearsal.json`, `evidence/fixtures.json`).
5. `test_report.py` - analyzer tests incl. the real parent summaries (`evidence/analysis-tests.log`).
6. `admission.py` - device/host/storage/duration (`evidence/admission.json`).
7. `package_rows.py` - proposal (mirror + ops copy) then `cpu_seal.py --seal` (plan after seal).
8. `check_queue_rows.py` - real `run_micro.py --plan`, private-copy `lanequeue.py plan --lane B`,
   `ops/rehearse_entry.py --report --json`, live pin guard (`evidence/check-queue-rows.json`).
9. `final_checks.py --ready` - receipts, proposal = mirror, lane state observed; writes
   `READY-FOR-DEVICE.json` LAST, then classifies every pin (0 cross-packet mutable).

Parent files are read in place and verified by digest at every plan/run (`lineage-inputs/parent-
inputs.json`); none is copied or pinned. See `DO-NOT-REPEAT.md`, `RETENTION.md`, and
`notes/2026-10-23-packet192-expert-issue-floor.md`.
