# After SPEED6: the next lossless packet

2026-10-15. **Recommend one size-aware snapshot batching packet, keeping 23/25
with drafting on rank 1.** Start with an 8:1 size-ratio cap and the existing
copy kernel; cache structural preparation only if the diagnostic shows it
matters. This has the best estimated gain
per hour: about **0.23 ms/hit and 0.81 ms/miss**, or **39.98 class-balanced
tok/s**, if it removes 0.7 ms from both the speculative HALF and ROLLBACK.
That is a conditional engineering forecast, not another measured record.
Keep the actual record at **39.422008903**, LocalMaxxing
`cmv9wjmtj013gle01v8k1yg4v`, until a new qualifying device suite proves a gain.

The strongest concrete opportunity is not another layer move. The snapshot
kernel launches a rectangular grid padded to the largest extent in each batch:
**11.456 million work-items for capture versus 3.021 million useful 16-byte
chunks**, and **5.689 million versus 1.171 million for miss restore**. It also
rebuilds, validates and sorts almost a thousand descriptors each time. Neither
optimization requires dropping protected bytes, changing arithmetic, or using
more rank-1 device memory.

This session read receipts and source only. No build, device execution, model
weight read, submission, runtime edit, or seal change occurred. Both packet
trees, their outputs and their Python caches remained untouched. The only new
files are this note and its read-only [analyzer](p45_after_speed6_analyze.py).

## Evidence and accounting

Here `P` means `experiments/own-xpu-runtime/stage2/packet45-merged3`.
The primary paths are:

- `P/build/speed6-c4096-dr1-s23-cards01-gpu/{WS,WS128,WS128-r2}`.
- `P/build/speed6-c4096-dr1-s23-cards23-gpu/WS128`.
- Historical anchors: `P/build/speed3-c4096-dr1-gpu/WS128` and
  `P/build/speed3-c4096-dr0-s24-gpu/WS128`, plus the retained
  [hit-gap analysis](2026-10-15-p45-hit-cycle-gap.md) and
  [split model](2026-10-15-p45-split-sweep-design.md).

The three SPEED6 timed suites are qualifying, same boot `13858eef`, runtime
`34c62b433`, 4K, split23/dr1, with 12/12 passing 128-token oracle comparisons.
The headline seal is
`9b6fa7f397151c380a25f79dc3cf08abca1c70853300d7159febbf9456b35fbf`.
WS also passed all twelve requests under this seal. Its retained fixtures make
it exactness evidence; it is not substituted for the uninstrumented WS128 speed.

The helper joins each rank's HALF trace to `timings.jsonl` and asserts matching
`(position, fixture, speculative)`. It uses the same cycle definition as the
original [regression analyzer][oldanalyzer], whose pure `analyze()` was also
run independently for all three SPEED6 suites. Headline, busy, and hit/miss
statistics agree exactly. Deferred/null draft GPU times are excluded from
numeric summaries, not replaced by zero.

For a draft row, L is `target_completed_monotonic` and R is
`L + cycle_ms/1000`. The interval contains exactly one next rank-1 HALF:

```
cycle = (r1 received − L) + (r1 completed − r1 received)
      + (R − r1 completed)
```

This adds exactly per interval. The headline cycle statistic is the median of
twelve per-request hit/miss **means**, not a pooled cycle median. Independently
aggregated component medians need not add to that statistic. The detailed
steady partition uses positions >=100 and excludes the last interval without
a following speculative HALF: **920 hits + 254 misses per suite**. This avoids
attributing nonexistent speculative work at request termination.

`decode_rank_metrics.busy_ms_per_interval` counts HALF and DRAFT command
occupancy over the 63-interval decode window. ROLLBACK/ACCEPT are excluded;
capture is inside the speculative HALF command but partly outside its inner
timer. Busy is neither pure kernel time nor a duration that can be added across
the two ranks. `guess_rows.cycle_ms` includes resolution/redo at the controller
loop boundary; it is not the emitted-token interval.

## Hit and miss critical paths

Full-request medians of request means, milliseconds:

