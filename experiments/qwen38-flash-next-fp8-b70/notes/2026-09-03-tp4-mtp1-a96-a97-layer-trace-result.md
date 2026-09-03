# A96 / A97 result: the MTP1 residual is inside layer 0, the first linear-attention layer

Date: 2026-09-03, 14:14--14:37 EDT
Status: **localized**; the two-row GDN spec-decode step, even with the
serial-exact recurrent mode, does not reproduce single-row decode

## What was captured

- A96 (eager MTP0, `afffd211...` at 2K, the graph line's own hash): every
  layer's output at positions 2048 and 2049, one capture each, four ranks.
- A97 (eager MTP1 with `MTP_EXACT=1`, `29a2947a...`): every layer's output
  for its first verification step, rows at positions 2048 and 2049, four
  ranks, with per-row digests.

Both start from the identical post-prefill state (the prefill is the same
computation on both lines) and the identical input token at 2048.

## Comparison (all four ranks agree)

| row | position | records identical | records differing | first differing record |
| --- | ---: | ---: | ---: | --- |
| 0 | 2048 | 17 | 151 | `layer_0_output.block_output` (the layer-0 attention block output) |
| 1 | 2049 | 15 | 153 | same |

The model input (embedding of the token) is identical; the very first
layer's block output differs for row 0, which had the same state and the
same input as the MTP0 decode. Layer 0 is a linear-attention layer. Its
surrounding dense projections are M-invariant (offline gate), the
hyperconnection mix and the norms are per-row GEMMs and reductions of the
same kind, so the difference is the GDN spec-decode kernel path (conv state
plus gated delta rule) against the single-row decode kernel, and it is
present with `VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1`.

This also explains the A94/A95 picture (every layer differing at 2059): by
then the recurrent state has drifted for eleven steps.

## What follows

A verifier-row path that runs each row through the single-row decode
kernel (`gdn_attention`, `num_decodes=1`) with the state copied between
the request's spec state columns, so the outputs are the decode kernel's by
construction: row 0 from the accepted-state column, row 1 from row 0's
result, each column holding "state after row j" as the native layout
expects. Flag-gated in `vllm/_xpu_ops.py`, validated first by the same
trace pair (A98 against A96), then by the frozen battery in the graph.

## Aside

A94 (traced at 2059) produced a 2K continuation that leaves the graph line
at token 108, while A96 (traced at 2048/2049) reproduces the graph line's
hash exactly. Either the traced forward perturbs a later step or the eager
line is not server-repeatable at depth; it does not affect the
first-step comparison above (both A96 and A97 trace the same code path at
2048) and is left as an open observation.

Data: [`a97 vs a96 at 2048`](../data/20260903-tp4-mtp1-a97-vs-a96-layer-trace-rank0-pos2048.json),
[`at 2049`](../data/20260903-tp4-mtp1-a97-vs-a96-layer-trace-rank0-pos2049.json),
[`a95 vs a94 at 2059`](../data/20260903-tp4-mtp1-a95-vs-a94-layer-trace-rank0-pos2059.json).
