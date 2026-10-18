# Packet135 — the 58.22 line's critical path

October 18, 2026. CPU synthesis only. **First finish the pending recurrent
snapshot experiment; second, test the combined exact token-input path described
below.** Conditional projections are **+1.18–1.78%** and **+0.62%**, respectively.
Neither is a measured gain or a proven lower bound. The second falls below
0.5% if less than about 60% of the assumed rank0 saving advances suffix service.
Do not turn that assumption into an admission receipt. There is no evidence
for two *already qualified* ≥0.5% winners.

The most consequential correction is that **token preparation on the actual
record is 0.102 ms, with zero major faults**, not packet134's instrumented
1.5–1.9 ms. The host path is still worth examining, but copying those larger
costs into the record would manufacture several percent of headroom.

All numbers below are either measured with their identity stated, byte-reference
calculations, or explicitly assumed savings. [model.json](model.json) reproduces
the record metric and the projections from frozen inputs. No runtime, GPU,
service, queue, setting, public result or existing experiment was changed.

## Identity and evidence hierarchy

The anchor is packet124c **WS128**, 58.2238342935355 tok/s, not its repeat or
the fastest screen. It is the quantized compressed Unsloth UD-IQ3_XXS model,
`iq3-p49-split32-v1` arithmetic, full BF16 KV, rank1 MTP, fixed 80,128 draft
rows, 202,240 target-head rows on rank1 and 46,080 on rank0. Bundle7 retains
the accepted expert half-cache, down-tile16, route/recurrence choices, draft
split32 attention, exact fusion and split target head.

The machine-readable selection says `layer_boundary=24`, `target_split=0`:
**24/24 layers**. The old prose in the prepared result packet says 23/25;
that is inconsistent with its own selection and the source/census, and is
not used here. Native binary:
`f77e0e9c50fa9f75d6d0900efa0241911fee34806dc9d118e1d9fab7edb73a01`.
The [record result](../packet124c-record-bundle/submission/prepared-a/result.json)
and [original-byte evidence bundle](../packet124c-record-bundle/submission/prepared-a/evidence.json.gz)
are the primary sources. WS128's owner-authorized 128-token scope and missing
strict512/prefill evidence remain as recorded; this analysis upgrades none of it.

Evidence is reconciled in this order:

1. **Actual record:** twelve requests, first 99 inter-token intervals each,
   common host-clock command traces, original per-half host timers. Recompute
   the six class medians and their median; obtain exactly **58.2238342935355**.
2. **Matched bundle7 history:** packet126's two complete packet118 compositions
   give hit/miss means 14.858/25.666 ms on A and 14.961/25.804 on B. They support
   the same dependency graph; they are not substituted for the record.
3. **Packet128b/134:** 84 sampled cycles, 66 hits/18 misses, all layers/both
   ranks. 51.475451 tok/s, 0.888 of 58.0; overhead gate **failed**. Use the
   class census and source attribution diagnostically. Do not divide its
   durations by 0.888, add its host and device rows, or derive ordinary-run
   head readiness from it. Its 25.6448 ms sample mean is not 17.2 ms/token.
4. **Packet110/122:** representative-layer rooflines and separate draft
   operator runs. Packet122's Markdown still says pending; its two completed
   `iterations.jsonl` receipts supply the fresh times here. Both have 40
   post-warmup samples at each of contexts 128 and 4096.
5. **Today's negative results:** the closed ledger and all **157 repository
   DO-NOT-REPEAT files** were read and pinned. Their matches and exact hashes
   are in `model.json:prior_audit`; full original text is in `inputs.json.gz`.
   Older packet108 budgets remain historical identities, not current timings.

## One consistent emission-to-emission model

An interval starts at a verified emission. Its hit/miss label describes the
guess verified **at that starting emission**. One interval yields one next
verified token; it never yields two tokens merely because two ranks overlap.
`A` is the **next** speculative rank0 half. The previous speculative half
is already complete; adding it again is double-counting.

