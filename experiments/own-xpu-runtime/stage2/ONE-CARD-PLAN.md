# One-card IQ3 plan — residency, expert misses and exact arithmetic

**2026-10-11; CPU-only design, not a fit or speed result.** Two B70s remain
the primary target; one 32 GB B70 is the secondary target after that line
works. Owner direction: “this model is probably going to be used by folks
with just 1 or 2 B70 GPUs; i figure 2 GPUs is a good target for us, but 1 is
also reasonable to target.” This document authorizes no native window.

Recommend **resident dense weights and a bounded expert cache, with explicit
packed-byte H2D transfers for misses**. A 24 decimal GB cache, if admitted,
has a **39.50 tok/s transfer-only ceiling** under uniform routing and the
historical 19 GB/s transport scenario; adding even ideal GPU weight reads
without overlap reduces the arithmetic to **28.95 tok/s**. Neither is a
runtime prediction. CPU computation of misses is a later candidate with a
higher bandwidth ceiling but unmeasured exact-math cost.

## Identity and evidence

The separate model is **Qwen3.8 Flash-Next UD-IQ3_XXS (Unsloth), quantized
compressed version**, revision `766911a6b7369840a91dbcd95f9f997acaab6cd6`.
Use its own oracle; FP8 differences are informational, never a tolerance
gate. Target-only initially: these files have 48 layers and **no MTP block**.
No expert is dropped, and KV remains full 16-bit.

- [Admitted census](../../qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json)
  and [packet 1 accounting](../../qwen38-flash-next-ud-iq3xxs-b70/packet1/README.md)
  bind all 1,224 tensors. Census SHA256:
  `3312f5a18582788c5c6c84572fd616488b6835b454272c81eec218a58521607c`.
