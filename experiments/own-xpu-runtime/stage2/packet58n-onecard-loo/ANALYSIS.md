# Packet58n: the one-card bundle loss and a single-lever screen

CPU analysis, 2026-10-18. **The observed loss is dominated by slower host
preparation with major page faults, not additional expert-cache misses.**
The receipts cannot establish which change caused that host state, or assign
the bundle's loss to an individual kernel. Prepare a **down-tile16-only**
screen: its unchanged one-card K1 implementation has a concrete positive
mechanism and improves the retained host-read cases in both fresh fixtures.
No device run was made for this analysis.

## Identity and metric

Inputs are frozen packet58k's `evidence/card0-screen-b/{production-before,port}`:
one B70, card 0, Unsloth UD-IQ3_XXS quantized compressed model, packet49
`iq3-p49-split32-v1` arithmetic, plain target-only decode, BF16 KV, context
4096, twelve fixed prompts once at 128 generated tokens, zero reused prompt,
KV or response tokens. Immutable expert weights may remain cached between
requests. Both arms match every output token. Production-after was cancelled;
this is an incomplete bracket, not a controlled three-arm speed verdict.

| Statistic from the same retained timestamps | Production | Bundle | Change |
| --- | ---: | ---: | ---: |
| All-prompt median, as quoted in the brief | 24.969353 tok/s | 22.181405 tok/s | −11.17% |
| Median of six class medians, registered primary | 24.888137 tok/s | 21.927475 tok/s | −11.90% |

Each request uses **99 / (timestamp 100 − timestamp 1)**. The numbers in the
brief are the all-prompt statistic, not the class-balanced statistic. No
historical receipt, record or headline is changed here. The 128-token screen
does not pass the strict 512-token final gate, fresh-process determinism gate
or retained-layer byte gate.

## What the receipts resolve

[analyze.py](analyze.py) joins all **2,386 positions** by request order, token
index and cache epoch: 850 prefill and 1,536 decode. It checks cumulative
cache counters, output identities, native file hashes and H2D/D2H counts.
All cache fill counts, fill bytes, eviction counts and resident bytes are
identical position by position. The following means use only generated
positions **2–100**, 1,188 positions matching the timing numerator.

| Mean per charged token | Production | Bundle | Bundle − production |
| --- | ---: | ---: | ---: |
| Complete token step | 39.9414 ms | 45.1393 ms | +5.1979 ms |
| Host preparation | 0.5835 ms | 8.4143 ms | **+7.8308 ms** |
| Host enqueue loop | 7.5737 ms | 7.2980 ms | −0.2757 ms |
| Host waits | 26.2238 ms | 24.3890 ms | −1.8348 ms |
| Cache planning/fills/publication | 7.1072 ms | 6.9672 ms | −0.1400 ms |
| Selected transfer helper spans | 0.4198 ms | 0.7637 ms | +0.3439 ms |
| Token step minus cache timer | 32.8342 ms | 38.1721 ms | +5.3379 ms |
| Major page faults | 0.1263 | **12.7020** | +12.5758 |
| Minor page faults | 16.8973 | 4.3013 | −12.5960 |
| Kernel submissions | 1,790 | 1,646 | −144 |
| Host waits, count | 8 | 8 | 0 |
| Expert fills / evictions | 33.0051 / 32.6397 | identical | 0 |
| Expert fill payload | 65.456571 MB | identical | 0 |

These timers **overlap**: preparation contains upload waits, cache time
contains waits and publication, and CPU submission overlaps GPU execution.
Do not add the rows as exclusive costs. Subtracting the preparation span from
the token wall leaves a remainder that is about **2.63 ms smaller** in the
bundle; that remainder is not isolated GPU compute. No corrected throughput
is claimed by subtracting page faults or preparation from timestamps.

The fault/preparation relationship is strong within the bundle (Pearson
correlation **0.9853** across those positions). Every prompt has more host
preparation and major faults; this is not one unusually slow prompt:

| Prompt | Production prepare ms | Bundle prepare ms | Production major faults | Bundle major faults |
| --- | ---: | ---: | ---: | ---: |
| incident-retrospective | 0.604 | 9.971 | 0.212 | 14.990 |
| code-review | 0.633 | 9.095 | 0.232 | 13.848 |
| customer-email | 0.636 | 9.491 | 0.253 | 14.263 |
| sql-debugging | 0.729 | 9.770 | 0.495 | 14.576 |
| release-plan | 0.560 | 8.258 | 0.020 | 12.485 |
| benchmark-analysis | 0.543 | 7.894 | 0.040 | 11.919 |
| architecture-tradeoff | 0.557 | 7.024 | 0.071 | 10.566 |
| bug-report-synthesis | 0.564 | 8.714 | 0.020 | 13.273 |
| technical-guide | 0.534 | 7.924 | 0.061 | 12.101 |
| risk-register | 0.544 | 8.061 | 0.061 | 12.253 |
| performance-hypotheses | 0.534 | 7.249 | 0.030 | 10.879 |
| decision-memo | 0.565 | 7.519 | 0.020 | 11.273 |

The source supplies a plausible cause of that *span*: `prepare_token` reads
the token embedding plus sixteen history-derived PLE rows, dequantizes them
on the CPU and uploads the results. `Weights::read` uses bounded file slices;
`Slice` maps and unmaps those rows. This one-card path does **not** call
`warm_lookups` or retain/touch all 28.8 GB of PLE pages. See
[main.cpp](../packet58j-onecard-port/main.cpp) at `prepare_token`, `lookup`,
`Weights::read` and the `residency_json` assignment, and
[gguf.cpp](../packet2/loader/gguf.cpp) at `Slice::Slice`.
An exact token stream selects the same input/history lookup rows. Page-backed
lookup I/O is therefore the leading explanation for the added preparation
latency. The process counters do not identify faulting addresses or distinguish
file faults from swap-in; they do not prove which mapping faulted. Nor do
they identify why the two arms saw different page residency. Tile loading,
intervening host activity and storage state are unresolved possibilities.

The model's load-and-pin time also differs: **41.23 s versus 140.36 s**.
That delay is outside token throughput, but reinforces the unequal host/I/O
state. The retained host monitor records similar minimum MemAvailable
(70.21 versus 70.94 GB), anonymous peaks (359.58 versus 359.45 MB) and maximum
accounted bytes (82.5136 versus 82.5132 GB). Estimated shadow peaks are
457.10 versus 624.87 MB, within the unchanged bound. Global SwapFree falls
by about 4.0 versus 171.8 MB during the windows; this is not a per-process
swap trace. High available RAM does not guarantee lookup pages are resident.
There is no evidence of a larger expert allocation or an admission failure.
Do not warm prompts, drop caches, touch all lookup pages, change memory
settings or retry a slow arm to make this comparison look better.

## Hits, misses, per-layer limits and read volume

Each position requests ten experts in each of 48 layers: **480 experts /
949,760,000 logical packed bytes**. All selected entries are touched before
victim selection and fit together in the 18 GB cache. Every selected miss is
filled after the position. Thus the exact aggregate counters recover:

- Expert hit rate: **93.123948%** in both arms.
- Logical byte hit rate: **93.108094%** in both arms.
- Layer 2 hit rate: **88.922559%** in both arms.
- Remaining 47 layers pooled: **93.213339%** in both arms.

Layer 2 uses 2,329,600 bytes/expert; the others use 1,971,200. Consequently
`(fill_bytes − fills × 1,971,200) / 358,400` recovers layer-2 misses in every
position. Individual ordinary-layer hit rates and route IDs were not saved.
Do not divide pooled counts by 47 and label the result a measured layer.

