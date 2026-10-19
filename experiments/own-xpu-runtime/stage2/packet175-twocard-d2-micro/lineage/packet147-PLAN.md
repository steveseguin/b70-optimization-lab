# Packet147 — remaining exact levers on both record lines

October 18, 2026. CPU-only synthesis; no build, model read, device experiment,
queue change or performance claim. Starting main: `b609404124c8da500ff6b3e85a25276a72269812`.

**Decision: brief the missing one-card packet60 HC fusion port first.** Its
conditional budget is **0.8–1.05 ms/token, +2.40–3.17%** on packet58z. There is
historical engine evidence for this mechanism and the current one-card source
does not contain it. Second, a small **changed-entry cache-publication** design
is worth a bounded feasibility brief: recovering 60–70% of its current measured
1.231 ms boundary would save 0.739–0.862 ms/token, **+2.21–2.59%**. That recovery
fraction needs proof; it is less secure than the HC port.

**Two cards: none of the unbuilt mechanisms has an evidence-supported ≥2%
forecast today.** Finish the existing packet145 question through its coordinator;
do not duplicate it. Cold/warm differences justify asking a locality question,
not assigning a new kernel an 80% transfer factor. Packet142's null result is
direct counterevidence to that shortcut. Larger changes remain possible; the
correction graph and one-card causal MTP research targets are priced below.

These are ranked hypotheses, not qualified winners or positive lower bounds.
Both proposed one-card briefs can fail. No changes are added together to claim
a composite gain. Two cards remain the primary objective; identifying a useful
one-card port does not manufacture a two-card candidate.

## Anchors and cost model

| Line | Current measured reference | Configuration retained |
| --- | ---: | --- |
| Two B70 | **58.798108759182306 tok/s**, packet136 WS128, record `cmve4dtir007wrf01k57sdf23` | Bundle8: bundle7 plus p131b snapshot banks; 24/24 target layers, rank 1 MTP, fixed 80,128-row draft prefix, full BF16 KV/state |
| One B70 | **29.259764156562692 tok/s**, packet58z WS128, record `cmvebtu5f009frf01gsnfi2eh` | All 48 target layers on card 0, no draft; down-tile16, overlapped maintenance, **21,552,729,600-byte** expert cache, pinned-host zero-copy misses, context 4096/full BF16 KV |

Both target the **quantized compressed Unsloth UD-IQ3_XXS version**, unchanged
`iq3-p49-split32-v1` arithmetic and packet49 oracle. These are the recorded
owner-authorized 128-token results; **strict512 remains false**. Prefill is not
measured for these record identities. This study supplies neither missing
promotion evidence nor a second fresh performance run.

Sources: [two-card result](../packet136-record-bundle/submission/prepared-a/result.json),
[one-card result](../packet58z-onecard-record/submission/prepared-a/result.json),
[submission ledger](../../../../results/localmaxxing-submissions.md).
The supplied Strata 52–62/~140 tok/s figures are goals, not matched comparisons
established here. At unchanged aggregation, 62 would require about **0.878 ms**
off the two-card reciprocal interval, a 5.45% throughput increase; 140 requires
about **9.864 ms**, a 138% increase. Neither is a prediction.

The reciprocal rates are **17.007350** and **34.176625 ms/token**. They are not
pooled mean latencies. For two cards, replay the 1,188 original intervals:

```text
T = max(D, R + C) + max(B, A + offset) + G
D = draft command; R = restore; C = corrected rank0 half on a miss
A = next speculative rank0 half; B = rank1 half including suffix wait
G = measured accounting remainder, not promised removable idle
```

Each prompt contributes `99000/sum(T)`; take the median within each of six
classes, then their median. Reconstruction matches the record to <1e-8 tok/s
and every interval to <1e-7 ms. There are **932 hits and 256 misses**. Saving
on both overlapping halves counts once, with another correction saving on
misses. Advancing rank 0 does not automatically advance the suffix-dependent B.

| Exact replay sensitivity for +2% | Required net saving/change |
| --- | ---: |
| Same body saving in A, B and C, full exposure | **0.275155 ms per half**; about 0.334 ms per pooled emitted interval |
| Correction C only | **1.573805 ms per miss**; about 0.339 ms per pooled interval |
| Draft D only | **0.423078 ms per hit**; D is hidden on these misses |
| Cost-free rescue of a uniform fraction of misses | **14.6129% of misses**, about **3.149 acceptance percentage points** |
| One card, uniform saving in every prompt's mean interval | **0.669655 ms/token** |

The convenient reciprocal one-card threshold is 0.670130 ms. The tiny
difference comes from reaggregating prompt rates. All one-card percentages
below use prompt reaggregation where available. No projected point is a
measurement, public curve point or submission.

## Ranked decisions

Build sizes below are planning caps, not actual builds: S = roughly 100–500
new/changed source lines and ≤200 MB build outputs; M = 500–1,500 lines and
≤300 MB; L = 1,500–4,000 lines and ≤500 MB. Source reuse does not waive fresh
proofs. Runtime memory is separate and called out explicitly. Work estimates
include CPU implementation/proofs, not device queue time.

