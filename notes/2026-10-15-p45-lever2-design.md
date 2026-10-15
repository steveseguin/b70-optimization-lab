# Packet45 lever 2 design: expert bodies inside the selected P39 fusions

2026-10-15. **Design only; patch not applied; no build or device execution.**
Base: SPEED7 `4af439d0e` (runtime source also at analysis HEAD `1f871acbf`).
The running packet45 tree and packet44 tree were read only, with `python3 -B`.
Only this note and [the unapplied implementation patch](../patches/packet45-speed8-expert-kernels.patch) were written.

The next test is two existing lossless expert bodies, composed with the checks
already fused by P39: packed IQ2 gate/up, and bank/vector IQ4 down. This is not a
proposal to disable P39. Current fused down is **faster than bare bank down**.
The new bodies must win a fresh, direct fused-versus-fused K2 comparison before
use, and remain subject to the existing full device exactness chain.

## Calibration: SPEED7's predicted copy saving did not appear

The earlier forecast of **0.225 ms/hit and 0.810 ms/miss** from batching was
wrong. Its assumed 0.7 ms capture/restore reduction was not a measured copy
kernel duration. It converted rectangular grid waste into time without proving
that inactive lanes were costly. Withdraw that assumption and assign **zero
central time saving to padded-slot removal**.

Sources are the four retained `build/speed{6,7}-c4096-dr1-s23-cards{01,23}-gpu/WS`
windows under packet45, especially `run/repeat-1/*/{receipt.json,rank*/timings.jsonl}`.
The [existing read-only analyzer](p45_after_speed6_analyze.py), lines 149–274,
aligns rank commands, draft rows and per-position timings. Each phase below is
the median of the twelve request means. Overlapping phase rows are not additive.

| Phase, ms | S6 cards 0–1 | S7 cards 0–1 | S6 cards 2–3 | S7 cards 2–3 |
|---|---:|---:|---:|---:|
| Reported hit cycle | 22.384 | 22.429 | 22.321 | 22.320 |
| Reported miss cycle | 38.873 | 39.024 | 39.080 | 38.993 |
| Hit draft command | 2.787 | 2.796 | 2.765 | 2.768 |
| Hit rank-0 speculative HALF | 19.367 | 19.420 | 19.388 | 19.387 |
| Hit rank-1 target HALF | 19.190 | 19.193 | 19.072 | 19.078 |
| Hit observation after rank-1 completion | 0.300 | 0.327 | 0.322 | 0.339 |
| Miss ROLLBACK command | 1.610 | 1.658 | 1.628 | 1.643 |
| Miss rank-0 redo HALF | 17.591 | 17.564 | 17.594 | 17.582 |
| Miss next rank-0 speculative HALF | 19.342 | 19.414 | 19.447 | 19.421 |
| Miss next rank-1 target HALF | 19.370 | 19.406 | 19.522 | 19.496 |
| Miss observation after rank-1 completion | 0.132 | 0.173 | 0.092 | 0.147 |

Matching speculative and redo HALF **at the same position**, positions >=100,
is a closer capture proxy than subtracting unrelated medians:

| Speculative minus redo, median ms | S6 0–1 | S7 0–1 | S6 2–3 | S7 2–3 |
|---|---:|---:|---:|---:|
| Complete rank command | 1.7815 | 1.8084 | 1.7820 | 1.8040 |
| Outside reported rank busy | 0.6822 | 0.7078 | 0.6918 | 0.7013 |
| Forward wait | 1.0619 | 1.0508 | 1.0543 | 1.0516 |
| Forward prepare + enqueue + wait | 1.0808 | 1.0877 | 1.0829 | 1.0831 |

These remain proxies: corrected tokens can route differently. No retained field
isolates a capture batch's GPU duration, capture submission cost, or its exact
contribution to readback drain. Claiming an exact bandwidth bottleneck would
exceed the evidence.

Paired per-prompt S7-minus-S6 median cycle changes are **+0.0635/+0.1038 ms**
hit/miss on 0–1 and **+0.0210/+0.0198 ms** on 2–3. Per-prompt miss deltas range
from -0.204 to +0.295 ms and -0.238 to +0.205 ms respectively. There is no
consistent improvement to explain away as a different aggregate median.

