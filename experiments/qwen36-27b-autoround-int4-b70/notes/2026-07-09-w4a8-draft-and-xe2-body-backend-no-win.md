# 2026-07-09 - W4A8 draft and Xe2 body backend screens: no-win

Status: microbenchmark closures only; no endpoint candidate and no quality or
LocalMaxxing run.

All measurements used GPU 0, the live oneAPI/XPU extension, synchronized each
iteration, and matched Qwen3.6 27B dimensions. These screens were run only
after the compiled GDN endpoint disproved the earlier eager-reference speedup.

## Draft LM-head W4A8

Shape: rows `1`, hidden `5120`, vocab `248320`, group size `128`; the W4A8
measurement includes `per_token_quant_int8_xpu` plus
`int4_gemm_w4a8`. Weight/scales match the runtime INT4 draft representation.

| Path | Median ms/call | Mean ms/call |
|---|---:|---:|
| current oneDNN W4A16 | `1.141812` | `1.145710` |
| oneDNN W4A8 including quantization | `1.170286` | `1.173442` |

Random-input top-1 agreement was `24/24`, but W4A8 was `2.5%` slower, so it
does not justify endpoint acceptance testing. Target output quality would have
remained target-verified, but draft acceptance is irrelevant when the primitive
is already slower.

## Dense target-body Xe2 grouped W4A16

The existing `cutlass_grouped_gemm_interface` was exercised as one expert and
compared with `int4_gemm_w4a16`. Signed INT4 values were packed separately for
each backend and outputs agreed to BF16 rounding error.

| Rows / K / N | oneDNN ms | Xe2 grouped ms | Xe2 result |
|---|---:|---:|---:|
| `4 / 5120 / 34816` gate+up | `0.199024` | `0.215425` | `8.2%` slower |
| `4 / 17408 / 5120` down | `0.111329` | `0.179628` | `61.3%` slower |
| `1 / 5120 / 34816` gate+up | `0.190238` | `0.213873` | `12.4%` slower |
| `1 / 17408 / 5120` down | `0.110808` | `0.179477` | `62.0%` slower |

## Decision

Keep oneDNN for both the draft INT4 LM-head and dense AutoRound body. Do not
wire either backend swap into vLLM. A future target-body kernel must fuse a
larger compiled boundary or reduce weight traffic; swapping the existing GEMM
backend cannot provide the approximately `12.8 ms/step` needed at current
acceptance.
