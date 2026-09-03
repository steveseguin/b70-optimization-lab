# MTP1 residual localized: the TP all-reduce (A104 vs A105, 2026-09-03)

## Runs

- **A104** (relaunch of A102 after its memory-PSI guard trip): eager MTP1 at
  4352 tokens, `VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1`, overlay fd81d811, trace on
  every rank at position 2048 with layer 0's inner GDN records
  (`Q38_REPEATABILITY_TRACE_GDN_LAYERS=0`). Exact-2K hash `29a2947a...`
  (same as A85 and A100).
- **A105**: the MTP0 reference of the same identity and head (built from the
  A96 generator; the first MTP0 packet, A103, was derived from the MTP1
  generator and refused by the fail-closed base before any server started).
  Exact-2K hash `afffd211...` (the deterministic line's authority).

## First differing tensor, every rank

Row 0 of A104 (position 2048, the accepted token) against A105:

| record | same |
|---|---|
| model_input.hidden_states | yes |
| layer_0_gdn_in_proj hidden_states / qkvz / ba | yes |
| layer_0_gdn_core core_attn_out / z | yes |
| layer_0_gdn_norm normed | yes |
| **layer_0_gdn_out_proj out** | **no** (ranks 0-3) |
| layer_0_gdn_attn_output, layer_0_output.block_output | no |

So the recurrent core and its input projection are exact under the serial
verifier-row path; the divergence enters at `out_proj`, the row-parallel
projection whose partial sums go through the TP all-reduce.

## Offline probe: XCCL all-reduce depends on the row count

`tools/equivalence-tp4-allreduce-m2-vs-m1-probe.py` runs four ranks (one per
B70) with the serving CCL environment and all-reduces fixed random BF16 rows
batched and one at a time.

| width | rows batched | equals single-row results | elements differing (trial 0) | max abs diff |
|---|---|---|---|---|
| 2560 | 1 | yes | 0 | 0 |
| 2560 | 2 | no | 1658 of 5120 | 0.0625 |
| 2560 | 3 | no | 2249 | 0.0625 |
| 2560 | 4 | no | 3330 | 0.03125 |
| 10240 | 2 | no | 6571 of 20480 | 0.0625 |

Every call is repeatable and all ranks agree; only the reduction order
changes with the message size. This is the MTP1 residual: a verification
step reduces [2, N] where the decode step reduces [1, N].
Data: `../data/20260903-b70-tp4-xccl-allreduce-m-vs-m1-probe.json`.

## Fix (overlay 8ca2cbc2)

`VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=<num_spec+1>`: the XPU communicator
all-reduces inputs with 2..N rows one row at a time, with exactly the calls
the M=1 decode step makes. Default 0 keeps the batched all-reduce, so MTP0
is untouched. Cost: one extra collective per row-parallel layer per
verification step (about 100 per step at TP4). A106 = A104's identity plus
this flag, traced at 2048, compared against A105.

Comparison data: `../data/20260903-tp4-mtp1-a104-vs-a105-layer-trace-rank{0,1,2,3}-pos2048.json`.