| Snapshot operation, 23/25 dr1 | Useful payload, unchanged | S6 grid byte slots | S7 grid byte slots | S6 → S7 submissions |
|---|---:|---:|---:|---:|
| Capture | 48,332,354 B / 46.0933 MiB | 183,303,680 | 54,000,160 | 31 → 32 |
| Redo restore | 18,730,562 B / 17.8629 MiB | 91,028,992 | 21,505,216 | 30 → 32 |

**Grid byte slots are not bytes transferred.** `strict_snapshot.hpp:29–31`
checks `off+j < item.bytes` before either load or store. Padding exits without
moving those bytes. Useful read/write traffic, descriptor preparation and owner
work remain. Launch count increased. The last cumulative snapshot receipts on
each pair agree on 1,525 captures / 73,706,839,850 useful bytes and 326 restores /
6,106,163,212 useful bytes; capture submissions increase 47,275→48,800 and
restore submissions 9,780→10,432. Private allocation remains 103,607,362 B.

Capture overlaps rank 1 and drains at the next rank-0 readback
(`rank.hpp:114–121`). However, restore explicitly drains synchronously
(`strict_snapshot.hpp:238–244`), and the controller waits for ROLLBACK plus redo
(`native_controller.hpp:96`). Restore did not improve either. Thus **overlap
alone cannot explain the null result**. Unchanged useful traffic and launch/
host costs, together with cheap masked lanes, fit the observations; the receipts
cannot separate those mechanisms. Rank 0 is still the later finisher on
50.9%/63.8% of steady S7 hit cycles, so a real 0.7 ms branch reduction would have
had exposed opportunities.

Each pair's K2 dispatch is byte-identical across SPEED6→SPEED7, and corresponding
request token arrays match. Across pairs the only dispatch difference is
`hc.f.act` (`packet18` versus `p42.tiny.range`), not an expert kernel.

## What actually runs on the two target halves

Plan source: S7 cards01 `WS/run/ranks/rank{0,1}/launch-plan.json`, checked against
both S6 plans and the other pair. Rank 0 owns layers 0–22: **22 IQ2 layers and
one IQ3 layer, blk.2**. Rank 1 owns layers 23–47: **25 IQ2 layers**. Every layer
selects ten experts from a bank of 512. The persistent output/route layout is
unchanged by this proposal.

| Executed expert class | Shape per layer | S7 0–1 isolated µs/site | Rank 0 sites / ms per half | Rank 1 sites / ms per half |
|---|---|---:|---:|---:|
| IQ2 paired gate/up + P39 checks | Two 640×2560 matrices, 10 routed experts | 80.416 | 22 / 1.769152 | 25 / 2.010400 |
| IQ3 paired gate/up + two separate checks | Same shape, blk.2 only | 90.9375 | 1 / 0.090938 | 0 / 0 |
| IQ4_NL down + P39 status | 2560×640, 10 routed experts | 93.437 | 23 / 2.149051 | 25 / 2.335925 |
| **Three-class total** | | | **4.009141** | **4.346325** |

These are **K2 isolated time × actual plan count**, not a pipeline profiler
breakdown. The WS per-site event files do not provide those kernel durations.
They cannot be subtracted from rank busy to assign the remainder precisely.

| Same three-class total, ms/half | Rank 0 | Rank 1 |
|---|---:|---:|
| SPEED6, cards 0–1 | 4.013658 | 4.351575 |
| SPEED6, cards 2–3 | 4.040797 | 4.380225 |
| SPEED7, cards 0–1 | 4.009141 | 4.346325 |
| SPEED7, cards 2–3 | 4.043114 | 4.382800 |

Other measured MoE composition is retained:

| Component | Selected implementation / shape | S7 0–1 µs/site | Rank 0 / rank 1 K2 proxy, ms |
|---|---|---:|---:|
| Route + gather | `p42.route.production_rank32`, 512→10 routing, width 2560 | 41.042 | 0.943966 / 1.026050 |
| Router/shared gate/up tuple | `p30.small.rows4`, shared rows 640, K2560; Q6 except blk.2 Q8 | Q6 17.500; Q8 16.042 | 0.401042 / 0.437500 |
| Shared down | `p33.dense.segment`, Q8_0 2560×640 | 9.791 | 0.225193 / 0.244775 |

The per-layer expert activation is a 10×640 BF16 SiLU/product and the mixture
reduces ten 2560-element outputs before shared-expert combination. They remain
separate. A generic K2 activation/mixture aggregate is not a shape-specific
pipeline duration, so no fabricated per-half cost is assigned to them.

