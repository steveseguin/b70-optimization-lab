# Packet170: complete one-card MTP cycle — close without a build

**The +3% gate is not supported.** Packet166 establishes a useful causal
two-row layer mechanism, but the retained record does not contain the M1
operation shares needed to turn those ratios into full-model V2. Cache misses,
feedback and state selection also lack a current one-card complete-cycle
measurement or upper bound. These unknowns are not zero. The binding term is
**the unsupported complete verifier/cache/state budget**, not host RAM.

The declared resident-draft layout fits at an **18,216,076,800-byte target
cache**, preserving the 1.5 GB device reserve. Conservative host accounting
requires **103,314,356,320 bytes**, including the current resident lookup copies,
all new private-state backing, margin and reserve. It fits even after debiting
the entire 10 GiB of blocks 53–57 from the historical available-memory floor.
This proves arithmetic for the declared layout, not a new runtime allocation
census or permission to launch.

At acceptance 0.787 the allowed complete cycle is **54.273508 ms**. An expressly
conditional, fully charged sensitivity is **63.613909 ms**, or **28.0913 tok/s
(−12.12%)**. It is not a measured result, a statistical bound, or the reason to
pretend the unknown primary estimate has become known. A favorable sensitivity
that omits feedback/selection can still show a gain. That is why the decision
uses evidence completeness as well as arithmetic. No `BUILD-PLAN.md`, runtime,
readiness marker or launch proposal is created.

## Identity and decision rule

[Preregistration](PREREGISTRATION.md), [reproducer](cycle.py),
[complete values, labels and source hashes](cycle.json),
[negative-history audit](dnr-audit.json), [all matching lines](dnr-scan.txt),
[closeout](CLOSEOUT.md), [new negative row](DO-NOT-REPEAT.md).

Anchor: packet58aj WS128, one B70, Unsloth UD-IQ3_XXS quantized compressed
target, `iq3-p49-split32-v1`, context4096, full BF16 KV, tile16, overlap,
21,552,729,600-byte weight cache, full resident lookup copies and the complete
accepted 58aj kernel composition. Actual receipt rate is 31.9668197878 tok/s;
the requested rounded anchor is **31.966820**, reciprocal **31.282435976 ms**.
This reciprocal is a modeling anchor, not measured mean token wall time.
The 12 prompts each have 128 outputs; strict512 remains false. Nothing is
promoted or submitted by this packet.

Paths below are relative to `experiments/own-xpu-runtime/stage2/` unless they
start with `notes/`. `cycle.json` gives full repository `file:line` citations,
JSON selectors and SHA256s. Labels mean: **measured** in the stated original
scope; **transferred** across configuration/schedule/workload; **assumed** as an
explicit sensitivity. A measured source does not make its transfer measured.

## Complete cycle and missing M1 shares

One confirmed frontier input and one proposed input produce `1+a` verified
tokens on average. There is no two-card overlap on this card:

```text
C = V2_layers + embedding/PLE + head/final-norm/argmax + exposed host issue
    + target miss service + D + F + S + (1-a)R + P + E
rate = 1000 * (1+a) / C
```

`E` is additional exposed fill/cache work only if not already in the chosen
miss-service model. A rejection does not add another full target forward:
the first verified row and its correct output are already in V2. It does
require discarding the wrong second row, restoring draft state and selecting
the correct target prefix. Accepted rows still require state selection and
draft advancement. Those costs cannot be charged only on rejection.

**Requested evidence unavailable:**
[58ao README](../packet58ao-onecard-next/README.md):77–90 explicitly records
that 58aj's device class times are zero placeholders and its enqueue-family
breakdown is null. `cycle.py` independently checks **all 1,536 generated rows**
in the twelve original 58aj timing streams, and retains their hashes and first
line citations. It does not mistake the empty suite-root stream for the actual
per-request streams. The primary `current_M1_ms`, `current_M1_share`, V2, cycle
and gain remain JSON **null**. Thus the requested measured-share calculation
cannot honestly be supplied from these receipts.

