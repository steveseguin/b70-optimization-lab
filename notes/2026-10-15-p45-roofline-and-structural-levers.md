# Packet45 after SPEED7: roofline and structural choices

2026-10-15. Read-only strategy study. **39.422009 remains the measured record.**
The current one-token pipeline has a **114–116 tok/s optimistic memory-only
roofline**, not a credible near-term speed forecast. The receipts do not contain
the instruction-throughput or cache-counter measurements needed to turn that
into a complete hardware ceiling. Large expanded dense projections already
approach the measured memory roofline; expert decoding and many small kernels
do not. Faster copies and another existing expert candidate cannot close this gap.

**Recommend a bounded, communication-coalesced, within-layer parallelism
experiment**, starting with one GDN and one QSA layer using the current kernels.
Its purpose is to establish whether a target-only two-card step can get below
23.5–24 ms, before implementing another full runtime. A conditional working
case is **41.1 tok/s**, with **36.7–44.6** in the sensitivity cases below.
The potential gain is about **4–13%**, but a regression is entirely possible.
This is a larger project than SPEED8, not a promised two-hour repair.

Deeper MTP is worth a subsequent diagnostic, but today's 79% one-step acceptance
does not establish second-proposal acceptance. A two-position verifier also
needs much more than a two-row GEMV to beat the existing overlapped pipeline.
Neither deserves a 50–60 tok/s promise from these receipts.

No packet45 or packet44 file, binary, receipt or cache was written. No model
payload was read, no build or device program ran, and no new speed measurement
is claimed. The only additions are this note and its
[read-only reproducer](p45_roofline_structural_analyze.py). It rejects file writes
and child execution, hashes its inputs, checks all 1,188 headline intervals,
and confirms identical guess sequences across the two other SPEED6 suites.

## Evidence and definitions

`P` below means `experiments/own-xpu-runtime/stage2/packet45-merged3`.

- Primary: `P/build/speed6-c4096-dr1-s23-cards01-gpu/WS128`, plus its
  `WS128-r2` and `speed6-c4096-dr1-s23-cards23-gpu/WS128`.
- Plans/census: headline `run/ranks/rank{0,1}/{plan.json,launch-plan.json,census.json}`;
  tensor dimensions/types: `P/build/input/plan.tsv`. These are metadata reads.
- Kernel timing: `P/build/speed7-c4096-dr1-s23-cards01-gpu/K2/run0/`
  `events.jsonl`, `summary.json`, `dispatch-measured.json`; SPEED6 controls and
  both card pairs are compared in the [lever-2 design][lever2].
- The [SPEED6 cycle analysis][after6] and [hit-gap study][hitgap] define how
  command timestamps join to emitted-token intervals. `sites.jsonl` does not
  supply a usable per-kernel WS128 profile. K2 class times multiplied by plan
  occurrences are **isolation proxies**, not a pipeline profile.
- The [same-boot streaming/copy measurement][ceiling] is packet7, card3,
  boot `13858eef`; the [peer measurement][peer] is cards2–3 on that boot.
  Neither proves identical behavior on every card or under simultaneous load.

The headline is a median of class medians over the **99 intervals between
events 1 and 100**. Full-request hit/miss figures are medians of request means.
They cannot be mixed into an exact reconstruction of the headline. The helper
replays the actual 99 hit/miss outcomes separately for each request when it
reports a class-balanced roofline. Structural renewal equations below are
explicitly **pooled planning rates**, not submitted class-balanced rates.

SPEED7's 39.368 is parity. Its instrumented cycles did not improve on either
pair. The [calibration][lever2] therefore assigns **zero demonstrated cycle
saving** to removed padded snapshot slots. Those masked work-items did not
copy extra bytes; deleting them did not delete memory traffic. Even synchronous
restore was unchanged, so overlap alone does not explain the failed forecast.
The calibrated existing-candidate expert proposal is about 0.08 ms/hit, with
zero plausible. Neither earlier optimistic forecast is carried forward here.

