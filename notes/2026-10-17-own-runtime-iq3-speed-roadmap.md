# IQ3 Flash-Next speed roadmap: one and two B70s

2026-10-17. CPU-only evidence review and design; no runtime change, build,
model payload read, device run, service action or new benchmark. Repository
review started at `eab78e6454bba203ef25af1e98fecad80d5281fd`.

**Prioritize specialized GPU kernels on both target halves, then genuinely
multi-token verification.** Graph replay is a useful scheduling mechanism but
already measured neutral. One card needs a separate hybrid design: resident
nonexpert weights and MTP, a bounded expert cache, and exact CPU computation of
misses. Its capacity is plausible; its CPU arithmetic speed is unproven.

The record remains **39.422009 tok/s**, SPEED6 `34c62b433`, LocalMaxxing
`cmv9wjmtj013gle01v8k1yg4v`: Unsloth UD-IQ3_XXS **quantized compressed version**,
23/25 target layers, draft on rank 1, 4K allocated capacity. This is a
128-output-token, owner-approved scope exception; the standard 512-cap final
gate is false. Twelve answers match the arithmetic-v2 oracles; repeats were
39.3856 and 39.3778. It is not a full-4K occupied-context measurement.
[Ledger](2026-10-14-packet45-device-qualification-rounds.md).

## Evidence boundary and credit