The once-through logical zero-copy miss payload is **65.456571 MB/token**,
including **30.417455 MB of down weights** (`fills × 921,600`). Those same
missing experts are subsequently copied to the cache for future positions;
this is not a copy-before-compute miss path. The source also publishes
1,179,648 pointer-table bytes and reads back 5,760 route bytes each position.
H2D copy counts reconcile exactly to `3 × fills + 147`; D2H is 50.
Actual PCIe transaction bytes, cache-line fetch amplification, PCIe read
time, and DMA-only time are **unavailable**. Logical payload is not a hardware
traffic counter.

Both native receipts have `profiling=false`, `timing=token`, empty
`sites.jsonl`, zero device-time placeholders and null family timers. There
are **no retained per-layer or per-operator durations** to split experts,
routing and recurrence. The −144 launches are attributable from source to
48 routers × three fewer kernels, not to fewer layers or less expert work.

## Each lever on one card

### Down-tile16: positive prediction; selected for the screen

[p100_down.hpp](../packet58j-onecard-port/p100_down.hpp) permutes each sixteen
360-byte IQ4_NL rows into a 5,760-byte tile. Code address is
`tile_base + block × 256 + row_in_tile × 16`; scale address is
`tile_base + 5120 + block × 32 + row_in_tile × 2`. Per-row successive code
blocks become strided, but neighboring output rows in a subgroup read
adjacent code/scale portions. The original subgroup already works across
sixteen rows, whose same-block addresses were 360 bytes apart. It is therefore
misleading to describe this as simply turning sequential PCIe reads into
scattered reads. The new kernel groups the code loads and preserves the
original FP32 accumulation chains, reduction tree and BF16 boundaries.

This is more than a byte permutation versus the one-card control: the old
virtual16 down kernel uses WG256/128 rows per group; tile16 uses WG64/32 rows
per group (200 versus 800 workgroups for ten 2,560-row experts). It changes
scheduling/load grouping, still with one kernel submission per layer.
`p49d_expert_submit.cpp` selects it only for routed IQ4_NL down projections.

`load_expert_bank` transposes bounded chunks in the pinned bank **before**
cache setup. Both host pointers and copied device entries use this layout.
All 921,600 down bytes per expert remain; gate/up bytes, expert sizes,
admission, victim policy, table publication and copy sizes are unchanged.
There is no per-token transpose, second full expert bank or cache-capacity
loss. The model receipts confirm identical counts/bytes, though no route-ID
trace was retained to compare the actual expert identities directly.

K1 changes only the down choice, even when launched for the full port view.
The gate/up cases are useful unchanged controls. The following are retained
**fixture** results, not inferred model-layer times:

| IQ4 down case, ten experts | Production K1a / K1b ms | Tile16 K1a / K1b ms |
| --- | ---: | ---: |
| All device, event time | 0.059474 / 0.064490 | 0.047141 / 0.063312 |
| All host, event time | 0.910198 / 0.899766 | **0.418125 / 0.417531** |
| Five host / five device, event time | 0.366588 / 0.366073 | **0.210271 / 0.207688** |
| Streamed copies plus compute, wall time | 1.125730 / 1.128270 | 1.121020 / 1.118280 |

Both runs use disjoint timed host regions, 562,176,000 bytes for the down
fixture, and pass byte checks. Gate/up all-host cases stay near their controls.
Aggregate useful host bandwidth is 13.964/14.026 versus 17.561/17.468 GB/s;
both exceed the unchanged 12.5 threshold. This directly contradicts a claim
that the retained host-down fixture regressed with tile16.

The positive mechanism is better subgroup load locality/grouping on host
misses, with possible resident benefits. The model has only about 0.69 misses
per layer on average, not five or ten. Sparse mixed-residency latency is
nonlinear, so no linear K1-to-model speed is a measurement or guaranteed
gain. The two fresh host/mixed fixture improvements justify one isolated
screen; they do not establish model speed or full-model determinism.

### Route-fast: weak positive prediction, unmeasured alone