```text
Starting emission: verified token t[p]
       |
       +-- rank1 D: hidden copy -> exact token embedding read/decode/upload
       |             -> draft kernels/head/argmax -> guess publication
       |
       +-- rank0: hit accept; or miss restore R -> correct target half C
                         |
                 wait until both ready
                         |
                 hand over corrected/accepted rank0 streams
                         |
          +--------------+----------------+
          |                               |
 rank1 target body                  rank0 snapshot capture
 final norm / hidden export         token/history/PLE preparation
 target head prefix + argmax         speculative target half A
          |                               |
          |                    suffix service after A completes
          |                    import hidden -> suffix head/argmax
          |                    -> export best candidate
          +--------------- merge full-head result
                                   |
                            verified next emission
```

Packet108's accounting remains correct:

```text
H = D + max(B_hit, A + offset) + G_hit
M = max(D, R + C) + max(B_miss, A + offset) + G_miss
T_pool = p H + (1-p) M
```

`B` already includes target-head suffix wait, merge, result retirement and
reply. `G` is the signed measured accounting remainder, not measured idle or
a promised removable overhead. Commands use the same host monotonic clock;
GPU clocks are never subtracted across ranks or against host/copy clocks.

| Actual WS128 host-envelope cost, ms | Hit (932 intervals) | Miss (256 intervals) |
| --- | ---: | ---: |
| Draft command D | 1.609391 | 1.608345 |
| Rank0 restore R | 0 | 0.546061 |
| Corrected rank0 half C | 0 | 11.820039 |
| Next speculative rank0 half A, including capture/preparation | 12.796884 | 12.798686 |
| Rank1 target half B, including head and suffix wait | 13.275496 | 13.323167 |
| A start relative to B start | −0.000578 | +0.000383 |
| G | 0.019700 | 0.013126 |
| Complete emission interval | **14.904587** | **25.702393** |

Every one of the 1,188 intervals reconstructs within 1e-7 ms. The pooled hit
fraction is 932/1188 = 0.784512. The weighted mean is **17.231387 ms**,
or 58.033633 pooled tok/s. The published median-of-class-medians instead has
reciprocal **17.175097 ms**. Both explain “about 17.2”; forcing the pooled
budget to equal the reciprocal headline would change the aggregation.
Projections below operate per interval and then recompute the actual class
metric, rather than silently substituting the pooled rate.

**B and A are coupled.** A useful refinement, relative to B's start, is

```text
B = max(U, max(A + offset, V) + S) + L
U = rank1 prefix/argmax and required local checks ready
V = rank1 hidden publication ready
S = rank0 suffix import, compute, export and publication
L = merge and final reply work after both branches are ready
```

These individual host boundaries were not captured in the record. Therefore
the measured `B−A` of 0.479/0.524 ms **is not free rank0 slack**. It includes
suffix service that cannot start before A. Conversely, all of B does not
necessarily advance when A gets faster: prefix readiness can become limiting.
Packets120,127,130 show that adding/delaying rank0 work hurts; they do not
prove that every future rank0 reduction transfers one-for-one.

## Serial segments, measured costs, floors and remaining mechanisms

“Floor” below means either an exact dependency limit or the explicitly labeled
useful-byte reference. No retained counter evidence establishes an attainable
numerical compute floor. A zero lower bound is not a claim of free work.
Unknown splits stay unknown; there is no complete measured additive kernel
partition of the uninstrumented 17.2 ms interval.

