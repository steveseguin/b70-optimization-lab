# Packet58aa: one-card MTP re-check on the 29.260 line

October 18, 2026. **Decision: close without a build.** The old host-memory
rejection no longer holds under the measured policy. Device memory fits only
after paying for the draft with target-cache capacity. The resident-draft
projection is **25.03–29.16 tok/s** across the assumptions below, versus
**30.723 tok/s** required for +5%. An intentionally favorable shared-cache
sensitivity reaches **30.62 tok/s**, still below the gate, before charging
draft cache pollution or remote draft-expert reads. These are CPU projections,
not measured MTP speeds, statistical confidence bounds, or proof of a hardware
limit. No build brief, runtime, readiness marker or queue proposal is created.

## Identity and evidence

The anchor is packet58z, one B70, Unsloth UD-IQ3_XXS quantized compressed
target, `iq3-p49-split32-v1`, tile16, overlapped cache maintenance,
21,552,729,600-byte expert cache, context 4096 and full BF16 KV. The retained
[WS128 summary](../packet58z-onecard-record/evidence/card0-58z-a/WS128/summary.json)
reports **29.2597641566 tok/s**; the requested rounded anchor is 29.260.
Predictions transform each prompt's recorded 99-interval rate and recompute
the median of six class medians. The reciprocal 34.176350 ms is only a modeling
anchor, not an observed mean token latency. The receipt has 128 output tokens
per prompt and its strict 512-token final gate remains false. This re-check
does not change that qualification or promote a new result.

The proposed draft is **58h's retained official-derived INT8/group-16-scale
draft**, with draft HC and the 91,392-row shared target-head prefix. The assumed
acceptance is the requested **0.787**, transferred from two-card evidence;
neither acceptance nor draft latency has been measured on this one-card
composition. Later 80,128-prefix and other draft variants are not silently
substituted. MTP only proposes: every emitted token must be verified by the
full unchanged target, with causal state, rollback and deterministic fresh
process output agreement with packet49. This CPU study establishes none of
those future implementation gates.

Read-only inputs and their SHA256s are in [analysis.json](analysis.json):

- [58h feasibility](../packet58h-onecard-mtp/FEASIBILITY.md): exact draft
  allocations, state reservation and the differing-route M2 timing proxy.
- [58i attribution](../packet58i-onecard-attribution/ATTRIBUTION.md): actual
  zero-copy miss semantics, expert sizes and limits of transfer proxies.
- [58u measured admission](../packet58u-host-admission/README.md): normalized
  accounted peak, empirical shadow, explicit margin and unchanged reserve.
- [58v](../packet58v-async-cache/README.md) and
  [58x admission](../packet58x-cache-capacity/ADMISSION.md): delayed publication,
  larger cache and retained device/host allowances.
- [58y report](../packet58y-onecard-attribution/analysis/report.json): native
  misses are distinct from fills; isolated miss time remains unmeasured.
- [58z window](../packet58z-onecard-record/evidence/card0-58z-a/WS128/window.json)
  and its census: actual larger-cache allocation and host admission.
- Packet55's raw held-out route stream and packet138's exact captured route
  truth, historical prefill and CPU cache simulator, all hash-bound below.

58h actually used the **24.012784 diagnostic WS128x** anchor and a 28.8 gate,
not the later 24.338653 whole-host WS128 record described by 58i. Its 24.62
projection is historical and is not scaled as though it measured one-card MTP.

## Memory under the measured bounds

All GB are decimal. The 58u tile16 required-available bound is **95.401027 GB**:
82.516125 GB normalized accounted peak + 4 GiB policy margin + 8 GiB reserve.
This accounted peak is not RSS. The observed full-model shadow envelope is
0.657900 GB, rather than a requirement to shadow the whole 26.409 GB device
budget. The 4 GiB shadow stop remains; a 0.66 GB observation is not a new cap.