| Run | Hit | Hit before r1 HALF | Hit r1 HALF | Hit observation | Miss | Miss before r1 HALF | Miss r1 HALF | Miss observation |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPEED6 cards01 run1 | **22.204** | 2.826 | 19.190 | 0.183 | **38.717** | 19.218 | 19.397 | 0.123 |
| SPEED6 cards01 run2 | 22.202 | 2.822 | 19.185 | 0.190 | 38.765 | 19.242 | 19.417 | 0.111 |
| SPEED6 cards23 replicate | 22.118 | 2.801 | 19.070 | 0.240 | 38.909 | 19.295 | 19.527 | 0.106 |
| SPEED3 24/24 dr1, cards23 | 22.865 | 2.866 | 18.274 | 1.693 | 40.434 | 20.185 | 18.732 | 1.537 |

SPEED6 moves work onto rank 1 but removes most of its old wait for rank 0.
The same-pair repeat is close to run1; the second pair's faster hit is offset
by a slower miss. The observed class-balanced rates are 39.422009, 39.385608
and 39.377848. Do not infer a meaningful card-pair advantage from these small
differences or pool the repeats into a new headline.

Detailed SPEED6 run1 phases below are **steady pooled medians**. Nested and
overlapping rows must not be added together.

| Phase / measured envelope | Hit ms | Miss ms | Critical-path interpretation |
|---|---:|---:|---|
| Before the next rank-1 HALF | 2.845 | 19.358 | Draft on hit; rollback + rank-0 redo on miss |
| Draft command on rank 1 | 2.811 | 2.792 | Exposed on hit; overlaps rollback/redo on miss |
| Rank-0 speculative HALF, including capture | 19.227 | 19.700 | Runs alongside the next rank-1 target HALF |
| Rank-1 target HALF, excluding the preceding DRAFT command | 19.366 | 19.544 | Other branch of the overlap |
| Rank-0 ROLLBACK command | 0 | 1.607 | Fully exposed before corrected HALF; restore is inside this envelope |
| Rank-0 corrected HALF / redo | 0 | 17.707 | Fully exposed before handover to rank 1 |
| Prior token observation → draft sent | 0.01435 | 0.01434 | Includes rank-1 ACCEPT and controller handling |
| Draft sent → rank received | 0.00515 | 0.00516 | Mailbox dispatch |
| Draft completed → rank-1 HALF sent | 0.00767 | 16.547 | The miss value is waiting for redo, not slow draft publication |
| Rank-1 HALF sent → rank received | 0.00673 | 0.00980 | Actual handoff/start latency |
| Rank-0 starts relative to rank-1 HALF start | +0.00277 | −0.00633 | Both halves begin together after their prerequisites |
| Rank-1 completion → token observation | 0.00696 | 0.00879 | Long tail when rank 0 finishes later; median hides that tail |
| Rank-0 ACCEPT execution | 0.00030 | 0.00032 | No millisecond opportunity here |
| Rank-1 ACCEPT execution | 0.00019 | 0.00019 | Remote round trip is included in the observation-to-draft row |

The additive **steady means** are more useful than medians for checking totals:

| Non-overlapping interval segment | Hit ms | Miss ms |
|---|---:|---:|
| Before rank-1 HALF | 2.853554 | 19.366124 |
| Rank-1 HALF | 19.352042 | 19.534987 |
| Completion observation | 0.108636 | 0.134757 |
| **Cycle** | **22.314232** | **39.035869** |

On hits, the first segment is 2.812510 ms draft command + 0.041044 ms remaining
dispatch/control. On misses it is 1.640893 ms ROLLBACK + 17.692767 ms redo +
0.032465 ms remaining work. The 2.797609 ms draft overlaps that miss segment.
After both parallel halves finish, mean observation is only 0.0041/0.0038 ms.

**Hits:** draft publication, then the slower of the two halves. Rank 0 finishes
later on **41.09%** of steady hits on cards01, 38.59% on the repeat, and 60.11%
on cards23. The mean positive observation delay is small, but a rank-0-only
optimization cannot be credited with its entire HALF saving. **Misses:**
rollback + redo first, then the same parallel-half maximum. Rank-1 draft work
already overlaps rollback/redo; proposing that overlap again earns zero.

