# Packet140 — target-body lever decision

October 18, 2026; CPU only. **Close this packet at the ranking gate. No new
mechanism has a defensible projection of at least +3% over 58.223834 tok/s.**
Do not implement, build or propose a device bracket on the strength of the
old roofline gap. This closes this bounded search, not the model lane.

The largest single-class *what-if* below is +0.495% at the provisional 20%
transfer assumption. Extending the same scale-sharing mechanism to every
possibly eligible class gives **+1.305%**. Assigning that whole-path hypothesis
80% transfer would give **+5.433%**, but it needs at least **45.22% transfer**
to clear +3%, unsupported by the analogous load-issue experiments. These are
sensitivity calculations, not measured gains, predictions with established
confidence, or a proof that a larger future mechanism cannot exist. An
arbitrary favorable transfer percentage is not a performance gate pass.

## Identity, timing authority and the bundle8 boundary

The requested baseline is the **quantized compressed Unsloth UD-IQ3_XXS** lane,
`iq3-p49-split32-v1`, full BF16 state/KV, unchanged target and verifier,
80,128-row draft prefix, 24/24 target layers. The actual record is packet124c
WS128 **58.2238342935355 tok/s**. Its 12 requests contain 1,188 first-99
inter-token intervals: 932 hits and 256 misses. The pooled mean and the
median-of-class-medians have different reciprocals; the calculator reproduces
the actual class-balanced metric before changing any cost.

Packet136's selected bundle8 adds `miss=banks-batch` to bundle7. It preserves
E1, down-tile16, route-fast, rec-both-plus, wide HC, packet109 fusion and split
head. Its source and [selection](../packet136-record-bundle/selection.json)
are frozen. **No matched per-class measurement of bundle8 is available in
these inputs.** Below, “current body proxy” means the packet128b instrumented
bundle7 implementation of those unchanged body kernels, not a new bundle8
measurement. Banking changes rollback/capture, not those kernels. Bundle8's
running chain and packet137/139 are not given speculative performance credit.

[Packet128b](../packet128b-attribution/BUDGET.md) measured 51.475451 tok/s,
0.888 of its 58.0 reference, and **failed the timing-overhead gate**. Its
66 sampled hit cycles give these rank1 compute sums per half:

| Current implementation, diagnostic proxy | ms/half |
| --- | ---: |
| Attention, including dense projections and recurrence | 4.898069 |
| HC gates, low projections and norms | 2.007932 |
| Routed experts, router tuple, route and final combine | 3.856182 |
| Shared-down fused epilogue | 0.352647 |
| Other target body | 0.007554 |
| Total, excluding final head/norm, draft and rollback | **11.122384** |

Rank0's corresponding body is 11.180332 ms before its additional 0.163118 ms
PLE and 0.019081 ms other work. It is not added to rank1's half: these halves
overlap. On misses rank0 executes correction as well as the next speculation.
The record's correction envelope is **11.820039 ms**; correction occurs in
256/1188 = 21.55% of these intervals.

[Packet134](../packet134-submission-stalls/README.md) finds only 0.084805 ms
of internal rank0 compute gaps on hits. Its 1.594 ms before kernels start is
mostly preparation, not an enqueue bubble. Record token preparation is about
0.102 ms, not that instrumented gap. Neither the 10.19 ms rank1 observed idle
nor host waits can be added to body compute or claimed as removable time.

[Packet110](../packet110-class-roofline/ROOFLINE.md) is **pre-packet109 fusion
and pre-down-tile16**, representative layers at context 128 scaled by 18 GDN
plus 6 QSA. Its 5.407656 ms useful-byte reference at 537 GB/s is neither a
measured half nor an attainable hardware floor. Its old headroom allowances:
gate/up 0.9589 ms, down 0.8048, HC gate/low about 0.913 plus norms 0.401,
route 0.4497,
recurrence 0.3247. The roughly 1 ms collection of small-kernel gaps overlaps
other groups and contains work already removed by packet109. Do not subtract
5.41 from 11.12 and call the difference achievable savings.

## Projection and transfer requirement

For every original interval the calculator first reconstructs:

```text
T = max(D, R + C) + max(B, A + offset) + G
```

For a net body saving `s` on each affected half, it replaces A, B and C with
`max(0, value-s)`; D, R, G and acceptance remain unchanged. This gives the
candidate full exposure on the overlapping target path and an extra saving
on correction when R+C still dominates D. B includes suffix wait: its own body
saving and the equally earlier suffix dependency are **one** saving, not two.
This optimistic dependency assumption is stated, not inferred from B−A.