58x/58z add full backing for the larger cache and metadata, requiring
**98.989728 GB** available. 58z WS128 admitted **121.002299 GB**, with a
**0.644334 GB** observed shadow peak. The retained 58x historical available
floor is 119.233389 GB. All comparisons are historical offline admission
arithmetic, not current permission to occupy the host or a measured MTP peak.

| Added item from the retained draft census | Bytes |
| --- | ---: |
| Draft weights, including 3,145,728,000 routed-expert bytes | 3,326,953,472 |
| Draft BF16 KV/index at context 4096 | 9,699,328 |
| Draft workspace | 17,711,414 |
| Pinned staging | 20,492 |
| Two complete private target rows | 942,046,696 |
| Private draft image and copy tables | 27,672,886 |
| Additional shared head/embedding weight bytes | **0** |

The target census still has the full **839,321,600-byte head**. Its first
91,392 rows (308,904,960 bytes) can be shared; the draft experts cannot alias
target experts. Workspace fits inside the existing 1 GiB workspace allowance.
The 969,719,582-byte private-state reservation fits the existing 1 GiB
transaction allowance, leaving 104,022,242 bytes. This is the same conservative
declared layout as 58h, not a new allocation/lifetime proof. Retain the 256 MiB
loader/transfer allowance; bounded source tensors are at most 62,914,560 bytes.
Do not retain another full official-draft source copy or duplicate the head.

58z's device-owned bound is **29,963,128,848 bytes**, plus a separate
**536,870,912-byte driver allowance** and **1,500,000,000-byte reserve**.
Only 240 bytes remain against the 32 GB floor. Its actual post-load payload
is 27,841,642,228 bytes; the difference is reserved transient space, not free
cache capacity to spend twice.

| Declared placement | Resident draft experts | Draft experts share cache |
| --- | ---: | ---: |
| New device-bound charge, after existing workspace/state allowances | 3,336,652,800 | 190,973,952 |
| Permitted cache arena | **18,216,076,800** | **21,361,755,648** |
| Target capacity if every draft expert is resident in that arena | 18,216,076,800 | 18,216,027,648 |
| Added actual payload before reducing the arena | 4,324,083,796 | 1,178,380,372 |
| Conservative required host availability | **103,313,832,032** | **103,313,881,304** |

The shared option adds 3,145,728,000 pinned expert bytes, pointer tables and
staging; every cached draft byte competes with target capacity. It cannot keep
21.55 GB of target cache and also get free resident draft experts.

For host review, deliberately retain **all** of 58x's extra-cache backing
charge even after reducing the cache, then add the entire proposed new device
payload and directly owned host payload. Thus the 103.314 GB bound charges
private-state backing too and does not depend on transferring a 0.66 GB shadow
to new draft allocations. Keep the 4 GiB margin, 4 GiB live shadow stop and
8 GiB host reserve. It fits the historical floor with about **15.92 GB** to
spare. Even subtracting another 2 GiB for 58h's recorded block57/exclusion
discrepancy leaves over **13.77 GB**. No memory exclusion is relaxed. A future
implementation still needs its own sealed bound, lifetime census, live
admission and guards; 58u explicitly did not qualify MTP itself.

## Real routes: M=2 grows the expert union

Packet138 supplies 48 accepted positions for each of the twelve independent
packet55 held-out text prompts. These cover code, prose, analysis, operations,
translation and arithmetic. They are separate from the record prompt suite;
there is no benchmark training, easy-prompt filtering or repeated-prompt cache.
Packet55 and packet138 are two captures of the same held-out text family,
not independent replications or a one-card native route measurement.

| Trace / selection | Adjacent layer-pairs | Mean experts in union (M1 is 10) | Range of per-layer means |
| --- | ---: | ---: | ---: |
| Packet138 accepted positions, every adjacent pair | 27,072 | **16.778590** | 15.414894–19.375887 |
| Packet55 observed target visits, adjacent position within prompt/layer | 146,880 | **16.515053** | 14.645098–19.296405 |