| Rank | Exact mechanism; affected line | Current-line budget and explicit assumption | Risk / size | Decision and next evidence |
| ---: | --- | --- | --- | --- |
| 1 | **Port packet60 three-stage HC to one card** | 0.8–1.05 ms/token, **+2.40–3.17%**, conditional on retaining roughly 75–100% of the weakest historical half saving after scaling its layer count | Medium arithmetic/integration risk; M, 1–2 days; no intended extra device weight memory | **≥2% brief.** Prove current source absence, identical BF16/tree/nonfinite behavior, then measure the exact port with current cache/overlap unchanged. Detail below. |
| 2 | **Publish only changed cache pointer/generation entries**, one card | Current serial boundary **1.231254 ms/token**. 60–70% net removal → **0.739–0.862 ms, +2.21–2.59%**. At 50%, only +1.84%; full removal ceiling +3.74% | Medium/high lifetime risk; S/M, 1–2 days; reuse existing staging allocation | **Conditional ≥2% feasibility brief.** Need >54.405% net boundary recovery. Separate host-table construction from copy/scatter/drain before a large implementation. This is not the already-adopted 144-to-one publication change. |
| 3 | Existing **packet145 router/GDN-z order600**, two cards | Router+z diagnostic cold/warm gap **0.412 ms/half**. Recovering half → 0.206/half, +1.49%; all → +3.02%. Needs >66.78% net recovery for +2% | Existing prepared packet; no new build here; 600 MiB bank/rank already belongs to its own admission | **Pending, no ≥2% forecast.** Consume its actual verdict; no additional order600 campaign. Attention-order600 was null. |
| 4 | Sparse **post-router demand transfer while resident expert slots compute**, one card | Legacy mixed-residency penalty scaled by cache-demand proxy ≈2.35 ms/token, already an optimistic cross-identity allowance. A new 2× reduction with 0.5 ms overhead leaves ≈0.67 ms, near +2%; old 1.22× improvement leaves only ≈0.42 ms before overhead | High synchronization/cache risk; M/L, 2–4 days; bounded staging must fit current allowances | **Measurement prerequisite, not ≥2% build.** Need current tile16 sparse-miss costs and real overlap windows. Existing p125 pipeline was slower than its tile16 arm; its win cannot be counted again. |
| 5 | One-card **causal M2 verifier/MTP with shared draft-expert cache**, newly accounted host budget | Old measured M2/M1 ratio applied to current line gives **29.734 tok/s, +1.62%, ≈0.545 ms/token**, before added feedback/cache costs. Favorable one-overhead-per-pair model gives **32.688, +11.72%, ≈3.58 ms/token**, but is unsupported | High state/traffic risk; L, several days to weeks; needs revised lifetime census and draft-cache ownership | **Reopen feasibility accounting only, not p58h implementation.** RAM objection changed; max-cache device admission and causal timing remain blockers. Detailed accounting below. |
| 6 | **Same-bit scale multicast** across all eligible dense classes, two cards; possible one-card port | p140 raw optimistic 0.912852 ms/half ×20% → **0.182570/half, +1.318%**. Needs **30.14%** net transfer, versus old 45.22% for +3%. At 80%: +5.49%, a sensitivity only. One-card doubled proxy at 20% ≈0.365 ms/token, ~1.08% | Medium exactness/occupancy risk; M, 2–3 days; no unique weight bytes saved | **Below supported ≥2% bar.** p141 does not establish this transfer. Need cold, in-order, class-matched issue/shuffle evidence first. |
| 7 | A **different correction graph**, two cards: cooperative corrected-row projection with both ranks, or row-shared causal verification | A net **2–3 ms reduction in C per miss** gives **+2.56–3.88%** (≈0.43–0.65 ms pooled/token). At 20% transfer of a 3 ms raw saving: only +0.75% | Very high; L+, weeks; immutable-weight duplication/transport and full-precision private state need new admission | **Structural research target, not a supported forecast.** Must change total corrected work/critical path, not move suffix work or guess earlier without inputs. |
| 8 | Actual contiguous/slab **class placement with verified address/traffic effect**, two cards | Router/z budget as rank 3; ≤0.412 ms/half gap is only a diagnostic ceiling. No measured recoverable amount. Attention contributes another 0.363 ms/half only if a distinct physical cause is proved | Medium/high; M, 2–4 days; use existing capacity, not unbudgeted duplicate banks | **No brief yet.** Separate allocations ordered at load do not prove physical adjacency. Require evidence order600 did not exercise the proposed mechanism; do not rename its null result. |
| 9 | **IQ2 five-byte metadata cells**, either line | p140 raw 0.288595 ms/half ×20% = **0.057719/half, +0.413%** two-card; even 80% only +1.673%. One-card doubled 20% proxy ≈0.115 ms/token (~0.34%) | Medium; M, 1–3 days; same 840-byte E1 row intended, not compressed KV | **Below bar.** Must prove aligned loads/lower dependency cost; retains original FP32 arithmetic. Not a table-relocation or large-GRF retry. |
| 10 | **Producer-emitted exact BF16 RMS leaf partials**, either line | Half of p140 norm proxy ×20% = **0.038101 ms/half, +0.272%** two-card; 80% ≈1.10%. One-card doubled 20% proxy ≈0.076 ms/token | High arithmetic/nonfinite and stream-version risk; M, 2–4 days; small scratch, not a global spinning barrier | **Below bar.** Preserve rounded BF16 producer value and original 32-leaf/upper tree; no p94 duplicated reduction per consumer workgroup. |
| 11 | One-card ports of accepted **p109 small fusion / E1 scale cache / later HC-wide geometry** | p109 historical ≈0.05 ms/half → ≈0.10 ms/full token (~0.29%); E1 two-card standalone +0.28% is not a one-card forecast. HC-wide has no isolated current one-card budget | Medium; S/M per port; E1 adds **616,038,400 host bytes** and larger cache entries | **No separate ≥2% brief.** HC-wide may follow the p60 result, not be counted twice. E1 needs new max-cache admission, not just new RAM. Route/rec ports remain closed by 58r. |
| 12 | **Delta-safe fill batching/contiguous expert triples**, one card | Current **15.825 submitted fills/token** ×2 fewer calls ×3.4–5 µs ≈**0.108–0.158 ms/token**, <0.5%, before overlap loss | Medium allocator/lifetime risk; S/M; must replace host layout without duplicate full banks | **Below bar.** p125 contiguous/aligned transport was only 1.06× against older production. Do not add hidden fill-submit savings to publication recovery. |
| 13 | **New causal cache admission/policy or proved lifetime reuse for more cache**, one card | Current extra admitted cache beyond 21.55 GB: **zero** under retained bounds. An illustrative 10% cut in the 2.35 ms miss proxy saves only 0.235 ms (<0.7%), before policy cost | Medium/high; M; only independently released actual bytes can increase cache | **No ≥2% evidence.** LFU/frequency/two-hit replays do not establish a win here. Need native max-cache route/miss replay with one-position lag; no benchmark-trained placements. |
| 14 | **Exact input precomputation / prepared-buffer reuse / event-retirement batching**, either line | p137 two-card projection +0.26–0.62% (roughly 0.044–0.105 ms/token). One-card actual prepare mean 0.674 ms is an entire enclosing bucket: even erasing it barely reaches 2%; no implementation can erase all necessary input work | Low/medium; S/M; token-table memory must be charged | **Below bar / deferred.** p137 stays closed-deferred until a separate measured ≥1.5% two-card gain. p58t residency is closed. p134/58y inflated host spans cannot justify replay/host rewrites. |