Packet166's [analysis](../packet166-m2-layer-micro/evidence/layer-micro-B1/analysis.json)
contains measured class ratios for GDN layer0 and QSA layer3 at positions
2/3/31. Every buffer and the CPU oracle matched in that micro. It excludes
embedding/PLE, head, host scheduling, transfers and draft. It does not measure
all 48 layers, exceptional IQ3 layer2, rejected full-model paths, or a native
one-card verifier. Its expert-union cost is already inside its expert ratios;
do not multiply those ratios by 16.5/10 again.

To expose sensitivity without inventing current shares, the following table
uses twice the **historical rank1 half-body** class times from
`packet58ao-onecard-next/README.md:87–114` (p128b/p140 diagnostic, instrumentation
overhead gate failed). Each class is mapped separately to packet166 operations;
the minimum/maximum across relevant measured operations and contexts is shown.
This is an imperfect mapping, not a fitted model or a statistical interval.
All values are **transferred**, never packet58aj measurements.

| Class | Proxy M1 ms, doubled half | M2/M1 sensitivity | Proxy V2 ms |
| --- | ---: | ---: | ---: |
| Dense attention projections | 6.974328 | 1.2311–1.3308 | 8.586307–9.281620 |
| Expert gate/up | 2.885950 | 2.6456–2.8770 | 7.635078–8.302814 |
| HC gate/mix | 2.121184 | 1.5714–1.6471 | 3.333296–3.493701 |
| Expert down | 1.879893 | 2.0256–2.0770 | 3.807943–3.904471 |
| Remaining small sites | 1.400984 | 0.8147–1.3426 | 1.141444–1.881021 |
| HC low/inject | 1.132664 | 1.6922–1.8053 | 1.916650–2.044803 |
| Route/shared activation | 1.085058 | 1.0543–1.0594 | 1.143934–1.149529 |
| Router/shared tuple | 1.054132 | 1.4334–1.6696 | 1.510949–1.759962 |
| GDN recurrence | 0.898924 | 1.6737–1.6791 | 1.504550–1.509380 |
| HC norms | 0.762016 | 1.7109–1.7522 | 1.303771–1.335219 |
| QSA attention/select | 0.716257 | 0.9606–1.3410 | 0.688025–0.960488 |
| Shared down/mix | 0.705293 | 1.3333–1.4913 | 0.940384–1.051828 |
| Small dense projections | 0.628084 | 1.2720–1.6696 | 0.798904–1.048640 |
| **Body proxy sum** | **22.244767** | No full-wall ratio used | **34.311235–37.723473** |

The unpartitioned remainder of the anchor after this assumed M1 body and
publication is **7.927669 ms**. It is not measured host time or measured cache
time. It contains unknown non-layer work, remote penalties and mismatch between
the old body proxy and this record. The two sensitivities pay this remainder
once/twice; neither pretends to know its internal shares.

| Non-layer/cycle term | Behavior and value | Label and source |
| --- | --- | --- |
| Embedding/PLE | Two causal input preparations; private provisional histories. Charged sensitivity uses 2× its unknown M1 cost inside the remainder. | Assumed; `packet58ao-onecard-next/README.md:77–90`; no isolated current cost. |
| Head, final HC/norm, argmax | Two full unchanged target decisions, original trees/tie order. Charged sensitivity uses 2× unknown cost; prefix head is draft-only. | Assumed; `packet58ao-onecard-next/README.md:108`. No full-head M2 ratio. |
| Exposed host issue | Unknown; 5.053453 ms enqueue and 0.206020 ms prepare are measured overlapping spans, not additive exclusive time. Charged remainder uses 2×; favorable uses 1×. | Assumed transfer; `packet58ao-onecard-next/README.md:60–83`. No graph-replay credit. |
| Draft D | **1.794747 ms**, fully serialized on this card. Resident INT8/group16 experts; 91,392-row shared head prefix. | Transferred; `packet58h-onecard-mtp/FEASIBILITY.md:171–186`, `packet85-critical-path/MODEL.md:61–68`. |
| Feedback/repair F | Historical op17 **1.603611 ms** when needed. Charged case pays one per cycle; favorable omits it. Actual frequency and one-card duration unknown. | Transferred duration, assumed frequency; `packet85-critical-path/model.json:2264`, `MODEL.md:246–267`. |
| Rejected-row R | **0.980923 ms/rejection**; expected **0.208937 ms/cycle** at a=.787. | Transferred restore proxy; `packet58h-onecard-mtp/FEASIBILITY.md:212–216`. |
| Target state S | Every cycle must initialize/select the proper prefix, including extents, recurrence, PLE/history, errors and prepared-pointer metadata. Charged sensitivity pays another **0.980923 ms/cycle**; favorable omits it. This assignment is not a proved bound. | Assumed; `packet58h-onecard-mtp/FEASIBILITY.md:78–114`. R and S represent different work. |
| Publication P | **1.11 ms once per cycle**, not per verified token, conditional on legal publication cadence. | Transferred rounded boundary; `packet58aq-onecard-split/.../resident/WSCREEN/run/summary.json`, `paired_differences.device_publication_and_drain`. |
| Target misses and E | Priced below; current M2 unknown. Native-capacity normalization includes exposed fill effects, so separate E=0 **in that sensitivity only**. | Transferred/assumed; cache section. |
| Draft cache/pollution | Resident option has no draft entries in target LRU; it pays the smaller arena instead. Shared option has unknown draft misses and target pollution. | Assumed placement, sourced allocation; `packet58aa-onecard-mtp-recheck/ANALYSIS.md:97–107,235–241`. |