## What each position reads and computes

The split is layers0–22 / layers23–47. Each side has 18 GDN layers; QSA counts
are five/seven. Each valid layer chooses ten **distinct** experts from 512.
Rank 0 has 22 IQ2 layers and the exceptional IQ3 layer 2; rank 1 has 25 IQ2 layers.

There is an evidence limit: retained per-position state archives contain
**route-buffer hashes, not expert IDs**. They cannot establish route popularity,
cross-position expert overlap, or an expert-cache hit rate. The distinct-top10
contract is nevertheless enough to compute the selected payload exactly:
`core_v2.hpp:327–354` sorts an ID permutation. It is 19.712 MB per IQ2 layer and
23.296 MB for layer 2, regardless of which ten valid IDs occurred. Claims about
observed routing reuse would require a new diagnostic; no uniform-routing
assumption is presented as a measurement here.

The table counts unique weight bytes used by one execution of each matrix,
not the whole resident bank, and not measured external-memory transactions.
Expanded Q6/Q8 uses the actual integer codes plus FP32 scales. Unused appended
provenance metadata is excluded. Cache-line overfetch, repeated cache-level
loads and activation traffic are not represented by this weight numerator.
MB and GB are decimal; GF counts multiply/add as two operations.

| Weight class | Rank 0 MB/half | Rank 1 MB/half | Rank 0 dot GF | Rank 1 dot GF |
|---|---:|---:|---:|---:|
| GDN projections and small weights | 1,313.021 | 1,318.264 | 2.0865 | 2.0865 |
| Hyperconnections | 346.685 | 384.205 | .6067 | .6726 |
| Norm weights | 1.909 | 2.120 | — | — |
| PLE projection | 37.151 | 0 | .0656 | 0 |
| QSA projections | 311.296 | 435.814 | .4981 | .6973 |
| QSA indexer | 16.384 | 22.938 | .0164 | .0229 |
| Selected expert gate/up/down | **456.960** | **492.800** | **2.2610** | **2.4576** |
| Routers | 120.822 | 131.328 | .0603 | .0655 |
| Shared experts | 136.192 | 148.480 | .2261 | .2458 |
| Final logits head | 0 | **794.624** | 0 | **1.2714** |
| **Target total** | **2,740.419** | **3,730.572** | **5.8207** | **7.5196** |

The draft on rank 1 adds **1,037.289472 MB** of unique weight reads per proposal,
including another 794.624 MB read of the same aliased head. Its selected INT8
experts account for 61.440 MB, BF16 QSA/indexer 102.892 MB, HC 39.485 MB,
shared/router 12.457 MB, merge projections 26.214 MB, and norms .177 MB.
The dot census is about **1.5901 GF**. The hidden merge matrix is used on four
input rows; the byte lower bound counts its 13.1072 MB once, while independently
issued rows could fetch another 39.3216 MB before cache reuse.
`mtp.hpp:84–112,138–163` defines these formats and aliases. This is the already
qualified draft representation, not a proposal to requantize the target.

The head's 839.3216 MB **allocation** is not its fetched code/scale payload.
Q6 K2560 has a 3,380-byte row stride: 2,560 codes +640 scale bytes +180 trailing
metadata bytes. The fast path reads the first 3,200. See
[`expanded.hpp:16–19,66–81`][expanded] and `P/p33_candidates.hpp:83–91`.
This corrects the previous note's 592 GB/s head estimate to about560 GB/s.
P39's fixture also reports the **whole 512-expert bank** as its payload;
using that as per-token traffic would overstate routed bytes by 51.2×.

State, history and KV are additional:

