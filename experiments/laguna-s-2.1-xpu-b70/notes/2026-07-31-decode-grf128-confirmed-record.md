# Laguna decode GRF128 confirmed record

Date: 2026-07-31 America/Toronto

Status: **confirmed exact BF16-KV record; eligible for promotion and
LocalMaxxing submission**.

## Two independent cold legs

| Leg | Historical compatibility | Conventional 99 intervals | Exact | Topology |
| --- | ---: | ---: | ---: | --- |
| first | 121.299321162 | 120.086327950 | 13/13 | target 146/145, draft 14/13 |
| confirmation | **122.515718154** | **121.290560973** | 13/13 | target 146/145, draft 14/13 |

Both legs used the same model revisions, vLLM commit, kernel commit, native
DSO, runtime lock, frozen suite, teacher, and selector stack. Every prompt ran
once, all 26 requests reported `cached_tokens=0`, neither service performed a
warmup generation or retry, and both completed graceful teardown plus verified
pre/post idle intervals.

The confirmation artifact is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-decode-grf128-confirm-20260731T0943Z
```

The first artifact and full source/binary provenance are recorded in
[`2026-07-31-decode-grf128-first-endpoint-result.md`](2026-07-31-decode-grf128-first-endpoint-result.md).

## Promotion decision

The confirmation beats the approved `119.826868476 tok/s` conventional record
by `1.463692497 tok/s` (`+1.2215%`). The first independent leg also beats it.
This clears the concern that the original `+0.22%` observation was merely host
noise. The confirmation is promoted as the record because it is a complete,
independently valid cold suite—not a retry of a failed run or a cherry-picked
partial prompt set. The first lower leg remains visible as reproducibility
support.

Record identity:

- vLLM `34b43849fc7c8ff8633f223469cc2a0d525c256e`;
- XPU kernels `e4163f93574326b2772742e0f51372a5a3777aa5`;
- grouped-GEMM DSO SHA-256
  `df2f63a04630c3b50d3ffe2d61db3e3d68914436ba14270dcc45ddfec6b3467f`;
- runtime lock SHA-256
  `4207f80d96b4219aa48b4d71f2d59333c1d77c942127b5c325c7107853dcb3b4`;
- BF16 KV, TP4/EP4, width 12, DFlash depth 11, one active generation;
- `VLLM_XPU_LAGUNA_DECODE_GRF128=1` with exact scale-vector mainloop;
- target 146/145 and draft 14/13 on all four ranks.

## Transferable learning

The exact scale-vector kernel used about 94 GRFs but had been forced into
256-GRF mode, limiting each EU to four resident threads. A separately named
128-GRF kernel doubled the permitted resident thread count to eight without a
spill or any arithmetic change. The isolated effect was shape-dependent
(`+0.7%` W13, `+3.3%` W2), while two endpoint improvements were `+0.22%` and
`+1.22%` over the previous record.

The reusable rule is to inspect **allocated GRF mode as well as actual register
use**. An instruction-level optimization that lowers pressure cannot improve
occupancy while a global or per-kernel 256-GRF property pins the residency
class. Use a separately named kernel and an exact shape/type gate so a resource
mode experiment cannot silently alter unrelated prefill or draft paths.

