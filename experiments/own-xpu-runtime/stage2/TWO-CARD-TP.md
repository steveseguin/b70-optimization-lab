# Two-card decode with an ordered exchange — Stage 2 design packet

October 11, 2026. **Design, CPU tests and compilation only. No device run.**
Target: the separate Unsloth Flash-Next UD-IQ3_XXS quantized compressed version,
revision `766911a6b7369840a91dbcd95f9f997acaab6cd6`, on two B70s. No weights,
KV precision, routing choices or model arithmetic are silently changed.
[Packet 12](packet12-peer/README.md) prepares the transport measurement on
physical cards 2 and 3. Its commands require a separately admitted window.

## Decision and important corrections

Use a single process, a shared Level Zero context, one ordered queue per card,
owned device buffers and explicit completion events. Query
`zeDeviceCanAccessPeer(A,B)` and `(B,A)` before allocating. If both succeed and
report access, measure peer-enabled copies without application host staging;
otherwise use an explicitly owned pinned host slab, D2H then H2D. A query or
copy error stops the attempt; it does not trigger an automatic fallback/retry.
Keep the bounce control even when peer access is available. Select the eventual
transport from exactness and wall timings, not capability flags alone.

The [census](../../qwen38-flash-next-ud-iq3xxs-b70/packet1/README.md) establishes
**hidden 2560, 512 experts, top 10, intermediate 640, 48 total layers = 36 GDN
+ 12 QSA**. There is no MTP block in these files. The requested 48 GDN + 12 QSA
and 60 exchanges remain explicitly hypothetical/stress workloads. A hidden
FP32 vector is **10,240 bytes = 10 KiB = 10.24 decimal KB**. It is not the entire
layer state: four HC streams are `[4,2560]`, 20,480 BF16 or 40,960 FP32 bytes.

Two requested shortcuts cannot yet satisfy the lossless requirement:

- One 10 KiB exchange at the *end* of a layer cannot supply its earlier
  attention-output dependency to the second HC mix, router and experts.
  With both sublayers split, at least two synchronization phases per layer
  are needed, plus any activation gathers/control agreement. One exchange
  per layer is an optimistic cost model, not a valid execution graph.
- A fixed FP32 `A_partial + B_partial` is deterministic but not automatically
  identical to the unchanged single-card dot or ten-slot expert sum. Mirroring
  a changed tree in a CPU oracle proves the new tree, not the old outputs.
  [CPU tests](packet12-peer/host_tests.cpp) retain a cancellation counterexample.

The implementation ladder therefore keeps both candidate arithmetic and frozen
single-card checks. A failing split is retained as a negative; changing the
oracle does not turn it into a lossless result.

## Placement within every layer

Matrices below use `W[out,in]`, the reverse of GGUF's fastest-first dimensions.
Both cards receive the same rounded input and token/position/active/error
controls. Neither computes the next layer before exchange completion.

| Component | Card A / card B work | Synchronization and exactness contract |
| --- | --- | --- |
| Q/K/V, GDN input/gate projections | Split output rows by complete heads; retain each output row's entire K reduction | GDN: 24 value heads/card and associated keys/conv/state; key replication where grouping requires it. QSA: 12 Q heads and one KV head/card, with index/compression dependencies explicitly mapped. Preserve head group membership and state casts. |
| Attention output projection, `2560 × 6144` | Conventional TP splits input columns, producing two H-wide FP32 partials | Gather/combine before HC residual and the MoE input. Ordinary contiguous K halves change arithmetic; see tree-preserving alternative below. Output-row splitting instead requires the full concatenated attention activation first. |
| Shared expert gate/up, `640 × 2560`, then down `2560 × 640` | Gate/up output rows split 320/320; conventional down input columns 320/320 | Preserve SiLU/product/BF16 boundaries. Down sum has the same reduction-order gate as attention output. No early BF16 partial rounding. |
| Routed experts | A owns expert IDs 0–255; B owns 256–511, each complete gate/up/down triplet | Each rank runs all its selected slots in original route order. Do not choose five convenient experts or route by rank. Two local sums cannot generally replace the original ten-slot accumulation. |
| Router and small controls | Replicate router weights and identical math; stable top-10 with declared tie order | Exact agreement of ten IDs and ten FP32 normalized weights before any expert read; abort/poison on mismatch, never average route probabilities. |
| Hyperconnections | Initially replicate HC matrices and four streams; execute unchanged norms/mix on each rank | Adds traffic/capacity; not half the bytes. Preserve BF16 stores and both HC residual boundaries. A later row split needs its own gathers and reduction proof. |
| Output head | Split 248,320 vocabulary rows 124,160/card, full K per row | Each row retains its dot order; exchange local best `(FP32 logit, I32 token)` and select global maximum with lowest token ID on ties. Nonfinite and inactive policies unchanged. |
| PLE/embedding | Retain packet3's host-backed lookup plan and exact layer-1 injection | Host mapping/latency are unresolved. The 3,540-byte lookup floor is not an observed host lookup cost. |