| Traffic per half/proposal | Rank 0 | Rank 1 target | Rank 1 draft |
|---|---:|---:|---:|
| GDN recurrent state reads, MB | 28.312 | 28.312 | 0 |
| GDN state writes, MB | 28.312 | 28.312 | 0 |
| Convolution history reads, MB | 1.106 | 1.106 | 0 |
| Convolution history writes, MB | 1.106 | 1.106 | 0 |
| Unique QSA KV/indexer reads at N122, MB | 1.288 | 1.803 | .258 |
| Same at **actual N4096**, MB | 22.282 | 31.195 | 4.456 |
| Snapshot capture payload, MB | 48.332 read +48.332 written | 0 | 0 |
| Miss/redo restore payload, MB | 18.731 read +18.731 written | 0 | 0 |

For `N=position+1`, selected QSA tokens are
`M=4*min(floor(N/4),512)+(N%4)`; unique K/V plus pooled-indexer reads are
`2048*M+256*floor(N/4)` bytes per QSA layer. Query heads share KV heads, so
actual cache-level reads can exceed this unique-byte floor. Current-row writes,
norm/elementwise operands, small controls, score/probability workspace and
partial GEMV outputs add traffic. They are not zero; these receipts do not
measure their external-memory amplification. State/attention formulas come
from [`core_v2.hpp:392–465`][core] and `P/p42_gdn.inc:11–21`.

**4K is allocated capacity, not the workload's live length.** Actual generated
positions in this headline have N60–217, median 135; the primary interval target
positions have N61–189, median 122. Charging a full 4096-row KV read to every
headline step would be false. Host lookup reads only a 2,100-byte embedding row
and 1,440 bytes of PLE rows, then uploads 10,240 BF16 bytes, not the 28.8 GB PLE
table (`P/main.cpp:928–973`).

The dot counts are not a complete instruction census. GDN state arithmetic adds
about .0991 GF per half before normalizations/transcendentals. QSA adds
`4*24*256*M` dot operations per layer plus index scoring; atN122 that is about
.0030 GF per layer. Integer unpacking, codebook lookup, scale conversion,
deterministic nonlinear functions, reductions, loads and GPU dispatch all cost
time absent from these GF figures. Quoting peak matrix TOPS against them would
be misleading: this is the frozen scalar/subgroup arithmetic, not a tensor-core
GEMM throughput measurement. A matching exact-arithmetic compute ceiling remains
unmeasured ([stage2 plan:58–61][stage2]).

## Measured rooflines and kernel efficiency

Packet7's 20 event intervals per case give:

| Payload | Streaming reads, GB/s, two patterns | D2D copy payload GB/s | D2D read+write GB/s |
|---|---:|---:|---:|
| 64 MiB | 588.62 /592.68 | 271.03 /272.58 | 542.06 /545.16 |
| 128 MiB | 598.60 /598.18 | 271.89 /271.89 | 543.78 /543.78 |
| 256 MiB | 601.12 /601.47 | 264.09 /263.99 | 528.18 /527.99 |

These are device-event access-pattern measurements, excluding allocation,
upload and readback. Streaming uses 16-byte reads plus a deterministic integer
sum. Copy counts its payload once; total read/write traffic is twice that.
Use **590–600 GB/s** for an optimistic read floor and about **270 GB/s payload**
for copy. They are not guaranteed simultaneous CCS/BCS rates.

Current SPEED7 pairA K2, rotated mode, with useful-byte numerators:

| Executed class | Useful MB | K2 µs | Effective GB/s | Fraction of 600 GB/s | Interpretation |
|---|---:|---:|---:|---:|---|
| IQ2 paired gate/up +checks | 10.496 | 80.416 | 130.52 | 21.8% | Far from streaming; decode/issue/occupancy costs |
| IQ3 paired gate/up +two checks | 14.080 | 90.938 | 154.83 | 25.8% | Far from streaming; one layer only |
| IQ4 down +status | 9.216 | 93.437 | 98.63 | 16.4% | Largest repeated expert gap |
| Expanded Q6 QKV | 32.768 | 62.396 | 525.16 | 87.5% | Near useful-byte bandwidth roofline |
| Expanded Q8 QKV | 29.491 | 57.292 | 514.75 | 85.8% | Near bandwidth roofline |
| Expanded Q6 logits | 794.624 | 1,418.073 | 560.35 | 93.4% | Little pure-bandwidth headroom |
| GDN recurrence, state read+write only | 3.146 | 37.292 | 84.35 | 14.1% | Reduction/normalization/dispatch; not a simple copy |

