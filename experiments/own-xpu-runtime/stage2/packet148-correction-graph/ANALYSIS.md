# Packet148 — can both ranks share the corrected first half exactly?

October 18, 2026. **Close at the requested +2% gate; no design brief.** None
of the graphs below has both a supported net saving and a complete memory fit.
The current two-card bundle8 result remains **58.7981087592 tok/s**.

The useful new result is a costed distinction between distributing **rows**,
moving **layers**, and sharing **causal token rows**. Whole boundary layers do
not fit. Selected dense rows fit, but their repeated exchanges consume most of
the possible saving. The broadest favorable head-sharing sensitivity reaches
**+1.914%**, even granting free state/KV coherence and its storage. That is not
a supported prediction, and it still misses the gate. This closes these
specified graphs under today's evidence, not all possible correction graphs.

| Graph | CPU decision on bundle8 | Main reason |
| --- | --- | --- |
| Cooperative independent output rows, rank0 owns all state | Payload-sized idle-transfer sensitivity **+1.042%**; implausibly cheap all-5-KiB sensitivity **+1.323%** | Per-layer/per-island exchange and resident row-bank cost |
| Whole GDN/QSA heads including state | Even free-coherence sensitivities **+1.569% / +1.914%** | Real coherence is additional; these are favorable relaxations, not qualified layouts |
| Correction-only layer-boundary move | **No whole boundary layer fits**; serial C is not eliminated by moving it | Layer23 weights alone **1.119 GB**, versus **0.786 GB** margin |
| Expert cooperation by resident rows, selected experts, or streamed weights | No supported +2% case | Full row banks exceed memory; current-route streaming is **241.28 MB/miss** for half the selected rows |
| Row-shared causal verification of corrected and next speculative tokens | Free second-row work gives **0%** with B fixed; even granting the old diagnostic suffix wait for free gives only **+1.864%** | Earlier A has no direct race benefit; an indirect head-readiness benefit needs new evidence |

All percentages in this document are **offline sensitivities**, not benchmark
points. The candidate has no implementation, quality pass, device measurement,
proposal, readiness marker or authorization to run.

## Identity and the exact value hurdle

The anchor is [packet136 bundle8](../packet136-record-bundle/submission/prepared-a/result.json):
the quantized compressed Unsloth UD-IQ3_XXS model, unchanged target weights,
`iq3-p49-split32-v1`, 24/24 target layers, rank1 MTP, fixed 80,128-row draft
prefix, full BF16 KV/state, context capacity 4096, banked rollback, E1,
down-tile16, the existing HC/route/recurrence/fusion choices and split head.
The binary SHA256 is
`fd7e8b6f5fb24c5042d051f59026091a9184c0f15149d7de110528b7d3ac5451`.
Its owner-authorized 128-token scope, false strict512 gate and missing prefill
measurement are unchanged. Nothing here updates a public performance claim.

The calculator reconstructs all twelve requests, six prompt classes and
**1,188 intervals between generated events 1 and 100** from the retained record
archive. It reproduces the median of class medians exactly, with **932 hits
and 256 misses**. It does not fit a pooled-average approximation to the record.

```text
Each emission interval:
    rank0: R -> C ----------------> A (next speculation) --+
    rank1: D -> wait for C -------> B (target + head) ------+-> emission

T = max(D, R + C) + max(B, A + offset) + G
```

On a hit R and C are absent. On a miss, host-envelope means are D=1.595828,
R=0.551168, C=11.818807, A=12.485768 and B=13.230429 ms. G is a signed
reconstruction remainder, not free idle. C-only saving changes the first max;
it does not also subtract the same work from B or from the next A.

**+2% requires 1.5738046002 ms net off C on every miss** in this replay.
For comparison, 0.5/1.0/1.5/2.0/3.0 ms give
+0.627/+1.262/+1.904/+2.556/+3.883%. Uneven per-layer or per-prompt gains
would require a new per-interval replay, not substituting their favorable mean.

