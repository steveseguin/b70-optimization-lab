# R210 / R210b / R210c: why INT4 AutoRound is not repeat-exact, and what padding fixes (2026-09-04)

Context: R208 (INT4 AutoRound on the R187 whole-graph stack) failed G1 at 7/12; R209 within-server repeats gave 8/12 with the
four divergent prompts flipping at decode indices 60-231. This census isolates the ARK `woqgemm` W4A16 kernel
(auto_round_kernel 0.9.2.1, XPU lib) on four real layers of devan-carlin/Qwen3.8-27B-int4-AutoRound and asks three questions
per row count M: is the kernel bit-identical run to run, does row 0 change with M, and what does a call cost.

Scripts: `scripts/qwen38-int4-ark-woqgemm-census.py` (R210), `scripts/qwen38-int4-ark-pad-census.py` (R210b),
`scripts/qwen38-int4-ark-smallm-timing.py` (R210c). Data: `data/2026-09-04-qwen38-int4-ark-*-r210*-result.json`.
Image: r156 (contract image of the FP8 lane), single B70, ZE_AFFINITY_MASK=0.

## Findings

| question | answer |
|---|---|
| run-to-run identical, M <= 16 | yes, all four layers |
| run-to-run identical, M in [32, 256] | **no** on down_proj, gate_proj, q_proj (out_proj: 256 also fails); this is the prefill band that R209 blamed |
| run-to-run identical, M = 512, 1024 | yes, all four layers |
| row 0 invariant across M (1 vs 2 vs 6 vs 16) | **no** at every M on every layer: the kernel's reduction order depends on the batch shape |
| zero-pad 60 -> 512 rows: run-to-run identical | yes, all four layers |
| zero-pad 60 -> 512 rows: row 0 equals a true M=512 call | yes, all four layers |
| zero-pad 60 -> 256 rows | deterministic on three layers, **not** on linear_attn.out_proj (K=6144); 512 is the smallest safe class |

Cost per call, microseconds (R210c, 30-call mean after warm-up):

| layer (K x N) | M=1 | M=2 | M=8 | M=16 | M=32 | M=60 | M=512 | M=1024 |
|---|---|---|---|---|---|---|---|---|
| mlp.down_proj 17408x5120 | 135 | 843 | 748 | 754 | 834 | 840 | 1158 | 1638 |
| mlp.gate_proj 5120x17408 | 82 | 751 | 753 | 762 | 796 | - | - | - |
| self_attn.q_proj 5120x12288 | 51 | 539 | 540 | 546 | 568 | - | - | - |
| linear_attn.out_proj 6144x5120 | 29 | 282 | 281 | 282 | 293 | - | - | - |

## What this means

1. **Determinism (G1) is a prefill problem.** Decode rows (M=1 for MTP0, M=depth+1 for MTP) are already run-to-run
   deterministic. The nondeterminism lives in the 32-256 row band that chunked prefill produces for the strict prompts.
   Zero-padding that band to 512 rows (or 1024 for 512 < M < 1024) is bit-identical run to run and identical to the
   natural 512-row result, so it is a pure determinism fix with no numerical change for the padded rows. Cost: about +38%
   on a 60-row prefill GEMM (840 -> 1158 us); decode is untouched. That is the R211 image
   (`docker/r211-ark-prefill-pad.py`, env `VLLM_XPU_ARK_PREFILL_PAD`, default on), patched into vLLM's
   `inc_ark_ops._inc_ark_woq_linear_impl` so both the eager and the whole-graph-compiled paths go through it.
2. **Lossless MTP (G3) is a different problem: the kernel is row-variant.** An M=1 call and row 0 of an M=5 call differ
   in the last bits, so MTP verify steps (M=depth+1) do not reproduce the MTP0 (M=1) logits bit-for-bit and tie tokens can
   flip. The FP8 lane solved the same issue with a fixed-K, batch-shape-invariant GEMM. Padding decode to a fixed class
   would work numerically (pad-16 is row-invariant) but see 3.
3. **ARK has no small-M path.** M=1 runs a GEMV-class kernel; M=2 already lands on the full GEMM tile and costs 6-10x
   more (down_proj 135 -> 843 us, out_proj 29 -> 282 us), flat out to M=16. Every INT4 MTP verify step therefore pays
   roughly 7x per linear layer versus MTP0, which is why INT4 MTP can only lose to INT4 MTP0 on this kernel. Padding
   decode rows to a fixed class inherits the same cliff.

## Consequence for the INT4 lane

The R211 padding makes MTP0 a candidate for repeat-exact G1 (pending the R211 campaign). Making INT4 MTP both lossless and
faster than MTP0 needs a batch-shape-invariant W4A16 kernel for M <= 8 whose per-row cost stays near the M=1 GEMV cost:
dequantize-on-the-fly, fixed per-row K reduction order, one program per (row-block, N-block). That kernel is the INT4
analog of the FP8 lane's fixed-K GEMM and is the next build item after the R211 result lands.
