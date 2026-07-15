# Exact M=1 router normalization component

Date: 2026-07-15

## Result

A second native M=1 router operator now performs biased sorted top-6,
unbiased-weight gather, normalization, and the production `1.5` routed scale in
one kernel. It is bitwise exact against the current native-top-k plus PyTorch
normalization chain on all four B70s:

- 40/40 changing eager epochs per card;
- 32/32 changing XPU graph replays per card;
- zero expert-ID or FP32 weight mismatches.

Under graph replay the fused operator saves `4.03-4.34 us/call`, or
`0.161-0.174 ms/token` over 40 normal routed layers. This does not meet the
standing `0.50 ms/token` standalone promotion threshold, so it is not being
loaded into the service alone. It is the first qualified component of the
direct M=1 routed-MoE lane.

## Exactness work

The production router uses `E=160`, `K=6`, normalization enabled, and routed
scale `1.5`. Two last-bit issues had to be matched explicitly:

1. XPU `torch.sum` reduces six values as
   `((w0+w1)+(w2+w3))+(w4+w5)`, not as a serial loop.
2. Ordinary SYCL FP32 division lowers to reciprocal multiplication and differed
   from PyTorch by one ulp. Intel's `fdiv_rn` helper was exact but increased the
   candidate to roughly `57 us`. An inline reciprocal estimate plus fused
   residual correction recovered the correctly rounded quotient and reduced
   eager candidate latency to roughly `8.2 us`.

This is important beyond the router: fused kernels must preserve tensor-boundary
rounding, not merely algebraic equivalence. The reduction tree and explicit
residual correction are now durable recipes for exact future fusions.

## Four-card graph result

| Rank | Reference | Fused | Saving/call | Projected saving/token |
|---:|---:|---:|---:|---:|
| 0 | 22.666 us | 18.635 us | 4.031 us | 0.161 ms |
| 1 | 22.711 us | 18.588 us | 4.124 us | 0.165 ms |
| 2 | 22.791 us | 18.670 us | 4.120 us | 0.165 ms |
| 3 | 23.003 us | 18.664 us | 4.339 us | 0.174 ms |

The next bounded integration is not normalization alone. A default-off direct
M=1 routed-MoE path should consume the six selected slots directly, removing
RowsPerExpertCount and RemapHiddenStates, then fuse the routed BF16 clamps into
the existing SwiGLU boundary. Together with this qualified normalization
component, the measured raw pool is approximately `0.52 ms/token`; MoeGather
fusion remains a fallback if the paired end-to-end gate misses 0.50 ms.

Structured result:
`data/m1-router-normalization-four-card-20260715.json`.

