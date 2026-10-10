# Sampler feasibility for the LTX continuation stream — 2026-10-10

**Recommendation: retain the packet-135 sampler; do not build packet 136. No positive sampler saving is supported by the admissible changes examined here (budgeted saving: 0 s/chunk).** A 24/24 split cannot shorten a serial dependency chain and fails card 0's memory floor. Stage A/B batching and overlapping B(N) with A(N+1) violate data dependencies. This closes those mechanisms for this design; it does not establish a hardware ceiling. A materially different tensor-parallel arithmetic path would require the owner's acceptance of a new numerical authority.

This is a design-only, CPU/read-only evidence audit on steve-b70s, with nice 19 and OMP_NUM_THREADS=2. No GPU/runtime import, device access, server, launcher, check-only, systemd/unit, port, process signal, or host-setting operation occurred. Existing runs and `/home/steve/ltx-stream` were read only. No scratch was created. The deliverables are this note and a short CURRENT entry; no runtime or evidence packet changes.

## Evidence and measurement boundary

The [campaign](2026-10-10-ltx-continuation-campaign.md) and [results ledger](../results/ltx25-continuation-stream-2026-10-10.md) establish the completed **135 GC60** line: 121 chunks, 111 periods, median **5.248 s per 6.0 s new video**, mean 5.727, p90 5.919, destination-even/odd medians 5.210/5.529. This note does not assign an outcome to the later GC10 A/B or inspect live services.

Let `B = /mnt/fast-ai/bench-results/ltx25-baseline-20260913/`,
`P = B/prepared-continuation-stream-135/`, and
`R = B/encoder-server-continuation-stream-135-frame-dg1-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-dseager-display-ra0-ssfull-gc60-ssbackground-sdc1-mi-cmtext-shift-textsplit36/`.
The old `dxpu2` name fragment is not placement evidence: the receipts specify display xpu:3.

Read all 121 `R/receipts/receipt-stream135-sNNNNNNNN.json` records. Timing below uses **source chunks 9–119 inclusive (111 chunks)**, corresponding to the work preceding the ledger's destination periods 10–120. No outliers were removed. Independent bucket medians need not add to the median period. The brief's rounded chain estimates mostly describe an earlier 133b window; these are recomputed packet-135 values.

| Chain interval | Median seconds | Interpretation |
| --- | ---: | --- |
| Submit to sampler A | 0.423505 | Text when needed, native A preparation, admission and snapshots |
| Sampler A | 1.920781 | Sampler node start to separate-A node start; wall time, not isolated kernels |
| A end to sampler B | 0.267927 | Upsampling plus B preparation and node handoffs |
| Sampler B | 1.674240 | B start to B done; wall time |
| A+B, summed within each chunk first | **3.600748** | **68.61%** of 5.248 s; ratio of medians, not measured utilization |
| Cone decode on chain | 0.749235 | Includes its scheduling boundary |
| Video done to anchor ready | 0.031380 | Anchor publication |
| Anchor ready to receipt staged | 0.069053 | Receipt staging, not the full next-submit delay |

The A-to-B gap's separately computed component medians are 0.000805 s separate-to-upsample, 0.064729 s upsample-to-B-conditioning, 0.206675 s B-conditioning-to-concat and 0.000513 s concat-to-B. They are node-event intervals, not isolated GPU costs. B conditioning retains the existing prepared-encode consumption and safety work; it cannot all be credited as an upsampler or inter-card transfer saving.

The measured geometry is A latent **[1,128,19,4,4]**, final video latent **[1,128,19,8,8]**, audio latent **[1,8,151,16]**, batch one. Saved latent outputs are float32; this does not change the BF16 transformer-weight contract. Video token counts are 304 in A and 1216 in B. There are eight A steps and three B steps, 48 blocks per forward: **528 block executions per chunk**. Streaming graph receipts report 48 routes, four signatures per route, **192 frozen captures**, zero new captures. “Four signatures” does not mean four sampler steps.

## What the sampler timing can and cannot tell us

`P/source/scripts/ltx_layer_shard.py:96–104,135–149` moves routed inputs with `to(device=..., non_blocking=False)` and preserves dtype. Blocks 0–19 execute on card 0; block 20 receives their output on card 1; blocks 20–47 execute there; the last route returns the activation to primary card 0. Thus the forward has **both a 0→1 boundary and a 1→0 return**, repeated on each of eleven forwards, not one hop per chunk. Invariant argument caching is scoped to one forward. Tensor contents and copies needed at a boundary cannot be removed by balancing block counts.