The code explains the receipts: [native_controller.hpp:32][controller] executes
rank 0 synchronously; `:72–85` hands over, starts rank 1, waits for the draft
publication and executes the next speculative rank-0 HALF before observing
rank 1. `:94–97` starts the next draft before resolving/redoing rank 0. This
is why the two branches form a maximum rather than a sum.
[mtp.hpp:232–249][mtp] already publishes a completed draft without the old
duplicate profiling pass. Median draft wall time is 2.7848 ms and the recorded
rank-0 wait for draft publication is only **0.00789 ms**. There is no remaining
0.49 ms publication gap to recover. Handover copies a 20,480-byte stream through
shared host slots (`Backend::handover():40`); the multi-millisecond
`rank0_to_rank1_handover_ms` field also includes intervening draft/redo work.

## Capture and restore: what is measured, what is only bounded

SPEED6 run1 steady HALF timings, milliseconds:

| Half | Prepare | Enqueue excluding waits | Wait | Forward sum | Complete command | Outside inner timer | Host waits | Issued compute commands |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| r0 speculative | 0.0515 | 3.4545 | 14.8020 | 18.2983 | 19.2297 | 0.6990 | 8 | 853 |
| r0 redo | 0.0501 | 3.5195 | 13.7983 | 17.3567 | 17.7073 | 0.0128 | 7 | 853 |
| r1 target | ~0 | 3.8901 | 14.5110 | 18.6001 | 19.4100 | 0.0498 | 3 | 927 |

Across 255 matched speculative/redo positions, speculative minus redo is
**1.526 ms command**, **0.686 ms outside the inner timer**, **1.006 ms wait**,
and **0.934 ms forward** at the median. These are enclosing proxies, not
separate capture timers. Guessed and corrected tokens can route differently;
capacity re-preparation and overlapping rank work also differ. No steady HALF
was cancelled, so these are complete halves, not shorter cancelled prefixes.

Capture starts before the inner timer (`rank.hpp:114`); the next token-history
readback drains it (`:120`). Begin also drains and reads sticky error/position
(`strict_snapshot.hpp:200–231`). Restore includes drains, sticky-error reads,
bank/launch/host-state restoration and transport (`rank.hpp:183–186`,
`strict_snapshot.hpp:233–263`). Event retirement can scan completion and
synchronize (`owner_retire.cpp:7–20`); readbacks have their own drain/wait/retire
path (`main.cpp:747–758`). The receipts cannot uniquely price GPU transfer,
descriptor construction, these tiny readbacks, or retirement. **Do not label
all 1.526 ms as capture bandwidth or all 1.607 ms as restore DMA.** The proposed
device A/B below adds short-lived diagnostic timers to resolve those parts.

Snapshot telemetry is cumulative across the resident suite. The final maxima,
not a sum of twelve cumulative files, show 1,525 captures, 326 restores and
326 completed redos, with zero redo fallbacks. Metadata reconstruction agrees
exactly with both total byte counters:

| Transport | Bytes each | MiB each | Source extents | Kernel/copy submissions | Current work-items | Useful packed 16-byte chunks |
|---|---:|---:|---:|---:|---:|---:|
| Capture / terminal full restore | 48,332,354 | 46.0933 | 975 | 31 | 11,456,480 | 3,020,900 |
| Confirmed-miss redo restore | 18,730,562 | 17.8629 | 938 | 30 | 5,689,312 | 1,170,788 |

Protected capture categories: 29,601,792 banked bytes, 12,800 current QSA-row
bytes, 6,653,310 other plan/control bytes and 12,064,452 standalone bytes.
The private image allocation is 103,607,362 bytes. The redo proof omits only
the 29,601,792 bank bytes that redo reconstructs; terminal/abandoned redo keeps
the full restore. Neither that proof nor the full-state contract needs changing.

