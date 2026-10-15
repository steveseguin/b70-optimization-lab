# Packet 45: exact, but slower — receipt attribution and packet 46

Analysis date: 2026-10-15 UTC. Packet 45 identity: `f912fdaf6`.
Read-only CPU analysis of retained receipts; no build, device execution, weight
read, runtime-source change, or write under `build/`. The coordinator owns the
packet-44 controls. This is an explanation and an A/B proposal, not a new speed
claim or permission to weaken an exactness check.

Packet 45 adds approximately **6 ms to each speculative rank-0 half, principally
capture, then spends another 5.4 ms in the rollback command after a miss**. Much of capture overlaps
rank 1, so these costs cannot simply be added to token latency. There is also a
specific kernel-composition loss: the P39 shared-up/activation fusion disables
the larger selected small-FFN group, leaving its other projections on `r5`.
Draft placement changes both the critical path and the target-layer split.
The evidence does **not** support reverting all the new kernels.

## Receipts, identities, and measurement scopes

The source paths below are relative to `experiments/own-xpu-runtime/stage2/`:

| Name | WS128 source | Cards | Target split / draft owner |
|---|---|---|---|
| p44 record | `packet44-context/build/c4096b/WS128` | 0–1 | 24/24, rank 1 |
| p45 dr0 | `packet45-merged3/build/c4096-dr0-gpu/WS128` | 0–1 | 22/26, rank 0 |
| p45 dr1 | `packet45-merged3/build/c4096-dr1-gpu/WS128` | 2–3 | 24/24, rank 1 |
| p44 control A | `packet44-context/build/c4096ctl15a/WS128` | 0–1 | 24/24, rank 1 |
| p44 control B | `packet44-context/build/c4096ctl15b/WS128` | 2–3 | 24/24, rank 1 |

All three completed source runs have boot ID
`13858eef-ec68-44ea-a67c-9444933b7100`. The record is nevertheless roughly 51 hours
earlier in monotonic time. Same boot alone does not remove time or card effects.
The three runs have **identical token sequences and identical guess sequences
for all 12 prompts**, not merely matching aggregate acceptance. Each has 128
tokens per prompt; median acceptance is 0.7913386.

| Completed run | Class-balanced tok/s | Reciprocal interval, ms | Loss vs record | Rank 0 / rank 1 reported busy, ms | Hit / miss cycle, ms |
|---|---:|---:|---:|---:|---:|
| p44 record | 37.856264 | 26.416 | — | 23.492 / 22.586 | 23.189 / 39.330 |
| p45 dr0 | 33.834893 | 29.555 | 10.62% | 27.418 / 21.763 | 25.412 / 46.922 |
| p45 dr1 | 31.025456 | 32.232 | 18.04% | 28.543 / 21.479 | 28.218 / 49.003 |

Rates are recomputed as the median of prompt-class medians using **99 intervals
between completion timestamps 1 and 100**. Packet 44's `window.json` contains a
different pooled submission field; it is not substituted for this metric.
Reported busy is the median across requests of `decode_rank_metrics`; reported
cycles are medians across requests of each hit/miss mean.

Three scopes must not be mixed:

* `decode_rank_metrics` uses **63 intervals**, and counts HALF plus DRAFT command
  wall occupancy, including the repeated rank-0 forward after a miss. It omits
  ACCEPT and ROLLBACK: [pipeline.py:503–513](pipeline.py#L503).
* A `timings.jsonl` forward is `prepare_ms + enqueue_loop_ms + wait_ms` for **one
  half**. Enqueue time has internal waits subtracted. Snapshot submission happens
  before its timer, but the next readback drains outstanding snapshot copies
  inside that timer: [rank.hpp:113–125](rank.hpp#L113),
  [rank.hpp:161–180](rank.hpp#L161).
* For the steady comparisons below, positions are **at least 100**. These are
  beyond the first eight fixture-retention positions for every prompt. Packet
  44 retained early layer fixtures; packet 45 WS128 did not. That early IO favors
  packet 45 in the primary window and cannot explain its regression.

Thus “busy minus one median forward” is not a direct snapshot measurement. It
also includes the approximately 0.21 extra forward per output interval on misses,
draft work on its owner, and a different averaging window.

## Rank and cycle accounting

These medians come from matched HALF trace/timing records at positions ≥100.
The speculative and plain rank-0 rows contain 1,186 and 255 halves respectively;
rank 1 has 1,186. All packet-45 speculative rows report `cancelled=false`.

| Run / half | Prepare | Enqueue excluding waits | Wait | Forward | Command outside inner timer | Host waits | Issued kernels |
|---|---:|---:|---:|---:|---:|---:|---:|
| p44 r0 speculative | 0.049 | 4.331 | 14.803 | 19.159 | 0.013 | 7 | 1,060 prepared |
| p44 r0 redo | 0.048 | 4.310 | 14.854 | 19.207 | 0.009 | 7 | 1,060 prepared |
| p44 r1 | 0.042 | 4.506 | 14.096 | 18.845 | 0.029 | 5 | 1,055 prepared |
| p45 dr0 r0 speculative | 0.095 | 3.854 | 13.517 | 17.473 | 3.917 | 8 | 906 |
| p45 dr0 r0 redo | 0.094 | 3.846 | 11.666 | 15.608 | 0.029 | 7 | 906 |
| p45 dr0 r1 | 0.008 | 4.576 | 17.965 | 22.548 | 0.012 | 7 | 1,066 |
| p45 dr1 r0 speculative | 0.052 | 4.005 | 16.923 | 20.965 | 3.506 | 8 | 990 |
| p45 dr1 r0 redo | 0.065 | 4.532 | 13.813 | 18.549 | 0.016 | 7 | 990 |
| p45 dr1 r1 | <0.001 | 4.270 | 13.866 | 18.334 | 0.054 | 3 | 982 |

Times are ms; medians of components need not sum to the median of their sum.
Packet 44 did not emit `launches_issued`, so its counts are explicitly the
retained prepared-command census. Packet 45's runtime counts match that census.

**Paired miss comparison:** match each speculative half to its non-speculative
redo at the *same position in the same request*, using the same dispatch. Across
255 such pairs, the median speculative-minus-redo command duration is **−0.159 ms
in p44, +5.910 ms in dr0, and +6.012 ms in dr1**. The new outside-inner differences
are 3.886/3.491 ms; forward differences are 1.880/2.024 ms, mostly waits. This is
strong evidence for capture plus its eventual drain. It is not a standalone copy
benchmark: the guessed token/expert routes, cache warmth, queue overlap,
speculative cancellation checks and bucket-restoration history differ from the
confirmed redo.

For an additive check, the following uses the same **99-interval window for
every column**, averaging the 12 requests. Forward decomposition includes only
whole HALF commands inside that window; all three runs have 99 speculative
halves plus an average 21.167 redos there. Command occupancy clips boundaries.

| Run / rank | All forwards / interval | Other inner HALF work | Outside inner HALF | Draft | Rollback | Accept | Total command occupancy |
|---|---:|---:|---:|---:|---:|---:|---:|
| p44 r0 | 23.221 | 0.366 | 0.022 | 0 | 0.005 | 0.067 | 23.680 |
| p45 dr0 r0 | 20.490 | 0.413 | 4.120 | 2.657 | 1.157 | <0.001 | 28.837 |
| p45 dr1 r0 | 24.248 | 0.664 | 3.902 | 0 | 1.129 | <0.001 | 29.943 |
| p44 r1 | 18.748 | 0.249 | 0.072 | 3.619 | 0 | 0.077 | 22.764 |
| p45 dr0 r1 | 22.042 | 0.026 | 0.045 | 0 | 0 | <0.001 | 22.114 |
| p45 dr1 r1 | 18.161 | 0.535 | 0.110 | 2.860 | 0 | <0.001 | 21.665 |

The ranks overlap: **do not add rank 0 and rank 1** to predict token latency.
Dr0's faster/smaller rank-0 forwards save 2.731 ms of occupancy per output
interval, but outside-timer work adds 4.098, draft placement adds 2.657, and
restoration adds 1.152. These are measured accounting deltas, not independent
end-to-end speedups. Dr1's forward column contains snapshot drain time; it does
not prove its target kernels became slower.

For hit/miss attribution, `draft_rows.cycle_ms` joins **this target completion
to the next target completion**. Clip rank command envelopes to those boundaries
and pool positions ≥100:

| Run / outcome | Cycle mean | Rank 0 HALF total | Rank 0 DRAFT | Rank 0 ROLLBACK | Rank 1 HALF | Rank 1 DRAFT |
|---|---:|---:|---:|---:|---:|---:|
| p44 hit | 23.157 | 19.244 | 0 | 0 | 19.080 | 3.648 |
| p44 miss | 39.349 | 38.982 | 0 | 0.022 | 19.568 | 3.660 |
| p45 dr0 hit | 25.575 | 21.587 | 2.690 | 0 | 22.315 | 0 |
| p45 dr0 miss | 47.253 | 37.337 | 2.691 | 5.404 | 22.716 | 0 |
| p45 dr1 hit | 28.452 | 24.790 | 0 | 0 | 18.909 | 2.895 |
| p45 dr1 miss | 48.942 | 43.642 | 0 | 5.191 | 19.354 | 2.901 |

This exposes the critical differences: on dr0 misses, rank-0 HALF work is actually
1.645 ms shorter than p44, but rollback and local drafting more than consume
that saving. Dr1's rank-0 HALF is longer on both outcomes and holds up otherwise
faster rank 1. These pooled means deliberately differ from the headline
median-of-request-means cycle table.

`guess_rows.cycle_ms` measures a different controller span, from loop entry to
accept/redo resolution ([native_controller.hpp:69–101](native_controller.hpp#L69)).
Its pooled hit/miss means are p44 **22.404/42.042**, dr0 **25.537/47.349**, dr1
**27.697/51.925 ms**. It corroborates the regression but must not be substituted
for target-completion intervals or added to `draft_rows` cycles.

`capacity_reprepares` is a cumulative counter, not work performed each token.
Its final rank-0 value is 158 in p44 and 194 in either p45 run; rank 1 remains 79.
Per-request deltas and initial values are retained in the analysis JSON. The
32-position admission bucket remains in [main.cpp:1223](main.cpp#L1223); restoration
can re-admit both prepared banks at a crossed boundary
([strict_snapshot.hpp:94–101](strict_snapshot.hpp#L94)). These occasional extra
reprepares are already inside the measured command costs. There is no evidence
of a fresh full-plan preparation every step.

## (a) Snapshot, rollback, cancellation, and request-boundary work

The dominant new site is [strict_snapshot.hpp:28–33](strict_snapshot.hpp#L28),
called by `SpeculativeImage::begin` from [rank.hpp:113](rank.hpp#L113), and by
`restore` from [rank.hpp:185](rank.hpp#L185). The CopyEngine 128 MiB bound is
correct. Raising or bypassing that bound is not a performance repair.

The retained census and launch-plan metadata reproduce the exact capture
inventory, without reading tensor or model bytes:

| Draft placement | Source extents | Copy submissions / capture or restore | Bytes at position 100 | MiB | Private allocation bytes |
|---|---:|---:|---:|---:|---:|
| rank 0 | 935 | 936 | 360,552,888 | 343.850 | 361,736,888 |
| rank 1 | 1,021 | 1,022 | 372,212,760 | 354.970 | 373,633,560 |

The 256 MiB `operator-scratch` allocation alone requires two 128 MiB copies on
every capture and restore. Nine standalone workspaces account for 278,902,468
bytes; hundreds of plan outputs account for most of the submission count.
This is **not** hundreds of chunks of one large KV buffer. The snapshot saves
inactive recurrent banks, overwriteable plan outputs, scratch, and QSA suffixes;
it deliberately protects committed active banks and QSA prefixes from being
silently repaired by rollback ([strict_snapshot.hpp:38–84](strict_snapshot.hpp#L38)).
At position 214 the payloads are still 359,203,768 / 370,593,816 bytes.

Packet 44's undo mainly swapped recurrent banks and restored position and the
16-byte token history ([packet44 rank.hpp:157](../packet44-context/rank.hpp#L157)).
Median ROLLBACK command time rises from **0.0205 ms** to **5.398/5.572 ms**.
The measured 99-interval rollback-command cost is **1.157/1.129 ms per output**.
This is a directly measured added serialized cost, not a pure copy timer:
dr0 starts asynchronous draft work before miss rollback
([native_controller.hpp:94–96](native_controller.hpp#L94)), so undo's first drain
can include residual draft work. Capture accounts for most of the approximately
6 ms per-attempt speculative gap, but dr0 hides much of it behind its longer
rank-1 half.

Other audited paths:

| Path | Receipt/source finding | Per-output attribution |
|---|---|---|
| ACCEPT | `image.accept()` drains an already completed half; steady accept commands are about 0.0002–0.0003 ms | Negligible; no snapshot copy-back on a hit |
| Cancellation | Per-site and per-command checks in [rank.hpp:127–160](rank.hpp#L127), observers in [owner.cpp:180](owner.cpp#L180); all 1,186 steady speculative halves per run issue their full command count | No observed saved speculative arithmetic; host checking cost is not separately timed |
| Sticky errors / configuration | `verify_configuration`, guard, position/error checks remain; the old runtime already checked configuration | Not evidence of a new multi-ms hash/check cost |
| Snapshot retirement | [strict_snapshot.hpp:107–113](strict_snapshot.hpp#L107) zeros private backup and writes `speculative-snapshot.json` at request boundary | Outside token1→token100; matters to request turnover, not this headline rate |
| Draft final state | [mtp.hpp:267–271](mtp.hpp#L267), [rank.hpp:263](rank.hpp#L263), [request_reset.hpp:13](request_reset.hpp#L13) | Boundary dump/reset; not a per-token disk-write explanation |
| Telemetry counters | Snapshot receipts are cumulative for the persistent worker, including startup work; last values are 1,525 captures / 326 restores, not 12 independent request counts | Do not sum cumulative receipts or convert all saved bytes into decode latency |

The exact rollback contract is documented in [ROLLBACK.md](ROLLBACK.md). Packet
46 must retain it, including invalid cache tails, overwrite-only buffers, bank
and launch metadata, shared-slot ownership, and sticky errors. Reverting to
packet 44's smaller undo without proving the full-state contract is not an
acceptable optimization.

## (b) Draft placement and handoff

Moving the draft changes more than its card. [rank.hpp:38–45](rank.hpp#L38)
changes the target split from 24/24 to 22/26 for dr0. The dr0 forward improvements
therefore cannot all be credited to K2; the extra two layers on rank 1 similarly
cannot all be blamed on a slower kernel.

| Steady median, ms | p44 | p45 dr0 | p45 dr1 |
|---|---:|---:|---:|
| Draft row wall | 3.622 | 2.690 | 2.838 |
| Draft row GPU time | 2.908 | 2.558 | 2.570 |
| Controller waiting for guess | 3.636 | <0.001 | 0.497 |
| Draft issue to rank-1 half start | 3.675 | 3.205 | 2.909 |
| Rank-0→rank-1 handover interval | 3.677 | 3.855 | 3.390 |
| Target completion observed after rank-1 HALF completed | 0.331 | 0.006 | **6.055** |

The near-zero dr0 guess-wait field does not make drafting free. `Backend.start`
executes rank 0 **synchronously** ([native_controller.hpp:31–35](native_controller.hpp#L31));
the controller spends about 2.69 ms there before the next rank-1 half begins.
For dr1, it posts rank-1 HALF before waiting for asynchronous draft publication
([native_controller.hpp:71–77](native_controller.hpp#L71)), reducing the explicit
wait. Draft work still shares rank 1's in-order queue; its residual tail can be
charged to a following HALF. Draft row wall time and HALF wait must not be
interpreted as disjoint device execution times.

More importantly, the controller starts the speculative local half before
`b.wait(1)` and the emitted-token timestamp
([native_controller.hpp:84–88](native_controller.hpp#L84)). In dr1 the approximately
25 ms rank-0 command delays observation of the approximately 19 ms rank-1 result
by 6.1 ms. This is an observed consequence of the critical path, **not an extra
6.1 ms to add on top of snapshot time**. Merely moving the timestamp would change
accounting, not accelerate useful work, and is not proposed.

The reverse hidden-state handoff for dr0 is 20,480 bytes: readback after target
layer 47 at [rank.hpp:149–152](rank.hpp#L149), shared-memory publication, then upload
at [mtp.hpp:197](mtp.hpp#L197). It adds a rank-1 drain and ownership edge, not a
hundreds-of-MiB transfer. Ordinary forward shared-slot memcpy remains at
[native_controller.hpp:42](native_controller.hpp#L42). Dr1's asynchronous path adds
two 4-byte result copies ([mtp.hpp:213–218](mtp.hpp#L213)) and queued 4-byte token /
20,480-byte streams inputs ([mtp.hpp:249–255](mtp.hpp#L249)). No retained event
timing isolates their individual costs. The signed reverse-handover field is
−19.050/−22.575/−18.877 ms: it describes overlap, not a negative copy duration.

The draft itself became faster, not slower. Its BF16 GEMV selection now inherits
the selected segment path ([mtp.hpp:98–109](mtp.hpp#L98)); its other operators use
the selected dispatch. The proposed fix should keep that gain.

A smaller host-side candidate remains: the progress callback is invoked before
and after every plan site and while draining
([rank.hpp:144–146](rank.hpp#L144), [main.cpp:704](main.cpp#L704)). `poll_result`
clears `async_pending` but the callback persists until request reset
([mtp.hpp:232–264](mtp.hpp#L232)). Gate it on an outstanding publication rather
than repeatedly checking an already completed one. No ms saving is credited
without an A/B. The futex timeout changed from 10 ms to 100 µs, but both versions
wake on publication; a 9.9 ms per-step saving or loss cannot be inferred from the
timeout value.

## (c) K2 selections versus the actual pipeline

Both p45 dispatches select the same material target changes. They differ only in
HC activation choices that P39 HC-low/activation already absorbs. Their measured
member winners before fusion conflict resolution are not the final dispatch.

| Site | p44 selection → p45 selection | Interpretation |
|---|---|---|
| `gdn.norm`, `qsa.prepare`, `qsa.pool` | packet18 → `p42.tiny.wg256` | Retain; isolated wins, no isolated pipeline regression established |
| `route`, `route+gather` | specialised → `p42.route.production_rank32` | Actual target capture goes from five to four commands/layer |
| IQ2 expert checks | separate → `p39.epilogue` | Removes 94 check commands across 47 IQ2 layers |
| Expert down/status | separate → `p39.epilogue` | Removes 48 status commands |
| HC low/activation | separate → `p39.epilogue` | Removes 97 activation commands, including final head |
| Shared up/activation Q6 and Q8 | separate → `p39.epilogue` | Isolated win, **composition loser** against enabled `small.ffn` |
| Attention/combine | separate → `p39.epilogue` | Removes 48 combine commands; retain |
| `hc.a.inject` | `p33.dense.segment` → `p28.dense.wg32` | Isolated selection change, not individually timed in WS128 |
| `expsdown` table entry | `p33.down.select` → `p33.down.bank` | P39 down/status owns the executed site; do not blame this unused table choice |
| `logits`, other material dense GEMVs, attention, small GDN | unchanged | Logits remains `p33.dense.segment`; small GDN remains `round2` |
| `small.ffn` | `p30.small.rows4` → same table entry | **Table says enabled, but P39 rewrite prevents its target group from forming** |
| IQ3 checks, shared-down/combine, small HC | off → off | Not new runtime costs |

K2 dr0 isolated examples, incumbent → candidate in microseconds: IQ2 checks
88.854→80.834; down/status 115.209→93.021; HC low/activation 18.228→16.145;
shared-up Q6 15.834→13.125; Q8 18.854→15.104; attention/combine 64.480→58.126;
GDN norm 7.083→5.625. QSA prepare/pool summary values aggregate multiple fixture
lengths; they cannot be multiplied by production layer count as though each
aggregate were one target invocation. Route+gather represents one
production-shaped fixture, but its isolated baseline/candidate event sums are
not a measured end-to-end latency saving against p44's specialised pipeline.
Both pairs' full comparison
tables are retained in [kernels.json](evidence/regression-analysis/kernels.json).

The small-FFN loss is reproducible from static composition and actual retained
command captures:

1. K2 selects the four-member small-FFN group and resets its individual GEMV
   entries to `r5`: [k2_summary.py:215–221](k2_summary.py#L215).
2. P39 first rewrites shared-up plus activation:
   [p39_plan.hpp:23](p39_plan.hpp#L23). The primitive sibling tuple no longer
   exists. Fix 6 correctly declines to fuse it:
   [main.cpp:655–664](main.cpp#L655). Reinstating the old throw is not a repair.
3. The remaining router, shared-gate projection, and shared scalar gate fall
   back to the reset `r5` entries while shared-up uses P39:
   [main.cpp:1033](main.cpp#L1033), [main.cpp:1068](main.cpp#L1068).
4. P39 registry entries declare empty fusion members, so conflict resolution
   does not see this overlap: [kernel-registry.json:535](kernel-registry.json#L535).

The old full tuple issued **two** commands per layer (one grouped projection,
one activation); the new tuple issues **six** (router two, gate one, fused up one,
scalar gate two). The captured schedule proves **192 extra commands** across
48 layers. Other fusions remove 335, so the net target still issues **143 fewer**:

| Captured command delta, both target ranks | p45 minus p44 |
|---|---:|
| Broken small-FFN composition | +192 |
| HC activation removal | −97 |
| IQ2 checks | −94 |
| Down status | −48 |
| Attention combine | −48 |
| Route/gather | −48 |
| **Total: 2,115 → 1,972** | **−143** |

The approximate cost opportunity from dr0's K2 Q6 workload is:
`10.730 + 13.958 + 13.125 + 6.667 = 44.480 µs` for the selected fallback tuple,
versus `17.292 + (15.834 − 10.937) = 22.189 µs` for the grouped projection plus
an estimated separate activation. Across 47 Q6 and one Q8 layer this projects
to **about 1.07 ms per complete target forward**, split roughly 0.49/0.58 ms for
22/26 or 0.535/0.535 for 24/24. This estimate combines isolated workload timings,
including a subtraction to estimate activation; it is **not a measured pipeline
speedup**, and host-launch savings must not be added again as though unoverlapped.

There is no evidence that P39 attention/combine lost an old active
attention/combine/norm fusion. The old matcher requires `next.inputs == outputs`,
but norm inputs include `active,error`
([main.cpp:499](main.cpp#L499), [packet3 plan.hpp:39–41](../packet3/step/plan.hpp#L39)). The actual old
capture already has separate norm commands; the new capture removes the separate
combine and keeps the same norm. The table label alone would misattribute this.

WS128 has no per-family event timings (`enqueue_family_ms` is null). Its aggregate
wait cannot assign the remaining fractions of a millisecond to individual
kernels. Non-speculative dr1 rank-0 forward and dr1 rank-1 forward are both faster
than the historical p44 values; broad “new kernels slow the pipeline” is not a
supported conclusion. The demonstrated composition loss is narrower.

## (d) Card-pair controls

Both controls completed during this analysis (receipts read at approximately
03:40 UTC). Their full artifact-hash maps match the historical p44 record, on
the same boot. Both pass all 12 × 128 tokens and have the same token and guess
sequences as all three original runs.

| Fresh p44 control | Class-balanced tok/s | Reciprocal interval, ms | Rank 0 / rank 1 busy, ms | Hit / miss cycle, ms | Steady r0 spec / redo / r1 forward, ms |
|---|---:|---:|---:|---:|---:|
| A, cards 0–1 | 37.940267 | 26.357 | 23.404 / 22.588 | 23.201 / 39.218 | 19.143 / 19.156 / 18.845 |
| B, cards 2–3 | 37.917139 | 26.373 | 23.480 / 22.707 | 23.245 / 39.416 | 19.130 / 19.137 / 18.937 |

The observed control difference is only **0.0231 tok/s (0.061%), or 0.0161 ms per
reciprocal primary interval**. Both reproduce the historical record within
0.23%. Against its own pair's control, p45 dr0 loses **10.82%, +3.198 ms/interval**;
p45 dr1 loses **18.18%, +5.858 ms/interval**. A simple subtraction of the observed
control pair gap leaves **2.660 ms** of the dr1-versus-dr0 difference. This is an
adjusted combined placement/split/runtime comparison, not an isolated placement
effect or a crossover experiment.

The controls rule against a broad slowdown of cards 2–3 as the explanation for
dr1's loss. They also strengthen the kernel conclusion: with the same 24/24
split, p45 dr1's non-speculative rank-0 forward is **0.588 ms faster**, and rank
1's is **0.602 ms faster**, than control B. Conversely, dr0's rank-1 forward is
**3.703 ms longer** than control A. That latter increase includes its 26-layer
split and reverse-handoff drains; the available aggregate timing does not
uniquely divide it among extra layers, queue/drain behavior and kernel effects.

All runs retain the same process affinity `0-3,16-19`. The steady medians of
host load average are 5.54 in the old record, 1.02/0.85 in p45, and about 1.86 in
the controls. Every analyzed steady half has zero major faults; minor faults
have median zero. This does not identify every scheduling effect, but there is
no evidence here for a paging regression or a changed affinity mask.

The fresh controls have one dispatch confound: control A selects
`hc.a.inject=p28.dense.wg32`, while historical p44 and control B select
`p33.dense.segment`; all other final dispatch entries match the record. Report
the observed pair difference, but do not call it a pure hardware difference.
A same-dispatch crossover would be needed to isolate that last component.

## Ranked regressions and packet 46

The ranking below separates measured cost from predicted removable latency.
Savings overlap and must not be summed into a promised tok/s number.

| Priority / cause | Evidence in ms | Packet-46 change | Predicted saving per output interval; cheapest confirming device A/B |
|---|---|---|---|
| 1. Broad snapshot capture and restore | About 5.9–6.0 extra per speculative attempt; about 5.4 per miss; rollback commands add 1.13–1.16 per output | First batch the same bounded source extents into a validated copy schedule / packed image, preserving the exact byte set and ordering. Then shrink copied scratch/invalid-tail ranges only with a writer-footprint proof and full-state comparison; unknown kernels keep full backup | Planning target **1–3 ms dr0, 3–5 ms dr1**, conditional on reducing both submission and transfer cost. Capture-only removal is often hidden on dr0 hits. One fixed 128-token prompt with natural hits/misses, old/new capture implementation, same split/dispatch; compare command envelopes, per-miss restore and every token. Run strict full-state rollback/cancellation checks as well |
| 2. Small-FFN/P39 composition | +192 commands; isolated projection about 1.07 ms/full target, roughly half per rank | Disable only `shared-up-act-q6/q8` so the measured `p30.small.rows4` group executes; retain other P39 wins. Repair registry membership and time the entire competing tuple before restoring P39 here | Tentative **0.5–1.0 ms/output**, not established by current aggregate timing. Cheapest A/B is one admitted dispatch delta with those two keys off, fixed placement, 128 tokens; verify two rather than six commands per layer and unchanged oracle tokens |
| 3. Placement / split / synchronous controller | dr0 versus dr1 differs by 2.676 ms in reciprocal primary interval, but also changes pair and split; dr1 completion observation lags by 6.055 ms | Keep dr0 as the provisional faster p45 setting. Rebalance only after snapshot repair; separate draft owner from target split for the experiment. Consider local asynchronous submission only if it accelerates work, not just timestamps | **0 ms independently credited**; 0–2.7 ms is an exploratory bound from the current combined difference, not a measured placement saving. On one pair compare both placements at the same split, then 22/26 vs 24/24 with owner fixed. Reuse the same unchanged oracle |
| 4. Idle draft-progress polling | Called around every plan site after publication is already complete; no isolated timing | Check `async_pending` before polling; keep watchdog/cancel checks and publication ordering intact | **0 ms credited until measured**. One same-dispatch prompt A/B; record enqueue/wait and context switches, without adding profiling to a headline run |

Preserve the measured draft-head gain, tiny kernels, route/gather, IQ2 checks,
down/status, HC low/activation and attention/combine. Keep the CopyEngine guard,
fault latch, watchdogs, admission, affinity, teardown and all immutable
arithmetic-v2-detmath token comparisons. Do not “fix” time by moving the completion
timestamp, hiding snapshot time, accepting guessed tokens, reducing retained
state exactness, or changing the model/KV precision.

The A/Bs above are **coordinator-run mechanism diagnostics**, not new performance
headlines. Use a fresh admitted packet-46 identity and real dispatch receipts;
do not edit packet-45 measured receipts or pretend a forced table passed K2.
One fixed varied-suite prompt is the cheapest screen; if it wins, repeat in fresh
processes in both orders before choosing it, then run the full registered suite
and required exactness windows for the final claim. Repeated screening prompts
must never be relabeled as the cold realistic submission suite. Do not repeat a
long CPU real-model suite to measure these device costs.

## Reproduction of this analysis

The three standard-library scripts under
[evidence/regression-analysis](evidence/regression-analysis/) only read retained
metadata and receipts. They write their own analysis directory, never `build/`.
Run each with `nice -n 19 ionice -c 3 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2
python3 -B`:

* [analyze.py](evidence/regression-analysis/analyze.py): validates and joins
  HALF/timing rows, recomputes rate and clipped occupancy, pairs misses, checks
  token/guess identity; writes [metrics.json](evidence/regression-analysis/metrics.json)
  and [input-hashes.json](evidence/regression-analysis/input-hashes.json).
* [snapshot_inventory.py](evidence/regression-analysis/snapshot_inventory.py):
  reconstructs exact source extents from census/plan metadata, checks total
  against the actual backup allocation, and retains cumulative snapshot
  telemetry in [snapshots.json](evidence/regression-analysis/snapshots.json).
* [kernel_inventory.py](evidence/regression-analysis/kernel_inventory.py): records
  measured dispatch/comparisons and actual prepared command labels;
  [kernels.json](evidence/regression-analysis/kernels.json) and
  [kernel-input-hashes.json](evidence/regression-analysis/kernel-input-hashes.json).

Input SHA-256 lists identify the exact original receipts; raw device outputs
remain untouched. All conclusions about pipeline causation are bounded by the
available wall timing; only the proposed device A/Bs can assign an independent
end-to-end saving to overlapping work.

Analysis validation passed: five complete suites, 60 matching token/guess
sequences, reproduced primary rates, 2,115/1,972 prepared-command totals,
matching p44 control artifact maps, all retained input hashes, and all report
file/line links. This validation executes only the analysis scripts; it is not a
new runtime qualification gate.
