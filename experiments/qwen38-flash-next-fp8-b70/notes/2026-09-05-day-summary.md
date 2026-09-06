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

A191 (MTP1 lineage, budget 12.5 GiB → 12.8 GiB offloaded: embedding + layer-0 experts + PLE, 0.88 GiB of headroom) keeps the authority ids but runs at 9.43 / 9.66 tok/s at exact 2K: the M=2 step, its draft buffers and the larger KV fill the card again and the driver pages (memory note: allocator reserved 31.908 GiB against 31.891 GiB of device memory, the first run where the pool itself exceeds the card). MTP0 is fine at this budget (A181, 35.8 ms); MTP1 needs the 13.4 GiB budget it was certified with (13.78 GiB offloaded). The headroom floor is workload-dependent, so the budget is part of each line's identity.

## 22:37 A192: the honest sub-op split of the un-paged step

A192 = the eager lineage (USB checkpoint, overlay `08df70ea`) with the headroom placement and LEVEL-3 sub-op events on real routing. The synchronizing hooks inflate the step to 389 ms, so only the event timings count: the two MoE GEMMs sum to 11.4 ms (w13, 0.21 ms/launch) and 8.2 ms (w2, 0.17 ms/launch) per step, matching the offline kernel cost, and the all-reduce events (33-35 ms) are almost entirely rank skew under per-op synchronization (sum of max-min across ranks 31 ms). Against the 37 ms graph step this puts the MoE GEMMs at roughly 20 ms and everything else (GDN, QSA attention, hyper-connection mix, norms, 49 all-reduces, sampler) at roughly 17 ms. The w13 launch moves 33 MB in 0.21 ms (~160 GB/s, a third of the card's bandwidth) at M=1, so the decode-shaped MoE GEMM is the next real lever; the split-K and GEMM-config negatives (A155, A169, A170) were measured under paging and deserve a re-screen with headroom.

## 22:56 A193: split-K 4 re-screened with headroom is exact and neutral

A193 (the A179 identity plus `VLLM_XPU_MOE_SPLIT_K=4`, `VLLM_XPU_MOE_SPLIT_K_MAX_TOKENS=40`) keeps the authority hash at 25.15 / 25.18 tok/s with a 37.2 ms step, i.e. the same as without split-K (A179/A180 25.13-25.20, 37.0 ms). The paged-era negative (A169) stands for the right reason now: at M=1 the two MoE GEMMs are not bandwidth-bound on a resident weight set either, so splitting K does not help. A194 (split-K 8) follows for completeness; the next MoE lever is the M=1 tile configuration (the W13-N32 map was selected under paging, A155's config negative too).

## 23:13 A194: split-K 8 with headroom, exact and neutral

A194 (`VLLM_XPU_MOE_SPLIT_K=8`) keeps the authority hash at 25.08 / 25.07 tok/s with the same step as A179/A193. Split-K is closed as a lever on this model: exact at 4 and 8, never faster, with or without paging. The offline M=1 tile-config sweep (54 candidates: block N 32/64/128, W1 block 16/32/64, warps 4/8, stages 2/3/4, hot clocks) runs next on card 0.

## 23:22 offline M=1 tile-config sweep: the W13-N32 map is already the optimum

54 configs (block N 32/64/128 × W1 block 16/32/64 × warps 4/8 × stages 2/3/4) on card 0 with hot clocks and fresh 10-hit routing. Warps 4 is 1.3-4x slower everywhere; stages do not matter; the W1 block does not change the w13 timing in this path; block N 64 with 8 warps is the floor at 0.30 / 0.15 ms per launch and the shipped map (N 64, W1 32, warps 8, stages 4) sits on it. No tile change beats it; the next MoE lever has to change the kernel's shape of work (fused w13→silu→w2 for M=1, or fewer launches), not its tiles. Data: `../data/20260905-b70-moe-m1-tile-config-sweep-hot-card0.log`.

Layer-level split from A192 (per-op synchronization, so proportions only): mlp 171 ms, hyper-connection mix 88, GDN attention 69, QSA attention 55 per step across 48 layers, i.e. the MoE block is ~45% and the three non-MoE blocks ~55% of the synchronized step; in graph replay the MoE GEMMs alone are ~20 of 37 ms, so the non-MoE blocks (many small launches) shrink most under the graph. The hyper-connection mix is the largest non-MoE block and is elementwise work, a candidate for fusion once the MoE lever is spent.

## 23:30 cold-expert census: most experts are never touched on a trajectory

From the A168 top-k dump (4,848 decode rows of a 2K request, 48,480 hits): 14,310 of the 24,576 (layer, expert) pairs are never hit, the coldest 40% of experts per layer receive 0.00% of hits, and per rank (linear placement) the coldest 13 of 128 local experts per layer receive 0.00%. The headroom the driver needs (about 1.6 GiB per rank, 2.7 expert layers) could therefore come from host-resident cold experts at essentially zero decode cost instead of 2.7 ms per step of PCIe reads, if the cold set is chosen from a broad sample. A195 dumps the top-k ids over the whole realistic suite on the headroom identity for that census; the placement change itself is a split-storage MoE launch (resident rows and host rows into one intermediate buffer, bit-exact) that needs a re-oracle.

## 23:45 per-expert host placement: patch written, test queued

Overlay (uncommitted until the offline test passes): `fused_moe_kernel` takes an optional per-expert base-address table (`USE_B_TABLE`; `b_base = table[max(e, 0)]` cast to a pointer, then the unchanged tiles, K loop and scale indexing), the launch passes `B._q38_base_table` when present, and `vllm/q38_expert_placement.py` splits each MoE layer's `w13_weight`/`w2_weight` into resident device rows and pinned host rows (UVA view) after the FP8 post-load step, per a JSON placement from `Q38_EXPERT_HOST_PLACEMENT`. Repo tools: `equivalence-and-timing-moe-expert-placement.py` (bit-identical outputs on 32 routings for table-no-host and table-half-host against the resident reference, then event timing for resident-only and host-hitting routings) and `build-q38-expert-host-placement.py` (never-hit experts from the top-k dumps, coldest first, capped by host GiB per rank). See the [design note](2026-09-05-per-expert-host-placement-design.md). A195 (top-k dump over the realistic suite) is running; the test follows it on card 0.

## 23:50 per-expert placement: bit-identical, resident rows at reference speed

The offline test passes: with a per-expert offset table the fused MoE kernel produces bit-identical outputs on 32 routings both with no host rows and with half the experts host-resident, and resident rows run at the reference speed (0.226 / 0.146 ms per launch against 0.224 / 0.144) once the loaded offset carries a `tl.multiple_of(off, 256)` hint; without the hint (or with an int-to-pointer cast) the kernel lost its vector loads and ran 3x slower on resident rows. A routing that hits three host-resident experts per call costs 0.59 / 0.23 ms, about 0.1 ms per host expert hit, so a rarely-hit cold set is close to free. Committed to the overlay as `567117d1`. A195 (graph lineage) could not run the top-k dump under graph capture; A197 repeats the census on the eager lineage with headroom at the new head. Data: `../data/20260905-b70-moe-expert-placement-equivalence-timing.txt`.

## 00:18 A197 census over the realistic suite

A197 (eager lineage, headroom, top-k dump over the whole realistic suite; 250,000 tensors ≈ 5,200 decode rows × 48 layers; outputs identical to A134): 3,141 of 24,576 (layer, expert) pairs (12.8%) are never routed to, the coldest 5% of experts per layer receive 0.002% of hits and the coldest 10% receive 0.035%. A 2.0 GiB per-rank host placement needs 6.8% of each rank's experts, so it is filled entirely from never-hit experts of the union census (A168 + A197); on other prompts a placed expert that does get hit costs about 0.1 ms per hit instead of a driver page migration. The eager rate with the dump hook (5.2 tok/s) is the hook's cost, not the line's.

## 00:30 A196 (placement) running; clean placement branch prepared

A196 = the promoted PLE-only identity plus the 2 GiB/rank cold-expert placement at overlay `68a410ba` (diagnostics + placement). For publication, the placement patch is re-applied on the promoted overlay alone as branch `q38-placement` (`c5228465`, three files, no diagnostics; `fused_moe.py` sha `4e611de0…`); the W13-N32 verifier's source contract has to learn that head and hash before the frozen client can certify it, which is a certification-policy change to be reviewed rather than slipped in.

## 00:36 A196: placement applies and stays bit-exact, but the split fragments the pool

A196 (promoted PLE-only identity + 2 GiB/rank cold-expert placement, overlay `68a410ba`) applied the placement on every layer (1.86-1.91 GiB per rank host-resident) and keeps the authority hash on both requests, but runs at 19.17 / 21.07 tok/s with a 44.9 ms step. The memory note explains it: allocator allocated 29.78 GiB (the weights did shrink, as in A179), but reserved 30.73-30.79 GiB and device free 0.01 GiB, i.e. copying each layer's resident rows into a new tensor while the original was alive left about 1 GiB of fragmentation in the caching pool and the card full again, so the driver pages partially. Fix: a two-phase split that stages every layer's resident rows to pinned host memory, frees all originals, empties the cache, then reallocates the resident tensors compactly and copies back.

## 00:45 placement split rewritten to free-then-reallocate; A199/A200 queued

The per-layer split now stages a layer's resident and cold rows on the host, frees the original device tensor, and only then allocates the compact resident copy, so it lands in the block the original released; `empty_cache` runs once after the last placed layer and logs the allocator's reserved size. A global two-phase staging was rejected because it would pin about 115 GB of host memory across the four ranks. A199 re-screens the promoted MTP0 identity with the placement (target: reserved ≈29.9 GiB, hash `afffd211…`, step ≈34 ms); A200 does the same for MTP1. The clean certification branch `q38-placement` carries the same module.

Certification prep for the placement line (held until A199 decides): a verifier draft that accepts `q38-placement` head `2780ab24` with its `fused_moe.py` hash, and generator makers for A201 (frozen-client battery) and A202 (realistic suite) on that head with the PLE-only offload plus `Q38_EXPERT_HOST_PLACEMENT`; both dry-run validated and removed again. Applying the verifier change is a certification-policy edit and will be committed as such.

## 01:00 A199: per-layer free-then-reallocate still leaves the pool at 31.2 GiB

The allocator gives each expert tensor a dedicated large segment; freeing it and allocating the smaller resident copy puts the copy inside the same segment, so the driver never gets the hole back (reserved 31.15-31.21 GiB after `empty_cache`). Version 3 records the placed layers and, on the last one, has the ranks take turns (gloo barrier) staging all their resident rows on the host, freeing every original, emptying the cache and reallocating compact tensors; the transient host staging is ~28.7 GB per rank in turn. A204 (MTP0) and A205 (MTP1) re-screen it; the clean branch `q38-placement` is at `df61032c` with the same module.

## 01:18-09:42 eighth host freeze; 09:53 A207 launched

A204's rank 0 was OOM-killed by the host while pinning 28.7 GB for the v3 staging (about 24 GB were available next to the PLE offload); the frozen launcher's host reset for A207 (swap off/on, cache drop) then ran seconds later and the kernel went into soft lockups (a CPU stuck for 28,212 s by the end), with `swapoff`, systemd, smartd and a block worker in D state and no disk I/O until the hard restart at 09:42. A207 had never launched. After the reboot: USB remounted, A207/A208 committed, A207 launched in the background with placement v4 (stage one layer, free, empty the cache, reallocate compactly); A208 (MTP1) chained. Lesson: never run the frozen launcher's host reset from a foreground shell, and treat a reset right after killed workers holding pinned memory as a freeze trigger.

## 10:05 A207: placement v4 cannot compact either; post-load compaction is closed

With the per-layer stage → free → `empty_cache` → reallocate order, the allocator still reports 31.15-31.21 GiB reserved (30.24 GiB allocated) after the last placed layer, the same as v2. The loader packs the expert tensors into shared allocator segments, so a freed expert tensor never lets a segment go back to the driver and the compact copy cannot land outside it. Three variants (copy-while-alive, free-then-reallocate, free + cache empty + reallocate) all end at ~31.2 GiB reserved; the global stage-everything variant (v3) is ruled out by host memory. A206 tries the expandable-segments allocator, which returns physical pages at page granularity inside segments; if that distorts decode timing (an earlier memory notes 2-5x on B70), the remaining route is placing experts at load time through the weight loader so the device tensors are created at their resident size.

## 10:28 A206: expandable segments have no effect on the XPU allocator; load-time placement next

With `PYTORCH_ALLOC_CONF=expandable_segments:True` the placement run lands on the same figures as A207 (31.2 GiB reserved after the last placed layer, 30.7 at the decode note, 0.014 GiB free), so the setting is ignored by the XPU caching allocator here. Placement v5 moves the split to weight-creation time: a placed layer's `w13_weight`/`w2_weight` are created at their resident size plus pinned host rows, the weight loader writes each expert through `row_view()` (cold experts straight to host memory), and the post-load hook only re-attaches the offset tables; the device pool is then compact by construction. It lives on the overlay branch `q38-placement-v5` (`ba1f4cde`); the offline check `test-q38-expert-placement-loadtime.py` runs before A209 (promoted MTP0 identity + load-time placement).

## 10:29 load-time placement passes the offline check

`test-q38-expert-placement-loadtime.py` on card 0: a placed layer created at resident size (110 of 128 rows on the device, 18 cold rows in pinned host memory), every expert written through the loader's `row_view()`, and `fused_experts` bit-identical to the full resident reference on 48 routings, 22 of which touch host-resident experts. A209 (promoted MTP0 identity + load-time placement, overlay `q38-placement-v5`) relaunched after a first launch tripped on a worktree holding the branch.

## 10:30–10:40 09-06 — A209 negative, A210 relaunch (load-time placement v5)

- **A209 crashed in model construction**: `q38_expert_placement.prepare_layer` raised `RuntimeError: Only dense CPU tensors can be pinned` from `torch.empty(..., pin_memory=True)`. The offline check had passed with the same code because it ran with the CPU default device; vLLM constructs the model under the XPU default device, so an allocation without an explicit `device="cpu"` lands on the card and cannot be pinned. Negative kept: load-time hooks must name the host device explicitly.
- Fix: both pinned allocations in `vllm/q38_expert_placement.py` now pass `device="cpu"`. Branch heads: `q38-placement-v5` c4f921f5 (diagnostic lineage), `q38-placement-clean-v5` 21633cea (certification lineage; `fused_moe.py` unchanged, so the verifier draft's per-head source hash still applies).
- **A210** = A209 with the fix (promoted MTP0 identity, exact-2K r1/r2, table kernel + load-time placement of 2 GiB/rank of never-hit experts, port 19880). Launched 10:32 in the background; chain55 restores `q38-exact-verify` after the run.
- Prep during the load window: A201 (frozen-client battery) and A202 (realistic suite) regenerated at the clean head 21633cea; both validate. A201 pins the *current* verifier sha, so it must be regenerated once the verifier policy commit (accept 21633cea with its `fused_moe.py` hash) lands — that commit waits for A210 to hold the hash.
- Overlay-restore race: the previous chain (chain54) was still alive and restored `q38-exact-verify` 27 s before A210's launch; the packet launch script checks out its pinned branch itself, so A210 started on `q38-placement-v5` regardless. Rule kept anyway: kill the previous restore chain by pid and confirm it is gone before the next launch on a diagnostic branch.

## 10:50–11:10 09-06 — A210 positive (small), A212 screen, the lossless line becomes a recipe

- **A210**: load-time placement of 2 GiB/rank never-hit experts holds both authority hashes (exact-2K `afffd211…`, `e39e32c3…`); exact-2K r1/r2 20.70/21.05 vs A207 20.29/20.62 (+2%). Allocator reserved 29.87 GiB (30.77 before), device free 0.124 GiB. A211 was lost to a launch-order mistake (the overlay restore chain of the previous run flipped the branch; the packet pins the *current* overlay head and does not check out its branch); **A212** = same with 3.5 GiB/rank (543–587 never-hit experts per rank) launched 10:53 on `q38-placement-v5`; loaded at 28.9–29.05 GiB.
- The user asked whether the lossless line is a released recipe, image, and non-experimental repro entry. It was not: only the `research-status` MTP3 guide (Aug 27 identity) existed, no Dockerfile, no package, no Recipes-page entry, overlay heads unhosted. Published now (commit "repro(qwen38): lossless MTP1 lab-replay guide…"):
  - `patches/qwen38-flash-next-fp8-b70/vllm-lossless-mtp1-1b2a17c1/`: 55-commit series + bundle over public `76cfe1cd`, `verify-series.sh --apply` re-creates tree `1cb86e07`;
  - `patches/qwen38-flash-next-fp8-b70/oneccl-4ceafd1-b70-public/`: byte receipt; release `qwen38-flash-next-oneccl-4ceafd1-b70-public-20260906` (zst `34dc2cad…`, verified by direct download);
  - `repro/qwen38-flash-next-fp8-tp4-mtp1-lossless-b70-27tps-20260905/` (`lab-replay`): `verify-identity.sh`, `run-record-gate.sh` (derives a fresh attempt from the pinned A189 packet, launches through the frozen launcher, runs the frozen client once, `check-replay-result.py` compares all 12 output pins and every gate with the record), `identity.json`, evidence manifests, untested `Dockerfile`/`container-serve.sh`/`build-image.sh` with `CONTAINER-STATUS.md`;
  - package `candidate` (`packages/…-27tps-20260905`), family packet grade B, coverage registry, `repro/README.md`, `docs/model-recipes.md`, results README link, index preview link; generated pages rebuilt; validators and the 91 tooling tests pass (two count-guard tests updated).
  - Not certified: clean-host install, dependency hash lock, non-originating-host replay, container replay. The record gate itself has not been executed end-to-end yet (it wraps the exact A189 path; first run queued behind the placement work).

## 11:08–11:17 09-06 — A212, the lineage mistake, A213

- **A212** (3.5 GiB/rank never-hit placement, 543–587 experts/rank): hashes hold; exact-2K r1/r2 21.04/21.09; allocator reserved 29.07 GiB, device free 0.53 GiB. Against A210 (20.70/21.05) the extra budget adds nothing: the placement lever plateaus at about +2% **on the PLE-only lineage**.
- **Lineage correction**: A196–A212 were derived from the frozen A78 packet (PLE-only, `--cpu-offload-gb 12.0`, 11.92 GiB offloaded), not from the promoted 13.4 GiB headroom identity. Same harness (`bench-openai-token-depth-suite`, exact-depth 2K, conventional 99-interval tok/s): the 13.4 identity reads **25.43** (A187 r1/r2), the lossless MTP1 line 28.27/28.73 (A190). So placement-on-PLE-only at 21.1 is far below the promoted line: placement replaced only part of the paging, while the 13.4 identity ends it by offloading embeddings plus the layer-0/1 expert tensors (which are hot: read over PCIe every step).
- **A213** = the right experiment: PLE + embeddings offloaded (`--cpu-offload-gb 12.25`, 12.22 GiB, `_selective_ple_embed_budget12p25_uva`), hot experts resident, 3.5 GiB/rank of never-hit experts host-placed at load time (v5 head c4f921f5). Generator `rewrite-q38-a78-to-a213-placement-ple-embed-12p25.py` derived from the A188 generator. First launch failed on the overwrite guard because `ATTEMPT=188` survived the text derivation (packet names, port and `attempt188` were renamed; the `ATTEMPT=` assignment was not); fixed and relaunched 11:15 on port 19883. Decision rule: A213 exact-2K vs 25.43; if higher with hashes held, certify this identity (A201/A202-style packets need the same offload change), then port to MTP1.
- Container route: first build failed because the stage tar's members sit under the archive prefix, not under `vllm_xpu_kernels/`; the Dockerfile now installs the stage through the mtp3 guide's frozen `prepare-runtime.py`; rebuild running.

## 11:31–11:40 09-06 — A213 negative resolved: the placed layers lost the tuned MoE map

- **A213** (PLE + embeddings offloaded at 12.25, hot experts resident, 3.5 GiB/rank never-hit placement, v5): hashes hold, exact-2K r1/r2 21.19/21.18, allocator reserved 28.78 GiB, device free 0.82 GiB. Same rate as A212 despite the identity change, and 17% below the 13.78 identity (25.43, A187) with more free memory than any run. The same-harness table (A151–A213) shows every placement head at 19–21 regardless of headroom.
- **Root cause**: `fused_experts` keys the tuned-config lookup on `w1.size()`; a placed layer's weight tensors are resident-sized (110–128 rows), so `E=110…` has no file in `moe-m1-w13-n32` and the layer silently takes the default config. A213's log carries eight "Using default MoE config" warnings (one per distinct resident count); A187's log has the single `E=128,N=640` selection. The sweep that produced the map showed the shipped config matters by exactly this kind of margin.
- **Fix** (clean head `823d4e42`, cherry-picked onto v5 as `2a7f1ea3`): the lookup uses the layer's logical expert count (`_q38_num_experts`) when the placement table is present. Verifier policy moved to `823d4e42` with its `fused_moe.py` hash. A214 (clean head before the fix) was stopped during load as a foregone negative.
- **A216** = frozen-client certification battery (A187 lineage) at the A213 identity on `823d4e42`, launched 11:38 on port 19886 (wait-and-run driver; client pins the verifier sha). **A217** = realistic suite (A188 lineage) at the same identity, generated and validated, launches after A216. Decision: A216 exact-2K vs 25.43 and both authority hashes; then A217 for the LocalMaxxing metric vs 25.62.
