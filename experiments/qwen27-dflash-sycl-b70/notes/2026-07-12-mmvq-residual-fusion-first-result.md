# MMVQ plus residual fusion: first result

## Implementation and correctness

`GGML_SYCL_FUSE_MMVQ_ADD=1` fuses a projection MMVQ epilogue with the
following residual ADD. The matcher follows only single-use, contiguous,
identity metadata chains and otherwise falls back. It covers the model's
Q4_0, Q4_1, and Q5_K MMVQ paths and remains default-off.

- B70 smoke proved 128 fused pairs per target M=1 pass.
- The existing Q4_0 reordered M=1..17 test remained 17/17 passing.
- A temperature-zero, seed-42 parity request produced the exact same 128-token
  output SHA256 with fusion off and on.
- Both full MTP3 A/B runs and both four-card crossover rounds passed all cold
  semantic/cached-token gates.

## Timing and throughput

Native diagnostic queue timing over steady no-spec passes measured:

- fusion off: about 37.03 ms device queue interval;
- fusion on: about 36.72 ms device queue interval.

Thus removing 128 ADD submissions and about 5 MiB of traffic saves only about
0.3 ms per target pass. A 128-token llama-bench A/B measured 25.550 tok/s off
and 25.724 tok/s on (+0.68%; steady repetitions about +0.79%).

The simultaneous strict MTP3 A/B was inconclusive: fusion increased mean from
46.312 to 46.527 tok/s (+0.46%) but reduced the median. A deterministic
four-card two-round crossover also failed the 3% promotion gate. Card-matched
mean differences (on minus off) were approximately -1.406, -0.406, +0.276,
and -0.075 tok/s; the average was -0.403 tok/s (-0.86%).

## Disposition

Correct but not promoted. Keep the guarded implementation and evidence, but
do not enable it alone. Its measured device saving is real and may be useful
inside a larger fused boundary; standalone ADD launch/traffic removal is too
small for the maximum-speed objective. Proceed to the combined residual +
RMSNorm + Q8_1 production boundary, where multiple submissions and the
activation intermediate can be removed together.
