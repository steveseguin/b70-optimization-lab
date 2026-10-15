# Packet 45 hit-cycle gap: retained-receipt analysis

2026-10-15. CPU reads only, while the coordinator runs device windows. No build,
device execution, weight read, or file write in `packet45-merged3`. This note is
the sole output. No runtime, dispatch, oracle, rollback contract or seal changed.

**SPEED1's extra hit time is on rank 1's target HALF, not an exposed rank-0
capture wait.** Against the same-boot packet-44 control, the reported hit gap is
**1.537 ms**. In an exactly additive steady-cycle decomposition, the rank-1 HALF
adds **2.491 ms**, offset by **0.405 ms less time before that HALF** and
**0.378 ms less completion-observation lag**. That steady subset has a 1.707 ms
mean gap; it is deliberately not substituted for the reported median statistic.

There is also a concrete, smaller regression: **about 0.49 ms between completing
the draft command and sending the next command**, versus about 0.01 ms in p44.
The new publication callback queries every draft event's profiling timestamps;
the ordinary drain subsequently queries the same events again. The enclosing
gap is measured; the profiling loop alone is not separately timed.

## Evidence and definitions

Paths in this table are relative to `experiments/own-xpu-runtime/stage2/`.
`P` below means `packet45-merged3`; `Q` means `packet44-context`.

| Label | Retained WS128 directory | Cards | Target layers r0/r1; draft owner |
|---|---|---|---|
| p44 control | `Q/build/c4096ctl15a/WS128` | 0–1 | 24/24; rank 1 |
| SPEED1 | `P/build/results-65c5eb22b/c4096-dr0-gpu/WS128` | 0–1 | 22/26; rank 0 |
| original dr0 | `P/build/results-f912fdaf6/c4096-dr0-gpu/WS128` | 0–1 | 22/26; rank 0 |
| original dr1 | `P/build/results-f912fdaf6/c4096-dr1-gpu/WS128` | 2–3 | 24/24; rank 1 |

All four windows use boot `13858eef-ec68-44ea-a67c-9444933b7100`. I checked
48/48 request receipts: every request passed its 128-token oracle comparison;
all four runs have identical token **and guess** sequences for each of the
12 prompts. These are comparable workloads, with placement/split still an
explicit confound. The control and SPEED1 also use the same card pair.

The calculation reads `run/repeat-1/*/receipt.json`, joins each rank's HALF
trace to its `rank*/timings.jsonl` by order and checks
`(position, fixture, speculative)`. The pure `analyze()` function in
[the retained analysis script][analyzer] was imported with `python3 -B`; its
file-writing `main()` was not called. Further partitions were calculated in
memory from the same receipts.

For each `draft_rows` entry with a hit/miss label and `cycle_ms`, let
`L = target_completed_monotonic` and `R = L + cycle_ms/1000`. There is exactly
one next rank-1 HALF wholly inside that interval. Define:

* before HALF = `1000 * (HALF.rank_received - L)`;
* HALF = `1000 * (HALF.rank_completed - HALF.rank_received)`;
* observation = `1000 * (R - HALF.rank_completed)`.

Their sum equals that cycle to within 0.000001 ms. This avoids adding overlapping
rank work. Steady tables select position ≥100: **931 hits and 255 misses per run**.
The reported headline uses each request's full recorded hit/miss mean, then the
median of those 12 means. Components' medians are not additive. `guess_rows`
instead time the controller loop through resolution; they are not inter-token
intervals ([native_controller.hpp:69,85–96][controller]).

## Measured phases

All times below are milliseconds. The first table reproduces the user-facing
statistic and puts its components on the **same full-request scope**. Each cell
is the median of the 12 request means; only within-request means add exactly.

| Run | Hit cycle | Hit: before HALF | Hit: r1 HALF | Hit: observation | Miss cycle | Miss: before HALF | Miss: r1 HALF | Miss: observation |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| p44 control | 23.201 | 3.728 | 19.032 | 0.386 | 39.218 | 19.645 | 19.506 | 0.068 |
| SPEED1 | 24.738 | 3.275 | 21.453 | 0.012 | 43.047 | 21.227 | 21.819 | 0.012 |
| original dr0 | 25.412 | 3.185 | 22.151 | 0.026 | 46.922 | 24.380 | 22.549 | 0.007 |
| original dr1 | 28.218 | 3.405 | 18.786 | 6.023 | 49.003 | 24.353 | 19.223 | 5.325 |

