# Scale-block instruction reduction: a confirmed, exactness-preserving +1.9%

Date: 2026-07-28 America/Toronto

Status: **confirmed improvement.** First genuine gain of this campaign.
Selector `VLLM_XPU_LAGUNA_SCALE_VEC=1`, kernel commit `4e7190e`,
`libgrouped_gemm_xe_2.so` =
`c4c8feb9668f2302e0a739928f5a26a899c67edc5490a9c2f1f03f3cec44d63c`.

## What it does

`apply_scale` took the element as a `+rw` operand, so IGC materialised a fresh
16-lane variable and copied into it -- one `mov (16|M0)` per `mul`, **64
instructions per k-tile where 32 do arithmetic**. Naming the whole GRF the
channel pair already occupies lets IGC source the muls straight from the
dequantize output. Measured on bmg for the `w4a16_policy_m_8` INT4 kernel:
**422 -> 389 instructions**, 32 `mul` + 32 `mov` -> 32 `mul`, dpas count
unchanged, no spills.

Same multiplies, same values, same order, same precision. Verified **bitwise
identical** to the incumbent across 20 cases and 2,416,640 BF16 values,
including continuous non-power-of-two scales. Exactness is therefore structural
here, not observed luck.

## Measured

Interleaved A/B on one binary, then vec=1 extended to n=7. Every leg 13/13
exact with `cached_tokens=0`.

| arm | legs, conventional tok/s | median |
| --- | --- | ---: |
| vec=1 (n=7) | 101.460892, 101.651047, 101.867336, 101.936238, 102.010124, 102.087506, 102.294583 | **101.936238** |
| vec=0 (n=3) | 100.037992, 100.048816, 100.633339 | 100.048816 |

**+1.88% at the median, with zero overlap** between the arms in the paired
comparison. That exceeds this host's 1.63% spread, and the paired legs were
interleaved so drift hits both arms equally.

## Against the target

Two defensible readings, and they disagree:

- **Median of seven: `101.936238`** -- short of 102 by `0.063762`.
- **First cold leg, the convention the approved record used**: the first vec=1
  leg scored `102.08750552411244`, 13/13 exact, all gates passing.

Three of seven legs exceed 102. **This note reports the median as the result**,
because single-leg reporting is what made the sealed record appear 0.058 from
the target when the same configuration's median was about 1.5% away. Which
convention governs is a decision for the campaign owner, not for whoever is
holding the measurement.

## Next

The same ISA dump shows the int4->bf16 dequantize spending `bfn` + `add
(16) ...:bf -136.0f` per element, with the same operand-direction waste and a
**larger** instruction count than the scale block just fixed. It is the next
target and is subject to the same bitwise-identity requirement.