Rows are a complete inventory of the concrete surviving classes found in the
requested ledgers, their deferred source notes and this source audit. Unknown
future algorithms are not counted as candidates. Per-row budgets overlap:
rank 3/8 share locality headroom; rank 1/11 share HC; rank 2/12/13 interact through
maintenance; rank 4/5/13 share cache traffic. There is no sum-of-best-cases plan.

## 1. The missing HC port has actual historical support

The [packet58z archived source closure](../packet58z-onecard-record/lineage/58x-build-source.tar.gz)
contains `packet58x-cache-capacity/build/native/main.cpp`. It has **no p60
hook**: target HC still dispatches the older low/gate/small-HC paths. This is
stronger evidence than `selection.json: hc=production`: packet60 also retained
that selection string while changing unconditional dispatch.

[Packet58j](../packet58j-onecard-port/README.md) ported down/route/recurrence;
[58r](../../../../notes/2026-10-18-own-runtime-packet58r-result.md) tested
route-fast plus rec-both-plus. Its inconclusive +0.37% does **not** test HC
fusion. Conversely, p60 is already included in the two-card record; its gain
cannot be claimed there again.

[Packet60](../packet60-hc-fusion/README.md) uses three kernels per HC side:
norm; low/activation plus inject; gate plus mix. Six instead of fourteen per
layer removes 384 commands over 48 layers while retaining BF16 intermediates,
FP32 chains, exact norm trees, sticky errors and ordinary layer hooks. Final
HC and draft are outside this port. Packet46's low-parallelism fusion,
packet67's four-stream geometry, packet94's repeated reduction, and packet117's
sigmoid change are different, closed mechanisms.

I recomputed saved `screen/evidence/packet56-a/run/*/receipt.json` and
`screen/evidence/packet60-a/run/*/receipt.json`, excluding incident64. Each has
12 complete 128-event requests and **936 hits/1,188 intervals**. Both have
bounded-spin=0 and the same route/rec selection. The class-balanced rates are
**46.7922355 → 48.8726114 tok/s**. Their mean command changes are:

| Historical 23/25 split, host-envelope ms | Packet56 | Packet60 | Reduction |
| --- | ---: | ---: | ---: |
| Rank0 next half A, 23 layers | 16.434104 | 15.659730 | 0.774374 |
| Rank1 half B, 25 layers | 15.962052 | 15.411870 | **0.550182** |
| Rank0 correction C, misses | 14.503722 | 13.835908 | 0.667814 |
| Draft D | 1.922168 | 1.918121 | 0.004047 |

These are older separate screens, not a fresh matched one-card comparison or
a rigorous isolated latency estimate. Do not attribute the larger combined
packet61 HC-plus-spin gain solely to HC. Taking the weakest half reduction,
`0.550182 * 48/25 = 1.05635 ms`, gives a useful port hypothesis. A 25% haircut
leaves **0.792 ms**, about +2.37% on 29.26. The conservative 0.8–1.05 planning range sits below p60's original
1.2–1.92 ms full-model engineering estimate; the estimate is not added to
the historical screen evidence.
At only 50% transfer of that historical weak-half saving, the port saves
0.528 ms and fails 2%. This is the central uncertainty, explicitly retained.

Brief boundary: port **only** this dispatch and arithmetic into a new copy of
58z's source closure. Keep tile16, all 48 layers, cache size, cache policy,
overlap, token cap and oracle unchanged. Prove all 48 labels, both sides,
absorbed prepared slots, BF16-writer invalidation, error behavior, exceptional
values and request reset. Use real-shape synthetic CPU fixtures before any
future device work. A short exact device screen then decides; do not spend a
week on geometry if the net saving is below 0.670 ms/token.

## 2. Current one-card receipts expose a smaller, distinct cache boundary

This study joins the **actual 58z WS128** cache log to request order and generated
events 2–100. Cumulative counts are differenced against the immediately previous
position; prefill and first events are not charged to the 99-interval window.
All 2,386 position rows join; the selected 1,188 rows give:

| Unprofiled current-line field | Mean per selected position |
| --- | ---: |
| Submitted cache-fill payload | **31,369,352 bytes** |
| Submitted fills | **15.824916 experts** |
| Table publications | **1.000000** |
| Publication logical payload | **1,179,648 bytes** |
| Publication enclosing host span | **1.231254 ms** |
| Token prepare enclosing span | 0.674013 ms |
| Host enqueue span, overlapping device work | 7.588130 ms |
| Host waits, overlapping other recorded spans | 20.925659 ms |

These are attribution counters, not a new speed result. In the asynchronous
engine **fills do not equal current misses**: planning lags, transactions can
remain pending, and a safe table can expose host pointers. No hit rate or PCIe
read bandwidth is derived from 31.37 MB. In particular, the old 58i identity's
65.46 MB/33fills and 93.12% inferred hit rate cannot be copied onto 58z.

The source executes `cache_boundary()` before the next position's compute.
`publish_cache_table()` visits 144 banks ×512 entries, rebuilds all pointers and
generations, uploads 1.18 MB, scatters and drains. The inherited publish helper
already combines the old 144 uploads into **one memcpy plus one scatter**.
The current timer includes CPU construction, submission, transfer/scatter and
its drain. It does not tell us their separate costs. This is a real serial
boundary, but not proof all 1.231 ms is removable.