`SnapshotBatch::submit` ([strict_snapshot.hpp:21–28][snapshot]) launches
`count × ceil(maximum/16)` work-items, although each extent only uses its own
length. Sorting followed by groups of 32 (`:154–170`) still puts an 8 MiB
workspace beside much smaller extents. The padded grids represent
**183,303,680 / 91,028,992 byte slots**, 3.79×/4.86× the useful payload.
Those are scheduled slots, **not extra memory traffic**: masked work-items do
not copy bytes. Removing them does not imply a 3.79× speedup. GPU issue and
host schedule-construction costs remain to be measured separately.

A particularly cheap metadata-only counterfactual limits each sorted batch's
largest extent to eight times its smallest, still at most 32 descriptors and
128 MiB. It preserves the exact extent multiset and all offsets:

| Schedule | Capture batches | Capture padded byte slots | Restore batches | Restore padded byte slots |
|---|---:|---:|---:|---:|
| Current | 31 | 183,303,680 | 30 | 91,028,992 |
| **8:1 max/min, proposed first A/B** | **32** | **54,000,160** | **32** | **21,505,216** |
| 4:1, comparison only | 33 | 53,998,784 | 33 | 21,503,840 |
| 2:1, comparison only | 37 | 49,548,112 | 36 | 19,255,856 |

The 8:1 choice removes 70.5%/76.4% of scheduled byte slots for just one/two
extra submissions. Its final 8 MiB workspace is alone and follows the existing
single-descriptor native-copy path; its byte count in this table is conservative
equivalent work, not a claim that native memcpy uses the same work-item grid.
The 4:1 alternative saves almost no additional work and adds another launch;
do not start a four-arm tuning campaign. **8:1 needs no new GPU kernel, device
descriptor allocation, weight layout, dispatch choice or copy checker.**

## Kernel opportunities on the 23-layer rank-0 half

WS128 has empty `sites.jsonl` and null family timings. Thus a measured
per-kernel pipeline ranking is unavailable. The following is an **isolated K2
cost proxy weighted by actual plan occurrences**, not a fabricated profile.
Rank 0 contains 18 GDN and five QSA layers. Its retained prepared schedule has
853 commands, including 92 route commands and 46 each of HC norm, HC injection,
attention and mixture commands. These counts are directly read from
`WS128/run/ranks/rank0/prepared-arguments-parity0.jsonl`.

| Work on rank 0 | Executed selection | K2 proxy per HALF | Useful next change |
|---|---|---:|---|
| Expert gate/up and expert down/status | IQ2 P39 checks epilogue over paired gate; IQ3 `p28.paired.wg32`; P39 down/status | **4.007 ms**: 22×80.729 + 84.062 + 23×93.334 µs | Largest clear repeated GEMV budget: improve loads/occupancy while preserving every dot-product and expert accumulation order |
| GDN QKV and Z projections | `p33.dense.segment` | **1.839 ms**, using 18 Q6 occurrences × (62.812+39.375) µs | Same arithmetic segment tuning; dtype-specific actual shapes must be checked |
| Attention output + combine | `p39.epilogue` | **1.337 ms**, 23×58.125 µs | Keep existing fusion; optimize its exact implementation |
| HC low/activation, gate, injection | P39 low/act; segment gates; segment/`p28.dense.wg32` injection | **1.943 ms combined proxy**, 46 low/act + 23 each gate/injection pair; excludes HC norm/mix | Many short commands; requires a full composition comparison, not blindly enabling `small.hc` |
| QSA score/softmax/value | `p30.attention.score_softmax` | Five × 113.542–186.979 µs at K2 lengths 88/152, **0.568–0.935 ms** | Length-specific evidence only; no interpolation to unseen shapes |
| GDN recurrence | `round2` | **0.671 ms**, 18×37.292 µs | Existing candidate only improved 3.6% in K2, below its threshold; not the next packet |

QKV/Z's first-layer dtype caveat is deliberate: the K2 Q8 counterparts are
57.500/36.459 µs; do not turn the all-Q6 proxy into an exact total. Expert
proxy includes the one IQ3 layer separately. Host enqueue overhead (3.45 ms)
and waits must not be added again to these isolated costs as if unoverlapped.