The calculator recomputes each prompt's rate, each class median, then the
median across classes. Exactly +3% requires **0.412758 ms net per half**:

| Transfer assumption | Required raw operator saving per half |
| --- | ---: |
| 20%, ordinary unproven kernel mechanism | **2.063788 ms** |
| 80%, favorable down-tile16-like sensitivity | **0.515947 ms** |

The approximate quick check is `s × (1 + 256/1188)` against a roughly 17.2 ms
interval. The committed calculation uses all original intervals instead.

Observed transfer is not universal. Down-tile16's **0.695×** kernel became
**+2.09% / +1.68%** in-engine, supporting the brief's roughly 80% favorable
case. In contrast, gate/up tile16's **0.893×** became essentially zero on B
and a loss on A. Packet81 cut static loads 51→27 and 79→31 but measured
+0.07/+0.13/−0.10%. Packet109 is already banked. See the retained
[104 result](../../../../notes/2026-10-18-own-runtime-packet104-micro-result.md)
and [81 negative index](../packet81-experts3/DO-NOT-REPEAT.md).
**Use 20% for an unproven arithmetic/issue change; show 80% as sensitivity,
never award it merely to clear the gate.** There is no measured positive lower
bound for the new proposals; a regression remains possible.

## Ranked table

The rows partition the 11.122384 ms body proxy exactly. Times in this table
are **post-fusion diagnostic in-engine costs**, unlike packet110's gaps.
Rank is by an explicitly assumed raw reduction, then 20% transfer and full
path exposure. The assumptions are deliberately visible: 10% for dense
attention, 50% for HC norms, 20% for other groups. They are screening
what-ifs, **not observed speedups**. N1–N3 are distinct proposed designs below;
“none” means no new exact mechanism justified by this audit. For those rows
the calculation is only a budget sensitivity, not a candidate forecast.