The new mechanism records the exact changed IDs while `Cache::prepare` already
updates fills and victims. Revoke victim pointers and newly assigned generations
before overwrite; publish filled device pointers only after completion; leave
unchanged entries byte-identical. Emit a bounded patch list rather than scan and
retransmit every bank. Maintain the existing no-live-reader boundary and real
terminal event. Include both evicted IDs **and** filled IDs, including generation
changes where the pointer stays host-backed. Full initialization/reset still
uses a full table; overflow must have a bounded full-table fallback.

This changes work proportional to all 24,576 experts into work proportional to
the transaction's changed entries. It is distinct from 58v's accepted coalescing,
58i's hidden-DMA proposal and 58y's instrumented host rewrite. Exactness concerns
are stale generations, overwritten victims, late fills, duplicate dirty IDs,
request boundaries and teardown, not approximate model arithmetic.

Replaying a uniform fraction of each prompt's **own measured publication span**:

| Assumed net boundary recovery | Projected gain |
| ---: | ---: |
| 30% | +1.093% |
| 50% | +1.835% |
| **54.40493%** | **+2.000%** |
| 60% | +2.210% |
| 70% | +2.588% |
| Impossible free publication | +3.739% |

The next brief must establish whether the uninstrumented boundary can fall
from 1.231 to roughly **0.56 ms/token** without making fills later. A CPU mock
can validate patch equivalence and time table construction; it cannot time the
device part. A minimal causal screen is still required. If most cost is fixed
submission/drain rather than full-table work, stop this design at that finding.

## 3. What the cold/warm evidence actually changes