The block dependency makes useful transformer work serial: card 1 cannot compute block 20 before block 19 supplies its input, and the next forward cannot begin its dependent state before the previous forward finishes. Each sampler card therefore has intervals with no useful work from this sampler while the other computes. Copies and queued tails can overlap in ways that this source audit does not time. This is not a claim that every engine on the whole host is idle: text and display use cards 2/3, and preparation has its own work.

**Exact per-card idle seconds, per-block GPU time, exposed inter-block host overhead and boundary-copy time are not measured by these receipts.** `sampler_a_split` in `P/resolution/components/integration.py:1606–1615` uses node-event wall timestamps. Ordinary graph replay (`ltx_graph_capture.py:1249–1261`) fills static inputs and replays without synchronizing after every block; Python work can overlap queued kernels. `LTX_BUSY_WINDOWS=0` is pinned in the runtime/launcher. None of the six run-level graph-capture reports has `graph_timing`, and no run-level timing/profile/restore report was found. The retained `measure()` method (`ltx_graph_capture.py:1491–1528`) is a separate synchronized replay diagnostic, not a measurement taken here.

For scale only, allocating the 3.600748 s wall budget in proportion to 20/28 blocks gives **1.500/2.100 s**. In that intentionally simplified serial model, card 1 waits through the former and card 0 through the latter. These are **not measured busy or idle times**: the budget contains sampler arithmetic, copies, host work and waits. A 24/24 split would merely make this proxy 1.800/1.800; the sum stays 3.601 s. There is no measured per-card imbalance to convert into a latency saving.

Historical [contiguous-capture measurements](../experiments/ltx25-b70/notes/contiguous-capture-retired.md) already superseded the pre-graph “three-quarters dispatch” diagnosis. Packet 33b measured summed replay times of 131.8/172.7 ms per forward at 64/256 video tokens, accounting for most of its approximately 1.58 s block region. Neither those small-shape timings nor the old 537 GB/s GEMM roofline establishes today's 304/1216-token GPU split. Do not subtract 75% of today's sampler wall time as recoverable Python overhead.

The residual parity gap also is not a demonstrated alternating GPU stall. Current A medians by source-even/odd are **1.920491/1.921565 s**, B **1.693806/1.671932 s**, and pre-A **0.479662/0.409493 s**. Source parity reverses the destination labels used for periods. These figures do not account for the whole 0.319 s period gap; adding independent medians or assigning the remainder to the boundary would be unjustified.

## Candidates, memory, and exactness

Physical-free minima from the same 111 receipts, across before/after and conditioning A/B observations:

| Card | Free GiB | Conservative floor GiB | Above floor | Above floor plus 0.75 GiB band |
| --- | ---: | ---: | ---: | ---: |
| 0 | 9.292038 | 8 | 1.292038 | 0.542038 |
| 1 | 9.828808 | 8 | 1.828808 | 1.078808 |
| 2 | 4.907825 | 2 | 2.907825 | 2.157825 |
| 3 | 14.596432 | 9 | 5.596432 | 4.846432 |

These are independent minima, not a simultaneous peak snapshot or a guarantee of free allocation capacity. Request-after has a lower two-GiB check; the table deliberately retains the stronger preconditioning floors. The card-0 minimum also occurs at conditioning B-after on source chunk 61, where the eight-GiB floor applies; its split refusal is not inferred solely from a request-after low. No reserve, band or snapshot is reduced.

