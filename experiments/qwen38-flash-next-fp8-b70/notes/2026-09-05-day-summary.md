# Qwen3.8 Flash-Next TP4 lane: 2026-09-05 (overnight through morning)

Standing lane: fastest possible without changing the answers, published so
anyone can reproduce it. Overnight work attributed the promoted MTP0 line's
72.7 ms decode step, by graph-mode subtraction and offline probes.

## What the step is made of (graph MTP0 identity, 2K, per step)

| component | ms | how |
|---|---:|---|
| everything except the MoE block | 19.1 | A145 (MoE path skipped) |
| MoE routing, alignment, quantization, sum | 3.3 | A148 minus A145 |
| the two MoE grouped GEMMs, execution | ~10 | A151 (all-reduce skipped) minus A148 |
| waiting at the 48 MoE all-reduces | ~40 | A146 minus A151/A154 |
| total | 72.7 | A146 control, authority hash |

The waiting appears only when the real GEMMs run before the collective and
the collective reduces the real MoE output (A146). It vanishes when the
GEMM launches are memsets (A148, 22.4), when the all-reduce is a no-op
(A151, 32.9), when it reduces a static zero buffer at the same site (A154,
34.2), and it is unaffected by the GEMM's launch configuration (A155, 4
warps / 2 stages, 74.8, exact). Offline, none of it reproduces: the same
collective on the dumped real MoE outputs (A156 dump, 48 tensors in
sequence, identical or rank-distinct) costs 0.025 ms per call inside an
XPU graph, every data class and every oneCCL knob is 0.6-1.7 ms per 48
calls, a Triton or matmul kernel before it adds nothing, and graph replay
adds nothing per Triton launch. Split-K for the GEMMs is a negative (the
launch is fixed-cost bound) and the platform XPU MoE backend does not match
the staged kernel package (rebuild needed).

## What the morning settled (A159-A163)

A159 (real data all-reduced, result discarded: 34.1 ms) showed the
subtraction was not additive: every perturbed run puts the model on a
wrong trajectory and costs 22-34 ms; only the real trajectory costs 72-75.
The per-layer embedding was cleared as the cause (A161 on device: exact but
313 ms, an on-device dequantization artifact; A162 eager with the XPU PLE
path instrumented: about 2.5 ms per step in total). A163, the same eager
instrumentation on a wrong trajectory, gives the differential: real minus
wrong is +18.5 ms per forward, all in the MoE block (all-reduce segment
+11.4, expert kernel +6.1, w13 GEMM +4.3), every other sub-operation flat.
The real trajectory routes to more distinct local experts per rank and
reaches the MoE collective more skewed; the graph replay, with nothing
else resynchronizing the ranks, doubles that into the 40 ms.

Midday results (promoted graph identity, one change each, telemetry
bypassed, 2K request, hash against the authority `afffd211`):

| attempt | change | hash | rate / step | verdict |
|---|---|---|---|---|
| A164 | `CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=0` | differs | 13.65 tok/s, 75.8 ms | rejected |
| A165 | `CCL_SYCL_ALLREDUCE_LL_THRESHOLD=8192` (low-latency path) | authority | 13.69 tok/s | exact, neutral (graph replay is correct with oneCCL 4ceafd1 now) |
| A166 | `CCL_SYCL_ALLREDUCE_ARC=1` | differs | 14.19 tok/s | rejected |
| A169 | split-K 4 MoE GEMMs (`VLLM_XPU_MOE_SPLIT_K=4`) | authority | 12.54 tok/s, median 63.7 with 90-118 ms outliers | exact, not faster |
| A168 | routing dump (eager, real text) | authority | slowest rank 204 blocks/step vs mean 120; round-robin 202, frequency-balanced 195 | static placement recovers at most 10% of the skew |

Offline, a deliberately late rank makes each captured all-reduce cost
exactly the extra arrival time (no fixed poll or backoff penalty), so the
40 ms is genuine per-layer arrival skew of the MoE block on the real
trajectory. Queue: A170 (split-K 8), then A171/A172 with forced
pseudo-random routing, balanced across ranks versus all on one rank
(timing only), to separate imbalance from per-hit weight streaming.

## Host

Sixth silent freeze at 09:48. In five of the six crashed boots the last
journal entry is the GPU telemetry audit (xpu-smi through the Intel MEI
driver), run by every packet at launch and teardown, seconds before the
freeze. New packets copy cached receipts (attempt 146) instead of calling
it (`tools/q38_freeze_mitigation.py`, supervisor and base-script rules);
launches since 10:39 ran with zero telemetry calls. The pending root-NVMe
firmware activation still needs a power-off.