The final dispatch's `expsdown=p33.down.bank` does **not** identify the executed
P39-tagged down kernel; `p39_plan.hpp:20` owns that site. Similarly the table
still records P39 shared-up candidates, but `p39_plan.hpp:22–26` deliberately
leaves them out so `p30.small.rows4` small-FFN runs. Preserve that repair.
`small.hc` was correctly disabled by K2's composition check: 27.604 µs grouped
versus 21.876/20.313 µs for selected attention/FFN members. It is not an
unclaimed free fusion win.

The **rank-1 target and draft head** both use the resident shared output head,
with `p33.dense.segment` selected: K2 logits is **1.417708 ms**, versus
1.920364 ms incumbent. The 839,321,600-byte head implies about 592 GB/s of
payload/time in that isolated measurement; a further 10–30% improvement is a
kernel hypothesis, not something established by these receipts. The old
duplicate-profile optimization is already present and must not be counted again.

## Memory and split options

SPEED6's actual census matches the ledger: rank 0 owns 26,039,514,280 bytes;
rank 1 owns **32,122,890,400**. Against the **32,212,254,720-byte (30 GiB)
arena**, rank 1 has **89,364,320 bytes = 85.224 MiB**. Its additional card
headroom above the 1.5 GB reserve, after the 1,228,800-byte accounting reserve,
is **589.541 MiB**. These are different admission constraints.

Moving GDN layer 22 onto rank 1 costs **1,115,963,658 bytes**: 1,114,046,336
weights, 283,018 workspace and 1,634,304 recurrent state. It adds no QSA cache.
The following counterfactuals retain 8 MiB scratch; they are **not admitted**:

| Configuration | Rank-1 arena bytes | Arena headroom MiB | Above card reserve MiB | Timing model |
|---|---:|---:|---:|---|
| Current 23/25 dr1, 4K | 32,122,890,400 | **85.224** | 589.541 | Measured 39.422 |
| Proposed 22/26 dr1, 4K | 33,238,854,058 | **−979.041** | −474.725 | **38.807 tok/s**, hit 22.736 / miss 38.645 ms |
| Hypothetical 22/26 dr1, 32K, still 8 MiB scratch | 33,782,016,426 | **−1497.041** | −992.725 | No valid device arm |
| Return to existing 24/24 dr1, 4K, original allocation | 31,267,162,826 | 901.310 | 1405.627 | SPEED6-calibrated **38.103**, versus measured historical 38.131–38.313 |

The existing scratch reduction only applies to 23/dr1/4K. The hypothetical
32K line explicitly extends that reduction just for arithmetic; it does not
claim the current admission accepts it. Current 23/dr1/32K remains refused.

The prior mixed-layer marginal is S=0.836 ms, redo=0.713 ms, rank1=0.760 ms
per layer. Applying it to the **now balanced** SPEED6 halves predicts that
22/26 slows hits by 0.532 ms and saves only 0.072 ms/miss. Even eliminating its
memory deficit for free would lose throughput. The moved layer is GDN whereas
the original calibration mixed GDN and QSA; the forecast is uncertain, but
there is no evidence supporting a memory-offload campaign for this split.

For completeness, capacity options that can preserve the original arithmetic
are, in practical order:

- **Compact the expanded integer weight layout**, rather than changing model
  quantization. Comparing `plan.tsv` tensor byte sizes with live target-weight
  allocations finds **1,099,079,680 bytes (1048.164 MiB)** of expansion on rank 1
  across 260 tensors; the output head alone is **317,849,600 bytes (303.125 MiB)**
  larger than its stored Q6_K tensor (839,321,600 versus 521,472,000 bytes).
  `main.cpp:784–796` and `arithmetic.hpp:35–44` explain the expanded layouts.
  A packed kernel must reconstruct exactly the current values and reduction
  tree; simply changing the arithmetic variant is not permitted. Compacting
  all these weights plus moved layer22's additional 32,317,440 expanded bytes
  would put 22/26 dr1 **99.943 MiB below the arena**, still short of a chosen
  128 MiB planning margin. This is the strongest lossless *capacity* direction,
  but no speed win is established: decoding packed bytes costs instructions.
  Compacting only the head raises current 23/25 rank-1 margin to **388.349 MiB**.
  For a separate 32K-capacity objective, head compaction plus another
  135,948,448 bytes would cover the 453,798,048-byte arena deficit after an
  independently proven 8 MiB scratch extension. Neither combination is admitted
  by today's seal.
