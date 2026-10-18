# Packet58i: one-card attribution and exact-lever ranking

October 18, 2026 UTC. CPU analysis of frozen packet58g receipts. **Decision:
close this packet without a runtime build or seal-ready design.** The receipts
do not support a credible prediction of at least **26.774 tok/s**, the required
+10% over 24.34. This is a measurement gap, not a claim that the one-card lane
has reached its limit. Post-router copying remains a potentially larger lever;
its missing synchronization and overlap costs decide which side of the bar it
lands on.

The strongest simple transfer-only scenario is **26.11 tok/s (+7.27%)** before
new overhead. The conditional larger-cache scenario is about **25.9 tok/s**.
Neither qualifies. More favorable post-router sensitivities exist below, but
their assumed overlap is not a measured result or an earned prediction.

## Identity and what is actually measured

Source: `../packet58g-onecard/evidence/card0-58g-a/`, windows KD, W2m, WS,
WS128x and WS128. Unsloth UD-IQ3_XXS, one B70 on card 0, target-only,
`iq3-p49-split32-v1`, context 4096, full BF16 KV, 18,000,000,000-byte cache.
The user supplied record ID is `cmvd8bhou000duj01hxaihg15`; no external lookup
or submission was made here.

WS128 records **24.3386533233 tok/s**: the median of six prompt-class medians,
each prompt using `99 / (timestamp100 - timestamp1)`. All twelve prompts have
128 output events, zero cached tokens and no prompt/KV/response reuse. The
immutable weight cache persists between requests. WS128 is whole-host timing;
WS128x is shared-host exactness, and KD/W2m/WS are diagnostics. Their times are
not pooled into the baseline. The recorded strict 512-token final gate is
**false**. This attribution does not change the record's qualification.

`1000 / 24.3386533233 = 41.0869075916 ms` is the reciprocal of that aggregate
rate, **not** an observed mean token time. The arithmetic mean of the 1,188
selected token `wall_ms` fields is **40.667671 ms**. Both are retained, with
different definitions. Estimates below subtract a proposed cost from each
prompt's measured 99-interval duration, then recompute the same class statistic.
They do not subtract unrelated medians from one another.

## The actual miss path

The saved selection is **zero-copy**. Missing expert weights are read from
pinned host memory during expert execution. After the complete position drains,
the runtime reads back all 48 routes, chooses global-LRU victims, fills their
device slots, publishes all 144 projection pointer tables, and drains before
the next position. Thus a miss has both a current host-read path and a later
copy for future reuse. This is not a demand copy that makes the current expert
resident before computing it.

Source boundaries, archived with their hashes in [inputs.json](inputs.json):

- `main.cpp`, `cache_after_position`, `fill_cache`, `publish_cache_table`:
  cache timing starts at policy planning and ends after copies, publication,
  drains and commit. The following log flush and cache-stats file write are
  outside this timer.
- `main.cpp`, token `step`: the generated timestamp is taken after cache
  maintenance, so the baseline includes its cost.
- `cache_table.hpp`, `Cache::prepare`: touch every selected expert before
  selecting victims. The 480 selected experts fit together in 949,760,000
  bytes, far below the cache capacity. No selected hit can be evicted while
  filling the selected misses under this policy.
- `owner.cpp`, `CopyEngine::copy`: submissions depend on the last owned event.
  Merely selecting the BCS queue does not enable overlap in this implementation.

## Per-token attribution

The table uses WS128's generated events 2–100, aligned by request order and
cache epoch. There are 99 charged positions per prompt, 1,188 in all.

