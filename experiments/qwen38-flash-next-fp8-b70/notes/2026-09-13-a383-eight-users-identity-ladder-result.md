# Result: A383 - eight users on the promoted MTP0 line: 81.6 tok/s aggregate, not output-identical past one user

Preregistration: `2026-09-13-a377-eight-users-identity-ladder-prereg.md` (A377 re-run as A383 with the
8 GB host floor). Overlay `2a372e86`, served stage, W13-N64 map, never-hit + max-count-2 placement,
`max_num_seqs=8`, KV 1,412,136,960 bytes, decode graph capture sizes [1, 2, 4, 8], row-wise all-reduce
and HC-norm selectors at 8 rows, port 19996. Server healthy at 10:40:12 UTC (host trough 8.10 GB).
`scripts/bench-openai-concurrency-oracle.py`, completions mode, the fixed 12-prompt realistic suite, 128
tokens with `ignore_eos`, temperature 0, `--require-output-identity` (each concurrent completion's token
ids must equal its sequential oracle on the same server), two repeats.

| users | repeat 1 aggregate tok/s | exact vs oracle | repeat 2 aggregate tok/s | exact vs oracle |
|---|---|---|---|---|
| 1 | 30.13 | 1/1 | 30.18 | 1/1 |
| 2 | 10.04 (first two-row batch: 25 s) | 0/2 | 47.36 | 1/2 |
| 4 | 57.34 | 0/4 | 59.18 | 1/4 |
| 8 | 77.68 | 0/8 | 81.62 | 0/8 |

Oracle exit code 4 (identity gate failed); classification `output-isolation-qualified-shape-variant`
(every request complete, cache zero, outputs differ from the sequential oracle).

## Reading

- Concurrency 1 is exact (the single-user oracle reproduces itself). At 2, 4 and 8 users the outputs
  are not identical to the single-user outputs: 2 of 28 concurrent completions matched. First
  divergence indices range from token 1 to 122 and depend on the prompt (c=8 r2: 97, 113, 95, 42, 100,
  14, 56, 11), so this is systematic numeric difference at M>1, not late near-tie flips. The preregistered
  cause stands: the MoE tuned tile map keys on the row count, and the M=2/4/8 configurations change
  accumulation order; the row-wise selectors cover only the all-reduce and the HC norm.
- Throughput: aggregate decode scales 30 -> 47 -> 59 -> 82 tok/s from 1 to 8 users (2.7x at 8; MoE
  activates more experts per step, so sub-linear as predicted). The first two-row batch paid a 25 s
  one-time cost (graph first touch at that capture size); every later batch is steady.
- Publication: per the preregistration the "Many users" cell is the largest exact concurrency, which is
  1, so the cell stays withheld on the front page with the measured aggregate stated in its note; the
  numbers are recorded in the results README as an output-variant measurement. No family measurement
  entry (those carry lossless-within-line evidence only).
- Next lever (lossless by construction if it works): make the MoE GEMM batch-invariant by serving
  M=2..8 with the M=1 tile configuration (same BLOCK_SIZE_K, no split-K: each row's K-loop order then
  matches the single-row kernel), keep the row-wise selectors at 8, and re-run this ladder. If the
  ids then match at every concurrency, the eight-user cell becomes lossless at whatever rate the
  M=1 tiles give at M=8; if not, the remaining term is in the attention kernels' batched paths.

## Addendum (11:15 UTC): the row-wise selectors were inert on this head

A read-only search of the served trees (agent report, 2026-09-13) found that
`VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS` and `VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS` do not exist at the MTP0
head `2a372e86` (verified: `git grep` at that revision is empty for both; they were added in the MTP1
lineage, commit `8ca2cbc28` and its HC-norm companion, and `2a372e86` is not an ancestor of `6d872457`).
A383 therefore ran the tensor-parallel all-reduce batched over 2-8 rows, the path A104/A105 showed is
not bit-equal to per-row reduction. The measured aggregates stand; the identity failure has at least one
known, fixable cause that the arm did not test. Next arm (A388): the same packet on `2a372e86` plus the
two selector commits cherry-picked (a new MTP0 candidate head; identical arithmetic at one user, so the
single-user pins must reproduce), selectors at 8. If identity then holds at 2-8 users the cell becomes
lossless; if not, the remaining suspects from the search are the oneDNN dense-projection primitive
choice per M (router and LM head logits, a one-ULP change flips a top-k or an argmax) and the HC
gate-mix mean, which the HC-norm selector does not cover.