- Right-size target and draft scratch from 8 MiB to the 1,597,440-byte bound:
  at most **12.953 MiB** more on rank 1, with a separate draft merge/read bound
  required. The target GEMV workspace's proved maximum is 7,946,240 bytes;
  reducing its 8 MiB allocation saves only **0.422 MiB**.
- Rank-1 non-weight device storage totals only **151,198,112 bytes (144.19
  MiB)**. Even deleting all of it—which is impossible—would not close 979 MiB.
  Compact rank-0 snapshot allocation does not create any rank-1 capacity.
  Draft output weights already alias the target head; there is no additional
  head to deduplicate. Staging is host-pinned, outside the device arena.
- To leave 128 MiB of arena margin for 22/26, remove at least
  **1,160,817,066 bytes** from rank 1. For example, 189 of the draft's 512
  6,144,000-byte experts would save 1,161,216,000 bytes by exact host placement.
  Under an explicitly hypothetical uniform top-10 routing distribution this
  reads 22.68 MB across PCIe per draft, **1.19–3.24 ms at illustrative 19–7
  GB/s**, before latency/amplification. No packet45 per-expert frequency census
  establishes a cold set. This would likely worsen an already unfavorable
  split. The previous lane's UVA result is evidence of a possible lossless
  mechanism, not a bandwidth or routing measurement for this packet; see the
  [memory design](2026-10-15-p45-memory-reduction-design.md).

25/23 dr0 is not a better immediate alternative: the earlier bounded-scratch
projection still had a **253.88 MiB arena deficit** and a 39.081 tok/s forecast,
below this new record. Retain 23/25 dr1 and spend the next effort on its actual
critical paths.

## Ranked levers and device checks

Forecasts below start from run1's **actual 99 intervals per request**. For each
interval the helper changes the relevant branch durations, preserves overlap,
then recomputes each request's rate and the class-balanced median. It does not
take the reciprocal of two median cycles. Positive milliseconds mean saving.
The ranges vary engineering assumptions, **not statistical confidence**. Any
implementation may save zero or regress. These are separate alternatives,
not additive forecasts. Implementation sizes include fast tests but exclude
the unchanged coordinator qualification chain.

| Rank / lossless lever | Central saving hit / miss | Projected class-balanced tok/s; sensitivity | Rank-1 memory impact | Estimated implementation | Cheapest decisive device A/B |
|---|---:|---|---|---|---|
| **1. Size-aware snapshot batching; cache preparation if justified** | **0.225 / 0.810 ms** | **39.979**; 39.729–40.079 | **0** new device bytes for 8:1 grouping; 85.22 MiB retained | 100–200 lines including gates, **1–3 h**; structural caching adds work | Same split, pair, dispatch and one fixed 128-token prompt with natural hits/misses. Current versus 8:1 batches; record capture preparation, submit, drain and restore separately; compare all tokens and full-state mini gates |
| **2. Exact expert gate/up + down kernels, on both target ranks** | **0.411 / 0.822 ms** | **40.201**; 39.808–40.602 | Reuse current workspaces; if <=4 MiB extra is needed, headroom stays >=81.22 MiB and must be admitted | 300–600 lines, **6–12 h**, substantial kernel uncertainty | One isolated production-shape byte-equality census, then one fixed-prompt A/B with the same selected topology. Compare both halves and redo, not just isolated events |
| **3. Faster exact target/draft logits, same resident head** | **0.344 / 0.146 ms** | **39.898**; 39.671–40.098 | **0** extra if existing 7,946,240-byte workspace is reused; no second weight copy | 200–400 lines, **4–8 h** | Single new exact head candidate against p33 segment, then fixed-prompt A/B; price DRAFT and target-head effect separately |
| **4. Earlier rank-1 observation/draft issue while rank-0 finishes** | **0.114 / 0.059 ms**, generous half-tail estimate | **39.592**; all-tail ceiling 39.763, zero-gain floor 39.422 | **0** device bytes proposed; a bounded host mailbox/worker state | 200–400 lines, **4–8 h** plus concurrency proof | Controller-only A/B, same kernels/snapshot/split; measure r1-complete→DRAFT-sent, all token/guess sequences, ownership and cancellation. Reject if merely moving the wait |
| **5. Further memory reduction to admit 22/26 dr1** | **−0.532 / +0.072 ms** before packing/offload costs | **38.807**, predicted regression | Needs **979.04 MiB** just to fit, **1107.04 MiB** for 128 MiB margin; exact packed weights could leave 99.94 MiB | >=1 day for packed-kernel or offload/lifetime work | **Do not spend device time now.** Reconsider only with a new measured layer model and a no-slowdown capacity mechanism |