| Recorded field or derived quantity | Mean per token | Meaning and limits |
| --- | ---: | --- |
| Token `wall_ms` | 40.667671 ms | Measured token step span |
| Cache `wall_ms` | 7.834869 ms | Measured planning + submissions + DMA waits + table publication; nested in token wall |
| Token wall minus cache span | 32.832803 ms | Derived remainder, still mixes device work and host work |
| `prepare_ms` | 0.562211 ms | Host lookup/dequantization/upload span; includes upload waits |
| `enqueue_loop_ms` | 7.429559 ms | Measured host submission span excluding its counted waits; overlaps device execution |
| `wait_ms` | 26.520821 ms | Host waiting across compute, transfers and cache publication; not pure device execution |
| `transfer_wall_ms` | 0.468363 ms | Selected upload/readback helper spans; excludes cache-fill copies and overlaps other spans |
| Wall − prepare − enqueue − waits | 6.155079 ms | Accounting residual, not an isolated housekeeping measurement |
| Kernel submissions / host waits | 1,790 / 8 | Measured counters |
| Cache fills / evictions | 33.005051 / 32.639731 experts | Measured counts |
| Cache fill payload | 65,456,571.044 bytes | Measured commanded expert H2D bytes; not hardware PCIe traffic |
| Extra pointer-table H2D payload | 1,179,648 bytes | Exact source-derived 144 × 512 × 16, every position |
| Route readback payload | 5,760 bytes | Exact source-derived 48 × 10 × 12; status/argmax adds 8 bytes |

**These spans are not additive exclusive buckets.** In particular, cache time
contains waits, prepare contains waits, and host submission overlaps compute.
The unknown prepare/wait overlap is at most the per-row minimum of prepare and
transfer spans: its mean bound is 0.286011 ms. The residual above undercounts
unassigned wall by that unknown overlap. It also includes housekeeping and
copy submission not otherwise separated. It must not be relabeled as all CPU
time, all PCIe time, or all removable time.

The H2D counters independently reconcile to `3*fills + 147` for every WS128
position: three projections per filled expert, 144 pointer-table copies, and
three other uploads. D2H is 50 copies: 48 routes plus status and next token.
Retained-fixture diagnostic steps have one extra copy in each direction; they
are not substituted for WS128. `cache-stats.json` counters are cumulative
across requests, not per-request deltas; all joins verify that convention.

### Expert hits and zero-copy reads

For the metric window, the source-backed inferred expert hit rate is
**93.123948%**; logical byte hit rate is **93.108094%**. Each position requests
480 experts / 949,760,000 logical packed bytes. A fill corresponds to exactly
one selected miss for this implementation, so `1 - fills/480` recovers the
per-token hit rate. The logical once-through missing payload equals the fill
payload, **65.46 MB/token**. Actual zero-copy PCIe reads and their time were
not recorded: hardware caching, repeated loads, transactions and scheduling can
make physical traffic differ. This is neither a PCIe counter nor an isolated
zero-copy duration.

One unusual layer can be recovered exactly from aggregate bytes:

```text
layer2_misses = (fill_bytes - fills * 1,971,200) / 358,400
```

Layer 2 has 2,329,600 packed bytes per expert; every other layer has 1,971,200.
The numerator is divisible in every row. Layer 2's inferred hit rate is
**88.922559%**; the other 47 layers pooled are **93.213339%**. Their individual
hit rates are **unavailable**, not assumed equal. No 58g route-ID stream or
per-layer hit counter was retained. The [per-position artifact](position-attribution.jsonl.gz)
contains every token's counts, bytes, aggregate and layer-2 hit rates, timings
and join identity. JSON explicitly uses null for unavailable per-layer values.

For scope comparison, all 1,536 decode steps average 64.52 MB of fills and
7.750 ms of cache work, with 93.222% expert hits. The 850 prefill steps average
116.70 MB and 12.009 ms, with 87.707% hits. These serial prefill observations
are not a measured 512-token prefill benchmark.

### Device compute by class

| Class | Isolated one-card time |
| --- | --- |
| Routed/shared experts | Not recorded |
| HC | Not recorded |
| Recurrence | Not recorded |
| Attention | Not recorded |
| Head | Not recorded |

All five windows ran `timing=token`, `profiling=false`. Both device-time fields
are zero placeholders; `enqueue_family_ms` is null. The host wait cannot be
divided into these classes. Packet81's reduced expert load counts did not
improve its measured lane speed; no instruction-count speedup is imported here.
No two-card operator sum is subtracted from this one-card wall time.

The [JSON](ATTRIBUTION.json) preserves separate statistics for every window.
WS/WS128x/WS128 have identical metric-window fill counts and bytes, but different
host preparation and wall costs. They support stable cache-count accounting,
not a causal compute-time split or a fresh whole-host performance repeat.

## Memory: capacity is not admission

