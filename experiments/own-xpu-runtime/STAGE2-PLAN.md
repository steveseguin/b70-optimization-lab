# Stage 2 — Flash-Next on four cards, then a separate two-card quant lane

This is a CPU preparation plan, **not native authorization, a measured runtime
result or a claim that two cards fit**. The present job permits no GPU, server,
systemd, port or device access. The owner's exclusive native window and current
fault-halt decision are prerequisites for every native packet below. Existing
model trees and the video lane stay protected. Stage 1's pending decisions are
independent; its CPU loader format work is reusable.

## Target and frozen authorities

The first target is official `Qwen/Qwen3.8-Flash-Next-FP8`, revision
`bcd9f01ddc9cff2316eb84281bebcd5b058bddce`. [Packet 1](stage2/packet1/README.md)
freezes 152,089 tensor descriptions, 131 headers and the 12 complete A367 output
arrays (5,979 tokens). It authenticates metadata, **not shard payloads**.
Architecture: H2560, 48 layers (36 GDN, 12 QSA), 512 experts/layer, top10,
FFN640 and shared640, four HC streams/rank320, PLE at `layers.1`, one native
MTP QSA/MoE block. BF16 activations and full 16-bit KV; **BF16 GDN inter-row
state on this certified line**, distinct from 27B's FP32 profile.

The [identity](stage2/packet1/identity.json) and [oracle](stage2/packet1/oracle-token-ids.json)
bind certified TP4/EP4, exact serial GDN, QSA/HC overlay, native MTP1, full
capture [1,2], 4,352 capacity and **46.85424994838007 tok/s** class-balanced
99-interval rate. Preserve the chat template, one user message, no system
message, thinking disabled, seed20260609, greedy settings and natural512 cap.
The [handoff](../../results/qwen38-flash-next-fp8-b70/HANDOFF.md) is historical
execution evidence; CURRENT remains live authority. Exactness retains the
inherited code-answer miss, not a new claim of perfect task quality.

## Four-card quantitative case — arithmetic, not measurement

[Checked census](stage2/packet1/tensor-contract.json): **10,983,590,682 logical
weight bytes/target token**, of which 2,359,584,000 are selected experts;
**1,501,698,416 more per full-head MTP proposal**. Count BF16 scales. The
[placement census](stage2/packet1/placement-census.md) gives EP4 whole-expert
ownership (128/rank/layer), sharded dense projections/head, vocabulary-sharded
host PLE/input embeddings, and replicated HC matrices. An expert is not a
quarter-sized matrix. Adding HC's three extra copies gives
`10,983,590,682 + 3 × 1,271,398,400 = 14,797,785,882 B/target` across TP4.

Optimistically balance all other bytes over ranks: **3,699,446,470.5 B/card**,
including 589,896,000 expected expert bytes/card (2.5 of top10/layer on average),
1,271,398,400 replicated HC bytes/card, and 1,838,152,070.5 remaining bytes.
The half byte marks an aggregate arithmetic average, not a physical allocation.
This is a **lower-bound accounting model of the certified split**, not an
exact rank traffic trace. Other replicas (routers, two KV heads over four
ranks, PLE projections, small norms/index state), imbalance, padding and scale
widening make it larger. A target layer can route all ten experts to one rank;
never assume the average describes the slowest rank. Off-device bytes must
use their actual transport, not VRAM bandwidth; including their tiny selected
PLE/embedding payload in the fast-rate denominator is optimistic.

The [27B receipt](../qwen38-27b-b70/notes/2026-09-16-fp8-review-findings.md)
reports about **507 GB/s** for its streaming linear family. The
[LTX diagnostic receipt](../ltx25-b70/notes/dispatch-bound-diagnosis-01.md)
reports **536.8 GB/s**, rounded here to **537**. These are measured family
rates on their stated workloads, **not Flash TP4 simultaneous bandwidth**.
Use decimal GB/s, no advertised peak FLOPS. `floor_ms = bytes/card / (rate ×
10^9) × 1000`; computation, state/KV/activation traffic, collective waits,
launch/replay overhead and PCIe misses are absent. A matching exact-math compute
floor remains unmeasured.

