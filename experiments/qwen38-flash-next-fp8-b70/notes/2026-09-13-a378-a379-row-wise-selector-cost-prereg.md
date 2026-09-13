# Preregistration: A378/A379 - what the two remaining exactness selectors cost at two rows

## Question

On the exact-mode line the two-row verify step's unattributed remainder is 12.7 ms against 6.5
at one row (A369-A373). Two exactness selectors live there: `VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=2`
(one tensor-parallel all-reduce per row instead of one [2,N] collective; A104/A105 showed the
[2,N] collective is not bit-equal to two [1,N] ones) and `VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=2` (the
hyper-connection grouped RMSNorm variance per row; A110/A111). How much of the 6.2 ms second-row
excess is theirs?

## Arms

MTP1 diag branch `f1d5cd88`, stage v2, exact-mode exports, step timing, three exact-2K rows:
- A378: `VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=0` (batched all-reduce; outputs change), port 19991.
- A379: `VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=0` (batched HC norm; outputs change), port 19992.
Timing only; hashes are expected to differ from `afffd211…`. Control: A369 (33.69 ms).

## Predictions

The all-reduce runs once per layer per residual site; at two rows the row-wise selector doubles
the collective count. If A378 recovers 3 ms or more, a row-invariant two-row collective (two
reductions in one submission that reproduce the per-row arithmetic) is the next kernel-level
lever, the same shape of fix as the GDN one. A379 is expected small (the norm is cheap) but the
per-row launch pattern is the same. If neither moves the step, the remainder is in the dense
projections at M=2 and the next arm zeroes those.

## Stop rules

Server fails health; rows fail. Timing arms only; nothing is promoted from them.
