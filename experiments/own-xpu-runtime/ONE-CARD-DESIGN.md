# One-card IQ3 Flash-Next: cached experts and exact CPU misses

2026-10-17. **Design only: no fit, CPU-throughput or device result.** Target:
one 32 GB B70, the Unsloth UD-IQ3_XXS **quantized compressed version** at
revision `766911a6b7369840a91dbcd95f9f997acaab6cd6`, unchanged
`iq3-p17-detmath-v2` oracle and full 16-bit KV. The
[roadmap](../../notes/2026-10-17-own-runtime-iq3-speed-roadmap.md) supplies the
two-card timing evidence and priorities. The older
[target-only plan](stage2/ONE-CARD-PLAN.md) remains historical; this design
adds the now-qualified separate MTP weights and current expanded allocations.

Credit **Niko1221 / Strata** for the publicly described GPU hot-expert cache,
pinned host experts with parallel CPU computation of misses, host/SSD PLE,
GPU attention/shared experts/head/state and MTP arrangement. The
[owner-supplied public description](https://vramcalculator.com/strata-qwen3-8-flash-next)
is design inspiration, not code or verified performance evidence. No Strata
source was read, copied or ported. All proposed implementations belong to this
lab; follow the [own-runtime objective](../../docs/own-xpu-runtime-objective.md).

## Placement and dependencies

Keep target attention/DeltaNet, HC, routers, shared experts, head and state on
GPU. Keep the complete existing MTP layer on GPU initially, sharing the target
head. Reserve a bounded cache of complete target experts. CPU workers compute
selected experts missing from the cache directly from their original packed
host bytes. PLE and input embedding stay host-backed, as in packet45.

For each layer:

1. GPU produces the exact MoE input and ordered top-10 route descriptors.
2. Copy one BF16 input vector and descriptors into a stable pinned mailbox;
   dispatch CPU misses by original slot. Concurrently run GPU hits and shared
   expert work on the sole compute queue, using a hit/miss mask that skips no
   selected expert overall.
3. Return each CPU expert's complete BF16 down result into its original slot.
   A completion event and request/position/layer/generation tag protect every
   slot. Preserve the GPU's original ten-slot accumulation, shared-expert
   addition, casts and HC residual. Do not sum CPU results by completion order.
4. Only after the combined result is complete may the next dependent layer run.
   All-hit and all-miss cases use the same arithmetic. An error poisons the
   request; it never supplies zeros or stale cached outputs.

CPU work can overlap current-layer GPU work; it cannot be assumed to overlap
an entire future model pass. Immutable **weight** caching is permitted; cached
answers, activations, KV, prompt reuse or learned drafts are not. Freeze a
content-independent first placement, then use independent calibration data
for a later hotness policy. Keep benchmark prompts out of cache training.
Record cold-fill policy and charge fills/evictions; bound all cache and mailbox
lifetimes. No inference-time SSD expert fetch belongs in the fast-path claim.

## Actual bytes, not a uniform three-bit model

The [GGUF tensor census](../qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json)
and [mixed-format accounting](stage2/packet1c/comparison.md) describe 48 layers,
512 experts/layer, top 10, hidden 2560 and intermediate 640. There are
**zero IQ3_XXS tensors**: the release name describes a mixed quantization.

| Stored item | Bytes |
| --- | ---: |
| Ordinary expert gate or up, IQ2_S: 640 rows × 820 B | 524,800 |
| Ordinary expert down, IQ4_NL: 2,560 rows × 360 B | 921,600 |
| **Ordinary complete expert** | **1,971,200** |
| Layer-2 gate or up, IQ3_S: 640 × 1,100 B | 704,000 |
| **Layer-2 complete expert** | **2,329,600** |
| All 24,576 target experts | **48,627,712,000** |
| Packed target nonexpert tensors, excluding input embedding and PLE table | **4,001,477,120** |
| Input embedding | 521,472,000 |
| Packed nonexpert including embedding, excluding PLE table | 4,522,949,120 |
| PLE table | **28,800,138,240** |
| All nonexpert tensors including both lookup tables | **33,323,087,360** |

Each position selects **949,760,000 B** of expert weights, independent of IDs:
47 ordinary layers × 10 × 1,971,200 plus 10 × 2,329,600. There are 480 expert
evaluations and **2,359,296,000 multiply-add pairs** per target position.
Selected PLE rows cost only 1,440 packed B and the embedding row 2,100 B;
the existing path uploads 10,240 decoded BF16 B. SSD page faults and cache-line
amplification are separate from that payload; never read the whole PLE table
per token in a traffic estimate.

Strata's quoted approximately 700 experts/GB is not this checkpoint's size:
ours stores about **507 ordinary experts per decimal GB**, or 429 exceptional
experts/GB, before metadata/alignment. Borrow placement ideas, not its capacity
ratio or speed multiplier.

### MTP-aware 4K capacity example

The live allocation inventory in
`stage2/packet45-merged3/evidence/audit6/W2m-c4096-dr1-r{0,1}/census.json`
gives target nonexpert 2,502,886,144 + 3,316,838,144 B, including one
4,194,304-byte RoPE table per rank. Deduplicate that table on one card.
Expanded weight layouts are retained; reverting to smaller packed dense
kernels needs separate exactness and speed qualification.

| Device category | Bytes / status |
| --- | ---: |
| Target nonexpert, one RoPE table, host embedding | **5,815,529,984**, census-derived |
| All 512 draft experts | 3,145,728,000 |
| Draft nonexpert weights | 181,225,472 |
| Draft scratch/control plus 4K KV/index | 27,410,742 |
| **Target nonexpert + complete draft** | **9,169,894,198** |
| Proposed target expert cache | **18,000,000,000**, design budget |
| Target 4K KV/index, GDN/conv/PLE state | 175,288,320, formula below |
| One target recurrent-state checkpoint | 58,896,384, allowance; full speculative write set still needs proof |
| Workspaces | 1,073,741,824, assumed |
| Static/graph/transaction buffers | 1,073,741,824, assumed |
| Device transfer slots | 268,435,456, assumed |
| **Illustrative owned total** | **29,819,998,006** |
| Remaining below 30 GiB arena | **2,392,256,714** |
| Remaining below conservative 32 decimal GB capacity | **2,180,001,994** |

The last line must retain at least the existing **1.5 GB card reserve**; only
about 680 MB beyond that remains in this conservative example. The arena and
physical reserve are separate checks. Allocation alignment, code/driver pools,
prefill peaks, pinned-memory shadow, graph rebuild overlap and complete MTP
rollback may consume that margin. **This is not admission.** Do not count the
same driver reserve twice; measure owned and non-owned peaks separately.

The shared expanded target head is already 839,321,600 B inside target
nonexpert bytes; do not allocate a second draft copy. Current draft residency
is **3,354,364,214 B**, not the target-only plan's zero. At capacity T, target
K/V is `12*T*2*2*256*2`, index storage `12*(T+ceil(T/4))*128*2`, recurrent
state `36*48*128*128*2`, conv history `36*10240*3*2`, PLE history `10240*3*2`.
Longer contexts need a new budget for target **and draft** plus rollback.

A concrete content-independent 18 GB cache can store 189 experts in each
layer plus one extra in 25 ordinary layers: **9,097 experts**, occupying
17,999,744,000 B before metadata/alignment. The ordinary-only upper count is
9,131. Final IDs and per-layer quotas must be explicit; a global hottest list
without layer coverage can leave individual layers CPU-bound.

Host backing for all target experts plus PLE is **77,427,850,240 B**, before
embedding, draft/loader copies, workers, staging, OS and driver shadow. Do not
pin a second expanded copy or assume that mmap/read-ahead pins pages. Retain
immutable packed backing, bounded transfer slabs and page-admission receipts;
whole-bank pinning is a future allocation decision. The active four-card FP8
experiment is not a place to test or allocate this design.

## Hit rate and CPU requirements

**The IQ3 hit rate is unknown.** The named routing files actually live under
`experiments/qwen38-flash-next-fp8-b70/data/20260907-tp4-mtp1-a315-routing-census-rank*.json`.
The [A315 diagnosis](../qwen38-flash-next-fp8-b70/notes/2026-09-07-a315-routing-census-and-the-window-problem.md)
says dumps preceded generation and were dominated by startup dummy routing:
rank 0 had 1,794,890 selections versus roughly 210–217 thousand on other ranks.
It explicitly rejects those histograms for placement. A316 corrected the
window, but FP8 arithmetic and mixed workloads still do not establish IQ3
popularity. Packet45 preserves route hashes, not recoverable per-token IDs.
The method of collecting routes transfers; the hit percentages do not.

Under a **hypothetical uniform, proportionally allocated** 18 GB cache,
byte hit rate is 37.016%, average CPU misses about 302.324 experts/position,
miss payload 598,197,500 B, and CPU work 1.485981 billion ordered multiply-add
pairs/position. Integer quotas and layer-2 size make small differences; these
are scenario values, not observed counts.

| Assumed byte hit rate | CPU MB/target position | CPU billion MAC pairs/position | Host GB/s needed at 60 target positions/s | Billion MAC pairs/s at 60 |
| --- | ---: | ---: | ---: | ---: |
| 37.016%, uniform 18 GB scenario | 598.198 | 1.486 | **35.892** | **89.159** |
| 60%, hypothetical measured-hotness target | 379.904 | .944 | 22.794 | 56.623 |
| 80%, hypothetical | 189.952 | .472 | 11.397 | 28.312 |
| 90%, hypothetical | 94.976 | .236 | 5.699 | 14.156 |

The last three rows assume comparable miss fractions across layer formats;
they are not a fitted cache curve. At **100 target positions/s**, uniform
18 GB requires **59.820 GB/s and 148.598 billion MAC pairs/s**, or about
297.2 GFLOP/s of separate multiplies/adds before unpacking, lookup, deterministic
SiLU and reduction overhead. At 60 it requires about 178.3 GFLOP/s.
To target emitted tok/s, multiply these rates by measured **target positions
executed per emitted token**, including rejected work. Do not apply MTP's
claimed speedup as a discount on necessary target verification.

[Host facts](../../docs/host-stability-and-fault-diagnosis.md#the-machine):
**Threadripper PRO 5955WX: 16 physical cores, 32 threads**, AVX2 rather than
AVX-512. Four 32 GB DDR4-3200 DIMMs occupy four channels: **102.4 GB/s theoretical**,
not an eight-channel sustained rate. **Sustained host bandwidth is unknown**;
no retained measurement was found. The approved fence of blocks **53–57**
removes 10 GiB; keep it unchanged. CPU experts, DMA and PLE share memory
bandwidth. Future CPU throughput tests need a separate quiet window; this
study ran only low-priority metadata/source analysis on cores 4–15,20–31.

### PCIe and the critical path

CPU misses exchange one 5,120-byte BF16 input per layer and one 5,120-byte
result per missing expert, plus route/status tags. Uniform 18 GB therefore
moves about **1.794 MB/target position**, or **107.6/179.4 MB/s at 60/100
positions/s**. All misses would move 2.703 MB. This is small payload but up to
48 dependent round trips; CPU tail latency, not link payload alone, can stall
every layer. Never return just a CPU partial expert sum with a different order.

Packed weight streaming instead transfers **598.2 MB/position** in that scenario:
21.36 ms at the historical packet5 approximately 28 GB/s H2D, or 31.48 ms
at illustrative 19 GB/s, before GPU work. Neither is a measurement of scattered
expert-cache fills. Use streaming as the exact GPU control/fallback, and charge
actual fills. Copy overlap is allowed only when producers are complete and
buffers remain live; the next layer's route cannot be guessed as verified work.

The [current useful-byte census](../../notes/2026-10-15-p45-roofline-and-structural-levers.md)
counts 5.521231360 GB non-routed target reads/position, excluding host lookup
tables. With the uniform 18 GB cache, GPU expert hits add .3515625 GB:
**5.872794 GB, or 9.788 ms at 600 GB/s** (10.678 ms at 550).
One current draft reads about **1.037289 GB, another 1.729 ms at 600 GB/s**.
Use these useful-byte counts for read floors, not the larger allocation sizes
including unused expanded metadata. Add state, scratch, decode instructions,
launches and synchronization; no complete one-card speed forecast follows.

At an illustrative sustained host 60 GB/s, CPU miss reads alone need 9.970 ms.
For target work, perfect whole-step CPU/GPU overlap would bound elapsed below
by `max(9.788,9.970)` ms; no overlap gives 19.758 ms of these ideal read costs.
Neither is a measured bound on instructions or a viable scheduler forecast:
real dependencies require summing per-layer maxima, and dense attention precedes
the CPU MoE input. Even a memory-only model cannot import Strata's 1.6–1.8× MTP
multiplier. The one GPU compute queue serializes GPU draft and target; only
CPU miss work and independent copy-engine work can overlap GPU compute.

## Bit-exact CPU expert contract

Exactness is feasible in principle; **fast exact AVX2 execution is unmeasured**.
A generic quantized CPU GEMV, BLAS call, FMA rewrite or FP8 oracle does not
satisfy this contract. Match the actual selected packet45 expert kernels:

- Decode the same IQ2_S/IQ3_S/IQ4_NL codebooks, integer signs, scale operations
  and FP32 values. Preserve intermediate FP32 multiply/add rounding.
- Current v2 arithmetic assigns **eight consecutive values to each logical
  lane**, starting at `256*tile + 8*lane`; preserve lane iteration and adjacent
  SG32 reduction order. Preserve split-four `(p0+p1)+(p2+p3)` wherever the
  selected kernel uses it. Do not revive the old plan's strided-lane dot order.
- Preserve separate gate/up BF16 results, deterministic SiLU and product/cast
  boundaries, exact down output and original slot-order mixture. Use our
  [deterministic math](stage2/packet17-detmath/README.md), not host `expf`.
- Preserve round-to-nearest, denormals, signed zero, nonfinite rejection and
  sticky-error behavior; no contraction, fast math or reassociation. Historical
  CPU compiler fixtures had NaN-payload differences: test the registered
  exceptional-value/error contract explicitly, never silently tolerate it.
- Parallelize independent rows/experts; vectorize independent logical lanes
  without reassociating a row. Route location and completion order cannot
  change any output bit or arithmetic-v2 oracle.

Source contracts: [packet28](stage2/packet28-dense/README.md), its
[expert kernel](stage2/packet28-dense/expert.hpp) and
[design](stage2/packet28-dense/expert-design.md), and
[merged3 kernels](stage2/packet45-merged3/KERNELS.md). The eventual CPU kernel
must be checked against the **selected current P39/P28 composition**, not just
an older generic reference with another tree.

## Bounded implementation ladder

| Stage | Deliverable and gate |
| --- | --- |
| 1. Static design / CPU exactness | Independently authored mixed-format CPU expert; compare intermediate FP32 accumulators, BF16 gate/up/down and errors with existing oracle fixtures. Cache/miss dispatch must reproduce all-GPU slot order for all-hit, all-miss and mixed routes. No model-weight sweep is authorized by this note. |
| 2. CPU throughput and route evidence | In a separately admitted quiet window, measure sustained DDR and exact expert throughput including dequant/SiLU, tail distributions and thread topology. Collect actual IQ3 per-layer routes on independent calibration inputs; log IDs, misses, fills and target work per emitted token. |
| 3. One-layer native composition | Once devices are available, compare GPU-only versus GPU-hit/CPU-miss complete GDN/QSA layers, all route placements and changed inputs, exact state and fresh owners. Measure D2H, CPU ready/compute, GPU hit, H2D and exposed wait separately. Reject infeasible CPU arithmetic before building a server. |
| 4. Full target-only one-card path | Prove allocation peak within arena/card/host limits and fixed full-16-bit context. Complete cold-suite exactness and fresh-process determinism; report prefill and decode separately. Streaming fallback preserves correctness, with slowdown recorded. |
| 5. MTP and temporal verifier | Add the existing qualified draft identity with shared head; gate M2 against two serial target positions and every accepted-prefix state. Keep separate recurrence/KV updates and rollback on misses. Measure one-card acceptance and total cost; do not inherit a two-card or Strata multiplier. |

The first useful speed decision is whether CPU misses meet the **per-layer
remaining budget after GPU attention/shared work**, not whether a standalone
CPU GEMV looks fast. If exact CPU arithmetic misses that budget, retain the
negative result and pursue better weight/dequant sharing, cache placement from
valid independent traces, or specialized GPU streaming. No lower precision,
pruning, skipped expert, changed oracle or power/host-setting change is implied.
