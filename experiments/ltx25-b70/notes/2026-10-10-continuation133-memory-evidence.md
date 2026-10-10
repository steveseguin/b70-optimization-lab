# Packet 133: text residency evidence and exact candidates

The useful candidate is a **static text boundary at layer 36**, retaining
layers 0–35 on card 2 and 36–47 on card 3, with the native display on card 3
and legacy audio placement. It changes residency once before text capture;
it does not unload, destroy, or recapture text graphs between scene cuts.
This is a guarded candidate for native qualification, not a measured fit or
an exact-output result. Card 3's 9 GiB floor, the 5 GiB capture allowance and
the 0.75 GiB screening band remain unchanged.

This CPU-only [analyzer](../data/resume-20261008/continuation133-memory-analysis.py)
and [frozen JSON](../data/resume-20261008/continuation133-memory-analysis.json)
bind 446 regular files by SHA256: packet 132's seven completed receipt/decode
pairs, its failure/setup records, two fixed packet 129 windows of 210 receipts
each, previous inventory/capture censuses, the sealed text sources, and the
historical bandwidth-assumption/copy-probe records.
Each 129 window has nine qualification rows and 201 stream rows. The input
paths are explicit, including the completed-run suffixes. Nothing was read
from or written to `/home/steve/ltx-stream`; no existing run was written.
The analyzer imports only the standard library and writes its adjacent new
JSON. It ran at nice 19, OMP_NUM_THREADS=2, with the pinned `bin/python -B`.
No GPU, server, launch, live-port, unit, device, or host-setting operation was
performed, and no scratch directory was created.

All memory values below are GiB, meaning 2^30 bytes, unless marked otherwise.
Counters are sampled physical free memory, not instantaneous peak bounds.
Summing source tensor sizes is not proof that allocator segments will release
the same number of physical bytes.

## Inventory and use

| Owner | Current card | Bytes | GiB |
|---|---|---:|---:|
| Text layers 0–23 | 2 | 10,900,713,520 | 10.152081 |
| Other primary text state | 2 | 4,430,157,332 | 4.125905 |
| Text layers 24–47 | 3 | 10,900,713,520 | 10.152081 |
| Native video encoder | 3 | 637,873,794 | 0.594066 |
| Native video decoder | 3 | 834,267,488 | 0.776972 |
| Optional display replica | 2 | 834,267,746 | 0.776972 |
| Audio VAE and vocoder | 3 legacy; 2 in measured 132 arm | 364,666,868 | 0.339622 |
| Upsampler | 0 | 995,735,808 | 0.927351 |

The other text state includes embeddings, vision state, projections, norm
and buffers; the JSON retains its complete named census. The sampler's
20/28 boundary belongs to cards 0/1 and is unrelated to the text's 24/24
boundary. The full text static inventory is 24.430067 GiB.

The text window setup captures 480 graphs: 48 layers, five windows
64/128/256/512/1024 and two worker-thread identities. Runtime-admitted short
windows remain 64/128/256/512; 1024 is the parent/oracle shape. Each layer's
route owns mirrored arguments and static outputs. Transient capture pools
are shared per `(device, thread)`, with a stable capture stream. They retain
weight addresses and live graph storage. They are not dead allocator cache.

Source-derived owned argument storage per layer is:

`2 workers × 4 bytes × [1984 × (3840 + 1024 + 512) + 1,396,736]`

`= 96,501,760 bytes = 0.089874268 GiB`.

The terms are FP32 hidden input, both rotary matrices, and the full W×W
attention mask across the five windows. `ltx_graph_text_encoder.py:196`
mirrors all keyword arguments; `ltx_graph_capture.py:303` owns same-layout
buffers outside the pool. `comfy/text_encoders/gemma4.py:98` defines width
3840, lines 441–454 construct both rotary tensors, lines 468–479 construct
the mask, and line 598 passes these arguments. The graph output aliases its
owned static hidden-state input (asserted at `ltx_graph_text_encoder.py:248`),
so it adds no independent output allocation. This excludes latest
staged-argument caches, allocator rounding and shared transient pools.
It estimates tensor storage moved with a layer, not measured physical release.
With both text cards retained, no smaller shared-pool peak is credited.

A scene cut's encode traverses both text shards. In each fixed 129 window,
51 cuts actually encode text. The elapsed interval from `text_start` to
`stream_text_start` is median **0.389263 seconds**, range 0.375678–0.408284,
in the first run; median **0.388459**, range 0.376644–0.406601, in the second.
The six measured 132 encodes take 0.396709–0.432802 seconds. This timing
includes the actual encode node's work, not an isolated kernel duration.
The `reuse_text` rows have no text-start event: they reuse the already
computed conditioning tensor and its prompt/shape/dtype/hash identity.
For example, 132 qgraph-000000 and reused qgraph-000001 have the same
FP32 [1,56,6144] conditioning SHA256; no layer execution is needed on that
reuse request. The stream's current-scene conditioning cache is separate
from its per-forward staging cache and graph static tensors.