The expert dot-operation rates are roughly .815/.721/.351 TFLOP/s for the three
expert rows; those are observed rates, not their attainable compute ceilings.
No stall counters identify how much is unpacking versus occupancy or lookup
latency. Earlier exact expert rewrites regressed from .298 ms to 1.45–2.60 ms;
one spilled6 KiB ([packet11 result][expertnegative]). A large memory-roofline
gap does not prove an easy kernel fix.

Weighted by this plan, the three expert classes cost **4.009/4.346 ms per
rank 0/rank1 half** in the K2 proxy. Their600 GB/s floors are .762/.821 ms.
If experts alone magically reached that floor, replaying their full savings
through the existing cycle model gives about **46.74 class-balanced tok/s**,
saving 3.31 ms/hit and 6.64 ms/miss. This is an optimistic limit on that lever,
not the SPEED8 forecast of about 39.57. It omits the very instruction work that
currently prevents the floor.

Other classes are mixed. Small HC projections and routing are dominated by
short-kernel/reduction work rather than sustained byte movement. QSA's K2
attention at lengths 88/152 costs 113.542–186.979 µs, much more than its unique-KV
byte floor; its ordered score/softmax/value reductions and launch count matter.
Shared small-FFN runs the already-repaired `p30.small.rows4`; generic dispatch
names must not override the P39 kernel actually executed. Detailed selections
and counts are retained in the [lever-2 table][lever2]. There is no valid
single “memory utilization” percentage for all these different kernels.

## Current pipeline and its ceiling

The supplied 22.75/21.71 ms **rank busy per emitted interval** includes repeated
work and, on rank 1, drafting. It is not the duration of one target half.
Retained steady command medians are rank 0 speculative 19.230 ms, rank 0 redo
17.707 ms, rank 1 target 19.410 ms. Full-request hit phase medians are draft 2.790,
rank 0 speculative 19.225, rank 1 target 19.184 ms. The two halves overlap; medians
cannot simply be added. Rank 0 is later on 41.1% of steady hits.

Let A=rank 0 corrected half, S=rank 0 speculative half including capture,
B=rank 1 target half, D=draft, R=rollback. Ignoring small dispatch residuals:

```
hit  = D + max(S, B)
miss = max(D, R + A) + max(S, B)
```

This matches `native_controller.hpp:72–97`: draft precedes the two parallel
halves on hits, and overlaps rank 0 rollback/redo on misses. Rank 1 draft and
rank 1 target **never compute concurrently** in this schedule. This study
respects the required one-CCS, no same-card compute-overlap model: cross-card
compute and correctly ordered BCS copies are the available overlap. The measured 22.204/38.717 ms cycles include the small
controller/observation tails omitted in the schematic formula.

At 600 GB/s, using the weight census, GDN state read+write, actual-length KV,
and 270 GB/s copy payload, the illustrative N122 floors are:

| Component | Floor ms | Measured enclosing command, ms |
|---|---:|---:|
| Rank 0 target A | 4.668 | 17.707 redo |
| Rank 1 target B | 6.319 | 19.410 |
| Draft D | 1.729 | about 2.79 |
| Capture | .179 | no isolated wall timer; overlaps/drains inside S |
| Redo restore | .069 | about 1.62 ROLLBACK, including more than data movement |
| Ideal hit | **8.048** | 22.204 |
| Ideal miss | **11.056** | 38.717 |