The historical draft is the 58h/58aa design, not bundle8's later 80,128-prefix
draft. Packet166's target-layer timing does not silently substitute that newer
draft or grant its acceptance. Every accepted token remains target-verified;
no draft variant or arithmetic change is adopted here.

## Cache shrink and larger route union

**Measured native capacity evidence:**
[58x result](../../../../notes/2026-10-18-own-runtime-packet58x-result.md):5–15,
and its pinned `evidence/card0-capacity-d/max/WSCREEN/summary.json`.
The 18 GB warm controls gave 28.156674/28.199899 tok/s, versus
29.568647/29.363935 with 21.553 GB. The reciprocal differences across all
four warm pairings are **1.405739–1.695951 ms/position**. A0's 23.109763 is
retained but excluded by that historical experiment's registered warm-up
rule. This is a one-load diagnostic capacity effect, not a new cold-suite
headline or a measured result at 18.216 GB.

**Measured native miss evidence:** 58y's 18 GB census recorded **47.115320
misses / 93.402268 MB per token**, versus **21.755892 fills / 43.128372 MB**.
Sources: `packet58aa-onecard-mtp-recheck/analysis.json`, `diagnostic58y`, and
`ANALYSIS.md:173–177`. Fills are not misses. The 58aj cache stream records fills,
not a paired 18.216/21.553 GB native miss census. No such paired measured
hit-rate curve is claimed.

The saved 58aa replay supplies the missing *conditional* capacities and M2
schedule, using held-out real route captures. All numbers below are
**transferred replay**, not native one-card measurements:

| Layout / work | Missing expert reads | Logical miss MB | Fill MB |
| --- | ---: | ---: | ---: |
| 21.553 GB, M1 | 32.664931 | 64.717022 | 31.633156 |
| 18.216 GB, M1 | 47.477431 | 94.064756 | 45.795244 |
| 18.216 GB, M2 stable union | 96.159722 | 190.497067 | 83.218489 |
| 18.216 GB, M2 separate reads | 103.208333 | 204.458489 | 83.048622 |
| Shared arena 21.362 GB, M2 union, **no draft pollution** | 67.993056 | 134.712356 | 58.233156 |

Counts are derived per layer using 1,971,200 bytes/ordinary expert and
2,329,600 bytes/layer2 expert, not by dividing all bytes by one size.
Cache shrink alone adds **14.8125 misses/position** and changes replay expert
hit rate from **93.1948% to 90.1089%** (480 selections/M1). Actual 18 GB native
hit rate was **90.1843%** in the older 58y diagnostic. This supports the scale,
not equivalence of the runs or proof of the extrapolated latency.

The measured route captures yield union **16.515053** experts per layer in
packet55 and **16.778590** in packet138, versus ten for M1
(`packet58aa-onecard-mtp-recheck/ANALYSIS.md:120–156`). The latter contains
accepted paths only. The M2 cache replay groups accepted consecutive rows and
assumes a 55 ms fill-progress window; it does not implement wrong-proposal
routes or prove their cost. We retain both union reuse and separate reads.