The source proof is the frozen packet136 `native_controller.hpp`: launch the
available draft, restore and correct rank0 on a miss, then hand over the
complete streams. `rank.hpp` traverses dependent layers and exports four
2560-element BF16 streams: **20,480 bytes**. Moving a single 5,120-byte hidden
vector is not the same as moving this layer boundary.

## What the attribution supports

[128b](../packet128b-attribution/BUDGET.md) is a diagnostic body proxy for the
unchanged bundle8 kernels, **not a bundle8 per-layer speed measurement**. It
failed its overhead gate at 51.475451 tok/s. Rank0 hit classes represent one
half; miss classes contain correction **and** the next speculative half.
The model uses the former as a proxy, never the full miss total as C.

Relevant rank0 hit sums in milliseconds per half: GDN qkv 1.19701, z 0.70746,
attention output 1.12921, QSA qgate 0.46270, expert gate/up 1.46022, expert
down 0.93154, HC low A/F 0.27311/0.28945, HC gate A/F 0.52647/0.52980,
router tuple 0.53323, shared-down fused class 0.35413. Counts are 18 GDN,
6 QSA, and 24 common layers. These averages do not establish that each layer
has exactly that cost; layer0 also has exceptional formats.

[134](../packet134-submission-stalls/ATTRIBUTION.md) finds correction compute
busy 11.355503 ms and internal gaps only 0.085150 ms. Its 2.046383 ms
restore-to-correction gap includes 1.941660 ms instrumented preparation.
[135](../packet135-critical-path/ANALYSIS.md) instead finds ordinary record
preparation about 0.102197 ms. Neither the large instrumented gap, overlapping
enqueue time, nor rank1's roughly 10 ms dependency wait is a second saving
budget. Packet136 already banked the snapshot change. Packet144's restore,
preparation and B-only ceilings remain closed.

## Transfer prices and their limits

[87t](../packet87t-transfer-micro/RESULT.json) measures a complete staged
device→host→device transfer, with host ownership/publication in between.
These are not direct peer-memory measurements.

| Payload/condition | Median end-to-end µs | p90 µs |
| --- | ---: | ---: |
| 5,120-byte hidden, idle | 15.1935 | 17.6730 |
| 5,120-byte hidden, compute pending | 66.4350 | 68.8200 |
| 20,480-byte streams, idle | 24.8970 | 26.3990 |
| 20,480-byte streams, compute pending | 73.3425 | 76.0630 |
| 16-byte status/winner, idle | 14.3170 | 16.4510 |

The idle hidden legs are export 7.0585, import 7.8200 and host boundary
0.2300 µs. Component medians need not sum to the total median. The 1.307 µs
host-only mailbox result excludes GPU export/import and cannot price a
cooperative GEMV. The busy micro includes synthetic outstanding compute
(roughly another 50 µs); charging it after already-counted body work is an
intentional stress sensitivity, **not an additive physical copy floor**.

The [retained packet105b smoke](inputs.json.gz)
provides 768 samples per leg over twelve 64-token requests:

| Packet105b leg | Bytes | Median µs | Interpretation |
| --- | ---: | ---: | --- |
| hidden-import | 5,120 | 22.763 | Host-timed import, including completion/retirement |
| best-export | 16 | 22.963 | Host-timed small export |
| prefix-export | 16 | 26.650 | Host-timed small export |
| hidden-export | 5,120 | 8,903.550 | **Dependency wait**, not isolated copy latency |

The smoke's asynchronous export starts behind the body; its
`host_dependency_wait_us` includes that pending work. It is not an 8.9 ms DMA
charge, and cannot be added to C. The later
[retained target-only split grid](inputs.json.gz)
uses the repaired p105 protocol in packet106b, with a drained export and a
different timing scope. Its 1,600 samples per leg include the separate 64-token
incident check plus twelve 128-token requests. Export/import medians are
**53.991/22.452 µs**, best/prefix export **22.943/25.428 µs**.
The modeled 5-KiB one-way sum is **76.443 µs**, before unmeasured new
controller/assembly cost. It is a sum of marginal medians, not a measured
round-trip percentile. We retain both versions and their source files; the
later drained leg is not mislabeled as the asynchronous smoke's DMA time.

