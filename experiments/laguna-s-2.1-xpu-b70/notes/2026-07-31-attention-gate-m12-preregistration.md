# Laguna exact M12 attention-gate fusion preregistration

Date: 2026-07-31 America/Toronto

Status: **source and one-card component gate authorized; no endpoint or
throughput claim authorized**.

## Premise

The confirmed `124.64241272122038 tok/s` BF16-KV record fuses Q/K RMSNorm plus
RoPE, proving that reducing actual device submissions inside captured target
segments survives graph replay. The next post-attention graph slot still
computes a per-head gate as two device operations:

1. `F.softplus(gate.float()).type_as(attn_output)`; then
2. broadcast BF16 multiply across each 128-element attention head.

At width 12 the two physical target shapes are 12 or 18 local query heads,
both with head dimension 128. A fused workgroup can own one row/head, compute
softplus once, explicitly round it to BF16, broadcast that BF16 value, and
multiply the 128 BF16 attention elements. This preserves the incumbent
softplus-before-BF16 and BF16-before-multiply boundaries while removing one
device submission per target layer.

## Frozen source design

- start from XPU kernels
  `69e8ad9119a9cc70c3906b82be6254dd0160f00e` and vLLM
  `58608c6361f1a958a7e933bed0be8c88c35aa26e`;
- add a separately named `_C` out-variant accepting only contiguous BF16
  `[12, heads*128]` attention, `[12, heads]` gate, and matching output, with
  `heads` restricted to 12 or 18;
- one 128-thread workgroup owns one row/head; lane zero computes the same
  threshold-20 FP32 softplus expression and stores its BF16 result for the
  group, then each lane performs exactly one BF16-input multiply;
- add one default-off literal vLLM selector restricted to the exact target
  verifier, width 12, BF16, gate-per-head, and head-dim 128;
- draft, prefill, other widths/shapes, selector-off execution, QKNorm/RoPE,
  attention, output projection, MoE, KV and sampling remain unchanged.

## Gates

1. Focus-build only `_C.abi3.so` with pinned oneAPI 2025.3.3 and retain every
   other native module/DSO byte-identical to the confirmed record.
2. On one B70, compare the fused output to the literal incumbent XPU expression
   over at least 32 independently seeded changing inputs for both 12-head and
   18-head physical shapes. Require raw BF16 equality for every tensor,
   including gate values around the softplus threshold and finite BF16
   extremes.
3. Require a material summed timing reduction and structural 96-to-48 kernel
   reduction for the 48-layer projection before separately authorizing vLLM
   integration or a model endpoint.
4. Any endpoint later authorized must preserve 13/13 canonical-q1 token/text
   exactness, cache-zero, target 146/145 and draft 14/13 on all ranks, one cold
   invocation per prompt, first-valid-score reporting, and clean teardown.

No target/draft/KV precision, width/depth, model, prompt, teacher, metric,
acceptance, graph topology, cache, warmup, retry, reboot, reset, or
LocalMaxxing action is authorized by this stage.