| Rank | Class; current proxy ms/half | Exact boundary | Prior attempts to exclude | New mechanism or reason none qualifies | Assumed raw cut | Projected gain, 20% / 80% transfer |
| ---: | --- | --- | --- | --- | ---: | ---: |
| 1 | Dense attention output, GDN QKV/Z, QSA Q-gate; **3.487164** | Original per-lane products, split32 and split4 trees, BF16 outputs/attention combine | p28/p33, p67, p72, p74, p104, p107 | **N1:** multicast identical scale bits within each row, with unchanged chains. Removes redundant issues, no distinct weight bytes; cannot justify the 59.18% raw cut needed at 20% transfer | 10% = 0.348716 ms | **+0.495% / +2.008%** |
| 2 | IQ2 gate/up; **1.442975** | Ten selected experts; independent gate/up metadata; 32 logical chains; original adjacent tree; both BF16 outputs/status | p25/28, p52/53/53b, p61 inherited kernels, p65/73/81, p86, p90 E1 already present/H1 closed, p95, p99, p102, p104/104b, p115, p119 | **N2:** 40-bit integer metadata cell, same 840-byte E1 row; preserve original arithmetic. Needs 35.76% raw cut even at 80% transfer; no evidence for it | 20% = 0.288595 ms | **+0.409% / +1.656%** |
| 3 | HC a/f gate + mix; **1.060592** | 320→10,240 gate outputs, original SG32 trees; BF16 gate before sigmoid; four-term ordered mix | p60/61 accepted, p53b/67/73, p90 H1, p94, p104, p117 | **N1-Q8:** same-bit scale multicast within existing row groups, not new four-stream geometry or sigmoid ordering | 20% = 0.212118 ms | **+0.300% / +1.212%** |
| 4 | HC a/f norm; **0.381008** | BF16 stream reload, 80 aligned 32-leaf subtrees padded to 128, original upper tree, rsqrt/division and output rounding | p46 four-WG norm, p60/61 accepted, p78, p94, p107 | **N3:** producer emits original RMS leaf partials after BF16 rounding; next norm consumes them. Applies only across an unchanged stream version; replacement overhead not measured | 50% = 0.190504 ms | **+0.270% / +1.087%** |
| 5 | IQ4 down, already tile16; **0.939947** | K640 tails, V16 logical chains/adjacent tree, BF16 per-expert output, route/status behavior | p33 bank/select, p65/73/81, p99 bytepair, p100 accepted tile16, p104, p115, p119 | None: Boolean/select decoder is p33; bytepair is p99/115; further warming is p119. No new measured locality defect | 20% sensitivity | **+0.266% / +1.073%** |
| 6 | Remaining small sites; **0.700492** | Expsact and combine BF16 boundaries; convolution history order; gated norm tree; QSA pool/prepare state and invalidation | p21/39/46, p60/61, p78, p94, p107, p109 | N3 can attach partial writes to a producer, but does not eliminate its own operation. No separate credited saving. Generic fusion and expert-act absorption are closed | 20% sensitivity | **+0.198% / +0.797%** |
| 7 | HC a/f low + inject; **0.566332** | K10240 split4 of split32 chains; BF16 low and inject; unchanged activation | p53b/60/61/67/73, p94, p104 | N1 where scale ownership is shared; F32 inject cannot use Q8 scale sharing. Whole-group budget deliberately overstates eligible work | 20% sensitivity | **+0.160% / +0.644%** |
| 8 | Route, including fused shared activation; **0.542529** | Original max/exp/denominator tree, rounded probabilities, lower-ID ties, invalid-input refusal before writes | p33 all-pairs, p78 accepted, p73 deferred fusion, p109 already fused, p112 pruned network | None: logit ranking is inexact; pruned normalized top10 is p112; router-to-route fusion crosses workgroups | 20% sensitivity | **+0.153% / +0.616%** |
| 9 | Router/shared gate/up tuple; **0.527066** | Independent dense rows, original chains and rounded tuple outputs | p27/49d accepted, p73/74, p104, p109 | N1 on Q6 row peers only; no merging independent scales or duplication of the tuple to fuse route | 20% sensitivity | **+0.149% / +0.599%** |
| 10 | GDN recurrence; **0.449462** | Original four ordered products and adjacent 32-leaf tree; BF16 state store/reload, token barriers and rollback | p67 head prepass, p82/82b accepted, p107 nonfinite failure, p113 row schedule | None: independent-row ownership exists already; extra head preparation/prepass repeats closed work | 20% sensitivity | **+0.127% / +0.510%** |
| 11 | QSA attention + select; **0.358128** | Original score/numerator trees, selected-ID ties, BF16 cache, breadth-tree NaN payloads | p44/p49 accepted, p107, p116 | None: more scoring groups or tree storage changes are p116; chronological key/value math cannot be reassociated | 20% sensitivity | **+0.101% / +0.406%** |
| 12 | Shared down + mixture/blend; **0.352647** | K640 Q8 dot, BF16 down, ten ordered expert slots, BF16 mixture/blend and compiler-specific NaNs | p39, p104 shared-down 2.095×, p109 already fused | N1 on existing Q8 row only. Another down/mixture/blend fusion is already present; HC combine needs its rounded output | 20% sensitivity | **+0.100% / +0.400%** |
| 13 | Small GDN a/b and QSA K/V/IQ/IK; **0.314042** | Original independent projections, split boundaries and finishes; BF16 results | p27/28/30/33, p72/74, p107 | N1 only on compatible quantized scale groups; no benefit credited to F32 paths or a new combined projection | 20% sensitivity | **+0.089% / +0.356%** |

The “remaining small” row is expsact 0.134217, ffn.combine 0.269449,
GDN conv 0.136411, gated 0.100754, QSA prepare 0.030818, pool 0.021290,
other 0.007554. HC norms and route are in their own rows, avoiding the usual
double count of the “~1 ms small kernels” budget. PLE is rank0-only and not
in this rank1 table; even deleting its diagnostic 0.163118 ms at 20% transfer
would be far below +3%, before accounting for suffix exposure.

## Three distinct designs, and why none is admitted

**N1 — same-bit scale multicast.** In `p33::dense_lane`, each lane owns eight
consecutive weights; adjacent pairs (Q6 groups of 16) or quads (Q8 groups of
32) load identical FP32 scale bits. One owner can load a `uint32_t` and use a
subgroup integer broadcast within that *same row*. Every lane still converts
the same bits, multiplies each signed code and BF16 input separately, and adds
in the same order. A predicate must cover incomplete ranges without reading
another row or consuming an inactive source lane. This is not packed-activation
loads, a dense-weight transpose, or changing virtual chains. It saves load
issues, **zero unique scale bytes**, and adds shuffle/predicate instructions.
The memory system may already combine the duplicate reads. Packet81 is direct
evidence against inferring speed from fewer static loads. The 10% large-dense
scenario already assumes a useful net win; 20% transfer gives only +0.495%.
The calculator also applies N1 to **all six possibly eligible groups together**
(dense attention, HC gate/low, router tuple, shared fused, small dense), rather
than artificially splitting one mechanism below the gate. Assuming every
site is eligible and achieves its stated cut gives 0.912852 ms raw saving,
**+1.305% at 20% transfer**, or **+5.433% at 80%**. The latter is a tempting
but unsupported qualifying scenario: transfer must exceed **45.22%**. It
also credits F32 and fused tails within whole-group timings where multicast
does not apply. Packet81's nearly halved static load counts with neutral
engine results, and packet104b's reversed transfer, do not support that
admission assumption. No counter evidence shows a redundant-scale issue
stall here. Reopen with such evidence and a net whole-path cost, not by
assigning down-tile16's transfer to an instruction-only change.

