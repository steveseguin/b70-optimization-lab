# A369-A373: where the 33.7 ms two-row verify step goes on the exact-mode line

MTP1 diag branch `f1d5cd88`, stage v2, the four exact-mode exports, exact-2K rows, step timing.
Preregistration: `2026-09-13-a369-a373-decomposing-the-exact-mode-verify-step-prereg.md`. Each
skip zeroes one block (`Q38_DIAG_SKIP`); its hash differs from `afffd211…` by construction and
matches the same skip on the old line (the switch engaged). The M=1 column is the old line's
single-row decomposition (A340/A349-A353); at one row the exact mode is not exercised.

| block | M=1 step (old line) | cost at M=1 | M=2 exact-mode step | cost at M=2 | M=2 old line (Python serial) |
|---|---|---|---|---|---|
| none (control) | 27.2 | | **33.69** (A369, `afffd211…`) | | 42.7 |
| moe_gemm | 15.9 | 11.3 | 19.47 (A370) | **14.2** | 13.9 |
| gdn_attn | 24.8 | 2.4 | 31.63 (A371) | 2.1 | 11.2 |
| qsa_attn | 22.9 | 4.3 | 28.99 (A372) | 4.7 | 4.4 |
| hc_mix | 24.5 | 2.7 | 33.88 (A373) | ~0 | ~0 |
| sum of the four | | 20.7 | | 21.0 | 29.5 |
| remainder | | **6.5** | | **12.7** | 13.2 |

## Reading

- The GDN verifier-row tax is gone entirely (11.2 -> 2.1 ms, below the single-row 2.4 within
  noise); the exact mode costs nothing measurable over a plain single-row decode of the block.
- MoE is the largest attributed term at two rows (14.2 ms, +2.9 over one row) and is
  weight-bandwidth bound; a two-row-aware dispatch is worth at most that increment.
- The remainder (everything the four zeroings leave: dense projections around both attention
  blocks, norms, the residual-stream glue outside the mix, the row-wise all-reduce and HC-norm
  selectors, sampler-side work) is 12.7 ms at two rows against 6.5 at one: it doubles with the
  second row and is now the largest per-row term (+6.2 ms), ahead of MoE (+2.9).
- Two of the three exactness selectors live in that remainder: `VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=2`
  turns each tensor-parallel all-reduce into one collective per row, and
  `VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=2` computes the hyper-connection RMSNorm per row. The next
  arms (A378/A379) time the step with each selector off (outputs change; timing only) to say how
  much of the 6.2 ms is theirs. If it is most of it, the lever is a row-invariant batched
  implementation (a fused two-row all-reduce / norm that reproduces the per-row arithmetic), the
  same shape of fix as the GDN one.

## Next

A374 (MTP2 on this line), A375/A376 (32K ladder), A377 (eight users) are queued; A378/A379
(selector cost) follow them.
