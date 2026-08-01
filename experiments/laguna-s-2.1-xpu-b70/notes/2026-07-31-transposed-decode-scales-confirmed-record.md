# Laguna transposed decode scales confirmed record

Date: 2026-07-31 America/Toronto

Status: **confirmed exact BF16-KV four-B70 record; approved by LocalMaxxing as
`cms9osksu00b3pm010hf9bnk8`**.

## Result

The immutable target INT4 scale tables are transposed once at model load from
checkpoint layout `[expert,N,K/32]` to decode layout `[expert,K/32,N]`. Only
the exact width-12 target route consumes the clones. This makes each K-group's
BF16 scale line contiguous while leaving every scale value and every arithmetic
operation unchanged.

| Leg | Conventional 99 intervals | Historical compatibility | Exact | Topology |
| --- | ---: | ---: | ---: | --- |
| selector-off control | 118.802183680 | 120.002205737 | 13/13 | target 146/145, draft 14/13 |
| first candidate | 121.383776672 | 122.609875426 | 13/13 | target 146/145, draft 14/13 |
| confirmation | **122.828558121** | **124.069250627** | 13/13 | target 146/145, draft 14/13 |

The first candidate beat its adjacent same-DSO control by `2.1730%`. Both
candidate starts beat the previous exact `121.290560973 tok/s` record; the
confirmation improves it by `1.2680%`. The lower independent candidate is
`121.383776672 tok/s`, so the improvement is not inferred from one favorable
start.

All three valid legs were 13/13 token-and-text exact against canonical q1,
cache-zero on every request, one invocation with no warmup or retry, and clean
after audited 146/145 target plus 14/13 draft capture/replay on all four ranks.
The confirmation completed 73-second prestart and 72-second poststop idle
intervals.

Record artifact:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-transposed-scales-confirm-20260801T010855Z
```

Supporting first candidate:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-transposed-scales-candidate-20260801T005945Z
```

## Identity and reproducibility

- target `poolside/Laguna-S-2.1-INT4` at
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- draft `poolside/Laguna-S-2.1-DFlash-INT4` at
  `5e07c246915c86dc6920fead03d019989224f2ba`;
- vLLM `34b43849fc7c8ff8633f223469cc2a0d525c256e`;
- XPU kernels `8dd94f2307db3b830fe07f212c4b36f719652a5c`;
- grouped-GEMM DSO SHA-256
  `c4845ed7704a9afcf59e12f9d51e288f293f2e39966e283e2a7e322fed68b839`;
- runtime lock SHA-256
  `5993828ee79c2ff5239e5a30ecd9e1f72acb62537cdb291fada7080d21354f5f`;
- BF16 KV, TP4+EP4, one active generation, exact width 12, DFlash depth 11;
- `VLLM_XPU_LAGUNA_DECODE_GRF128=1` and
  `VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES=1`.

Review patch and complete-history source bundle:

- `patches/laguna-s-2.1-xpu-b70/0001-laguna-transpose-exact-width12-decode-scales.patch`;
- `patches/laguna-s-2.1-xpu-b70/vllm-xpu-kernels-laguna-transposed-scales-8dd94f2-20260731.bundle`.

The preserved production DSO is
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-transposed-scales-build-2f0b061-20260731T152719Z/libgrouped_gemm_xe_2.so`.
The initial malformed prefetch and device-loss failure remain in the source
history and preregistration rather than being erased.

## Transferable learning

For groupwise quantized GEMMs, weight layout alone is not the complete memory
layout problem. A small scale table can still force scattered cache-line
transactions in every K group. If scales are immutable, a decode-only
transposed clone can make their access contiguous without changing numerical
semantics. Gate the clone by exact shape and role, keep prefill on checkpoint
layout, and validate the actual block-prefetch geometry independently: a
malformed 2D descriptor can lose the device even when the ordinary loads are
correct.

## Publication

The authenticated LocalMaxxing preflight returned `valid: true`. The
conventional result was then accepted with HTTP 201 and approved as
[`cms9osksu00b3pm010hf9bnk8`](https://www.localmaxxing.com/en/runs/cms9osksu00b3pm010hf9bnk8).
The queue and receipt are preserved under `data/`; the preceding GRF128 receipt
remains historical evidence and is superseded for the matching four-B70 row.