State is head-sharded where dependency coverage permits; no remote recurrence
polling. Replicate index/control pieces only after a byte census. Keep full
BF16/FP16 KV and the lane's BF16 inter-row GDN state, with transaction rollback
and error propagation on both cards. Never duplicate a full KV cache merely
because the activation is replicated. Packet3's sequential 24/24 layer placement
remains the fallback/control; this packet does not replace its launch plan.

Expert ID placement balances **stored weights**, not selected bytes per token.
All ten selected experts can belong to one card. Under an explicitly hypothetical
independent uniform routing model, `E[max(hitsA,hitsB)] = 6.23047`, not five;
the expert-only ideal speedup is then about 1.605× before copies. Real routing
histograms, mixed grids and arrival skew must replace that model. Both cards
have work in each layer, but neither perfect simultaneity nor half the active
bytes is guaranteed.

## Determinism and what is actually exchanged

The proposed primitive is **B partial → A; A computes FP32 A+B; result A → B**.
A is always the left operand, B the right. Round to BF16 only at the original
operator's output boundary; do not round partials. Disable contraction, fast
math and FTZ. Finite values, signed zero, ties, cancellation and nonfinite
error handling belong in the gate. Both ranks then consume the same result
bytes; no floating atomics, unordered reduction or peer spin kernel is used.
The CPU reference explicitly calls the same two-term operation.

For one H-wide reduction that is 20,480 delivered bytes/round trip; host bounce
moves **40,960 link bytes** (two legs each way). Top-10 metadata requires at
least `10 × (4-byte ID + 4-byte weight) = 80 B`, with a position/step tag and
sticky status beyond that. Native packet3 Route descriptors contain three U32
fields (120 B/ten), and are not the same as just IDs/probabilities. Replicated
routing still needs agreement: a future device comparison exchanges the
ordered raw 80 bytes and produces a sticky error before launching experts.
A hash alone is insufficient for the exact gate. Packet12 times the vector
primitive, **not routing, HC exchange or this agreement check**.

There are two paths to preserving the frozen arithmetic:

1. **Output-row split plus ordered gather.** Each card computes whole rows
   with unchanged K order, then copies the missing rows by index. Concatenation
   makes no arithmetic change. For expert parallelism, retain each expert's
   rounded BF16 down result separately. Gather remote slots to A and accumulate
   slots 0…9 exactly as packet3, then add the shared expert at its original
   cast boundary and broadcast. Five remote slots cost 25,600 B as BF16, ten
   cost 51,200 B, plus the returned result; not one two-term reduction. This
   is the initial exactness candidate despite more communication.
2. **Partition an existing reduction tree, never invent a new one.** Packet2's
   `lane_dot` visits `lane, lane+32, …` in increasing order; `tree32` merges
   adjacent leaves. A can compute unchanged logical lanes 0–15 and their
   subtree, B lanes 16–31 and theirs, then perform the original final A+B.
   This is a strided column partition, **not contiguous K/2**. Packed block
   scales/codewords span both partitions, so the present layout may force
   duplicate block reads. An invertible storage repack or finer decode map
   needs its own byte/fit/reconstruction proof before claiming half the traffic.
   Packet9 split4 has a different tree and must be treated separately. Expert
   slot-order accumulation is serial, not this tree: expert-ID partition still
   needs slot gathering or transport of the running accumulator in slot order.

The logical layer sequence is replicated HC input → sharded attention/GDN →
attention combine/gather → replicated HC residual and next mix → router
agreement → local expert work → ordered expert gather/sum and shared addition
→ replicated HC residual. Fusing communications across these nonlinear/cast
dependencies would change the function. Packet12's 60-round loop validates
transport ordering only; it cannot qualify this complete layer sequence.

## Cost budget using local evidence