| Candidate | Saving supported for this chunk | Memory and implementation | Required exactness gate / disposition |
| --- | --- | --- | --- |
| **(c) Rebalance 20/28 to 24/24** | **0 s from balance alone**; sum of dependent block times unchanged | Four BF16 blocks are **3,093,399,040 B = 2.880952 GiB**. Weights alone leave card 0 **6.411086 GiB**, **1.588914 GiB below its floor**, before transferred graph state/workspace. Card 1 could release weights, but that does not fix card 0. Medium change: layout allowlists, native authority, routing, captures, census and pins, not one flag. | Same-operation relocation could qualify against the unchanged oracle, but `native_adapter.py:92–128` explicitly requires named20/28. Reject at memory/design screen; no build. Even moving one 0.720238-GiB block exceeds card 0's current margin after the band without proven reclamation. |
| **(e) Batch A and B** | **0 s admissible** | B consumes A's audio and upsampled video; grids, sigmas and conditioning differ. No independent pair exists. Padding/batching also changes GEMM shapes and demands extra activations/graphs on cards 0/1; unbudgeted. | Not schedulable under unchanged dataflow. CPU graph dependency test would reject it before any native gate. |
| **(b) Pipeline B(N) with A(N+1)** | **0 s admissible** | A(N+1) needs N's final decoded anchor, which requires B(N) and its cone. A second worker/buffer cannot remove this dependency and would consume the narrow sampler margins. | A stale/predicted anchor changes the contract. No unchanged-output candidate. Independent reset scenes are a different workload. |
| **(b) Advance the next fresh text encode** | No sampler saving. Median-based allowance **0.3627 s per cut**, approximately **0.0907 s/chunk** at one cut per four chunks if fully hidden; no established median-period gain | 27 fresh pipeline records in this window have median `detail.stage_seconds=0.3627`; their summed encode time divided by all 111 chunks is **0.088124 s/chunk**, the observed mean-budget ceiling if all that time could be hidden. Existing weights/graphs stay on cards 2/3; one additional result plus overlapping transient memory must fit their +2.158/+4.846 GiB band margins. Incremental bytes and concurrent peak are unmeasured, so not admitted. Medium state/protocol change: early prompt admission, owner/lifetime binding, cancellation and separate current/future conditioning. | Independent of predecessor pixels, but only useful if the actual future prompt is admitted early. Same text hash oracle and full-chain parity required. Existing within-scene reuse, B-encode overlap, preparation ahead and off-chain display cannot be credited again. Card 3 display contention may erase the saving. Outside authorized c/e build scope. |
| **Exact output-column tensor partition** | No present positive estimate; historical economics negative | Large re-sharding/graph/communication change on both sampler cards, new full-activation gather buffers and graph pools. No current memory admission; cannot spend either card's existing margins without a new census. | Full reduction dimension retained, ordered byte-preserving gathers can avoid cross-card summation. But changed GEMM output shape can change kernels/rounding. Requires current-shape operator and block exactness before full unchanged-oracle chains. Retired evidence below; no build. |
| **Same-card multi-block graph grouping** | **0 s bankable**, current exposed dispatch fraction unknown | No weight move; replacement capture pools/static state have unknown incremental peak against card 0's +0.542 and card 1's +1.079 GiB band margins. Medium contract/capture change despite existing implementation. | Preserve every operation, input refresh and owner; compare grouped eager/replay/repeat and all full outputs to unchanged authority. Previously retired on measured lack of exposed dispatch; no reason to reopen without matching evidence. Outside c/e scope. |

The block weight size comes from the header-only [duration108 census](../experiments/ltx25-b70/notes/2026-10-07-duration108-residency.md): **773,349,760 bytes/block** loaded BF16. It also agrees with packet135's secondary segment bytes 21,653,793,280 / 28. Existing graph buffers are additional; no unmeasured allocator recovery is credited.

The dependency is explicit in `stream_contract.py:605–625`: B concatenates audio from A's `367:1` and video through upsampler `348`, whose input is `367:0`; both derive from A sampler `344`. Frame-mode A/B conditioning (`:706–713`) reads the predecessor anchor. The authority (`:407–421`) binds the predecessor's final image, one worker, batch one and chain one. Text (`:664–670`) instead depends on the actual prompt/clip/window and can in principle run earlier. Existing preparation overlap does not make the sampler inputs independent.

**(d) Fewer steps or a different sigma schedule is rejected as non-exact.** The pinned eight-plus-three Euler-ancestral steps (`stream_contract.py:177–178`) define the computation. Likewise dropping audio, approximate attention, reduced precision or compressed state is not an exact substitute.

## Tensor parallelism and a new authority

Deterministic collectives are not sufficient for bit identity to the unchanged single-device GEMM operation. Splitting the reduction dimension computes separately rounded partial dot products and combines them in a different order. A repeatable all-reduce can make the new answer repeatable without making it the old answer. Exact copies do not recover discarded rounding information. The sealed implementation provides routing/copies, not a cross-card implementation of the original GEMM's internal accumulation schedule. Accordingly **ordinary row-parallel/all-reduce TP cannot be claimed bit-exact with the available implementation**. This is not a mathematical impossibility claim about every conceivable custom kernel.