The central kernel hypothesis is 0.4 ms saved from each rank-0 HALF and
0.435 ms from rank 1, roughly a 10% improvement in the 4 ms expert proxy.
It requires improving both target ranks. Rank-0-only kernel tuning would have
a much smaller hit benefit and cannot be assigned the table's 0.411 ms.
For logits, the central hypothesis removes 0.28 ms from DRAFT and rank-1
target HALF; draft work on a miss remains hidden behind redo. K2 already rejected
the existing rows4, scale8, wide8, FP32-input and packed64 head recipes
(about 1.99–2.92 ms versus 1.418 ms selected). Do not rerun that old candidate
list as a new lever. A new load/layout improvement needs its own exact-tree
implementation; this is why head tuning ranks below snapshot transport.

For lever 4, the whole 2.8 ms draft is not removable serialization: its inputs
are confirmed target outputs and the next speculative rank-0 half needs the
guess. A useful change could publish rank-1 completion and start its next draft
while rank 0 finishes its old speculative half. It needs a separate controller
execution path plus stable stream ownership; the current controller is inside
rank-0 `execute()`. Reusing shared slots before the old HALF completes is not
allowed. Pre-capturing rank-0 state during the draft is another possible overlap,
but must wait until ACCEPT/redo commits the prior state; it cannot double-count
the capture saving in lever 1. The observed positive tail over the primary
99-interval scope bounds this opportunity at about **0.228/0.119 ms hit/miss**
at the median of per-request means. This differs from the smaller late-position
steady means above; both scopes are explicitly retained.

## The next packet: scope and stopping criterion for its first lever

Make **snapshot transport batching** the only behavior change.
The central forecast assumes 0.7 ms off S and 0.7 ms off R; low/high assumptions
are 0.3/1.0 ms. On the same-pair repeat it predicts 39.983 tok/s; on cards23,
40.065. The directly exposed hit saving saturates once rank 1 becomes the
slower branch. No additional hit credit is taken for uncertain bandwidth
contention relief. The 0.7 ms is a budget within observed enclosing costs,
not a claim that a CPU-only read has timed the proposed transport.

1. Use the 8:1 size-ratio grouping above, preserving the current kernel and
   real CopyEngine extent/lifetime validation. This changes how the exact
   admitted extents are grouped, not their content. Keep the existing per-copy
   **128 MiB** limit and bounded submission totals. Gate byte conservation,
   aliases, partial tails, bank parity, single-copy batches and invalid extents.
2. If diagnostic timers show host preparation is still material, build the
   structural recipe once: extent classification, stable size order,
   bank-specific bindings and batch shapes. Patch QSA offsets from admitted
   position; preserve allocation generations and every copy check. Do not cache
   stale pointers. A packed work list is a later alternative if ratio grouping
   underperforms; it needs owned immutable descriptors and must not overflow
   the existing 1,024-byte captured-argument bound. Neither extra complexity is
   a prerequisite for the first device A/B.