For the sensitivity only, divide the **measured** capacity period change by
the **replayed** 14.8125 extra misses: **0.094902–0.114495 ms per extra miss**.
This mixes workloads, 18 versus 18.216 GB, and scheduling. It is **assumed
normalization**, not a measured sparse-miss price, an interpolated measurement,
or a guarantee at other cache capacities. It includes the capacity experiment's
exposed fill/maintenance effects; charging fill bandwidth again would duplicate
cost. With remainder multiplicity `k`, add only `(N2-k*N1)*price`. The baseline
remote component was already carried `k` times. Thus favorable union adds
6.025796 ms over one baseline miss component; charged separate reads add
4.336881 ms over two. The union factor is not applied a second time to kernels.

**The requested CPU-miss price is a different path.**
`packet55-feasibility/evidence-copy/cpu-bench-receipt.json:826` records eight
threads at **0.514465–0.534364 ms/expert** across measured 4/6/10-expert batches.
At twelve threads it is **0.348518–0.365165 ms/expert** (`:1199`). These are
synthetic exact CPU expert kernels on this host, not GPU host-memory reads.
At the requested rounded 0.5, shrink alone costs **7.40625 ms/M1**; the whole
M2 miss service costs **48.079861–51.604167 ms/cycle**, before resident GPU work,
draft and state handling. The CPU fallback remains closed. Applying this
number to the current GPU zero-copy path would misprice the mechanism.

The shared-cache option saves resident bytes by placing 3,145,728,000 draft
expert bytes in host memory. If all become cached, target capacity falls to
18,216,027,648 bytes—essentially the resident case. If none become cached, each
draft step can read 61.44 MB remotely; resident D then no longer prices it.
The 58aa 19–25 GB/s scale is 2.46–3.23 ms, only a transfer sensitivity, not a
zero-copy measurement. Partial draft caching trades misses against pollution;
its optimum is unknown. Do not combine the no-pollution row with resident D
and call it a complete build case.

## Acceptance, drain and sensitivity

The specified **a=.787** is rounded from **100/127=.787401575**, the median
per-prompt acceptance in packet77's two-card control. `cycle.py` checks that
all twelve prompt IDs **and prompt-token hashes match 58aj**. It is the same
quantized target/arithmetic and suite, but a different topology/schedule and
historical draft, so acceptance is **transferred**, not measured for this
one-card causal-M2 design. The pooled first-99 value was .787879; it is not
substituted for the requested median. Source: `packet85-critical-path/MODEL.md:26–52`.

Packet58aq measured combined publication/drain removal at **1.107661 and
1.111002 ms/token**; drain alone was about 1.071 ms. Use the requested rounded
**1.11** once per cycle. Relative to paying it per emitted token this credits
`a*1.11`: **0.873570 ms/cycle**, or **0.488847 ms/verified token** at .787.
This is not a second saving on top of subtracting the same boundary from V2.
The charged cycle below excludes P from the body/remainder and adds P once.

If packet58ar/58as remove that boundary for plain decode, its hypothetical
anchor becomes **33.142833 tok/s** (`1000/(31.282436-1.11)`). That is not a
measured record. Remove P from MTP too for a fair drain-free comparison; also
retain the less favorable comparison with P still present in MTP in JSON.
No extra gain from either packet is claimed or added here.

| a | +3% maximum complete cycle, ms | Same threshold with drain-free plain baseline, ms | Charged sensitivity cycle, ms | Charged tok/s / gain vs record | Both drain-free gain |
| ---: | ---: | ---: | ---: | ---: | ---: |
| .70 | 51.631205 | 49.799166 | 63.699250 | 26.6879 / −16.51% | −18.05% |
| .787 | 54.273508 | 52.347712 | 63.613909 | 28.0913 / −12.12% | −13.74% |
| .85 | 56.186900 | 54.193210 | 63.552111 | 29.1100 / −8.94% | −10.61% |

The charged .787 row is the explicit sum:
**37.723473** class V2 + **15.855337** doubled unknown remainder +
**4.336881** extra cache/fill + **1.794747** D + **1.603611** F + **0.980923** S +
**0.208937** rejection + **1.110000** P = **63.613909 ms**.

