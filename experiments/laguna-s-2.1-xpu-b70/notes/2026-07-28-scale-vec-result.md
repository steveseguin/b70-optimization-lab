# Scale-block instruction reduction: median 102.13 tok/s conventional

Date: 2026-07-28 America/Toronto

Configuration: `VLLM_XPU_LAGUNA_SCALE_VEC=1`, `VLLM_XPU_LAGUNA_DEQUANT_MAD=0`,
width 12 / DFlash depth 11, BF16 KV, TP4+EP4, one active generation.
Kernel `46a88e0`, `libgrouped_gemm_xe_2.so` =
`53f3d2941ce322bcdff1b0463ec6fe72387036ea54d3f602a08d690744b3459f`.

## Result

Thirteen legs. **Every one is 13/13 bitwise exact against the q=1 teacher,
`cached_tokens=0` on all rows, output-text SHA-256 equal on all rows.**

```
100.597067  101.171624  101.361727  101.391907  101.578704
102.093945  102.134914  102.275480  102.354633  102.408227
102.565744  102.609985  102.764821
```

| statistic | conventional tok/s |
| --- | ---: |
| **median (n=13)** | **102.134914** |
| mean | 101.946829 |
| min / max | 100.597067 / 102.764821 |
| legs at or above 102 | 8 of 13 |

Matched control on the same binary, `SCALE_VEC=0`: median `100.048816`.
**The improvement is +2.09% at the median.**

**State the mean alongside the median.** At `101.946829` it sits below 102, and
five of thirteen legs fall short. The distribution straddles the target with
its centre above it; it does not sit clear of it. Anyone citing this result
should cite both numbers.

## Why it is exact by construction, not by luck

`apply_scale` took its element as a `+rw` operand, so IGC materialised a fresh
16-lane variable and copied into it: one `mov (16|M0)` per `mul`, 64
instructions per k-tile where 32 did arithmetic. Naming the whole GRF the
channel pair already occupies lets IGC source the muls straight from the
dequantize output. Measured on bmg for `w4a16_policy_m_8`: **422 -> 389
instructions**, 32 `mul` + 32 `mov` -> 32 `mul`, dpas count unchanged, no
spills.

Same multiplies, same values, same order, same precision. Verified **bitwise
identical** to the incumbent across 20 cases and 2,416,640 BF16 values,
including continuous non-power-of-two scales. The 13/13 gate cannot fail for
arithmetic reasons here.

## Rejected on the way

- **Scale folding into the FP32 accumulator**: ~+8%, **0/13 exact**. More
  numerically accurate than the incumbent and therefore just as disqualified.
- **`add(-136)` + `mul` fused to `mad`**: float pipe -45% (65 -> 36 per k-tile),
  bitwise identical over 1,044,480 exhaustive cases, and **~1% slower**
  end-to-end. The int pipe grew 50 -> 65 and is the binding constraint.
- **Prefetch distance 3 and 12**: control equalled or beat both.
- **Generic N-tile 32 and 128**: both below the default 64.
- **Draft graph capture**: 0/13 exact; root cause documented separately.

## Reading this against the sealed record

The record's `101.94172124017027` was one cold leg. Across eleven legs this
session the incumbent configuration's median is `100.439886`. Single-leg
reporting is why the target appeared 0.058 away when the median was about 1.5%
away. This note reports a median over thirteen legs for that reason.
