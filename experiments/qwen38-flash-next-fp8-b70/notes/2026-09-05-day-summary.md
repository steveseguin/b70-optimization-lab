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

Queue (promoted graph identity, one collective knob each, hash-checked
against the authority, telemetry bypassed): A164
`CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=0` (offline: the same all-reduce
halves, exact), A165 `CCL_SYCL_ALLREDUCE_LL_THRESHOLD=8192` (the
low-latency path, graph-replay correctness retest with oneCCL 4ceafd1),
A166 `CCL_SYCL_ALLREDUCE_ARC=1`. Beyond knobs: balance the per-rank expert
load (routing-aware expert placement across the four ranks) or overlap
the MoE collective.

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
