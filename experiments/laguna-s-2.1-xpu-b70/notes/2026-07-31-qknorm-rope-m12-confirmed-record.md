# Laguna M12 Q/K RMSNorm plus RoPE confirmed record

Date: 2026-07-31 America/Toronto

Status: **confirmed exact BF16-KV four-B70 record; LocalMaxxing submission
pending**.

## Result

The exact target attention path now fuses Q/K RMSNorm and NeoX RoPE at verifier
width 12. The fusion preserves the incumbent reduction tree, explicit BF16
norm boundary, BF16 weights and cos/sin cache, and multiply/add order. It
reduces three device kernels to one per attention layer without changing the
target, draft, KV precision, verifier, or sampling policy.

| Leg | Conventional 99 intervals | Historical compatibility | Exact | Topology |
| --- | ---: | ---: | ---: | --- |
| first candidate | 124.442780113 | 125.699777892 | 13/13 | target 146/145, draft 14/13 |
| confirmation | **124.642412721** | **125.901426991** | 13/13 | target 146/145, draft 14/13 |

The confirmation improves the preceding confirmed `122.828558121 tok/s`
record by **`1.476736866%`**. The two independent cold candidates are only
`0.160421206%` apart. Both runs were token-and-text exact against canonical
q1, cache-zero on all 13 prompts, one invocation per prompt with no warmup or
retry, and clean after audited capture/replay on all four ranks.

Record artifact:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-qknorm-rope-m12-confirm-20260801T032027Z
```

Supporting first candidate:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-qknorm-rope-m12-candidate-20260801T031134Z
```

The confirmation's conventional p10 and mean are `85.974005399` and
`143.276247086 tok/s`; full-output after-TTFT median is `163.155708668 tok/s`,
wall median is `56.060120509 tok/s`, and TTFT median is `5811.516058 ms`.
Prestart and poststop idle intervals were each 72 seconds, and every cleanup
status was zero.

## Identity and reproduction

- target `poolside/Laguna-S-2.1-INT4` at
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- draft `poolside/Laguna-S-2.1-DFlash-INT4` at
  `5e07c246915c86dc6920fead03d019989224f2ba`;
- vLLM `58608c6361f1a958a7e933bed0be8c88c35aa26e`;
- XPU kernels `69e8ad9119a9cc70c3906b82be6254dd0160f00e`;
- native `_C.abi3.so` SHA-256
  `ba7a3f6d21a15eec2a78a458b92a11ef4b8f4c8655752d9c47386dba628b0e9b`;
- grouped-GEMM DSO SHA-256
  `c4845ed7704a9afcf59e12f9d51e288f293f2e39966e283e2a7e322fed68b839`;
- runtime lock SHA-256
  `1b7a6d01969d09c3f9bde114a75748dace0ecbaecd7f01ebc3051d22ad74d606`;
- BF16 KV, TP4+EP4, one active generation, exact width 12, DFlash depth 11;
- selectors retain segmented inline DFlash attention, decode GRF128 and
  transposed scales, and add `VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=1`.

Review patches and complete-history bundles:

- `patches/laguna-s-2.1-xpu-b70/0001-laguna-qknorm-rope-exact-m12.patch`;
- `patches/laguna-s-2.1-xpu-b70/0002-vllm-select-laguna-qknorm-rope-m12.patch`;
- `patches/laguna-s-2.1-xpu-b70/vllm-xpu-kernels-laguna-qknorm-rope-m12-69e8ad9-20260731.bundle`;
- `patches/laguna-s-2.1-xpu-b70/vllm-laguna-qknorm-rope-m12-58608c6-20260731.bundle`.

The built candidate binary is preserved in the component artifact
`laguna-qknorm-rope-m12-component-20260801T030706Z`. Its 64/64 raw-BF16 gate
passed and projected a 48-layer reduction from `1.640180760` to
`0.579850380 ms`; the endpoint gain was smaller because graph replay already
amortizes part of the incumbent launch overhead.

## Transferable learning

Captured graphs do not erase the cost of extra device kernels, but they do
erase much of ordinary host dispatch overhead. Prioritize fusions that reduce
actual device submissions and preserve every BF16 rounding boundary. Use eager
component timing as an upper bound, not an endpoint prediction. A fusion can
remain exact across a wider verifier batch when the head-local reduction tree
and arithmetic order stay identical and the new workgroup geometry divides
all physical Q+K head totals without a tail.