The archive retains both original `summary.json` files and all transfer logs
under their original keys in `stage2/screen/v4-lanes/evidence/`:
`p105b-eeccee46f0f1-B-smoke12` and
`p106b-13e3630d590c-B-grid-1-head-split`. These local screen paths are not
tracked individually; the new input archive makes the cited evidence durable.

Those production costs explain why 87t's idle micro is an optimistic price,
not guaranteed transfer into a new engine. Neither historical line measures
bidirectional per-layer cooperation on bundle8. The production proxy and the
87t busy stress make all modeled row islands prefer **off**; that means no
positive modeled saving under those assumptions, not a new device result.

## Memory: exact allocation census, not nominal card capacity

The bundle8 banks selection's memory plan and saved rank0 allocation census
are retained in [inputs.json.gz](inputs.json.gz). The plan is a measurement of
**actual allocation calls on the mock backend**. Physical driver residency
is unmeasured by it. It corroborates the brief's cards-are-full warning without
treating the card's nominal capacity as available duplicate-weight space.

| Bytes at capacity 4096 | Rank0 | Rank1 |
| --- | ---: | ---: |
| Device arena allocations | 28,144,182,388 | 31,425,985,242 |
| Arena limit | 32,212,254,720 | 32,212,254,720 |
| Remaining arena bytes | **4,068,072,332** | **786,269,478** |
| Plan's nominal physical free, including its allocation accounting | 6,051,614,920 | 2,815,083,814 |

Do not substitute that last row for the arena margin or reduce the standing
1.5 GB physical reserve. Rank1 already includes **3,354,364,214 draft bytes**.
Evicting/reloading them on each miss, or moving the draft to rank0, creates a
different critical path; packet79's relocation is not reopened here.

Useful duplicate-storage numbers, in **decimal MB/GB**, not MiB/GiB:

| First-half object copied to rank1 | Device bytes before extra scratch |
| --- | ---: |
| All layer0–23 weights | 27,205,763,840 |
| All routed expert banks, 512 experts per layer | 24,707,072,000 |
| Half of every routed bank's output rows | 12,353,536,000 |
| Half of qkv + z + attention-output + QSA-qgate rows | 869,416,960 |
| One quarter of qkv + z + QSA-qgate rows | 310,108,160 |
| Whole layer23 weights | 1,118,902,272 |
| Layer23 KV / workspace | 9,699,328 / 280,022 |
| Layer22 weights / recurrent state including both banks | 1,127,153,536 / 3,268,608 |

Even the three **packed original expert tensors alone** in layer23 total
1,009,254,400 bytes (two 268,697,600-byte IQ2_S banks and a 471,859,200-byte
IQ4_NL down bank). Avoiding expanded dense padding cannot make a complete
boundary layer fit. Requantization is outside this identity.

## Graph 1: cooperative rows with state staying on rank0

For each chosen projection island:

```text
rank0: exact input ready -> send input --------> rank1 resident row slice
       unchanged local rows -----------------> local row slots
rank1:                         unchanged remote rows -> send result
rank0: receive into original row slots -> original dependent consumer
```

Rank1 needs the chosen immutable weight rows, original quant metadata/codebook
access, private input/output/status buffers and bounded staging. **It needs no
KV or recurrent state** when it executes only stateless projections. Rank0
retains norms, recurrence/attention, causal state and expert combination.
The input and output copies preserve original BF16/FP32 representations.
No partial K reduction crosses devices. Every row keeps its original split32
tree, lane order, scales, rounding and finite/error behavior.

The chosen fraction f has optimistic per-island completion
`max((1-f)*t, send + f*t + return)`. Both transfer legs may overlap local rows;
we do not pessimistically add them after both ranks finish. Granting perfect
linear row scaling gives `f=max(0,(1-(send+return)/t)/2)` and saving `f*t`.
This is a generous scheduling model, **not measured row scaling**. It ignores
launch floors, gather work, alignment, error publication, draft contention and
additional scratch. An unchanged kernel's reduction ordering is necessary but
does not prove its throughput scales with row count.