Notes: [MoE share and attribution](2026-09-04-tp4-mtp0-a145-a146-moe-share-of-the-graph-step.md),
[request-shape matrix](2026-09-04-tp4-mtp1-a143-request-shape-matrix-result.md),
[sub-op timing](2026-09-04-tp4-mtp1-a141-a142-subop-timing-attribution.md).
Data: `../data/20260905-tp4-*`, `../data/20260905-b70-moe-*`,
`../data/20260905-tp4-allreduce-data-and-knob-probes/`.

## Afternoon: forced-routing runs point at VRAM oversubscription

| run | routing | step (ms, forward) | note |
|---|---|---|---|
| promoted graph MTP0 | real | 72.7 | authority |
| A171 | forced balanced pseudo-random, ≤3 hits/rank | ~125 | identical on all ranks, no recompiles, output collapsed to one token |
| A172 | forced, all 10 hits on one rank | 159.3 | identical on all ranks, coherent output |
| A173 | A171 + `Q38_LAYER_TIMING_LOG=3` | capture failed | the layer hook synchronizes; illegal while recording a graph → sub-op timing is eager-only |

Offline, the same Triton MoE GEMMs with fresh random experts every call (cold, `Q38_BENCH_FRESH_ROUTING`) cost 0.35 ms/layer at 1 hit and 0.54 ms/layer at 10 hits, so the server's extra ~2 ms/layer under forced routing is not the kernel. Linear fit across A171/A172: ≈0.09 ms per hit plus a fixed ≈2 ms per layer that appears only when cold experts are touched.

Per rank the weights take 31.57 GiB of the B70's 31.89 GiB (routed experts 114.86 GiB / 4 = 28.7 GiB; the rest is GDN, attention, the vocab-sharded embedding and head, shared expert, router). Card 0 showed 0.09 GiB free during a load. The runtime is already minimal (64-token prefill chunks, one sequence, one graph size, 128 MiB KV). Hypothesis: the xe driver evicts weight buffers to host memory under pressure and pages them back on first touch at PCIe speed (≈7 GB/s, the A171 rate). Hot experts stay resident, which is why degenerate trajectories (a few warm experts) run in 22–34 ms and PLE on the device (A161) ran at 313 ms. Probes queued: free VRAM after startup, an offline VRAM-filler run of the fresh-routing bench (chain19), and A174 (eager forced routing with the sub-op split).

## 14:42 seventh host freeze, the first with a kernel trace

A174 (eager lineage, checkpoint on the root NVMe) launched 14:40:31; its server log stops at 14:41:35 as weight loading begins. The previous boot's journal then shows `watchdog: BUG: soft lockup - CPU#30 stuck for 678s! [VLLM::Worker_TP]` in `smp_call_function_many_cond` (TLB-shootdown IPIs from the page-fault path) and `kworker … blk_mq_timeout_work blocked for more than 122 seconds` (the block layer), i.e. the root 980 PRO stalled under the mmap'd checkpoint read and the host hung. With xpu-smi bypassed since the morning, this is the next failure mode exposed. The host was hard-restarted at 16:33 (a first reboot at 16:16 was restarted again). Eager-lineage runs, which load from the root NVMe, are now a suspected freeze trigger; the graph lineage loads from USB.

## 17:00 the step is VRAM paging, confirmed offline at the server's footprint

`timing-moe-gemm-events-offline.py` gained `Q38_BENCH_SETS` (layer-sized FP8 expert weight sets, 629 MB each) and `Q38_BENCH_FRESH_ROUTING` (new random local experts every call). On card 0:

| resident expert sets | GB | reported free | w13 GEMM | w2 GEMM |
|---|---|---|---|---|
| 8 | 5 | 26 | 0.23 ms | 0.16 ms |
| 24 | 15 | 12.8 | 0.23 | 0.16 |
| 40 | 25 | 3.45 | 0.23 | 0.16 |
| 42 / 44 / 46 | 26 / 28 / 29 | 1.9 / 0.33 / 0.33 | 0.23 | 0.16 |
| 48 | 30.2 | 0.51 | **21.7** | **12.2** |

The 48-set cost is the same for 3 and 10 hits and equals one whole 419 MB / 210 MB buffer crossing PCIe at ~19 GB/s: the xe driver migrates entire buffers on touch once the footprint no longer fits, and there is no watermark slack below that (0.33 GiB free is still clean). A175's memory note puts the server at 31.746 GiB reserved of 31.891 per rank, i.e. at the edge, so transients evict weight buffers and every later touch of a cold expert pays a migration. This is the mechanism behind the promoted 72.7 ms step (real routing keeps hot experts resident), the 125–159 ms forced-routing steps (A171/A172), the 313 ms PLE-on-device step (A161), and the fast degenerate trajectories (a few warm experts).

