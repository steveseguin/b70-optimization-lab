# Exact two-card communicator: NaN characterization result

Run on September 15, 2026 (stage `nan-semantics-01`, newest-base image
`sha256:506fcc26…`, no cross-card memory sharing). It compared standard XCCL
all-reduce with four fixed ways of adding the two cards' FP16 values: FP32 or
half precision, with either card's value first. Input was every ordered pair of 21
edge values (quiet and signaling NaNs with several payloads and both signs,
infinities, signed zeros, one, maximum finite, a subnormal), tiled over the four
production shapes `[1|2|512|4096, 5120]`.

**Result: every formulation matches XCCL on every non-NaN result. The only
differences are NaN payload and sign bits, and XCCL itself chooses those
depending on element position. No fixed formula can be bit-identical, so the
preregistered verdict is `no-single-formulation-matches` and stage 05 was not
run.**

## Details

- Both cards agreed with each other at every shape.
- Every mismatch, for all four modes, both ranks and all shapes, was "both
  outputs are NaN, payload or sign differs": 648 of 5,120 elements at one row,
  2,567,965 of 20,971,520 at 4,096 rows. There were zero NaN-versus-number
  mismatches and zero differences in infinities, zeros, subnormals or finite
  values.
- Each mode fails on a different set of elements: no element pair was wrong for
  all four modes. XCCL picks the first operand's NaN at some positions and the
  second's at others, which fits a vectorized kernel with a different operand order in
  its tail or chunk path.
- The stage completed cleanly: confirmed container exit, memory guard exited
  normally, no kernel fault signature and no fault latch.

## What it means

Real model activations are finite; a NaN anywhere already means a broken
answer. Bit-identical NaN payloads matter only for the lab's strict operator
oracle. Continuing needs a user decision to compare NaNs by class (any NaN
equals any NaN, every other bit exact). Without it the communicator stays
blocked on exactness.

Evidence: `/mnt/fast-ai/bench-results/optimization-validation-20260915/nan-semantics-01`,
[verdict copy](../data/2026-09-15-nan-semantics/nan-semantics-verdict.json).