| Segment | Measured cost and source | Floor / exact open lever / projected value |
| --- | --- | --- |
| Rank1 target body, before final head | Inside record B; packet128b hit compute classes total **11.122384 ms**, excluding final norm/head/draft | Packet110's representative 18 GDN + 6 QSA useful-byte reference is **5.407656 ms/half at 537 GB/s**, excluding PLE/head/draft and predating newer fusions/down layout. It is not a current half prediction. No new qualified ≥0.5% body-kernel mechanism survives today's closures. |
| Rank1 final norm/merge and target head prefix/argmax | Packet128b **0.051408 + 1.167601 ms** on hits; **0.051516 + 1.167535** on misses. Prefix bucket includes argmax | Must read the unchanged full partition and preserve reduction/ties. Prefix useful head weights alone: 647.168 MB, **1.205 ms at 537 GB/s** (1.166 at 555). Already faster than the first reference: it is not a hard hardware bound. Row moves/transpose/packed-head arms are closed. No new gain credited. |
| Rank0 head suffix, then rank1 merge | Packet128b suffix **0.293747/0.293993 ms**; merge pack compute **0.001577/0.001829** hit/miss. Full host merge/import/export is not separately measured | Suffix useful weights: 147.456 MB, **0.2746 ms at 537 GB/s**, plus required argmax/pack/transport. CPU `merge(local,best)` must preserve error and lowest-ID ties. Early suffix interleave lost; no new schedule gain credited. |
| Token handling **between head and draft** | Record D **1.609/1.608 ms** includes hidden copy, `Weights::read(token_embd)`, Q6 decode, BF16 upload, admission, submit gaps and publication. Their individual costs are **unmeasured**. Context-128 draft micro sum is **1.381717 ms** | The roughly 0.228 ms difference is a cross-run envelope diagnostic, **not measured embedding time**. D must consume the verified token and prior hidden state. Open: precompute the token-only draft embedding norm/project into a complete immutable table; remove **0.056823 ms** of draft kernels as a hypothesis, **+0.261% alone**. Do not credit the whole 0.228 ms. |
| Draft step, including head and argmax | Packet122 ctx128 processes **1.381613/1.381822 ms**; ctx4096 **1.933283/1.933439 ms**. Logits **0.445313 ms** at 128; argmax **0.020417/0.020521**. Packet128b in-engine diagnostic draft sum **1.405709/1.407263 ms** hit/miss | Packet122 useful-byte reference **0.902243 ms at 128 / 0.909799 at 4096**, at 555 GB/s; no hard compute floor. Logits alone reference 0.462297 ms is above observed 0.445313: bandwidth-only subtraction is invalid. Fixed prefix 80,128, format, placement and failed HC/load arms stay fixed. Static token-only precomputation is distinct from a new GEMV geometry or a shorter prefix. |
| Guess transfer, pending-draft wait and rank0-to-rank1 stream handover | Packet134 pre-speculation host gap **1.286492/1.305130 ms**, of which **1.275533/1.293395** overlaps the draft command. Explicit publication wait **0.007324/0.007827** is largely inside that gap. Record G is only 0.019700/0.013126 ms total | Wait floor is the actual dependency, not zero while drafting is pending. Guess/status uses the existing 8-byte pinned publication and host mailbox. Known copy event widths (~0.002 ms) omit unresolved copies and host synchronization. Even deleting all G is only about 0.1%; no transfer-only ≥0.5% lever supported. |
| Rank0 speculative capture | Packet128b capture compute **0.522394/0.523177 ms** each hit/miss cycle. Packet131 census **48,627,432 bytes**, not 1,021 launches: one descriptor upload plus one flat copy kernel | Full-copy read+write reference **0.181108 ms at 537 GB/s**. Bank rotation removes 29,601,792 bytes; retained 19,025,640 bytes have reference 0.070859 ms. Exact deletion of copies, not merely a faster copy micro, is candidate 1. Assumed net 0.20–0.30 ms plus exposed suffix path gives **+1.18–1.78%**; caveats below. |
| Rank0 token/history/lookup/decode/upload before speculative compute | **Record preparation 0.102435 ms**, correction 0.102197, all observed major-fault counts zero. Source reads one 2100-byte Q6 embedding row plus sixteen 90-byte IQ4 PLE rows and uploads 10,240 BF16 bytes. Packet134 instead sees 1.527433/1.406371 ms speculative preparation and 1.941660 correction | Subphase split and CPU/copy latency floor are unmeasured. Preallocate row/output buffers, block-decode without changing scalar rounding, preserve PLE history/IDs and batch only independent copies with a real terminal event. A **0.05 ms** cut is an engineering target, not a measurement: **+0.354% alone** if suffix fully follows. Even impossible zero preparation is only **+0.728%**. Combine with the draft token-only change for candidate 2. |
| Rank0 speculative target compute | Packet134 hit/miss busy unions **11.362531/11.357489 ms**, 564 kernels; internal compute gaps **0.084805/0.085040 ms**. All inside A, with the separate capture and preparation above | Body useful-byte reference as above, plus rank0 PLE; actual device/host residual split unavailable. Prepared arguments and pure-spin waits already exist. Command replay closed. At 20% transfer, erasing the entire diagnostic 0.085 ms internal gap would save only 0.017 ms per half before path weighting. |
| Suffix wait / verification / bookkeeping | Packet128b rank1 suffix wait **1.619550/1.468740 ms**. Packet134 rank0 command gap before accept/rollback **0.598090/0.602391 ms** includes service and verification. Record rank1 host profiling timer **0.435852 ms** and retirement 0.049702 per half | These overlap device/peer work; none may be added to B or treated as an empty delay. `Engine::drain()` still queries deferred draft events and enforces the 4-second submission budget. Batching checks is a distinct future mechanism, but exposed time is unmeasured: **0 to +0.586% for a hypothetical 0.10 ms exposed cut**. Not ranked above candidates with a concrete work-removal mechanism. Never delete safety checks or reintroduce packet92's losing report move. |
| Miss restore and full correction | Record R **0.546061 ms**, C **11.820039 ms**, running beside D. Packet128b restore compute 0.213588; packet134 restore-end→correction-begin gap **2.046383**, including 1.941660 host preparation and other boundaries; correction busy 11.355503 and internal gaps 0.085150 | R+C is serial on rank0; D is hidden there. No wrong-token target-layer reuse is exact. Restore's current 19.03 MB useful-copy reference 0.070859 ms is not its host duration. Packet121's small restore lever is closed. Candidate 1 does **not** claim a restore reduction; candidate 2 credits only its separately assumed 0.05 ms correction preparation cut. |

