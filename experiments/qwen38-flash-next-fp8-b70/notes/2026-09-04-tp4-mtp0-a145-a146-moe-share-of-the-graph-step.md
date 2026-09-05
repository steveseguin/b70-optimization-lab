# A146/A145: the MoE block is three quarters of the promoted decode step (2026-09-04, 23:12-23:47)

Graph MTP0 identity (A78 lineage: full decode graph, size 1, overlay
`f8c7c0ee` with the timing hooks and the `Q38_DIAG_SKIP` no-op hook, both
inert unless set), one exact-2K request each, `Q38_STEP_TIMING_LOG=10`
(one device sync per logged step, no per-op syncs).

| attempt | change | graph forward per step at 2K (TP0, 13 logged steps) | exact-2K output | rate |
|---|---|---:|---|---:|
| A146 | control, nothing skipped | median **72.7 ms**, mean 69.0, range 44.2-90.5 | `afffd211...` (authority) | 14.75 tok/s |
| A145 | `Q38_DIAG_SKIP=moe`: the MoE runner returns zeros instead of calling the expert path (router top-k, alignment, quantization, both grouped GEMMs, sum; the TP all-reduce after it stays) | median **19.1 ms**, range 19.08-19.17 | garbage by construction | 46.0 tok/s |
| A144 (MTP1 graph identity, three selectors, size-2 steps; control is A127 at mean 181 ms, 144-255) | `Q38_DIAG_SKIP=moe` | median **32.9 ms**, range 32.86-32.96 (drafter 2.0) | garbage by construction | 25.9 tok/s |
| A148 (overlay `edfd2155`) | `Q38_DIAG_SKIP=moe_gemm`: only the two Triton grouped-GEMM launches skipped (output zeroed); routing, alignment, activation quantization, sum and all-reduce kept | median **22.4 ms**, range 22.35-22.6 | garbage by construction | 40.0 tok/s |

The MoE block costs about 50-54 ms of the 71-73 ms step, three quarters
of it, and all of the step's variance (the remainder of the network is a
flat 19.1 ms). At M=2 (A144 against A127) the MoE block is about 150 ms of
the 181 ms verification step, over 80% of it; the rest of the two-row
network, serial verifier GDN rows included, is a flat 32.9 ms, 13.8 ms
more than the one-row step.

A148 splits the block: the two grouped GEMMs (w13: N=1280, K=2560; w2:
N=2560, K=640) are about **50 ms** of the 72.7 ms step and all of its
variance; every other MoE kernel together (router GEMM, top-k, block
alignment, per-token-group quantization, SiLU, sum, the TP all-reduce)
about 3.3 ms. Per rank and layer the two GEMMs stream about 12 MB of
expert weights in about 1.05 ms, an effective 11 GB/s, forty times off the
card's bandwidth: the launch is latency-bound (about a hundred valid
programs per GEMM, each walking K in serial 128-wide steps), which is what
the split-K variant attacks. Streaming the local experts a token touches (about 2.5 of
the 128 experts per rank per layer, 4.9 MB each) is a few ms per step at
this card's bandwidth, so the block runs an order of magnitude off the
memory bound: the Triton fused MoE at M=1 launches about 100 valid
programs per GEMM per rank (`BLOCK_SIZE_M` 16, `BLOCK_SIZE_N` 32/64,
split-K forced to 1) and each walks K=2560 in 20 serial 128-wide steps.

A147, the platform XPU FP8 MoE backend (`--moe-backend auto`), is a
negative on this stack: the overlay's `xpu_moe.py` calls an arch-probe op
the staged `vllm_xpu_kernels` build does not export and constructs the
kernel class with arguments the staged interface lacks, whose block-FP8
grouped-GEMM path is INT8-repurposed (the 2026-08-26 interface audit).
The native backend needs a kernel rebuild plus the block-FP8 scale path.

Next: A144 (graph MTP1, `Q38_DIAG_SKIP=moe`) for the M=2 share, A148
(`Q38_DIAG_SKIP=moe_gemm`, overlay `edfd2155`: only the two grouped GEMM
launches skipped) to split the block between the GEMMs and the routing,
alignment, quantization and sum kernels around them; then a decode
specialized small-M MoE kernel (more programs per GEMM, deterministic
split-K with a fixed-order reduction), re-oracled at promotion because its
accumulation order is new.

Data: `../data/20260904-tp4-mtp0-a146-graph-step-timing-2k.json`,
`../data/20260904-tp4-mtp1-a144-graph-step-timing-skip-moe-2k.json`,
`../data/20260905-tp4-mtp0-a148-graph-step-timing-skip-moe-gemm-2k.json`,
`../data/20260904-tp4-mtp0-a145-graph-step-timing-skip-moe-2k.json`,
`../data/20260904-tp4-mtp0-a14{5,6}-exact-depth-2k-r1.json`.