The favorable .787 row uses the low per-class proxies, remainder once, stable
union, lower cache normalization and **free F/S**: 51.378383 ms,
34.7812 tok/s (+8.80%). It is not complete supported evidence. The charged
case is also not a certified conservative upper bound: doubling old rank1
body times and assigning S=R cannot replace actual current operation shares.
The primary bound remains unknown in both cases. The favorable endpoint
cannot authorize a build; the unfavorable endpoint does not prove all MTP
designs lose. Per-prompt transformed class-balanced values are also retained
(charged .787: 28.090871); aggregate reciprocals are not silently presented as
recomputed measured class statistics.

After D, expected rejection and P, the .787 +3% budget leaves **51.159824 ms**
for the complete V2, feedback, state selection and any uncounted cache/fill
cost. This is the concrete binding budget for reopening this composition.

## Device and host fit, with lifetime ownership

Source bounds: `packet58aj-onecard-resident/MEMORY.md:20–35`;
`packet58x-cache-capacity/admission.json:5–31`;
`packet58h-onecard-mtp/FEASIBILITY.md:34–114`.
Bytes are decimal; a GiB is 1,073,741,824 bytes.

| Conservative device category | Current | Resident draft | Shared-cache draft |
| --- | ---: | ---: | ---: |
| Target fixed/nonexpert | 5,815,529,984 | same | same |
| Target BF16 KV/index | 116,391,936 | same | same |
| Target recurrent | 59,019,280 | same | same |
| Workspace allowance | 1,073,741,824 | same | same |
| Private transaction allowance | 1,073,741,824 | same | same |
| Transfer allowance | 268,435,456 | same | same |
| Pointer generations + publication staging | 3,538,944 | same | same |
| Target/shared cache arena | 21,552,729,600 | **18,216,076,800** | **21,361,755,648** |
| Added resident draft weights + KV (+ shared tables) | 0 | 3,336,652,800 | 190,973,952 |
| **Device-owned bound** | **29,963,128,848** | **29,963,128,848** | **29,963,128,848** |
| Separate driver allowance | 536,870,912 | same | same |
| **Separate device reserve** | **1,500,000,000** | **same** | **same** |
| Margin under 32,000,000,000 | **240** | **240** | **240** |

The current 58aj census has **27,841,904,372** actual bytes, 262,144 more than
58z's older census. The new actual resident/shared payload projections after
arena reduction are **28,829,335,368 / 28,829,310,792**. The existing conservative
bounds still dominate; their reserved transient difference is not spare cache.
Unchanged max cache plus resident draft fails by **3,336,652,560 bytes**; even
the shared design fails by **190,973,712 bytes** without shrinking it.

Current canonical mutable target row: workspace 295,612,132 + recurrence
59,019,280 + KV/index 116,391,936 = **471,023,348** bytes, independently summed
from the current census. Keep canonical state untouched during verify; two
private rows consume **942,046,696** bytes. Add full draft mutable backup
27,410,742 and copy tables 262,144: **969,719,582**, inside the existing 1 GiB
transaction allowance with **104,022,242** spare. Original plus draft workspaces
are **313,323,546**, inside the separate 1 GiB workspace allowance.

Lifetime requirements remain binding: row1 consumes row0's *causal* temporal
state; do not use independent snapshots. Private KV writes stay BF16. On hit
select the second valid prefix; on rejection select the first, discard the
second, restore/repair the draft and preserve the correct next input. Sticky
errors, history/extent metadata, lookup bindings and command completion must
all survive selection. Do not restore cache pointers to overwritten slots.
Keep readers/generations fenced until reuse. Head/embedding/RoPE weights may
alias immutable target allocations; the draft's INT8 expert weights may not
alias IQ3 target bytes. Source tensors peak at 62,914,560 bytes, within the
retained 256 MiB loader allowance. No full extra source mapping is made resident.

These are a declared conservative allocation design, not proof that existing
M2 code meets it. Additional kernel scratch, private pointer structures or
staging must fit those reserved lifetimes; no unsafe alias is authorized.