Fix under test: A177 = promoted graph identity with `embed_tokens.weight`, `layers.46.mlp.experts` and `layers.47.mlp.experts` added to the UVA offload (≈1.56 GiB/rank freed for ≈5 ms/step of PCIe expert reads; the kernel reads the same bytes, so the output hash must stay `afffd211…`).

## 17:37 A179: bit-exact 2x from VRAM headroom

A177's per-layer selectors (`layers.46.mlp.experts`) matched nothing: the UVA offloader wraps decoder layers through `make_layers` with the prefix `…layers.` and the layer module's own parameter names carry no index, so the total stayed at 12.22 GiB (embedding + PLE) and the base script's receipt guard stopped the run. A179 uses the selector `mlp.experts` under a 13.4 GiB budget; the greedy fill takes the embedding, layer 0's experts, PLE, layer 1's experts and layer 2's `w13_weight`, and every rank logged the predicted 13.78 GiB.

| | A175 (promoted identity, memory note) | A179 (+ expert offload) |
|---|---|---|
| host-offloaded per rank | 11.92 GiB (PLE) | 13.78 GiB |
| allocator reserved per rank | 31.746 GiB | 29.891 GiB |
| forward step (graph, M=1) | 74.5 ms | **37.0 ms** |
| exact-2K conventional tok/s | 14.42 | **25.13** |
| output token ids | authority `afffd211…` | identical |