The rank-1 **draft** also has expert work, but uses its own INT8 draft kernel:
`mtp.hpp:99–112` explicitly excludes these experts from target IQ2/IQ4 dispatch.
Its enclosing draft command is about 2.77–2.80 ms here; receipts do not separate
its expert bodies from other draft work. The patch does not change draft
kernels and credits **zero draft-command saving**.

## Two concrete candidates and why the existing sweep misses them

1. **`p39.gate.packed`: packed IQ2 gate/up plus the existing checks tail.**
   SPEED7 cards01's plain GEMV comparison is 82.396→76.667 µs for IQ2, but
   83.750→82.813 µs for IQ3. The class-wide `expsgate` entry requires every
   workload to clear its guard; the IQ3 improvement is only 1.12%, below 3%.
   Thus K2 correctly retains `p28.paired.wg32` globally. The per-format P39
   IQ2 fusion runs, but hardcodes the older paired body.

   Reuse `p42expert::gate_lane<IQ2_S,2560>` (`p42_expert.hpp:9–96`) inside
   `Kind::expert_checks`. Preserve the exact lane products/additions, the
   32-lane adjacent reduction, BF16 outputs, both status writes and sticky
   failure handling. This changes code-table lookup/input loading using an
   existing candidate, not model precision, weights, activation, or reduction.
   The existing exceptional-scale/NaN fallback remains. IQ3 is untouched.

2. **`p39.down.bank`: bank/vector IQ4 down plus the existing status tail.**
   `p39_fused.hpp:85` uses `p33::down_lane<1,K>` (select/scalar). Yet the generic
   K2 dispatch says `expsdown=p33.down.bank`, Mode0. `p39_plan.hpp:21` tags all
   these down sites, and `main.cpp:1041–1053` intercepts them before the generic
   GEMV recipe. The generic winner does not supply P39's body.

   Reuse `p33::down_lane<0,640>` (`p33_candidates.hpp:12–62`) with unchanged
   integer levels, scale/product/add order, subgroup reduction and BF16/status
   tail. Bare select/bank rotated medians are 109.479/101.4065 µs (reread
   108.229/98.229). **Current fused select/status is already 93.437 µs.**
   Therefore neither disabling P39 nor subtracting bare bank from fused select
   is justified. Only the new fused-bank measurement can establish a benefit.
   This candidate is more uncertain: P39 may already let the compiler remove
   much of the work the standalone bank body saved.

SPEED6 and the second pair support the direction of the bare-body differences,
not their transfer into a fusion: IQ2 packed saves 5.312–5.729 µs across the four
runs; bank/select rotated saves 7.9165–8.0725 µs. No new candidate has been timed.

## How the patch measures, admits and executes a winner

Two additional closed-registry entries:

| K2 class | Dispatch modifier key | Candidate | Timed baseline |
|---|---|---|---|
| `fusion:p39.expert-checks-iq2-body` | `expert-checks-iq2-body` | `p39.gate.packed` | Current fused `p39.epilogue` |
| `fusion:p39.down-status-body` | `down-status-body` | `p39.down.bank` | Current fused `p39.epilogue` |

The existing original fusion-versus-unfused classes still run and choose the
parent fusion independently. A body modifier **cannot activate a declined
fusion**. Its `packet18` fallback means "keep that parent's original body";
`baseline_implementation=p39.epilogue` binds what actually executes. Runtime
adoption requires a tagged parent, the matching parent fusion enabled, and the
matching IQ2/IQ4 type. Missing modifiers reproduce SPEED7 behavior. The packed
GEMV alternative's existing plan conflict handling also stays in place.

Both candidates reuse the same complete production fixture allocations:
17 full-output/status/error scenarios, followed by eight untimed preflight
iterations, 200 measured repetitions per arm, and eight postflight iterations,
**in both reread and eight-bank rotated modes**. Timing rows identify the real
old/new bodies and record full payload, all stages, and bytes equality. Any
exactness mismatch aborts the fixture. Neither timing nor comparison allocates
an additional production model buffer.

Selection is the existing `k2_summary.py:119–149,237–329` algorithm. Each new
body class costs over 2 ms/token at its actual 47/48-layer frequency, so the
existing **strict >3% improvement** guard applies against the current fused
incumbent. There is no lowered guard or forced winner. Rotated measurements are
the selection primary; reread is also required and reported, following the
existing selector's mode policy. The original IQ3 fusion remains under its
existing 10% light-class guard. All deadline, stage-count, equality, rotation,
identity, registry and runtime safety checks remain.