The larger column below pads to 87t's measured 5,120/20,480-byte sizes and
splits larger messages into multiple chunks. It is an explicit size-pricing
assumption, not an interpolated measurement. For a favorable cross-check the
calculator also prices **every message at 5 KiB**, including larger ones.

| Island, occurrences in C | Rank0→1 / rank1→0 bytes at half rows | Idle exchange µs/island | Proxy compute µs/island | Serial work left |
| --- | --- | ---: | ---: | --- |
| GDN qkv+z, 18 | 5,120 / 16,384, combined result | 40.090 | 105.804 | Conv, recurrence, gates, output, HC, MoE, then next layer |
| Attention output, 24 | 12,288 / 2,560 | 40.090 | 47.050 | Original projection tree and stream combine |
| QSA qgate, 6 | 5,120 / 12,288 | 40.090 | 77.117 | K/V/index preparation and causal attention |
| HC low A/F, 24 each | 20,480 / at most 648 | 40.090 | 11.380 / 12.060 | Gate consumes all rounded low activations |
| HC gate A/F, 24 each | 10,880 / 12,800 | 49.794 | 21.936 / 22.075 | Keep all four stream gates for each mix output together |
| Router/shared tuple, 24 | 5,120 / 1,794 | 30.387 | 22.218 | Original global route normalization and sorted top10 |
| Expert gate/up, 24 | 5,240 / 12,840 | 49.794 | 60.843 | Complete activation before down |
| Expert down, 24 | 12,920 / 25,620 | 74.691 | 38.814 | Ten separate expert slots, original ordered combine |
| Shared down/fused class, 24 | 1,280 / 2,560 minimum | 30.387 | 14.755 | Fused mixture dependencies still required |

Small scalar controls/error flags either ride the envelope's spare bytes or
need additional work. The small-class estimates deliberately grant whole
class time to the distributed rows; fused stream/mixture work would not all
disappear. A single exchange at the end of each layer does **not** provide
the intervening HC, attention and expert dependencies. Packet12 already
refuted that assumption. Only qkv and z are combined here because they share
the same input and are independent projections. HC low→gate and expert
gate→activation→down remain separate joins.

The best fractional allocation under the 786.27 MB **weights-only** margin
gives the following. Fractional layer selection and zero scratch are favorable
relaxations, not an admitted runtime layout.

| Price model | Net C cut ms | Projected tok/s | Gain |
| --- | ---: | ---: | ---: |
| Payload-sized 87t idle | 0.827674 | 59.410726 | **1.041899%** |
| All messages charged as 5 KiB idle | 1.048280 | 59.576179 | **1.323291%** |
| 87t compute-pending stress | 0, choose off | 58.798109 | 0% |
| Production drained 5-KiB leg proxy for every message | 0, choose off | 58.798109 | 0% |

In the payload-sized case, qkv/z, attention output and qgate consume
307.821+36.863+59.825 MB and save 0.591421+0.083519+0.111079 ms.
The remaining memory buys only a fractional expert-gate subset, adding
0.041656 ms. In the all-small case, those dense families consume 517.035 MB
and save 1.018902 ms; the remaining expert slice adds 0.029377 ms.
The entire all-small island set, **without enforcing memory at all**, saves
only 1.485495 ms, still below the 1.573805 ms hurdle in this particular model.

A simple quarter-row qkv/z/qgate subset costs only 310.108 MB plus bounded
scratch, showing that the row idea is not categorically memory-impossible.
It is the **value** test that fails. Rank1 initially owes D; grants of immediate
availability are favorable. A real schedule must either start collaboration
only after D or charge contention/delay. Averaging C/24 does not prove the
draft is finished before a particular early layer.

## Graph 2: whole attention heads, including state