Applying these formulas to each headline interval and preserving the class
aggregation gives **113.725 tok/s at590 GB/s;115.650 at 600 GB/s**. Thus39.422
is about **34–35% of this memory-only model**, a 74–76 tok/s gap, or 2.88–2.93×.
It is not proof that an attainable implementation can triple throughput.

This answers “every kernel at roofline” only as an explicitly optimistic
**one-fetch, memory-only roofline**. A full ceiling must instead sum each
dependent kernel's `max(bytes/bandwidth, instructions/achievable_issue_rate)`
plus mandatory dispatch and synchronization, then apply the parallel maximum.
The receipts lack the second term and external-memory counters. Small cached
weights also need not reach DRAM on every invocation. Therefore an exact
physical ceiling, or a defensible 50/60/80 tok/s attainable ceiling, cannot be
identified from existing evidence. The helper does not relabel missing
activation traffic or arithmetic as measured zero; its number is a declared
optimistic model. Whole-bank storage divided by advertised bandwidth would be
less useful and substantially wrong for this MoE pipeline.

## Structural options and fair forecasts

These are alternative projects, not additive savings. The measured record and
unchanged arithmetic/oracle remain the comparison throughout.

### Deeper official MTP, k=2

Across the three identical SPEED6 guess sequences there are 1,199 hits in 1,524
guesses: pooled `p=.786745`, versus the reported median per-prompt acceptance
`.791339`. Within requests, transitions are HH 945 / HM 243 / MH 244 / MM 80, giving
`P(next hit | hit)=.795455`. The primary 99-interval subset has 934 hits/254 misses,
with conditional probability 733/927=.790723. There are 254 maximal hit runs,
mean 4.72 and maximum 41; 77.2% contain at least two hits. Request boundaries censor
some runs. The helper prints the full histogram.

Those are consecutive **teacher-forced one-step** outcomes, not second-draft
acceptance. `mtp.hpp:195–199` requires the next target position, copies target
hidden streams and embeds the confirmed token. `rank.hpp:237–241` requires
confirmation and no pending rank 1 candidate. Autoregressive reuse must instead
feed the previous draft hidden output and guessed token, checkpoint private
KV/position, then re-anchor correctly. Even after a correct first guess, that
hidden state differs from the confirmed target hidden used by today's next call.

For a complete recurring verification block, let T3 include **all** target
execution, rollback/recovery, prefix-state handling, controller and pipeline
fill/rollover. With two 2.8 ms drafts, actual conditional second acceptance q:

`rate = 1000*(1+p+p*q)/(T3+5.6)`.

This verifies two proposals **and obtains the bonus target output**. A two-row
target pass alone does not earn three outputs. No initial rank 0 half is free
at every block boundary. At the one-step proxy q=.795455, expected outputs are
2.412566. At the record's 25.3665 ms/token:

| T3 ms | Actual q needed to beat record | Planning tok/s at proxy q=.795455 |
|---|---:|---:|
| 45 | >.2644 | 47.68 |
| 50 | >.5149 | 43.39 |
| 55 | >.7655 | 39.81 |
| 60 | >1.0160, impossible | 36.78 |

**Forecast:** no established gain from depth alone. Three serial target
positions would be about 111 ms, already far outside the budget. The positive
43–48 scenarios require a substantially faster verifier and measured q.
Cheapest acceptance experiment later: one bounded diagnostic on the fixed
suite, recording both real self-fed proposals and target verification, with
first-/second-rejection, cancel and end-of-request state checks. No oracle
guesses may enter a speed headline. This is several days of state/controller
work; do it only after a verifier cost experiment justifies it.

### Batch verification of two positions

For the existing one proposal, a complete two-position target block yields
`E[L]=1+p=1.786745`; `rate=1000*(1+p)/(T2+2.8)`.
T2 must be **below42.524 ms**, including every recovery/rollover cost.
T2=35/40/45/50 ms gives 47.27/41.75/37.38/33.84 pooled planning tok/s.