| Host category | Bytes, resident option |
| --- | ---: |
| Existing pinned experts | 48,627,712,000 |
| Existing full resident lookup copies | 29,321,610,240 |
| Remaining reclaimable-file allowance | 4,001,477,120 |
| Measured process overhead | 565,325,824 |
| Independent shadow margin / live stop | 4,294,967,296 |
| Cache/metadata/staging allowance | 3,587,987,968 |
| Newer measured increment | 1,236,992 |
| **Existing host bound** | **90,400,317,440** |
| Retained 8 GiB reserve | 8,589,934,592 |
| Backing for **all** added actual device payload, before cache reduction | 4,324,083,796 |
| Added direct pinned staging | 20,492 |
| **Required available** | **103,314,356,320** |

For shared cache, added device backing is 1,178,380,372 and direct host payload
3,145,773,188, total requirement **103,314,405,592**. No reduced-cache backing
refund is taken. This is 524,288 bytes above the corresponding old 58aa
requirements because it uses the current 58aj host floor.

Historical available floor **119,233,388,544** minus **all five 2 GiB blocks
53–57** = **108,495,970,304**. Margins are **5,181,613,984 / 5,181,564,712**.
This deliberately subtracts blocks again even if already excluded in that
snapshot. It is a conservative accounting floor, not a new physical-capacity
measurement. It avoids relying on 58h's historical block57-online discrepancy
(`FEASIBILITY.md:162–167`) and gives no credit for excluded memory or swap.
Actual live availability, sealed admission and guards remain mandatory for
any future implementation. No settings or block states were readjusted.

## Negative history and reproducibility

The audit reads **253** repository-visible DO-NOT-REPEAT files and retains
**305** matching lines (`mtp|draft|speculat|verify|depth`), including all inherited
copies. Four indexes were Git-ignored; their exact text is retained in
`dnr-audit.json` so its check also works without the originating host's files.
Packet147 has no negative index: its `PLAN.md:290–347` is the decision
record. Prior mechanisms stay closed:

| Prior packet | Retained exclusion |
| --- | --- |
| 58h / 58aa | No free draft/cache, no obsolete full-device host-shadow rejection, no acceptance-only reopening, no fill=miss substitution. |
| 71b / 71c | No recursive three-pass proposal/controller revival; actual feedback/rebuild/selection made depth two lose ~47%. Restore extents/history and private ownership, not bytes alone. |
| 79 | No rank0 relocation, duplicated head or imported cross-rank overlap; measured placements lost 2.3%/1.3%. |
| 147 | A new causal graph needs the complete cycle, cache cost and private-state lifetime; proxy kernel ratio is insufficient. |
| 154 / 155 | Required waits are not idle; do not add overlapping host/device clocks or count already selected bundle changes again. |
| 156 | Hidden-only draft moved into suffix slack remains closed at ~0.29–0.32%. |
| 157 / 158 | No further draft decomposition/build on the closed rank1 critical-path arm; no load8/HC/prefix/precision/suffix/history retry. A one-card serial design cannot borrow two-card slack. |

No frozen packet, `stage2/screen/*` or `ops/*` is edited. `CURRENT.md` already
has unrelated concurrent edits; loaded state, active operational lane and
queues did not change in this CPU study. Its result is indexed by this new
packet's closeout and the new dated work note. No public package changed.

From the repository root:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet170-onecard-mtp-cycle/cycle.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet170-onecard-mtp-cycle/cycle.py --check </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet170-onecard-mtp-cycle/audit.py --check </dev/null
```

The native record/capacity/acceptance receipts include Git-ignored files.
[inputs.json](inputs.json) maps **16 exact compressed snapshots** in `inputs/`
to their original paths, byte counts and SHA256s. The archive bytes are also
hashed. `cycle.py` always uses these frozen copies, so a fresh checkout does
not need the originating host's ignored result tree. `capture_inputs.py`
records how these snapshots were created; rerunning capture requires the
original receipts, but normal reproduction does not. They are small retained
evidence, not model weights or generated caches. No original file was removed.

Both analysis scripts enforce a **2,000,000,000-byte address-space ceiling**. The cycle
run uses about 46 MB RSS. It reads only retained JSON/text, checks original
record tokens and missing class fields, and reproduces all numeric tables.
`--check` compares the complete JSON including input hashes, refusing drift.
No GGUF read, compile, GPU job, service, sudo, settings change or external
submission occurred. The packet does not claim new model quality evidence.