Distribute complete GDN head groups through qkv, convolution, recurrence, z
and gating, then join their outputs before the original output projection.
This keeps each head's original arithmetic and avoids several intra-head
round trips. Similarly, complete QSA query heads could be computed remotely,
with the original softmax and attention reduction per head. This is distinct
from splitting the summation over K or changing recurrence arithmetic.

Rank1 must now hold more than stateless rows: committed conv/GDN state or
the QSA keys/values/index state the remote heads actually read. With **half**
the GDN heads, one committed conv+recurrence image is **14,708,736 bytes**
over 18 layers, or **817,152 bytes per layer**. A correction-only owner must
send the prior committed image and return updated state, in addition to the
5,120-byte input and roughly 6,144-byte head result. Those state messages are
far outside 87t's measured payloads. Persistent mirrors instead require
coherent updates on **every accepted token**, including hits, plus correct
rollback, terminal and reset handling. QSA at 4096 has 9,699,328 bytes per
layer of KV/index allocations; query-head partitioning does not automatically
halve shared K/V and index state. No compressed KV is allowed.

GDN's diagnostic head-chain sum is 2.743320 ms. Granting **free state storage
and coherence**, perfect head scaling, the same weight-only fractional budget,
and the remaining graph-1 islands gives:

| Favorable head-chain sensitivity | C cut ms | Gain |
| --- | ---: | ---: |
| Payload-sized idle exchanges | 1.240003 | 1.569123% |
| Every message priced as 5 KiB; QSA state also free | 1.507762 | 1.914460% |

The second number is only 0.066043 ms short of the mathematical threshold,
but has **not paid any real state-coherence cost** and uses failed-overhead
class proxies. Its proximity is uncertainty, not evidence of a pass or an
invitation to round 1.91% up to 2%. The real graph needs new state-transfer,
head-partition and hit-path evidence before a positive projection is supported.

## Graph 3: move the boundary only during correction

For boundary b<24, rank0 computes corrected layers 0..b-1, sends the
**20,480-byte streams**, then rank1 computes b..23 and its usual 24..47.
One boundary message costs 24.897 µs idle / 73.342 µs busy in 87t, not
15 µs. There is no transfer between the consecutive layers on rank1, but
**their causal compute stays serial**: layer b+1 needs layer b's result.
If rank0 resumes ownership for next-token speculation at layer24, it also
needs the completed layer23 streams back, another 20,480-byte transaction,
plus the moved layers' updated state before their next use.

Rank1 must duplicate every moved layer's immutable weights, KV/recurrent
state and scratch, or receive them. The nearest whole layer, 23, requires
**1,128,881,622 bytes** including its listed KV/workspace, exceeding the
margin by **342,612,144 bytes** before new transfer/control storage. Thus
**zero complete boundary layers fit** on the existing arena plan. Moving
only dense operators within a boundary layer returns to graph 1 or 2.

Even with free memory, moving serial work to an equally fast idle rank does
not by itself shorten C. It can let rank0 start A sooner. But saved miss
intervals have `B-A-offset >= 0.493968 ms`: **B is later on all 256 misses**.
Granting A free has no emission benefit **with B held fixed**. B includes
split-head service dependencies, so earlier A might also advance its suffix.
That indirect benefit is not measured by the command-level slack; graph 5
prices a favorable diagnostic sensitivity rather than declaring it impossible.
A faster remote implementation or a different overlapping verifier would
need its own measured mechanism.

Permanently moving layers/weights back the other way to make room changes
the hit graph and re-enters packet120/123's placement and state-ownership
question. Packet120's static 25/23 loss is not proof that this new graph loses;
the new rejection here is its **duplicate memory and serial dependency**.
There is no unpriced static-placement retry hidden in this correction study.

## Graph 4: cooperate on routed experts or stream their rows

Exact expert cooperation can either split each selected expert's output rows
or assign complete selected experts. Rank0 must assemble each rounded expert
output in its original slot and execute the original ten-slot mixture order.
Summing two card-local partial mixtures changes FP32 order; packet12's
cancellation counterexample already closes that shortcut.

