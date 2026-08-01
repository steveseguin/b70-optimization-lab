# Laguna exact M12 attention-gate fusion preregistration

Date: 2026-07-31 America/Toronto

Status: **one-card component gate passed; default-off vLLM integration and one
strict endpoint leg authorized**.

## Premise

The confirmed `124.64241272122038 tok/s` BF16-KV record fuses Q/K RMSNorm plus
RoPE, proving that reducing actual device submissions inside captured target
segments survives graph replay. The next post-attention graph slot still
computes a per-head gate as four measured XPU device submissions:

1. BF16-to-FP32 copy;
2. FP32 softplus;
3. FP32-to-BF16 copy; and
4. broadcast BF16 multiply across each 128-element attention head.

At width 12 the two physical target shapes are 12 or 18 local query heads,
both with head dimension 128. A fused workgroup can own one row/head, compute
softplus once, explicitly round it to BF16, broadcast that BF16 value, and
multiply the 128 BF16 attention elements. This preserves the incumbent
softplus-before-BF16 and BF16-before-multiply boundaries while removing three
device submissions per target layer.

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
3. Require a material summed timing reduction and structural 192-to-48 kernel
   reduction for the 48-layer projection before separately authorizing vLLM
   integration or a model endpoint.
4. Any endpoint later authorized must preserve 13/13 canonical-q1 token/text
   exactness, cache-zero, target 146/145 and draft 14/13 on all ranks, one cold
   invocation per prompt, first-valid-score reporting, and clean teardown.

## Component result and authorization

The exhaustive component artifact is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-attention-gate-m12-component-exhaustive-20260801T041000Z
```

Candidate source identity is XPU kernels
`0ecea928c3b447b103bb0cd46ffe75ae94f2c065` and vLLM
`2b644445e573f37d67919ac854167159eecf5493`; the candidate `_C` SHA256 is
`6613ae0de241c9de5c3722c606ae89138a00e4c8f4486cab59eaaa4c4217fa13`.

- 64/64 changing shape/seed tensors matched in raw BF16, including finite
  extremes and threshold-adjacent values;
- all 65,280 finite BF16 gate encodings matched the incumbent softplus-to-BF16
  result with zero mismatches;
- 12-head median: `0.04591002 -> 0.00560976 ms`, `8.18395x`;
- 18-head median: `0.04591236 -> 0.00562744 ms`, `8.15866x`;
- PyTorch XPU profiling measured four incumbent device kernels and one
  candidate kernel for one call. Chrome traces and `profiler-summary.json` are
  retained in the artifact.

The initial two-submission premise was wrong because it omitted both dtype-copy
kernels. The measured structural projection is therefore 192 target device
submissions to 48, not 96 to 48.

Default-off vLLM integration and exactly one strict endpoint leg are now
authorized. No target/draft/KV precision, width/depth, model, prompt, teacher,
metric, acceptance, graph topology, cache, warmup, retry, reboot, reset, or
LocalMaxxing change is authorized. Report the first valid endpoint score even
if it loses; stop on any bitwise, topology, cache, or operational gate failure.
