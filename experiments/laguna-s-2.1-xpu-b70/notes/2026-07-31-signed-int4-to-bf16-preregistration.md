# Laguna signed-INT4 to BF16 conversion preregistration

Date: 2026-07-31 America/Toronto

Status: **closed at the first static gate**. No model, GPU component, or scored
endpoint run occurred.

## Premise

The protected width-12 target grouped GEMM expands each packed signed INT4
weight through three native instruction blocks before its exact BF16 scale
multiply: nibble extraction (`shr`), construction of an offset BF16 integer
(`bfn`), and subtraction of 136 (`add`). The final value is exactly one of the
integers -8 through 7 in BF16.

Xe vISA has signed bit-field extraction and integer-to-float conversion. If a
single signed four-bit extract can consume the same duplicated-byte region as
the incumbent `shr`, followed by a direct signed-word-to-BF16 conversion, the
three blocks may become two without changing a numeric value or a rounding
boundary. This attacks the dominant B028 loop body rather than endpoint noise.

## Gates

1. Compile an isolated, matched BMG AOT probe. Reject on compiler failure.
2. Inspect final BMG ISA, not source or vISA. Proceed only if the candidate
   preserves the fragment mapping and removes at least one native instruction
   block per converted fragment without adding an equivalent block elsewhere.
3. Before any model build, exhaustively compare all 16 signed INT4 values and
   representative/all BF16 scales through the real fragment operation.
4. Before endpoint scoring, require changed-input component bitwise equality,
   dispatch confinement to the BF16/INT4 width-12 target route, and a component
   timing improvement large enough to plausibly move the endpoint.

The promoted 125.461973 conventional tok/s record remains protected until all
gates pass.

## Result

The signed `bfe` form was accepted by vISA and BMG, but direct signed-word to
BF16 `mov` is illegal: the compiler reports that a BF mixed-mode source must be
BF or FP32. The only legal exact form therefore widened the extracted signed
word to FP32 and multiplied the FP32 integer by the original FP32-widened BF16
scale into a BF16 destination.

That form is numerically promising but statically worse. In a matched GRF128
BMG AOT probe, including the same eight native BF16 scale multiplies:

| form | final instructions | result |
| --- | ---: | --- |
| incumbent `shr+bfn+add`, then scale | 61 | control |
| signed `bfe`, widen, then scale | 72 | +11 / rejected |

The candidate required extra source-region materialization for `bfe`, width
and offset vector setup, and several integer/half/FP32 marshalling moves. Final
ISA, rather than the shorter source sequence, closed the route. The artifact
root is
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/igc-int4-signed-scale-20260731T060721`.

Generic lesson: on Xe2, an apparent two-stage packed-integer conversion is not
a saving unless final mixed-mode legality and region restrictions are checked.
Signed extraction itself was cheap; getting its word result into a BF16 DPAS
fragment was not.