The next table gives **pooled steady hit-phase medians**. Rows describing parts
of another row must not be added again. Draft completion-to-HALF-send includes
publication/retirement and controller work; it is not a timer around a memcpy.

| Phase | p44 control | SPEED1 | original dr0 | original dr1 |
|---|---:|---:|---:|---:|
| Entire hit cycle | 23.123 | 24.516 | 25.811 | 28.453 |
| Before next r1 HALF | 3.684 | 3.294 | 3.204 | 3.409 |
| Previous token observation → draft sent | 0.0158 | 0.0259 | 0.0144 | 0.0197 |
| Draft sent → rank received | 0.0054 | 0.00006 | 0.00003 | 0.0081 |
| Draft command, received → completed | 3.647 | 2.768 | 2.689 | 2.870 |
| Draft completed → next r1 HALF sent | 0.0093 | 0.4917 | 0.4938 | 0.0088 |
| r1 HALF sent → rank received | 0.0065 | 0.0064 | 0.0062 | 0.4985 |
| r1 HALF, received → completed | 19.062 | 21.222 | 22.581 | 18.890 |
| r1 completed → controller token observation | 0.3371 | 0.0118 | 0.0059 | 6.1428 |
| ACCEPT rank 1, sent → completed | 0.0076 | 0.0111 | 0.0072 | 0.0100 |
| ACCEPT rank 0, sent → completed | 0.00028 | 0.00070 | 0.00030 | 0.00043 |

In dr1, the approximately 0.49 ms cost moves into **worker start latency**:
the rank-1 worker invokes the progress callback before calling `execute()`
([native_controller.hpp:44–48][controller]). It did not disappear merely because
the controller's draft-completed-to-send gap is small. In dr0, the callback runs
on rank 0 before the next `sent` timestamp, at `Backend::start():33`.

For completeness, these are pooled steady **miss-phase medians**:

| Phase | p44 control | SPEED1 | original dr0 | original dr1 |
|---|---:|---:|---:|---:|
| Entire miss cycle | 39.118 | 43.721 | 47.251 | 48.703 |
| Before next r1 HALF | 19.501 | 21.345 | 24.473 | 24.483 |
| r1 HALF | 19.552 | 22.364 | 22.748 | 19.349 |
| Completion observation | 0.0076 | 0.0119 | 0.0059 | 4.9362 |
| Rank-0 rollback envelope inside interval | 0.0209 | 2.7646 | 5.3957 | 5.3573 |
| Rank-0 redo occupancy before r1 HALF | 19.454 | 15.273 | 15.868 | 18.951 |
| Draft command | 3.655 | 2.771 | 2.687 | 2.879 |

P44's rank-1 draft overlaps rank-0 redo on a miss; SPEED1's rank-0 draft is
serialized with rollback/redo. Adding p44's draft and redo durations would
invent a cost that is hidden by overlap. The originals show why dr1 was slow:
its target rank 1 finished about 6 ms before the controller could observe it,
because `Backend::start(rank=0)` executes the speculative half synchronously
before the subsequent `wait(rank=1)`.

### Exact additive attribution and ranking

These are pooled **steady means**, so the rows sum exactly within rounding.

| Cycle segment | p44 hit | SPEED1 hit | Hit delta | p44 miss | SPEED1 miss | Miss delta |
|---|---:|---:|---:|---:|---:|---:|
| Before r1 HALF | 3.702198 | 3.296715 | −0.405483 | 19.556724 | 21.359062 | +1.802338 |
| r1 HALF | 19.083329 | 21.573928 | +2.490599 | 19.549618 | 21.973847 | +2.424229 |
| Completion observation | 0.389979 | 0.011794 | −0.378185 | 0.060194 | 0.011840 | −0.048354 |
| **Cycle** | **23.175506** | **24.882436** | **+1.706930** | **39.166536** | **43.344749** | **+4.178213** |