**Resident row banks:** arbitrary routes require coverage of all **512** expert
IDs, not just the ten currently selected. Half of all first-half banks costs
12.354 GB. Even giving every remaining rank1 byte to these banks covers only
3.1824% of their rows across all layers, before workspace or status. A single
ordinary layer's half banks fit at about 511.18 MB, but its roughly 100 µs
expert GEMV work cannot supply 1.574 ms of net C saving. The calculator prices
the much more favorable fractional multi-layer alternative above.

**Fixed resident expert subset:** rank1 can retain a bounded, prompt-independent
subset and take whichever current routes hit it, with rank0 providing the
fallback. This is an immutable weight cache, not forbidden prompt reuse.
However, a fixed ID partition does not guarantee five selected experts per
rank: all top10 may lie on one side. No new independent route/coverage and
load-balance evidence qualifies such a subset here. Balanced five/five work
still needs the original per-expert outputs, about 25,600 bytes plus status
back per active layer, and the input/route data out. It is not a 16-byte
winner reduction like the already-adopted split head.

**Demand-streamed row slices:** the actual selected ten experts' half rows
total **241,280,000 bytes per miss**, averaging **10,053,333 bytes/layer**.
This counts the loaded layouts, including the exceptional layers, with
512 experts per bank. It does not select easy routes or read model payloads.
The route is known only after that corrected layer's router, so transfers
cannot all start at the beginning of C. Per-layer gate/up, activation and
down dependencies still apply. Ping-pong scratch can fit, but loading must
finish before consuming each row and evicted rows cannot remain magically
resident for the next layer.

For scale only, **assumed**, unmeasured end-to-end service of 20/40/80 GB/s
costs **12.064/6.032/3.016 ms per miss**, versus at most **1.195880 ms**
from perfect halving of the two expert GEMV class totals before communication.
These copy times may partly overlap local expert computation; the round-trip
branch model still requires remote rows to arrive before the original join.
They cannot be priced with 15 µs independent of bytes. A direct peer read,
remote weight mapping or cache-hit variant lacks matched bandwidth/residency
evidence; local-device copy bandwidth is not inter-card bandwidth. It does
not pass the supported-transfer gate. Streaming all boundary-layer weights
is still larger and remains serial.

## Graph 5: row-shared causal verification

There are two different meanings of “row” here. Disjoint **output dimensions**
of the same token are graph 1. Consecutive **token rows** require causal
state: corrected token p must update each layer's state before the speculative
p+1 row uses it. The latter must consume its actual draft proposal, not an
invented or benchmark-selected next token. QSA must see p's full-precision KV;
GDN/conv must see p's corrected state. Rejected p+1 work is private and rolled
back exactly, including histories, banks and terminal cases.

One possible graph evaluates C and the next A together on rank0 with shared
weight reads, then sends the corrected streams to rank1 for B. The next-token
pair needs at least 40,960 bytes of layer streams if both rows are transferred
(two 20-KiB messages: 49.794 µs idle / 146.685 µs busy), and appropriate
private mutable state. This may save A's weight traffic, but a barrier waiting
for the pair delays B. In the most favorable model, D remains fully hidden:

```text
T_pair = max(D, R + V2) + B + G, on misses only
```

`V2=C` (the second row free) reproduces **exactly 0% gain with B fixed**,
because B was already later than A on every miss. Assumed V2/C ratios 1.2 and 1.700307 give
**−2.859% and −9.342%**. The latter is merely a sensitivity using the scale of
the historical M2 ratio cited by packet147; it is **not** a measured causal
two-card ratio or a transfer of one-card performance into this record.

This is a component-only counterfactual, not a bound on every fused verifier:
earlier A could free rank0 for the split-head suffix and thereby reduce B.
Granting **all 1.468740 ms** of packet128b's instrumented rank1 miss suffix wait
as removable, plus a free second row (`V2=C`) and no new state/copy cost,
gives **+1.863986% (59.894097 tok/s)**. That historical diagnostic wait is not
a measured removable bundle8 budget; packet123/135 already warn against
equating it with ordinary slack. No supported ≥2% benefit follows from it.