Credit **Niko1221 / Strata** for the publicly described combination of
GPU-cached hot experts, pinned host experts with parallel CPU miss computation,
host/SSD PLE, GPU nonexpert/state placement and MTP. Sources supplied by the
owner: [Strata public description](https://vramcalculator.com/strata-qwen3-8-flash-next)
and the ExplainX blog description in the brief; the latter's exact article
URL/revision is unspecified. No Strata source was cloned, read, copied or ported
in this study. Our arithmetic, kernels, cache/controller and validation design
remain independently authored, under the [runtime objective](../docs/own-xpu-runtime-objective.md)
and [idea policy](../experiments/own-xpu-runtime/IDEAS.md).

The supplied 52–62 tok/s RTX 5070 claim (51.6 IQ3_S at 4K), 60–66 RTX 3090
IQ3_XXS claim, 120–150 RTX 5090 community reports and 1.6–1.8× MTP benefit
remain **community-reported**, not matched B70 comparisons. Exact workload,
quality, arithmetic and timing identities are incomplete. No validated boost
is assigned. This is a bounded informational review using the repository's
[contribution skill](../.agents/skills/review-model-contribution/SKILL.md), not
integration of contributed code or promotion of an outside result.

## 1. Where the two-card time goes

Here `S = experiments/own-xpu-runtime/stage2/`, `P = S/packet45-merged3/`.
Primary local receipts are
`P/build/speed6-c4096-dr1-s23-cards01-gpu/WS128/`; timing rows are under
`run/repeat-1/*/rank*/timings.jsonl`, plans/census under `run/ranks/rank*/`.
These ignored local receipts are not all GitHub artifacts. The tracked
[cycle analysis](2026-10-15-p45-after-speed6-levers.md), its
[read-only reproducer](p45_after_speed6_analyze.py),
[roofline study](2026-10-15-p45-roofline-and-structural-levers.md) and
[reproducer](p45_roofline_structural_analyze.py) retain their identities and
calculations. Later negative results supersede the earlier recommendations.

### Submission and launch count

**Production merged3 uses prepared per-kernel SYCL submission, not command-graph
replay.** `P/rank.hpp:136–162` invokes prepared callbacks and counts actual
compute submissions; `P/main.cpp` owns preparation/issue. Prepared command
records match the runtime counts:

| Site | Kernels per layer or boundary |
| --- | ---: |
| Ordinary GDN | 35 |
| PLE GDN, layer 1 | 48 |
| IQ3 gate/up exception, layer 2 | 37 |
| QSA | 41 |
| Rank 0 boundaries | 3 |
| Rank 1 boundaries and final prediction | 10 |
| **Rank 0: 18 GDN, 5 QSA** | **853 per target position** |
| **Rank 1: 18 GDN, 7 QSA** | **927 decode; 919 prompt** |

Thus a target position is **1,780 compute kernel launches**, excluding draft,
lookup/transfer commands and speculation snapshots. A speculative rank-0
position adds 31 capture submissions; a miss adds 30 restore submissions and
another 853-kernel corrected half. These are not launches per emitted token:
the pipeline speculates and sometimes redoes work. Headless prompt positions
omit eight rank-1 kernels. Source counts are in the prepared parity-0 JSONL,
`launch-plan.json` and `rank.hpp`; they are not the older packet22 count.

### Recorded wall-time budget

SPEED6 steady pooled medians, ms; independent medians do not add exactly.
"Wait" includes waiting for GPU completion, not a separate additive GPU stall.

| Work | Rank | Prepare | Enqueue, excluding waits | Wait | Forward | Complete command | Host waits |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Speculative target half | 0 | .0515 | 3.4545 | 14.8020 | 18.2983 | 19.2297 | 8 |
| Corrected target half | 0 | .0501 | 3.5195 | 13.7983 | 17.3567 | 17.7073 | 7 |
| Target half | 1 | approximately 0 | 3.8901 | 14.5110 | 18.6001 | 19.4100 | 3 |

GPU work proceeds during enqueue. Do not add an isolated GPU sum to these
columns or assume the 3.5–3.9 ms enqueue can be removed from elapsed time.
Reported rank busy per emitted interval (22.75/21.71 ms) includes repeated
HALFs and rank-1 drafting; it is not a per-position kernel duration.

| Other work | Evidence / accounting |
| --- | --- |
| Draft, rank 1 | About 2.81 ms complete command on hits; about 2.79 on misses, already overlapping rollback/redo. The duplicate profiling pass is already removed. |
| Snapshot, rank 0 | Capture 48,332,354 B in 31 submissions; matched speculative-minus-redo command difference 1.526 ms is an enclosing proxy, **not isolated copy time**. |
| Miss restore, rank 0 | 18,730,562 B in 30 submissions; ROLLBACK envelope median 1.607 ms includes drains, status reads, host/bank restoration and transport. |
| Cross-card handoff | 20,480 B forward via shared host slots, rank-1 draft uses its local hidden state (the alternate draft-rank-0 placement needs a reverse stream). Transfer events are not separately timed. HALF sent-to-received medians .0067/.0098 ms hit/miss describe mailbox latency, not complete PCIe transfer. |
| Synchronization/control | Observation-to-draft-send about .0143 ms; ACCEPT execution about .0003/.0002 ms rank 0/1. Readback, retirement and drains are already in the enclosing command/wait times. |
| Sampler/head | Target rank-1 head K2 proxy 1.418 ms; draft rereads the shared head. Argmax belongs in the eight prediction kernels; begin/commit are two further boundary kernels; no independently timed production sampler subtotal is retained. |

Hit/miss medians of request means are **22.204/38.717 ms**. The useful model is
`hit = D + max(S,B)` and `miss = max(D,R+A) + max(S,B)`, where S is speculative
rank 0, A corrected rank 0, B rank 1, D draft, R rollback. Rank 0 and rank 1
halves overlap; rank-1 draft and target compute do not. The millisecond
`rank0_to_rank1_handover_ms` field includes draft/redo dependencies and cannot
be called PCIe latency.

### GPU time by class: what is actually available

**A complete current per-rank GPU-event budget cannot be recovered.** SPEED6
WS128 `sites.jsonl` is empty and family times are null; retained KD owner
`timings.jsonl.gz`/`sites.jsonl.gz` are also empty. Use the following
representative SPEED6/SPEED7 K2 isolation proxies, weighted by SPEED6 plan occurrences,
not an invented production profile. [Class evidence](2026-10-15-p45-lever2-design.md) and
[other class proxies](2026-10-15-p45-after-speed6-levers.md).

| Class | Rank 0 ms/position | Rank 1 ms/position | Scope |
| --- | ---: | ---: | --- |
| Routed gate/up and down/status | 4.009 | 4.346 | Actual selected P39/P28 composition |
| Route/gather | .944 | 1.026 | 23/25 × 41.042 µs |
| Shared gate/up/router tuple | .401 | .438 | Current small.rows4 selection |
| Shared down | .225 | .245 | 23/25 × 9.791 µs |
| GDN QKV + Z | about 1.839 | about 1.839 | All-Q6 approximation; first-layer Q8 differs |
| Attention output/combine | 1.337 | 1.453 | 23/25 × 58.125 µs proxy |
| HC low/activation, gate/injection | about 1.943 | about 2.112 | Proportional occurrence estimate; excludes HC norm/mix |
| GDN recurrence | .671 | .671 | 18 × 37.292 µs |
| QSA score/softmax/value | .568–.935 | .795–1.309 | Two measured K2 lengths, 88/152; no interpolated context point |
| Target logits | 0 | 1.418 | Expanded Q6 head |
| Remaining norm, mix, activation, checks, sampler | unavailable | unavailable | No complete current shape-specific profile |

These rows mix representative K2 selections; they are not an additive residual
accounting against the wall table. The historical evidence explains why:

| Packet | Recorded finding and limit |
| --- | --- |
| [20](../experiments/own-xpu-runtime/stage2/packet20-launch/receipts-card3-20261011-attempt-a/README.md) | Tiny kernels cost about 3.4–5 µs/launch; waiting after every kernel about 9.5 µs. Replay did not run in that attempt. |
| [22](../experiments/own-xpu-runtime/stage2/packet22-replay/README.md) | CPU/native-build design: 876 kernels, six resident replay segments; not a production speed measurement. |
| [34](../experiments/own-xpu-runtime/stage2/packet34-replay-bench/receipts-card3-20261012-r1/README.md) | Older 24-layer/1,142-kernel synthetic-weight half: direct wall 19.823 ms, summed GPU 19.520; whole graph 19.858, layer graphs 20.109. Changed-input states 420/420 exact. |
| [44](../experiments/own-xpu-runtime/stage2/packet44-context/README.md) | Prior pipeline/context baseline, about 37.856 record. Ledger comparison reports rank command-busy 23.49/22.59, hit/miss 23.19/39.33 ms. Not current per-class GPU timing. |
| [45](2026-10-14-packet45-device-qualification-rounds.md) | Actual SPEED6 budget above; snapshots, split, arithmetic and dispatch differ from the older probes. |

Packet34 `iterations.jsonl.gz` zipped with `launch-plan.jsonl` gives historical
class medians: generic dense/shared/HC GEMV 8.089 ms, routed GEMV 3.107,
paired gate/up 2.022, routing 1.632, QSA 1.488, GDN .648; other classes summed within each iteration then medianed: 2.517 ms. Ordinary GDN layers were .757–.770 ms GPU-busy,
QSA .970–.977 ms. These exclude final head, draft, copies and snapshots and
must not be relabeled as a SPEED6 rank profile.

### Weight floor at 550 GB/s

Use actual mixed expert formats and expanded dense payload, not "3 bits" times
parameter count. [Metadata-derived byte census](2026-10-15-p45-roofline-and-structural-levers.md):

| Per target position | Rank 0 (23 layers) | Rank 1 (25 layers + head) |
| --- | ---: | ---: |
| Unique useful weight bytes | 2.740419 GB | 3.730572 GB |
| Weight-only floor at assumed 550 GB/s | 4.983 ms | 6.783 ms |
| Floor averaged over owned layers | .217 ms | .271 ms, including amortized head |
| Recorded forward / layer, **wall not GPU-busy** | .755 ms redo; .796 speculative | .744 ms including head |

Excluding rank-1 head, its per-layer weight floor is .214 ms; the head alone
has a 1.445 ms floor. Selected expert reads total .949760 GB/position, about
19.712 MB/ordinary layer (23.296 MB for layer 2); expert-only floors are
.831/.896 ms per rank versus K2 proxies 4.009/4.346 ms. GDN state, KV,
intermediates, decoding instructions and dispatch are additional. A 550 GB/s
assumption is conservative beside packet7's measured 590–600 GB/s streaming
probe, but not guaranteed concurrent pipeline bandwidth. The older .8 ms/layer
GPU observation and today's .2 ms/layer weight floor establish an opportunity,
not a measured removable .6 ms on every current layer.

## 2. Ranked two-card levers

Ranges below are **conditional planning arithmetic, not measurements or
confidence intervals**. Every new kernel can regress. The first experiment
column describes later admitted work; this study ran none of it.

| Rank / lever | Mechanism and expected value | Expected tok/s / conditional range | Effort | Exactness risk | First experiment |
| --- | --- | --- | --- | --- | --- |
| 1. Specialized per-layer subgraphs | Remove short device dispatches and redundant loads with compile-time shape/format kernels; retain parallel reduction structure. Biggest credible remaining engineering scope. | No measured gain; **43.6–48.7** if both halves lose 2–4 ms; 39.4 or regression remains possible | Multi-day | High | One ordinary GDN and one QSA composition: unchanged FP32 intermediates/state, exact fresh-owner repeats; demand roughly 80–160 µs/layer saving before full integration |
| 2. Temporal M=2, then M=3 verification | Reuse dense weight reads/dequant across token rows with independent exact accumulators; preserve causal state and prefix rollback | Current M3 schedule **23.1–29.9**, unattractive; new T3=48 ms gives **43.0–48.9** depending on draft overlap | Large, multi-day | Very high | Dense QKV/head M2/M3 against serial rows, then full T3 and accepted-prefix state; only reopen full controller below 52.90 ms, preferably 48 |
| 3. Structural expert implementation | Change instruction/data layout beyond the already-tested bank/vector tweaks; same decoded values and tree | Existing candidates about **39.4–39.6**; even expert memory-floor ideal only **46.74** | Multi-day for a new approach | High | Instruction/live-range hypothesis with a byte-exact fused-body comparison; reject tiny or spilled variants promptly |
| 4. Miss-cycle reduction | Avoid exposed restore/control work and shorten the corrected rank-0 half; shared kernel improvements count in rank 1 too | Entire rollback removed gives only about **40.0**; eliminating the whole miss penalty is an impossible-work-free upper scenario around **45–46** | Medium | High | Separate restore/redo timers and full-state hit/miss/terminal checks; do not repeat SPEED7 padding-only work |
| 5. Copy-engine overlap | Overlap only genuinely independent copies with compute; preserve producer completion and buffer lifetimes | No supported positive range; likely near **39.4**, unless new trace exposes a larger copy stall | Medium | Medium/high | Timestamp actual transfer/drain phases with changed payloads, without double-counting existing overlap |
| 6. Host affinity/preparation | Maintain quiet issuing cores and prepared callbacks; protect against host interference | Near **39.4** on a quiet host; recovery of contention loss is unquantified | Low | Low | Read existing affinity/load/page-fault receipts; later matched controlled-load check, no host/power changes |
| 7. Whole-step graph replay | Batch host submission; useful for schedule ownership, not fewer device kernels | Neutral in packet34; no justified 60+ forecast | Medium | High lifetime risk | Port only if a new design needs it; changed-input replay plus real pipeline timing, not repeated fixed-input equality |

**Host profile:** SPEED6 rank `host-environment.json` receipts pin both
issuers to CPUs **0–3,16–19**, with recorded one-minute loads .488/.449.
Keep helper work on 4–15,20–31 as in this study; the runtime profile uses
`OMP_NUM_THREADS=2`. Prepared callbacks already remove repeated string/map
lookup and allocation. Lookup read-ahead is `MADV_WILLNEED` plus page touches,
**not mlock**. Preserve that distinction when investigating major faults;
OS affinity is not permission to change governors, power, swap or cache settings.

**Why specialization, not a giant fused interpreter:** packet24's
[generic fusion](../experiments/own-xpu-runtime/stage2/packet24-kernels/evidence/20261011-k2-c0-generic-kernels-slow/README.md)
was exact but 50–100× slower for major projections (8,804 vs 101 µs QKV;
129,193 vs 2,137 µs logits). Even specialized serial reductions regressed in
[packet30](../experiments/own-xpu-runtime/stage2/packet30-leftovers/receipts-card2-20261012-g3/README.md).
Fuse dependency-compatible tiles/epilogues, preserve BF16 cast sites and each
lane's accumulation/tree, and do not serialize a whole layer into one workgroup.
Avoid full codebook register staging and spilling. Separate correctness from
speed; fewer launches alone does not pass either gate.

**Replay contract:** packet22 required device-resident changing position/token
controls, stable descriptor allocations, owner generation/address/extent keys,
fixed geometry per capacity, and invalidation/re-recording on configuration or
allocation changes. No host pointer, allocation node or host read belongs in
the recorded region. Copies must finish before consuming graphs; recordings
must drain/die before allocations, queues and context. Whole-step speculation
adds bank/rollback/accepted-prefix lifetime rules. A graph cannot capture a
host decision as a constant, reuse stale routes, skip inactive/error checks,
or remove events needed for safe teardown. Packet34's success does not prove
all those merged3 cases; its near-zero speed gain also rules out subtracting
the entire enqueue column as a forecast.

**MTP accounting:** the current one-proposal pipeline already overlaps target
halves. M2 is a two-position verifier, not rows4 output-neuron grouping; k=2
requires M3 plus partial-prefix commit on both ranks. The diagnostic measured
p1=.787, p2 conditional=.714, expected tokens/cycle=2.348, D1+D2=6.668 ms.
Existing exact single-row kernels give estimated T3=76 ms (72–95), not a win.
[Full estimate and receipts](2026-10-15-p45-k2-t3-estimate.md).
For 60/100 tok/s, that same renewal model requires T3 below 32.47/16.82 ms
with serialized draft, or 39.14/23.48 ms even if draft is entirely hidden.
For M2, `E2=1+p1=1.786745` and D≈2.79 ms: existing-kernel
T2≈56.54 ms implies only 30.1–31.6 tok/s. Beating the current pipeline needs
T2<42.53 ms with serialized draft (45.32 fully hidden); reaching 60 needs
T2<26.99/29.78 ms. These are planning equations, not measured M2 timings.
No receipt demonstrates those values. Temporal batching must preserve separate
lane accumulators, ordered GDN updates, each QSA prefix, every head result and
0/1/2-accepted rollback; routing reuse is unmeasured.

**Size of the goal:** 39.422 implies 25.367 ms/effective token. Reaching
60/80/100 needs 8.700/12.867/15.367 ms less, or 34.3/50.7/60.6%.
An illustrative baseline-anchored model is
`rate = 1000 / (25.36654 - (2-.791)*d)`, where both halves save d ms,
hits save d and misses 2d. At d=2/4/6/8 ms it gives
43.6/48.7/55.2/63.7 tok/s; 60 needs about 7.20 ms/half.
This simplified model is not the class-balanced interval replay. The 114–116
memory-only roofline in the prior study is also not an expected speed.
**60 is a substantial architecture milestone; 100+ has no evidence-backed
implementation forecast yet.** Reopening within-layer tensor split also needs
new evidence: the latest [ordered-exchange study](2026-10-15-p45-within-layer-split-step1.md)
projected 25.64 ms, above its 23.5–24 ms gate.

## 3. One-card decision and next work

The [one-card design](../experiments/own-xpu-runtime/ONE-CARD-DESIGN.md) gives
actual mixed-format sizes, MTP-aware capacity, routing evidence limits, CPU
throughput requirements, PCIe traffic and the exact arithmetic contract.
It makes the Strata-inspired CPU-miss path the performance research target;
packed GPU streaming is a correctness fallback/control, not a promised fast
path. No matched IQ3 hit rate or sustained exact CPU expert rate exists yet.

Next bounded work is (1) a static specialized GDN/QSA dependency/tile design,
(2) the exact CPU expert arithmetic specification and cache budget, and
(3) a diagnostic schema for route IDs and GPU/host phase timings. Later, under
separate device ownership, qualify these in that order of prerequisites.
Require unchanged IQ3 oracle outputs, complete state, fresh-process repeats,
full 16-bit KV and the registered varied cold suite; use the standard 512 cap
for any new unrestricted headline. Preserve the historical 128-cap record.
There is no new GPU admission or pending permission request in this study.