[p78_route.hpp](../packet58j-onecard-port/p78_route.hpp) replaces the control's
four router kernels (`route-exp32-rank4`) with one WG512 kernel and a bitonic
probability/index sort. It preserves rounded probabilities, tie-breaking,
normalization and route outputs. The comparison count and launch count fall;
the sorting barriers and occupancy cost must still be measured. The bundle's
−144 submissions confirms the launch mechanism and its enqueue span improves
slightly, but cannot attribute the full wall effect to this lever.

It does **not** read or modify `Cache`, change hit/miss accounting, introduce
demand copies, or alter zero-copy/streamed selection. `cache_after_position`
still reads all routes after the position and uses the same LRU publication
path. One card has the same per-layer router dimensions; there is no new
cross-card dependency to remove here. This is a plausible small gain, with
less direct one-card timing evidence than the down fixture.

### Rec-both-plus: positive mechanism, uncertain endpoint magnitude

[p82b_recurrence.hpp](../packet58j-onecard-port/p82b_recurrence.hpp) advances
independent q/k normalization and gate calculations on producer subgroups,
uses vector BF16 state loads/stores, and replaces the guard-only workgroup
barrier with a subgroup-local entry decision. Against this one-card control
(`rows4-shared`), the change includes parallel producers as well as the
guard simplification; it is not merely removing one barrier from an already
parallel baseline. Each group still updates four rows, using the same FP32
trees and rounded BF16 state; tokens reread that rounded state.

All recurrence operands/state are device allocations checked by
`recurrence_validate`. There are no host expert pointers, cache admission
changes, topology-specific branches or MTP in this path. Kernel count stays
one per GDN site. Shorter dependency chains support a positive prediction,
but register pressure and scheduling can offset it. No one-card recurrence
time was retained, so this analysis does not blame it for the bundle loss or
claim a measured standalone benefit. Packet58h's one-card MTP closure stands.

### Device-cache-only tile16: feasible design, not selected

Identical arithmetic permits selecting row-major or tiled addressing per
expert if the pointer carries a trustworthy layout/residency tag. Current
`p58::Pointer` carries only address and generation; `resolve` does not expose
residency, and one launch may mix host and device pointers. Pointer address
guessing or using the tile kernel on row-major host bytes would be wrong.

A new implementation would keep the host bank row-major, copy each admitted
down expert into its existing device slot, then transpose via a bounded
scratch region before publishing a tagged table. It would need ordered
reader/victim/copy/transpose/publication lifetimes, a complete scratch peak
budget, and full byte/startup gates. Extra per-fill work is not free. No
second 48.6 GB host bank is needed in principle, but the current binaries
cannot select this mode. Because the retained **host** cases improve most,
discarding that benefit and adding fill conversions has no supported advantage
over the ready tile16-only view. Defer it unless a matched sparse-miss result
shows host tile16 itself losing.

## Decision and evidence limits

Prepare production / **down-tile16 only** / production with the copied 58k
protocol and unchanged native binaries. Keep route-exp32-rank4 and
rows4-shared. [README](README.md) specifies the 33–39 minute whole-host gap,
one model load plus two fresh K1 fixtures per arm, lossless oracle gate and
newest-captured-kernel-line-minus-two-seconds fault boundary. This is a
proposal, not an installed queue or authorization to run devices in this task.

Retain all preparation and fault counters in that bracket. A recurrence of
the host-I/O disparity remains part of the observed endpoint cost; do not
silently subtract it, cherry-pick fault-free tokens or retry for favorable
page residency. Even an exact winning screen needs later fresh candidate
repeat and full quality/performance gates before a speed claim.

Reproduction uses only the standard library under nice19/helper affinity:
`python3 -B analyze.py` with stdin `/dev/null`. [analysis-data.json](analysis-data.json)
contains per-prompt and phase summaries; [position-pairs.jsonl.gz](position-pairs.jsonl.gz)
contains every aligned position. [analysis-inputs.json](analysis-inputs.json)
binds original paths, hashes and byte-exact gzip snapshots (including ignored
raw receipts), so the analysis can replay without restoring files into frozen
packets. Runtime imports and device binaries are never used by the analyzer.
