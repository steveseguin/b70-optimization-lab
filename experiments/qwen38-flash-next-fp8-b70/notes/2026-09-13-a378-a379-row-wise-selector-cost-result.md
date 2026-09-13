# Result: A378/A379 - the two exactness selectors cost 1.5 ms and 0.0 ms at two rows

Preregistration: `2026-09-13-a378-a379-row-wise-selector-cost-prereg.md`. MTP1 diag branch `f1d5cd88`,
stage v2, exact-mode exports, step timing over three exact-2K rows each; control A369 (same packet,
selectors at 2).

| arm | selector off | forward M=2 median (min) ms | sample | draft | exact-2K hash |
|---|---|---|---|---|---|
| A369 control | none | 33.69 (31.90) | 0.89 | 2.22 | `afffd211…` (certified) |
| A378 | `VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=0` | 32.22 (30.50) | 0.89 | 2.15 | `54771cfd…` |
| A379 | `VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=0` | 33.66 (31.89) | 0.89 | 2.23 | `54771cfd…` |

Medians over 88/84 two-token steps per arm; all three rows of each arm agree with each other.

## Reading

- The row-wise all-reduce is worth 1.47 ms of the two-row step (4.4%), under the 3 ms the
  preregistration set for making a row-invariant two-row collective the next kernel lever. It stays
  on the list, behind the larger term below.
- The row-wise HC norm is free (0.03 ms, inside the noise). Nothing to recover there.
- Both arms change the outputs (they were expected to; A104/A105 and A110/A111 established the
  batched forms are not bit-equal). The two arms produce the same changed hash: the divergence from
  the certified trajectory happens at the same near-tie position under either perturbation, after
  which the greedy path is identical. Neither arm is promotable; both are timing evidence only.
- Remainder accounting on the exact-mode line, two rows, 2K: 33.69 ms = MoE 14.2 + QSA 4.7 + GDN 2.1
  + HC ~0 + all-reduce row-wise excess 1.5 + 11.2 unattributed (against 6.5 at one row). The
  unattributed part is now the largest per-row term: the dense projections (QKV/O, gate/up of the
  shared path, LM head, the draft-head forward at M=2) and the graph-replay glue. The next diag arm
  zeroes those one family at a time with a new skip switch on the diag branch (preregistered
  separately), the same zero-input differencing the A369-A373 decomposition used.
