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
