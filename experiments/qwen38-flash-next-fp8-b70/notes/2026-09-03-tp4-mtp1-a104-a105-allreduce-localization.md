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

## A106 result: layers 0-42 exact at both verify rows; residual moves to layer 43

A106 (A104's identity plus `VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=2`, overlay
8ca2cbc2) gave exact-2K hash `3c861245...` (new: neither MTP0's `afffd211`
nor the earlier MTP1 `29a2947a`). Against A105 on every rank:

- Row 0 (position 2048): every numeric record through `layer_42_output`
  identical; the only earlier differences are the PLE metadata tensors that
  differ by construction (`query_start_loc` [0,1] vs [0,2]). First numeric
  difference: `layer_43_output.block_output`, then layers 44-47 and the
  model output.
- Row 1 (position 2049): identical through `layer_43_output`; first
  difference `layer_44_output` (its recurrent state inherits row 0's
  layer-44 state, which already differs).

So the all-reduce fix and the serial recurrent path make the verify step
exact through 43 of 48 layers. Layer 43 is a full-attention (QSA) layer, and
position 2048 is the first position past the indexer's 2048-token budget,
where top-k selection first becomes active; the earlier full-attention
layers (3, 7, ..., 39) at the same position are exact. A106 did not carry
the per-row indexer flag (`VLLM_XPU_QSA_SERIAL_SPEC_INDEXER`, A93); A108
adds it to A106's identity. Data:
`../data/20260903-tp4-mtp1-a106-vs-a105-layer-trace-rank{0..3}-pos{2048,2049}.json`.

## A108: the per-row indexer changes nothing; layer 43 traced next

A108 (A106 plus `VLLM_XPU_QSA_SERIAL_SPEC_INDEXER=1`; the flag's marker fired
on the server) gave the same exact-2K hash as A106, `3c861245...`, and the
same comparison against A105: exact through layer 42 at row 0 and through
layer 43 at row 1, first numeric difference `layer_43_output` at row 0. The
QSA index side path is therefore not the residual. Overlay 76b787e2 adds
report-only records inside the QSA layer (`_qsa_proj`, `_qsa_selected`,
`_qsa_attn_output`, `_qsa_gated`, `_qsa_o_proj`) for traced layers; A110
(MTP1, serial GDN rows and row-wise all-reduce) and A111 (MTP0 reference)
trace layers 0 and 43. Data:
`../data/20260903-tp4-mtp1-a108-vs-a105-layer-trace-rank{0..3}-pos{2048,2049}.json`.