Ranked positive hit contributions are:

1. **Rank-1 target HALF: +2.491 ms.** This is the dominant measured location.
   It contains 26 target layers instead of 24 and the reverse-hidden transfer
   for the rank-0 draft. Those costs cannot be split exactly from these receipts.
2. **Draft completion → next HALF send: +0.483 ms.** The profile/publication
   callback is the identified new code path. Faster draft execution saves
   0.893 ms, so the entire before-HALF segment still improves.
3. **Observation → draft send: +0.010 ms.** This includes ACCEPT and controller
   handling. Rank-1 command dispatch changes by less than 0.001 ms in dr0.
   Neither is a plausible source of a 1.5 ms regression.

The remaining hit offsets are −0.378 ms observation lag and about −0.006 ms
combined draft/HALF dispatch. There is **no separately measured positive hit
term for rank-0 capture**, and no reason to relabel the 2.491 ms rank-1 interval
as capture time. Queue or memory contention from overlapping capture is possible
but not isolated here.

For misses, SPEED1's before-HALF mean is 2.772624 draft + 2.760506 rollback +
15.294809 redo + 0.531123 remaining control/publication. P44's corresponding
critical segment is 19.507755 redo + 0.021825 rollback + 0.027144 remaining work;
its 3.671659 ms draft overlaps redo. Thus the +1.802338 ms pre-HALF regression
includes a new exposed draft, +2.738681 ms rollback, and −4.212946 ms redo savings.

This finding is consistent across requests. The following uses each request's
**full recorded hit means**, with SPEED1 minus p44; each row adds within rounding:

| Prompt | Before HALF delta | r1 HALF delta | Observation delta | Hit-cycle delta | Miss-cycle delta |
|---|---:|---:|---:|---:|---:|
| architecture-tradeoff | −0.442 | +2.446 | −0.359 | +1.645 | +3.986 |
| benchmark-analysis | −0.426 | +2.434 | −0.374 | +1.635 | +3.617 |
| bug-report-synthesis | −0.520 | +2.401 | −0.493 | +1.388 | +3.750 |
| code-review | −0.426 | +2.475 | −0.353 | +1.697 | +3.550 |
| customer-email | −0.410 | +2.530 | −0.349 | +1.771 | +3.765 |
| decision-memo | −0.478 | +2.365 | −0.458 | +1.429 | +4.505 |
| incident-retrospective | −0.452 | +2.407 | −0.375 | +1.579 | +4.195 |
| performance-hypotheses | −0.436 | +2.398 | −0.360 | +1.602 | +3.816 |
| release-plan | −0.502 | +2.363 | −0.405 | +1.456 | +3.919 |
| risk-register | −0.454 | +2.387 | −0.503 | +1.431 | +3.633 |
| sql-debugging | −0.521 | +2.529 | −0.332 | +1.676 | +3.751 |
| technical-guide | −0.440 | +2.435 | −0.385 | +1.610 | +3.865 |

## Inside the rank and controller paths

Reported busy is **HALF plus DRAFT command occupancy over 63 token intervals**,
not one forward's GPU time ([pipeline.py:503–513][pipeline]). P44 rank 1 includes
its draft; SPEED1 rank 1 does not. SPEED1 capture submission is inside the HALF
command envelope and therefore inside reported busy, although outside the inner
half timer. Rollback and ACCEPT are not counted in that busy metric. Subtracting
one median forward from reported busy mixes scopes and does not measure capture.

The steady per-HALF medians below cross-check the phase attribution:

| Run / half | Prepare | Enqueue excluding waits | Wait | Forward sum | Command outside inner timer | Host waits | Issued commands |
|---|---:|---:|---:|---:|---:|---:|---:|
| p44 r0 speculative | 0.049 | 4.332 | 14.802 | 19.143 | 0.014 | 7 | not emitted |
| p44 r0 redo | 0.048 | 4.298 | 14.815 | 19.156 | 0.009 | 7 | not emitted |
| p44 r1 | 0.043 | 4.571 | 14.050 | 18.845 | 0.030 | 5 | not emitted |
| SPEED1 r0 speculative | 0.097 | 3.452 | 13.362 | 16.923 | 0.955 | 8 | 818 |
| SPEED1 r0 redo | 0.096 | 3.448 | 11.464 | 15.020 | 0.029 | 7 | 818 |
| SPEED1 r1 | 0.009 | 4.214 | 16.943 | 21.181 | 0.013 | 7 | 962 |
| original dr0 r0 speculative | 0.095 | 3.854 | 13.517 | 17.473 | 3.917 | 8 | 906 |
| original dr0 r0 redo | 0.094 | 3.846 | 11.666 | 15.608 | 0.029 | 7 | 906 |
| original dr0 r1 | 0.008 | 4.576 | 17.965 | 22.548 | 0.012 | 7 | 1,066 |
| original dr1 r0 speculative | 0.051 | 4.005 | 16.923 | 20.965 | 3.506 | 8 | 990 |
| original dr1 r0 redo | 0.064 | 4.532 | 13.813 | 18.549 | 0.016 | 7 | 990 |
| original dr1 r1 | <0.001 | 4.270 | 13.866 | 18.334 | 0.054 | 3 | 982 |

SPEED1 removed 88 rank-0 and 104 rank-1 commands, matching its 192-command
small-FFN repair. Rank-1 enqueue became faster, while its wait and complete
forward remain longer than p44. Reverse-hidden readback at
[rank.hpp:149–152][rank] occurs between the last layer and the final head when
draft rank is 0. `readback()` drains and then waits for its host copy
([main.cpp:740–741][main]); it accounts structurally for the two additional
rank-1 host waits versus p44. The receipt has no separate timer for this transfer,
the two extra layers, or competing copy traffic. Kernel and host-plan choices
also differ. An exact numerical split among those causes would be invented.
Original dr1's 18.334 ms rank-1 forward, at p44's 24/24 split, is faster than the
control's 18.845 ms; this is evidence against a blanket reversal of K2's choices,
not an isolated kernel A/B.

**Capture and its drain.** `image.begin()` precedes the inner timer, followed by
the token-history readback ([rank.hpp:113–120][rank]). That readback drains the
capture. Across the 255 same-position speculative/redo pairs:

| Speculative minus redo median | p44 control | SPEED1 | original dr0 | original dr1 |
|---|---:|---:|---:|---:|
| Outside inner timer | 0.004 | 0.925 | 3.886 | 3.491 |
| Forward waits | −0.013 | 1.911 | 1.874 | 2.113 |
| Complete HALF command | 0.004 | 2.851 | 5.910 | 6.012 |

These are enclosing proxies, not isolated GPU copy measurements. The outside
timer difference also includes deferred event retirement/profiling; guesses,
expert routes, cache warmth and overlapping peer work can differ on redo.
Across 1,174 matched steady overlapping halves, SPEED1 rank 0 completes before
rank 1 in **1,174/1,174**, with **3.326 ms median slack**. Original dr0 does so in
81.1%; original dr1 in 0%, with rank 0 finishing 6.061 ms later at the median.
P44 has −0.272 ms median slack. This supports **0 ms directly credited per dr0
hit** to SPEED2's faster capture; it does not predict zero effect from reduced
contention, nor zero capture benefit for dr1.

**Draft publication and polling.** The relevant source is unchanged between
SPEED1 and the frozen SPEED2 tree (`rank.hpp`, `native_controller.hpp`,
`mtp.hpp`, `main.cpp` have no diff between `65c5eb22b` and analysis HEAD).

1. [mtp.hpp:218][mtp] copies `e.pending` into `pending_profile`.
2. [rank.hpp:251,281][rank] installs `poll_result()` as the progress callback,
   also invoked by native controller/worker cancellation checks.
3. [mtp.hpp:236–247][mtp] timestamps draft wall time **before** querying every
   draft event's timing. Only after those queries does it return a completion
   for publication. `Device::timing()` checks completion and fetches profiling
   data ([owner.cpp:148–151][owner]); the SYCL backend performs status and two
   profiling-info queries ([backend.hpp:163,168–170][backend]).