The union therefore grows about **65–68%**, adding **619.247–644.065 MB** of
logical selected target weights per full 48-layer pair before cache hits.
Packet55 preserves
speculative/rejected observed work: 64,831 eligible pairs have a speculative
second row; 7,377 rewind/nonadjacent transitions are excluded from adjacency,
not silently labeled consecutive. [All 48 layer rows](route-union-by-layer.csv)
and exact counts/ranges are retained. Packet138's accepted trace alone cannot
price a wrong proposed token; rejected paths are an additional uncertainty.

For cache replay, the first-fit byte allocator, global LRU, revoked pointers
and delayed publication come from the saved packet138 CPU simulator. Each
variant begins empty, preserves immutable weight residency across all twelve
requests and consumes packet55 historical prefill before the 48 captured
decode positions. M1 has 576 positions; M2 groups nonoverlapping pairs into
288 cycles. M2 assumes maintenance lag per pair and a **55 ms** cycle window
for fill progress, versus the record reciprocal for M1. That timing and the
grouped publication schedule are explicit assumptions, not a causal verifier
implementation. No state/prompt/KV cache is reused.

Two read sensitivities are retained: ideal stable union reuse (one read of a
shared expert's weights for both rows), and separate reads for each row.
Packet68c implements stable union reuse in its sampled expert kernels, but
has not established it for this complete one-card zero-copy causal path.

| Replay | Logical zero-copy MB per position/cycle | Fill MB per position/cycle |
| --- | ---: | ---: |
| Current 21.553 GB, M1 | 64.717 | 31.633 |
| Resident draft leaves 18.216 GB, M1 | 94.065 | 45.795 |
| Resident draft, M2 union reads | **190.497** | **83.218** |
| Resident draft, M2 separate reads | **204.458** | **83.049** |
| Shared arena 21.362 GB, M2 union, no draft pollution | 134.712 | 58.233 |
| Same shared sensitivity, separate reads | 143.662 | 58.240 |

Relative to the current M1 step, resident-draft M2 adds **125.780–139.741 MB**
of logical missing-weight reads per cycle. Cache reduction alone adds
29.348 MB at M1. These are once-through logical packed bytes, not hardware
PCIe measurements. Missing experts are read remotely during computation;
later fills are a separate transfer, not a replacement for that read.

58y independently shows why fills cannot stand in for misses after overlap:
at its **18 GB diagnostic** setting it records 93.402 MB of logical misses
but 43.128 MB of fills per token. Its 22.8605 diagnostic rate and overlapping
host spans are not substituted for the 29.260 baseline or treated as removable
device time. Actual one-card M2 sparse-miss time remains unmeasured.

## Time model and transfer limits

For one confirmed input plus one proposed input, with complete target
verification, the optimistic reward is `1+a = 1.787` tokens per cycle:

```text
cycle = V2 + D + (1-a)*R + exposed extra fill cost
rate = 1000*(1+a)/cycle
```

One card serializes draft and target work; no two-rank overlap is imported.
The retained draft **D = 1.794747 ms** is a complete command measured on one
card of the two-card engine, including publication. It is a transfer assumption
for our single-card target composition, not a new measurement. The sensitivity
uses D through 2D, allowing an extra feedback/repair pass. Packet85's older
causal controller measured a 1.604 ms feedback command when needed, which
supports retaining that cost risk; it does not establish its frequency here.
Rejection repair uses the packet68 proxy **R = 0.980923 ms**, or
**0.208937 ms/cycle** at the requested acceptance. This is neither an unavoidable
lower bound nor a proof that successful-prefix selection costs zero.

The 39 differing-route samples per rank in packet68c give combined
M2/M1 device ratio **r = 1.700307**, and combined device increment
**Δ = 18.5012 ms**. The paired probe uses saved independent state snapshots;
it is not a causal two-position target command. It also predates tile16 and
overlap, so both its ratio and additive increment are transfers, not bounds.

Let `T` be each measured 58z prompt's period, `Z1` its modeled current-cache
remote cost and `Z2` the modeled two-row remote cost after cache reduction:

```text
ratio transfer:       V2 = r*(T-Z1) + Z2
favorable additive:  V2 = T + Δ + (Z2-Z1)
```

The first explicitly replaces the scaled baseline remote component instead
of charging extra miss bytes twice. The second pays every other one-card
overhead only once per pair, an optimistic assumption. Neither subtracts
58y's host wait from the record or assumes an isolated measured compute split.

`Z` uses the saved 58i/138 K1 mixed/all-host linear proxies: ordinary experts
**0.10399325–0.156005475 ms per miss**, special layer 2
**0.09253651–0.135582555 ms**. They are device-event differences at fixture
densities, not calibrated sparse M2 miss latencies. Extra fill service is
either completely hidden or charged at the inherited **25 GB/s assumption**.
For the resident union case, the exposed extra fill endpoint is 2.063413 ms.
No measured link-bandwidth guarantee or zero-cost fill claim is made.

| Conditional model | Projected tok/s range |
| --- | ---: |
| Old ratio directly on current periods, free new cache/state costs | 29.8297 |
| Resident draft, ratio with changed miss bytes | **25.0337–27.7786** |
| Resident draft, favorable fixed-overhead increment | **25.7081–29.1634** |
| Shared arena, free draft pollution/misses, ratio | 27.2340–29.1007 |
| Shared arena, free draft pollution/misses, fixed overhead | **28.0332–30.6235** |

The shared rows are deliberately favorable sensitivities, not feasible speed
claims: they leave all arena capacity to target experts while using resident
draft time. A fully host-served draft reads another **61.44 MB** of routed
expert bytes per step; dividing by 19–25 GB/s gives 2.46–3.23 ms merely as a
transfer scale, not measured zero-copy time. Caching some draft experts instead
costs target capacity and introduces cache misses/pollution. Neither cost is
credited away in deciding to build.

The gate allows a total cycle of **58.164893 ms**. After the base draft and
rejection repair, verification has **56.161209 ms** at the rounded aggregate
anchor. Even the favorable shared case models 56.340039 ms before those costs.
Removing its repair charge can move this narrow sensitivity across the gate,
but that is not evidence for free state handling, free draft misses and free
cache capacity together. The fully resident case misses by much more.

## Decision, reproduction and revisit condition

**Memory passes a conservative hypothetical-layout review; speed does not
support +5%, so no build is briefed.** This replaces the reason to leave this
composition closed: do not repeat 58h's 121.65 GB host rejection as a current
physical-memory claim. Do not interpret this study as closing every one-card
MTP design or the optimization lane.

Reopen with evidence for a complete, causal one-card M2 path—including
cache loss, wrong proposals, draft feedback and prefix selection—below the
58.164893 ms cycle budget at acceptance 0.787, or a distinct exact mechanism
that credibly lowers those costs. Keep 1.5 GB device reserve, the measured
host policy's margin/reserve and the unchanged target/KV/output oracle.
Do not reopen on ideal union counts or acceptance alone.

Reproduce from the repository root (standard library, no model reads):

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet58aa-onecard-mtp-recheck/analyze.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet58aa-onecard-mtp-recheck/analyze.py --check </dev/null
```

The script enforces a 4 GiB address-space ceiling. The first replay peaked at
127,508 KiB RSS; the final replay peaked at 129,508 KiB. It reads only saved
receipts, routes and a CPU cache simulator;
existing packet trees, screen trees, ops and live queues are unchanged.
The tracked compact route truth is retained; packet55's raw route stream is
locally retained at its hash-bound original path. Missing raw evidence must
be restored, not regenerated with a model in this CPU-only task.

[Closeout](CLOSEOUT.md), [new negative entry](DO-NOT-REPEAT.md),
[work note](../../../../notes/2026-10-18-own-runtime-packet58aa.md).
