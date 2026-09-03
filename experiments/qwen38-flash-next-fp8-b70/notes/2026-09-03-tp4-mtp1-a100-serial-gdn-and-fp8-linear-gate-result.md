# A100 serial-GDN verifier rows and the block-FP8 linear gate (2026-09-03)

## A100 result (eager MTP1, GDN verifier rows through the decode kernel)

A100 ran the eager deterministic identity at 4352 tokens with the overlay's
`VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1` path (overlay fd81d811): during an MTP1
verification step every packed row of a sequence goes through the ordinary
non-spec decode kernel one row at a time, each row starting from the state
the previous row produced, instead of the multi-row spec-decode kernel.
Traced on every rank at the first forward whose maximum position reaches 2048.

- Exact-2K output hash `29a2947a...`: identical to A85 (the exact-recurrent
  kernel stage), still not the MTP0 line's `afffd211...`. Two independent
  implementations of "exact recurrence for verifier rows" therefore agree
  with each other, which localizes the residual outside the recurrent core.
- Layer trace against A96 (MTP0 at 2048): the model input `hidden_states`
  row 0 matches A96 bit for bit, `layer_0_output.injection` matches, and
  `layer_0_output.block_output` row 0 already differs (head values
  ref `-0.017822, -0.007446, 0.035645, -0.024658` vs
  cand `-0.017822, -0.007324, 0.035645, -0.023926`). Same for row 1 at 2049.
  Every later layer inherits the difference. Data:
  `../data/20260903-tp4-mtp1-a100-vs-a96-layer-trace-rank0-pos2048.json`.

So the first divergence sits inside decoder layer 0 (a linear-attention
layer): hyperconnection mix, `in_proj_qkvz` / `in_proj_ba`, causal conv,
recurrent core, gated RMSNorm, `out_proj`, or the residual injection, with
row 0 seeing exactly the same input as MTP0.

## Block-FP8 linear gate: M=2 equals M=1 (cleared)

The BF16 GEMM gate of the morning used `torch.matmul`; the model's dense
projections actually run the oneDNN block-scaled FP8 GEMM
(`torch.ops._xpu_C.fp8_gemm`) after dynamic per-token [1,128]-group
activation quantization. `tools/equivalence-fp8-linear-m2-vs-m1-gate.py`
reproduces that path exactly (same quant function, same op, same
`[k_blocks, n_blocks]` scale layout, ragged-N scale expansion, kernel stage
`runtime-core-moe-negidguard-b70`, `torch.backends.mkldnn.deterministic`)
on the layer-0 shapes at TP4 and compares a two-row batch with each row alone,
four activation draws per shape.

| shape (N x K) | trials | batched == singles |
|---|---|---|
| gdn in_proj_qkvz 4096 x 2560 | 4 | yes, 0 elements differ |
| gdn out_proj 2560 x 1536 | 4 | yes |
| attn qkv_proj 1792 x 2560 | 4 | yes |
| attn o_proj 2560 x 1536 | 4 | yes |
| shared-expert gate_up 320 x 2560 | 4 | yes |

Data: `../data/20260903-b70-block-fp8-linear-m2-vs-m1-equivalence.json`.
Caveat: random block-FP8 weights, not the checkpoint's; the activation
quantization is per row by construction, so this gate covers the GEMM's
M-dependence, which is what MTP1 changes.

## Cleared and remaining

Cleared for M=2 vs M=1 bit-exactness: graph replay (A83), BF16 oneDNN GEMM,
block-FP8 oneDNN GEMM (this gate), Triton block-FP8 MoE, QSA indexer side
path (A93), GDN recurrent core (A85 and A100 agree). Remaining inside layer
0: the causal conv1d update for spec rows, the `in_proj_ba` path (N=24 per
rank, too ragged for block FP8, so it runs unquantized), the gated RMSNorm,
and the hyperconnection residual injection. A102 (MTP1, serial GDN rows) and
A103 (MTP0 reference) trace layer 0's inner records (`gdn_in_proj`,
`gdn_core`, `gdn_norm`, `gdn_out_proj`, `gdn_attn_output`) with
`Q38_REPEATABILITY_TRACE_GDN_LAYERS=0` to name the first differing tensor.