4. It clears `pending_profile`, but not `e.pending`. The next
   [Engine::drain():612–625][main] queries the same events again. On a dr0 hit
   that drain is at the next image's `begin()`; on a miss it is at undo.

The roughly 0.49 ms dr0 gap therefore contains **completion retirement before
publication**, not a half-millisecond mailbox transfer. The duplicate second
pass is folded into capture/undo proxies; it cannot be independently priced
from these receipts. The four-second submission check in `Engine::drain()`
must survive any deduplication.

Idle per-site polling (old priority 4) is a different issue. Calls remain around
each launch, but `poll_result()` immediately returns when `async_pending` is
false. Rank 1 in dr0 has no draft provider/callback at all. Idle polling cannot
directly explain its slower target HALF, and gets **0 ms measured saving** here.
Active completion profiling is the demonstrable cost worth testing first.

Raw draft/guess fields reinforce the scope distinction; these are steady pooled
medians, not additional additive phases:

| Receipt field | p44 control | SPEED1 | original dr0 | original dr1 |
|---|---:|---:|---:|---:|
| `draft_wall_ms` | 3.622 | 2.769 | 2.690 | 2.838 |
| `draft_gpu_ms` | 2.909 | 2.585 | 2.558 | 2.570 |
| `rank0_idle_waiting_for_guess_ms` | 3.641 | 0.00007 | 0.00007 | 0.497 |
| `rank1_before_half_ms` | 3.676 | 3.281 | 3.205 | 2.909 |
| `guess_rows.cycle_ms`, hit | 23.071 | 24.516 | 25.775 | 28.418 |
| `guess_rows.cycle_ms`, miss | 42.458 | 43.063 | 47.507 | 52.239 |

`rank1_before_half_ms` ends after the controller sends HALF, not when the worker
enters it. The dr1 worker's 0.49 ms delay is consequently outside that field.
Likewise `rank0_to_rank1_handover_ms` includes intervening work after producer
completion: its medians are 3.679/6.484/3.855/3.390 ms for these four runs. It is
not the cost of the shared-slot memcpy. The matched `sent`/`received` table is
the useful handoff-latency measure.

## Live-out undo: quantified, analysis only

The checked SPEED2 write-set artifact is
[write-set-proof.json.gz][writeproof], summarized by
[speed2-snapshot-inventory.json][inventory]. These are conservative write unions,
not claims that every saved byte is actually written at every position. At
positions 100, 128 and 214, contexts 4K and 32K, the saved byte counts are:

| Saved category | Draft rank 0, bytes | Draft rank 1, bytes |
|---|---:|---:|
| Inactive GDN recurrent banks | 26,738,688 | 28,311,552 |
| Inactive convolution-history banks | 1,228,800 | 1,290,240 |
| Current QSA rows | 12,800 | 15,360 |
| Other plan intermediates | 6,349,784 | 6,912,824 |
| Streams and scalar/history controls | 20,508 | 20,508 |
| Standalone workspaces/scratch | 12,064,452 | 12,064,452 |
| **SPEED2 capture and restore, each** | **46,415,032 / 44.264824 MiB** | **48,614,936 / 46.362816 MiB** |
| Bounded batched submissions, each direction | 30 | 32 |

For a **hypothetical logical-state-only contract**, p44's effective target-device
undo is **20 bytes for either placement**: 16 bytes of token history plus the
four-byte position. The token history needs a 16-byte capture; the old position
is already known on the host. Restore is two host uploads, not a bulk D2D image.
[P44 undo at rank.hpp:140–145][oldrank] implements precisely these writes, restores
host histories/bank selection, and invalidates lookup/FP32 caches. This is a
candidate byte target, **not a validated live-out proof for all p45 paths**.

| Hypothetical semantic-only scheme | dr0 restore | dr1 restore | Status |
|---|---:|---:|---|
| P44-style bank/position undo | 20 B (0.000019 MiB) | 20 B (0.000019 MiB) | Requires the consumer proof below |
| Also conservatively retain changed QSA rows | 12,820 B (0.012226 MiB) | 15,380 B (0.014668 MiB) | Still omits full-storage observers |
| Current full-state contract | 44.264824 MiB | 46.362816 MiB | Existing conservative SPEED2 capture; no liveness-based reduction established |