**N2 — five-byte IQ2 metadata cells.** Per sixteen weights, the original
metadata has two 8-bit grid codes, two 8-bit sign masks, two 2-bit high fields
and one 4-bit scale: **40 bits**. Encode these as
`index0[10], sign0[8], index1[10], sign1[8], scale[4]`. Sixteen such cells per
256-weight block consume 80 bytes; ten blocks plus ten cached FP32 half scales
remain **840 bytes**, exactly E1's current row. This is an invertible integer
permutation, not a larger effective-scale cache, relocated IQ2 lookup table,
tile16 transpose, cross-row scale sharing or another prefetch bank. It removes
separate high/scale-plane address construction. Decoding keeps the unchanged
IQ2 grid words, exceptional expression, products and split32 accumulation.
Five-byte cells lose easy aligned vector loads; two-word extraction and added
shifts may cost more than they save. No overread at a row tail is allowed.
The source gives no basis for the required 35.76% raw cut with 80% transfer,
let alone 143.03% with 20%. The hypothetical 20% cut yields +0.409% / +1.656%.
Do not revive E2 by expanding cells to effective float scales: rank1 has only
786,269,478 bytes under its arena limit in the pinned bundle8 plan.

**N3 — produce the norm's existing leaves.** A compatible stream-writing
combine epilogue could store the original BF16 output, widen that exact
rounded value, square it and emit each original aligned 32-leaf RMS partial.
The following norm retains the identical padded upper tree and output math,
but need not recompute the same leaves ten times. This differs from p94's
duplicated normalization in every consumer and p46's four-workgroup serial
upper tree. It needs a real mapping of each complete subtree to one producer
workgroup, dependency publication to the norm, unchanged intermediate bytes,
and stream-version invalidation wherever PLE or another operation intervenes.
If that mapping needs a new kernel or barrier, count it; no cross-workgroup
barrier is assumed. Full two-site eligibility is an optimistic ceiling:
even impossible zero-cost deletion of **all** HC norms at 80% transfer cannot
save the required 0.515947 ms raw (the entire class is 0.381008 ms).

For all three, “exact” describes the proposed unchanged arithmetic contract,
**not a passed implementation**. GNU and Intel must each compare complete
outputs/scratch/status against their own frozen production with real shapes,
tails, all scale encodings, NaNs/payloads, infinities, signed zeros and ties.
Existing p48 rejection of nonfinite weight scales remains a refusal-before-write
contract, not permission to canonicalize them. Compiler call-site changes can
alter NaN payloads even without algebraic changes. Device exactness, acceptance,
fresh-process determinism and unchanged verifier remain separate gates.

## Complete prior-attempt audit

The capture searched **all 164 repository DO-NOT-REPEAT files**, including
other model lanes, plus the complete current `ops/screen-cleanup/closed.json`.
[prior-search.txt](prior-search.txt) retains filename/line matches;
[analysis.json](analysis.json) retains per-file hashes and matched rows;
[inputs.json.gz](inputs.json.gz) retains **every original byte of every index**
and the closed ledger, so nonmatching lines and stale “pending” language remain
reviewable. The ledger and later result notes override old pending prose.
No index or closed-ledger entry was edited. This is the concise body-relevant
inventory; the complete audit is not limited to these packet numbers:

| Packets | Disposition carried forward |
| --- | --- |
| 21, 39, 46 | Generic/interpreted fusion; serial/global producer-consumer fusion; expert activation predicate spills; QKV/conv added scheduling cost; PLE tail too small. No legal grid barrier supplied by renaming a fusion. |
| 25, 28, 33, 48, 49 | Scale hoisting and packed decode are existing work. IQ4 balanced select branched/regressed; static ISA count did not predict held-out speed; compact repack rejects nonfinite weight scales; arithmetic and strides are binding. |
| 52, 53, 53b | Free-order arithmetic excluded; persistent/SLM losses; V16 gate/up ~52 µs slower; HC virtualization slower, spill/NaN failures retained. |
| **60/61/61x** | Exact three-kernel HC fusion and pure-spin are already accepted; neither is a new body lever. Do not alter frozen source/object identities. |
| 65, 67, 72, 73 | Ten-expert batching already production; raw lookahead insufficient; HC four-stream/rec-head −6% to −22%; QKV/Z/Qgate geometry too little headroom; HC and full-span IQ4 spill failures. |
| 74, 78, 81, 82/82b | Packed-dense and packed-input sweeps closed; raw-logit ranking inexact; route-fast and rec-both-plus already included; rec-both alias is not a new change. |
| **86** | Non-exact limiter diagnostics only; preserve reads/loadkeep controls; no additive ablation savings or invented cache/DRAM attribution. |
| 90, **94** | E1 accepted; H1 HC cache closed. Norm-consumer fusion **−23%** on B. |
| **95** | E2 does not fit; subset lacks measured layer value. E3 grid-word pipeline closed despite exact/zero-spill final code; earlier 15,488/1,152-byte spill variants retained; E5 revisited by 102/115. |
| **99** | Table relocation/compaction **1.24–1.78× slower**; IQ4 bytepair 1,664-byte spills; no separate IQ2 sign table to optimize. |
| 100, **102** | Down-tile16 is accepted, not new headroom. Batch2 −1.89% kernel time (below gate); batch4 +0.16%; shared input +3.31%; combined V4/V8 spill failures. |
| **104/104b** | All original arms miss 0.85× gate. Gate/up 0.898/0.893× allowed one exception, then no B/A engine gain. Shared Q6 0.951; HC 1.007; router 1.026; draft gate/down 1.262/1.347; shared gate/up 1.496; shared down 2.095. Closed. |
| 107, **109** | QSA specialization slower; GDN shared-head preparation changes Intel NaN payload. Exact shared activation/down/mixture/blend fusion already adopted; four rejected NaN/call-site forms retained. |
| **112** | Pruned normalized top10 network 0.926/0.920×, fails 0.5× gate; 2,048 exact cases include 512 nonfinite. No logit-ranking shortcut. |
| **113** | Row recurrence 1.50×, fails 0.6×; exact cases do not confer a speed pass. |
| **115** | Large GRF production 1.44×; E3 1.70×; E5 1.50×; V4 batch2 1.38×; best bytepair 0.995×, fails 0.85×. |
| **116** | Attention/select 0.936× at 128 and 0.944× at 4096; fails 0.6×; depth-first/fixed-array tree rewrites changed NaN payloads. |
| **117** | Earlier sigmoid/products 0.98×, fails 0.70×; unconditional products changed mixed-NaN payloads. |
| **119** | Down warming during gate/up **1.079× slower**, fails 0.85×. Cache-capacity labels are not effective-capacity evidence. |
| 120/123/127/130, 134 | Placement/head-row/interleave regressions; no unmeasured rank0 slack; internal compute gaps only 0.085 ms; submission rewrite closed. |
| 121/122/126/129/132/135 | Miss restore and draft micro changes too small; early draft wait unproved; acceptance +0.08 points; second candidate +2.25%/+1.77% below its +3% gate. Snapshot/token work is already owned by 131b/136/137/139. |

## Decision and reproducibility

**No lever selected.** The table, source-level sketches and replayable
projection are the deliverable authorized by step 1. Steps 2–3 are conditional
on a qualifying lever and do not run: there is no copied runtime, compiler
turn, GNU/Intel implementation gate, device admission, smoke/v5 proposal, or
`READY-FOR-DEVICE.json`. A readiness marker here would falsely advertise work
that did not pass the selection gate. No queue, service, GPU or frozen packet
was touched.

Recompute offline, using only retained small receipts:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet140-body-lever/analyze.py --check </dev/null
```

The analysis-only main process caps address space at 4,000,000,000 bytes;
no imported module changes limits. Initial capture used about 116 MiB peak RSS.
There is no build. Reopen with a **distinct exact mechanism** and evidence
supporting at least 0.412758 ms net body saving on the matched path, or a
new matched ordinary-run attribution that changes this projection. A fresh
roofline subtraction, renamed closed arm or favorable transfer assumption
alone is not that evidence.