The packet128b rank0 hit groups are attention 4.945147, HC 1.995517,
MoE 3.885539, shared 0.354129, PLE 0.163118 and other 0.019081 ms. Rank1's are
attention 4.898069, HC 2.007932, MoE 3.856182, shared 0.352647 and other 0.007554.
On a miss the rank0 target groups contain **two** halves; rank1 contains one.
These totals and every original class row remain in the frozen budget. Rank1's
10.19 ms observed compute gap is also retained, but it includes peer/correction
dependencies and sample effects: it is not an additional serial cost or a
10 ms optimization opportunity.

The host lookup “decode” above means **dequantizing embedding weights**. It
does not mean text detokenization. This native path publishes token IDs; there
is no evidence here for a large tokenizer/string-decoding bottleneck.

## Today's transfer ratios and closed opportunities

For an ordinary kernel candidate, use **20% of the operator time saved** as
the provisional in-engine saving, then apply the dependency graph. For an
actual removed serial host operation or draft operation use 100% of its **net**
saving, still respecting overlap: D helps hits, not misses while R+C dominates.
Deleting work must include replacement lookups/uploads/drains; no 100% transfer
is promised merely because a proposal is called “host” or “snapshot.”

At the 58.22 anchor, +0.5% needs about **0.08545 ms/token**. A draft-only cut
therefore needs roughly 0.109 ms/hit; a correction-only cut about 0.397 ms/miss.
An ordinary kernel micro needs about 0.427 ms of *exposed* aggregate raw saving
before the 20% discount. These are screening scales, not new benchmark points.

