# Packet 39 CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Can row-local tails remove tiny launches from the quantized Qwen3.8 Flash-Next
arithmetic-v2 plan without disturbing the measured GEMV bodies or adding serial
reductions? Preparation spans October 11–12, 2026, using the packet29 B70 chain
receipts and packet28/33 bodies. This packet performed CPU-only builds, tests and
offline compilation for B70 PCI 0xe223 revision 0. It did not contact a device.
The precise sources, binaries and compiler flags are in
[build-receipt.json](build-receipt.json).

## Outcome

Seven format/shape cases admitted to a future device gate, five rejected by
assembly. The admitted combinations can remove 431 launches/token, with an
estimated old tiny-launch budget of 2.277 ms/token; no net saving was measured
or predicted. No production integration or speed promotion occurred.
Finite/control fixtures pass across two compilers and fresh processes. Poisoned
nonfinite arithmetic is explicitly unqualified. The real CPU plan passed 8/8 tokens and 384/384 layer comparisons in
[real-eight.json](real-eight.json).

## What worked

Keep the measured GEMV geometry and append the exact scalar sequence after its
BF16 store/reload boundary. IQ2 expert checks, expert-down check, HC low
activation, both shared-up activations, attention combine and shared-down
blend/combine pass static admission. Moving the already-existing mixture and
shared gate before shared down removes no required reduction. Atomically setting
only zero sticky error to one preserves previous errors. The corrected rows4
control and independent unrolled-down audit are captured in
[review-assembly.md](review-assembly.md).

## What failed or remains uncertain

Full paired activation adds predicate spills. QKV/convolution and IQ3 checks-only
add a GEMV-loop scheduling instruction and are rejected conservatively. Earlier
iterations used the wrong HC/shared control geometry; they are retained as
negative evidence and superseded by measured rows4 geometry. GCC has 36
nonfinite payload mismatches; finite gates cannot establish general NaN identity.
The CPU overlay proves scalar epilogues in the real host plan, not the native
lane bodies. K0, G4, a full-model device oracle and fresh-window timing remain
pending. No device speed or output claim is made.

## Evidence and patches

[CHAINS.md](CHAINS.md), [CPU receipts](cpu-gates.json),
[assembly gate](assembly-review.json), [retained offline bytes](offline-retention.json),
[independent identity review](identity-review.md), and
[wrapper mock receipts](protocol-tests.json) contain the checks. Implementations
are [fused.hpp](fused.hpp), [fused_sycl.hpp](fused_sycl.hpp), and
[runtime_baseline.hpp](runtime_baseline.hpp). Earlier source patches and iteration
receipts remain under `evidence/`. The offline archive is deliberately retained
with per-member hashes and restoration instructions; compiler/mock scratch is
removed. Weights and original runtime build objects remain external read-only
inputs, pinned by the host receipt. None were copied into Git.

## When to revisit

The coordinator can run [K0/G4](WINDOW.md) on one assigned card, then follow
[INTEGRATE.md](INTEGRATE.md) only for admitted device-identity/timing winners.
Reopen a rejected assembly arm only with new emitted code removing its identified
spill/loop regression while preserving identity. Any nonfinite adoption needs
its own exact gate; do not relax comparisons. The model lane remains open.

## October 12 CPU repair addendum

The coordinator's partial G4 run found an incorrect dense expanded-row stride
check. [Original evidence and screening table](evidence/20261012-g4-row-stride-check/README.md)
retain the failed sixth case and all five completed rows. [Repair review](repair-review.md)
records the corrected metadata-inclusive validation, exact shared G4 host gate,
case-level continuation, unchanged device images and retained assembly rejects.
The repaired K0/G4 binaries are prepared only; new coordinator output names are
`k0-card3b` and `g4-card3b`. This closes the fixture-validation defect; device and
model-level qualification remain open.