| Explicit weight-reuse scenario | B/card | Floor at 537–507 GB/s | 33.69 ms / floor |
| --- | ---: | ---: | ---: |
| One target, balanced EP; optimistic M=2 identical experts and weights read once | 3,699,446,470.5 | **6.889–7.297 ms** | **4.62–4.89×** |
| M=2, dense weights read once, disjoint top10 expert sets on the two rows | 4,289,342,470.5 | 7.988–8.460 ms | 3.98–4.22× |
| M=2, every target weight read twice | 7,398,892,941 | 13.778–14.593 ms | 2.31–2.45× |

The measured **33.69 ms control forward at M=2** is A369's three-row timing
packet, in the [A378/A379 attribution note](../qwen38-flash-next-fp8-b70/notes/2026-09-13-a378-a379-row-wise-selector-cost-result.md),
not A367's full-suite timing. It decomposes into MoE14.2, QSA4.7, GDN2.1,
row-wise collective excess1.5 and about11.2 ms unattributed; HC selector cost
is about0.03 ms/noise. The 11.2 includes dense projection work and replay glue:
**it is not measured removable dispatch**. A378's 1.47 ms collective saving
changed output and cannot be adopted. The floor ratio is total forward time
divided by a hypothetical weight-streaming component; it is neither achieved
speedup nor proven recoverable overhead. Under the first scenario the excess
is 26.39–26.80 ms (3.62–3.89 floor units), to be localized by the native census.
This sizeable gap justifies our runtime; first target MoE dependency/parallelism,
QSA and dense/replay attribution, not an already free selector.

46.854250 tok/s corresponds arithmetically to **21.3428 ms/emitted token**.
MTP can commit one or two tokens/step; that reciprocal is not M=2 forward time.
Do not divide 33.69 by two or infer acceptance from different workloads.
A target plus full-head proposal adds HC-adjusted 404,915,804 B/card to the
one-target model (total4,104,362,274.5 B/card); rejected verifier work remains
extra. No per-emitted-token bandwidth prediction follows without measured
accepted counts, reuse and traffic. [Recomputable arithmetic](stage2/packet1b/planning-arithmetic.json)
and [calculator](stage2/packet1b/planning.py) retain the assumptions.

## Two-card capacity and PCIe arithmetic