The large apparent reduction is possible only because banked GDN/conv **live
inputs** are untouched: 26.671875/28.230469 MiB stay in the active physical banks
while speculation writes the spare banks ([rank.hpp:65–77][rank],
[main.cpp:1126–1128][main]). Undo can reselect the old banks. Appended QSA rows are
outside the committed prefix; resetting position makes them invalid. At position
100, the existing committed QSA prefix is 1,184,000/1,420,800 bytes and needs no
undo copy. The corrected half overwrites its new row before consuming it;
pooled rows require the corresponding four-position validity proof
([kernels.hpp:176–200][kernels]). Intermediate outputs and workspaces can be dead
at this logical boundary even though their physical bytes changed.

The required proof is substantially stronger than scanning output names:

* Work with **physical allocations, bank parity, aliases and byte ranges**.
  For every reachable next read, prove that the same byte was rewritten from
  confirmed state first, or that the speculation never touched it. Inputs and
  outputs of a fused site need internal access ordering; a same-site label is
  insufficient. Cover all selected kernel variants, partial outputs, caches,
  workspace reuse and communication consumers.
* Cover every partial-launch cancellation point, complete miss, hit/accept,
  EOS/cancel without redo, request reset and next request, both placements,
  both contexts and all bank/pooled-QSA boundaries. Swap back only if the
  speculative half actually swapped. Prove no stale invalid row can become
  visible before overwrite.
* Invalidate or correctly version lookup and FP32 caches. Restoring old cache
  metadata while leaving its overwritten backing storage is unsafe. Keep host
  histories, launch extents, slot ownership and confirmed draft state coherent.
  Conservatively retain the existing **65,536-byte host shared-slot snapshot**;
  the 20-byte device target does not price or eliminate host metadata.
* Sticky errors remain fatal. Never restore an older zero over a newly reported
  failure. Preserve the oracle, arithmetic, verifier and safety checks.
* Explicitly define which observers the contract admits. The current contract
  includes raw state dumps and terminal inventories, not just future token
  arithmetic. [rank.hpp:190–193][rank] observes every plan allocation and inactive
  bank; [request_state_inventory.hpp:10–13][stateinventory] observes standalone
  bytes. Those reads make changed physical state live-out even with no next
  model half. A relaxed semantic contract would change those observables and
  requires an explicit contract decision. Under the existing contract, excluded
  bytes instead need exact preservation or reconstruction before observation.

Thus the source explains p44's 20-byte effective undo, but the current
[ROLLBACK.md][rollback] does **not** permit adopting it. SPEED1's failed
whole-buffer exclusion is precisely why next-half overwrite alone is inadequate.
No claim is made that the existing plan metadata proves the semantic candidate
for every consumer or cancellation. No live-out optimization was implemented.

## Packet 46: two focused tests

These are forecasts, not measured gains. Keep SPEED2's write-set repair, the
small-FFN composition repair, all other selected kernels and every exactness
and runtime-safety check. Do not change the running tree for these proposals.

| Priority / change | Predicted saving per hit | Predicted saving per miss | Cheapest confirming device A/B |
|---|---:|---:|---|
| 1. Publish a completed draft without duplicate synchronous profiling; collect/account each event once, preserving lifetime, error and four-second duration checks. Make inactive progress callbacks cheap. | **0.4–0.5 ms dr0** if the enclosing 0.49 ms gap is removed; no credit for the unmeasured duplicate second pass | **0.4–0.5 ms dr0**, with possible additional drain savings uncredited | Fixed 4K dr0, 22/26, same dispatch and write-set implementation, one preregistered 128-token prompt with natural hits/misses per arm. Compare post-draft gap, HALF start latency, event-query counts, tokens/guesses and hit/miss cycles. A diagnostic timing arm can count/timestamp profiling; it is not a headline run. |
| 2. Separate layer split from draft placement and test **24/24 with draft still on rank 0**, first at 4K. | **1.2–1.6 ms** planning estimate: move two layers off the critical rank with 3.326 ms observed rank-0 slack | **−0.3 to +0.3 ms**: faster r1 is largely offset by two extra layers in rank-0 redo; do not promise a miss win | Same pair, same prompt, same draft owner, dispatch, snapshot and publication implementation; compare 22/26 vs 24/24. Keep event envelopes and reverse-handoff timing, verify every token against the same oracle, and require the unchanged memory admission before launch. |