There is a concrete mechanism: load shared dense weights once for two input
rows while keeping each row's original accumulation and cast sequence.
Execute GDN recurrence, convolution history, QSA append/pool/select and causal
attention in the original position order. Gather expert sets independently;
the receipts do not establish shared experts between the two positions.

But two unbatched complete targets cost approximately
`2*(17.7+19.4)=74.2 ms`. The non-expert shared weight payload is 5.521 GB/token;
one read avoided at 600 GB/s accounts for only **9.20 ms per two-position block**.
This simple byte-reuse scenario leaves about65 ms, or**26.3 tok/s** after drafting.
It is not a hard bound on a new fused algorithm, but it exposes over 22 ms of
additional saving that a positive forecast still has to explain. Current large
dense kernels are already near their bandwidth floor. Claiming 35–40 ms from
“two rows” alone is unjustified.

Preserving today's draft conditioning also requires advancing the private MTP
body at intermediate accepted target positions. An illustrative 1.4 ms body
(full draft minus its head) adds `p*1.4=1.10 ms/block`; T2 must include this
catch-up. A generic two-row GEMM or reassociated recurrence would change output
and is excluded. Existing rank 1 speculative execution is refused at
`rank.hpp:111`; `strict_snapshot.hpp:181` protects rank 0 only. Prefix rejection
needs a new exact state proof on **both** ranks. With only 85.224 MiB of current
rank 1 arena space, extra workspace and state images require a complete census,
not an assumption that the second row fits.

Cheapest decisive A/B: a diagnostic complete two-position GDN/QSA sequence with
known input tokens, scalar-per-row versus shared-weight execution, comparing
all state. Include launch and state costs. Known inputs are permissible for
this diagnostic, never for a claimed speculative speed. **Do not implement the
full block controller unless the measured recurring budget clears 42.52 ms
with margin.** Current evidence ranks this below the next project.

### Schedule, draft placement and caching

| Change | Evidence-based forecast | Cheapest useful check |
|---|---|---|
| Observe rank 1 completion and start its next draft while rank 0 is still finishing | Exact replay gives an aggressive ceiling of **.228 ms/hit, .119 ms/miss**, 39.763 class-balanced; half credit 39.592 | Asynchronous local command completion with unchanged ownership; measure whether the late-rank 0 tail overlaps legally |
| BCS capture/restore with per-extent first-writer dependencies | **0 demonstrated gain**; best pure-transfer terms are only .179/.069 ms, though current command envelopes are larger | Time actual copy events and first-write fences, then one matched complete-state A/B; do not credit all snapshot overhead as bandwidth |
| Move draft to rank 0 or a new split | No positive forecast; current split is balanced, and rank 1 drafting already hides behind rank 0 redo on misses | Existing dr0/dr1 evidence is the control; a new placement needs admitted memory and a measured DAG, not just lower rank busy |
| Cache/deduplicate the logits head | Already aliases one allocation; no second resident head to remove. At 560 GB/s, ideal 600 saves only about **.094 ms per head call** | A different head kernel must beat the selected segment kernel in both K2 modes and the pipeline |
| Cache expanded hot experts | Unknown hit rate; route IDs/frequencies are not retained. No forecasted gain | First record an ID histogram; do not allocate an unproven cache in 85.22 MiB headroom |
| Graph replay | Prior actual result **19.82 ms direct vs19.86 ms whole graph**, 420/420 byte-equal; zero speed credit | Closed as a speed lever absent evidence of new host starvation |

The last row is the [packet34 device result][replay], not its older unrun README.
It found 19.52 ms summed GPU time inside 19.82 ms wall: submission already stayed
ahead of the GPU. Its 3–5 µs smallest-kernel costs remained under replay. Thus
the current 3.5–3.9 ms host enqueue loops cannot be subtracted as exposed delay.
The current in-order queue and dependencies serialize draft and target on
rank 1. Under the required no same-card compute-overlap model, moving work
between queues earns no overlap credit.