The same Triton kernels read the same bytes (two and a half layers' experts now cross PCIe each step, ≈6 ms), so the change is numerically inert by construction and the ids match token for token. A180 (fresh server, exact-2K twice) is the certification pair; A181 (budget 12.5 GiB: embedding + one expert layer) probes how little headroom is enough. MTP1/MTP2, whose 0.60x on real text was measured under the same paging, are next in line for re-evaluation with headroom.

## 18:12 headroom certification pair and budget probe

| run | host offload per rank | allocator reserved | forward step | exact-2K tok/s | output |
|---|---|---|---|---|---|
| A175 (promoted identity + memory note) | 11.92 GiB (PLE) | 31.746 GiB | 74.5 ms | 14.42 | authority `afffd211…` |
| A179 (budget 13.4: +embed, L0/L1 experts, L2 w13) | 13.78 GiB | 29.891 GiB | 37.0 ms | 25.13 | identical |
| A180 (A179 identity, fresh server, r1 / r2) | 13.78 GiB | 29.891 GiB | 37.1 ms | 25.14 / 25.20 | identical / identical |
| A181 (budget 12.5: +embed, L0 experts) | 12.8 GiB | 30.867 GiB | 35.8 ms | 24.44 / 25.94 | identical / identical |

Under 1 GiB of headroom already ends the paging, and each offloaded expert layer costs about 1 ms of PCIe reads per step, so the smallest offload that fits is the fastest. Certification (A182 realistic suite, A183 frozen-client battery) continues on the A179 identity that was already in flight; the embedding-only placement (A178) is the follow-up floor probe, and A184 re-evaluates MTP1 with headroom.

## 18:54 MTP1 with headroom is lossless and faster than MTP0

A184 = the graph MTP1 lineage (A120/A135) with the same expert offload (13.78 GiB per rank), the USB checkpoint copy and overlay `08df70ea`. Both exact-2K requests reproduce the MTP0 authority ids (`afffd211…`): r1 20.42 tok/s, r2 28.52 tok/s (MTP0 with headroom: 25.1-25.2). The two-token step is 57.7 ms forward plus 2.5 ms draft, where the same step cost 120-220 ms under paging (A143), so MTP1's "0.60x on real text" was paging, not the draft. Allocator reserved 30.93 GiB with the device again full to the byte, so MTP may want a little more budget. A185 (MTP1 headroom on the realistic suite) and A186 (MTP2 with headroom) are queued after the certification battery and the floor probe.

## 19:28 A178: the embedding alone is not enough headroom

A178 (budget 12.25 GiB: embedding + PLE, 12.22 GiB offloaded, the lineage's original "PLE plus embedding" placement) keeps the hash but runs at 14.58 / 15.97 tok/s at exact 2K, i.e. still in the paging regime (A175 14.42). One expert layer (A181, 0.88 GiB freed) is the smallest placement that ends the paging; the floor lies between 0.3 and 0.9 GiB of freed VRAM.

## 20:08 A185: MTP1 with headroom on the realistic suite is lossless and edges past MTP0

A185 (the A184 identity) passes the fixed cold realistic gate at **25.933214 tok/s** class-balanced median (all-prompt 26.34, p10 23.31, wall 25.09, TTFT median 0.86 s), with all twelve row hashes equal to the approved MTP0 A134 run. The same MTP1 line scored 8.66 class-balanced under paging (A135), so the withdrawn "MTP1 slower on real text" conclusion was a paging artifact; the draft costs ~2.5 ms per step and the two-token step is 57 ms. MTP0 with headroom is 25.27 on the same suite, so MTP1 is a small net gain at this budget; the MTP line is reopened (A186 = MTP2 with headroom queued).

## 20:27 A187: the certification battery passes on the promoted overlay

The frozen client's W13-N32 verifier also hashes the MoE source files, so the diagnostic overlay `08df70ea` can never pass it (A183, three launches). Publishing on the promoted overlay `2169dbfe` with nothing but the placement flags changed is the stronger claim anyway. A187 (battery) passed every gate: 6/7 quality with the inherited miss, 16/16 repeat, exact needle, exact-2K `afffd211…` at 25.43/25.43 (TTFT 12.6 s, was 58), exact-4K `c6193cc6…` at 25.43/25.40 (TTFT 25 s, was 100; rate was 12.9). See the [A187 note](2026-09-05-tp4-mtp0-a187-certification-battery-headroom-result.md). A188 (realistic suite at `2169dbfe`) is the LocalMaxxing run.

## 20:52 published: LocalMaxxing run `cmtp3g14502cun701y5ey93rh` approved at 25.617613 tok/s

A188 (realistic suite on the promoted overlay `2169dbfe`, headroom placement) passed the gate at 25.617613 tok/s class-balanced (all-prompt 25.88, p10 25.82, wall 24.83, TTFT median 0.59 s), all twelve row hashes equal to the approved A134 run. Attestation `20260905-tp4-mtp0-a188-promotion-attestation.json` binds the suite JSON to the A187 battery and the three-server exact-2K pair; payload queue `20260905-tp4-mtp0-a188-localmaxxing-payload-queue.json`; submission approved on the first attempt (HTTP 201). The ledger, results packet, top README row, index research-preview paragraph, model page result strip and CURRENT.md are updated. The prior approved row (14.43, `cmtn32b2w000tmm01t7j2wlpn`) stays listed; nothing was lowered or overwritten.

## 21:08 A186: MTP2 with headroom is lossless but no faster than MTP1

A186 (graph MTP2 lineage A139/A140 with the same expert offload, USB checkpoint, overlay `08df70ea`) reproduces the MTP0 authority ids on both exact-2K requests at 19.72 / 25.82 tok/s, against MTP1's 20.42 / 28.52 (A184) and MTP0's 25.4 (A187). The three-token step costs more than its extra accepted token buys at this budget, so MTP1 is the speculative depth to certify; MTP2 stays research.

## 21:31 A190: the MTP1 headroom line passes the certification battery

A190 = the MTP1 lineage's frozen client on its own overlay `1b2a17c1` (the head the W13-N32 verifier accepts) with the headroom flags and the USB checkpoint. Every gate passed: 6/7 quality with the inherited miss, 16/16 repeat, exact needle; exact-2K `afffd211…` at 28.27 / 28.73 tok/s (MTP0 headroom 25.43), exact-4K `c6193cc6…` at 27.31 / 30.26 (MTP0 headroom 25.4; the paged MTP0 line was 12.87); short rows 35.3. Both depth hashes are the MTP0 line's own two-server authorities, so MTP1 is lossless at every measured pin. A189 (realistic suite, same identity) is the LocalMaxxing run for this line.

## 21:56 published: lossless MTP1 headroom line approved, run `cmtp5u0ip02eln701lntsl2ns` at 27.048435 tok/s

A189 (MTP1 lineage overlay `1b2a17c1`, headroom flags) passed the fixed cold realistic gate at 27.048435 tok/s class-balanced (all-prompt 27.53, p10 24.12, wall 26.05, TTFT median 0.96 s), all twelve row hashes equal to the MTP0 rows; attestation binds it to the A190 battery and the A184/A190 exact-2K pair. Approved on submission. Ledger, results packet, README, index, model page and CURRENT.md updated; both prior rows stay listed.

## 22:19 A191: the MTP1 line needs the larger offload budget

A191 (MTP1 lineage, budget 12.5 GiB → 12.8 GiB offloaded: embedding + layer-0 experts + PLE, 0.88 GiB of headroom) keeps the authority ids but runs at 9.43 / 9.66 tok/s at exact 2K: the M=2 step, its draft buffers and the larger KV fill the card again and the driver pages. MTP0 is fine at this budget (A181, 35.8 ms); MTP1 needs the 13.4 GiB budget it was certified with (13.78 GiB offloaded). The headroom floor is workload-dependent, so the budget is part of each line's identity.
