# Packet 17 deterministic elementary functions — host preparation closeout

<!-- campaign-closeout -->

## Question and identity

Can the IQ3 compressed model's runtime arithmetic be defined by our own fixed
FP32 operations rather than a platform elementary library? Identity:
`iq3-p17-detmath-v2`; unchanged model weights, BF16 cache/rounding points and
r234-sg32-split4 GEMV order. October 11, 2026, steve-b70s, CPU-only at idle
priority. No GPU, model server, device discovery, host setting or protected
runtime was changed. No device ran.

## Outcome

Host implementation and prepared device gates are accepted as preparation only.
Both GNU and IntelLLVM pass 72/72 parallel/core cases, both fresh host repeats
pass, and both compilers' core bytes match 72/72. V1 versus v2 differs in 68
bytes of qsa-attention-87 and zero bytes in the other 71 fixtures. These are
numerical fixtures, not performance measurements or a quality waiver.

Independent true-value samples stay below one ULP (maximum approximately
0.500000045 for exp and 0.500000011 for log). All 2^32 inputs per function have
host hash rows, exhaustive monotonic checks and glibc sanity comparisons; each
finite discrepancy is at most one ULP. Device hash/fixture gates remain unrun.
The real-model CPU oracle is recorded separately with its explicit coverage
and v1 comparison once complete.

## What worked

Compensated binary32 polynomials with explicit FMA remove the host library
choice from exp/log. A pinned BF16 table removes pow/sin/cos from device RoPE.
Two independent reviewers checked arithmetic special cases and measured
accuracy. Review corrected subnormal tie handling and replaced a reciprocal
Newton probe with an integer-corrected reciprocal. Source review found unchanged
reduction trees, operand order and GEMV arithmetic. Three independent native
gates now prevent same-device equality from masquerading as host equality.

## What failed or remains uncertain

Platform libm was not a reproducible arithmetic definition: v1 matched only
50/72 host/device fixtures and 0/48 first-step layer states. Exp/log are not
claimed correctly rounded everywhere: some measured vectors slightly exceed
0.5 ULP, while meeting the one-ULP target. Sampled high-precision checking plus
exhaustive glibc sanity is not a formal whole-domain proof against real arithmetic.
The FP32 device division/sqrt/FMA lowering, default rsqrt barrier spelling,
actual kernel duration bounds, device/compiler denormal behavior and full-model
device state equality remain unproven. Fingerprints have a collision risk.

The actual read-only loader preflight found missing `libsycl.so.9` and correctly
returned before creating an output or latch. The coordinator must supply oneAPI
libraries; this is not a device attempt or a GPU failure.

## Evidence and patches

- [Precise definition and scope](README.md), [detmath source](detmath.hpp).
- [All fixture results](fixture-comparison.md), [build receipt](build-receipt.json).
- [Independent special-case review](review-special-cases.md),
  [integration review](review-integration.md), [accuracy receipt](accuracy-receipt.json),
  [100-digit worst cases](accuracy-high-precision.json).
- [Exhaustive host hashes](host-hashes-receipt.json),
  [actual fixture arguments](fixture-trace-receipt.json), [RoPE constants](rope-receipt.json).
- [Window commands](WINDOW.md), [loader preflight](loader-preflight.json),
  [retention/restoration](RETENTION.md), [closed v1 arm](DO-NOT-REPEAT.md).

## When to revisit

Run W-A after coordinator admission and library setup; select only an rsqrt
spelling with its required exactness evidence. Run W-B on the final hash-bound
identity, with exhaustive exp/log hashes, all three fixture gates and two fresh
owners. Preserve any failure as evidence, latch it and do not retry. Then use
the frozen v2 CPU oracle for real-model device layer/state comparisons before
integration or promotion. The broader runtime lane remains open.