| Post-load quantity, WS128 | Bytes |
| --- | ---: |
| Actual device allocation census | 24,287,732,980 |
| Actual pinned-host allocation census | 48,633,091,712 |
| Packed expert part of pinned host | 48,627,712,000 |
| DRM VRAM occupancy | 24,605,085,696 |
| DRM occupancy above allocation payload | 317,352,716 |
| Device floor / retained reserve | 32,000,000,000 / 1,500,000,000 |
| Physical free margin after reserve, using DRM | 5,894,914,304 |
| Original conservative device/shadow bound | 26,409,219,600 |
| Actual allocation slack inside that bound | 2,121,486,620 |
| **Original whole-host admission requirement** | **118,308,908,048** |

KD/W2m/WS/WS128x admission is about 85.6 GB for their exactness/diagnostic
scope. That is not 85.6 GB of measured pinned allocations. Whole-host WS128
also reserves file-backed lookup residency and full device backing, and keeps
the 8 GiB host reserve. Available RAM at its admission was 120,904,699,904
bytes; this analysis does **not** spend that extra margin or raise the original
118,308,908,048-byte budget. Post-load host-global shadow estimates are not
substituted for the reserved full backing.

A cache of **20,121,486,620 bytes** would consume all currently unallocated
bytes inside the original device bound. It is only a conditional scenario:
those bytes are workspace/transaction/transfer allowances, not automatically
reclaimable memory. Keeping all allowances unchanged permits **zero** extra
cache bytes. A later full lifetime census must prove any reallocation while
retaining required transient peaks, driver margin, BF16 KV, reserve and the
original host cap. An independently proved release of N actual device bytes
can fund at most N cache bytes without raising device backing. No unused
scratch or captured buffer is declared free by this packet.

Spending the physical 5.89 GB would exceed the existing shadow budget unless
something else is freed. Keep the 1.5 GB reserve: the brief's roughly 0.3 GiB
paging region is a boundary to avoid, not extra capacity to exploit. No live
memory, device, service or setting was inspected or changed to make a fit.

## Route replay and ranked estimates

58g's missing route IDs prevent a true one-card policy replay. The CPU replay
therefore uses packet55's **independent** calibration trace: its existing
converter, native route and timing bindings are checked before extracting
compact inputs. Twelve training prompts set frequency order only; twelve
held-out prompts supply replay demand. No benchmark prompts train placement.
All target visits, including rejected speculation, stay charged, in original
two-rank observation order. Each simulated admission publishes after a layer
route, not after a full position. The cache starts empty and persists across
the held-out prompts. Those differences forbid treating these hits as native
58g observations.

The replay compares global 256-byte first-fit LRU, LFU with counts since
admission, two-hit admission, and one frequency-predicted absent expert per
layer visit. The predictor chooses **before** seeing the route. Speculative
copies and pollution count even when wrong. This tests total offload traffic;
it does not reopen the rejected idea that merely choosing different static
host expert identities makes computation faster.

The exact counts, per-layer proxy results, per-prompt demand and source pins
are in [route-replay.json](route-replay.json) and
[route-inputs/binding.json](route-inputs/binding.json). The LRU implementation
also agrees with an independent ordered-dictionary oracle over 1,200 positions;
an independent LFU oracle checks another 1,000 positions. Three hundred
variable-size positions check complete, non-overlapping arena coverage.

| Held-out decode replay | Logical byte hit rate | Fill traffic, including speculation |
| --- | ---: | ---: |
| 18 GB LRU | 93.669% | 194.056 GB |
| Conditional 20.12 GB LRU | 95.009% | 152.987 GB |
| 18 GB LFU | 68.282% | 972.178 GB |
| 18 GB two-hit admission | 93.482% | 177.661 GB |
| 18 GB LRU plus frequency prefetch | 91.814% | 557.427 GB |

These totals cover 154,833 observed decode route visits, not emitted tokens.
Larger cache reduces miss bytes by 21.164%. Only 1.086% of speculative copies
in this predictor are used by their intended next route; it also evicts useful
entries. Two-hit admission saves fills while increasing logical misses by
2.952%, so its small modeled benefit depends on charging both effects.

The table ranks **conditional estimates**, not established performance. The
shared anchor is 24.33865 tok/s. Differences within the small-estimate ranges
are not a resolved ordering. Levers are not added together: several remove
the same cache cost.