The new host `Bindings::body` field chooses a compile-time kernel template;
there is no extra runtime device binding, workspace, snapshot extent or launch.
The same nineteen bindings, `Bound` payload, guards and ownership apply. No
Arena allocation grows: **23/25 dr1 rank-1 arena headroom remains 85.22 MiB**
and all existing memory admissions are unchanged. The rebuilt device image
would change and its code footprint can grow; this design does not claim a
binary-compatible source change. Transport/wire structures are unchanged.

## Calibrated forecast — planning, not a measurement

The old generic "10% faster experts" forecast, 0.411/0.822 ms hit/miss, is
withdrawn. Use the two measured bare-body deltas only as hypotheses to be tested
inside the fusion, with no credit for masked grid slots, instruction counts,
draft acceleration, snapshots, or a change of split.

For cards01, let `g=0.005729 ms`, `d=0.0080725 ms`. Full transfer would shorten
rank 0 by `22g+23d = 0.3117055 ms` and rank 1 by `25(g+d) = 0.3450375 ms` per
target half. This is an optimistic sensitivity case, **not a proven upper bound**.
For planning, assume half that delta survives composing the body with P39, and
then half of that reaches the pipeline. The first factor gives candidate
improvements of 3.56%/4.32%, sufficient to test the unchanged K2 guard; the
second factor is a conservative transfer assumption, not a fitted confidence
interval. A 25%-of-bare K2 win itself would fail the guard; the low pipeline
case assumes the 50%-of-bare K2 win and a further pipeline reduction.

Replay the existing critical-path model on every observed interval:

```
hit  ~= draft + max(rank1_target, rank0_start_offset + rank0_speculative)
miss ~= max(draft, rollback + rank0_redo)
        + max(rank1_target, rank0_start_offset + rank0_speculative)
```

Keep the observed controller residuals. Recompute all 99 submission intervals
per request, then medians within prompt class and across classes. Do not invert
one aggregate hit/miss median. The unchanged replay reproduces 39.422008903
class-balanced tok/s for the SPEED6 cards01 headline.

| Conditional sensitivity on S6 headline intervals | Hit saved, ms | Miss saved, ms | Projected class-balanced tok/s |
|---|---:|---:|---:|
| Neither candidate helps or qualifies | 0 | 0 | 39.4220 |
| Packed only, half bare delta transferred | 0.0659 | 0.1317 | 39.5447 |
| Bank only, half bare delta transferred | 0.0955 | 0.1910 | 39.6004 |
| **Combined working forecast: half fused transfer, then half pipeline transfer** | **0.0807** | **0.1613** | **39.5725** |
| Combined: half bare delta, full pipeline transfer | 0.1613 | 0.3225 | 39.7241 |
| Combined: full bare delta, full pipeline transfer | 0.3224 | 0.6444 | 40.0303 |

On the cards23 SPEED6 replicate, the same working case gives **0.0791/0.1614 ms**
and **39.5261 tok/s**, versus its own 39.3778 baseline. This supports applying
the target-body experiment to both ranks/pairs; it does not forecast a card
advantage. On instrumented S7 WS intervals the working savings are
**0.0810/0.1597 ms** (01) and **0.0791/0.1614 ms** (23), so the overlap result
is not dependent on using S6's timing trace. Their instrumented baseline rates
38.9692/39.0814 are not substituted for a WS128 submission rate.

Uncertainty includes zero and a pipeline regression even after an isolated K2
win. The working +0.38% headline-rate gain is smaller than ordinary run drift.
The 39.42–40.03 range is a planning sensitivity envelope, not a confidence
interval or a record claim. The more defensible first milestone is **measured
fused-body savings >3%, with exact bytes**, not a promised 40 tok/s.

## Validation and cheapest next device work

Performed now, without applying the patch:

- `git apply --check patches/packet45-speed8-expert-kernels.patch`: passed.
- Parsed every patched Python file; executed the new Python tests from an
  in-memory view of the patch, under an audit hook forbidding filesystem writes
  and subprocesses: **13/13 passed**. No packet or build file was created.
- Read-only review of template wiring, route/scale resets, guards, and current
  versus historical receipt counts. No C++ compiler or binary was run.

Tests included for application after the queue stops:

- `p39-body-tests` is a CPU-only CMake target: 342 checks, including 80
  scale/input combinations per body, invalid/partial/duplicate/zero routes,
  inactive and sticky cases, alias rejection, disabled-parent/type fallback,
  and 160 deliberate output-bit negative controls across the two bodies.
  **Authored, not built or executed here.**