The split forecast is a coarse per-layer estimate, not measured layer timing.
It should not be added to a placement change, and the two projected savings are
not guaranteed additive. Rank-1 reverse-hidden readback remains a possible next
lever, but its isolated cost is absent from these receipts; no invented saving
is assigned to moving it to another queue.

The current memory projection gives 24-layer rank-0 target bytes plus the existing
dr0 draft and duplicated head **31,925,548,110 bytes at 4K**, leaving
**2,316,749,746 bytes**, above the unchanged 1,500,000,000-byte reserve. The same
calculation at 32K leaves **1,434,110,898 bytes**, **65,889,102 bytes below** that
reserve. Therefore this recommendation authorizes no 32K 24/24 run; it needs a
different admitted plan or a separately proven memory reduction. These are
read-only projections from [memory-plan.json][memory], not new admission receipts.

Neither tiny idle-poll cleanup alone nor semantic-only undo is recommended as
the next speed claim. The former has no isolated measured cost; the latter would
change the full-state contract. After a successful screening A/B, the unchanged
coordinator suite remains the qualifying exactness and speed authority.

## Reproduction identities

For each run below, the input digest is SHA-256 of sorted lines
`relative_path + " " + sha256(file_bytes) + "\n"`, relative to its WS128 root,
covering its 12 request receipts and 24 rank timing files (36 files). No files
were rewritten or decompressed to disk. The window hashes bind run identity.

| Run | 36-file input digest | `window.json` SHA-256 |
|---|---|---|
| p44 control | `4c22cf86b855d2e3514a746c9e2da7e3b34fea4a3bb8f8dc32bd81b05a5b585b` | `e9bf3994b5ed38348351536a2de3bc7658fb98c0dde26fbbaf1bac1db462e2d5` |
| SPEED1 | `778ae10db55714e9889ac0d19e5b9fca44e77647f1648fe948f57bbe18faf02f` | `36bf52fde273bf126473d799358737288c183f1c608b994f347f98a7a24f4265` |
| original dr0 | `21195a397597872d9c59381373983bd7aa11618044f6992c98c18726c6ff3601` | `0ca8bd899f203bb7763dd00caf8d396fbade5d357d069621d135d95066c06706` |
| original dr1 | `9fb88dea01e46da67ee64bbb5c3cdbfc2d7acd8bd7a7b4b9f7c1ac61aeb6c430` | `ac5a06741084bd4ffa13314906d74244f35a0b14d4098ef4349b62966679b13d` |

Analysis source HEAD: `9b91d3270cb18a8d03c053d98e84822849f150fe`.
Commands used `nice -n 19 ionice -c 3 taskset -c 4-15,20-31`, `OMP_NUM_THREADS=2`
and `python3 -B`. No new speed or exactness run was performed.

[analyzer]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/evidence/regression-analysis/analyze.py
[controller]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/native_controller.hpp#L33
[pipeline]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/pipeline.py#L503
[rank]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/rank.hpp#L113
[main]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/main.cpp#L612
[mtp]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/mtp.hpp#L218
[owner]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/owner.cpp#L148
[backend]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/backend.hpp#L163
[oldrank]: ../experiments/own-xpu-runtime/stage2/packet44-context/rank.hpp#L140
[kernels]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/kernels.hpp#L176
[stateinventory]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/request_state_inventory.hpp#L10
[writeproof]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/evidence/speed2/write-set-proof.json.gz
[inventory]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/speed2-snapshot-inventory.json
[rollback]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/ROLLBACK.md
[memory]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/memory-plan.json