| Order | Lever | Conditional tok/s | Decision |
| --- | --- | ---: | --- |
| 1 | Hide existing fill DMA on BCS while later work computes | 26.11 | +7.27% even with free scheduling and all estimated DMA hidden; below bar |
| 2 | Increase cache to conditional 20.12 GB | About 25.9 | About +6%; host-budget/lifetime proof still missing |
| 3–4 | Coalesce 144 table publications to one | 24.63–24.77 | Launch-only estimate; under +2% |
| 3–4 | Two-hit admission | 24.68 | Small proxy benefit, no native qualification |
| 5 | Store each expert's three projections contiguously | 24.48–24.55 | Saving two launches per fill is under +1% |
| 6 | Tested frequency speculative prefetch | About 17.5 | Extra traffic and pollution outweigh reduced wait assumptions |
| 7 | Tested LFU | 11.46 | More misses; reject this policy |
| Unranked | Post-router copy overlapping resident gate/up | No supported point estimate | Potentially larger; missing stage costs decide the result |
| Unranked | Indexed LRU victim selection | No isolated cost | Useful host hypothesis, but fitted residual is not removable time |
| Unranked | Change zero-copy/copy threshold | No supported point estimate | Sparse per-layer matched cost missing |

The cache-size/policy estimates transfer replay miss/fill **ratios** to WS128.
They use K1's mixed-host-minus-resident proxy for missing experts and scale the
*entire* cache span by relative fill bytes. Scaling fixed table/metadata costs
down is favorable to lower-traffic candidates; no new policy overhead is
charged. Thus the cache-size result is already optimistic, not a conservative
fit prediction. Every assumption and full-precision result is in
[lever-models.json](lever-models.json).

### BCS overlap: two different opportunities

1. **Existing next-position cache maintenance.** The current routes are already
   available after the position. Start next-position independent work while
   filling, but fence each expert consumer on its exact table generation and
   completed weight copies. Reorder fills/publications by upcoming layer if
   needed; never let an old reader see an overwritten victim. At the inherited
   25 GB/s copy-floor proxy, 65.46 MB needs **2.618 ms** of service. Hiding all
   of it, with no new work, gives 26.11 tok/s. This estimate does not hide the
   full 7.83 ms cache timer, which includes host work and publication.
2. **After the current layer's router.** Read the selected IDs, copy missing
   experts on BCS, execute gate/up for resident experts on the sole compute
   queue, then execute missing experts after copy completion and combine in
   the original route order. There is no compute/compute overlap. Layer L+1's
   actual choices are unknown until L+1's router finishes; previous-layer
   compute cannot prefetch those choices exactly. This path adds router
   readback, split dispatch, earlier policy decisions and publication, and may
   change later cache residency. Its transfers must replace, not duplicate,
   the baseline end-position fills.

K1a/b do retain separate IQ2 gate/up, IQ3 gate/up and IQ4 down cases. Using the
inferred ordinary/layer-2 miss counts gives **estimated**, linearly scaled
remote-read penalties of about **3.42 ms/token** from the half-host cases, or
**5.13 ms/token** from all-host cases. They disagree materially. Neither is a
measured sparse-miss full-model penalty, nor a measurement of the independent
resident gate/up interval available for hiding copies.

For the more cautious mixed-case proxy, illustrative post-router estimates are:

| Assumed hidden DMA service | Assumed new total overhead | Estimated tok/s |
| --- | ---: | ---: |
| None | 0.48 ms | 26.36 |
| Half | 0.48 ms | 27.32 |
| Half | 2.40 ms | 25.96 |
| All | 2.40 ms | 26.90 |

The 0.48 ms scenario charges only 96 launches at 5 microseconds, before real
host round-trip waiting. The 2.40 ms scenario is a **sensitivity assumption**
of 50 microseconds per layer, not a measurement. No receipt establishes half
or full overlap. Treating the favorable row as a prediction would silently
assume away the decisive measurement. The full all-host sensitivity range is
also retained in JSON rather than cherry-picking its larger estimate.

Frequency speculation can start before the router, but must pay for wrong
copies, displacing useful entries, and contention between BCS and zero-copy
reads. The tested one-expert predictor is selected only from independent
training counts. Its poor replay result closes **that predictor**, not every
possible causal prefetch predictor.

