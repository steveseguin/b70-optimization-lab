# Laguna exact M12 attention-gate fusion preregistration

Date: 2026-07-31 America/Toronto

Status: **closed endpoint negative; exact but `0.238903%` slower than the
confirmed record**.

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

The first formal invocation stopped before GPU use because the focus build had
also emitted a local `xpumem_allocator.abi3.so`; the runtime verifier rejected
that unapproved origin. The generated extra was quarantined and the frozen
external allocator was retained. That early stop also exposed that the RPC
directory was created before the cleanup trap; the launcher now creates it
only after installing the trap. Neither preflight stop loaded the model or
produced a throughput result.

## First valid endpoint result: reject

The single authorized cold endpoint leg passed every honesty and operational
gate but lost on the primary metric:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-attention-gate-m12-candidate3-20260801T052000Z
```

- conventional 99-interval median: `124.34463781920448 tok/s`;
- historical compatibility median: `125.60064426182271 tok/s`;
- conventional p10 / mean: `86.21236189100075 / 143.41712440903672`;
- full-output-after-TTFT median: `165.4201300837471 tok/s`;
- wall median / TTFT median: `54.98022575132142 tok/s` /
  `5967.311908003467 ms`;
- 13/13 token IDs and text hashes exact against canonical q1;
- `cached_tokens=0` on all 13 prompts;
- target `146/145` and draft `14/13` captured on all four ranks;
- pre/post idle intervals were 72 seconds; cleanup status was all zero.

Against the confirmed `124.64241272122038 tok/s` record, the candidate lost
`0.2977749020159024 tok/s` or `0.238903352%`. It remains default-off and is not
promoted or submitted.

The component evidence remains valid but did not transfer: reducing four tiny
eager device kernels to one measured an `8.16-8.18x` isolated speedup, yet the
work lives inside already segmented graph replay and saves too little of the
complete target/draft/collective cycle to overcome endpoint variance and any
new graph-node overhead. Future candidates need to remove or shorten a
material graph segment, attention body, collective boundary, or MoE mainloop;
another isolated elementwise launch-count win is not enough by itself.