[Packet141's result](../../../../notes/2026-10-18-own-runtime-packet141-result.md)
is a coordinator reading of raw events; its analyzer refused on touch-count
bookkeeping. There is no qualified p141 gate pass and no repair proposed here.
It shows diagnostic cold/warm class costs of attention 1.137/0.774,
router 0.536/0.289 and GDN-z 0.707/0.542 ms/half. Its `attention` label is the
dense attention-output class, **not** packet128b's entire 4.898 ms attention group.

This challenges using one warm micro as an absolute engine cost for all classes.
It does **not** measure `engine saving / micro saving` for N1 or prove the gap
is recoverable. Naturally ordered half wall 11.90 ms versus forced-cold 11.76 ms
also warns against a simple additive cold-penalty model. Down-tile16's successful
transfer and gate/up-tile16's failed transfer remain the better mechanism-matched
examples. Neither a universal 20% nor a universal 80% factor is a physical law.

[Packet142 attention-order600](../../../../notes/2026-10-18-own-runtime-packet142-attention-result.md)
was exact and null:58.585/58.620 versus 58.624/58.634/58.636 controls.
[Packet145](../packet145-router-gdnz-layout/README.md) tests the same ordering
mechanism on router and GDN-z and remains pending at this review. Its allocations
do not guarantee physical adjacency. A positive result must be read at its
measured magnitude; a null closes that implementation, not all imaginable
memory-system work. Any later slab/tiling proposal needs a measured distinct
cause before a new layout is built. Warmed prompts, pre-touch timing and cache
eviction sweeps never become headline workloads.

For N1, the current 2% threshold is0.275155/0.912852 = **30.14% transfer**.
The lower requested bar changes the number, not the missing mechanism evidence.
The six-group0.912852 raw budget itself overstates eligible work by including
some unquantized suboperations; same-bit multicast removes duplicate issues,
not unique weight bytes. p81 already showed why lower load counts are not a
speed proof. N2/N3 also stay below the supported bar. No p140 arm is quietly
reopened by substituting a favorable transfer percentage.

## 4. One-card miss bandwidth after the bigger cache

[58y](../packet58y-onecard-attribution/analysis/report.md) has a20.7657 ms
compute-tail bucket including zero-copy experts. Its tracing added about 8 ms/token
and it lacks isolated miss stalls. That entire tail is not a transport budget.
[58i](../packet58i-onecard-attribution/ATTRIBUTION.md) had mixed-host/all-host
scaled remote penalties 3.42/5.13 ms on the older 18 GB, non-tile16 line.
[58x's independent replay](../packet58x-cache-capacity/ADMISSION.md) predicts
miss-demand ratio 41.283/60.160 =0.6862 at max cache. Applying that ratio gives
2.35/3.52 ms as **legacy sensitivities**, not current miss measurements. Tile16
already improves down's host access; no second credit is taken for that change.

[p125](../../../../notes/2026-10-18-own-runtime-packet125-micro-result.md)
measured zero-copy tile16 at 187.0/185.8 µs, faster than BCS-pipeline3 at 192.2/194.9.
The old 8.75 GB/s figure is useful-byte throughput of a fixture, not physical PCIe
bandwidth of the current full model. A new demand-copy design must compare
against **tile16 with actual sparse misses and resident neighbors**.

The remaining exact opportunity is after the real router: copy known missing
expert bytes on BCS while resident slots compute, then calculate missing slots
and combine in the original route order. It replaces later fills rather than
duplicating them. New router readback, split dispatch, policy, safe publication
and PCIe contention must all be charged. It is not p138's prediction of unknown
future-layer routes; all 45 of those modeled arms exceeded their copy windows.

With the cautious legacy 2.35 ms allowance, a 2× cut saves 1.175 ms gross; subtract
0.5 ms new overhead and only 0.675 ms remains. **Neither 2× nor0.5 ms is measured.**
The observed old 1.22× cut gives only 0.424 ms gross, already below 2% before overhead.
Thus a current sparse-miss causal measurement is worthwhile if cheap, but there
is no evidence-supported ≥2% transport implementation brief yet. Preserve the
negative micro; do not rerun its old pipeline with a lower pass threshold.

## 5. One-card MTP: changed RAM assumption, unchanged need for a new graph

[58h](../packet58h-onecard-mtp/FEASIBILITY.md) closed a+20% proposal under
the old 24.0128 diagnostic line and conservative full-device shadow accounting.
Its reasons must now be separated.

**Host memory:** [58u](../packet58u-host-admission/README.md) replaced the
26.409 GB shadow assumption with a measured bound of about 0.658 GB plus retained
margins. Current 58x timing admission is98,989,727,744 bytes. Merely carrying over
58h's conservative 3,336,747,140-byte shared-cache increment gives about
**102,326,474,884 bytes**, plausibly below the old 121.65 GB requirement. This is
not a new admission: MTP adds mappings, draft conversions, two-row private
state and a different lifetime; the 0.658 GB observation belongs to the old
workload. Keep the 4 GiB shadow stop,4 GiB margin and 8 GiB reserve. No host setting,
offlined block or swap allowance is changed to make it fit.

**Device memory:** cache expansion spent the old headroom. Current conservative
bound 29,963,128,848 plus 512 MiB driver allowance leaves only **240 bytes** below
the 30.5 GB post-reserve floor. 58h's shared-cache design adds **190,973,952 bytes**
to conservative device accounting; its fully resident draft adds 3,336,652,800.
Neither fits the current max-cache bound unchanged. Prove new actual lifetime
reuse or explicitly cost a smaller cache as a separate configuration. Never
shrink the cache silently and still claim a prediction for 58z.

The draft has3,326,953,472 bytes of weights, including 3,145,728,000 routed-expert
bytes. Those INT8 draft experts cannot alias the target's IQ3 bytes. The head
prefix can share the existing expanded full head. The969,719,582-byte private
state reservation fits the existing 1 GiB transaction allowance and must not be
charged twice, but its implementation and peak lifetime still need proof.

**Timing on 29.259764:** retain 58h's explicitly transferred `a=0.787401575`,
`D=1.794747301 ms`, `R=0.980923 ms` and unchanged target verification:

```text
cycle = D + V2 + (1-a)*R + new_feedback_and_cache_cost
rate  = 1000*(1+a)/cycle
```

| Assumption for V2 on current one-card line | V2 ms | Before new feedback/cache costs |
| --- | ---: | ---: |
| Transfer measured differing-route M2/M1=1.700307 | 58.110755 | **29.73351 tok/s, +1.619%** |
| Pay all old overhead once per pair; add only device M2−M1=18.5012 ms to 34.176625 | 52.677825 | **32.68773 tok/s, +11.716%** |
| Existing causal71c combined command proxy | 63.646967 | About 27.23 tok/s; even this omits one-card penalties |

At the new+2% bar, `V2 + new_feedback_and_cache_cost` must be **≤57.886273 ms**.
The measured-ratio transfer misses by 0.224483 ms/cycle even before extra work.
The favorable overhead-once scenario leaves 5.208447 ms/cycle, but no current
receipt proves it. The old+20% gate is not retroactively changed or passed;
this is a new feasibility question on a different line.

The largest one-card structural possibility is a genuinely causal two-row
verifier with shared weight reads, original per-row arithmetic, bounded state
ownership and correct draft feedback. Different routes, rejected rows, draft
cache pollution and full BF16 rollback all count. It must improve the measured
M2 graph, not re-run packet71's expensive recursion under new RAM accounting.
Its rough range above is an engineering sensitivity spanning a loss to+11.7%,
not an earned prediction. First deliver a complete lifetime/cycle design; only
then consider the much larger implementation.

## 6. Larger two-card change and the closure map

With no supported new≥2% two-card candidate, the largest concrete structural
target is **the extra corrected half on misses**. During C the draft branch
often finishes early. A new graph might split exact output rows of corrected
projections across both devices and retain each row's original arithmetic,
or verify consecutive causal rows with shared weight loads and bounded state
deltas. These require actual weight placement and communication diagrams.
They are not the closed 25/23 layer move or suffix interleave.

The rough value target is **2–3 ms net off11.819 ms C**, giving **60.30–61.08 tok/s**
from actual interval replay (+2.56–3.88%). That net target already has to include
new sends, synchronization, row assembly, draft interference and allocation
costs. Giving a hypothetical 3 ms kernel reduction only 20% transfer yields
0.6 ms off C and **+0.753%**. There is currently no evidence for the required net
reduction, no large spare duplicate-weight budget, and no claim that rank 1 can
read rank 0's resident weights for free. This is a weeks-scale original runtime
research task, not the next small brief. A split that changes a row's FP32
summation order fails the unchanged oracle.

For completeness, these are the closed/adopted classes excluded from new gain:

| Existing family | Current decision; what would actually be new |
| --- | --- |
| HC fusion60/61, early accepted route/recurrence/HC-wide, p100 down-tile16,109 fusion,114 prefix,131b banks | Already on two-card record. Only demonstrated absent one-card ports can count again. One-card tile16/58v overlap/58x capacity are already banked. |
| p25/28/33/52/53/53b/65/67/72/73/74/81/90/93/95/99/102/104/107/112/113/115/116/117/119 | Old geometry, packed dense/head formats, grid placement/prefetch, large-GRF, duplicated norms, recurrence/QSA/sigmoid schedules remain closed. p140's source-level N1/N2/N3 distinctions are retained; no generalized roofline subtraction reopens them. |
| p58k/58r route+rec,58t resident lookups,58i LFU/frequency/two-hit,125 transport,138 future-route prediction | Different caches do not erase prior losses. New dirty-entry publication and missing HC dispatch were not those arms. Demand-copy requires the different sparse/current-route overlap proof above. |
| p76/78 accepted housekeeping;92 reply-first;134 enqueue diagnosis;128/128b/58y instrumentation | Moving existing work later or eliminating fictitious profile overhead has no supported gain. Current preparation/copy clocks, not distorted host buckets, set budgets. |
| p79 draft relocation;120/123 layer moves;127 suffix rows;130 early suffix | No demonstrated spare rank 0 time. A new cooperative correction graph must reduce exposed work, not shift the same work into the next speculation. |
| p121/144 restore, correction preparation, miss B elimination | On136, removing all restore gives **+0.691%**; restore+all 0.102 ms preparation <0.83%; free miss-only B <0.92%. These stay below 2% too. |
| p83 draft formats/prefix trades;108 draft loads;122 draft-HC;129 faithful draft weights | Existing draft micro savings are small; acceptance changed only+0.08 pp in129. New precision is not an exact-target speed claim; no draft-quantization sweep. |
| p126 earlier guessed draft;132 second sibling choice;146 lookup |126 lacks measured recoverable ordinary-run wait.132 held-out expert-only model is **+1.77%**, and its primary total-cost model prefers never; it does not pass the new2% question either.146 remains policy-closed; no n-gram/prompt-history escape. |
| p137,139/143 prepared bundles | Deferred/pending bookkeeping is not a performance source.137 may stack only after its recorded prerequisite; no autonomous repair or queued duplicate here. |
| Larger batch/concurrency, prefill, long context, start time | Valid future objectives with the same exact arithmetic. They do not supply a percentage against either current one-user decode record; measure separately, full 16-bit KV. No invented crossover point. |

Deleting all remaining free control gaps, completing the full draft head or
retuning the old confidence sample likewise fails a supported 2% case. Packet144's
unrealistically free rescue of every eligible out-of-prefix miss was only+1.233%.
At2%, a truly new draft would need at least 3.149 pp independent acceptance gain
**before** its extra cost, or a measured 0.423 ms draft-only reduction. Those are
research requirements, not permission to train on the benchmark or change the
target. New prompt/KV/response reuse, compressed KV, lower-precision target,
nonverified speculation and altered FP32 trees are outside this exact inventory.

## Execution order and stop conditions for future briefs

1. The coordinator finishes the already-prepared 145 question. Preserve the
   attention null and raw diagnostic limitations. No queue is changed here.
2. New one-card HC-only port brief: source/lifetime/byte proofs, exact short
   screen, then current-record comparison. Prefer this concrete work to a
   speculative rewrite of all 20.8 ms in58y.
3. New changed-entry-publication feasibility brief: CPU equivalence and a
   minimally perturbing boundary split. Require net recovery>54.405%, or a
   measured≥2% engine gain, before growing it into a record candidate.
4. If those miss their gates, move to current sparse-miss causal costs and
   MTP lifetime accounting. Do not rerun closed micros, retune benchmark
   prompts, relax previous kill gates or launch a broad geometry sweep.

Any future speed verdict needs at least two fresh starts, complete varied
cold-response suites with cached_tokens=0, and full unchanged-target token,
layer/state and fresh-process determinism gates. Loaded immutable weight caches
and compiled kernels are valid; repeated-prompt benefits are not. Compare the
same target, cache capacity, precision, context and output cap; include every
first prompt and disclose host contention/control drift. Keep 128-token screening
and strict512 promotion status distinct. Packet147 authorizes no device launch,
server, settings change or publication.

## Evidence audit and replay

Read the closed ledger and **all 182 repository DO-NOT-REPEAT.md paths**
(173 unique contents, 417,999 bytes), including non-own-runtime lanes and vendored
duplicates. Scanned all 141 October 18 notes; read the relevant result notes and
110/128b/134/135/140/141/144/58i/58y analyses, then checked current archived
source and raw record counters. Later completed results take precedence over
older preparation paragraphs that still say pending. No deletion/cleanup is
performed by this audit.

The negative-index manifest is sorted rows `[path, byte_length, sha256]`, compact
JSON with separators `(',', ':')`, UTF-8, no trailing newline. Its SHA256 is
`aeb0f493070624d8f01ab40a99707f0d25921464c84e6b956a4c2de8d5dfeaf1`.
All 182 hashes were unchanged on the audit recheck. The initial pull refused
unrelated dirty work; fetch confirmed HEAD=origin/main. Existing dirty 128b and
58y analyses were read as observed working-tree evidence, not edited or adopted
as clean committed results. Key input hashes and a standard-library-only replay
are retained below so the new arithmetic is reviewable without model payloads.

The saved-record replay passed, using about **104 MiB peak RSS** (106,180 KiB),
under the 4 GiB cap. Input hashes and local Markdown links were checked. The
calculator writes only stdout; no frozen analyzer was run in its write mode.
The historical HC/control prompts, output hashes, split23, spin setting and
zero-cache counters also match pairwise. The current one-card native receipt
confirms `profiling=false`, `timing=token`. A pre-commit fetch found shared main
and origin/main both at `aa39bad5e306d8b41dfeffad64dcabb0aec109b0`; the key
input hashes and all negative-index hashes still matched the original audit.

The same manifest encoding for the 141 pre-existing October 18 notes has
SHA256 `10a8548e0a5d1e1c4f469ad6290c7918b88bc62384cbe0d87163b39d1e27cc0c`. The 24 historical HC/control request receipts
have manifest SHA256 `8e005dd81b2f94e2d3edfc1f5adb942f3f38188de56cfd8fd2388c9ea9e8f3b3`.

<details>
<summary>Key evidence SHA256 values (paths relative to repository root)</summary>

```json
{
  "experiments/own-xpu-runtime/ops/screen-cleanup/closed.json": "98492d0f44cde5546438aeae0f7e5ea02bd2fb90adabb2e611fd01b9dd95a89d",
  "experiments/own-xpu-runtime/stage2/packet110-class-roofline/ROOFLINE.md": "7c56dedf9fea713fee24c187a28800224b1ec41ace32bbf603120642062ffaab",
  "experiments/own-xpu-runtime/stage2/packet128b-attribution/BUDGET.md": "a4d87c75433f687550666bf16368b8690a9bdae05314540e7cadf921e781c1cd",
  "experiments/own-xpu-runtime/stage2/packet134-submission-stalls/ATTRIBUTION.md": "6352455aedabf19912b516c3c895d1795ffe56e1aa3f7c6e46d3de1e2c5e077a",
  "experiments/own-xpu-runtime/stage2/packet135-critical-path/ANALYSIS.md": "c8d1157521f1808a0a1ae4d44330b96d81d79ff1e5cf6b1453354144cd47a287",
  "experiments/own-xpu-runtime/stage2/packet140-body-lever/ANALYSIS.md": "5220bd14849db80699bdf955a296530f53290a61959d76e174ef8abeeb7e42be",
  "experiments/own-xpu-runtime/stage2/packet144-miss-path/ANALYSIS.md": "19ba528112a0fdceca72dac0781f8966e69ba21ba93629405c8bc950baf7694c",
  "experiments/own-xpu-runtime/stage2/packet58i-onecard-attribution/ATTRIBUTION.md": "f0de325f9c6e1c5b41a5df04fe34006008bc7f2210bfa44f5a52177b6ee447ae",
  "experiments/own-xpu-runtime/stage2/packet58y-onecard-attribution/analysis/report.md": "805ac2b763935b073fa21b719b32aadbf298bd1dcde383b19df7c336f8c955b7",
  "experiments/own-xpu-runtime/stage2/packet58h-onecard-mtp/FEASIBILITY.md": "c005d7fd428220fa0ac6d9c98a7d6c631a7cced280577477880d263e17ffaec4",
  "experiments/own-xpu-runtime/stage2/packet58u-host-admission/README.md": "9c083d72702ddb0adc2930cd1d0189ad0c54c05710b65af97e330182475f9080",
  "experiments/own-xpu-runtime/stage2/packet58x-cache-capacity/ADMISSION.md": "d1708d404783ef2283fd6d49b0b6466df44d9a99070341807b65d66425c15bf0",
  "experiments/own-xpu-runtime/stage2/packet136-record-bundle/submission/prepared-a/result.json": "bb332db12448927db479141661938c156f9b85c85bb9d6d27612e3f3f7c9fc38",
  "experiments/own-xpu-runtime/stage2/packet136-record-bundle/submission/prepared-a/evidence.json.gz": "e768ee3dc3d5100312d3226c273b3e02a569f99aedf9e9894f5eec80d93e7122",
  "experiments/own-xpu-runtime/stage2/packet58z-onecard-record/submission/prepared-a/result.json": "69ea4d606b4c11fb4b13c1eb319f924eaf74d67da4bd177a5940ac9eb1c35ad6",
  "experiments/own-xpu-runtime/stage2/packet58z-onecard-record/lineage/58x-build-source.tar.gz": "efd357edc751e929553880b2638cada3fedb869d2f8584c51ce9bc2646d3ab9f",
  "experiments/own-xpu-runtime/stage2/packet58z-onecard-record/evidence/card0-58z-a/WS128/summary.json": "4bd5ddfd3588b5cabd4685a90d49281dcd957ac2008e76fecd3b7a3df5e1136b",
  "experiments/own-xpu-runtime/stage2/packet58z-onecard-record/evidence/card0-58z-a/WS128/window.json": "46effe5c6ca5ca093338276c5a4d0af0e603f7657a54d6c0b70cf1762d681da1",
  "experiments/own-xpu-runtime/stage2/packet58z-onecard-record/evidence/card0-58z-a/WS128/run/run/cache.jsonl": "cc181ecff1d3ae99c82565c6487e48cf0b596ce97b6b951a6d32501619d0a743",
  "experiments/own-xpu-runtime/stage2/packet126-early-draft/method/p85_model.py": "6627ffa350361a85aed5160f1f5738409cb23bab4f9ca1f34fea7317a0b63ad4",
  "experiments/own-xpu-runtime/stage2/packet60-hc-fusion/README.md": "9e50feea89640c08db50017b99239910514ae8f0dce708546ea784751b0cbf8f",
  "experiments/own-xpu-runtime/stage2/packet145-router-gdnz-layout/README.md": "3f8fda6e9eabbf60b388ad9650f1899f02901008e86d1605c488b4f3d51ce9e3",
  "notes/2026-10-18-own-runtime-packet141-result.md": "2f2d3226ed1fa91b9c365c3b710ff9830b6d5f0a6b6569a5cbda691f240be0a6",
  "notes/2026-10-18-own-runtime-packet142-attention-result.md": "71b9b2b481dacc1a5cefc0b8c5e2e06057baadbde3f87b0c4a3772c6d6ccb86e"
}
```

</details>

Run this Python block from the repository root under
`nice -n 19 taskset -c 8-15,24-31 bash -c 'ulimit -v 4194304; python3 -B /tmp/packet147-replay.py' </dev/null`.
Save only this block to that temporary file. It reads saved receipts and the two
AST-extracted pure interval functions; it does not import a runtime, read weights,
write into a packet or start a device. A failed source assertion stops the replay.

```python
import ast, base64, gzip, hashlib, json, statistics as st
from collections import defaultdict
from pathlib import Path
S=Path('experiments/own-xpu-runtime/stage2')
method=(S/'packet126-early-draft/method/p85_model.py').read_bytes()
assert hashlib.sha256(method).hexdigest()=='6627ffa350361a85aed5160f1f5738409cb23bab4f9ca1f34fea7317a0b63ad4'
tree=ast.parse(method)
scope={}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('duration','intervals')],type_ignores=[]),'saved-method','exec'),scope)
def balanced(pairs):
    c=defaultdict(list)
    for cls,v in pairs:c[cls].append(v)
    return st.median(st.median(v) for v in c.values())
def aggregate(requests,fn):
    return balanced((cls,99000/sum(fn(r) for r in rr)) for cls,rr in requests)
def model(r,half=0,c=0,d=0,restore=0,rescue=0):
    ready=max(max(0,r['D']-d),max(0,r['R']-restore)+max(0,r['C']-half-c))
    return ready+max(r['B']-half,r['A']-half+r['spec_start_offset_ms'])+r['unresolved_control_gaps_ms']-rescue*(max(r['D'],r['R']+r['C'])-r['D'])
P=S/'packet136-record-bundle/submission/prepared-a'
members=json.loads(gzip.decompress((P/'evidence.json.gz').read_bytes()))['members']
req=[]
for k,v in sorted(members.items()):
    if not(k.startswith('WS128/run/repeat-1/') and k.endswith('/receipt.json')):continue
    raw=base64.b64decode(v['raw_base64']);assert hashlib.sha256(raw).hexdigest()==v['sha256']
    r=json.loads(raw);assert r['passed'] and r['cached_tokens']==0
    req.append((r['prompt_class'],scope['intervals'](r)))
rows=[r for _,rr in req for r in rr];assert len(rows)==1188
assert max(abs(model(r)-r['elapsed_ms']) for r in rows)<1e-7
rate=aggregate(req,model)
assert abs(rate-json.loads((P/'result.json').read_text())['primary_metric']['value_tok_s'])<1e-8
def gain(**kw):return 100*(aggregate(req,lambda r:model(r,**kw))/rate-1)
def thresh(key):
    lo=0;hi=10 if key!='rescue' else 1
    for _ in range(70):
        mid=(lo+hi)/2
        if gain(**{key:mid})<2:lo=mid
        else:hi=mid
    return hi
out={'two':{'rate':rate,'reciprocal_ms':1000/rate,'threshold2':{k:thresh(k) for k in ['half','c','d','rescue']},'scenarios_percent':{str(kw):gain(**kw) for kw in [dict(half=.912852*.2),dict(half=.912852*.8),dict(half=.288595*.2),dict(half=.288595*.8),dict(half=.190504*.2),dict(half=.412),dict(half=.412*.5),dict(c=.6),dict(c=1.5),dict(c=2),dict(c=3),dict(d=.4),dict(d=.6),dict(rescue=.15),dict(restore=100)]}}}
P1=S/'packet58z-onecard-record/submission/prepared-a/result.json'
one=json.loads(P1.read_text())['primary_metric']['value_tok_s'];t=1000/one
out['one']={'rate':one,'reciprocal_ms':t,'two_percent_ms':t-t/1.02,'uniform_cuts_percent':{str(x):100*(t/(t-x)-1) for x in [.1,.5,.67,.8,1,1.2,1.5,2]}}
hist={}
for tag in ['packet56-a','packet60-a']:
    data=[]
    for p in sorted((S/'screen/evidence'/tag/'run').glob('*/receipt.json')):
        r=json.loads(p.read_text())
        if 'prompt_class' not in r or len(r.get('generated_token_completion_timestamps',[]))<100:continue
        data.append((r['prompt_class'],scope['intervals'](r)))
    rr=[r for _,a in data for r in a];assert len(rr)==1188
    hist[tag]={'rate':aggregate(data,lambda r:r['elapsed_ms']), 'components':{k:st.mean(r[k] for r in rr if r['hit'] or k in ['A','B','D']) for k in ['A','B','D']},'C_miss':st.mean(r['C']for r in rr if not r['hit']), 'hits':sum(r['hit']for r in rr)}
out['historic_hc']=hist
a=.787401575;d=1.794747301;r=.980923
for name,v in [('ratio',t*1.700307),('fixed_overhead',t+18.5012)]:
    cost=d+v+(1-a)*r
    out['one'][name+'_mtp']={'V2_ms':v,'cycle_ms':cost,'rate':1000*(1+a)/cost,'gain':100*((1000*(1+a)/cost)/one-1),'extra_budget_for_2percent_ms':1000*(1+a)/(1.02*one)-cost}
out['one']['mtp_required_V2_ms_for_2percent']=1000*(1+a)/(1.02*one)-d-(1-a)*r
B=S/'packet58z-onecard-record/evidence/card0-58z-a/WS128'
summary=json.loads((B/'summary.json').read_text())
assert summary['passed'] and summary['arithmetic']=='iq3-p49-split32-v1'
cache=[json.loads(l) for l in (B/'run/run/cache.jsonl').read_text().splitlines()]
window=json.loads((B/'window.json').read_text())
for rel in ['run/run/cache.jsonl','summary.json']:
    if rel in window['native_files']:
        assert hashlib.sha256((B/rel).read_bytes()).hexdigest()==window['native_files'][rel]
idx=0;native=[];prompts=[];pubprompts=[]
for request in summary['requests']:
    assert request['passed'] and request['cached_tokens']==0
    prompt=request['prompt_id'];p=B/'run/run'/prompt
    pre=[json.loads(l)for l in (p/'prefill-timings.jsonl').read_text().splitlines()]
    gen=[json.loads(l)for l in (p/'timings.jsonl').read_text().splitlines()]
    assert len(pre)==request['prompt_tokens']-1 and len(gen)==128
    prompt_native=[]
    for timing in pre+gen:
        c=cache[idx];prev=cache[idx-1] if idx else None;idx+=1
        assert c['position']==idx
        if timing['kind']=='generated_token' and 2<=timing['generated_index']<=100:
            row=dict(timing,**{k:c[k]-prev[k] for k in ['fill_bytes_total','fills_total','publication_uploads_total','publication_bytes_total','publication_host_ms_total']})
            native.append(row);prompt_native.append(row)
    counter=json.loads((p/'cache-stats.json').read_text())
    assert counter['fill_bytes_total']==cache[idx-1]['fill_bytes_total']
    ts=request['token_timestamps'];ms=1000*(ts[99]-ts[0])/99
    prompts.append((request['prompt_class'],ms))
    pubprompts.append((request['prompt_class'],ms,st.mean(r['publication_host_ms_total'] for r in prompt_native)))
assert idx==len(cache) and len(native)==1188
def onegain(cut):return 100*(balanced((cls,1000/(ms-cut))for cls,ms in prompts)/one-1)
assert abs(onegain(0))<1e-8
lo=0;hi=2
for _ in range(70):
    mid=(lo+hi)/2
    if onegain(mid)<2:lo=mid
    else:hi=mid
out['one']['per_prompt_2percent_ms']=hi
out['one']['per_prompt_uniform_cuts_percent']={str(v):onegain(v) for v in [.67,.8,1,1.2,1.5,2]}
out['one']['native_means']={k:st.mean(r[k]for r in native) for k in ['fill_bytes_total','fills_total','publication_uploads_total','publication_bytes_total','publication_host_ms_total','wall_ms','prepare_ms','enqueue_loop_ms','wait_ms']}
out['one']['native_fill_is_not_current_miss_count']=True
def pubgain(f):return 100*(balanced((cls,1000/(ms-f*pub)) for cls,ms,pub in pubprompts)/one-1)
lo=0;hi=1
for _ in range(70):
    mid=(lo+hi)/2
    if pubgain(mid)<2:lo=mid
    else:hi=mid
out['one']['publication_fraction_for_2percent']=hi
out['one']['publication_recovery_percent']={str(f):pubgain(f) for f in [.3,.5,.6,.7,1]}
print(json.dumps(out,indent=2))
```