3. Keep capture payload **48,332,354 bytes**, redo payload **18,730,562 bytes**,
   full terminal restore, inactive-bank/QSA protection, metadata, shared-slot
   ownership, sticky errors, event lifetime and four-second checks unchanged.
   No precision, routing, acceptance, target/draft arithmetic or dispatch-rule
   change. Do not combine this with head tuning or another split in the first A/B.

Before device contact, fast mini tests must compare complete state for hit,
miss+redo, partial cancellation, abandoned redo, terminal/request boundary,
both placements and admitted splits; an omitted required extent must still
fail. Sparse production-size plan tests must check every item and new descriptor
bound. These are required future gates, **not tests run in this analysis**.

For the cheapest diagnostic, preregister one realistic prompt (for example
`benchmark-analysis`) with its unchanged 128-token oracle and natural hit/miss
sequence, fixed pair and dispatch, baseline → candidate → baseline. Add
temporary phase timers only to diagnostic receipts. If it does not remove
roughly 0.3 ms of the enclosing S/R costs, close that implementation quickly
and move to expert-kernel work. If promising, minimally reseal and run the
unchanged W2m/WS/WSs/WS128x and uninstrumented fixed twelve-prompt suite, followed
by confirmation. The device oracle remains exactness authority; no diagnostic
number, projection or partial prompt becomes a headline.

## Reproduce the read-only analysis

From repository root:

```bash
nice -n 19 ionice -c 3 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 \
  python3 -B notes/p45_after_speed6_analyze.py --verify
nice -n 19 ionice -c 3 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 \
  python3 -B notes/p45_after_speed6_analyze.py speed6-a speed6-a2 speed6-b
```

The helper writes only stdout and installs an audit hook refusing filesystem
writes and subprocess execution. The first command verifies the independent
legacy cross-check, census-to-ledger agreement, snapshot byte totals, and memory
counterfactuals. The second emits phase statistics and explicit forecast inputs.
The forecast asserts **99 intervals for every request** and its unchanged case
reproduces the headline. All three cross-checks passed. This is analysis
validation, not new model qualification.

Read-only input identities: each input digest hashes sorted lines
`relative_path + " " + sha256(bytes) + "\n"` for twelve receipts and twenty-four
rank timing files, relative to its WS128 directory.

| Run | 36-file input digest | Window SHA256 |
|---|---|---|
| SPEED6 cards01 run1 | `34115c0819bc498db39e5ec6b3544d1fc8dcd3e122d28d644f2a302d25397e5e` | `18a30e68ca8c94d3c1a988f61d5c1f7f7bbd1fed49f5c6114311723f1a5192d2` |
| SPEED6 cards01 run2 | `a4486bfcd7cd879275cbb4b8cc95afe8ab075bfbe497f0f4e467b0d9543436bc` | `809a75a6b3c2a2362bec5c55cdb44ccb5a3c0f29ef74ee7aed28d90c45cb6b98` |
| SPEED6 cards23 | `5bf637958608cd6bd4c311d0b6367ecbf3cb89979f431ff7c2e4708c37df2dc3` | `abf76112de758c6d3b2330a38c8f9245c20e601ea1532b744bf1b2e9048e40a4` |

Headline K2 dispatch SHA256:
`477f62ec5cea61624047267ff69d74580c153ef40afe8558822dedb544018612`.
K2 summary SHA256:
`e1c3efea37e40cce628e4780f7dc0f555c9484adeb5b44cae8eab00b6be61313`.
Snapshot source SHA256:
`f3df4371d04b49121064a0215febd0a48806443642dfb54784b3d4429fe98a2c`.
Analysis started from repository HEAD `3d0c4c467`; runtime identity remains
`34c62b433`. Initial root free space was 23,177,621,504 bytes; the analysis
creates only small note/script files.

[oldanalyzer]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/evidence/regression-analysis/analyze.py
[controller]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/native_controller.hpp#L32
[mtp]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/mtp.hpp#L232
[snapshot]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/strict_snapshot.hpp#L21