- The integrated fixture retains its original 56 scenario pairs and adds 34
  body comparisons, for **90**. It exercises the production owner/submit path
  as well as the direct CPU arithmetic test. Those 90 checks are not claimed
  passed until the patch is applied and the host fixture is run.
- Python tests reject a stale 56-check current receipt against the ten-class
  registry, wrong bare incumbent, nonexact output, missing reread, incomplete
  stages, short payload, bad rotation, same-kernel fake win, unknown recipe,
  slow candidate and the exact 3% boundary.
- Current fixture consumers (`capacity_fixture_gate.py`, `validation_gate.py`,
  `seal45.py` current-fixture checks) use the new inventory. The historical
  fusion matrix's 56/372/2232 counts and archived failure evidence stay intact.

Application must generate a new build/seal and bind the new body tests and
current 90-check fixtures. This patch deliberately does not manufacture build
receipts, output hashes, source-reuse authorizations or a passing seal. The
existing sealed 56-check fixture/output digest is **not** evidence that the new
bodies were tested. Keep the pinned historical matrix distinct from the new
body proof when preparing the narrow amendment. All four device exactness
windows W2m, WS, WSs and WS128x remain mandatory before any speed publication.

The cheapest A/B is already in the proposed K2 fixture: same allocations,
paired current/new fused kernels, both cache modes, full payload, byte checks,
and per-event durations. If neither candidate clears the guard, keep the
original recipes and close these candidates without a geometry search. If one
or both clear it, use the normal admitted coordinator chain and instrumented
WS on both pairs; compare with the retained same-boot S7 controls, inspecting
actual adoption as well as the dispatch JSON. Do not replace the original
fusion decisions or edit qualifying receipts to force a candidate. Proceed to
WS128x/WS128 and fresh-process A-B-A only if the pipeline gain is visible. The
same fixed cold prompts, immutable arithmetic-v2-detmath oracle and full token
comparison decide exactness and any later headline.

## Evidence identities and reproducibility

All paths below are relative to packet45. K2 source medians are in each
`K2/run0/summary.json` (`classes`, `comparisons`, `workloads`, `reread`, `rotated`).
The summary's own `events_sha256` binds its raw timing table.

| Artifact | SHA256 |
|---|---|
| S6 cards01 K2 summary | `e1c3efea37e40cce628e4780f7dc0f555c9484adeb5b44cae8eab00b6be61313` |
| S6 cards23 K2 summary | `ac3ee3f53d7500729af76c2d3949efbc10ced683fbf2f30780a60567e0e907b3` |
| S7 cards01 K2 summary | `550f2b0a4f3a7d64c87ca1d7616833e028ec2e63f04bca8fc8a44e90df9f0da8` |
| S7 cards23 K2 summary | `f0e5b54901ef371d3c35a24e5748436bbf98d2bf1d9ee8fe2489cc0416019bf0` |
| Cards01 dispatch, both revisions | `477f62ec5cea61624047267ff69d74580c153ef40afe8558822dedb544018612` |
| Cards23 dispatch, both revisions | `a62f0ff1a9306152fafc15c08ef54a5054bd92ecc15021534c69b1880d24410f` |
| Rank0 launch plan, all four runs | `7a29e4b02662799f2bdb711df64b0d5f9cc40a0aa28d9740e82b2274d10461e9` |
| Rank1 launch plan, all four runs | `6426b6c84fbf668fa5c287e767a09b605eb71c70ead56756a15e20e8d534b57f` |
| S7 cards01 WS window | `bbec87c54c9eab5833e7deded986366cc5c8f11f7470e9969a02e26331e06636` |
| S7 cards23 WS window | `4f5a51efff9cee409c981d8c1fe884b9ab559c38e626c82eb2ea5f1a5542baa4` |

Forecast reproduction uses `notes/p45_after_speed6_analyze.py` in memory, replacing
only its `scenarios` mapping: `S=A=0.077926375,T=0.086259375` for the working
case; zero `D`, `R`, and `early`. Use twice those values for half bare/full
pipeline, and four times for the full-transfer sensitivity. Leave interval
alignment, token assertions, rate endpoints and class aggregation unchanged.

Patch SHA256: `e7f282fd4a16b2d0b79dceabecdcdc2b3bf62eb68352187044a6a0140304939b`.
Today the running packet source, binaries and seal are unchanged.