| Evidence | Consequence for this ranking |
| --- | --- |
| Packet120 25/23 −3.9%; packet127 larger rank0 suffix −1.95%; packet130 interleave −1.61%, exact | Rank0 cannot absorb arbitrary additional work. No placement/row/interleave retry. Packet120/127 incomplete trailing controls remain disclosed; packet130 has the complete low-drift bracket. |
| Packet112 route 0.926/0.920×; packet116 QSA 0.936× at 128; packet117 HC 0.98×; packet115 best 0.995× | Approximate optimistic endpoint gains after 20% transfer are only **0.04%, 0.04%, 0.03%, 0.02%**, respectively, even allowing correction savings. These misses of their preregistered micro gates stay closed. |
| Packet119 down warming 1.079×; packet113 recurrence 1.50× | Negative. No speedup from the large byte-reference gaps alone. |
| Packet108 draft loads at best about 6 µs; packet122 HC whole draft 1382→1366 µs | At full draft transfer these are only roughly **0.03%/0.07%**, not 0.5%. No second geometry campaign. |
| Packet129 975→976 hits of 1230, +0.08 percentage points | With about 10.8 ms miss penalty, roughly **0.05%** throughput sensitivity; draft format is not the next lever. |
| Packet132 two-candidate best +2.25%, held-out +1.77%, gate +3% | Closed under its own cost/acceptance gate. Today's 0.5% screening request is not permission to lower that previous gate and revive it. |
| Packet126 early draft needs about 0.43 ms recoverable wait; packet134 overhead failed | Still unproven. Do not equate 1.62 ms instrumented suffix wait with safely recoverable ordinary-run draft time. |
| Packet131 removes 60.87% of capture bytes; device pending | Remains first candidate, not a measured winner. A naive byte-proportional 0.318 ms gain, discounted as a kernel micro at 20%, gives only **+0.372%** even with full exposure. The ≥0.5% hypothesis specifically requires real removal of serial copying, measured net in-engine. |

Packet110's old top three are not three new suggestions: gate/up tile16 lost,
packet109 fusion is already in bundle7, and packet112's selection mechanism
closed. The table's large above-byte-floor budgets cannot reopen them.

## Two bounded implementation sketches

These are **proposed runtime-switchable designs**, not claims that today's
sealed v5 accepts the switches. No implementation, build or queue proposal
was made in this analysis. Use a new copy, preserve the frozen parent, extend
the real selection/parser/reset/seal path and reject unqualified switches.

**1. Recurrent snapshot rotation, with a v5-compatible allocation union.**
Use packet131's exact A/B/C physical-bank ownership and full-overwrite proof
for GDN/conv destinations; retain full QSA-row and remaining scratch/state
capture. This is already prepared under packet131, so consume its pending
device evidence first; do not run a duplicate independent campaign.

For a future one-load bracket allocate the maximum control backup, descriptor
tables and extra 29,601,792-byte bank **before the first view**, keeping the
same pointers and allocation-descriptor hashes through all views. This costs
up to 29.60 MB beyond the current control, unlike packet131's separate-load
zero-net-allocation plan. Its rank0 census has 3.79 GiB arena headroom, but
actual host/device admission must be redone. Prebind every required physical
pair for both modes. At a quiescent switch, drain, clear every private/active/
old-spare bank and snapshot, reset parity and histories, then select
`snapshot=flat|rotate`. No weight allocation, arithmetic or target state may
change across a switch. Existing packet131 explicitly requires v4 reloads;
it must not be mislabeled as already v5-switchable.

Planning target: remove **0.20–0.30 ms net** from A, leaving 0.22–0.32 ms of
the diagnostic capture cost for remaining copies and synchronization. This is
an assumption below the 0.318 ms byte-proportional estimate, not an extrapolated
measurement. No R/C/D saving is credited. If the suffix follows A, the model
gives **58.91–59.26 tok/s (+1.18–1.78%)**. With 0.20 ms saved but only half
exposed, **+0.586%**; at zero exposure, **0%**. The 0.20 ms scenario needs
at least **42.72% exposure** to reach 0.5%. Require the endpoint to prove it;
a small copy micro alone is insufficient.