Whole-bank expert expansion would exceed capacity: one layer's gate/up+down
adds about 2.150 GB. Expanding only selected experts requires conversion and
short-lived storage before reuse; it does not make one-token dequantization
free. Reusing immutable decoded weights can be lossless, but prompt/KV/response
reuse remains excluded. The head is too large for the remaining arena space,
and its existing resident allocation is not evidence of cache residency.

### Within-layer parallelism: the larger but conditional opportunity

Run **target-only** with both cards contributing to the same position, avoiding
the draft head and wrong-guess rank 0 redo. Complete output rows and independent
heads retain their full K reduction; gather their rounded activations in the
original index order. Expert outputs must retain all ten original slot results
and their serial mixture order. A generic all-reduce, two locally accumulated
expert sums, or contiguous half-K dot split is not equivalent. A lower-traffic
split can partition only an existing reduction tree, with a separate proof for
each frozen tree/shape; no replacement oracle can excuse changed target bits.

There is prior evidence, both useful and limiting. [Packet14][tp14] ran 87
positions through a real GDN layer, bit-identical to one-card execution. It also
made **41 exchanges/layer costing 1.53 ms**, larger than its compute saving.
Its full-row design counted 1,926 peer copies and 9.273 MB/token before the head.
The [older TP design][tpdesign] explicitly rejects the fiction of one exchange
per layer. Simply porting that implementation would regress badly.

Current plans contain 881 projection sites, 100 norms, 97 HC mixes, 36 GDN and 12
QSA operations. A gather after every projection cannot win. Packet12 measured
about 18–20 µs per 10–64 KiB peer copy and **52 µs per ordered 10 KiB round trip**;
96 such rounds already cost about 5 ms, before extra gathers. Host bounce was
about 3× slower for the small exchange sequence. These are transport diagnostics,
not permission to reuse an old shared-context owner or assume a new IPC path is
safe. The current process ownership, fault and teardown rules must remain.

A useful Amdahl sensitivity starts from 37.1 ms for the two unchanged target
halves, excluding speculative capture and drafting:

`T_TP = 37.1*(1-f/2) + L`.

f is the fraction that **actually halves**, including small-shape efficiency;
L is total additional communication, synchronization and scaling loss. Replicated
norms/HC, uneven expert ownership, unchanged dispatch costs and gather kernels
cannot quietly join f. No within-card compute overlap is assumed.

| f | L ms | Target-only ms/token | Planning tok/s | Versus39.422 |
|---:|---:|---:|---:|---:|
| .70 | 3 | 27.115 | 36.88 | −6.4% |
| .80 | 5 | 27.260 | 36.68 | −6.9% |
| .80 | 3 | 25.260 | 39.59 | +.4% |
| **.85** | **3** | **24.333** | **41.10** | **+4.2%** |
| .90 | 3 | 23.405 | 42.73 | +8.4% |
| .90 | 2 | 22.405 | 44.63 | +13.2% |

To beat25.3665 ms/token, f must exceed 74.0/79.4/84.8/90.2% for L=2/3/4/5 ms.
The central case would be about 2.13 ms **slower than today's hit** but 14.38 ms
faster than today's miss. Target-only no longer has hit/miss cycles; it wins
only through the complete token rate, not by relabeling those categories.

Capacity is more promising than another layer move: current target weight
allocations sum to **54,447,436,288 B**, after subtracting 3,326,953,472 B of private
draft weights. Balanced target ownership starts near 27.224 GB/card before
replication and mutable storage, leaving several GB under each 30 GiB arena.
That is a projection, not admission. It needs the same explicit per-card arena
and 1.5 GB free-reserve check; shard layout, replicated weights, full-precision
KV, transport buffers and opaque runtime allocations must all be included.

## The single next project and its stopping test

