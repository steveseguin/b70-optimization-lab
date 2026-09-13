# Result: A378/A379 - the two exactness selectors cost 1.5 ms and 0.0 ms at two rows

Preregistration: `2026-09-13-a378-a379-row-wise-selector-cost-prereg.md`. MTP1 diag branch `f1d5cd88`,
stage v2, exact-mode exports, step timing over three exact-2K rows each; control A369 (same packet,
selectors at 2).

| arm | selector off | forward M=2 median (min) ms | sample | draft | exact-2K hash |
|---|---|---|---|---|---|
| A369 control | none | 33.69 (31.90) | 0.89 | 2.22 | `afffd211…` (certified) |
| A378 | `VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=0` | 32.22 (30.50) | 0.89 | 2.15 | `99a2b9a3…` (changed) |
| A379 | `VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=0` | 33.66 (31.89) | 0.89 | 2.23 | `afffd211…` (unchanged) |

Medians over 88/84 two-token steps per arm; all three rows of each arm agree with each other.

## Reading

- The row-wise all-reduce is worth 1.47 ms of the two-row step (4.4%), under the 3 ms the
  preregistration set for making a row-invariant two-row collective the next kernel lever. It stays
  on the list, behind the larger term below.
- The row-wise HC norm is free (0.03 ms, inside the noise). Nothing to recover there.
- A378 changes the outputs (`99a2b9a3…` on all three rows): the batched two-row all-reduce is not
  bit-equal to two single-row reductions, as A104/A105 found. A379 does not: the batched HC-norm variance
  reproduced the certified `afffd211…` on all three rows, so on this line the HC-norm selector is both free
  and output-neutral at two rows (A110/A111's non-equality did not surface on these rows). Neither arm is
  promotable from a timing packet; A378 is timing evidence only.
- Correction (11:20 UTC): the first version of this note cited `54771cfd…` for both arms. That value is a
  request-level `sha256` field the timing driver's summary picked up by regex, not the output-ids hash;
  the hashes above are `output_token_ids_sha256` from the row files, and the driver now records that field.
- Remainder accounting on the exact-mode line, two rows, 2K: 33.69 ms = MoE 14.2 + QSA 4.7 + GDN 2.1
  + HC ~0 + all-reduce row-wise excess 1.5 + 11.2 unattributed (against 6.5 at one row). The
  unattributed part is now the largest per-row term: the dense projections (QKV/O, gate/up of the
  shared path, LM head, the draft-head forward at M=2) and the graph-replay glue. The next diag arm
  zeroes those one family at a time with a new skip switch on the diag branch (preregistered
  separately), the same zero-input differencing the A369-A373 decomposition used.
