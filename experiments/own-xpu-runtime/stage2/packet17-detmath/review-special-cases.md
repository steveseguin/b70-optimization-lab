# Independent contraction and special-case review

CPU-only review on 2026-10-11. No device binary or discovery was run. The
review used one GNU compilation job and one bounded, single-thread host probe.
Compiler options: `-std=c++20 -O2 -fno-fast-math -ffp-contract=off`.
Reviewed initial header SHA-256: `b7480b675e50d564b92b5ca7084efa769e142ee3912deb2bba76f2e04de69c9f`.

## Findings

The exp/log operation graph contains no ordinary `a*b+c` expression. Products
that need their residual use an explicit fused multiply-add. The compensated
sum algorithm requires round-to-nearest ties-to-even, no reassociation and
`-ffp-contract=off`; gradual underflow is also part of the identity. Header use
under fast-math is outside this contract. Explicit builtin FMA must lower to a
correctly rounded fused operation. IEEE division and sqrt are requirements,
not consequences established by this host review.

Exp and log canonicalize every NaN to positive quiet NaN `0x7fc00000`,
including signaling NaNs; this differs from glibc payload/sign preservation.
Exp maps both zeros to 1, +infinity to +infinity, -infinity to +zero.
Log maps both zeros to -infinity, all negative nonzero values to canonical
NaN, +infinity to itself, and 1 to positive zero. Positive subnormals are
normalized by an exact multiplication by 2^23. Floating exception flags and
errno are not part of this identity. The exp threshold floats on each end
are consistent with rounding to overflow and half-minimum-subnormal.

The initial reciprocal residual implementation still used hardware division
for its leading estimate and correction. It is not an independent proof of
correct division, despite agreeing with plain division in this sample. The
recommended alternate uses exact unsigned-integer division on the 24-bit
significand of the correctly rounded sqrt. For finite positive sqrt s with
unbiased exponent E and significand integer m, m=2^23 gives 2^-E exactly;
otherwise round the quotient 2^47/m to nearest-even and use exponent -E-1.
Compare twice the integer remainder to m to decide rounding and renormalize
if rounding reaches 2^24. The sqrt of every positive finite binary32 input
and its reciprocal are normal, so this path needs no subnormal handling.
Handle signed zeros, infinities and NaNs before this path. This proves the
reciprocal of the rounded sqrt; it does not turn a non-IEEE sqrt into an IEEE
sqrt. The parent was sent this proposed correction before implementation.

The initial exp subnormal path rounded a compensated half-integer remainder
back to one float before its ties-to-even test. That can lose which side of
one half the low component represents. The parent was asked to compare
normalized remainder.hi with 0.5 and use remainder.lo for equality instead.
The existing sampled result remained within the requested one-ULP target,
but its comment claiming a single rounding was too strong before that fix.

## Bounded host evidence

The probe covered 1,000,000 inputs from a fixed uint32 LCG seed 1234567,
plus 131,071 consecutive float bit patterns around each of exp's underflow,
normal/subnormal and overflow boundaries (393,213 boundary inputs). The
reference was `float(expl(long double(x)))` / `float(logl(long double(x)))`.
This is an independent high-precision host sanity check, not a proof of the
whole-domain bound and not a device equality result.

| Probe | Result |
| --- | --- |
| Exp max distance to rounded long-double reference | 1 ULP, first maximum input `0xc2aed982` |
| Exp differences greater than 1 ULP | 0 |
| Log max distance on sampled positive finite inputs | 0 ULP |
| Exp boundary monotonicity violations | 0 |
| Initial corrected reciprocal versus plain on sampled positive finite inputs | 0 differing values |

The following special inputs were explicitly checked: both signed zeros,
both signs of minimum subnormal, largest subnormal, minimum normal, one,
maximum positive/negative finite values, both infinities, signed quiet NaNs
and a signaling NaN. These matched the exp/log semantics above. For rsqrt,
plain and initial corrected paths agreed on their host results, including
signed-zero infinities; NaN payload/sign remain implementation-dependent
unless deliberately canonicalized.

No performance or exhaustive accuracy claim follows from this review. The
other independent accuracy review and future device windows remain needed.
The reproducible source is `review-special-cases.cpp`; temporary build scratch
was removed after the final probe.

## Review of corrected header

The final reviewed header SHA-256 is `fbc845e5327579447fed4a6fb3d2638b6b5a389330ea712c45f9d8f2bf043cfc`.
The parent replaced the residual reciprocal with the exact integer algorithm
above, extended the integer exp rounding path to n <= -126 so it covers the
normal/subnormal boundary too, and compares both components of the remainder.
All three requested changes were independently inspected and are present.
For the integer reciprocal, the quotient significand exponent is 126-E as a
biased exponent; normalization on a 2^24 rounded quotient is correct. Integer
remainders cannot overflow their uint64 storage. The special cases are before
the significand arithmetic. No further defect was found in that path.

Repeating the same bounded probe against the revised header produced zero
positive-finite reciprocal differences, zero exp/log errors greater than one
ULP and zero boundary monotonicity failures. Exp max remained one ULP (first
observed maximum input `0xc2ae7135`); sampled log max remained zero ULP.
The new reciprocal deliberately canonicalizes NaNs (including a sqrt-domain
error) to positive `0x7fc00000`, whereas plain/barrier spelling may preserve
payload/sign or yield a negative domain NaN. Raw NaN-bit differences in W-A
are expected and must be reported separately from valid finite arithmetic.
The operation contract excludes exception flags and errno. This is still
host-only evidence; correctly rounded device sqrt and division are unproven.