**Project: prove a communication-coalesced, exact within-layer split on current
GDN/QSA blocks.** The attraction is removal of draft/redo work and balanced use
of both cards, not another theoretical doubling of bandwidth. Budget roughly
**1–3 engineering days for the decision prototype**, then several more days
for production ownership/controller integration only if it passes. This is
an effort estimate, not a seal/requalification instruction.

1. From the current launch DAG, produce a legal exchange schedule for a normal
   GDN, upgraded GDN and QSA block. Keep full-row kernels initially, group only
   independent transfers, and compare every rounding boundary and state bank.
   If the required exchange count alone exceeds the timing budget, reject this
   layout before building a full model. Do not assume four boundaries/layer is
   legal without the dependency proof.
2. The first coordinator experiment is one short, explicitly diagnostic A/B
   of those blocks, plus the final head, at current production shapes on a
   card pair. Use retained finite inputs and changing routes, including uneven
   and all-on-one-card expert selections. Measure **whole block wall time**,
   replicated work and actual exchanged bytes, not summed GPU-clock spans.
   Compare complete outputs/state byte-for-byte against the unchanged kernels.
3. Apply measured shape-specific costs to the 36/12 layer census, with the
   exceptional layers and head separate. Continue only if the recurring full
   step projects below **23.5–24 ms** with memory and exactness intact; below
   25.37 ms without margin is too vulnerable to a full-pipeline regression.
   A full realistic device suite and fresh repeat, with the immutable oracle,
   still decide whether any result counts.

This project has a falsifiable 4–13% upside and a cheap early rejection. It is
preferable to building k=2 on an unmeasured second acceptance probability, to
resurrecting the 41-exchange TP implementation, or to predicting another copy
speedup from padded grid size. Failure would constrain the structural ceiling;
it would not establish that the lane is finished.

## Reproduce this study

From the repository root, output goes to stdout only:

```bash
nice -n 19 ionice -c 3 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 \
  python3 -B notes/p45_roofline_structural_analyze.py
```

The helper reproduces the byte/operation table, streaming/copy medians,
acceptance transitions, repeat equality, roofline aggregation, and renewal/TP
sensitivity arithmetic. Its input map includes SHA-256 for every read receipt.
The expert-only 46.74 sensitivity uses the existing [cycle analyzer][analyzer]
with S=A=3.2475405 ms and T=3.5249917 ms reductions; those are hypothetical K2
proxy savings, not newly timed kernels. Both packet trees stayed read-only.

[after6]: 2026-10-15-p45-after-speed6-levers.md
[hitgap]: 2026-10-15-p45-hit-cycle-gap.md
[lever2]: 2026-10-15-p45-lever2-design.md
[analyzer]: p45_after_speed6_analyze.py
[ceiling]: ../experiments/own-xpu-runtime/stage2/packet7-kopt2/receipts-card3-20261011/ceiling/native.json
[expanded]: ../experiments/own-xpu-runtime/stage2/packet10-kopt5/expanded.hpp
[core]: ../experiments/own-xpu-runtime/stage2/packet18-decode-v2/core_v2.hpp
[stage2]: ../experiments/own-xpu-runtime/STAGE2-PLAN.md
[expertnegative]: ../experiments/own-xpu-runtime/stage2/packet11-kopt6/README.md
[replay]: ../experiments/own-xpu-runtime/stage2/packet34-replay-bench/receipts-card3-20261012-r1/README.md
[peer]: ../experiments/own-xpu-runtime/stage2/packet12-peer/README.md#first-measurement--cards-2-and-3-2026-10-11-061x-utc-boot-13858eef
[tp14]: 2026-10-11-first-device-answer-and-arithmetic-v2.md#4-within-layer-two-card-split-is-exact-on-the-cards-and-its-exchanges-are-too-many-packet-14-cards-23
[tpdesign]: ../experiments/own-xpu-runtime/stage2/TWO-CARD-TP.md