The 10.15 GiB secondary shard is not needed to compute anything between
cuts. It is **nevertheless still needed as live storage by the captured
graphs**. This is stateless prefill: no incoming past KV or shared KV, and
dead present/shareable outputs are discarded. There is no evidence that a
persistent autoregressive KV cache consumes those weight bytes. Reuse does
not make the weights' graph addresses disposable.

## What actually failed in 132

The saved failure is **`conditioning-B-before` on qrepeat-c000001**,
not the initial request-before sample. Its initial request and A checks
had 12.079517 GiB free on card 3. The later B-before snapshot had
**9,103,118,336 B = 8.477939606 GiB**, short **560,558,080 B = 0.522060394
GiB** of the unchanged 9 GiB floor. Including a 0.75 screening allowance,
the shortfall would be 1.272060394 GiB. This distinction matters when
projecting a reload or overlap schedule.

| 132 sampled minimum | Card 0 | Card 1 | Card 2 | Card 3 |
|---|---:|---:|---:|---:|
| Before | 9.494965 | 9.848198 | 10.144085 | 12.079514 |
| A-before | 9.494965 | 9.848202 | 10.144089 | 12.079517 |
| A-after | 9.494965 | 9.848202 | 10.144089 | 12.079517 |
| B-before, including refusal | 9.282059 | 9.848125 | 10.007450 | 8.477940 |
| B-after, completed only | 9.297695 | 9.867729 | 10.007450 | 12.079575 |
| After, completed only | 9.285965 | 9.828655 | 10.007355 | 9.692783 |

Columns may come from different moments. The first cone capture was admitted
at 16,173,350,912 B against 15,837,691,904 B, a 335,659,008 B (0.312607 GiB)
margin. The decoder receipt's actual `pool.growth_bytes` is
**3,806,330,880 B = 3.544921875 GiB**. The earlier 4.505890 GiB number was
a temporal-squared estimate from 121 frames, not this run's measured growth.
Neither value is an isolated instantaneous capture peak. Keep the 5 GiB
reserve; this single sample does not justify tightening it.

Card 2's lowest **before-display** free is 10,745,401,344 B = 10.007435 GiB,
at qeager-c000002. After its 2 GiB floor, 5.640625 GiB display transient
reserve and 0.75 band, only 1.616810 GiB remains. Post-display low readings
must not be substituted for this admission boundary.

## Ranked options

| Rank / option | Freed memory and cost | 145 cone / 169 status |
|---|---|---|
| 1. Static boundary 36; native display 3, legacy audio | Move layers 24–35: **5.076040 GiB weights**, plus **1.078491 GiB estimated owned graph arguments**, 3→2. Cards 0/1 unchanged. No per-cut reload or recapture. Encode-cost delta unknown; existing encode is about 0.389 s/cut. | A guarded 145 candidate with useful projected margins below. 169 remains unqualified; no matched native3/legacy graph receipt. |
| 2. Static boundary 27; retain 132 replica/audio on 2 | Move **1.252530 GiB weights** plus **0.269623 GiB graph-argument estimate**, 3→2. No per-cut copy. | Projects only **0.094657 GiB** card2 and **0.250093 GiB** card3 after relevant screens. Too narrow to prefer over boundary36. No 169 admission evidence. |
| 3. Host-pinned secondary shard, reload on each cut | Nominally **10.152081 GiB** freed on3 while absent, zero weight saving on2. Assumed 5–10 decimal GB/s gives **1.09–2.18 s one-way reload/cut**, or **0.273–0.545 s/chunk** across four chunks. | Idle145 free projects18.630020 GiB, but retained graphs pin weight addresses; ordinary module movement neither frees graph-owned storage nor preserves replay. Reload also restores pressure beside the cone pool. No admissible exact lifetime design is established; 169 unknown. |
| 4. Entire text on2, replica removed, display back on3 | **10.152081 GiB** weight transfer3→2; replica removal saves0.776972 on2 relative to132. Full text weights24.430067 GiB before graph/workspace. No per-cut reload; encode timing unknown. | Against native129's already-no-replica minimum11.705807, transferring weights alone leaves1.553726 on2, below2floor before additional graph storage. Shared-pool consolidation might help but is not measured. Keeping replica2 is worse. Neither arrangement is admitted by present evidence. |
| 5. Scheduled next-scene prefetch | **0 GiB freed by scheduling alone.** Can shift the existing roughly0.389 s encode; a host reload would add its own1.09–2.18 s. | It does not cure pinned residency. Exact deterministic scheduling is possible in principle with authenticated scene/prompt identity and unchanged runtime math; current receipt authority and graph-thread ownership do not support it. Neither length becomes admitted merely by prefetch. |
| 6. Destroy text graphs/pinned pools between cuts | No separately measured guaranteed GiB; preparation live residuals2.275 on2/2.771 on3 include other allocations. | Changes the sealed frozen-graph/window contract and requires full new proofs and recaptures. No current exact admitted implementation for either length. |