### Zero-copy thresholds, host layout and housekeeping

K1's all-host/resident entries are device-event timings; its streamed entries
are wall timings including copy submission and waits. Their aggregate values
are roughly 2.42 / 0.36 / 5.60 ms for a 33.792 MB fixture spanning three cases,
not a representative single layer. Comparing only these numbers would favor
zero-copy for a single use, but misses that 58g subsequently copies a missed
expert anyway. The JSON retains per-format reuse crossover calculations with
the mixed timing definitions explicitly labeled. There is no defensible new
threshold for sparse production misses in these receipts.

Combining each expert's gate/up/down source into one pinned contiguous triple
can reduce three copy calls to one. At 33.005 fills and the brief's 3.4–5 us
launch range, that saves only **0.224–0.330 ms/token** before new packing cost.
The final host layout would have to replace the existing banks during bounded
loading; retaining a second 48.6 GB pinned copy is forbidden. Repacking per
token is not credited as free, and coalescing unrelated experts transfers
unused bytes unless source and destination ranges genuinely coincide.

The host cache policy scans all 24,576 entries to choose each victim, copies
metadata vectors, and rebuilds every table. A regression of cache wall against
fill count on the 184 zero-eviction positions gives about 2.19–2.25 ms fixed
cost plus 0.081 ms/fill. Applying that relation to decode leaves **2.87–2.94 ms**
of additional cache time across WS/WS128x/WS128. This is an **estimate confounded
by occupancy, fragmentation and scheduling**, not measured victim-scan time.
An ordered index can preserve exact LRU choices and reduce scans; its effect
cannot be sealed from that residual. Removing the entire 7.83 ms cache span
would give 30.18 tok/s, but that is an impossible zero-cost-maintenance ceiling,
not a candidate prediction.

## Exactness, next evidence and stop decision

Only immutable weight placement, timing and cache metadata are in scope. All
arithmetic, packed values, reduction order, router ordering, sticky-error
checks, target bytes, BF16 KV and output oracle stay fixed. Any future split
expert dispatch must keep original output slots and mixture order. Copy events
must remain owned through failure; no victim or staging buffer may be reused
before all readers/copies finish. Keep the prior 58b–58g pointer, allocation,
publication and teardown fixes; packet58h's MTP rejection and packet81's neutral
load-count lever remain closed.

To reconsider a build, the missing evidence is a short **separately admitted**
one-card diagnostic capturing route IDs, per-layer hits, copy bytes/events,
cache-plan CPU time, publication time, router-readback delay, resident gate/up
duration and host enqueue/wait spans on a common clock. It must keep the same
host admission and account for instrumentation. That diagnostic would identify
the overlap and policy costs; it would not be a speed headline. A candidate
would still need exact packet49 output/state checks, fresh-process determinism,
and matched complete realistic-suite measurements on at least two fresh starts.
No such job is prepared, queued or launched here.

## Reproduce and verify on CPU

All generated files stay in this new packet, apart from the explicitly requested
[lane note](../../../../notes/2026-10-18-own-runtime-packet58i.md). Existing
trees, CURRENT.md and prior DO-NOT-REPEAT files remain frozen. Inputs needed
for attribution are lossless gzip snapshots, indexed by original path and
SHA256; original large route traces are reduced to exact phase/layer/ID replay
inputs with validation provenance. No model payload is copied or read.

From the repository root:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet58i-onecard-attribution/analyze.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet58i-onecard-attribution/replay.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet58i-onecard-attribution/models.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet58i-onecard-attribution/verify.py </dev/null
```

`analyze.py` reads archived snapshots once `inputs.json` exists, so a clean
checkout does not require ignored local 58g receipts. `replay.py` likewise
uses the hash-checked compact inputs. Add `--originals` to `verify.py` on the
originating host to verify every archived input still matches frozen evidence.
The [verification receipt](verification.json) records those checks. Attribution
and replay were recomputed from the archived inputs; all five derived output
files match byte for byte in the [reproduction receipt](reproduction.json).
Timing percentiles use nearest rank; the ordinary median retains its standard
definition. Estimates are not public measurements or interpolated benchmark
points. No GPU, service, sudo, memory-block/fence access, setting change,
signal, reboot, build or external submission was used.
