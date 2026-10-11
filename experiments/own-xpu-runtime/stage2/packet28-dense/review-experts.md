# Independent expert-kernel identity review

Reviewer: dense-family implementation agent, independently reading the expert
implementation. Sources examined: `expert.hpp`, packet8 `decode.hpp` (`decode8`
and `dot`), packet9 `kernels.cpp` (`Projection`), packet2 `kernels/math.hpp`
(`decode`, `element`, `tree32`). This is a source review; no device was run.

IQ4_NL retains the exact `(half(block_scale) * float(level)) * input`
expression. The level table is the same sixteen signed values, indexed by
the original low/high nibble positions. Private and shared scale variants
select the same block. Neither variant uses a different scale precision.

IQ2_S uses the same 10-bit grid index, sign byte, and scale expression
`(d * (0.5f + float(sc))) * 0.25f`. IQ3_S uses the same two 9-bit
indices, sign byte, and `d * float(1 + 2 * sc)` scale. IQ3_XXS uses
the same two indices, parity-extended sign mask, and
`(d * (0.5f + float(sc))) * 0.5f`. Constant evaluation converts the
credited normative grids to bytes in explicitly little-endian order; device
access then reads the byte at precisely the index formerly shifted out.

For finite scales the signed-magnitude folding is identical to packet8.
On NaN or infinite block scales the new code preserves the scalar reference's
magnitude-then-sign multiplication and its two rounding points. IQ scale
multipliers are strictly positive, so no `infinity * zero` scale-generation
case is missed. On nonfinite IQ4 scales packet2 and packet8's fallback have
exactly the same one-scale-times-level expression as the new code.

The range validator admits only complete format blocks, beginning on a
256-column boundary. Each active lane begins at `begin + 256*t + 8*lane`;
8 divides both 16- and 32-weight scale groups. No active lane can straddle a
scale group. At K=640, the final 128 columns are exactly sixteen full lane
tiles. Inactive lanes decode a safe first block of that tile and still take
part in the subgroup broadcasts; none contributes a product or reads x.

The paired variant loads each x once and accumulates into two independent
FP32 sums, in the old per-lane order. It does not combine gate/up sums or
move either output's BF16 rounding. The bridge must keep the old lane tree
and each output's own final rounding; lane-source review alone cannot prove
the bridge.

One requested cleanup: the local helper callbacks initially used `[&]`.
Although these refer only to device-local temporaries and are not host
kernel captures, changing them to `[=]` satisfies the user's literal
by-value-only requirement and removes that ambiguity. No arithmetic issue
was found in the expert lane source. CPU evidence and the pending device
bit comparisons remain separate gates; this review grants no speed result.