- [Stage 2 corrections](../STAGE2-PLAN.md#packet-1c-corrections) replace the
  homogeneous-grid estimates with actual mixed formats. The name IQ3_XXS
  does not mean an IQ3_XXS kernel: **zero tensors use that format**.
- [Packet 2](packet2/README.md) and its [roofline](packet2/roofline.json)
  supply packed GEMV arithmetic and per-layer bytes. Operator receipts do
  not establish full-model identity; that remains a separate gate.
- [Placement and communication](../DESIGN.md#placement-and-communication)
  and [expert streaming/host shadow](../DESIGN.md#expert-streaming-uva-and-host-shadow)
  govern allocations, queues, capture and orderly release.

All GB below are decimal; GiB means 2^30 bytes. All ceilings divide bytes by
a stated rate and omit costs explicitly discussed below. None is a headline.

## 1. What fits on one card

Keep the following packed tensors resident. This avoids streaming weights
that every token needs. The head is untied, so count the input embedding
separately. Keep the input embedding on device to avoid a host embedding
callback; PLE's much larger table stays host/file-backed with bounded gathers.

| Resident component | Actual formats | Bytes |
| --- | --- | ---: |
| GDN weights and controls | Q6_K, Q8_0, F32 | 1,754,576,384 |
| QSA attention projections | Q6_K | 490,291,200 |
| QSA indexer projections | BF16 | 39,321,600 |
| Hyperconnections, one logical copy | Q8_0, F32 | 691,159,040 |
| Routers | F32 | 252,149,760 |
| Shared experts | Q6_K, Q8_0 | 213,376,000 |
| Norms | F32 | 4,028,416 |
| PLE projections and controls in tensors | Q8_0, F32 | 35,102,720 |
| Full target head | Q6_K | 521,472,000 |
| **Dense/nonexpert subtotal without input embedding** | | **4,001,477,120** |
| Input embedding | Q6_K | 521,472,000 |
| **Chosen resident nonexpert tensors** | | **4,522,949,120** |
| PLE metadata, separate from tensor bytes | 35 U64 values | 280 |

Routed experts total **48,627,712,000 B**. Ordinary gate/up matrices are
IQ2_S, layer 2 gate/up is IQ3_S, and every down matrix is IQ4_NL. The
[component/grid table](packet1c/comparison.md) retains every exception.
PLE is **28,800,138,240 B**, IQ4_NL, off device. Sixteen selected PLE rows
cost 1,440 packed B/token; an embedding row costs 2,100 B locally. Host
page reads can greatly exceed the PLE payload; measure them separately.

The familiar **53,304,619,520 B** two-card weight number excludes both
lookup tables and includes an extra **675,430,400 B** HC replica. One card
needs no such replica: `53,304,619,520 - 675,430,400 + 521,472,000 =
53,150,661,120 B` with our resident embedding, before working memory.
The full expert bank therefore cannot fit. Under a conservative 32,000,000,000
B capacity, weights alone leave **27,477,050,600 B** for experts after the
nonexpert tensors and PLE metadata; working memory reduces that further.

### One user: 4K and 16K capacity arithmetic

Adapt the [packet 1 memory formulas](../../qwen38-flash-next-ud-iq3xxs-b70/packet1/memory-admission.json)
to one card, with no extra TP index or HC copy. Here 4K=4,096 and 16K=16,384
total allocated tokens, including output capacity. The old 753,139,712 B
two-rank KV allowance is not a context formula and is not reused.

| Memory class | Formula or allowance | 4K bytes | 16K bytes |
| --- | --- | ---: | ---: |
| Nonexpert tensors + PLE metadata | Above | 4,522,949,400 | 4,522,949,400 |
| Full 16-bit K/V | 12 × T × 2(K,V) × 2 heads × 256 × 2 B | 100,663,296 | 402,653,184 |
| QSA raw + pooled index | 12 × (T + floor(T/4)) × 128 × 2 B | 15,728,640 | 62,914,560 |
| BF16 GDN state | 36 × 48 × 128 × 128 × 2 B | 56,623,104 | 56,623,104 |
| GDN convolution history | 36 × 10240 × 3 × 2 B | 2,211,840 | 2,211,840 |
| PLE convolution history | 10240 × 3 × 2 B | 61,440 | 61,440 |
| One state checkpoint | GDN + convolution + PLE, conservative allowance | 58,896,384 | 58,896,384 |
| Graph/static buffers | Assumed 1 GiB | 1,073,741,824 | 1,073,741,824 |
| Operator/activation workspace | Assumed 1 GiB | 1,073,741,824 | 1,073,741,824 |
| Allocator/driver reserve | Assumed 1 GiB | 1,073,741,824 | 1,073,741,824 |
| Bounded device transfer slots | Assumed 256 MiB | 268,435,456 | 268,435,456 |
| **Total before resident experts** | | **8,246,795,032** | **8,595,970,840** |
| **Expert budget at 32 decimal GB** | Capacity minus total | **23,753,204,968** | **23,404,029,160** |
| **Expert budget at 32 GiB** | 34,359,738,368 minus total | **26,112,943,336** | **25,763,767,528** |
| **Expert budget at historical per-card capacity** | 34,242,297,856 minus total | **25,995,502,824** | **25,646,327,016** |

The historical capacity is half the Stage 2 two-card scenario, **not a fresh
device query**. An 8 or 16 GB cache fits all these assumed budgets; **24 GB
does not fit the strict 32 decimal GB budget**, but fits the historical and
32 GiB scenarios before uncounted peaks. Choose cache size only after actual
free-byte and peak-allocation admission. Do not shrink KV to force 24 GB.
Prefill temporaries, graph rebuild overlap, padding, exact QSA scratch and
any repacking can invalidate these allowances. No full FP16/FP32 expert
expansion is permitted by this budget. BF16 recurrent storage follows this
lane's reference; FP32 temporary updates need workspace, not a silent state
precision change. Target-only does not require speculative rollback; the
checkpoint row deliberately leaves room for controlled comparison/reset.

### Host backing is part of fit

On `steve-b70s`, keep immutable packed expert pages in host RAM where admitted,
plus bounded pinned staging, PLE pages, loader/control memory and any driver
shadow. With a 24 GB device cache, nonresident expert storage is
**24,627,712,000 B**. Full host backing for those misses plus PLE is
**53,427,850,240 B**; retaining the entire expert source plus PLE instead is
**77,427,850,240 B**, before staging and runtime overhead. These are distinct
policies, not two allocations to add together. Dynamic eviction may need
pages of cached experts again; account for that page-cache pressure.

The [host-memory design](../../qwen38-flash-next-fp8-b70/notes/2026-10-08-host-memory-reduction-design.md)
and [stability guide](../../../docs/host-stability-and-fault-diagnosis.md)
record expensive multi-card host shadows, but also a single-card 16 GiB
allocation probe with unchanged MemAvailable. Do not automatically charge
the multi-card shadow to this one-card process or assume ours has none.
Record actual MemAvailable, RSS/PSS, GPUActive, pinned slabs, file pages and
capture/load peaks without double-counting aliases. No host setting changes.
The 15 GiB two-card host cannot hold this miss bank plus PLE in RAM: it needs
a separate storage-I/O design and cannot inherit these ceilings. One card
describes GPU count, not a promise of low system-RAM requirements.

## 2. Three mechanisms and their costs

### A. Stream selected experts over PCIe

Device routing chooses all top-10 IDs and weights in the registered order.
Gather their exact packed gate/up/down slices from admitted host backing
into bounded device slots, then use the same device kernels as the resident
two-card line. Preserve scales inside the grid bytes. Never migrate a whole
512-expert bank to obtain ten experts.

For an ordinary layer, a triplet is `2 × 640 × 820 + 2560 × 360 =
1,971,200 B`. Layer 2 uses `2 × 640 × 1100 + 2560 × 360 = 2,329,600 B`.
Thus **47 × 10 × 1,971,200 + 10 × 2,329,600 = 949,760,000 B/token**.
The whole-model **4,951,240,940 B/token** is 4,001,477,120 dense +
949,760,000 experts + 3,540 lookup + 280 metadata bytes. Streaming all
4.95 GB would incorrectly charge resident dense tensors to PCIe.

| All-miss transport scenario | Transfer floor/token | Transport-only ceiling |
| --- | ---: | ---: |
| Historical inferred migration, 19 GB/s | 49.987 ms | 20.01 tok/s |
| PCIe 4.0 ×16 theoretical, one direction | 30.144 ms | 33.17 tok/s |
| Historical effective paging, 7 GB/s | 135.680 ms | 7.37 tok/s |

PCIe arithmetic is `16 GT/s × 16 lanes × (128/130) / 8 = 31.507692 GB/s`,
before transaction/protocol overhead; it is not measured link payload rate.
The [September 5 timings](../../qwen38-flash-next-fp8-b70/notes/2026-09-05-day-summary.md)
give roughly 19 GB/s from whole-buffer migrations of 419/210 MB in
21.7/12.2 ms and roughly 7 GB/s effective paging. Neither is our wrapper's
pinned H2D benchmark. Page faults, host gathers, packet overhead, synchronization
and dequantization reduce end-to-end speed. Only one link is credited here.

The packet 2 lower bounds for GPU packed reads are 0.171669–0.181827 ms
for an ordinary GDN layer, 0.237038–0.251064 ms for layer 1 with PLE
projections, 0.198738–0.210497 ms for upgraded layer 2, and
0.163626–0.173308 ms for QSA. They assume 537–507 GB/s from other lab
kernel families, not a measured IQ3 kernel rate. All logical token reads at
those rates cost **9.220–9.766 ms**, before KV/state/activation traffic,
repeated packed accesses, codebooks and actual compute. At 19 GB/s with
no overlap, adding the optimistic 9.220 ms floor gives **16.89 tok/s**.
Even the perfect-overlap bound cannot exceed 20.01 in that all-miss scenario.

**Prefetch has a dependency limit.** Exact next-layer top-10 normally depends
on this layer's completed expert result and the next attention/GDN branch.
It cannot generally be known while the current layer computes. A proposed
next-layer prefetch behind current-layer work is therefore a measured
prediction/cache-policy experiment, not guaranteed overlap: wrong guesses
transfer extra bytes, every true miss is still fetched, and no route changes.
Begin with current-layer miss copies overlapping independent resident-expert
work or the shared branch, buffering results for the original reduction
order. Gate/up and down slices can also be pipelined once routes are known.
Measure the exposed per-layer wait; do not model all 48 layers as one freely
overlappable transfer. With only one compute queue, there is no extra GPU
compute concurrency to assume.

The [packet 3-prep CopyEngine](../stage1/packet3-prep/README.md) owns at most
two pending copies of at most 128 MiB each; an ordinary top-10 layer is
19.712 MB, layer 2 is 23.296 MB. Its current in-order queue and retained
preceding-copy dependencies **do not prove independent copy/compute overlap**.
Extend our wrapper with separately owned copy-engine events/queue only under
native lifetime tests. A host gather following route readback is segmented
replay. A device-indexed UVA gather is a distinct path needing stable pinned
backing and actual-byte tests; it must not inherit the explicit-copy rate.

### B. Keep a hot-expert cache on the device

Cache complete packed expert triplets; keep a device table mapping layer and
expert ID to a stable slot or miss descriptor. Slots remain leased until all
dependent work drains. An immutable initial set and deterministic eviction
tie-break make traces reproducible; cache state may change scheduling, never
model arithmetic. All 512 experts/layer remain callable.

No matched IQ3 one-card hit histogram is established in the retained notes.
Use the explicit **uniform-access assumption** `h = C / 48,627,712,000`
with proportional capacity across layers; `miss_B = 949,760,000 × (1-h)`.
Here h is a byte-weighted hit fraction; integer slots and layer imbalance
need the real trace. The sizes are total decimal GB on this one card.

| Cache GB | Assumed hit % | Miss B/token | Miss ms at 19 GB/s | Ceiling at 19 GB/s | Ceiling at PCIe theoretical |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 8 | 16.45 | 793,510,000 | 41.764 | 23.94 | 39.71 |
| 16 | 32.90 | 637,260,000 | 33.540 | 29.82 | 49.44 |
| 24 | 49.35 | 481,010,000 | 25.316 | 39.50 | 65.50 |

Units in the last two columns are tok/s, transport-only. Add ideal 9.220 ms
GPU reads with zero overlap to obtain respectively **19.61, 23.39, 28.95
tok/s** at 19 GB/s; real compute/dispatch adds more. At 7 GB/s, the
transfer-only ceilings are **8.82, 10.98, 14.55 tok/s**. Under the strict
32 decimal GB budget use a smaller admitted cache (16 GB is the tabulated
safe starting point); the 24 GB row is conditional, as the budget states.

The [A316 note](../../qwen38-flash-next-fp8-b70/notes/2026-09-07-a316-decode-window-census-and-the-rebuilt-placement.md)
predicts hot-rank parked-expert selections falling **12.410% → 0.048%**
(rounded 12.4% → 0.05%), with parked counts 543/587/550/586 unchanged.
That is FP8 TP4, with about half the routed census blocks from prefill.
Changing **which** experts were parked did not produce a speed improvement:
[A314](../../qwen38-flash-next-fp8-b70/notes/2026-09-07-a314-negative-host-placed-selections-cost-nothing.md)
reported a mean −0.021 tok/s change, within noise. Persistent page migration
was a hypothesis. These are not measured IQ3 cache hits and do not imply a
99.95% hit rate or that every parked selection paid a fresh PCIe transfer.

Collect fixed-suite routing traces from the CPU oracle for observation, but
do not train the final cache placement on those benchmark answers. Set policy
from independent data or a content-independent allocation; reset declared
cache state per cold attempt and charge fills. Immutable weight residency
is allowed; prompt/KV/response reuse or learned draft behavior is not.

### C. Compute nonresident experts on the CPU

Keep resident experts on GPU and run missing experts directly from packed
host memory using our AVX2 GEMV; AVX-512 is an option only on a supporting
host. Send the layer's BF16 activation and route IDs/weights to CPU, and
return each expert's BF16 result to its original route slot. GPU combines
them in the registered order. For ten misses this is approximately 5,120 B
of shared input plus 51,200 B of outputs/layer, about **2.70 MB/token** for
48 layers, plus descriptors and any explicitly required intermediates.
At 19 GB/s that payload alone is 0.142 ms; 48 synchronization boundaries
and dependency latency are likely more material. Do not combine experts on
CPU in a new order just to reduce the return payload.

The [exploratory fitter](../../qwen38-flash-next-ud-iq3xxs-b70/explore/README.md)
shows **21.64 tok/s decode and 49.8 prompt tok/s**, one B70, 63 output
tokens; two cards recorded 25.9–26.9 tok/s. The fitter assigned some tensors
to CPU, which is the relevant hybrid-compute idea. Its quiet log did not
retain the split, so it does **not** prove an expert-only CPU assignment.
Outputs differed after the first sentence. This is feasibility evidence,
not a certified speed or exactness target, and none of its runtime code is
our implementation base.

`/proc/cpuinfo` read during this task identifies **Threadripper PRO 5955WX,
16 cores/32 threads, AVX2/FMA and no AVX-512**. The
[host hardware notes](../../../docs/host-stability-and-fault-diagnosis.md#the-machine)
record four 32 GB DDR4-3200 DIMMs in A1/B1/E1/F1. Four populated 64-bit
channels give `4 × 3.2e9 × 8 = 102.4 GB/s` theoretical. No sustained DDR
measurement was found; `/proc` does not measure memory bandwidth. The
40/60/80 GB/s rows below are assumptions, not readings or an assertion that
16 cores attain them. This CPU-only task used nice 19 and OMP_NUM_THREADS=2;
it did not run a 16-core bandwidth or model test.

| Assumed sustained host GB/s | All experts on CPU: ms / bandwidth ceiling tok/s | 24 GB resident cache: miss ms / bandwidth ceiling tok/s |
| ---: | ---: | ---: |
| 40 | 23.744 / 42.12 | 12.025 / 83.16 |
| 60 | 15.829 / 63.17 | 8.017 / 124.74 |
| 80 | 11.872 / 84.23 | 6.013 / 166.32 |
| 102.4 theoretical only | 9.275 / 107.82 | 4.697 / 212.89 |

Formula: `CPU_read_ms = miss_B / (host_GBps × 10^6)`. This assumes each
packed byte read once and excludes decoder instructions, gathers/codebooks,
cache-line amplification and activations. All selected experts require
`480 × 4,915,200 = 2,359,296,000` multiply-add pairs/token; CPU misses with
the assumed 24 GB cache account for **about 1.195 billion** pairs
(`2,359,296,000 × (1 - 24,000,000,000 / 48,627,712,000)`). Separate rounded
multiply and add, format decoding and a fixed reduction tree can dominate
DDR. Parallelize independent rows/experts over 16 physical cores, preserving
each row's accumulation; do not divide elapsed memory time by 16 again.

Resident GPU reads with that cache are `4,001,477,120 + 468,750,000 =
4,470,227,120 B/token`, a **8.324 ms** floor at 537 GB/s. At assumed
60 GB/s host bandwidth, the perfect-overlap combined bound is therefore
`1 / max(8.324, 8.017) ms = 120.13 tok/s`, and no-overlap ideal work sums
to **61.19 tok/s**, before transfers and compute. These are deliberately
optimistic bounds, not expected production speed. CPU work can overlap GPU
resident/shared work within a layer; the next layer still waits for its
combined input. CPU expert reads, PLE page activity and DMA share host
bandwidth; do not add their separately measured peak rates.

## 3. Recommendation and identity gates

Start with cache plus explicit streaming: it preserves the qualified device
arithmetic and exposes real bytes, unlike uncontrolled whole-bank migration.
Admit 16 GB first, then grow toward 24 GB if measured capacity permits.
Its conditional 19 GB/s ceiling is **29.82 tok/s at 16 GB, 39.50 at 24 GB**;
unhidden ideal GPU reads reduce those to 23.39/28.95. All-miss streaming's
20.01 ceiling makes it a useful control, not the preferred placement.
CPU misses may raise the bandwidth ceiling substantially (the 24 GB/60 GB/s
scenario above is bounded at 120.13 with ideal overlap), but exact-kernel
throughput and layer stalls must be measured before predicting a useful rate.

Streaming and caching are bit-neutral **only if packed bytes, per-row math,
casts and route combination order remain unchanged**. Placement must not
select a different reduction or let completion order choose the sum order.
CPU compute additionally needs the same 32 logical lanes and adjacent tree
as [packet 2's shared header](packet2/kernels/math.hpp): each lane visits
columns lane, lane+32, …; multiply/add round separately, tree widths are
1/2/4/8/16, final BF16 rounding occurs at the same boundary. Vectorize
independent lanes/rows without horizontal reassociation or FMA contraction;
pin rounding, denormals, compiler flags and activation/SiLU semantics too.
The shared header makes a common implementation possible, **not already
proven** across AVX and Xe. Require accumulator and output bits, routing and
state equality, then full cold outputs and fresh-process determinism against
the IQ3 oracle. Any disagreement blocks adoption; no FP8 tolerance rescues it.

## 4. Packet ladder after the two-card line works

Reuse two-card loader, operator and full-output gates first. These packets
are plans; the present task performs no native or model-payload work.

| Packet | Work and measurements | Exit gate |
| --- | --- | --- |
| OC1: CPU placement and traces | Reconcile one-card census, admit both context budgets, collect CPU-oracle routing IDs/weights/order for the fixed varied suite. Report per-layer/expert counts, prefill separately from decode, byte-weighted hits at 8/16/24 GB, cold fills, reuse distance and eviction misses. | Trace identity binds model, prompts and oracle arithmetic; no inferred FP8 histogram or final-suite-trained placement. Every expert has a fallback. |
| OC2: bounded transport window | Our packet 3-prep CopyEngine on the intended physical card/host: changed-pattern H2D at 1,971,200 and 2,329,600 B per expert, 19,712,000 and 23,296,000 B per top-10 layer, contiguous versus gathered slices. Measure route-readback, host gather, pin/copy setup, completed-event payload rate, exposed wait, bytes moved and concurrent compute interference. Separately measure UVA amplification. | Byte-exact transfers, bounded ownership, actual H2D rate, no fault, drained graceful exit; a second owned copy path needs its own lifetime/dependency tests. No automatic retries. |
| OC3: one-card all-miss and cache operators | All layer shapes, cache hit/miss/eviction paths, changed routes, in-flight slot reuse rejection; compare against unchanged resident kernels. Measure cache occupancy, all miss bytes, kernel time, copy overlap and peak host/device allocations. | Exact outputs/state across policy and address changes, repeated fresh processes; replace memory allowances with measured admission. |
| OC4: CPU expert candidate | First measure sustained DDR with admitted buffers and 16-core placement in a separately permitted CPU window, then exact AVX2 mixed-grid dequant+GEMV at real shapes. Record all-core bandwidth, compute time, row parity and simultaneous DMA contention. | CPU/device accumulators and BF16 outputs exact; no reassociation/FMA shortcut. AVX-512 needs a different host's own gate. |
| OC5: complete one-card target | Own prefill plus decode at 4K and 16K; graph/segmented-replay labels honest, PLE timing included. Compare each mechanism with matched controls and at least two fresh processes. | Full IQ3 oracle output/state/repeat gates; fixed realistic varied suite once per cold attempt, cached_tokens=0, natural 512-token cap, full 16-bit KV, no prompt/response reuse; report prefill/TTFT and class-balanced 99-interval decode plus full-completion rate. |
| OC6: recipe evidence | Retain byte budgets, source/binary identities, traces, receipts, failed arms and measured contexts; qualify startup/teardown and host-RAM requirements. | Separately reviewed promotion and publication; projections never replace measured results. MTP is a later separately budgeted, target-verified extension. |

**First measurement needed:** actual H2D payload rate on this host through
our bounded copy wrapper at expert and top-10 sizes, including gathered
sources and exposed synchronization time. In parallel preparation, obtain
the fixed-suite CPU-oracle routing statistics; these decide whether a hot
cache beats the uniform assumption. Do not launch either a native window or
a 16-core CPU workload under this document's CPU-only preparation authority.

Validation for this document: arithmetic reconciled against the retained
census and packet 2 roofline; repository links checked. No downloads, model
payload reads, GPU/device access, server, Docker, systemd or host-setting
change; no scratch retained.
