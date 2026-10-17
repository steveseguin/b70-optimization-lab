# Packet52: deterministic free-order GEMV ceiling

CPU preparation for seven expensive production classes, at M=1 and the
engine's two serial M=2 rows. Every candidate has its own fixed arithmetic
order and CPU mirror. The source is independent lab code; earlier lab packets
supply unchanged production controls and format decoders.

- [Source diagnosis and useful-byte bounds](DIAGNOSIS.md).
- [Decision registered before device runs](PREREGISTRATION.md).
- [Coordinator E1/E2/T1/T2 commands](WINDOW.md).
- [Conditional arithmetic-v3 and packet53 design](ARITHMETIC-V3.md).
- [Independent review](REVIEW.md).
- [Preparation evidence](../../../../notes/2026-10-17-own-runtime-packet52.md).

Arithmetic-v3 remains pending until fresh exactness and timing windows pass.
The threshold is at least 120 microseconds per ordinary M=1 layer in each
of two timing owners using the same selected variants. No model oracle is
started and no production dispatch changes in this packet. Both device
qualification and full-model quality remain unmeasured during preparation.

[Variant inventory](VARIANTS.md) explains the five choices and fixed reduction
orders. [CPU build commands](CPU-BUILD.md) reproduce compilation and gates.
The timing windows contain44,100 class-arm records each, with targeted fixture
restores to keep their planned duration at6–12 minutes. No interpolation,
model-speed estimate or automatic production adoption is part of the result.