**2. Complete immutable draft-embedding projection plus bounded target
token preparation.** Treat these as two independently selectable subarms and
one preregistered combined candidate, so a combined win has an attribution.

The draft's `merge.embedding_norm` and `merge.embedding_projected` depend
only on an immutable embedding row and immutable draft weights, **not** hidden
state, position or prompt history. For all 248,320 vocabulary IDs, precompute
the exact BF16 result of those two existing operators. Keep the original
single-row chain, normalization tree, BF16 boundaries and exceptional-value
behavior; do not replace the calculation with a mathematically equivalent
matrix product or batch-shape-dependent GEMM. Generate a revision/kernel-bound
artifact, byte-check it against the original path, and make its hash part of
the selection. This is a full model-derived lookup table, never a suite-token
cache, learned draft or stored response. The verified target and fixed prefix
remain unchanged, and **draft proposals/acceptance must also remain identical**.

The table is **1,271,398,400 bytes** (248,320×2560×2). Rank1's current 0.732 GiB
arena margin cannot hold it on device. Keep it read-only on the host, admitted
and loaded identically in all bracket views; use a bounded pinned staging row
and upload 5120 bytes directly into the existing private
`merge.embedding_projected` buffer. That replaces the current 5120-byte raw
embedding upload, rather than adding a second transfer. Preserve raw norm/
embedding intermediate observability in diagnostics where required, and prove
all consumers in the production capture skip only those two sites. Error,
terminal/EOS and reset semantics stay unchanged. Complete-table construction
and device equality belong to a later authorized experiment, not this CPU task.

For rank0 keep its existing persistent mappings (`warm_lookups()` already
exists). Replace repeated temporary row/ID/vector allocations and per-element
quant-block setup with fixed-capacity buffers and exact block decoding;
pre-resolve immutable metadata/lookup launch descriptors. Combine independent
embedding/PLE uploads under one real terminal completion only after proving
all input-buffer lifetimes and unchanged ordered error handling. Preserve
signed PLE hash/remainder semantics, EOS history behavior and rollback of both
host history and device `token_history`. Do not call target `prepare_token()`
from the draft; that would advance PLE histories. Do not add the 29.32 GB
anonymous PLE table from one-card packet58t: this record already has mapped
lookups and no observed major faults.

Use `token_input=original|draft_table|target_buffers|both`, with all resources
allocated before the first control. Hold both source mappings and derived
table through every view; switches alter neither allocation descriptors nor
weights. Reset scratch and request state completely. No demand-filled table,
prompt-dependent row selection, extra process or background worker is needed.

Planning assumptions: remove **0.056823 ms from D** (the measured ctx128
two-kernel sum) and **0.05 ms from each A/C** (roughly half the measured target
preparation). Credit **zero** additional draft host saving, even though its
source read/decode is bypassed. Net table lookup/upload must fit inside the
old embedding read/decode/upload envelope; otherwise subtract its excess.
At full suffix exposure: **58.5833 tok/s, +0.617%**. At half exposure:
**+0.470%**; at none: **+0.324%**. It needs **60.13% exposure** to reach 0.5%.
The draft-only and target-only subarms project just 0.261% and 0.354%; do not
launch prolonged separate campaigns for either. If the small CPU buffer/decode
gate cannot halve preparation, or a low-overhead endpoint cannot establish
enough suffix exposure, close the combined ≥0.5% claim promptly.

For **both candidates**, the next experimental contract is:

1. GNU/Intel repeated raw-byte gates, unchanged weights/KV/verifier, full
   hit/miss/alternating/cancel/error/EOS/capacity-boundary state checks and
   every real startup/argument path. Test view switches after poisoned state;
   prove identical allocation identities and deterministic draft proposals.