Letting rank1 run p+1's first-half layers while rank0 runs p would require
the missing first-half weights (27.206 GB before state for a whole mirror)
and per-layer causal state/stream messages. A correction-only boundary
wavefront still cannot make p's dependent first half vanish. Streaming row p
early from a fused kernel might avoid the pair barrier, but has to establish
an earlier C completion and retain the original per-row reduction/BF16
boundaries; existing independent-snapshot M2 tests do not demonstrate it.
Using only rank1's already-resident second-half weights cannot evaluate p's
first-half operators. Sharing future A alone supplies no supported +2% case;
any additional benefit through B must be established, not silently credited.

This is not a new sibling draft, packet132 acceptance rescue, packet71's
recursive depth-two controller, or a lowered gate for any of those packets.
It would be a new verifier graph with unresolved lifetime and speed evidence.

## Exactness requirements and decision boundary

All assessed graphs preserve the same oracle identity. A future design would
have to preserve each original row's arithmetic, intermediate BF16 boundaries,
per-expert slot order, tie/finite/error handling, state commit/rollback and
draft feedback. Rank1 scratch cannot alias its live draft/target state. A miss
must use the verified actual token and matching sequence/position, with no
stale partial output after cancellation, EOS, request reset or peer failure.
Full token, layer/state, deterministic repeat and fresh-process equality
remain necessary. None were run for a candidate in this CPU study.

The decision needs **both** supported net saving ≥1.573805 ms/miss and a
complete allocation/lifetime fit. Favorable arithmetic scenarios, an idle
rank, an old micro win, a nominal physical-free number or a CPU feasibility
argument do not satisfy those jointly. No design brief is created.

This extends, rather than restates, [packet144](../packet144-miss-path/ANALYSIS.md):
that packet closed existing miss mechanisms at +3% and left cooperation
unpriced. Packet148 evaluates the new +2% question with actual arena objects,
message counts/volumes, both historical transport scopes, a fractional row
allocation sensitivity, state-coherence costs and the causal-pair dependency.
Its own [DO-NOT-REPEAT](DO-NOT-REPEAT.md) gives separate reopen conditions.

## Reproduction, checks and retained evidence

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet148-correction-graph/analyze.py --check </dev/null
```

This standard-library calculator caps its own address space at 4 GiB, reads
only saved source/metadata/receipts, extracts just two hash-pinned pure
interval functions by AST, and writes nothing in check mode. It verifies
captured source hashes and the external record archive, twelve successful
cache-zero receipts and their member hashes, all 1,188 reconstruction
identities, the exact baseline, transfer aggregates, arena margins and saved
analysis bytes. Peak RSS was about **148 MiB**. It imports no runtime, reads
no model payload, launches no GPU or service, and alters no settings or queue.

[analysis.json](analysis.json) contains every source hash, count, family
allocation and numerical scenario. [inputs.json.gz](inputs.json.gz) is about
**1.73 MB**: retention is intentional because the full historical 105b/106b
summaries and raw transfer logs may otherwise be unavailable after cleanup.
They bind timing scope and sample population, while the small source/census
snapshots preserve the derivation. Restore any captured member only under a
new scratch root: base64-decode `files[path].raw_base64`, verify its SHA256,
and optionally decompress an originally gzipped member. Never overwrite a
frozen original. The existing 5.56 MB packet136 record archive is referenced
by hash, not copied. No original evidence was removed.

Packet128b's BUDGET was already dirty at entry; its observed bytes are retained
as diagnostic evidence, not staged as a clean upstream result. Relevant
negative indexes were read and captured. No existing packet, shared screen,
ops file or live queue was edited. No external technique was adopted.

[Closeout](CLOSEOUT.md) · [Work note](../../../../notes/2026-10-18-own-runtime-packet148.md).