The [weight-only gap](stage2/packet1/placement-census.md#what-two-cards-would-need)
is **64,958,850,586 B**, already after offloading PLE/input embeddings. At the
historical scenario capacity68,484,595,712 B, the FP8 device weight requirement
is133,443,446,298 B; KV alone adds753,139,712 B across two ranks. State, graphs,
scratch and exact extra replication still need admission. **65 GB is missing
capacity, not bytes transferred on every token**. At most top10 of512 per
layer are selected; misses depend on their distribution and resident set.

Transport evidence exists, but not a matched two-card streaming benchmark:
[Flash memory-class notes](../qwen38-flash-next-fp8-b70/notes/2026-09-05-day-summary.md)
record A171 effective paging around7 GB/s and the 48-set whole-buffer migration
probe around**19 GB/s** from419/210 MB divided by21.7/12.2 ms. These are inferred
rates from measured timings, not isolated pinned H2D/UVA throughput. The
[MiniMax contiguous H2D probe](../minimax_xpu_kv_offload/README.md) measured about
28 GB/s at64–256 MiB versus2.1–2.4 GB/s in a copy loop; that is cross-lane
context and is **not substituted as Flash throughput**. No spec rate is needed.
Plan with **19 GB/s aggregate conservative scenario** or an **optimistic38 GB/s
aggregate** assuming two independent simultaneous19 GB/s links, balanced
misses and no host-memory/root-complex contention. Neither is a demonstrated
upper hardware limit. All “ceilings” below are conditional bandwidth-only
ceilings at those rates, excluding compute, transfers of other data, granularity
amplification, staging and dequantization. At7 GB/s aggregate multiply the
19 GB/s result by7/19. UVA whole-buffer migration can move far more than a
selected expert; explicit bounded staging must prove actual bytes first.

Each expert has `3 × 2560 × 640 = 4,915,200` weight elements; one target token
selects `48 × 10` triplets. Use the [GGUF block table](stage1/packet1b/loaders/FORMAT.md):
IQ4_XS136/256, IQ3_XXS98/256, Q3_K110/256 bytes/element block, including grid
scales. No extra FP8 scale is added to GGUF grids. FP8 adds600 BF16-scale
bytes/triplet. MTP adds ten triplets separately.

**UD names are mixed quantization recipes, not homogeneous grid declarations.**
The following rows compute the requested *grid* scenarios; actual Unsloth
per-tensor types, upgraded experts/dense/PLE/MTP bytes are still unknown. Only
file metadata, not those GGUF headers, is frozen. Do not publish these as
Unsloth's measured active bytes or fit. Packet2 must replace each scenario
with the complete header census and preserve the difference.

| Scenario / allowed candidate | Triplet B | Expert B/target token | All49 expert banks B | Stream all experts, tok/s at19 /38 GB/s |
| --- | ---: | ---: | ---: | ---: |
| Official FP8 + BF16 scales | 4,915,800 | 2,359,584,000 | 123,327,590,400 | **8.05 /16.10** |
| Unsloth UD-IQ4_XS, idealized IQ4_XS experts | 2,611,200 | 1,253,376,000 | 65,509,785,600 | **15.16 /30.32** |
| Unsloth UD-IQ3_XXS, idealized IQ3_XXS experts | 1,881,600 | 903,168,000 | 47,205,580,800 | **21.04 /42.07** |
| Unsloth UD-Q3_K_XL, idealized Q3_K experts | 2,112,000 | 1,013,760,000 | 52,985,856,000 | **18.74 /37.48** |

For FP8 retaining the maximum possible resident expert bank, assume **uniform
routing**, proportional misses and no reserve: miss fraction
`64,958,850,586 / 123,327,590,400 = 52.6718%`; active misses1,242,835,151.5
B/target give **15.29 /30.58 tok/s** at19/38 GB/s. This optimistic capacity
scenario already trails46.854250 before other costs, but is not a universal
impossibility theorem: routing skew can change it materially.

### Hot-expert cache sensitivity

Cache sizes below are **8/16/24 decimal GB total across both cards**, balanced,
not per-card and not extra on top of a resident full bank. Assume uniform
access across all49 target/MTP expert banks: `h = C / bank_bytes`, no hit
benefit from previous benchmark prompts; `miss_B = active_B × (1-h)` and
`ceiling = aggregate_rate / miss_B`. This conservative content-independent
hit assumption gives a reproducible sensitivity, not a measured hot-cache
prediction. A real hot cache could do better or worse under rank skew, cold
start, different tasks and policy overhead; charge every miss and do not train
it on the fixed final suite.

| Grid | 8 GB: hit%; ceiling19 /38 | 16 GB: hit%; ceiling19 /38 | 24 GB: hit%; ceiling19 /38 |
| --- | --- | --- | --- |
| FP8 | 6.49%; 8.61 /17.22 | 12.97%; 9.25 /18.51 | 19.46%; 10.00 /20.00 |
| IQ4_XS | 12.21%; 17.27 /34.54 | 24.42%; 20.06 /40.12 | 36.64%; 23.92 /47.85 |
| IQ3_XXS | 16.95%; 25.33 /50.66 | 33.89%; 31.82 /63.65 | 50.84%; **42.79 /85.59** |
| Q3_K | 15.10%; 22.08 /44.15 | 30.20%; 26.85 /53.70 | 45.30%; 34.26 /68.52 |

The [A316 census](../qwen38-flash-next-fp8-b70/notes/2026-09-07-a316-decode-window-census-and-the-rebuilt-placement.md)
reduced *predicted* hot-rank parked selections12.410%→0.048% at fixed543/587/550/586
parked experts/rank. It used a mixed prefill/decode window, about50% prefill by
routed blocks. [A314](../qwen38-flash-next-fp8-b70/notes/2026-09-07-a314-negative-host-placed-selections-cost-nothing.md)
found no measurable speed gain; persistent page migration was a hypothesis.
This does not establish99.95% hit rate in an8–24 GB two-card cache or permit
omitting any expert. The [cards-are-full note](../qwen38-flash-next-fp8-b70/notes/2026-09-13-a375-a376-32k-context-ladder-prereg.md)
and [host-memory accounting](../qwen38-flash-next-fp8-b70/notes/2026-10-08-host-memory-reduction-design.md)
explain why memory classes, physical ownership, PLE residency, shadows and
transient peaks must be counted separately; mmap is not free RAM.

### Verdict and source

**Prioritize Unsloth UD-IQ3_XXS as the two-card capacity/quality candidate,
prefer resident experts over streaming.** Keeping the official nonexpert
weight floor10,115,855,898 B and replacing only the49 expert banks gives:
IQ3_XXS57,321,436,698 B total, **11.16 GB** before KV/state/graphs; Q3_K63,101,711,898
B, **5.38 GB** remaining; IQ4_XS75,625,641,498 B, **7.14 GB too large**. These are
homogeneous-grid arithmetic, not actual UD allocation plans. Q3_K is a
conditional tighter alternative; IQ4_XS needs offload even in this scenario.
FP8 streaming is not the first two-card speed candidate. IQ3's all-miss
ceiling is42.07 tok/s under the optimistic38 GB/s assumption; a24 GB cache
with the stated50.84% hit assumption raises that transport-only bound to85.59.
If its full expert bank fits, this streaming bound no longer limits decode;
there is still no measured runtime speed prediction.

Use only `unsloth/Qwen3.8-Flash-Next-GGUF` revision
`766911a6b7369840a91dbcd95f9f997acaab6cd6`, all three selected shards in the
[allow-list](data/unsloth-flash-next-stage2-files.json); IQ3 totals81,961,823,936
file bytes. [STORAGE](STORAGE.md) specifies space/reserve and exact identities.
No download occurs here. Official FP8 remains the four-card authority; these
quants are quality-changing alternatives, never the lossless FP8 headline.

“Two cards” here is a topology on a host with an admitted memory budget, not
proof of viability on the15 GiB two-card machine. Even the51.2 GB PLE host
table alone exceeds that host. Its path needs bounded file-backed PLE/storage,
measured I/O and driver-shadow/host staging admission before a viable claim.
No configuration is deployment-qualified today; IQ3 is the strongest **planning
candidate**, conditional on mixed-grid headers, host fit and owner quality gates.

## Packet ladder and exit gates

CPU packets come first; no native command is scheduled by this document.
Each native packet needs a preregistered complete runner, build/model identity,
all measured/failed arms retained, bounded work and graceful teardown. Start
from newest available upstream research/toolchain at that future window, pin
immutable identities, inventory the accepted overlay and never rewrite A367.
Other runtimes supply credited arithmetic evidence, never our code base.

| Order | Deliverable | Exit gate |
| --- | --- | --- |
| 1 | CPU identity/tensors/oracle/placement | Passed metadata-only; all12 full arrays and tensor totals reproduce. Payload authentication remains open. |
| 1b | [CPU Flash math](stage2/packet1b/README.md): BF16 inter-row GDN, QSA pooling/indexer, top10 weights/order, shared expert, four-stream HC, layers.1 PLE lookup, separate MTP merge/block; packet1b-style fixtures | Deterministic synthetic real-width tests, known-value/causality/state checks, source/cast ledger and explicit UNVERIFIED table. No device parity claim. |
| 2 | CPU admission/loader preparation: official tensor map, complete production M1/M2/prefill shape list, tokenizer parity contract; selected GGUF header census only after storage/acquisition decision | Reject unknown/missing grids/names/scales; authenticated payloads before any native use; count per-rank dense/experts/PLE/head/MTP and all simultaneous host/device peaks. Quant's own tokenizer/model authority frozen. |
| 3 | Native resource/transport owner, only after owner window | One queue/card, explicit event and allocation lifetimes; changed-input copy tests, directed H2D/UVA/peer rates at actual expert sizes, no faults, graceful ordered release and clean postflight. No model server. |
| 4 | Complete native operator census and comparator fixture extraction | Prove instrumentation neutrality against all12 oracle arrays before extraction; bind image/overlay/compiler/library/kernel/dispatch/scales and raw tensors. Every production shape at all served M and EP imbalance/host-hit cases; repeat/fresh-process exactness, reject poison/padded-row mutation. Fill U1–U7; census before bisection; speed recorded, not identity gate. |
| 5 | Own GDN and QSA decoder layers, MoE/shared/HC/PLE | Exact layer outputs, router IDs/weights/order, conv/recurrent/QSA/KV/PLE states against certified fixtures, full BF16 precision; request reset, EOS/history and rank-order tests. No hidden CPU callbacks inside claimed replay. |
| 6 | Own prefill + target-only full text decode TP4/EP4 | All12 full frozen outputs exact from cold prompt inputs, matching tokenizer/template, capacity and quality battery; two fresh-process repeats. Prefill diagnostic timings recorded separately; saved prefill state cannot stand in for this gate. |
| 7 | Native MTP1 and transaction/sampler | All target-verified accepted tokens; acceptance0/partial/all, EOS, first-token phantom, cancellation, rejected-row rollback across GDN/conv/QSA/KV/PLE/HC/MTP. Full target head remains authority; same outputs as target-only and oracle. |
| 8 | Whole-step capture and honest miss scheduling | Eager/replay/fresh repeats exact; mutate every input, poison tails, no inert capture, stable ownership and bounded physical peaks. Explicitly label segmented replay if host cache misses require host decisions; no claim of one replay with callbacks. |
| 9 | Four-card unprofiled cold qualification | Two fresh processes and matched controls, complete once-per-attempt varied suite, cache0, natural512, no reuse; all12 arrays exact plus quality/determinism. Class-balanced99-interval rate **≥46.854250 tok/s**, clean exit after every run. Record accepted counts, TTFT, prefill, p10/mean/wall/full-natural rate and all hashes; no lucky-run selection. |
| 10 | Separate two-card quant qualification and review packet | Owner-approved grid and quality authority/tolerances first; full header/payload/fit validation, exactness within that quant's authority, quality deltas versus FP8, fresh-process determinism and complete cold-suite measurement. Owner sets its speed target;42.07/85.59 are not measured gates. Every expert callable; full16-bit KV; no silent lossy adoption. Reviewable source/build/receipts before any separate publication decision. |

Owner rules remain binding at the future window: no power/host-memory changes,
no reboot without explicit permission, no restart loops, stop and preserve
fault evidence; recovery only under that window's host rules. No native action
or health probe is authorized by this CPU-only job. Current native blockers are
not reasons to manufacture a speed/quality pass.

## Owner decisions

1. Choose IQ3_XXS first or the Q3_K/IQ4_XS alternative, set quant quality
   tolerances (exact-token divergence, semantic/arithmetic/code cases and
   acceptable regressions), designate its independent oracle and two-card
   speed/context goal. The inherited FP8 known miss remains visible.
2. Approve storage/acquisition destination and reserve, any external mount or
   separately justified cleanup, and the host for the two-card topology.
   The15 GiB host needs a separately admitted file-backed PLE/host plan.
3. Resolve the halt and grant an exclusive native window for packets3+,
   including safe transport/census/teardown checks; choose restart/reboot only
   if required by the owner's recovery decision. No video-lane interference.
4. Review the final lossless/quant evidence and any later publication.
   Planning arithmetic and this CPU packet cannot authorize promotion.