Output-column partition with full-K accumulation and concatenation is the narrower potentially exact exception. The [historical column-parallel study](../experiments/ltx25-b70/notes/column-parallel-retired.md) found 19/20 two-way operator cases exact, with `a2v.to_q` failing one shape. Its ideal no-communication 48-block timing was 104.34→67.82 ms, but sixteen gathers per block made it **116.27 ms**, slower than serial. The [source audit](../experiments/ltx25-b70/notes/ltx-linear-output-partition-source-audit-01.md) explains why output-shape changes still need exact tests. Those older shapes neither certify nor benchmark today's 145 frames. Do not multiply their speedup into a current savings forecast.

A new-authority path would require owner acceptance that output bytes may change, an explicit TP arithmetic and communication contract, pinned models/runtime/kernels, current-shape operator determinism (video/audio, masks and both stages), block and full-chain references, repeated/fresh-process determinism, and video/audio/continuation quality review against the retained old authority. It also needs a new memory census and matched end-to-end measurements including communication, capture and display contention. The existing three-chain identity gate must remain for the unchanged line; a newly generated reference plus three self-consistent chains is not proof of equality to it. Potential saving is **unmeasured**, not the ideal 1.8 s obtained by halving all sampler wall time.

For any future exact candidate, retain capture eager/replay bit equality and non-inert-input checks, frozen owner/signature coverage, and c0/c1/c2 eager/graph/repeat chains consuming each chain's own verified predecessor. Compare stage-A/video/audio latents, full images, waveform, anchor and prompt identity against the pinned reference, plus fresh-server repeat and stream comparisons. Full floors, safety checks and decoder equality remain independent gates. A future packet must follow 135's sealed-import test, inner-plan pins and complete suites; none is warranted by c/e here.

## Reproducibility of this audit

Source packet manifest identity: `4356482eae2f1d7ac95b17e6483379ceed0cc90ed488d46765803451980402c3`; inner plan: `7750e7b54c885f99a73ab87b17013fc0a850a1af942f0c00422adbae596258c4` (see [135 build/design](../experiments/ltx25-b70/notes/2026-10-10-continuation135-stream-design.md)). Key files read as text, never imported:

| File relative to P | SHA256 |
| --- | --- |
| source/scripts/ltx_layer_shard.py | a000ccd309e70b2f41167c84b73aae01caf50f9cd38d1256a21f6cc7b0dd2ef3 |
| source/scripts/ltx_graph_capture.py | fc691e4ff4fdbeba0724a8946dbb58dbf3b4cbd9ccdaf325c307f2d86981d7e5 |
| resolution/components/native_adapter.py | f39420afe2907dab4075d05419be1cd1740cfd8e12732c558fae9b2dc91666e8 |
| resolution/components/stream_contract.py | da8b1a82c3c3dfb4f8e848433bcfec47aef3e728c47874b9f29d6581e3ee2296 |

`R/stream-geometry-measured.json` SHA256:
`ca2b5a51a1d07317fe5c55c65d5b7c572f39a5bb3a786a019268e8e55f71cae4`.
`R/stream-qualification-verdict.json` SHA256:
`7ca7bbdde174c6698c352b80843ba854823c046e96d2280526746f4bc83e2598`.
The sorted 121-receipt inventory digest is
`15465e2c6a188bfd004b949bef714ad84aa91a57bcb7962d410f69c9cc92e762`:
SHA256 of concatenated `filename + " " + SHA256(file bytes) + "\n"` lines in filename order.

Recompute with standard-library Python under `nice -n 19 env OMP_NUM_THREADS=2 python3 -B`: parse the above receipt glob, select `9 <= stream_seq <= 119`, take `statistics.median` of `timing_s.sampler_a_split.sampler_a`, `timing_s.sampler_b` and their per-row sum. The gap sums the other four `sampler_a_split` fields per row. Other timing rows use the correspondingly named `timing_s` fields. Memory minima use `memory.before.free`, `memory.after.free` and each conditioning entry's `free_before/free_after`, dividing bytes by 2**30. Fresh-text timing selects the 27 `R/pipeline-stream135-s*.json` files in the same sequence window and takes the median of `detail.stage_seconds`. This reads JSON only and writes nothing.
