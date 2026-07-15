# Split FP8 geometry record

Date: 2026-07-15

Status: promoted; new strict TP4 single-session record.

## Profiling correction

The first fresh profiler run appeared to make `_bf16_mla_sparse_kernel` the
largest residual, with 43 calls. That interpretation was wrong. Starting the
profiler immediately, or after only one worker step, records the asynchronous
prefill tail. The promoted steady decode path uses `_fp8_sparse_qk_lse_kernel`
and `_fp8_sparse_pv_kernel`; it does not use the BF16 sparse kernel.

With a two-step delay, graph decode is an opaque reusable Level Zero command
list. The visible work outside it is about 0.6 ms/token, led by the TP-sharded
BF16 `[1,4096] x [4096,32320]` vocabulary projection at about 0.45 ms. A
matching eager trace exposed seven full decode tokens and attributed the graph
interior. The largest useful buckets were approximately 6.55 ms/token of dense
GEMMs, 4.05 ms of mHC post/pre, 3.35 ms of MXFP4 MoE, and 2.74 ms of split QK.
Profiler collective durations remain unusable because PTI serializes and
distorts the four ranks.

Evidence:

- prefill trace: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/record-lane-profile-20260715T0111Z`;
- graph decode boundary: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/record-lane-decode-profile2-20260715T0122Z`;
- eager decode attribution: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/record-lane-eager-decode-profile-20260715T0125Z`.

## Geometry change

The split FP8 kernel was hard-coded to `BLOCK_H=16`, eight QK warps, and four
PV warps. With 64 query heads, that launches only four large QK programs. The
new guarded controls retain the same math and cache format but run sixteen
four-head QK programs with 16 warps each. PV remains at four warps.

One-B70 exact-shape measurements for the complete QK+PV call were:

| Shape | 16 heads / 8 QK warps | 4 heads / 16 QK warps | Reduction |
| --- | ---: | ---: | ---: |
| C4, short | 88.556 us | 68.588 us | 22.56% |
| C128, short | 87.568 us | 63.466 us | 27.52% |
| C4, 128-token | 220.428 us | 128.700 us | 41.61% |
| C128, 128-token | 201.864 us | 118.456 us | 41.32% |

The focused test compares the tuned and original split outputs bitwise. It also
retains the existing BF16 reference, invalid-index, runtime-length, and command
graph replay coverage. vLLM commit:
`fa3e27b461ce7846ba71aefb161c40a017319fd2`.

## Full-model result

The exact promoted identity plus:

```text
VLLM_XPU_V4_SPLIT_FP8_BLOCK_H=4
VLLM_XPU_V4_SPLIT_FP8_QK_NUM_WARPS=16
VLLM_XPU_V4_SPLIT_FP8_PV_NUM_WARPS=4
```

returned the changed-input sequence `1073 -> 437 -> 1073` exactly. The strict
12-prompt cold suite passed with `cached_tokens=0` for every request:

- median tokens 1-100 after TTFT: **40.020972 tok/s**;
- p10: **39.608039 tok/s**;
- mean: **39.972761 tok/s**;
- median full-response wall rate: **37.842852 tok/s**;
- median TTFT: **156.445 ms**.

This is a 17.48% improvement over the prior 34.067121 tok/s record. LocalMaxxing
approved it as `cmrlnp01l12q4mj01p58ynsyd`. The evidence directory is
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/split-fp8-geometry-b4-qk16-recordidentity-20260715T0144Z`.

The first 40.106930 tok/s screen is preserved at
`split-fp8-geometry-b4-qk16-20260715T0135Z`, but it is not a headline row: that
server omitted `--enable-prompt-tokens-details`, so cached-token evidence was
null. It independently confirms speed but not the strict freshness gate.

## Decision

Promote the geometry as the nonspeculative base. The 40 tok/s gate is now
cleared, so speculative work may begin as a separate measured lane, while
continued base optimization should target dense projections or a larger
producer/consumer fusion. Do not return to the BF16 sparse prefill kernel or
the rejected compact collective fusion based on these traces.