2. A **12×64 exact smoke first**, including original→candidate→original reset
   behavior, cache-zero requests and graceful failure/drain. New low-overhead
   host stamps should bind snapshot/preparation, hidden-ready, prefix-ready,
   suffix-entry/reply and merge to request/position/sequence. No every-kernel
   timestamp queries in the speed arm.
3. Then one-load **C/X/C/X/C v5**, the full varied twelve-prompt screen in each
   view, no history/KV/response reuse, both X views ≥0.5% above the strongest
   control and all controls within 3%. Preregister gates before launching.
   Runtime switches, timing fields and seals need their own qualification.
4. A one-load screen is diagnostic, not two fresh servers. Only an improving
   candidate earns independent fresh-load repeats and the lane's full quality/
   performance promotion gates. Do not publish these projections or alter the
   existing record. All GPU steps remain coordinator-owned and unrun here.

## Practical ceiling and remaining uncertainty

For these local mechanisms, a plausible **planning band is roughly 59–60 tok/s**,
not a measured ceiling. The central two changes together give 59.2779
(+1.810%) under full suffix exposure. An optimistic local envelope removing
0.40 ms from A,0.10 from C and 0.10 from D gives 59.9698 (+2.999%). These are
explicit assumed cuts, not interpolated measurements. They are not additive
to the event-query scenario or packet132's closed study.

For perspective, the impossible operation of removing all 1.61 ms of drafting
while retaining target/restore costs and acceptance only reaches 62.8523
(+7.949%) in the exact per-prompt model. That is a fixed-target Amdahl scenario,
**not a hardware limit**. Better target kernels, a different proven dependency
graph, longer-context work or more concurrent users can change it.

If “≥0.5%” requires a data-established lower bound before any implementation,
**neither candidate currently satisfies that stronger requirement**: snapshot
net saving and ordinary suffix exposure are not measured, and token preparation
has not been split. The decision is to finish the already-pending snapshot
gate and make the token-path experiment earn its small threshold, rather than
claim certainty from the failed-overhead trace. Command replay, more rank0
placement, more head rows, draft-format variants and two-candidate retries do
not follow from this analysis.

## Reproduction and retention

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet135-critical-path/analyze.py --check </dev/null
```

The script installs a 4 GiB address-space cap only in its CPU entrypoint and
imports no runtime/device module. It evaluates only the pinned pure position-
join functions from packet85 as retained by packet126. It checks all frozen
member hashes, the record archive hash, twelve cache-zero successful requests,
the binary identity,1,188 interval identities, the exact class-balanced metric,
the failed 128b gate and both 40-sample draft runs/context. `--check` writes
nothing. This is analysis validation, not candidate byte or device testing.

`inputs.json.gz` deliberately exceeds 1 MiB (~1.52 MB): it retains original
bytes of the otherwise ignored/local record host timers, completed 128b budget,
two 122 micro iteration files, source snapshots, historical summaries and all
157 negative indexes. Hashes alone would not reproduce the key 0.102-ms versus
1.5-ms finding after build cleanup. The existing tracked record evidence bundle
is referenced by hash instead of copied. Decode a member's `raw_base64`, check
its SHA256, and read it in memory or restore it under a new scratch root; never
overwrite its original path. No source artifact was deleted or consolidated.
Peak RSS during the first complete reconstruction was 163,472 KiB; build bytes 0.

The pull refused pre-existing worktree changes; fetch confirmed main equaled
origin/main at entry. Other workers continued committing while this analysis
ran. Its frozen capture records the exact HEAD and input hashes. In particular,
packet128b's completed `BUDGET.md` was already dirty and is copied as evidence,
never edited or staged. `CURRENT.md` was concurrently dirty; this task changes
no live state and leaves it to its owner. Only this packet and its work note
are committed. [Work note](../../../../notes/2026-10-18-own-runtime-packet135.md).