Ranks 3–6 are analysis, not launch options. Host-pinned memory capacity is
also not an admission proof: packet132 construction reported 56,181,190,656 B
MemAvailable, but no new pinning was attempted. No measured link bandwidth
was found in the inspected receipts/notes. The October 4 GPU-work survey
explicitly labels its pinned20–25 GB/s and pageable5–10 GB/s rates as
assumptions; the old copy probe reports whole-schedule time without bytes.
The 1.09–2.18 second estimate above is arithmetic at assumed5–10 GB/s,
not a host measurement. If immutable host weights allow upload without a
download, one-way bytes suffice; preserving changed state or copying back
would cost more. Graph reconstruction remains additional and unmeasured.
The observed132 window qualification took337.149493 seconds, including
480 captures and multiple proofs: it is not a per-cut recapture estimate.

Packet119's rejection of speculative next-prompt work was correct for the
existing protocol: the successor prompt is not authoritative at receipt
commit. A deterministic scenes file can supply future text only if its
schedule, prompt, index, revision, cancellation rules and eventual request
are bound and checked. An unconsumed result cannot silently replace a cut's
text. Running on the decode thread also needs that thread's qualified graph
routes and serialization against the cone/display work. Exact math alone
does not establish these authority and memory conditions. Such future work
must not be counted as saved latency or recovered memory here.

Dropping only a pool handle does not release live graph tensors. Destroying
graphs then restoring them violates the inherited capture freeze and window
identity until requalified; eager fallback is not proven bit-identical to
the sealed graph path merely because it uses the same weights. These are
the reasons the host/pool ideas are not implemented in this packet.

## Selected boundary36 arithmetic

Use the matched native-display/legacy-audio129 window, not replica132's
post-display low point. Its minima on cards0/1/2/3 are
**9.270363 / 9.828613 / 11.705807 / 10.806747 GiB**.

| Projected 145 quantity | Card 2 | Card 3 |
|---|---:|---:|
| After moving5.076040GiB weights, before changed graph storage | 6.629766 | 15.882788 |
| Include1.078491GiB owned argument transfer | 5.551275 | 16.961279 |
| After additionally charging observed132 cone growth3.544922 on3 | 5.551275 | 13.416357 |
| Margin after card2 floor2+band.75; card3 **full5 reserve+floor9+band.75** | **2.801275** | **2.211279** |

Cards0/1 retain projected observed minimum margins1.270363/1.828613 GiB
above their8GiB floors. All four are scenarios, not simultaneous snapshots.
Private allocator rounding, pool peaks and staging can move the actual values.
No spare GiB from graph-pool consolidation is credited. The first qualifying
cone's native129 minimum14.478330GiB is already a higher boundary than the
all-phase tail used here, so the preserved14.75GiB first-capture check has
substantial projected room after redistribution. Runtime must still refuse
if fresh physical admission or any exactness check fails.

For comparison, boundary32 moves3.373040GiB weights and estimates0.718994GiB
owned arguments. Charging the full5GiB reserve to its all-phase tail leaves
only0.148782GiB beyond9+.75 on3. Boundary36 buys materially more robustness
without the wholetext2 capacity problem.

Moving12 layers between equal B70 devices preserves their BF16 parameter
bits and existing FP32 arithmetic route; the text model still executes the
same ordered layers. Each secondary layer currently stages its hidden input
to card3 and its result back to card2. Moving twelve layers removes twelve
such activation round trips per encode; it is not just one boundary transfer.
The graphs must be captured after final placement. Display/audio cross-card
identity is encouraging evidence about those operations, not proof of text
identity. A sealed-parent text oracle, window proof, changed-input checks,
repeat comparisons and full native outputs remain mandatory. CPU accounting
does not pass those gates.

The inherited conditional cadence target is **5.25–5.35 seconds per6 seconds
of new video =0.875–0.892 s/s**, plus any text-placement timing delta. There
is no measured split36 period. Unlike moving the display/audio to2, this
choice retains129's native display/audio arrangement. At roughly0.389 s/cut
every four chunks, current text contributes about0.097 s/chunk; that existing
cost is already in the baseline and must not be added again. The hypothetical
host-upload option would add0.273–0.545 s/chunk before recapture, yielding
5.523–5.895 s or0.920–0.983 s/s if all other assumptions held. These are
engineering forecasts only, not benchmark points.

169 has no matched native3/legacy/cone-graph receipt. The available169 records
are123b auxiliary2/native3 and127 legacy/replica2/parallel, the latter refused
its replica admission. No 169 graph peak, complete new text placement gate,
or repeated period is established. The historical6.20–6.65 s per7 s forecast
belongs to a different parallel-display schedule and is not a prediction for
this candidate. Do not claim169 admissibility or a169 speed from this audit.

Open items are actual physical redistribution and allocator effects,
native cross-card text identity, complete145 graph
qualification, later scene-cut peaks, repeat speed and169 admission.