[Packet5](packet5-h2d/README.md#first-measurement--card-3-2026-10-11-033x-utc-boot-13858eef)
measured roughly 28 GB/s pinned H2D for 2–20 MB and 270–540 GB/s for **same-card**
D2D at larger sizes. Neither establishes inter-card bandwidth or 10 KiB latency.
Its millisecond host polling inflated small-copy wall time. Packet12 uses
bounded yielding completion polls and records full wall latency as well as
nullable per-event times; CPU scheduling overhead remains part of wall cost.

At an **assumed** 28 GB/s in each host direction, the payload-only bounce floor
is `4 × 10,240 / 28e9 = 1.463 µs` per round, or **0.0878 ms for 60**. This excludes
four submission/completion latencies, the combine, host contention and arrival
skew, and extrapolates a large-transfer rate; it is not a latency prediction.
At the same assumed peer rate, two copies would cost 0.731 µs in payload time.
Do not substitute the local 270–540 GB/s for either PCIe route.

Let `E_peer = L_BA + B/R_BA + C_add + L_AB + B/R_AB`, where L includes exposed
submit/event/completion overhead and arrival skew. Host bounce replaces each
copy with dependent D2H + H2D. Then `T_exchange = N × E`, with **N=60** for
the requested diagnostic, **48** for the optimistic one-per-real-layer case,
and **at least 96** for two dependent phases per real layer before extra gathers.
Cross-card timestamp origins must never be subtracted. End-to-end wall time
decides the cost; sums of local event durations omit gaps.

Historical evidence supplies risk bounds and experiment choices, not calibration:

- [MiniMax IPC](../../minimax_qk_rms_xpu_ipc/README.md) reported peer ACCESS
  without remote ATOMICS, **417 ms** polling versus **0.061791 ms** XCCL for
  FP32 `[1,2]`. This is a different four-card scalar workload and old driver.
  It rules out reviving the polling method, not today's peer copy mechanism.
- [A340/A341](../../qwen38-flash-next-fp8-b70/notes/2026-09-11-a340-a341-the-moe-allreduce-term-is-gone-on-the-promoted-line.md)
  found the apparent ~40 ms MoE collective term disappeared with paging
  pressure; skipping the 48 collectives bounded their mechanical cost near
  0.7 ms on that FP8 line. Do not solve a memory-placement problem with a
  collective rewrite or borrow that rate for IQ3.
- [A378/A379](../../qwen38-flash-next-fp8-b70/notes/2026-09-13-a378-a379-row-wise-selector-cost-result.md)
  saved 1.47 ms by disabling row-wise collectives **and changed answers**.
  Deterministic repeats are insufficient without frozen-output parity.

For planning, **61.8 µs/complete exchange** is an explicitly unmeasured
scenario near the unrelated XCCL observation, not a predicted property of
our peer or bounce paths. It gives **3.708 ms/60 exchanges** and **5.933 ms/96**.
Use 20 and 200 µs sensitivity arms: 1.2–12.0 ms/60, 1.92–19.2 ms/96.
Replace these assumptions with packet12's measured 60-round wall distribution.

## Packet9-based throughput projection, never a headline

The [raw packet9 receipt](packet9-kopt4/receipts-card3-20261011/timing.json),
`experts_split4` checkpoint row, supplies the following representative timings.
Its tree is not thereby qualified against the whole-model oracle.

| GEMV subsequence | Count | Sequential ms each | Optimistic half-time ms each |
| --- | ---: | ---: | ---: |
| Ordinary GDN | 34 | 1.1427345 | 0.5713673 |
| PLE GDN | 1 | 1.467448 | 0.733724 |
| Upgraded GDN | 1 | 1.251875 | 0.6259375 |
| QSA | 12 | 1.11541625 | 0.5577081 |
| Head + final HC | 1 | 5.4658855 | 2.7329428 |

Include packet9's optimistic 0.000006 ms embedding floor: the sum is
**60.42318 ms = 16.54994 tok/s**, sequential layer split with one card active
at a time. The halved compute sum is **30.21159 ms**, an optimistic ceiling
scenario only. The head is actually **521,472,000 packed Q6_K bytes** in the
census; packet9 README's “1.27 GB head” is not used to infer bandwidth here.
No model decode or prefill rate was measured in this packet.

Traffic replication alone prevents a simple 2× claim: packet3 counts
4.95124 GB sequential versus 5.62667 GB across tensor-split cards with an extra
HC copy. Even perfect balance gives `2 × 4.95124 / 5.62667 = 1.7599×` payload
benefit. That is a separate bandwidth accounting bound, not a multiplier for
packet9's decode/launch-bound kernels. Duplicated packed blocks, head imbalance,
HC replication, launch cost and exact expert gathers reduce the benefit further.

For a less optimistic **sensitivity**, assume only 80% of GEMV time can halve:
`T_compute = 60.42318 × (0.2 + 0.8/2) = 36.25391 ms`. The 80% is an assumption,
not a measured profile. With the 61.8 µs exchange budget:

| Scenario | Exchange ms | Ideal-half projection | 80%-parallel projection | Gain over 16.55 in 80% scenario |
| --- | ---: | ---: | ---: | ---: |
| 48 rounds, optimistic one/layer | 2.9664 | 30.14 tok/s | 25.50 tok/s | 1.54× |
| Requested 60-round stress budget | 3.7080 | 29.48 tok/s | **25.02 tok/s** | 1.51× |
| 96 rounds, two/real layer before extra work | 5.9328 | 27.67 tok/s | **23.70 tok/s** | 1.43× |

These still exclude nonlinear/state/KV work, route agreement, larger exact
gathers, lookup latency and native fit effects. They are **conditional GEMV plus
exchange projections**, not promised full-model speed or measured performance
curves. A literal 60-layer model instead starts from packet9's 74.136 ms
hypothetical baseline; never attach its layer count to the 60.423 ms checkpoint.
The 28.49 tok/s reference remains faster than the 80% scenarios. Two cards alone
do not remove the need for kernel improvements. [project.py](packet12-peer/project.py)
and [projection.json](packet12-peer/projection.json) retain the receipt hash,
formula, assumptions and sensitivity rows.

## Packet ladder and go/no-go gates

1. **P12 transport:** compile and CPU mock checks now; later one admitted
   cards-2/3 window for bidirectional sizes and 60 dependent rounds, exact
   changed payloads, clean owner teardown and fault-latched receipts. Then a
   separately admitted fresh-owner repeat before any speed verdict. No retry
   loop and no server. Record UUIDs, driver, source/binary hashes and actual route.
2. **Dense split arithmetic census:** compare output-row gather and the
   tree-preserving column split across every packet9 dispatch shape, grid,
   BF16/F16 input and tail. Check FP32 accumulators and rounded outputs against
   unchanged single-card and independently evaluated CPU references. Include
   adversarial cancellation/ties and two fresh processes. Contiguous K halves
   fail closed if any bit changes; retain the failed arm. Measure repack bytes.
3. **Expert split and routing:** CPU/device top-10 ID/probability agreement,
   exact whole-expert results and slot-ordered gather/sum; all-on-A/all-on-B,
   alternating owners, ties and all 512 IDs. No two-local-sums substitution.
   Record real hit imbalance and activation bytes; require both placements
   and card-role reversal to reproduce unchanged single-card outputs.
4. **One complete GDN and QSA layer:** extend packet3's Buffer/Launch plan with
   explicit exchange nodes and owned dependencies; no enqueue-time host
   routing, allocations or readback. Bind actual weights. Compare every HC,
   norm, gate, router, attention/index, expert, BF16 recurrence/conv/KV state
   and residual boundary. Packet4's real-layer mismatch remains an independent
   blocker; a transport pass cannot waive it.
5. **Whole 48-layer two-card transaction:** compare the sequential split and
   within-layer split to the same CPU and single-card identity, every token
   and committed state across several positions/QSA pool boundaries, resets,
   changed prompts and failure rollback. Measure actual two-phase/gather cost,
   per-card peak memory and host backing. Atomic commit requires both owners'
   completion/error agreement. Keep 16-bit KV and no prompt reuse.
6. **Capture then complete-model qualification:** changed-input eager/replay
   parity, no stale buffers, row/batch invariance, deterministic repeats and
   fresh-owner repeat; then the fixed realistic cold suite, prefill alongside
   decode, unchanged weights and recorded zero cached tokens. Only matched
   quality and two fresh timing runs can support promotion. Nothing in the
   cost table substitutes for these gates.

The useful next measurement is PCIe copy/exchange latency. No existing runtime
has been forked; code reuses our pinned owner and Intel libraries only. This
packet changes no power, memory, driver, service or live-device state.
